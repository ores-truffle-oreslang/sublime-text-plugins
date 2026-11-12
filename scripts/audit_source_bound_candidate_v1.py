#!/usr/bin/env python3
"""Independently cross-check a candidate ZIP against authenticated GitHub REST.

Only source+artifact integrity is established. Never authorizes a merge/signature.
"""
from __future__ import annotations

import argparse
import hashlib
from http.client import HTTPSConnection
import json
import os
from pathlib import Path
import re
import stat
import zipfile

SHA40 = re.compile(r"[a-f0-9]{40}\Z")
SHA256 = re.compile(r"[a-f0-9]{64}\Z")
REPOSITORY = re.compile(r"ores-truffle-oreslang/[A-Za-z0-9._-]+\Z")
MAX_ARCHIVE = 32 * 1024 * 1024
MAX_SUBJECT = 16 * 1024 * 1024
MAX_MANIFEST = 8 * 1024
MAX_JSON = 1024 * 1024
CHECKOUT_STEP = "Verify immutable source head and physical Git tree"
TEST_STEP = "Run source-bound candidate receipt negative controls"
EMIT_STEP = "Emit unsigned source-bound candidate receipt"
UPLOAD_STEP = "Upload candidate source-bound receipt (not signed)"
SOURCE_WORKFLOW = ".github/workflows/source-bound-release-provenance-v1.yml"


class AuditDenied(ValueError):
    pass


def positive(n: object) -> bool:
    return type(n) is int and 0 < n <= 2**53 - 1


def sha40(v: object) -> bool:
    return type(v) is str and SHA40.fullmatch(v) is not None


def digest(v: object) -> bool:
    return type(v) is str and SHA256.fullmatch(v) is not None


def github_get_json(token: str, path: str):
    if not isinstance(token, str) or not token or not isinstance(path, str) or not re.fullmatch(
        r"/repos/ores-truffle-oreslang/[A-Za-z0-9._-]+/(?:pulls/[1-9][0-9]*|git/commits/[0-9a-f]{40}|actions/runs/[1-9][0-9]*|actions/runs/[1-9][0-9]*/attempts/[1-9][0-9]*/jobs\?per_page=100&page=[1-8]|actions/artifacts/[1-9][0-9]*)", path
    ):
        raise AuditDenied("GITHUB_METADATA_PATH_DENIED")
    connection = HTTPSConnection("api.github.com", timeout=10)
    try:
        connection.request("GET", path, headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "atto-source-bound-auditor-v1",
        })
        response = connection.getresponse()
        if response.status != 200:
            raise AuditDenied("GITHUB_METADATA_UNAVAILABLE")
        raw = response.read(MAX_JSON + 1)
        if not raw or len(raw) > MAX_JSON:
            raise AuditDenied("GITHUB_METADATA_OVERSIZED_OR_EMPTY")
        try:
            return json.loads(raw.decode("utf-8", "strict"))
        except (UnicodeError, ValueError) as exc:
            raise AuditDenied("GITHUB_METADATA_INVALID") from exc
    finally:
        connection.close()


def _read_zip_bytes(path: Path) -> bytes:
    if not isinstance(path, Path) or path.is_symlink():
        raise AuditDenied("ZIP_SYMLINK_OR_PATH_INVALID")
    # Do not permit a symlinked ancestor to redirect a candidate artifact to
    # another directory after its caller-visible path is selected.
    try:
        for ancestor in path.parents:
            parent = os.lstat(ancestor)
            if not stat.S_ISDIR(parent.st_mode):
                raise AuditDenied("ZIP_SYMLINK_OR_PATH_INVALID")
    except OSError as exc:
        raise AuditDenied("ZIP_SYMLINK_OR_PATH_INVALID") from exc
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        raise AuditDenied("ZIP_UNREADABLE") from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode) or st.st_nlink != 1 or not 0 < st.st_size <= MAX_ARCHIVE:
            raise AuditDenied("ZIP_TYPE_LINK_OR_SIZE_INVALID")
        chunks, size = [], 0
        while True:
            part = os.read(fd, 65536)
            if not part:
                break
            chunks.append(part)
            size += len(part)
            if size > MAX_ARCHIVE:
                raise AuditDenied("ZIP_OVERSIZED")
        if size != st.st_size:
            raise AuditDenied("ZIP_MUTATED_DURING_READ")
        # Compare both ends of the pinned descriptor, not just its name.
        # A same-inode edit can preserve size and fool pathname-only checks.
        after = os.fstat(fd)
        try:
            current = os.stat(path, follow_symlinks=False)
        except OSError as exc:
            raise AuditDenied("ZIP_MUTATED_DURING_READ") from exc
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size,
                              s.st_nlink, s.st_mtime_ns, s.st_ctime_ns)
        if (identity(st) != identity(after) or
                identity(st) != identity(current) or current.st_nlink != 1 or
                not stat.S_ISREG(current.st_mode)):
            raise AuditDenied("ZIP_MUTATED_DURING_READ")
        return b"".join(chunks)
    finally:
        os.close(fd)


