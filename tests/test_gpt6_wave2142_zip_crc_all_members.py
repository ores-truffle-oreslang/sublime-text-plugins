"""Actual installed ZIP CRC admission and deterministic repair for every package member.

Mutate only stored payload bytes, not the filename or checksum metadata.
"""
import importlib.util
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("wave2142_crc_packager", ROOT / "tools/package_sublime.py")
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class ZipMemberCrcTamperMatrix(unittest.TestCase):
    def test_one_byte_corruption_in_each_reviewed_member_rejected_then_recovered(self):
        files = packager.package_files()
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "Oreslang.sublime-package"
            packager.create_package(files, destination)
            canonical = destination.read_bytes()
            packager.verify_package(files, destination)
            for member in packager.MEMBERS:
                with self.subTest(member=member):
                    with zipfile.ZipFile(destination, "r") as archive:
                        info = archive.getinfo(member)
                        self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                        self.assertGreater(info.file_size, 0)
                        _, _, _, _, _, _, _, _, _, name_len, extra_len = struct.unpack_from(
                            "<IHHHHHIIIHH", canonical, info.header_offset)
                        offset = info.header_offset + 30 + name_len + extra_len
                    hostile = bytearray(canonical)
                    hostile[offset] ^= 0x01
                    destination.write_bytes(hostile)
                    # CRC metadata remains unchanged, so zipfile must refuse
                    # the forged bytes before a verified install can proceed.
                    with self.assertRaises(zipfile.BadZipFile):
                        packager.verify_package(files, destination)
                    packager.create_package(files, destination)
                    self.assertEqual(destination.read_bytes(), canonical)
                    packager.verify_package(files, destination)


if __name__ == "__main__":
    unittest.main()
