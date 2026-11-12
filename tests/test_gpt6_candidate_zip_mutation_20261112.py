"""Adversarial pinned candidate ZIP input validation; all bytes are synthetic."""
from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import audit_source_bound_candidate_v1 as auditor


class CandidateZipReadIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.data = b"synthetic-candidate-container" * 8
        self.path = self.root / "candidate.zip"
        self.path.write_bytes(self.data)

    def test_ordinary_single_linked_candidate_still_reads_exact_bytes(self):
        self.assertEqual(auditor._read_zip_bytes(self.path), self.data)

    def test_in_checkout_symlinked_parent_is_refused(self):
        (self.root / "real").mkdir()
        (self.root / "real" / "candidate.zip").write_bytes(self.data)
        (self.root / "alias").symlink_to(self.root / "real", target_is_directory=True)
        with self.assertRaisesRegex(auditor.AuditDenied, "ZIP_SYMLINK_OR_PATH_INVALID"):
            auditor._read_zip_bytes(self.root / "alias" / "candidate.zip")

    def test_same_size_in_place_edit_during_read_is_refused(self):
        original_read = os.read
        touched = [False]

        def mutate_after_first_read(fd, size):
            chunk = original_read(fd, size)
            if chunk and not touched[0]:
                touched[0] = True
                with self.path.open("r+b") as target:
                    target.write(b"Z")
                    target.flush()
                    os.fsync(target.fileno())
            return chunk

        with patch.object(auditor.os, "read", side_effect=mutate_after_first_read):
            with self.assertRaisesRegex(auditor.AuditDenied, "ZIP_MUTATED_DURING_READ"):
                auditor._read_zip_bytes(self.path)
        self.assertTrue(touched[0])
        self.assertEqual(self.path.stat().st_size, len(self.data))

    def test_disappearing_path_fails_closed(self):
        original_stat = os.stat
        calls = [0]

        def disappear_after_read(path, *args, **kwargs):
            if str(path) == str(self.path):
                calls[0] += 1
                if calls[0] == 1:
                    self.path.unlink()
                    raise FileNotFoundError(str(path))
            return original_stat(path, *args, **kwargs)

        with patch.object(auditor.os, "stat", side_effect=disappear_after_read):
            with self.assertRaisesRegex(auditor.AuditDenied, "ZIP_MUTATED_DURING_READ"):
                auditor._read_zip_bytes(self.path)


if __name__ == "__main__":
    unittest.main()
