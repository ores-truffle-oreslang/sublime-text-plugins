"""Directory-swap adversarial tests for the pinned dir_fd ZIP publisher."""
from __future__ import annotations

import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools import package_sublime as publisher


@unittest.skipUnless(os.name == "posix", "POSIX directory-fd tests only")
class PinnedDirectorySwapTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.parent = self.root / "safe"
        self.parent.mkdir()
        self.moved = self.root / "moved"
        self.external = self.root / "external"
        self.external.mkdir()
        self.dest = self.parent / "package.sublime-package"
        self.dest.write_bytes(b"OLD PACKAGE")
        self.sentinel = self.external / self.dest.name
        self.sentinel.write_bytes(b"EXTERNAL SENTINEL\n")
        self.files = publisher.package_files()
        self.swapped = False

    def swap_parent(self):
        self.assertFalse(self.swapped, "attack must occur exactly once")
        self.parent.rename(self.moved)
        try:
            self.parent.symlink_to(self.external, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("directory symlinks unavailable")
        self.swapped = True

    def assert_external_unchanged(self):
        self.assertEqual(self.sentinel.read_bytes(), b"EXTERNAL SENTINEL\n")
        self.assertEqual(list(self.root.rglob(".oreslang-release-*.tmp")), [])

    def test_parent_swapped_after_preflight_before_directory_open_is_refused(self):
        original = publisher._secure_parent_fd

        def swap_before_open(dest):
            self.swap_parent()
            return original(dest)

        with patch.object(publisher, "_secure_parent_fd", side_effect=swap_before_open):
            with self.assertRaisesRegex(ValueError, "symlinked package destination parent"):
                publisher.create_package(self.files, self.dest)
        self.assertEqual((self.moved / self.dest.name).read_bytes(), b"OLD PACKAGE")
        self.assert_external_unchanged()

    def test_parent_swapped_during_archive_staging_is_refused(self):
        original = zipfile.ZipFile

        def swap_during_open(*args, **kwargs):
            self.swap_parent()
            return original(*args, **kwargs)

        with patch.object(publisher.zipfile, "ZipFile", side_effect=swap_during_open):
            with self.assertRaisesRegex(ValueError, "symlinked package destination parent"):
                publisher.create_package(self.files, self.dest)
        self.assertEqual((self.moved / self.dest.name).read_bytes(), b"OLD PACKAGE")
        self.assert_external_unchanged()

    def test_parent_swapped_after_final_validation_cannot_redirect_replace(self):
        original = os.replace

        def swap_just_before_replace(*args, **kwargs):
            self.swap_parent()
            self.assertEqual(kwargs["src_dir_fd"], kwargs["dst_dir_fd"])
            return original(*args, **kwargs)

        with patch.object(publisher.os, "replace", side_effect=swap_just_before_replace):
            with self.assertRaisesRegex(ValueError, "symlinked package destination parent"):
                publisher.create_package(self.files, self.dest)
        # The package still lands only in the original pinned directory inode.
        # It must NOT report successful publication at the now-redirected path.
        publisher.verify_package(self.files, self.moved / self.dest.name)
        self.assert_external_unchanged()

    def test_grandparent_swap_during_archive_staging_is_refused(self):
        deeper = self.parent / "nested"
        deeper.mkdir()
        dest = deeper / self.dest.name
        dest.write_bytes(b"OLD NESTED")
        outside = self.external / "nested"
        outside.mkdir()
        nested_sentinel = outside / dest.name
        nested_sentinel.write_bytes(b"EXTERNAL NESTED\n")
        original = zipfile.ZipFile

        def move_grandparent(*args, **kwargs):
            self.swap_parent()
            return original(*args, **kwargs)

        with patch.object(publisher.zipfile, "ZipFile", side_effect=move_grandparent):
            with self.assertRaisesRegex(ValueError, "symlinked package destination parent"):
                publisher.create_package(self.files, dest)
        self.assertEqual(nested_sentinel.read_bytes(), b"EXTERNAL NESTED\n")
        self.assertEqual((self.moved / "nested" / dest.name).read_bytes(), b"OLD NESTED")
        self.assert_external_unchanged()

    def test_unsupported_directory_fd_provider_fails_closed(self):
        with patch.object(publisher.os, "supports_dir_fd", set()):
            with self.assertRaisesRegex(ValueError, "secure directory-relative"):
                publisher.create_package(self.files, self.dest)
        self.assertEqual(self.dest.read_bytes(), b"OLD PACKAGE")
        self.assert_external_unchanged()


if __name__ == "__main__":
    unittest.main()
