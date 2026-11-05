"""Release byte identity must not depend on the caller's current directory."""
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
from scripts.build_sublime_package import build, verify, FILES

class ReleaseCwdReproducibility(unittest.TestCase):
    def test_two_working_directories_produce_identical_release_bytes(self):
        cwd = Path.cwd()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            one = root / "one" / "Oreslang.sublime-package"
            two = root / "two" / "Oreslang.sublime-package"
            one.parent.mkdir()
            two.parent.mkdir()
            try:
                os.chdir(one.parent)
                digest_one = build(one)
                verify(one)
                os.chdir(two.parent)
                digest_two = build(two)
                verify(two)
            finally:
                os.chdir(cwd)
            self.assertEqual(digest_one, digest_two)
            self.assertEqual(one.read_bytes(), two.read_bytes())
            with zipfile.ZipFile(two) as archive:
                self.assertEqual(archive.namelist(), sorted(FILES))

if __name__ == "__main__":
    unittest.main()
