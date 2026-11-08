"""Adversarial atomic-publisher rollback and staging collision tests.

This suite is layered on the security publisher implementation in PR #143;
it exercises synthetic archive bytes, not source compiler or release attestation.
"""
from __future__ import annotations

import errno
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from tools import package_sublime as publisher


@unittest.skipUnless(os.name == "posix", "secure dir_fd publisher is POSIX-only")
class PublisherRollbackTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.destination = self.directory / "release.sublime-package"
        self.previous = b"EXISTING USER RELEASE MUST SURVIVE A FAILURE\n"
        self.destination.write_bytes(self.previous)
        self.files = {name: b"synthetic-allowlisted-fixture:" + name.encode("ascii")
                      for name in publisher.MEMBERS}

    def assert_unchanged(self):
        self.assertEqual(self.destination.read_bytes(), self.previous)
        self.assertEqual(list(self.directory.glob(".oreslang-release-*.tmp")), [])

    def test_fsync_failure_cleans_stage_and_preserves_previous_artifact(self):
        with patch.object(publisher.os, "fsync",
                          side_effect=OSError(errno.EIO, "injected fsync failure")):
            with self.assertRaisesRegex(OSError, "injected fsync failure"):
                publisher.create_package(self.files, self.destination)
        self.assert_unchanged()

    def test_atomic_replace_failure_cleans_stage_and_preserves_previous_artifact(self):
        with patch.object(publisher.os, "replace",
                          side_effect=OSError(errno.EACCES, "injected replace denial")):
            with self.assertRaisesRegex(OSError, "injected replace denial"):
                publisher.create_package(self.files, self.destination)
        self.assert_unchanged()

    def test_zip_member_write_error_is_atomic_and_cleans_stage(self):
        original = zipfile.ZipFile.writestr
        writes = 0

        def abort_second_write(archive, info, data):
            nonlocal writes
            writes += 1
            if writes == 2:
                raise OSError(errno.EIO, "injected mid-archive write failure")
            return original(archive, info, data)

        with patch.object(publisher.zipfile.ZipFile, "writestr", abort_second_write):
            with self.assertRaisesRegex(OSError, "injected mid-archive write failure"):
                publisher.create_package(self.files, self.destination)
        self.assertEqual(writes, 2)
        self.assert_unchanged()

    def test_eight_colliding_stage_names_do_not_clobber_an_existing_file(self):
        token = "f" * 32
        occupied = self.directory / (".oreslang-release-" + token + ".tmp")
        sentinel = b"NEVER CLOBBER AN UNRELATED STAGING FILE\n"
        occupied.write_bytes(sentinel)
        with patch.object(publisher.secrets, "token_hex", return_value=token) as random_name:
            with self.assertRaisesRegex(ValueError, "cannot reserve unique staging file"):
                publisher.create_package(self.files, self.destination)
        self.assertEqual(random_name.call_count, 8)
        self.assertEqual(self.destination.read_bytes(), self.previous)
        self.assertEqual(occupied.read_bytes(), sentinel)
        self.assertEqual(list(self.directory.glob(".oreslang-release-*.tmp")), [occupied])

    def test_staged_archive_name_replaced_during_zip_write_fails_closed(self):
        original_zip = zipfile.ZipFile
        planted = b"ATTACKER-CONTROLLED ZIP BYTES\n"

        def replace_visible_stage(stream, *args, **kwargs):
            stage_paths = list(self.directory.glob(".oreslang-release-*.tmp"))
            self.assertEqual(len(stage_paths), 1)
            stage_paths[0].unlink()
            stage_paths[0].write_bytes(planted)
            return original_zip(stream, *args, **kwargs)

        with patch.object(publisher.zipfile, "ZipFile", side_effect=replace_visible_stage):
            with self.assertRaisesRegex(ValueError, "staged archive pathname replaced"):
                publisher.create_package(self.files, self.destination)
        self.assert_unchanged()

    def test_staged_archive_name_swapped_for_symlink_cannot_publish_external_file(self):
        external = self.directory / "external-sentinel"
        external.write_bytes(b"EXTERNAL FILE MUST REMAIN UNTOUCHED\n")
        original_zip = zipfile.ZipFile

        def install_stage_symlink(stream, *args, **kwargs):
            stage_paths = list(self.directory.glob(".oreslang-release-*.tmp"))
            self.assertEqual(len(stage_paths), 1)
            stage_paths[0].unlink()
            try:
                stage_paths[0].symlink_to(external)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unsupported")
            return original_zip(stream, *args, **kwargs)

        with patch.object(publisher.zipfile, "ZipFile", side_effect=install_stage_symlink):
            with self.assertRaisesRegex(ValueError, "staged archive pathname replaced"):
                publisher.create_package(self.files, self.destination)
        self.assert_unchanged()
        self.assertEqual(external.read_bytes(), b"EXTERNAL FILE MUST REMAIN UNTOUCHED\n")

    def test_staged_archive_hardlink_alias_is_rejected(self):
        original_zip = zipfile.ZipFile
        outside_alias = self.directory / "outside-alias"
        def hardlink_staged_file(stream, *args, **kwargs):
            stages = list(self.directory.glob(".oreslang-release-*.tmp"))
            self.assertEqual(len(stages), 1)
            os.link(stages[0], outside_alias)
            return original_zip(stream, *args, **kwargs)
        try:
            with patch.object(publisher.zipfile, "ZipFile", side_effect=hardlink_staged_file):
                with self.assertRaisesRegex(ValueError, "staged archive pathname replaced"):
                    publisher.create_package(self.files, self.destination)
        finally:
            outside_alias.unlink(missing_ok=True)
        self.assert_unchanged()

    def test_success_after_failed_publish_still_produces_verified_deterministic_bytes(self):
        with patch.object(publisher.os, "replace",
                          side_effect=OSError(errno.EACCES, "simulated denial")):
            with self.assertRaises(OSError):
                publisher.create_package(self.files, self.destination)
        self.assert_unchanged()
        publisher.create_package(self.files, self.destination)
        publisher.verify_package(self.files, self.destination)
        first = self.destination.read_bytes()
        self.assertTrue(first.startswith(b"PK"))
        publisher.create_package(self.files, self.destination)
        publisher.verify_package(self.files, self.destination)
        self.assertEqual(self.destination.read_bytes(), first)
        self.assertEqual(list(self.directory.glob(".oreslang-release-*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
