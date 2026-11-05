"""Reject altered allowlisted member bytes even with valid ZIP CRC and metadata."""
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.build_sublime_package import build, verify, FILES, ROOT


class ArchiveCorruptionRecovery(unittest.TestCase):
    def test_valid_crc_cannot_authorize_modified_allowlisted_member(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trusted = root / "trusted.sublime-package"
            altered = root / "altered.sublime-package"
            digest = build(trusted)
            original = trusted.read_bytes()
            with zipfile.ZipFile(trusted, "r") as source, zipfile.ZipFile(altered, "w") as dest:
                for entry in source.infolist():
                    payload = source.read(entry.filename)
                    if entry.filename == "oreslang.py":
                        payload += b"\n# forged extra source despite correct ZIP CRC\n"
                    dest.writestr(entry, payload, compress_type=entry.compress_type)
            with zipfile.ZipFile(altered) as archive:
                self.assertEqual(archive.namelist(), sorted(FILES))
                self.assertEqual(archive.testzip(), None)
                self.assertNotEqual(archive.read("oreslang.py"), (ROOT / "oreslang.py").read_bytes())
            with self.assertRaisesRegex(ValueError, "archive differs from source"):
                verify(altered)
            self.assertEqual(build(altered), digest)
            self.assertEqual(altered.read_bytes(), original)
            verify(altered)


if __name__ == "__main__":
    unittest.main()
