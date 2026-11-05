"""Verify source-owned Sublime release archive integrity at Unicode nested destinations."""
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.build_sublime_package import build, verify, FILES, ROOT


class UnicodeOutputPath(unittest.TestCase):
    def test_nested_unicode_destinations_preserve_identical_member_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            left = root / "atō-α" / "nested" / "release.sublime-package"
            right = root / "emoji-💠" / "deep" / "release.sublime-package"
            first = build(left)
            second = build(right)
            self.assertEqual(first, second)
            self.assertEqual(left.read_bytes(), right.read_bytes())
            self.assertEqual(first, hashlib.sha256(left.read_bytes()).hexdigest())
            for archive_path in (left, right):
                with self.subTest(path=archive_path.parent.name):
                    verify(archive_path)
                    with zipfile.ZipFile(archive_path) as archive:
                        self.assertEqual(archive.namelist(), sorted(FILES))
                        for name in FILES:
                            self.assertEqual(archive.read(name), (ROOT / name).read_bytes())
                        self.assertTrue(all(not name.startswith("tests/") for name in archive.namelist()))


if __name__ == "__main__":
    unittest.main()
