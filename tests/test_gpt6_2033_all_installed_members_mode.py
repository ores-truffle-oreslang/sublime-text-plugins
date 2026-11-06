"""Every allowlisted installable ZIP member carries canonical UNIX file type and mode."""
import copy
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "package_sublime.py"
spec = importlib.util.spec_from_file_location("gpt6_2033_package", SCRIPT)
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class InstalledAllMembersMode(unittest.TestCase):
    def test_every_member_rejects_filetype_spoof_with_canonical_restore(self):
        files = packager.package_files()
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "Oreslang.sublime-package"
            packager.create_package(files, output)
            canonical = output.read_bytes()
            packager.verify_package(files, output)
            for target in packager.MEMBERS:
                with self.subTest(member=target):
                    with zipfile.ZipFile(output, "r") as original:
                        members = [(copy.copy(info), original.read(info.filename))
                                   for info in original.infolist()]
                    with zipfile.ZipFile(output, "w") as mutated:
                        for info, content in members:
                            if info.filename == target:
                                info.create_system = 3
                                info.external_attr = 0o120777 << 16
                            mutated.writestr(info, content)
                    with self.assertRaisesRegex(ValueError, "Package verification failed"):
                        packager.verify_package(files, output)
                    packager.create_package(files, output)
                    self.assertEqual(output.read_bytes(), canonical)
                    packager.verify_package(files, output)


if __name__ == "__main__":
    unittest.main()
