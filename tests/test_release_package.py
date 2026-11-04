import hashlib
import pathlib
import tempfile
import unittest
import zipfile
from scripts.build_sublime_package import build, verify, FILES, ROOT

class PackageReleaseTest(unittest.TestCase):
    def test_two_independent_builds_are_byte_identical_and_allowlisted(self):
        with tempfile.TemporaryDirectory() as folder:
            a=pathlib.Path(folder)/"first.sublime-package"
            b=pathlib.Path(folder)/"second.sublime-package"
            self.assertEqual(build(a),build(b))
            self.assertEqual(a.read_bytes(),b.read_bytes())
            with zipfile.ZipFile(a) as z:
                self.assertEqual(z.namelist(),sorted(FILES))
                self.assertNotIn("Preview.sublime-syntax",z.namelist())
                self.assertNotIn("syntax_test_oreslang.ores",z.namelist())
                self.assertIn("oreslang.py",z.namelist())
                self.assertIn("Oreslang.sublime-syntax",z.namelist())
                self.assertEqual(z.read("oreslang.py"),(ROOT/"oreslang.py").read_bytes())
            verify(b)
    def test_modified_file_is_not_accepted_as_original_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            p=pathlib.Path(folder)/"corrupt.sublime-package"
            build(p)
            with zipfile.ZipFile(p,"a") as z:
                z.writestr("unexpected.ores", "should not ship")
            with self.assertRaisesRegex(ValueError, "unexpected"):
                verify(p)

if __name__ == "__main__":
    unittest.main()
