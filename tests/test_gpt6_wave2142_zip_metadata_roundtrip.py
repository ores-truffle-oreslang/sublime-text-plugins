"""Canonical ZIP verification must reject per-member metadata-only tampering."""
import copy
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wave2142_packager", ROOT / "tools/package_sublime.py")
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class ZipMetadataRoundtrip(unittest.TestCase):
    def test_each_allowlisted_member_rejects_three_metadata_only_mutations(self):
        files = packager.package_files()
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "Oreslang.sublime-package"
            packager.create_package(files, destination)
            canonical = destination.read_bytes()
            packager.verify_package(files, destination)
            for target in packager.MEMBERS:
                for mutation in ("compression", "date", "extra"):
                    with self.subTest(member=target, mutation=mutation):
                        with zipfile.ZipFile(destination, "r") as archive:
                            original = [(copy.copy(info), archive.read(info.filename))
                                        for info in archive.infolist()]
                        with zipfile.ZipFile(destination, "w") as archive:
                            for info, content in original:
                                if info.filename == target:
                                    if mutation == "compression":
                                        info.compress_type = zipfile.ZIP_DEFLATED
                                    elif mutation == "date":
                                        info.date_time = (2024, 1, 2, 3, 4, 6)
                                    else:
                                        info.extra = b"\x01\x00\x00\x00"
                                archive.writestr(info, content)
                        with self.assertRaisesRegex(ValueError, "Package verification failed"):
                            packager.verify_package(files, destination)
                        packager.create_package(files, destination)
                        self.assertEqual(destination.read_bytes(), canonical)
                        packager.verify_package(files, destination)


if __name__ == "__main__":
    unittest.main()
