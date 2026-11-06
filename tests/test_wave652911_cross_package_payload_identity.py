"""Independent cross-publisher member identity and metadata positive/negative controls."""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts import build_sublime_package as release
from tools import package_sublime as install


class CrossPublisherPackageIdentity(unittest.TestCase):
    def test_both_publishers_share_source_bytes_but_require_own_canonical_metadata(self):
        source = install.package_files()
        self.assertEqual(set(source), set(install.MEMBERS))
        self.assertEqual(set(source), set(release.FILES))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            release_zip = root / "release.sublime-package"
            install_zip = root / "installed.sublime-package"
            release_digest = release.build(release_zip)
            install.create_package(source, install_zip)
            release.verify(release_zip)
            install.verify_package(source, install_zip)
            first_install = install_zip.read_bytes()
            first_release = release_zip.read_bytes()
            self.assertEqual(hashlib.sha256(first_release).hexdigest(), release_digest)
            with zipfile.ZipFile(release_zip) as a, zipfile.ZipFile(install_zip) as b:
                self.assertEqual(a.namelist(), b.namelist())
                for name in sorted(source):
                    self.assertEqual(a.read(name), source[name], name)
                    self.assertEqual(b.read(name), source[name], name)
                    for info in (a.getinfo(name), b.getinfo(name)):
                        self.assertEqual(info.date_time, (1980, 1, 1, 0, 0, 0))
                        self.assertEqual(info.create_system, 3)
                        self.assertEqual(info.external_attr, 0o100644 << 16)
                    self.assertEqual(a.getinfo(name).compress_type, zipfile.ZIP_DEFLATED)
                    self.assertEqual(b.getinfo(name).compress_type, zipfile.ZIP_STORED)
            # A self-consistent untrusted install snapshot must fail when checked
            # against canonical source, without changing the release artifact.
            forged = dict(source)
            forged["Default.sublime-commands"] += b"\nUNREVIEWED\n"
            install.create_package(forged, install_zip)
            install.verify_package(forged, install_zip)
            with self.assertRaisesRegex(ValueError, "verification failed"):
                install.verify_package(source, install_zip)
            release.verify(release_zip)
            self.assertEqual(release_zip.read_bytes(), first_release)
            install.create_package(source, install_zip)
            install.verify_package(source, install_zip)
            self.assertEqual(install_zip.read_bytes(), first_install)
            self.assertEqual(release.build(release_zip), release_digest)


if __name__ == "__main__":
    unittest.main()
