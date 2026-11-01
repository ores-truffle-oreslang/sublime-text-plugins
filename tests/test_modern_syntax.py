import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ModernSyntaxContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.syntax = (ROOT / "Oreslang.sublime-syntax").read_text(encoding="utf-8")

    def test_compound_keywords_before_regular_keyword_match(self):
        compound = "critical-read|critical-write|nb-select|transform-pipe"
        self.assertIn(compound, self.syntax)
        self.assertLess(self.syntax.index(compound),
                        self.syntax.index("- match: '{{keywords}}'"))
        self.assertIn("scope: keyword.oreslang", self.syntax)

    def test_hash_symbols_are_scoped_as_symbols(self):
        line = next(line.strip() for line in self.syntax.splitlines()
                    if line.strip().startswith("- match: '#(?:"))
        pattern = line[len("- match: '"):-1].replace("''", "'")
        pattern = pattern.replace("{{identifier}}", "[A-Za-z_][A-Za-z0-9_]*")
        regexp = re.compile(pattern)
        for literal in ("#ready", "#'with spaces'", '#"quoted symbol"'):
            with self.subTest(literal=literal):
                self.assertEqual(regexp.fullmatch(literal).group(0), literal)
        self.assertIn("constant.other.symbol.oreslang", self.syntax)

    def test_canonical_runtime_controls_are_one_scope(self):
        self.assertIn("recover|defer|throw|raise", self.syntax)
        self.assertIn("support.function.global.oreslang", self.syntax)


if __name__ == "__main__":
    unittest.main()
