"""Source-free candidate receipt negative controls, not signed provenance."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts.source_bound_release_receipt_v1 import (ReceiptDenied, candidate_receipt,
                                                     write_candidate_receipt, MAX_ARCHIVE_BYTES)

SCRIPT_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = SCRIPT_ROOT / ".github/workflows/source-bound-release-provenance-v1.yml"


class ReceiptTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        self.root.mkdir()
        self.run_git("init", "-q")
        self.run_git("config", "user.email", "fixture@example.invalid")
        self.run_git("config", "user.name", "Fixture")
        (self.root / "source.atto").write_text("fnc main(): int { return 1; }\n")
        self.run_git("add", "source.atto")
        self.run_git("commit", "-qm", "fixture")
        self.head = self.run_git("rev-parse", "HEAD")
        (self.root / "dist").mkdir()
        self.archive = self.root / "dist/Oreslang.sublime-package"
        self.archive.write_bytes(b"PK\x03\x04source-free-example-not-a-real-package")
        self.env = {"GITHUB_REPOSITORY": "ores-truffle-oreslang/sublime-text-plugins",
                    "EXPECTED_HEAD": self.head, "GITHUB_SHA": "b" * 40,
                    "GITHUB_EVENT_NAME": "pull_request", "GITHUB_REF": "refs/pull/145/merge",
                    "GITHUB_RUN_ID": "41002", "GITHUB_RUN_ATTEMPT": "2", "GITHUB_JOB": "receipt"}

    def run_git(self, *args):
        x = subprocess.run(["git", "-C", str(self.root), *args],
                           check=True, capture_output=True, text=True)
        return x.stdout.strip()

    def emit(self, **env):
        return candidate_receipt(self.root, {**self.env, **env})

    def test_source_bound_candidate_exact_head_tree_digest(self):
        x = self.emit()
        self.assertEqual(x["source_head_sha"], self.head)
        self.assertEqual(x["source_tree_sha"], self.run_git("rev-parse", "HEAD^{tree}"))
        self.assertEqual(x["artifact"]["sha256"], hashlib.sha256(self.archive.read_bytes()).hexdigest())
        self.assertEqual(x["artifact"]["size_bytes"], self.archive.stat().st_size)
        self.assertFalse(x["merge_authorized"])
        self.assertFalse(x["signature_verified"])
        self.assertFalse(x["compiler_guest_execution_verified"])
        self.assertNotIn("job_id", x)

    def test_push_main_requires_sha_equal_head(self):
        x = self.emit(GITHUB_EVENT_NAME="push", GITHUB_REF="refs/heads/main", GITHUB_SHA=self.head)
        self.assertEqual(x["event"], "push")
        for data in [{"GITHUB_SHA": "b" * 40}, {"GITHUB_REF": "refs/heads/evil"}]:
            with self.subTest(data=data), self.assertRaises(ReceiptDenied):
                self.emit(**{**{"GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/main",
                                   "GITHUB_SHA": self.head}, **data})

    def test_source_wrong_head_and_same_tree_different_commit_rejected(self):
        with self.assertRaisesRegex(ReceiptDenied, "HEAD_OR_TREE_MISMATCH"):
            self.emit(EXPECTED_HEAD="c" * 40)
        self.run_git("commit", "--allow-empty", "-qm", "same tree different head")
        with self.assertRaisesRegex(ReceiptDenied, "HEAD_OR_TREE_MISMATCH"):
            self.emit()

    def test_malformed_security_context_rejected(self):
        invalid = [
            {"GITHUB_REPOSITORY": "evil/repo"},
            {"GITHUB_REPOSITORY": "ores-truffle-oreslang/repo/../../secret"},
            {"EXPECTED_HEAD": "A" * 40},
            {"EXPECTED_HEAD": "a" * 39},
            {"GITHUB_EVENT_NAME": "workflow_dispatch"},
            {"GITHUB_REF": "refs/pull/145/head"},
            {"GITHUB_REF": "refs/heads/main"},
            {"GITHUB_RUN_ID": "0"},
            {"GITHUB_RUN_ID": "12.3"},
            {"GITHUB_RUN_ATTEMPT": "0"},
            {"GITHUB_RUN_ATTEMPT": "-1"},
            {"GITHUB_JOB": "../../evil"},
            {"GITHUB_JOB": ""},
            {"GIT_DIR": "/tmp/evil"},
            {"GIT_CONFIG_GLOBAL": "/tmp/evil"},
        ]
        for data in invalid:
            with self.subTest(data=data), self.assertRaises(ReceiptDenied):
                self.emit(**data)

    def test_missing_and_empty_archive_rejected(self):
        self.archive.unlink()
        with self.assertRaises(ReceiptDenied): self.emit()
        self.archive.write_bytes(b"")
        with self.assertRaises(ReceiptDenied): self.emit()

    def test_symlink_and_hardlink_archive_rejected(self):
        target = self.root / "source.atto"
        self.archive.unlink()
        self.archive.symlink_to(target)
        with self.assertRaises(ReceiptDenied): self.emit()
        self.archive.unlink()
        os.link(target, self.archive)
        with self.assertRaises(ReceiptDenied): self.emit()

    def test_nonregular_and_oversized_archive_rejected(self):
        self.archive.unlink()
        self.archive.mkdir()
        with self.assertRaises(ReceiptDenied): self.emit()
        self.archive.rmdir()
        with self.archive.open("wb") as fh:
            fh.truncate(MAX_ARCHIVE_BYTES + 1)
        with self.assertRaises(ReceiptDenied): self.emit()

    def test_artifact_parent_alias_and_relative_path_traversal_rejected(self):
        (self.root / "outside").mkdir()
        (self.root / "alias").symlink_to(self.root / "dist")
        for relative in ("/dist/Oreslang.sublime-package", "../source.atto",
                         "alias/Oreslang.sublime-package", "Oreslang.sublime-package"):
            with self.subTest(relative=relative), self.assertRaises(ReceiptDenied):
                candidate_receipt(self.root, self.env, artifact=relative)

    def test_output_is_deterministic_and_not_overwritten(self):
        x = write_candidate_receipt(self.root, self.env)
        receipt_path = self.root / "dist/source-bound-release-receipt-v1.json"
        blob = receipt_path.read_bytes()
        self.assertEqual(json.loads(blob), x)
        self.assertTrue(blob.endswith(b"\n"))
        with self.assertRaisesRegex(ReceiptDenied, "RECEIPT_DESTINATION"):
            write_candidate_receipt(self.root, self.env)
        self.assertEqual(receipt_path.read_bytes(), blob)

    def test_symlink_output_cannot_replace_existing_source(self):
        (self.root / "dist/source-bound-release-receipt-v1.json").symlink_to(self.root / "source.atto")
        original = (self.root / "source.atto").read_bytes()
        with self.assertRaisesRegex(ReceiptDenied, "RECEIPT_DESTINATION"):
            write_candidate_receipt(self.root, self.env)
        self.assertEqual((self.root / "source.atto").read_bytes(), original)

    def test_safe_wrapper_declares_no_independent_merge_or_signature_proof(self):
        x = self.emit()
        self.assertEqual(x["classification"], "CANDIDATE_ONLY_UNTRUSTED_UNTIL_INDEPENDENT_VERIFICATION")
        for key in ("signature_verified", "independent_approval_verified",
                    "compiler_guest_execution_verified", "merge_authorized"):
            self.assertIs(x[key], False)

    def test_workflow_has_separate_main_only_signature_privilege(self):
        text = WORKFLOW.read_text()
        self.assertIn("if: github.event_name == 'push' && github.ref == 'refs/heads/main'", text)
        self.assertIn("id-token: write", text)
        self.assertIn("attestations: write", text)
        self.assertIn("artifact-metadata: write", text)
        self.assertIn("actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6", text)
        candidate = text.split("  candidate-receipt:\n", 1)[1].split("  signed-main-release:\n", 1)[0]
        self.assertNotIn("id-token: write", candidate)
        self.assertNotIn("attestations: write", candidate)
        self.assertIn("contents: read", candidate)
        self.assertIn("persist-credentials: false", candidate)
        self.assertIn("bash scripts/verify_ci_checkout_head.sh", candidate)


if __name__ == "__main__":
    unittest.main()
