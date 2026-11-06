"""A package destination hardlinked to unrelated caller data must fail closed.

Host ZIP publisher behavior only; no compiler/backend guest execution.
"""
import os
import tempfile
import unittest
from pathlib import Path

from tools import package_sublime as publisher


class ForeignSentinelHardlinkAdmission(unittest.TestCase):
    def test_foreign_hardlink_never_truncates_caller_owned_sentinel(self):
        reviewed = publisher.package_files()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dest = root / "sub" / "Oreslang.sublime-package"
            dest.parent.mkdir()
            sentinel = root / "private-caller-owned.txt"
            original = b"preserve foreign, not-reviewed bytes\x00\xff\n"
            sentinel.write_bytes(original)
            os.link(sentinel, dest)
            self.assertEqual(os.stat(dest).st_ino, os.stat(sentinel).st_ino)

            for _ in range(3):
                with self.assertRaisesRegex(ValueError, "hardlinked package destination"):
                    publisher.create_package(reviewed, dest)
                self.assertEqual(sentinel.read_bytes(), original)
                self.assertEqual(dest.read_bytes(), original)
                self.assertEqual(os.stat(dest).st_ino, os.stat(sentinel).st_ino)

            dest.unlink()
            publisher.create_package(reviewed, dest)
            publisher.verify_package(reviewed, dest)
            canonical = dest.read_bytes()
            self.assertNotEqual(os.stat(dest).st_ino, os.stat(sentinel).st_ino)
            self.assertEqual(sentinel.read_bytes(), original)
            dest.unlink()
            publisher.create_package(reviewed, dest)
            publisher.verify_package(reviewed, dest)
            self.assertEqual(dest.read_bytes(), canonical)
            self.assertEqual(sentinel.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
