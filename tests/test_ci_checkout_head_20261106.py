"""Local Git identity admissions; never claims compiler/guest execution."""
import os
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_ci_checkout_head.sh"


class ExactSourceCheckoutGate(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "repo"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "ci-fixture@example.invalid")
        self.git("config", "user.name", "CI Fixture")
        (self.root / "source.atto").write_text("fnc main(): int { return 1; }\n", encoding="utf-8")
        self.git("add", "source.atto")
        self.git("commit", "-qm", "initial fixture")
        self.head = self.git("rev-parse", "HEAD").stdout.strip()

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args],
                              check=True, capture_output=True, text=True)

    def check(self, expected=None, directory=None, inherited=None):
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        if expected is not None:
            env["EXPECTED_HEAD"] = expected
        else:
            env.pop("EXPECTED_HEAD", None)
        env.update(inherited or {})
        return subprocess.run(["bash", str(SCRIPT)], cwd=directory or self.root,
                              env=env, capture_output=True, text=True)

    def test_exact_original_head_is_accepted(self):
        result = self.check(self.head)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("EXACT_SOURCE_HEAD=" + self.head, result.stdout)
        self.assertRegex(result.stdout, r"EXACT_SOURCE_TREE=[0-9a-f]{40}\n")

    def test_wrong_head_is_denied(self):
        result = self.check("0" * 40)
        self.assertEqual(result.returncode, 65)
        self.assertIn("does not match", result.stderr)
        self.assertNotIn("EXACT_SOURCE_HEAD=", result.stdout)

    def test_same_git_tree_different_commit_is_denied(self):
        self.git("commit", "--allow-empty", "-qm", "same tree, new commit")
        self.assertNotEqual(self.git("rev-parse", "HEAD").stdout.strip(), self.head)
        self.assertEqual(self.git("rev-parse", "HEAD^{tree}").stdout.strip(),
                         self.git("rev-parse", "HEAD~1^{tree}").stdout.strip())
        result = self.check(self.head)
        self.assertEqual(result.returncode, 65)
        self.assertIn("does not match", result.stderr)

    def test_malformed_and_missing_expectations_are_denied(self):
        for value in (None, "", "A" * 40, "0" * 39, self.head + "\n"):
            with self.subTest(expected=value):
                result = self.check(value)
                self.assertEqual(result.returncode, 65)
                self.assertIn("malformed expected commit", result.stderr)

    def test_inherited_git_directory_redirect_is_denied(self):
        result = self.check(self.head, inherited={"GIT_DIR": str(self.root / ".git")})
        self.assertEqual(result.returncode, 65)
        self.assertIn("inherited Git control environment", result.stderr)

    def test_nested_directory_cannot_impersonate_checkout_root(self):
        nested = self.root / "nested"
        nested.mkdir()
        result = self.check(self.head, directory=nested)
        self.assertEqual(result.returncode, 65)
        self.assertIn("not at checkout root", result.stderr)


    def assert_dirty_denied(self, expected="checkout has staged, modified or untracked files"):
        result = self.check(self.head)
        self.assertEqual(result.returncode, 65, result.stdout + result.stderr)
        self.assertIn(expected, result.stderr)
        self.assertNotIn("EXACT_SOURCE_HEAD=", result.stdout)

    def test_modified_tracked_source_is_denied_despite_matching_head(self):
        (self.root / "source.atto").write_text("fnc main(): int { return 9; }\n", encoding="utf-8")
        self.assert_dirty_denied("physical source bytes differ from HEAD")

    def test_staged_source_rewrite_is_denied_despite_matching_head(self):
        (self.root / "source.atto").write_text("fnc main(): int { return 9; }\n", encoding="utf-8")
        self.git("add", "source.atto")
        self.assert_dirty_denied()

    def test_untracked_checkout_file_is_denied_despite_matching_head(self):
        (self.root / "foreign.atto").write_text("fnc main(): int { return 2; }\n", encoding="utf-8")
        self.assert_dirty_denied()

    def test_ignored_checkout_file_is_denied_despite_matching_head(self):
        (self.root / ".gitignore").write_text("ignored.atto\n", encoding="utf-8")
        self.git("add", ".gitignore")
        self.git("commit", "-qm", "fixture ignore rule")
        self.head = self.git("rev-parse", "HEAD").stdout.strip()
        (self.root / "ignored.atto").write_text("fnc main(): int { return 2; }\n", encoding="utf-8")
        self.assert_dirty_denied("checkout has ignored files")

    def test_assume_unchanged_does_not_hide_tampered_source(self):
        self.git("update-index", "--assume-unchanged", "source.atto")
        (self.root / "source.atto").write_text("MALICIOUS\n", encoding="utf-8")
        self.assert_dirty_denied("unsafe Git index flags")

    def test_skip_worktree_does_not_hide_tampered_source(self):
        self.git("update-index", "--skip-worktree", "source.atto")
        (self.root / "source.atto").write_text("MALICIOUS\n", encoding="utf-8")
        self.assert_dirty_denied("unsafe Git index flags")

    def test_core_filemode_false_cannot_hide_exec_bit_change(self):
        script = self.root / "run.sh"
        script.write_text("#!/bin/sh\necho hello\n", encoding="utf-8")
        script.chmod(0o644)
        self.git("add", "run.sh")
        self.git("commit", "-qm", "tracked non-executable script")
        self.head = self.git("rev-parse", "HEAD").stdout.strip()
        script.chmod(0o755)
        self.git("config", "core.filemode", "false")
        self.assert_dirty_denied("tracked executable mode differs from HEAD")

    def test_core_symlinks_false_cannot_hide_replaced_symlink(self):
        link = self.root / "source-alias.atto"
        link.symlink_to("source.atto")
        self.git("add", "source-alias.atto")
        self.git("commit", "-qm", "tracked symlink")
        self.head = self.git("rev-parse", "HEAD").stdout.strip()
        link.unlink()
        link.write_text("source.atto", encoding="utf-8")
        self.git("config", "core.symlinks", "false")
        self.assert_dirty_denied("tracked symlink type differs from HEAD")

    def test_core_ignorecase_true_cannot_hide_case_variant_new_file(self):
        (self.root / "SOURCE.atto").write_text("untracked attacker source\n", encoding="utf-8")
        self.git("config", "core.ignorecase", "true")
        self.assert_dirty_denied()

    def test_clean_checkout_is_accepted_with_relaxed_repository_git_config(self):
        for key, value in (("core.filemode", "false"), ("core.symlinks", "false"),
                           ("core.ignorecase", "true"), ("core.checkstat", "minimal"),
                           ("core.trustctime", "false"), ("core.untrackedCache", "true")):
            self.git("config", key, value)
        result = self.check(self.head)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("EXACT_SOURCE_HEAD=" + self.head, result.stdout)

    def test_git_clean_filter_cannot_launder_or_execute_when_auditing(self):
        # Git status runs clean filters, which can both hide modified bytes
        # and execute a command supplied by repository-local Git config.
        (self.root / ".gitattributes").write_text("source.atto filter=scrub\n", encoding="utf-8")
        self.git("add", ".gitattributes")
        self.git("commit", "-qm", "tracked filter attribute")
        self.head = self.git("rev-parse", "HEAD").stdout.strip()
        marker = Path(self.temporary.name) / "filter-invoked"
        cleaner = Path(self.temporary.name) / "cleaner.sh"
        cleaner.write_text("#!/bin/sh\nprintf touched > " + shlex.quote(str(marker)) +
                           "\nsed s/9/1/g\n", encoding="utf-8")
        cleaner.chmod(0o755)
        self.git("config", "filter.scrub.clean", shlex.quote(str(cleaner)))
        (self.root / "source.atto").write_text("fnc main(): int { return 9; }\n", encoding="utf-8")
        # Demonstrate the false-green status and actual filter invocation.
        self.assertEqual(self.git("status", "--porcelain=v1").stdout.strip(), "")
        self.assertTrue(marker.exists())
        marker.unlink()
        self.assert_dirty_denied("physical source bytes differ from HEAD")
        self.assertFalse(marker.exists(), "the preflight must never run clean filters")

    def test_unchanged_tracked_symlink_is_accepted_by_raw_tree_gate(self):
        (self.root / "source-link.atto").symlink_to("source.atto")
        self.git("add", "source-link.atto")
        self.git("commit", "-qm", "tracked symlink")
        self.head = self.git("rev-parse", "HEAD").stdout.strip()
        result = self.check(self.head)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_unusual_tracked_filename_is_hashed_without_splitting(self):
        (self.root / "line\nname\t.atto").write_text("safe\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "tracked unusual filename")
        self.head = self.git("rev-parse", "HEAD").stdout.strip()
        result = self.check(self.head)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_untracked_symlink_is_denied(self):
        (self.root / "foreign.atto").symlink_to("source.atto")
        self.assert_dirty_denied()


if __name__ == "__main__":
    unittest.main()
