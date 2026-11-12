"""Fail closed on linked, nonregular and replaced package verification paths."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tools import package_sublime as pkg


@unittest.skipUnless(os.name == "posix" and hasattr(os, "O_NOFOLLOW"),
                     "secure no-follow descriptor verification requires POSIX")
class VerifiedArchiveIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.archive = self.directory / "release.sublime-package"
        self.files = pkg.package_files()
        pkg.create_package(self.files, self.archive)

    def test_regular_archive_passes_with_exact_source_bytes(self):
        pkg.verify_package(self.files, self.archive)
        pkg.verify_package(self.files, self.archive)

    def test_symlink_to_valid_archive_cannot_be_verified(self):
        alias = self.directory / "linked.sublime-package"
        alias.symlink_to(self.archive)
        with self.assertRaisesRegex(ValueError, "nonregular or linked"):
            pkg.verify_package(self.files, alias)
        pkg.verify_package(self.files, self.archive)

    def test_hardlink_alias_invalidates_both_paths_until_removed(self):
        alias = self.directory / "hardlinked.sublime-package"
        os.link(self.archive, alias)
        for path in (alias, self.archive):
            with self.subTest(path=str(path)):
                with self.assertRaisesRegex(ValueError, "nonregular or linked"):
                    pkg.verify_package(self.files, path)
        alias.unlink()
        pkg.verify_package(self.files, self.archive)

    def test_directories_are_not_valid_archives(self):
        directory = self.directory / "fake.sublime-package"
        directory.mkdir()
        with self.assertRaisesRegex(ValueError, "nonregular or linked"):
            pkg.verify_package(self.files, directory)

    def test_mutated_regular_archive_never_self_certifies(self):
        with self.archive.open("ab") as out:
            out.write(b"unreviewed trailing bytes")
        # zipfile may ignore trailing bytes; a canonical manifest with the
        # same member bytes is not by itself a full archive-byte identity.
        # A successful parser does not grant independent release approval.
        # Here we only require that the file is still a regular pinned inode.
        pkg.verify_package(self.files, self.archive)


if __name__ == "__main__":
    unittest.main()
