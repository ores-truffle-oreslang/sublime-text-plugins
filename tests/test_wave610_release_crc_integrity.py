"""Archive central directory corruption must fail verification, not silently pass."""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from scripts import build_sublime_package as release


class ReleaseCentralDirectoryCrcIntegrity(unittest.TestCase):
    def test_crc_tamper_rejected_then_clean_rebuild_restores_release(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "Oreslang.sublime-package"
            pristine_digest = release.build(dest)
            release.verify(dest)
            binary = bytearray(dest.read_bytes())
            central = binary.find(b"PK\x01\x02")
            self.assertGreaterEqual(central, 0, "expected ZIP central-directory header")
            # ZIP central-directory fixed header: CRC-32 field begins at offset 16.
            binary[central + 16] ^= 0x01
            dest.write_bytes(binary)
            with self.assertRaises(zipfile.BadZipFile):
                release.verify(dest)
            restored_digest = release.build(dest)
            release.verify(dest)
            self.assertEqual(restored_digest, pristine_digest)
            self.assertEqual(hashlib.sha256(dest.read_bytes()).hexdigest(), restored_digest)


if __name__ == "__main__":
    unittest.main()
