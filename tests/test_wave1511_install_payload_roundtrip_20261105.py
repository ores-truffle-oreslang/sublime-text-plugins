"""Installable editor package source-byte authority and deterministic recovery."""
import tempfile
import unittest
import zipfile
from pathlib import Path
from tools.package_sublime import create_package, package_files, verify_package, MEMBERS


class InstallableArchiveRoundtrip(unittest.TestCase):
    def test_unreviewed_allowlisted_payload_corruption_rejected_then_repaired(self):
        files = package_files()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Oreslang.sublime-package"
            create_package(files, path)
            verify_package(files, path)
            original = path.read_bytes()
            with zipfile.ZipFile(path, "r") as archive:
                entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
            with zipfile.ZipFile(path, "w") as archive:
                for info, data in entries:
                    if info.filename == "oreslang.py":
                        data += b"\n# unreviewed payload\n"
                    archive.writestr(info, data)
            with self.assertRaisesRegex(ValueError, "verification failed"):
                verify_package(files, path)
            create_package(files, path)
            self.assertEqual(path.read_bytes(), original)
            verify_package(files, path)

    def test_canonical_member_names_and_bytes_survive_repeated_installable_builds(self):
        files = package_files()
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "first.sublime-package"
            second = Path(temp) / "second.sublime-package"
            create_package(files, first)
            create_package(files, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), sorted(MEMBERS))
                for name in MEMBERS:
                    with self.subTest(member=name):
                        self.assertEqual(archive.read(name),files[name])
            verify_package(files, second)


if __name__ == "__main__":
    unittest.main()
