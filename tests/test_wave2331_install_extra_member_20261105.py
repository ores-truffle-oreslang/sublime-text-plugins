"""Source-owned Sublime archive allowlist negative and restoration controls."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.package_sublime import create_package, package_files, verify_package


class Wave2331InstallAllowlist(unittest.TestCase):
    def test_extra_editor_script_denied_then_clean_package_restored(self):
        files = package_files()
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "Oreslang.sublime-package"
            create_package(files, package)
            verify_package(files, package)
            baseline = package.read_bytes()
            with zipfile.ZipFile(package, "a") as archive:
                archive.writestr("unreviewed-plugin.py", b"print('unreviewed')\n")
            with self.assertRaisesRegex(ValueError, "unexpected package files"):
                verify_package(files, package)
            create_package(files, package)
            self.assertEqual(package.read_bytes(), baseline)
            verify_package(files, package)

    def test_metadata_entry_outside_allowlist_never_becomes_an_editor_module(self):
        files = package_files()
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "Oreslang.sublime-package"
            create_package(files, package)
            baseline = package.read_bytes()
            with zipfile.ZipFile(package, "a") as archive:
                archive.writestr("tests/diagnostic-exfiltration.py", b"pass\n")
            with self.assertRaisesRegex(ValueError, "unexpected package files"):
                verify_package(files, package)
            create_package(files, package)
            self.assertEqual(package.read_bytes(), baseline)


if __name__ == "__main__":
    unittest.main()
