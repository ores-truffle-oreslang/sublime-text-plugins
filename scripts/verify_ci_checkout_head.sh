#!/usr/bin/env bash
# Source-owned CI preflight only: verifies exact checked-out Git identity and bytes.
set -euo pipefail
export LC_ALL=C

fail() {
  printf 'EXACT_HEAD_ADMISSION_DENIED: %s\n' "$1" >&2
  exit 65
}

expected="${EXPECTED_HEAD:-}"
[[ "$expected" =~ ^[0-9a-f]{40}$ ]] || fail "missing or malformed expected commit"

# Git control variables can redirect rev-parse to an unrelated repository.
# A source checkout must not borrow identity from the caller environment.
while IFS='=' read -r name _; do
  [[ "$name" != GIT_* ]] || fail "inherited Git control environment"
done < <(env)

root="$(pwd -P)"
actual_root="$(/usr/bin/git -C "$root" rev-parse --show-toplevel 2>/dev/null)" ||
  fail "not a Git checkout"
[[ "$(cd "$actual_root" && pwd -P)" == "$root" ]] ||
  fail "not at checkout root"

actual="$(/usr/bin/git -C "$root" rev-parse --verify 'HEAD^{commit}' 2>/dev/null)" ||
  fail "missing HEAD commit"
[[ "$actual" == "$expected" ]] || fail "checked-out HEAD does not match expected commit"

tree="$(/usr/bin/git -C "$root" rev-parse --verify 'HEAD^{tree}' 2>/dev/null)" ||
  fail "missing HEAD tree"
[[ "$tree" =~ ^[0-9a-f]{40}$ ]] || fail "invalid HEAD tree identity"
# Git's assume-unchanged and skip-worktree index bits can hide altered files
# from status/diff even when HEAD and the Git tree are correct. Fail closed on
# any nonordinary index tag before inspecting worktree changes.
index_entries="$(/usr/bin/git -c core.fsmonitor=false -c core.quotePath=true \
  -C "$root" ls-files -v 2>/dev/null)" ||
  fail "cannot inspect Git index flags"
[[ -n "$index_entries" ]] || fail "empty checked-out Git index"
while IFS= read -r entry; do
  [[ "$entry" == "H "* ]] || fail "unsafe Git index flags"
done <<< "$index_entries"

# Exact HEAD alone is not an exact-source proof: smudged, staged, modified,
# untracked or ignored working-tree files can change what a later test executes.
# Disable filesystem monitors and avoid hooks / external diff commands.
tracked_or_untracked="$(/usr/bin/git -c core.fsmonitor=false -c core.hooksPath=/dev/null \
  -C "$root" status --porcelain=v1 --untracked-files=all 2>/dev/null)" ||
  fail "cannot inspect checkout worktree"
[[ -z "$tracked_or_untracked" ]] || fail "checkout has staged, modified or untracked files"
ignored="$(/usr/bin/git -c core.fsmonitor=false -c core.hooksPath=/dev/null \
  -C "$root" ls-files --others --ignored --exclude-standard 2>/dev/null)" ||
  fail "cannot inspect ignored checkout files"
[[ -z "$ignored" ]] || fail "checkout has ignored files"

printf 'EXACT_SOURCE_HEAD=%s\nEXACT_SOURCE_TREE=%s\n' "$actual" "$tree"
