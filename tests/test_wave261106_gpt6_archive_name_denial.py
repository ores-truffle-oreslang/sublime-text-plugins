"""Reject unreviewed path aliases in both independent Sublime ZIP publishers."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.package_sublime import create_package, verify_package, package_files
from scripts.build_sublime_package import build, verify


class ArchiveMemberNameDenial(unittest.TestCase):
    def test_both_packagers_reject_unreviewed_member_aliases_and_restore(self):
        reviewed_files = package_files()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            install = root / "install.sublime-package"
            release = root / "release.sublime-package"
            create_package(reviewed_files, install)
            release_digest = build(release)
            canonical_install = install.read_bytes()
            canonical_release = release.read_bytes()
            for member_name in ("../oreslang.py", "Ｏreslang.py", "tests/hidden.ores"):
                with self.subTest(member=member_name):
                    with zipfile.ZipFile(install, "a") as package:
                        package.writestr(member_name, b"unreviewed payload")
                    with self.assertRaisesRegex(ValueError, "unexpected package files"):
                        verify_package(reviewed_files, install)
                    create_package(reviewed_files, install)
                    verify_package(reviewed_files, install)
                    self.assertEqual(install.read_bytes(), canonical_install)

                    with zipfile.ZipFile(release, "a") as package:
                        package.writestr(member_name, b"unreviewed payload")
                    with self.assertRaisesRegex(ValueError, "unexpected, missing or duplicate"):
                        verify(release)
                    self.assertEqual(build(release), release_digest)
                    self.assertEqual(release.read_bytes(), canonical_release)


if __name__ == "__main__":
    unittest.main()
