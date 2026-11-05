"""ZIP member type and mode are part of the reviewed installable payload identity."""
import copy
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "package_sublime.py"
spec = importlib.util.spec_from_file_location("wave2310_packager", SCRIPT)
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class InstallableMemberTypeAdmission(unittest.TestCase):
    def test_symlink_style_and_writable_zip_members_rejected_then_restored(self):
        files = packager.package_files()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Oreslang.sublime-package"
            packager.create_package(files, path)
            canonical_bytes = path.read_bytes()
            packager.verify_package(files, path)

            for altered_type, altered_mode in [
                (3, 0o120777 << 16),  # Unix symlink masquerading as source
                (3, 0o100666 << 16),  # regular file but group/world writable
                (0, 0o100644 << 16),  # DOS identity masquerading as Unix mode
            ]:
                with self.subTest(system=altered_type, attributes=altered_mode):
                    with zipfile.ZipFile(path, "r") as archive:
                        entries = [(copy.copy(info), archive.read(info.filename))
                                   for info in archive.infolist()]
                    with zipfile.ZipFile(path, "w") as archive:
                        for info, payload in entries:
                            if info.filename == "oreslang.py":
                                info.create_system = altered_type
                                info.external_attr = altered_mode
                            archive.writestr(info, payload)

                    # A false-positive here means matching bytes conceal a
                    # different ZIP member identity in the installed package.
                    with self.assertRaisesRegex(ValueError, "Package verification failed"):
                        packager.verify_package(files, path)

                    packager.create_package(files, path)
                    self.assertEqual(canonical_bytes, path.read_bytes())
                    packager.verify_package(files, path)


if __name__ == "__main__":
    unittest.main()
