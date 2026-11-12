#!/usr/bin/env python3
"""Verify a GitHub OIDC attestation for one exact main-branch release artifact.

This is signed *integrity/provenance* evidence only, NEVER a merge/release grant.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
from typing import Callable

SHA40 = re.compile(r"[a-f0-9]{40}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
REPO = "ores-truffle-oreslang/sublime-text-plugins"
WORKFLOW = ".github/workflows/source-bound-release-provenance-v1.yml"
WORKFLOW_ID = f"{REPO}/{WORKFLOW}"
REF = "refs/heads/main"
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
PREDICATE = "https://slsa.dev/provenance/v1"
MAX_BYTES = 16 * 1024 * 1024
MAX_JSON = 1024 * 1024
GH_BINARY = "/usr/bin/gh"


class SignatureDenied(ValueError):
    """Cryptographic provenance or source binding was not established."""


def _strict_positive(value: object) -> bool:
    return type(value) is int and 0 < value < 2 ** 53


def _valid_hex(value: object, pattern: re.Pattern) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _source_snapshot(path: Path, expected_digest: str) -> bytes:
    if not isinstance(path, Path) or path.name != "Oreslang.sublime-package":
        raise SignatureDenied("UNEXPECTED_ARTIFACT_NAME")
    if path.is_symlink():
        raise SignatureDenied("SYMLINK_ARTIFACT_DENIED")
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise SignatureDenied("ARTIFACT_NOT_READABLE") from exc
    try:
        first = os.fstat(fd)
        if (not stat.S_ISREG(first.st_mode) or first.st_nlink != 1
                or not 0 < first.st_size <= MAX_BYTES):
            raise SignatureDenied("ARTIFACT_TYPE_SIZE_LINK_DENIED")
        digest = hashlib.sha256()
        chunks, length = [], 0
        while True:
            data = os.read(fd, 64 * 1024)
            if not data:
                break
            length += len(data)
            if length > MAX_BYTES:
                raise SignatureDenied("ARTIFACT_SIZE_LIMIT")
            digest.update(data)
            chunks.append(data)
        last = os.fstat(fd)
        try:
            current = os.stat(path, follow_symlinks=False)
        except OSError as exc:
            raise SignatureDenied("ARTIFACT_DISAPPEARED") from exc
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if length != first.st_size or signature(first) != signature(last) or (
                signature(first) != signature(current)):
            raise SignatureDenied("ARTIFACT_CHANGED_DURING_SNAPSHOT")
        if digest.hexdigest() != expected_digest:
            raise SignatureDenied("ARTIFACT_DIGEST_MISMATCH")
        return b"".join(chunks)
    finally:
        os.close(fd)


def _verified_entry_ok(entry: object, source_sha: str, digest: str,
                       run_id: int, attempt: int, repo_id: int) -> bool:
    if not isinstance(entry, dict):
        return False
    verification = entry.get("verificationResult")
    if not isinstance(verification, dict):
        return False
    signature = verification.get("signature")
    certificate = signature.get("certificate") if isinstance(signature, dict) else None
    statement = verification.get("statement")
    timestamps = verification.get("verifiedTimestamps")
    if not isinstance(certificate, dict) or not isinstance(statement, dict):
        return False
    # A nonempty list of arbitrary scalars is not structured verification
    # metadata. This is shape validation only; `gh attestation verify` must
    # have succeeded cryptographically before these claims are read.
    if (not isinstance(timestamps, list) or not timestamps
            or any(not isinstance(t, dict) or not t for t in timestamps)):
        return False
    expected_cert = {
        "issuer": OIDC_ISSUER,
        "sourceRepositoryURI": f"https://github.com/{REPO}",
        "sourceRepositoryDigest": source_sha,
        "sourceRepositoryIdentifier": str(repo_id),
        "githubWorkflowRef": REF,
        "subjectAlternativeName": f"https://github.com/{WORKFLOW_ID}@{REF}",
        "runInvocationURI": (
            f"https://github.com/{REPO}/actions/runs/{run_id}/attempts/{attempt}"
        ),
        "runnerEnvironment": "github-hosted",
    }
    if any(certificate.get(key) != val for key, val in expected_cert.items()):
        return False
    if statement.get("predicateType") != PREDICATE:
        return False
    subjects = statement.get("subject")
    if not isinstance(subjects, list) or len(subjects) != 1:
        return False
    only = subjects[0]
    return (
        isinstance(only, dict)
        and only.get("name") == "Oreslang.sublime-package"
        and only.get("digest") == {"sha256": digest}
    )


def verify_signed_main(
    artifact: Path, *, repository: str, repository_id: int, source_sha: str,
    raw_sha256: str, run_id: int, run_attempt: int, github_token: str,
    runner: Callable = subprocess.run,
) -> dict:
    """Require gh's successful live cryptographic verification, then bind cert claims.

    Injected runner exists for isolated negative tests. Production CLI uses
    subprocess.run with fixed absolute /usr/bin/gh, never untrusted JSON input.
    """
    if (repository != REPO or not _strict_positive(repository_id)
            or not _strict_positive(run_id) or not _strict_positive(run_attempt)
            or not _valid_hex(source_sha, SHA40)
            or not _valid_hex(raw_sha256, SHA256)
            or not isinstance(github_token, str) or not github_token):
        raise SignatureDenied("INVALID_VERIFIER_EXPECTATIONS")
    snapshot = _source_snapshot(artifact, raw_sha256)
    with tempfile.TemporaryDirectory(prefix="atto-attestation-") as tmp:
        subject = Path(tmp) / "Oreslang.sublime-package"
        with subject.open("xb") as target:
            target.write(snapshot)
            target.flush()
            os.fsync(target.fileno())
        # Live lookup, not --bundle: GitHub CLI binds the current repo identity.
        # No user-supplied trust root, host, bundle, or certificate identity regex.
        command = [
            GH_BINARY, "attestation", "verify", str(subject),
            "--repo", REPO,
            "--signer-workflow", WORKFLOW_ID,
            "--source-ref", REF,
            "--source-digest", source_sha,
            "--cert-oidc-issuer", OIDC_ISSUER,
            "--deny-self-hosted-runners",
            "--predicate-type", PREDICATE,
            "--format", "json",
            "--limit", "10",
        ]
        # Do not inherit GH_HOST, GH_CONFIG_DIR, GIT_*, credential helpers or
        # a caller-selected GitHub Enterprise instance / custom trusted root.
        environ = {
            "PATH": "/usr/bin:/bin",
            "HOME": tmp,
            "GH_TOKEN": github_token,
            "GH_PROMPT_DISABLED": "1",
            "GH_NO_UPDATE_NOTIFIER": "1",
        }
        try:
            result = runner(
                command, check=False, capture_output=True, text=True,
                timeout=45, cwd=tmp, env=environ,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SignatureDenied("GH_ATTESTATION_VERIFIER_UNAVAILABLE") from exc
        if result.returncode != 0:
            raise SignatureDenied("GH_ATTESTATION_CRYPTOGRAPHIC_VERIFICATION_FAILED")
        if not isinstance(result.stdout, str) or (
                len(result.stdout.encode("utf-8")) > MAX_JSON):
            raise SignatureDenied("VERIFICATION_OUTPUT_OVERSIZED")
        try:
            verified = json.loads(result.stdout)
        except (UnicodeError, ValueError) as exc:
            raise SignatureDenied("VERIFICATION_OUTPUT_INVALID") from exc
        if (not isinstance(verified, list) or not 0 < len(verified) <= 10
                or not any(_verified_entry_ok(
                    entry, source_sha, raw_sha256, run_id, run_attempt,
                    repository_id,
                ) for entry in verified)):
            raise SignatureDenied("CERTIFICATE_OR_SUBJECT_IDENTITY_UNVERIFIED")
    return {
        "classification": "SIGNED_MAIN_ARTIFACT_PROVENANCE_VERIFIED_ONLY",
        "repository": REPO,
        "source_head_sha": source_sha,
        "artifact_sha256": raw_sha256,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "signature_verified": True,
        "source_certificate_bound": True,
        "branch_protection_verified": False,
        "independent_review_verified": False,
        "compiler_guest_execution_verified": False,
        "release_authorized": False,
        "merge_authorized": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--repository-id", required=True, type=int)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--raw-sha256", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--run-attempt", required=True, type=int)
    args = parser.parse_args()
    try:
        result = verify_signed_main(
            args.artifact, repository=args.repository,
            repository_id=args.repository_id,
            source_sha=args.source_sha, raw_sha256=args.raw_sha256,
            run_id=args.run_id, run_attempt=args.run_attempt,
            github_token=os.environ.get("GH_TOKEN", ""),
        )
        print(json.dumps(result, sort_keys=True))
    except SignatureDenied as exc:
        print(json.dumps({
            "classification": "UNVERIFIED", "reason": str(exc),
            "release_authorized": False, "merge_authorized": False,
        }), file=sys.stderr)
        raise SystemExit(65)
