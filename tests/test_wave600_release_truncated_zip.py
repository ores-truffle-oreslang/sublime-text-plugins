"""An incomplete release ZIP must never be accepted as an installable artifact."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_sublime_package import build, verify


class ReleaseTruncationWave600(unittest.TestCase):
    def test_truncated_central_directory_is_rejected_then_rebuild_restores_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "out.sublime-package"
            expected_hash = build(path)
            complete = path.read_bytes()
            self.assertGreater(len(complete), 22)
            verify(path)

            for amount in (1, 8, 22):
                with self.subTest(bytes_removed=amount):
                    path.write_bytes(complete[:-amount])
                    with self.assertRaises((ValueError, zipfile.BadZipFile)):
                        verify(path)

            rebuilt_hash = build(path)
            self.assertEqual(rebuilt_hash, expected_hash)
            self.assertEqual(path.read_bytes(), complete)
            verify(path)


if __name__ == "__main__":
    unittest.main()
