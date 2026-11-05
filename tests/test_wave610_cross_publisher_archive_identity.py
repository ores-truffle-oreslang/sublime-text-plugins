"""Cross-publisher release/install ZIP byte contract; host-side package tests only."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts import build_sublime_package as release
from tools import package_sublime as install


class CrossPublisherArchiveIdentity(unittest.TestCase):
    def test_two_independent_builders_ship_identical_allowlisted_source_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            release_zip = Path(folder) / "release.sublime-package"
            install_zip = Path(folder) / "install.sublime-package"
            files = install.package_files()
            self.assertEqual(set(files), set(release.FILES))
            digest = release.build(release_zip)
            self.assertEqual(len(digest), 64)
            install.create_package(files, install_zip)
            release.verify(release_zip)
            install.verify_package(files, install_zip)
            with zipfile.ZipFile(release_zip) as a, zipfile.ZipFile(install_zip) as b:
                self.assertEqual(a.namelist(), b.namelist())
                for name in sorted(files):
                    with self.subTest(name=name):
                        self.assertEqual(a.read(name), files[name])
                        self.assertEqual(b.read(name), files[name])
                        self.assertEqual(a.getinfo(name).compress_type, zipfile.ZIP_DEFLATED)
                        self.assertEqual(b.getinfo(name).compress_type, zipfile.ZIP_STORED)
            # Different published containers must never masquerade as byte-identical artifacts.
            self.assertNotEqual(release_zip.read_bytes(), install_zip.read_bytes())


if __name__ == "__main__":
    unittest.main()
