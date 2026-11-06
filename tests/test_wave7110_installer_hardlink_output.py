"""Installer ZIP creation must not overwrite a hardlinked source or sentinel."""
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("wave7110_install", ROOT / "tools" / "package_sublime.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class Wave7110InstallerHardlinks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = package.package_files()

    def test_external_file_hardlink_cannot_be_truncated_by_zip(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "trusted"
            source.write_bytes(b"do not modify this file")
            archive = root / "Oreslang.sublime-package"
            archive.hardlink_to(source)
            with self.assertRaisesRegex(ValueError, "hardlinked package destination"):
                package.create_package(self.files, archive)
            self.assertEqual(source.read_bytes(), b"do not modify this file")
            archive.unlink()
            package.create_package(self.files, archive)
            package.verify_package(self.files, archive)

    def test_staged_source_member_hardlink_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "Main.sublime-menu"
            original = self.files["Main.sublime-menu"]
            source.write_bytes(original)
            archive = root / "output.sublime-package"
            archive.hardlink_to(source)
            with patch.object(package, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "hardlinked package destination"):
                    package.create_package(self.files, archive)
                self.assertEqual(source.read_bytes(), original)
                archive.unlink()
                package.create_package(self.files, archive)
                package.verify_package(self.files, archive)


if __name__ == "__main__":
    unittest.main()
