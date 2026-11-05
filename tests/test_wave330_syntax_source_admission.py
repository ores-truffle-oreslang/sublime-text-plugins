"""Sublime package source admission: syntax identity must survive inputs, not aliases."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "package_sublime.py"
spec = importlib.util.spec_from_file_location("wave330_sublime_source", SCRIPT)
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class SyntaxSourceAdmission(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in package.MEMBERS:
            (self.root / name).write_bytes((package.ROOT / name).read_bytes())
        self.assertEqual(set(package.package_files(self.root)), set(package.MEMBERS))

    def test_source_scope_marker_must_be_present(self):
        target = self.root / "Oreslang.sublime-syntax"
        original = target.read_bytes()
        self.assertIn(b"source.oreslang", original)
        target.write_bytes(original.replace(b"source.oreslang", b"source.untrusted"))
        with self.assertRaisesRegex(ValueError, "source.oreslang"):
            package.package_files(self.root)
        target.write_bytes(original)
        self.assertEqual(package.package_files(self.root)["Oreslang.sublime-syntax"], original)

    def test_ores_extension_marker_must_be_present(self):
        target = self.root / "Oreslang.sublime-syntax"
        original = target.read_bytes()
        self.assertIn(b"  - ores", original)
        corrupted = original.replace(b"  - ores", b"  - changed", 1)
        self.assertNotIn(b"  - ores", corrupted)
        target.write_bytes(corrupted)
        with self.assertRaisesRegex(ValueError, "sublime"):
            package.package_files(self.root)
        target.write_bytes(original)
        self.assertEqual(package.package_files(self.root)["Oreslang.sublime-syntax"], original)


if __name__ == "__main__":
    unittest.main()
