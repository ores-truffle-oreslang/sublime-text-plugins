"""Source-free adversarial tests: never claim a real GitHub signature was issued."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.verify_signed_main_attestation_v1 import (
    GH_BINARY, MAX_BYTES, OIDC_ISSUER, PREDICATE, REF, REPO,
    SignatureDenied, WORKFLOW_ID, verify_signed_main,
)

HEAD = "a" * 40
REPO_ID = 1402482919
RUN_ID = 42314137217
ATTEMPT = 1
CONTENT = b"PK\x03\x04source-free-test-subject-only"


def verified_fixture(digest: str) -> list:
    return [{
        "verificationResult": {
            "signature": {"certificate": {
                "issuer": OIDC_ISSUER,
                "sourceRepositoryURI": f"https://github.com/{REPO}",
                "sourceRepositoryDigest": HEAD,
                "sourceRepositoryIdentifier": str(REPO_ID),
                "githubWorkflowRef": REF,
                "subjectAlternativeName":
                    f"https://github.com/{WORKFLOW_ID}@{REF}",
                "runInvocationURI":
                    f"https://github.com/{REPO}/actions/runs/{RUN_ID}/attempts/{ATTEMPT}",
                "runnerEnvironment": "github-hosted",
            }},
            "verifiedTimestamps": [{"type": "tlog", "time": "2026-11-06T00:00:00Z"}],
            "statement": {
                "predicateType": PREDICATE,
                "subject": [{
                    "name": "Oreslang.sublime-package",
                    "digest": {"sha256": digest},
                }],
                "predicate": {"untrusted": "caller controlled"},
            },
        },
        "attestation": {"bundle": "test-only-not-an-actual-sigstore-bundle"},
    }]


class SignedMainVerifierTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.subject = Path(self.tmp.name) / "Oreslang.sublime-package"
        self.subject.write_bytes(CONTENT)
        self.digest = hashlib.sha256(CONTENT).hexdigest()
        self.fixture = verified_fixture(self.digest)
        self.calls = []

    def runner(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        self.assertEqual(argv[:3], [GH_BINARY, "attestation", "verify"])
        self.assertEqual(Path(argv[3]).read_bytes(), CONTENT)
        return subprocess.CompletedProcess(
            argv, 0, stdout=json.dumps(self.fixture), stderr="",
        )

    def verify(self, **overrides):
        args = {
            "repository": REPO,
            "repository_id": REPO_ID,
            "source_sha": HEAD,
            "raw_sha256": self.digest,
            "run_id": RUN_ID,
            "run_attempt": ATTEMPT,
            "github_token": "test-secret",
            "runner": self.runner,
        }
        args.update(overrides)
        return verify_signed_main(self.subject, **args)

    def test_matching_fixture_reports_only_signed_integrity_not_release_permission(self):
        r = self.verify()
        self.assertEqual(r["classification"],
                         "SIGNED_MAIN_ARTIFACT_PROVENANCE_VERIFIED_ONLY")
        self.assertTrue(r["signature_verified"])
        self.assertFalse(r["release_authorized"])
        self.assertFalse(r["merge_authorized"])
        self.assertFalse(r["branch_protection_verified"])
        self.assertFalse(r["independent_review_verified"])
        self.assertFalse(r["compiler_guest_execution_verified"])

    def test_gh_command_restricts_identity_ref_source_and_oidc_issuer(self):
        self.verify()
        cmd, kwargs = self.calls[0]
        for exact in (
            ("--repo", REPO),
            ("--signer-workflow", WORKFLOW_ID),
            ("--source-ref", REF),
            ("--source-digest", HEAD),
            ("--cert-oidc-issuer", OIDC_ISSUER),
            ("--predicate-type", PREDICATE),
            ("--format", "json"),
            ("--limit", "10"),
        ):
            pos = cmd.index(exact[0])
            self.assertEqual(cmd[pos + 1], exact[1])
        self.assertIn("--deny-self-hosted-runners", cmd)
        self.assertNotIn("--bundle", cmd)
        self.assertNotIn("--hostname", cmd)
        self.assertEqual(kwargs["env"]["GH_TOKEN"], "test-secret")
        self.assertEqual(kwargs["env"]["GH_PROMPT_DISABLED"], "1")
        self.assertNotIn("GH_HOST", kwargs["env"])
        self.assertNotIn("GIT_DIR", kwargs["env"])
        self.assertNotIn("GH_CONFIG_DIR", kwargs["env"])
        self.assertEqual(kwargs["timeout"], 45)
        self.assertFalse(kwargs["check"])

    def test_mismatched_expected_digest_denied_before_executing_gh(self):
        with self.assertRaisesRegex(SignatureDenied, "DIGEST_MISMATCH"):
            self.verify(raw_sha256="b" * 64)
        self.assertEqual(self.calls, [])

    def test_invalid_repositories_heads_run_id_token_denied_before_gh(self):
        invalids = [
            {"repository": "evil/repo"},
            {"repository": "ores-truffle-oreslang/other"},
            {"repository_id": 0},
            {"repository_id": True},
            {"source_sha": "A" * 40},
            {"source_sha": "a" * 39},
            {"raw_sha256": "bad"},
            {"run_id": 0},
            {"run_id": True},
            {"run_attempt": 0},
            {"github_token": ""},
            {"github_token": None},
        ]
        for mutation in invalids:
            with self.subTest(mutation=mutation), self.assertRaisesRegex(
                SignatureDenied, "INVALID_VERIFIER_EXPECTATIONS",
            ):
                self.verify(**mutation)
        self.assertEqual(self.calls, [])

    def test_reject_symlink_hardlink_empty_directory_and_oversize(self):
        self.subject.unlink()
        self.subject.symlink_to(Path(self.tmp.name) / "missing")
        with self.assertRaises(SignatureDenied):
            self.verify()
        self.subject.unlink()
        self.subject.write_bytes(CONTENT)
        alias = Path(self.tmp.name) / "alias"
        os.link(self.subject, alias)
        with self.assertRaisesRegex(SignatureDenied, "TYPE_SIZE_LINK"):
            self.verify()
        alias.unlink()
        self.subject.write_bytes(b"")
        with self.assertRaisesRegex(SignatureDenied, "TYPE_SIZE_LINK"):
            self.verify()
        with self.subject.open("wb") as out:
            out.truncate(MAX_BYTES + 1)
        with self.assertRaisesRegex(SignatureDenied, "TYPE_SIZE_LINK"):
            self.verify()
        self.assertEqual(self.calls, [])

    def test_wrong_artifact_filename_never_invokes_gh(self):
        different = Path(self.tmp.name) / "wrong-package.bin"
        different.write_bytes(CONTENT)
        with self.assertRaisesRegex(SignatureDenied, "UNEXPECTED_ARTIFACT_NAME"):
            verify_signed_main(
                different, repository=REPO, repository_id=REPO_ID,
                source_sha=HEAD, raw_sha256=self.digest,
                run_id=RUN_ID, run_attempt=ATTEMPT,
                github_token="test-secret", runner=self.runner,
            )
        self.assertEqual(self.calls, [])

    def test_nonzero_gh_exit_never_uses_forged_stdout(self):
        def failure(argv, **kwargs):
            return subprocess.CompletedProcess(
                argv, 1, stdout=json.dumps(self.fixture),
                stderr="forged success",
            )
        with self.assertRaisesRegex(SignatureDenied, "CRYPTOGRAPHIC_VERIFICATION_FAILED"):
            self.verify(runner=failure)

    def test_unavailable_or_timed_out_gh_blocks(self):
        def unavailable(argv, **kwargs):
            raise OSError("no such gh")
        def timed_out(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, 45)
        for impl in (unavailable, timed_out):
            with self.subTest(impl=impl), self.assertRaisesRegex(
                SignatureDenied, "VERIFIER_UNAVAILABLE",
            ):
                self.verify(runner=impl)

    def test_invalid_or_missing_verification_output_rejected(self):
        for stdout in ("not json", "{}", "[]", "null", " " * 1048577):
            def fake(argv, **kwargs):
                return subprocess.CompletedProcess(
                    argv, 0, stdout=stdout, stderr="",
                )
            with self.subTest(data=stdout[:10]), self.assertRaises(SignatureDenied):
                self.verify(runner=fake)

    def test_forged_certificate_claims_fail_closed(self):
        mutations = [
            ("issuer", "https://attacker.invalid"),
            ("sourceRepositoryURI", "https://github.com/evil/repo"),
            ("sourceRepositoryDigest", "b" * 40),
            ("sourceRepositoryIdentifier", str(REPO_ID + 1)),
            ("githubWorkflowRef", "refs/heads/feature"),
            ("subjectAlternativeName",
             f"https://github.com/{REPO}/.github/workflows/other.yml@{REF}"),
            ("runInvocationURI",
             f"https://github.com/{REPO}/actions/runs/{RUN_ID}/attempts/2"),
            ("runnerEnvironment", "self-hosted"),
        ]
        for field, value in mutations:
            with self.subTest(field=field):
                self.fixture = verified_fixture(self.digest)
                cert = self.fixture[0]["verificationResult"]["signature"]["certificate"]
                cert[field] = value
                with self.assertRaisesRegex(
                    SignatureDenied, "CERTIFICATE_OR_SUBJECT_IDENTITY_UNVERIFIED",
                ):
                    self.verify()

    def test_missing_timestamps_wrong_predicate_wrong_subject_digest_rejected(self):
        mutations = [
            lambda v: v["verificationResult"].update(verifiedTimestamps=[]),
            lambda v: v["verificationResult"]["statement"].update(
                predicateType="https://fake.invalid/predicate",
            ),
            lambda v: v["verificationResult"]["statement"]["subject"][0].update(
                digest={"sha256": "b" * 64},
            ),
            lambda v: v["verificationResult"]["statement"]["subject"][0].update(
                name="other.sublime-package",
            ),
            lambda v: v["verificationResult"]["statement"].update(subject=[]),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                self.fixture = verified_fixture(self.digest)
                mutate(self.fixture[0])
                with self.assertRaises(SignatureDenied):
                    self.verify()

    def test_untrusted_predicate_cannot_be_used_for_release_authorization(self):
        self.fixture[0]["verificationResult"]["statement"]["predicate"] = {
            "approved": True, "branch_protected": True, "merge_authorized": True,
        }
        result = self.verify()
        self.assertFalse(result["merge_authorized"])
        self.assertFalse(result["release_authorized"])
        self.assertFalse(result["independent_review_verified"])

    def test_snapshot_is_isolated_from_modification_during_cli_verification(self):
        def runner(argv, **kwargs):
            # The CLI sees only a private immutable snapshot, not the source path.
            self.subject.write_bytes(b"CHANGED_BY_OTHER_PROCESS")
            self.assertEqual(Path(argv[3]).read_bytes(), CONTENT)
            return subprocess.CompletedProcess(
                argv, 0, stdout=json.dumps(self.fixture), stderr="",
            )
        result = self.verify(runner=runner)
        self.assertTrue(result["signature_verified"])
        self.assertFalse(result["release_authorized"])


if __name__ == "__main__":
    unittest.main()
