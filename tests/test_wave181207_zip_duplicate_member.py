"""Reject duplicate and unexpected archive members, then rebuild exactly."""
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

from tools.package_sublime import MEMBERS, create_package, package_files, verify_package


class ArchiveMemberAdmissionTests(unittest.TestCase):
    def test_duplicate_or_unexpected_member_never_verifies(self):
        files = package_files()
        with tempfile.TemporaryDirectory() as folder:
            archive_path = Path(folder) / "Oreslang.sublime-package"
            create_package(files, archive_path)
            original = archive_path.read_bytes()
            verify_package(files, archive_path)
            for extra_name, payload in (
                (sorted(MEMBERS)[-1], files[sorted(MEMBERS)[-1]]),
                ("unreviewed/../payload", b"unreviewed"),
            ):
                with self.subTest(member=extra_name):
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        with zipfile.ZipFile(archive_path, "a") as archive:
                            archive.writestr(extra_name, payload)
                    with self.assertRaisesRegex(ValueError, "unexpected package files"):
                        verify_package(files, archive_path)
                    create_package(files, archive_path)
                    self.assertEqual(archive_path.read_bytes(), original)
                    verify_package(files, archive_path)


if __name__ == "__main__":
    unittest.main()
