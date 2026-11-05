"""Release ZIP payload integrity: valid names and metadata do not authorize altered bytes."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_sublime_package import build, verify


class Wave242ReleasePayloadIdentity(unittest.TestCase):
    def test_modified_payload_with_original_metadata_is_denied_then_rebuild_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive_path = Path(tmp) / "Oreslang.sublime-package"
            build(archive_path)
            verify(archive_path)

            with zipfile.ZipFile(archive_path, "r") as source:
                entries = [(info, source.read(info.filename))
                           for info in source.infolist()]
            self.assertIn("oreslang.py", [info.filename for info, _ in entries])
            with zipfile.ZipFile(archive_path, "w") as dest:
                for info, payload in entries:
                    if info.filename == "oreslang.py":
                        payload += b"\n# unreviewed payload appended\n"
                    dest.writestr(info, payload, compress_type=info.compress_type)

            with self.assertRaisesRegex(ValueError, "differs from source"):
                verify(archive_path)

            build(archive_path)
            verify(archive_path)


if __name__ == "__main__":
    unittest.main()
