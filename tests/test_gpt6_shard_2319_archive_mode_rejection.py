"""A byte-identical payload with tampered POSIX mode is not a trusted release."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts import build_sublime_package as release


class ReleaseArchiveModeAdmissionTest(unittest.TestCase):
    def test_modified_file_mode_is_rejected_and_clean_rebuild_is_identical(self):
        with tempfile.TemporaryDirectory() as directory:
            pristine = Path(directory) / "pristine.sublime-package"
            modified = Path(directory) / "mode-tamper.sublime-package"
            expected_digest = release.build(pristine)
            with zipfile.ZipFile(pristine) as original:
                members = [(entry, original.read(entry.filename))
                           for entry in original.infolist()]
            with zipfile.ZipFile(modified, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for entry, content in members:
                    metadata = zipfile.ZipInfo(entry.filename, entry.date_time)
                    metadata.create_system = entry.create_system
                    metadata.external_attr = entry.external_attr
                    metadata.compress_type = zipfile.ZIP_DEFLATED
                    if entry.filename == "Main.sublime-menu":
                        metadata.external_attr = 0o100755 << 16
                    archive.writestr(metadata, content, compress_type=zipfile.ZIP_DEFLATED,
                                     compresslevel=9)
            with zipfile.ZipFile(modified) as tampered:
                self.assertEqual(tampered.namelist(), sorted(release.FILES))
                for entry, content in members:
                    self.assertEqual(tampered.read(entry.filename), content)
            with self.assertRaisesRegex(ValueError, "nonportable archive file mode"):
                release.verify(modified)
            self.assertEqual(release.build(modified), expected_digest)
            release.verify(modified)
            self.assertEqual(modified.read_bytes(), pristine.read_bytes())


if __name__ == "__main__":
    unittest.main()
