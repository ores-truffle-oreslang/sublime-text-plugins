# Independently verifying a GitHub-signed **main** release (v1)

This module is an offline *policy wrapper around a LIVE official GitHub CLI
cryptographic verification*. It does **not** itself parse or trust arbitrary
signed JSON bundles, doesn't accept `--bundle` or a custom trust root,
and never asserts that the source was reviewed, main is protected, or merging
is allowed.

## What exists today

- [Source-bound release candidate #146](https://github.com/ores-truffle-oreslang/sublime-text-plugins/pull/146)
  emits a candidate receipt on pull requests, with **no signing privileges**.
- The `signed-main-release` workflow job on #146 is allowed to request
  GitHub OIDC credentials **only on push to main**, after the source-bound
  candidate job. **It is not yet merged or executed.**
- [Candidate ZIP auditor #147](https://github.com/ores-truffle-oreslang/sublime-text-plugins/pull/147)
  validates the unsigned candidate against authenticated GitHub workflow,
  run-attempt, job, source SHA/tree, ZIP and raw package byte identities.
- This tool checks the *different* later step: that the raw package is the
  subject of a **cryptographically verified GitHub OIDC/Sigstore attestation**
  with the intended signed workflow and immutable main commit identity.

## External independent verification

Only after the administrator has protected main, independent reviews have
been obtained, and a real main-triggered signed job has succeeded:

1. Download the **raw** `Oreslang.sublime-package` file (not the Actions
   artifact ZIP container) into a private workspace. Independently obtain
   the expected GitHub repository numeric ID, exact main source commit,
   workflow run ID, run attempt and archive SHA-256.
2. On a trusted machine, install an up-to-date official `gh` CLI at
   /usr/bin/gh (not a wrapper on PATH), and authenticate using a
   read-only `GH_TOKEN` with access to the repository's attestations.
3. Run, filling in verified values:

```sh
GH_TOKEN=... python3 scripts/verify_signed_main_attestation_v1.py \
  --artifact ./Oreslang.sublime-package \
  --repository ores-truffle-oreslang/sublime-text-plugins \
  --repository-id <GITHUB_REPOSITORY_NUMERIC_ID> \
  --source-sha <ACTUAL_MAIN_COMMIT_40_HEX> \
  --raw-sha256 <ACTUAL_PACKAGE_SHA256_64_HEX> \
  --run-id <SIGNED_MAIN_WORKFLOW_RUN_ID> \
  --run-attempt <EXECUTED_ATTEMPT>
```

The verifier snapshots and hashes the raw package with no symlink/hardlink
following, then uses official `gh attestation verify` **live GitHub lookup**,
pinning exactly:

- `--repo ores-truffle-oreslang/sublime-text-plugins`
- `--signer-workflow ores-truffle-oreslang/sublime-text-plugins/.github/workflows/source-bound-release-provenance-v1.yml`
- `--source-ref refs/heads/main`
- `--source-digest <expected immutable 40-char SHA>`
- `--cert-oidc-issuer https://token.actions.githubusercontent.com`
- `--deny-self-hosted-runners`
- SLSA provenance v1 predicate, JSON output, limited attestation result count.

Any verifier non-zero exit blocks. The follow-on policy checks **certificate**
fields (not caller-controlled SLSA predicate assertions): repository URL and
numeric ID, source commit, workflow ref, signer subject alternative name,
OIDC issuer, GitHub-hosted runner and exact run invocation / attempt.
It checks transparency timestamps and the attested subject name and SHA256.

The CLI output states
`SIGNED_MAIN_ARTIFACT_PROVENANCE_VERIFIED_ONLY` only upon actual
successful cryptographic verification and full policy match.
`release_authorized` and `merge_authorized` are **always false**.
A signed artifact from an **unprotected main** can be a genuine signature over
unreviewed source, so this is not source admission or approval evidence.

## Negative test scope

```sh
python3 -m unittest discover -s tests -p 'test_verify_signed_main_attestation_v1.py' -v
```

The source-free suite mocks `subprocess.run` and **does not pretend to
cryptographically verify an actual signature**. It checks mandatory CLI
flags, scrubbed host/credential overrides, strict source/hash/run binding,
symlink/hardlink/size limits, forged cert issuer and identity, timestamp
omission, failed verification exit, manipulated predicate claims and
TOCTOU-resistant artifact snapshots.

## Remaining non-optional gates

Real signed-main execution is **NOT_EXECUTED** at writing.
GitHub protected-main rules, genuinely independent code-owner approval,
build isolation, and backend compiler guest test receipts must all be checked
by separate authenticated sources. Do not release or merge merely because
this verification succeeds.

References: [GitHub attestation verify CLI](https://cli.github.com/manual/gh_attestation_verify),
[GitHub artifact attestations](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations).
