"""Installed package ZIP payload CRC tamper must reject and rebuild exactly."""
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.package_sublime import (
    MEMBERS, create_package, package_files, verify_package,
)


class InstallArchiveCorruptionTests(unittest.TestCase):
    def test_payload_mutation_fails_crc_and_canonical_rebuild_recovers(self):
        files = package_files()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "Oreslang.sublime-package"
            create_package(files, target)
            canonical = target.read_bytes()
            verify_package(files, target)
            for member in (sorted(MEMBERS)[0], sorted(MEMBERS)[-1]):
                with self.subTest(member=member):
                    with zipfile.ZipFile(target) as archive:
                        info = archive.getinfo(member)
                        self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                        self.assertGreater(info.file_size, 0)
                        offset = info.header_offset
                    changed = bytearray(canonical)
                    name_size, extra_size = struct.unpack_from("<HH", changed, offset + 26)
                    payload_offset = offset + 30 + name_size + extra_size
                    changed[payload_offset] ^= 1
                    target.write_bytes(changed)
                    with self.assertRaises((zipfile.BadZipFile, ValueError)):
                        verify_package(files, target)
                    create_package(files, target)
                    self.assertEqual(target.read_bytes(), canonical)
                    verify_package(files, target)


if __name__ == "__main__":
    unittest.main()
