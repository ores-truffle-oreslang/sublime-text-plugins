"""Two source-owned publisher implementations must preserve each review-listed file.

Their archive formats intentionally differ: release ZIP_DEFLATED versus
installed-package ZIP_STORED; byte-identical archives are not expected.
"""
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.build_sublime_package import build, verify, FILES, ROOT
from tools.package_sublime import (
    MEMBERS, FIXED_DATE, package_files, create_package, verify_package,
)


class IndependentPublisherIntegrity(unittest.TestCase):
    def test_both_archives_preserve_bytes_with_distinct_compression(self):
        self.assertEqual(set(FILES), set(MEMBERS))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)
            release = path / "release.sublime-package"
            installed = path / "installed.sublime-package"
            sources = package_files()
            self.assertEqual(set(sources), set(FILES))
            build(release)
            create_package(sources, installed)
            verify(release)
            verify_package(sources, installed)
            with zipfile.ZipFile(release) as a, zipfile.ZipFile(installed) as b:
                expected_names = sorted(FILES)
                self.assertEqual(a.namelist(), expected_names)
                self.assertEqual(b.namelist(), expected_names)
                for name in expected_names:
                    with self.subTest(name=name):
                        source = (ROOT / name).read_bytes()
                        self.assertEqual(a.read(name), source)
                        self.assertEqual(b.read(name), source)
                        self.assertEqual(a.getinfo(name).compress_type, zipfile.ZIP_DEFLATED)
                        self.assertEqual(b.getinfo(name).compress_type, zipfile.ZIP_STORED)
                        self.assertEqual(a.getinfo(name).date_time, FIXED_DATE)
                        self.assertEqual(b.getinfo(name).date_time, FIXED_DATE)
            self.assertNotEqual(release.read_bytes(), installed.read_bytes())


if __name__ == "__main__":
    unittest.main()
