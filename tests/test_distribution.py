"""Tests for deterministic and fail-closed Sublime package exports."""
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "package_sublime.py"
spec = importlib.util.spec_from_file_location("sublime_packager", SCRIPT)
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class SublimePackageDistributionTests(unittest.TestCase):
    def test_archive_is_reproducible_and_allowlisted(self):
        files = packager.package_files()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "Oreslang.sublime-package"
            packager.create_package(files, dest)
            packager.verify_package(files, dest)
            first = dest.read_bytes()
            packager.create_package(files, dest)
            self.assertEqual(first, dest.read_bytes())

    def test_missing_source_or_symlink_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in packager.MEMBERS:
                source = packager.ROOT / name
                (root / name).write_bytes(source.read_bytes())
            (root / "Oreslang.sublime-syntax").write_bytes(b"bad grammar")
            with self.assertRaisesRegex(ValueError, "source.oreslang"):
                packager.package_files(root)

    def test_archive_member_injection_is_rejected(self):
        files = packager.package_files()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "Oreslang.sublime-package"
            packager.create_package(files, dest)
            with zipfile.ZipFile(dest, "a") as archive:
                archive.writestr("../untrusted.py", "print('oops')")
            with self.assertRaisesRegex(ValueError, "unexpected"):
                packager.verify_package(files, dest)


if __name__ == "__main__":
    unittest.main()