def _zip_manifest(raw: bytes) -> tuple[dict, bytes]:
    from io import BytesIO
    try:
        with zipfile.ZipFile(BytesIO(raw)) as z:
            infos = z.infolist()
            names = [i.filename for i in infos]
            if len(infos) != 2 or set(names) != {
                "Oreslang.sublime-package", "source-bound-release-receipt-v1.json"
            } or len(set(names)) != 2:
                raise AuditDenied("ZIP_MEMBER_SET_INVALID")
            for i in infos:
                if i.flag_bits & 1 or stat.S_ISLNK(i.external_attr >> 16) or i.is_dir():
                    raise AuditDenied("ZIP_ENCRYPTION_OR_TYPE_INVALID")
                bound = MAX_MANIFEST if i.filename.endswith(".json") else MAX_SUBJECT
                if not 0 < i.file_size <= bound:
                    raise AuditDenied("ZIP_MEMBER_SIZE_INVALID")
            m = z.read("source-bound-release-receipt-v1.json")
            p = z.read("Oreslang.sublime-package")
    except (zipfile.BadZipFile, RuntimeError, OverflowError) as exc:
        raise AuditDenied("ZIP_CORRUPT") from exc
    try:
        manifest = json.loads(m.decode("utf-8", "strict"))
    except (UnicodeError, ValueError) as exc:
        raise AuditDenied("CANDIDATE_MANIFEST_MALFORMED") from exc
    if not isinstance(manifest, dict):
        raise AuditDenied("CANDIDATE_MANIFEST_MALFORMED")
    return manifest, p


