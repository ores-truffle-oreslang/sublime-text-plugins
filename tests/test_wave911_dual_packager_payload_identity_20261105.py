"""Both independently implemented package paths must ship exactly reviewed bytes.

Host-only package verification; it does not prove compiler or editor guest execution.
"""
import hashlib
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.build_sublime_package import FILES, ROOT, build, verify
from tools.package_sublime import create_package, package_files, verify_package


class DualPackagerPayloadIdentity(unittest.TestCase):
    def test_installed_and_release_archives_share_exact_six_source_blobs(self):
        files = package_files()
        self.assertEqual(set(files), set(FILES))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            release = root / "release.sublime-package"
            installed = root / "installed.sublime-package"
            release_hash = build(release)
            create_package(files, installed)
            verify(release)
            verify_package(files, installed)
            self.assertEqual(release_hash, hashlib.sha256(release.read_bytes()).hexdigest())
            with zipfile.ZipFile(release) as a, zipfile.ZipFile(installed) as b:
                self.assertEqual(a.namelist(), sorted(FILES))
                self.assertEqual(b.namelist(), sorted(FILES))
                for name in sorted(FILES):
                    with self.subTest(name=name):
                        expected = (ROOT / name).read_bytes()
                        self.assertEqual(a.read(name), expected)
                        self.assertEqual(b.read(name), expected)
                        self.assertEqual(files[name], expected)
                        self.assertEqual(a.getinfo(name).compress_type, zipfile.ZIP_DEFLATED)
                        self.assertEqual(b.getinfo(name).compress_type, zipfile.ZIP_STORED)

    def test_repeated_independent_builds_preserve_respective_archive_bytes(self):
        files = package_files()
        with tempfile.TemporaryDirectory() as temp:
            a, b = (Path(temp) / name for name in ("first.sublime-package", "second.sublime-package"))
            self.assertEqual(build(a), build(b))
            self.assertEqual(a.read_bytes(), b.read_bytes())
            create_package(files, a)
            create_package(files, b)
            self.assertEqual(a.read_bytes(), b.read_bytes())
            verify_package(files, a)
            verify_package(files, b)


if __name__ == "__main__":
    unittest.main()
