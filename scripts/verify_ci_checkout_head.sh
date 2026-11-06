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
# Explicitly pin filesystem interpretation rather than trusting attacker-controlled\n# core.filemode, core.symlinks, core.ignorecase or cached stat settings.\n# Disable filesystem monitors and avoid hooks / external diff commands.
# Compare staged Git index directly with HEAD, without worktree clean filters.
/usr/bin/git -C "$root" diff-index --cached --quiet --no-ext-diff HEAD -- ||
  fail "checkout has staged, modified or untracked files"
untracked="$(/usr/bin/git -c core.fsmonitor=false -c core.ignorecase=false \
  -c core.untrackedCache=false -C "$root" ls-files --others --exclude-standard 2>/dev/null)" ||
  fail "cannot inspect untracked checkout files"
[[ -z "$untracked" ]] || fail "checkout has staged, modified or untracked files"

ignored="$(/usr/bin/git -c core.fsmonitor=false -c core.hooksPath=/dev/null \
  -c core.ignorecase=false -c core.untrackedCache=false \
  -C "$root" ls-files --others --ignored --exclude-standard 2>/dev/null)" ||
  fail "cannot inspect ignored checkout files"
[[ -z "$ignored" ]] || fail "checkout has ignored files"


# Git status can be spoofed by local clean filters, even when HEAD is correct.
# Hash raw physical tracked source against the immutable HEAD blobs, never
# through Git's clean/smudge filters. Preserve newline- and tab-bearing paths.
/usr/bin/git -C "$root" ls-tree -r -z HEAD |
while IFS= read -r -d '' item; do
  [[ "$item" == *
\t'* ]] || fail "malformed Git tree entry"
  meta="${item%%
\t'*}"
  path="${item#*
\t'}"
  mode="${meta%% *}"
  type_and_oid="${meta#* }"
  type="${type_and_oid%% *}"
  blob="${type_and_oid##* }"
  [[ "$type" == blob && "$blob" =~ ^[0-9a-f]{40}$ && -n "$path" ]] ||
    fail "invalid tracked Git blob"
  case "$mode" in
    100644|100755)
      [[ -f "$root/$path" && ! -L "$root/$path" ]] ||
        fail "tracked file type differs from HEAD"
      if [[ "$mode" == 100755 ]]; then
        [[ -x "$root/$path" ]] || fail "tracked executable mode differs from HEAD"
      else
        [[ ! -x "$root/$path" ]] || fail "tracked executable mode differs from HEAD"
      fi
      digest="$(/usr/bin/git -C "$root" hash-object --no-filters -- "$root/$path")" ||
        fail "cannot hash tracked source"
      ;;
    120000)
      [[ -L "$root/$path" ]] || fail "tracked symlink type differs from HEAD"
      digest="$(readlink -n -- "$root/$path" |
        /usr/bin/git -C "$root" hash-object --no-filters --stdin)" ||
        fail "cannot hash tracked symlink"
      ;;
    *) fail "unsupported tracked Git mode" ;;
  esac
  [[ "$digest" == "$blob" ]] || fail "physical source bytes differ from HEAD"
done

printf 'EXACT_SOURCE_HEAD=%s\nEXACT_SOURCE_TREE=%s\n' "$actual" "$tree"
