"""Offline CODEOWNERS policy checks. Not proof of GitHub branch enforcement."""
import re
import unittest
from pathlib import Path

POLICY = Path(__file__).resolve().parents[1] / ".github" / "CODEOWNERS"
EXPECTED = (
    ("*", "@ORESoftware"),
    ("/.github/workflows/", "@ORESoftware"),
    ("/scripts/", "@ORESoftware"),
    ("/tools/", "@ORESoftware"),
    ("/tests/", "@ORESoftware"),
)
ALLOWED = re.compile(r"(?:\*|/[A-Za-z0-9_./-]+/) @[A-Za-z0-9-]+\Z")


def parse_policy(text):
    """Accept only the deliberately small CODEOWNERS dialect used here."""
    result = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not ALLOWED.fullmatch(line):
            raise ValueError(f"invalid CODEOWNERS entry on line {lineno}")
        pattern, owner = line.split()
        if (pattern, owner) in result:
            raise ValueError("duplicate CODEOWNERS entry")
        result.append((pattern, owner))
    return tuple(result)


def require_policy(text):
    parsed = parse_policy(text)
    if parsed != EXPECTED:
        raise ValueError("CODEOWNERS policy drift: missing/extra/reordered ownership")
    return parsed


def owners_for(path, policy):
    """Model only the star/root-directory patterns in EXPECTED, last match wins."""
    if path.startswith("/") or ".." in path.split("/"):
        raise ValueError("invalid repository-relative path")
    owner = None
    for pattern, current in policy:
        if pattern == "*" or path.startswith(pattern.lstrip("/")):
            owner = current
    return owner


class CodeownersPolicyTests(unittest.TestCase):
    def test_policy_file_is_valid_and_exact(self):
        content = POLICY.read_text(encoding="utf-8")
        self.assertEqual(require_policy(content), EXPECTED)

    def test_every_release_and_security_path_has_a_reviewer(self):
        policy = require_policy(POLICY.read_text(encoding="utf-8"))
        for path in (
            ".github/workflows/ci.yml",
            ".github/CODEOWNERS",
            "scripts/verify_ci_checkout_head.sh",
            "scripts/build_sublime_package.py",
            "tools/package_sublime.py",
            "tests/test_ci_checkout_head_20261106.py",
            "Oreslang.sublime-syntax",
            "oreslang.py",
            "README.md",
        ):
            with self.subTest(path=path):
                self.assertEqual(owners_for(path, policy), "@ORESoftware")

    def test_missing_default_owner_fails_closed(self):
        data = POLICY.read_text(encoding="utf-8").replace("* @ORESoftware\n", "")
        with self.assertRaisesRegex(ValueError, "policy drift"):
            require_policy(data)

    def test_late_override_owner_fails_closed(self):
        data = POLICY.read_text(encoding="utf-8") + "* @other\n"
        with self.assertRaisesRegex(ValueError, "policy drift"):
            require_policy(data)

    def test_empty_owner_and_invalid_syntax_fail_closed(self):
        for text in ("*\n", "* @\n", "!/scripts/ @ORESoftware\n", "[a-z] @ORESoftware\n"):
            with self.subTest(text=text):
                with self.assertRaisesRegex(ValueError, "invalid CODEOWNERS"):
                    parse_policy(text)

    def test_duplicate_owner_entry_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate CODEOWNERS"):
            parse_policy("* @ORESoftware\n* @ORESoftware\n")


if __name__ == "__main__":
    unittest.main()
