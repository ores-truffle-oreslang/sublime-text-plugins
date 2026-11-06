"""Cross-publisher byte identity and independent corruption denial.

Host-only tests exercise both real ZIP publishers; no guest compiler execution.
"""
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts import build_sublime_package as release
from tools import package_sublime as install


class Wave2031DualPublisherSourceIdentity(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.installer = root / 'install.sublime-package'
        self.released = root / 'release.sublime-package'
        self.reviewed = install.package_files()
        install.create_package(self.reviewed, self.installer)
        install.verify_package(self.reviewed, self.installer)
        self.digest = release.build(self.released)
        release.verify(self.released)

    def test_every_member_has_identical_extracted_source_bytes_across_publishers(self):
        self.assertEqual(sorted(release.FILES), sorted(install.MEMBERS))
        with zipfile.ZipFile(self.installer) as installed, zipfile.ZipFile(self.released) as published:
            for archive in (installed, published):
                self.assertEqual(archive.namelist(), sorted(release.FILES))
            for name in sorted(release.FILES):
                with self.subTest(source_member=name):
                    actual = self.reviewed[name]
                    self.assertEqual(actual, (release.ROOT / name).read_bytes())
                    self.assertEqual(installed.read(name), actual)
                    self.assertEqual(published.read(name), actual)
        self.assertNotEqual(self.installer.read_bytes(), self.released.read_bytes())

    def test_each_publisher_rejects_mutated_extracted_member_and_recovers(self):
        for destination, verify, rebuild, reason in (
            (self.installer,
             lambda p: install.verify_package(self.reviewed, p),
             lambda p: install.create_package(self.reviewed, p),
             'Package verification failed'),
            (self.released, release.verify, release.build, 'archive differs from source'),
        ):
            with self.subTest(publisher=destination.name):
                original = destination.read_bytes()
                with zipfile.ZipFile(destination) as archive:
                    members = [(info, archive.read(info.filename)) for info in archive.infolist()]
                with zipfile.ZipFile(destination, 'w') as damaged:
                    for info, data in members:
                        if info.filename == 'oreslang.py':
                            data = b'# altered but syntactically inert bytes\n' + data
                        damaged.writestr(info, data)
                with self.assertRaisesRegex(ValueError, reason):
                    verify(destination)
                rebuild(destination)
                verify(destination)
                self.assertEqual(destination.read_bytes(), original)
        self.assertEqual(release.build(self.released), self.digest)


if __name__ == '__main__':
    unittest.main()
