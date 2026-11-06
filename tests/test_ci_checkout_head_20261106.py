"""Local Git identity admissions; never claims compiler/guest execution."""
import os
import re
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


if __name__ == "__main__":
    unittest.main()
