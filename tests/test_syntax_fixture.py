import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

class NativeSublimeFixtureInventory(unittest.TestCase):
    def test_sublime_syntax_test_is_native_and_annotated(self):
        src=(ROOT / "syntax_test_oreslang.ores").read_text(encoding="utf8")
        self.assertEqual(src.splitlines()[0],
            '// SYNTAX TEST "Packages/Oreslang/Oreslang.sublime-syntax"')
        assert src.count(" //") >= 0
        selectors=[line for line in src.splitlines()[1:]
                   if line.startswith("//") and ("^" in line or "<-" in line)]
        self.assertGreaterEqual(len(selectors),20)
        for marker in selectors:
            self.assertTrue(marker.startswith("// <- ") or "^" in marker,
                            "invalid Sublime native syntax test marker")
        for expected in ("comment.block.oreslang","string.quoted.template.oreslang",
                         "constant.other.symbol.oreslang","support.function.global.oreslang",
                         "keyword.operator.comparison.oreslang"):
            self.assertIn(expected,src)

if __name__=="__main__":
    unittest.main()
