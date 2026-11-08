"""Post-publication identity checks for the pinned directory-fd ZIP writer.

These are deterministic race injections; they prove the writer does not
report success after an observed namespace/inode substitution. They do
not claim to eliminate arbitrary attacks after the final readback.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import package_sublime as publisher


@unittest.skipUnless(os.name == "posix", "POSIX directory-fd publication only")
class PostPublicationIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.parent = self.root / "publish"
        self.parent.mkdir()
        self.dest = self.parent / "release.sublime-package"
        self.dest.write_bytes(b"OLD PACKAGE\n")
        self.sentinel = self.root / "unrelated.txt"
        self.sentinel.write_bytes(b"DO NOT ALTER\n")
        self.files = publisher.package_files()

    def assert_no_stage_left(self):
        self.assertEqual(list(self.root.rglob(".oreslang-release-*.tmp")), [])
        self.assertEqual(self.sentinel.read_bytes(), b"DO NOT ALTER\n")

    def test_after_replace_leaf_symlink_cannot_report_success(self):
        actual = os.replace

        def redirect_leaf(*args, **kwargs):
            result = actual(*args, **kwargs)
            self.dest.unlink()
            try:
                self.dest.symlink_to(self.sentinel)
            except (OSError, NotImplementedError):
                self.skipTest("file symlinks unsupported")
            return result

        with patch.object(publisher.os, "replace", side_effect=redirect_leaf):
            with self.assertRaisesRegex(ValueError, "symlinked package destination"):
                publisher.create_package(self.files, self.dest)
        self.assertTrue(self.dest.is_symlink())
        self.assert_no_stage_left()

    def test_after_replace_unrelated_regular_inode_cannot_report_success(self):
        actual = os.replace

        def substitute_unrelated_regular_file(*args, **kwargs):
            result = actual(*args, **kwargs)
            self.dest.unlink()
            self.dest.write_bytes(b"FOREIGN REGULAR FILE\n")
            return result

        with patch.object(publisher.os, "replace", side_effect=substitute_unrelated_regular_file):
            with self.assertRaisesRegex(ValueError, "package output changed after atomic replace"):
                publisher.create_package(self.files, self.dest)
        self.assertEqual(self.dest.read_bytes(), b"FOREIGN REGULAR FILE\n")
        self.assert_no_stage_left()

    def test_after_replace_parent_replaced_by_new_real_directory_cannot_report_success(self):
        actual = os.replace
        moved = self.root / "original-published-directory"

        def replace_parent(*args, **kwargs):
            result = actual(*args, **kwargs)
            self.parent.rename(moved)
            self.parent.mkdir()
            return result

        with patch.object(publisher.os, "replace", side_effect=replace_parent):
            with self.assertRaisesRegex(ValueError, "package destination parent moved during staging"):
                publisher.create_package(self.files, self.dest)
        self.assertFalse(self.dest.exists())
        publisher.verify_package(self.files, moved / self.dest.name)
        self.assert_no_stage_left()

    def test_normal_atomic_publish_has_verified_bytes_and_repeatable_output(self):
        publisher.create_package(self.files, self.dest)
        publisher.verify_package(self.files, self.dest)
        first = self.dest.read_bytes()
        publisher.create_package(self.files, self.dest)
        publisher.verify_package(self.files, self.dest)
        self.assertEqual(self.dest.read_bytes(), first)
        self.assert_no_stage_left()


if __name__ == "__main__":
    unittest.main()
