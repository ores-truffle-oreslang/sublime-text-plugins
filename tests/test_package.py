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

    def test_new_compiler_constructs_are_highlighted(self):
        syntax = (ROOT / "Oreslang.sublime-syntax").read_text()
        keyword_line = next(
            line for line in syntax.splitlines() if line.strip().startswith("keywords:")
        )
        names = set(keyword_line.split("(?:", 1)[1].split(")", 1)[0].split("|"))
        for keyword in ("do", "match", "over", "select", "nb", "case",
                        "readch", "writech", "while", "const", "val", "let", "mut"):
            self.assertIn(keyword, names)

    def test_global_controls_are_separate(self):
        syntax = (ROOT / "Oreslang.sublime-syntax").read_text()
        global_line = next(
            line for line in syntax.splitlines()
            if line.strip().startswith("global_controls:")
        )
        for name in ("recover", "defer", "throw", "raise"):
            self.assertIn(name, global_line)
        self.assertIn("scope: support.function.global.oreslang", syntax)

    def test_json_resources_parse(self):
        for name in (
            "Default.sublime-commands",
            "Oreslang.sublime-build",
            "Oreslang.sublime-settings",
            "Main.sublime-menu",
        ):
            with self.subTest(name=name):
                json.loads((ROOT / name).read_text())

    def test_editor_commands_use_canonical_oreslang_cli(self):
        build = json.loads((ROOT / "Oreslang.sublime-build").read_text())
        settings = json.loads((ROOT / "Oreslang.sublime-settings").read_text())
        self.assertEqual(["oreslang", "check", "$file"], build["cmd"])
        self.assertEqual(
            ["oreslang", "check", "--format=json", "$file"],
            settings["cli_command"],
        )
        self.assertNotIn("ores", build["cmd"])
        self.assertNotIn("ores", settings["cli_command"])

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

    def test_command_placeholder_expansion_is_atomic_and_nonrecursive(self):
        class Settings:
            def get(self, key, default=None):
                if key == "cli_command":
                    return ["oreslang", "$file", "$file_path", "$file_name",
                            "$project", "$project_path", "$file_extra"]
                return default

        class Window:
            def project_file_name(self):
                return "/tmp/source/workspace.sublime-project"

        class View:
            def file_name(self):
                return "/tmp/dir$project/sample.ores"

            def window(self):
                return Window()

        original = self.plugin._settings
        self.plugin._settings = lambda: Settings()
        try:
            command = self.plugin._expand_command(View())
        finally:
            self.plugin._settings = original

        self.assertEqual([
            "oreslang", "/tmp/dir$project/sample.ores", "/tmp/dir$project",
            "sample.ores", "/tmp/source/workspace.sublime-project",
            "/tmp/source", "$file_extra"
        ], command)

    def test_oreslang_cli_json_diagnostic(self):
        items = self.plugin._parse_diagnostics(
            json.dumps(
                {
                    "version": 1,
                    "ok": False,
                    "diagnostics": [
                        {
                            "version": 1,
                            "path": "/tmp/demo.ores",
                            "range": {
                                "start": {"line": 8, "column": 4},
                                "end": {"line": 8, "column": 5},
                            },
                            "severity": "error",
                            "message": "unknown binding",
                        }
                    ],
                }
            ),
            "/tmp/demo.ores",
        )
        self.assertEqual(1, len(items))
        self.assertEqual("/tmp/demo.ores", items[0]["file"])
        self.assertEqual(8, items[0]["line"])
        self.assertEqual(4, items[0]["column"])
        self.assertEqual(8, items[0]["end_line"])
        self.assertEqual(5, items[0]["end_column"])
        self.assertEqual("unknown binding", items[0]["message"])

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