def verify_candidate(zip_path: Path, repo: str, pr_number: int,
                     artifact_id: int, expected_head: str, expected_tree: str,
                     get) -> dict:
    """Independent REST+ZIP integrity verification; NEVER signature/merge proof.

    get must be a trusted HTTPS metadata client; injected only in tests.
    """
    if not (isinstance(repo, str) and REPOSITORY.fullmatch(repo) and positive(pr_number)
            and positive(artifact_id) and sha40(expected_head) and sha40(expected_tree)
            and callable(get)):
        raise AuditDenied("INVALID_AUDIT_EXPECTATIONS")
    raw = _read_zip_bytes(zip_path)
    root = "/repos/" + repo
    artifact = get(root + "/actions/artifacts/" + str(artifact_id))
    if not isinstance(artifact, dict) or artifact.get("id") != artifact_id or artifact.get("expired") is not False:
        raise AuditDenied("GITHUB_ARTIFACT_IDENTITY_UNVERIFIED")
    sha_zip = hashlib.sha256(raw).hexdigest()
    if artifact.get("digest") != "sha256:" + sha_zip or artifact.get("size_in_bytes") != len(raw):
        raise AuditDenied("GITHUB_ARTIFACT_DIGEST_OR_SIZE_MISMATCH")
    workflow = artifact.get("workflow_run")
    if not isinstance(workflow, dict) or not positive(workflow.get("id")) or workflow.get("head_sha") != expected_head:
        raise AuditDenied("GITHUB_ARTIFACT_RUN_UNBOUND")
    run_id = workflow["id"]
    run = get(root + "/actions/runs/" + str(run_id))
    if not isinstance(run, dict) or run.get("id") != run_id or not positive(run.get("run_attempt")) or (
        run.get("event") != "pull_request" or run.get("head_sha") != expected_head or
        run.get("path") != SOURCE_WORKFLOW or run.get("status") != "completed" or
        run.get("conclusion") != "success" or run.get("repository", {}).get("full_name") != repo or
        workflow.get("repository_id") != run.get("repository", {}).get("id")
    ):
        raise AuditDenied("GITHUB_RUN_IDENTITY_UNVERIFIED")
    attempt = run["run_attempt"]
    commit = get(root + "/git/commits/" + expected_head)
    pr = get(root + "/pulls/" + str(pr_number))
    if not isinstance(commit, dict) or commit.get("sha") != expected_head or (
        commit.get("tree", {}).get("sha") != expected_tree
    ) or not isinstance(pr, dict) or pr.get("number") != pr_number or (
        pr.get("head", {}).get("sha") != expected_head
    ) or pr.get("base", {}).get("repo", {}).get("full_name") != repo:
        raise AuditDenied("SOURCE_COMMIT_OR_PR_CHANGED")
    jobs = get(root + "/actions/runs/" + str(run_id) + "/attempts/" + str(attempt) +
               "/jobs?per_page=100&page=1")
    if not isinstance(jobs, dict) or not isinstance(jobs.get("jobs"), list) or (
        jobs.get("total_count") != len(jobs["jobs"]) or len(jobs["jobs"]) >= 100
    ):
        raise AuditDenied("JOB_PAGINATION_INCOMPLETE")
    selected = [j for j in jobs["jobs"] if isinstance(j, dict) and j.get("name") == "candidate-receipt"]
    if len(selected) != 1:
        raise AuditDenied("CANDIDATE_JOB_MISSING_OR_DUPLICATE")
    job = selected[0]
    if not positive(job.get("id")) or not positive(job.get("runner_id")) or (
        job.get("run_id") != run_id or job.get("run_attempt") != attempt or
        job.get("head_sha") != expected_head or job.get("status") != "completed" or
        job.get("conclusion") != "success" or not isinstance(job.get("steps"), list) or
        len(job["steps"]) == 0
    ):
        raise AuditDenied("CANDIDATE_JOB_NOT_EXECUTED")
    if any(not isinstance(s, dict) or not positive(s.get("number")) for s in job["steps"]) or (
        len({s["number"] for s in job["steps"]}) != len(job["steps"])
    ):
        raise AuditDenied("JOB_STEP_IDENTITY_INVALID")
    for required in (CHECKOUT_STEP, TEST_STEP, EMIT_STEP, UPLOAD_STEP):
        matches = [s for s in job["steps"] if s.get("name") == required]
        if len(matches) != 1 or matches[0].get("status") != "completed" or matches[0].get("conclusion") != "success":
            raise AuditDenied("REQUIRED_JOB_STEP_NOT_SUCCESSFUL")
    manifest, package = _zip_manifest(raw)
    values = {
        "schema": "atto.source-bound-release-candidate.v1",
        "classification": "CANDIDATE_ONLY_UNTRUSTED_UNTIL_INDEPENDENT_VERIFICATION",
        "repository": repo,
        "event": "pull_request",
        "run_id": run_id,
        "run_attempt": attempt,
        "job_key": "candidate-receipt",
        "source_head_sha": expected_head,
        "source_tree_sha": expected_tree,
        "signature_verified": False,
        "independent_approval_verified": False,
        "compiler_guest_execution_verified": False,
        "merge_authorized": False,
    }
    if any(manifest.get(key) != value for key, value in values.items()) or manifest.get("artifact") != {
        "path": "dist/Oreslang.sublime-package",
        "sha256": hashlib.sha256(package).hexdigest(),
        "size_bytes": len(package),
    } or set(manifest) != set(values) | {"artifact"}:
        raise AuditDenied("CANDIDATE_MANIFEST_CONTENTS_UNVERIFIED")
    return {
        "classification": "SOURCE_BOUND_CANDIDATE_INTEGRITY_VERIFIED_ONLY",
        "repository": repo,
        "head_sha": expected_head,
        "tree_sha": expected_tree,
        "pr_number": pr_number,
        "run_id": run_id,
        "run_attempt": attempt,
        "numeric_job_id": job["id"],
        "artifact_id": artifact_id,
        "uploaded_zip_sha256": sha_zip,
        "package_sha256": manifest["artifact"]["sha256"],
        "signature_verified": False,
        "independent_approval_verified": False,
        "merge_authorized": False,
        "guest_parity": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True, type=Path)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr", type=int, required=True)
    parser.add_argument("--artifact-id", type=int, required=True)
    parser.add_argument("--head", required=True)
    parser.add_argument("--tree", required=True)
    a = parser.parse_args()
    try:
        token = os.environ.get("GITHUB_TOKEN")
        if not token:
            raise AuditDenied("GITHUB_TOKEN_REQUIRED")
        result = verify_candidate(a.zip, a.repository, a.pr, a.artifact_id,
                                  a.head, a.tree, lambda path: github_get_json(token, path))
        print(json.dumps(result, sort_keys=True))
    except (AuditDenied, OSError) as exc:
        print(json.dumps({"classification": "UNVERIFIED", "reason": str(exc)}))
        raise SystemExit(1)
