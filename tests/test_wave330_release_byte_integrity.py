"""Deterministic Sublime release ZIP verification must compare member bytes."""
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_sublime_package.py"
spec = importlib.util.spec_from_file_location("wave330_sublime_release", SCRIPT)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleasePayloadIntegrity(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / "Oreslang.sublime-package"
        self.original_digest = release.build(self.output)
        release.verify(self.output)

    def test_modified_payload_rejected_even_with_original_portable_metadata(self):
        for victim in ("oreslang.py", "Oreslang.sublime-settings"):
            with self.subTest(victim=victim):
                release.build(self.output)
                with zipfile.ZipFile(self.output, "r") as archive:
                    contents = [(entry, archive.read(entry.filename)) for entry in archive.infolist()]
                with zipfile.ZipFile(self.output, "w") as modified:
                    for old, payload in contents:
                        info = zipfile.ZipInfo(old.filename, date_time=old.date_time)
                        info.create_system = old.create_system
                        info.external_attr = old.external_attr
                        info.compress_type = old.compress_type
                        if old.filename == victim:
                            payload += b"\n# synthetic corruption\n"
                        modified.writestr(info, payload, compress_type=info.compress_type)
                with self.assertRaisesRegex(ValueError, "archive differs from source"):
                    release.verify(self.output)
                self.assertEqual(release.build(self.output), self.original_digest)
                release.verify(self.output)


if __name__ == "__main__":
    unittest.main()
