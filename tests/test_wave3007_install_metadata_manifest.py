"""Each installed Sublime package member must preserve source and emitted ZIP metadata."""
import tempfile
import unittest
import zipfile
from pathlib import Path
from tools.package_sublime import package_files, create_package, verify_package, FIXED_DATE, MEMBERS


class InstalledManifestRoundtrip(unittest.TestCase):
    def test_manifest_metadata_and_source_bytes_hold_across_two_rebuilds(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "Oreslang.sublime-package"
            files = package_files()
            baseline = None
            for _ in range(2):
                create_package(files, dest)
                verify_package(files, dest)
                content = dest.read_bytes()
                if baseline is None:
                    baseline = content
                else:
                    self.assertEqual(content, baseline)
                with zipfile.ZipFile(dest) as archive:
                    self.assertEqual(archive.namelist(), sorted(MEMBERS))
                    self.assertEqual(archive.comment, b"")
                    for name in MEMBERS:
                        with self.subTest(name=name):
                            info = archive.getinfo(name)
                            self.assertEqual(info.date_time, FIXED_DATE)
                            self.assertEqual(info.external_attr, 0o100644 << 16)
                            self.assertEqual(info.create_system, 3)
                            self.assertEqual(info.compress_type, zipfile.ZIP_STORED)
                            self.assertEqual(info.extra, b"")
                            self.assertEqual(info.comment, b"")
                            self.assertEqual(archive.read(name), files[name])


if __name__ == "__main__":
    unittest.main()
