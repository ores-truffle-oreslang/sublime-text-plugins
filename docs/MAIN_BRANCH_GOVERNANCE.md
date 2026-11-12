# Sublime main — reviewable but not installed GitHub ruleset

**2026-11-12 observed state: NOT ENFORCED.** `GET /repos/ores-truffle-oreslang/sublime-text-plugins/rulesets` returned `[]`. The repository's CODEOWNERS file requests one independent review from `ORESoftware` or `the1mills`, but neither this file nor the ruleset template enables branch protection by itself.

An authorized GitHub administrator must create an **active branch ruleset** for `refs/heads/main` from the proposed payload in `.github/policies/main-ruleset.proposed.json`. Require PR review by an independent CODEOWNER after the last push, reject stale approvals, resolve threads, deny bypasses/force pushes/deletion, and require the observed GitHub Actions App ID `15368` check contexts `package`, `sublime-syntax-engine`, and `release-package`. These three jobs run on both PR heads and main; do not require `signed-main-release` on PR heads because that signing job is intentionally main-only.

This file documents a desired **external GitHub setting**, not proof of installation or CI execution. The connected GitHub app cannot inspect branch-protection policy (403), and it cannot install rulesets through the available connector. An administrator must read back the effective ruleset, and a harmless test PR should demonstrate that missing independent approval or a failed, stale, or zero-step check truly blocks a merge.

A source-bound unsigned candidate receipt, signed main release provenance, or model test alone never authorizes a PR merge or release. For every PR retain immutable head/tree and actual executed test steps.
