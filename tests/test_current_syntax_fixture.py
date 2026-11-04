import pathlib
import unittest
ROOT = pathlib.Path(__file__).resolve().parents[1]
class CurrentNativeSyntaxInventory(unittest.TestCase):
    def test_default_compiler_current_native_syntax_oracles_exist(self):
        source = (ROOT / "syntax_test_compiler_current.ores").read_text(encoding="utf8")
        self.assertEqual(source.splitlines()[0],
            '// SYNTAX TEST "Packages/Oreslang/Oreslang.sublime-syntax"')
        self.assertGreaterEqual(source.count("keyword.oreslang"), 7)
        self.assertIn("keyword.operator.comparison.oreslang", source)
        self.assertIn("keyword.operator.oreslang", source)
        for value in ("isoactor", "null", "panic", "cpu", "gpu"):
            self.assertIn(value, source)
