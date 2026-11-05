"""Unreviewed source-side files cannot change an installable package."""
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "package_sublime.py"
spec = importlib.util.spec_from_file_location("wave610_allowlist", SCRIPT)
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class Wave610PackageQuarantine(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for name in package.MEMBERS:
            (self.root / name).write_bytes((ROOT / name).read_bytes())
        self.archive = self.root / "out" / "Oreslang.sublime-package"

    def test_stray_preview_and_nested_script_never_enter_package(self):
        before = package.package_files(self.root)
        package.create_package(before, self.archive)
        baseline = self.archive.read_bytes()

        (self.root / "Preview.sublime-syntax").write_bytes(b"unreviewed preview")
        (self.root / "tests").mkdir()
        (self.root / "tests" / "untrusted.py").write_text("raise RuntimeError('never package')")
        (self.root / ".github").mkdir()
        (self.root / ".github" / "secrets.txt").write_text("not a release member")
        after = package.package_files(self.root)

        self.assertEqual(after, before)
        package.create_package(after, self.archive)
        self.assertEqual(self.archive.read_bytes(), baseline)
        package.verify_package(after, self.archive)
        with zipfile.ZipFile(self.archive) as archive:
            self.assertEqual(archive.namelist(), sorted(package.MEMBERS))
            self.assertFalse(any(name.startswith((".github/", "tests/")) for name in archive.namelist()))

    def test_snapshot_bytes_are_stable_after_original_input_is_mutated(self):
        snapshot = package.package_files(self.root)
        package.create_package(snapshot, self.archive)
        first = self.archive.read_bytes()
        source = self.root / "Main.sublime-menu"
        source.write_bytes(source.read_bytes() + b" \n")
        package.create_package(snapshot, self.archive)
        self.assertEqual(self.archive.read_bytes(), first)
        self.assertNotEqual(package.package_files(self.root), snapshot)
        package.verify_package(snapshot, self.archive)


if __name__ == "__main__":
    unittest.main()
