"""No ZIP writer may follow a caller-supplied release output symlink."""
import tempfile
import unittest
from pathlib import Path

from scripts.build_sublime_package import build, verify


class ReleaseOutputDestinationTrust(unittest.TestCase):
    def test_symlinked_archive_destination_does_not_overwrite_target(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            sentinel = root / "outside-source.txt"
            sentinel.write_bytes(b"independent and preserved\n")
            destination = root / "Oreslang.sublime-package"
            try:
                destination.symlink_to(sentinel)
            except (NotImplementedError, OSError):
                self.skipTest("symlinks unavailable")
            with self.assertRaisesRegex(ValueError, "symlinked release destination"):
                build(destination)
            self.assertTrue(destination.is_symlink())
            self.assertEqual(sentinel.read_bytes(), b"independent and preserved\n")

            fresh = root / "safe.sublime-package"
            digest = build(fresh)
            self.assertEqual(len(digest), 64)
            verify(fresh)
            self.assertNotEqual(fresh.read_bytes(), sentinel.read_bytes())


if __name__ == "__main__":
    unittest.main()
