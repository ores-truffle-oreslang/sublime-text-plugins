import importlib.util
import json
import pathlib
import sys
import types
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class PackageContractTest(unittest.TestCase):
    def test_requested_keywords_share_one_scope(self):
        syntax = (ROOT / "Oreslang.sublime-syntax").read_text()
        requested = {
            "pub", "fnc", "void", "class", "module", "return", "if", "else",
            "elif", "fi", "case", "match", "switch", "try", "catch", "select",
        }
        keyword_line = next(
            line for line in syntax.splitlines() if line.strip().startswith("keywords:")
        )
        for keyword in requested:
            self.assertIn(keyword, keyword_line)
        self.assertIn("scope: keyword.oreslang", syntax)

    def test_global_controls_are_separate(self):
        syntax = (ROOT / "Oreslang.sublime-syntax").read_text()
        global_line = next(
            line for line in syntax.splitlines()
            if line.strip().startswith("global_controls:")
        )
        for name in ("recover", "defer", "throw", "raise"):
            self.assertIn(name, global_line)
        self.assertIn("scope: support.function.global.oreslang", syntax)

    def test_canonical_colors(self):
        scheme = json.loads((ROOT / "Oreslang Magenta.sublime-color-scheme").read_text())
        colors = {rule["scope"]: rule["foreground"] for rule in scheme["rules"]}
        self.assertEqual("#FF00FF", colors["keyword.oreslang"])
        self.assertEqual("#4169E1", colors["support.function.global.oreslang"])

    def test_json_resources_parse(self):
        for name in (
            "Default.sublime-commands",
            "Oreslang.sublime-build",
            "Oreslang.sublime-settings",
        ):
            with self.subTest(name=name):
                json.loads((ROOT / name).read_text())

    def test_plugin_python_compiles(self):
        source = (ROOT / "oreslang.py").read_text()
        compile(source, str(ROOT / "oreslang.py"), "exec")


class DiagnosticParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sublime = types.ModuleType("sublime")
        sublime.DRAW_SQUIGGLY_UNDERLINE = 1
        sublime.DRAW_NO_FILL = 2
        sublime_plugin = types.ModuleType("sublime_plugin")
        sublime_plugin.TextCommand = type("TextCommand", (), {})
        sublime_plugin.EventListener = type("EventListener", (), {})
        sys.modules["sublime"] = sublime
        sys.modules["sublime_plugin"] = sublime_plugin

        spec = importlib.util.spec_from_file_location(
            "oreslang_plugin_under_test", ROOT / "oreslang.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        cls.plugin = module

    def test_standard_diagnostic(self):
        items = self.plugin._parse_diagnostics(
            "/tmp/demo.ores:7:11: error: expected expression", "/tmp/demo.ores"
        )
        self.assertEqual(1, len(items))
        self.assertEqual(7, items[0]["line"])
        self.assertEqual(11, items[0]["column"])
        self.assertEqual("expected expression", items[0]["message"])

    def test_native_parser_diagnostic(self):
        items = self.plugin._parse_diagnostics(
            "java.lang.IllegalArgumentException: "
            "Oreslang parse error at 4:9: expected expression",
            "/tmp/demo.ores",
        )
        self.assertEqual(1, len(items))
        self.assertEqual("/tmp/demo.ores", items[0]["file"])
        self.assertEqual(4, items[0]["line"])
        self.assertEqual(9, items[0]["column"])


if __name__ == "__main__":
    unittest.main()
