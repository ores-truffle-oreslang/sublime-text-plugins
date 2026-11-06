"""Mocked authenticated-source verification; no GitHub secrets or writes."""
from __future__ import annotations

import copy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from scripts.audit_source_bound_candidate_v1 import (AuditDenied, verify_candidate,
                                                      github_get_json)

A = "a" * 40
B = "b" * 40
REPO = "ores-truffle-oreslang/sublime-text-plugins"
BASE = "/repos/" + REPO
ZIP = b"zip container stub"


def package_zip(manifest, package=b"PK\x03\x04fixture"):
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("Oreslang.sublime-package", package)
        z.writestr("source-bound-release-receipt-v1.json", json.dumps(manifest))
    return buf.getvalue()


def fake():
    manifest = {
        "schema": "atto.source-bound-release-candidate.v1",
        "classification": "CANDIDATE_ONLY_UNTRUSTED_UNTIL_INDEPENDENT_VERIFICATION",
        "repository": REPO, "event": "pull_request", "run_id": 51,
        "run_attempt": 2, "job_key": "candidate-receipt",
        "source_head_sha": A, "source_tree_sha": B,
        "artifact": {"path": "dist/Oreslang.sublime-package",
                     "sha256": hashlib.sha256(b"PK\x03\x04fixture").hexdigest(),
                     "size_bytes": len(b"PK\x03\x04fixture")},
        "signature_verified": False, "independent_approval_verified": False,
        "compiler_guest_execution_verified": False, "merge_authorized": False,
    }
    raw = package_zip(manifest)
    run = {"id":51,"run_attempt":2,"event":"pull_request","head_sha":A,
           "path":".github/workflows/source-bound-release-provenance-v1.yml",
           "status":"completed","conclusion":"success",
           "repository":{"id":111,"full_name":REPO}}
    job = {"id":71,"name":"candidate-receipt","run_id":51,"run_attempt":2,
           "head_sha":A,"runner_id":999,"status":"completed","conclusion":"success",
           "steps":[{"number":i+1,"name":n,"status":"completed","conclusion":"success"}
                    for i,n in enumerate([
                        "Verify immutable source head and physical Git tree",
                        "Run source-bound candidate receipt negative controls",
                        "Emit unsigned source-bound candidate receipt",
                        "Upload candidate source-bound receipt (not signed)"])]}
    values={
        BASE+"/actions/artifacts/91": {"id":91,"expired":False,
            "digest":"sha256:"+hashlib.sha256(raw).hexdigest(),
            "size_in_bytes":len(raw),"workflow_run":{"id":51,"repository_id":111,"head_sha":A}},
        BASE+"/actions/runs/51": run,
        BASE+"/git/commits/"+A: {"sha":A,"tree":{"sha":B}},
        BASE+"/pulls/7": {"number":7,"head":{"sha":A},"base":{"repo":{"full_name":REPO}}},
        BASE+"/actions/runs/51/attempts/2/jobs?per_page=100&page=1": {"total_count":1,"jobs":[job]}
    }
    return manifest, raw, values


class CandidateAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/"candidate.zip"
        self.manifest,self.raw,self.data=fake()
        self.path.write_bytes(self.raw)
        self.calls=[]

    def get(self,path):
        self.calls.append(path)
        return copy.deepcopy(self.data[path])

    def audit(self):
        return verify_candidate(self.path,REPO,7,91,A,B,self.get)

    def test_positive_integrity_is_not_merge_or_signature_proof(self):
        x=self.audit()
        self.assertEqual(x["classification"],"SOURCE_BOUND_CANDIDATE_INTEGRITY_VERIFIED_ONLY")
        self.assertEqual(x["numeric_job_id"],71)
        self.assertEqual(x["run_attempt"],2)
        self.assertFalse(x["merge_authorized"])
        self.assertFalse(x["signature_verified"])
        self.assertFalse(x["independent_approval_verified"])
        self.assertEqual(len(self.calls),5)

    def test_zip_mutation_digest_mismatch_rejected(self):
        with self.path.open("ab") as f: f.write(b"x")
        with self.assertRaisesRegex(AuditDenied,"DIGEST_OR_SIZE_MISMATCH"):
            self.audit()

    def test_duplicate_or_extra_zip_member_rejected(self):
        for extra in ["../evil", "extra.txt", "Oreslang.sublime-package"]:
            with self.subTest(extra=extra):
                with zipfile.ZipFile(self.path,"a") as f: f.writestr(extra,b"x")
                raw=self.path.read_bytes()
                self.data[BASE+"/actions/artifacts/91"]["digest"]="sha256:"+hashlib.sha256(raw).hexdigest()
                self.data[BASE+"/actions/artifacts/91"]["size_in_bytes"]=len(raw)
                with self.assertRaisesRegex(AuditDenied,"ZIP_MEMBER_SET_INVALID"):
                    self.audit()
                self.path.write_bytes(self.raw)

    def test_manifest_forged_head_and_approval_rejected(self):
        for key,value in [("source_head_sha","c"*40),("merge_authorized",True),
                          ("signature_verified",True),("run_attempt",1),
                          ("job_key","signed-main-release")]:
            with self.subTest(key=key):
                m=copy.deepcopy(self.manifest);m[key]=value
                self.path.write_bytes(package_zip(m))
                raw=self.path.read_bytes()
                self.data[BASE+"/actions/artifacts/91"]["digest"]="sha256:"+hashlib.sha256(raw).hexdigest()
                self.data[BASE+"/actions/artifacts/91"]["size_in_bytes"]=len(raw)
                with self.assertRaisesRegex(AuditDenied,"MANIFEST_CONTENTS_UNVERIFIED"):
                    self.audit()

    def test_admin_style_forged_job_and_step_metadata_rejected(self):
        mutations=[
            lambda j:j.update(runner_id=0),
            lambda j:j.update(run_attempt=3),
            lambda j:j.update(steps=[]),
            lambda j:j["steps"][0].update(conclusion="failure"),
            lambda j:j["steps"][1].update(name="not a security test"),
            lambda j:j["steps"][2].update(number=1),
        ]
        for i,mutate in enumerate(mutations):
            with self.subTest(mutation=i):
                _,_,data=fake();self.data=data
                job=self.data[BASE+"/actions/runs/51/attempts/2/jobs?per_page=100&page=1"]["jobs"][0]
                mutate(job)
                with self.assertRaises(AuditDenied): self.audit()

    def test_untrusted_run_artifact_pr_tree_metadata_rejected(self):
        cases=[
            (BASE+"/actions/runs/51",("head_sha","c"*40)),
            (BASE+"/actions/runs/51",("conclusion","failure")),
            (BASE+"/git/commits/"+A,("sha","c"*40)),
            (BASE+"/pulls/7",("number",8)),
            (BASE+"/actions/artifacts/91",("expired",True)),
            (BASE+"/actions/artifacts/91",("id",92))
        ]
        for key,(field,value) in cases:
            with self.subTest(field=field):
                _,_,data=fake();self.data=data;self.data[key][field]=value
                with self.assertRaises(AuditDenied):self.audit()

    def test_incomplete_job_pagination_fails_closed(self):
        key=BASE+"/actions/runs/51/attempts/2/jobs?per_page=100&page=1"
        self.data[key]["total_count"]=101
        with self.assertRaisesRegex(AuditDenied,"JOB_PAGINATION_INCOMPLETE"):
            self.audit()

    def test_forged_expectations_rejected_without_fetch(self):
        for repo,pr,aid,head,tree in [
            ("evil/repo",7,91,A,B), (REPO,0,91,A,B),(REPO,7,0,A,B),
            (REPO,7,91,"f",B),(REPO,7,91,A,"z"*40)
        ]:
            with self.assertRaisesRegex(AuditDenied,"INVALID_AUDIT_EXPECTATIONS"):
                verify_candidate(self.path,repo,pr,aid,head,tree,self.get)
        self.assertEqual(self.calls,[])

    def test_symlinked_zip_and_hardlink_rejected(self):
        linked=Path(self.tmp.name)/"linked.zip"
        linked.symlink_to(self.path)
        with self.assertRaisesRegex(AuditDenied,"ZIP_SYMLINK_OR_PATH_INVALID"):
            verify_candidate(linked,REPO,7,91,A,B,self.get)
        linked.unlink();os=__import__("os");os.link(self.path,linked)
        with self.assertRaisesRegex(AuditDenied,"ZIP_TYPE_LINK_OR_SIZE_INVALID"):
            self.audit()

    def test_github_api_get_path_allowlist_rejects_before_connecting(self):
        for path in [
            "https://evil.example/file", "/repos/evil/repo/actions/runs/1",
            BASE+"/contents/README.md", BASE+"/actions/jobs/7/logs",
            BASE+"/actions/artifacts/../7", BASE+"/actions/runs/1?token=x"
        ]:
            with self.subTest(path=path), self.assertRaisesRegex(AuditDenied,"GITHUB_METADATA_PATH_DENIED"):
                github_get_json("secret",path)


if __name__ == "__main__":
    unittest.main()
