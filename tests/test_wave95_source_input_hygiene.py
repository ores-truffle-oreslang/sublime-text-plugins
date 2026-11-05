"""No unreviewed filesystem alias or malformed plugin source in a package."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "package_sublime.py"
spec = importlib.util.spec_from_file_location("wave95_source_hygiene", SCRIPT)
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class Wave95SourceInputHygiene(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in package.MEMBERS:
            (self.root / name).write_bytes((package.ROOT / name).read_bytes())
        self.assertEqual(set(package.package_files(self.root)), set(package.MEMBERS))

    def test_symlinked_python_source_is_not_admitted(self):
        source = self.root / "oreslang.py"
        source.unlink()
        try:
            source.symlink_to(package.ROOT / "oreslang.py")
        except (OSError, NotImplementedError):
            self.skipTest("filesystem does not support symbolic links")
        with self.assertRaisesRegex(ValueError, "symlinked"):
            package.package_files(self.root)

    def test_missing_required_member_is_not_admitted(self):
        (self.root / "Main.sublime-menu").unlink()
        with self.assertRaisesRegex(ValueError, "Missing"):
            package.package_files(self.root)

    def test_malformed_plugin_syntax_is_refused_before_packaging(self):
        (self.root / "oreslang.py").write_bytes(b"def cannot_compile(:\\n")
        with self.assertRaises(SyntaxError):
            package.package_files(self.root)


if __name__ == "__main__":
    unittest.main()
