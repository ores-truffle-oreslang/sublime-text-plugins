"""Adversarial leaf swaps must not let ZIP creation overwrite an unrelated inode."""
from __future__ import annotations

import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools import package_sublime as publisher


class AtomicSublimeDestinationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dest = self.root / "package.sublime-package"
        self.external = self.root / "independent-user-sentinel.txt"
        self.external.write_bytes(b"NEVER OVERWRITE THIS FILE\n")
        self.dest.write_bytes(b"previous package")
        self.files = publisher.package_files()

    def assert_clean_staging(self):
        self.assertEqual(list(self.root.glob(".oreslang-release-*.tmp")), [])

    def swap_during_archive_open(self, swap):
        original_zip = zipfile.ZipFile

        def swap_then_open(*args, **kwargs):
            swap()
            return original_zip(*args, **kwargs)

        with patch.object(publisher.zipfile, "ZipFile", side_effect=swap_then_open):
            publisher.create_package(self.files, self.dest)

    def test_symlink_swap_is_refused_without_touching_target(self):
        def insert_symlink():
            self.dest.unlink()
            try:
                self.dest.symlink_to(self.external)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable on this host")

        with self.assertRaisesRegex(ValueError, "symlinked package destination"):
            self.swap_during_archive_open(insert_symlink)
        self.assertEqual(self.external.read_bytes(), b"NEVER OVERWRITE THIS FILE\n")
        self.assertTrue(self.dest.is_symlink())
        self.assert_clean_staging()

    def test_hardlink_swap_is_refused_without_touching_target(self):
        def insert_hardlink():
            self.dest.unlink()
            try:
                os.link(self.external, self.dest)
            except (OSError, NotImplementedError):
                self.skipTest("hardlinks unavailable on this host")

        with self.assertRaisesRegex(ValueError, "hardlinked package destination"):
            self.swap_during_archive_open(insert_hardlink)
        self.assertEqual(self.external.read_bytes(), b"NEVER OVERWRITE THIS FILE\n")
        self.assertEqual(self.dest.read_bytes(), self.external.read_bytes())
        self.assert_clean_staging()

    def test_writer_exception_keeps_existing_artifact_and_cleans_stage(self):
        old_bytes = self.dest.read_bytes()
        with patch.object(publisher.zipfile, "ZipFile", side_effect=OSError("simulated write failure")):
            with self.assertRaisesRegex(OSError, "simulated write failure"):
                publisher.create_package(self.files, self.dest)
        self.assertEqual(self.dest.read_bytes(), old_bytes)
        self.assert_clean_staging()

    def test_parent_symlinks_and_dotdot_are_denied_before_staging(self):
        external_dir = self.root / "external"
        external_dir.mkdir()
        sentinel = external_dir / "package.sublime-package"
        sentinel.write_bytes(b"EXTERNAL SENTINEL\n")
        redirect = self.root / "redirect"
        try:
            redirect.symlink_to(external_dir, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("directory symlinks unavailable")
        for destination in (
            redirect / sentinel.name,
            redirect / "nested" / sentinel.name,
        ):
            with self.subTest(path=str(destination)):
                with self.assertRaisesRegex(ValueError, "symlinked package destination parent"):
                    publisher.create_package(self.files, destination)
                self.assertEqual(sentinel.read_bytes(), b"EXTERNAL SENTINEL\n")
                self.assertFalse((external_dir / "nested").exists())
        with self.assertRaisesRegex(ValueError, "noncanonical package destination parent"):
            publisher.create_package(
                self.files, self.root / "new" / ".." / "redirect" / sentinel.name
            )
        self.assertEqual(sentinel.read_bytes(), b"EXTERNAL SENTINEL\n")
        self.assert_clean_staging()

    def test_successful_atomic_rebuild_remains_byte_identical(self):
        publisher.create_package(self.files, self.dest)
        publisher.verify_package(self.files, self.dest)
        first = self.dest.read_bytes()
        self.assertTrue(first.startswith(b"PK"))
        self.assertNotEqual(first, b"previous package")
        publisher.create_package(self.files, self.dest)
        publisher.verify_package(self.files, self.dest)
        self.assertEqual(self.dest.read_bytes(), first)
        self.assertEqual(self.external.read_bytes(), b"NEVER OVERWRITE THIS FILE\n")
        self.assert_clean_staging()


if __name__ == "__main__":
    unittest.main()
