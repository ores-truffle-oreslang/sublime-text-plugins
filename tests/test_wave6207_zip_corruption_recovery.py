"""Installed Sublime package integrity: mutate stored source payload and recover."""
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("wave6207_install_package", ROOT / "tools" / "package_sublime.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class Wave6207StoredPackageCRC(unittest.TestCase):
    def test_corrupted_stored_payload_fails_crc_and_fresh_rebuild_recovers(self):
        files = package.package_files()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "Oreslang.sublime-package"
            package.create_package(files, output)
            package.verify_package(files, output)
            original = output.read_bytes()

            # ZIP_STORED preserves the bytes of the canonical grammar, so a
            # same-size mutation proves that metadata/filename checks alone
            # cannot approve a corrupted archive.
            needle = b"source.oreslang"
            self.assertIn(needle, files["Oreslang.sublime-syntax"])
            self.assertIn(needle, original)
            corrupted = original.replace(needle, b"source.oresxlang", 1)
            self.assertNotEqual(corrupted, original)
            output.write_bytes(corrupted)
            with self.assertRaises((zipfile.BadZipFile, ValueError)):
                package.verify_package(files, output)

            package.create_package(files, output)
            self.assertEqual(output.read_bytes(), original)
            package.verify_package(files, output)

    def test_reordered_member_archive_rejected_even_when_payloads_match(self):
        files = package.package_files()
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "Oreslang.sublime-package"
            with zipfile.ZipFile(output, "w") as archive:
                for name in reversed(sorted(files)):
                    archive.writestr(name, files[name])
            with self.assertRaisesRegex(ValueError, "unexpected"):
                package.verify_package(files, output)
            package.create_package(files, output)
            package.verify_package(files, output)


if __name__ == "__main__":
    unittest.main()
