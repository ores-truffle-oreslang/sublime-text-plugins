#!/usr/bin/env bash
# Source-owned CI preflight only: verifies the checked-out Git identity.
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
printf 'EXACT_SOURCE_HEAD=%s\nEXACT_SOURCE_TREE=%s\n' "$actual" "$tree"
