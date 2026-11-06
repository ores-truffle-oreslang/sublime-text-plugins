#!/usr/bin/env python3
"""Emit a source-bound *candidate* receipt; never an authenticated merge decision."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
from typing import Mapping

SHA = re.compile(r"[0-9a-f]{40}\Z")
REPOSITORY = re.compile(r"ores-truffle-oreslang/[A-Za-z0-9._-]+\Z")
JOB_KEY = re.compile(r"[A-Za-z0-9_-]{1,100}\Z")
MAX_ARCHIVE_BYTES = 16 * 1024 * 1024


class ReceiptDenied(ValueError):
    """A candidate source or artifact cannot be bound to the expected run."""


def _sha(value: str | None) -> bool:
    return isinstance(value, str) and SHA.fullmatch(value) is not None


def _positive_decimal(value: str | None) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{0,15}", value) is not None


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["/usr/bin/git", "-C", str(root), "rev-parse", "--verify", *args],
        check=False, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, timeout=5,
    )
    if result.returncode != 0:
        raise ReceiptDenied("GIT_IDENTITY_UNAVAILABLE")
    return result.stdout.strip()


def _safe_path(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or relative.startswith("/"):
        raise ReceiptDenied("UNSAFE_ARTIFACT_PATH")
    parts = Path(relative).parts
    if any(part in {"", ".", ".."} for part in parts) or len(parts) < 2:
        raise ReceiptDenied("UNSAFE_ARTIFACT_PATH")
    path = root.joinpath(*parts)
    # Parent must be an ordinary directory within the current Git checkout.
    if not path.parent.is_dir() or path.parent.is_symlink() or (
        not path.parent.resolve().is_relative_to(root.resolve())
    ):
        raise ReceiptDenied("UNSAFE_ARTIFACT_PARENT")
    return path


def _hash_artifact(root: Path, path: str) -> tuple[str, int]:
    candidate = _safe_path(root, path)
    flags = os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW
    try:
        fd = os.open(candidate, flags)
    except OSError as exc:
        raise ReceiptDenied("ARTIFACT_UNREADABLE_OR_SYMLINK") from exc
    try:
        metadata = os.fstat(fd)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or not (
            0 < metadata.st_size <= MAX_ARCHIVE_BYTES
        ):
            raise ReceiptDenied("ARTIFACT_TYPE_SIZE_OR_LINK_UNSAFE")
        sha = hashlib.sha256()
        size = 0
        while True:
            chunk = os.read(fd, 64 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_ARCHIVE_BYTES:
                raise ReceiptDenied("ARTIFACT_TOO_LARGE")
            sha.update(chunk)
        if size != metadata.st_size:
            raise ReceiptDenied("ARTIFACT_SIZE_CHANGED")
        # Detect replacement or in-place mutation during generation. This is
        # local race hardening, not a cryptographic or remote attestation.
        final = os.fstat(fd)
        current = os.lstat(candidate)
        if (final.st_ino, final.st_dev, final.st_size, final.st_mtime_ns) != (
            metadata.st_ino, metadata.st_dev, metadata.st_size, metadata.st_mtime_ns
        ) or (current.st_ino, current.st_dev) != (metadata.st_ino, metadata.st_dev):
            raise ReceiptDenied("ARTIFACT_CHANGED_DURING_HASH")
        return sha.hexdigest(), size
    finally:
        os.close(fd)


def candidate_receipt(root: Path, environment: Mapping[str, str], artifact: str =
                      "dist/Oreslang.sublime-package") -> dict:
    root = root.resolve()
    if not root.is_dir() or any(k.startswith("GIT_") for k in environment):
        raise ReceiptDenied("UNTRUSTED_GIT_CONTEXT")
    repo, expected = environment.get("GITHUB_REPOSITORY"), environment.get("EXPECTED_HEAD")
    event, ref = environment.get("GITHUB_EVENT_NAME"), environment.get("GITHUB_REF")
    run, attempt, job = (environment.get("GITHUB_RUN_ID"),
                         environment.get("GITHUB_RUN_ATTEMPT"), environment.get("GITHUB_JOB"))
    if not isinstance(repo, str) or not REPOSITORY.fullmatch(repo) or not _sha(expected):
        raise ReceiptDenied("INVALID_REPOSITORY_OR_EXPECTED_HEAD")
    if not (_positive_decimal(run) and _positive_decimal(attempt) and
            isinstance(job, str) and JOB_KEY.fullmatch(job)):
        raise ReceiptDenied("INVALID_RUN_ATTEMPT_OR_JOB")
    if event == "push":
        if ref != "refs/heads/main" or environment.get("GITHUB_SHA") != expected:
            raise ReceiptDenied("PUSH_NOT_BOUND_TO_MAIN_HEAD")
    elif event == "pull_request":
        if not isinstance(ref, str) or re.fullmatch(r"refs/pull/[1-9][0-9]*/merge", ref) is None:
            raise ReceiptDenied("UNEXPECTED_PULL_REQUEST_REF")
        # GITHUB_SHA is the synthetic merge SHA in many pull_request events.
        # Never use it as proof of the original PR source head.
    else:
        raise ReceiptDenied("UNSUPPORTED_EVENT")
    actual = _git(root, "HEAD^{commit}")
    tree = _git(root, "HEAD^{tree}")
    if actual != expected or not _sha(tree):
        raise ReceiptDenied("EXACT_SOURCE_HEAD_OR_TREE_MISMATCH")
    digest, size = _hash_artifact(root, artifact)
    return {
        "schema": "atto.source-bound-release-candidate.v1",
        "classification": "CANDIDATE_ONLY_UNTRUSTED_UNTIL_INDEPENDENT_VERIFICATION",
        "repository": repo,
        "event": event,
        "run_id": int(run),
        "run_attempt": int(attempt),
        "job_key": job,  # not the numeric GitHub job ID
        "source_head_sha": actual,
        "source_tree_sha": tree,
        "artifact": {"path": artifact, "sha256": digest, "size_bytes": size},
        "signature_verified": False,
        "independent_approval_verified": False,
        "compiler_guest_execution_verified": False,
        "merge_authorized": False,
    }


def write_candidate_receipt(root: Path, environment: Mapping[str, str],
                            artifact: str = "dist/Oreslang.sublime-package",
                            output: str = "dist/source-bound-release-receipt-v1.json") -> dict:
    receipt = candidate_receipt(root, environment, artifact)
    target = _safe_path(root.resolve(), output)
    payload = (json.dumps(receipt, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=True) + "\n").encode("ascii")
    # Never follow, reuse or clobber an existing receipt (including symlinks).
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        fd = os.open(target, flags, 0o600)
    except OSError as exc:
        raise ReceiptDenied("RECEIPT_DESTINATION_EXISTS_OR_UNSAFE") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        target.unlink(missing_ok=True)
        raise
    return receipt


if __name__ == "__main__":
    try:
        result = write_candidate_receipt(Path(__file__).resolve().parents[1], os.environ)
        print(json.dumps({"result": "CANDIDATE_WRITTEN", "head": result["source_head_sha"],
                          "tree": result["source_tree_sha"],
                          "artifact_sha256": result["artifact"]["sha256"]}))
    except (ReceiptDenied, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"result": "DENIED", "reason": str(exc)}), file=__import__("sys").stderr)
        raise SystemExit(65)
