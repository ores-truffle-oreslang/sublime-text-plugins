"""Every installed Sublime ZIP member must reject writable permission metadata."""
import copy
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "package_sublime.py"
spec = importlib.util.spec_from_file_location("gpt6_2033_permission_packager", SCRIPT)
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class PackageMemberPermissionMatrix(unittest.TestCase):
    def test_each_allowlisted_member_refuses_group_and_world_write_bits(self):
        files = packager.package_files()
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "Oreslang.sublime-package"
            packager.create_package(files, archive_path)
            canonical = archive_path.read_bytes()
            packager.verify_package(files, archive_path)

            for name in packager.MEMBERS:
                for mode in (0o100664, 0o100646):
                    with self.subTest(member=name, mode=oct(mode)):
                        with zipfile.ZipFile(archive_path, "r") as original:
                            entries = [(copy.copy(info), original.read(info.filename))
                                       for info in original.infolist()]
                        with zipfile.ZipFile(archive_path, "w") as changed:
                            for info, payload in entries:
                                if info.filename == name:
                                    info.external_attr = mode << 16
                                changed.writestr(info, payload)
                        # Payload is unchanged; only unsafe ZIP mode bits differ.
                        with self.assertRaisesRegex(ValueError, "Package verification failed"):
                            packager.verify_package(files, archive_path)
                        packager.create_package(files, archive_path)
                        self.assertEqual(archive_path.read_bytes(), canonical)
                        packager.verify_package(files, archive_path)


if __name__ == "__main__":
    unittest.main()
