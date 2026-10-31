import json
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CORPUS = json.loads((ROOT / "conformance" / "oreslang-syntax-v1.json").read_text(encoding="utf-8"))
SYNTAX = (ROOT / "Oreslang.sublime-syntax").read_text(encoding="utf-8")


def yaml_single_quoted_variable(key):
    line = next(line.strip() for line in SYNTAX.splitlines()
                if line.strip().startswith(key + ":"))
    return line.split(": ", 1)[1].strip()[1:-1].replace("''", "'")


class SharedLexerConformance(unittest.TestCase):
    def test_upstream_observation_is_distinct_from_editor_target(self):
        self.assertEqual("oreslang.editor-syntax-conformance/v1", CORPUS["schema"])
        self.assertEqual("ores-truffle-oreslang/oreslang-source.java",
                         CORPUS["authority"]["repo"])
        self.assertIn("null", CORPUS["profiles"]["compilerMainObservation"]["reserved"])
        self.assertIn("null", CORPUS["profiles"]["editorTarget"]["excludedReservedWords"])
        self.assertEqual(2, len(CORPUS["authority"]["files"]))
        self.assertEqual(len(CORPUS["cases"]),
                         len({case["id"] for case in CORPUS["cases"]}))

    def test_positive_negative_fixture_vocabulary(self):
        keywords = re.compile(yaml_single_quoted_variable("keywords"))
        controls = re.compile(yaml_single_quoted_variable("global_controls"))
        compound = re.compile(r"\b(?:critical-read|critical-write|nb-select|transform-pipe)\b")
        for fixture in CORPUS["cases"]:
            with self.subTest(fixture=fixture["id"]):
                for word in fixture["keywords"]:
                    matcher = compound if word in CORPUS["profiles"]["editorTarget"]["compoundForms"] else keywords
                    self.assertIsNotNone(matcher.fullmatch(word), word)
                for word in fixture["notKeywords"]:
                    # A valid reserved keyword inside an opaque comment/string
                    # remains a *reserved spelling* outside that region. Only
                    # full editor tokenization (not this regex source test) can
                    # prove the region is masked. Keep those checks separate.
                    if fixture["id"] in {
                            "nested-comments", "quoted-string",
                            "template-body", "unicode-string"}:
                        self.assertIn(word, fixture["source"])
                    else:
                        self.assertIsNone(keywords.fullmatch(word), word)
                        self.assertIsNone(compound.fullmatch(word), word)
                for word in fixture["globals"]:
                    self.assertIsNotNone(controls.fullmatch(word), word)
                for word in fixture["notGlobals"]:
                    # These appear inside comments/strings; the source grammar
                    # must mask them rather than globally forbid their spelling.
                    self.assertIn(word, fixture["source"])

    def test_compound_hash_and_opaque_regions_have_priority(self):
        main = SYNTAX.split("  main:", 1)[1].split("\n  comments:", 1)[0]
        self.assertLess(main.index("- include: comments"), main.index("- match: '{{keywords}}'"))
        self.assertLess(main.index("- include: strings"), main.index("- match: '{{keywords}}'"))
        self.assertLess(main.index("critical-read|critical-write|nb-select|transform-pipe"),
                        main.index("- match: '{{keywords}}'"))
        self.assertIn("push: block-comment", SYNTAX)
        self.assertIn("  block-comment:\n", SYNTAX)
        self.assertIn("string.quoted.template.oreslang", SYNTAX)
        symbol_line = next(line.strip() for line in main.splitlines()
                           if line.strip().startswith("- match: '#(?:"))
        expression = symbol_line[len("- match: '"):-1].replace("''", "'")
        expression = expression.replace("{{identifier}}", "[A-Za-z_][A-Za-z0-9_]*")
        symbol_re = re.compile(expression)
        for fixture in CORPUS["cases"]:
            for literal in fixture["symbols"]:
                self.assertIsNotNone(symbol_re.fullmatch(literal), literal)

    def test_excluded_operator_forms_do_not_get_valid_operator_scope(self):
        operator = next(line.strip() for line in SYNTAX.splitlines()
                        if line.strip().startswith("- match: '=>|->|"))
        operator_re = re.compile(operator[len("- match: '"):-1])
        for removed in CORPUS["profiles"]["editorTarget"]["excludedArithmeticOperators"]:
            self.assertIsNone(operator_re.fullmatch(removed), removed)


if __name__ == "__main__":
    unittest.main()
