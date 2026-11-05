"""Reproducible release package metadata cannot be silently changed."""
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_sublime_package.py"
spec = importlib.util.spec_from_file_location("wave95_release", SCRIPT)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class Wave95ReleaseMetadataFences(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / "Oreslang.sublime-package"
        digest = release.build(self.output)
        self.assertEqual(len(digest), 64)
        release.verify(self.output)

    def replace_one_metadata_field(self, field):
        with zipfile.ZipFile(self.output, "r") as source:
            entries = [(info, source.read(info.filename)) for info in source.infolist()]
        with zipfile.ZipFile(self.output, "w") as dest:
            for i, (old, payload) in enumerate(entries):
                info = zipfile.ZipInfo(old.filename, date_time=old.date_time)
                info.create_system = old.create_system
                info.external_attr = old.external_attr
                info.compress_type = old.compress_type
                if i == 0 and field == "timestamp":
                    info.date_time = (2026, 11, 5, 0, 0, 0)
                if i == 0 and field == "mode":
                    info.external_attr = 0o100777 << 16
                dest.writestr(info, payload, compress_type=info.compress_type)

    def test_timestamp_mutation_rejected_despite_identical_content(self):
        self.replace_one_metadata_field("timestamp")
        with self.assertRaisesRegex(ValueError, "timestamp"):
            release.verify(self.output)

    def test_executable_mode_mutation_rejected_despite_identical_content(self):
        self.replace_one_metadata_field("mode")
        with self.assertRaisesRegex(ValueError, "mode"):
            release.verify(self.output)


if __name__ == "__main__":
    unittest.main()
