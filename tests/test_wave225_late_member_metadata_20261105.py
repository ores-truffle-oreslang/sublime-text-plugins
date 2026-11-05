"""Sublime package verification must inspect metadata of every ZIP entry."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_sublime_package import FILES, build, verify


class FinalMemberMetadataTest(unittest.TestCase):
    def test_foreign_system_on_final_member_denied_with_identical_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "Oreslang.sublime-package"
            expected = build(output)
            final_name = sorted(FILES)[-1]
            with zipfile.ZipFile(output, "r") as archive:
                entries = [(entry, archive.read(entry.filename))
                           for entry in archive.infolist()]
            with zipfile.ZipFile(output, "w") as archive:
                for previous, payload in entries:
                    entry = zipfile.ZipInfo(previous.filename, previous.date_time)
                    entry.create_system = (0 if previous.filename == final_name
                                           else previous.create_system)
                    entry.external_attr = previous.external_attr
                    entry.compress_type = previous.compress_type
                    archive.writestr(entry, payload, compress_type=entry.compress_type)
            with self.assertRaisesRegex(ValueError, "mode"):
                verify(output)
            self.assertEqual(build(output), expected)
            verify(output)


if __name__ == "__main__":
    unittest.main()
