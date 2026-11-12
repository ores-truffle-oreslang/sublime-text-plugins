"""Adversarial structured-metadata checks after gh signature verification.

All response objects here are synthetic; no real signed release is claimed.
"""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.verify_signed_main_attestation_v1 import SignatureDenied, verify_signed_main
from test_verify_signed_main_attestation_v1 import (
    HEAD, REPO, REPO_ID, RUN_ID, ATTEMPT, CONTENT, verified_fixture,
)


class VerifiedTimestampShapeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.artifact = Path(self.tmp.name) / "Oreslang.sublime-package"
        self.artifact.write_bytes(CONTENT)
        self.digest = hashlib.sha256(CONTENT).hexdigest()

    def check_entry(self, fixture):
        def runner(argv, **kwargs):
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(fixture), stderr="")
        return verify_signed_main(
            self.artifact, repository=REPO, repository_id=REPO_ID,
            source_sha=HEAD, raw_sha256=self.digest, run_id=RUN_ID,
            run_attempt=ATTEMPT, github_token="synthetic-test-token",
            runner=runner,
        )

    def test_invalid_timestamp_containers_and_elements_denied(self):
        for mutant in [None, [], {}, "timestamp", 1, [None], [False], ["proof"], [{}],
                       [{"type": "tlog"}, None], [{"type": "tlog"}, {}]]:
            with self.subTest(mutant=repr(mutant)):
                sample = verified_fixture(self.digest)
                sample[0]["verificationResult"]["verifiedTimestamps"] = mutant
                with self.assertRaisesRegex(SignatureDenied, "CERTIFICATE_OR_SUBJECT_IDENTITY_UNVERIFIED"):
                    self.check_entry(sample)

    def test_valid_shape_is_not_permission_to_merge_or_release(self):
        sample = verified_fixture(self.digest)
        result = self.check_entry(sample)
        self.assertTrue(result["signature_verified"])
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["independent_review_verified"])


if __name__ == "__main__":
    unittest.main()
