"""Editor command expansion is bounded and preserves literal argv boundaries.

Host-only source test; it must not launch shell commands or guest compilers.
"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest


def load_plugin():
    sublime = types.ModuleType("sublime")
    sublime.DRAW_SQUIGGLY_UNDERLINE = 1
    sublime.DRAW_NO_FILL = 2
    sublime_plugin = types.ModuleType("sublime_plugin")
    sublime_plugin.TextCommand = type("TextCommand", (), {})
    sublime_plugin.EventListener = type("EventListener", (), {})
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = sublime_plugin
    path = Path(__file__).resolve().parents[1] / "oreslang.py"
    spec = importlib.util.spec_from_file_location("oreslang_wave911b_argv", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Wave911bCliArgumentAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def expand(self, command, filename="/tmp/src/$project;$(touch_bad).ores"):
        class Settings:
            def get(self, key, default=None):
                return command if key == "cli_command" else default

        class View:
            def file_name(self):
                return filename

            def window(self):
                return None

        original = self.plugin._settings
        self.plugin._settings = lambda: Settings()
        try:
            return self.plugin._expand_command(View())
        finally:
            self.plugin._settings = original

    def test_user_controlled_filename_stays_one_literal_argument(self):
        filename = "/tmp/src/$project;$(touch_bad).ores"
        argv = self.expand([
            "oreslang", "check", "--format=json", "$file", "$file_name",
            "$project_path", "$file_extra", "prefix:$file",
        ], filename)
        self.assertEqual(argv, [
            "oreslang", "check", "--format=json", filename,
            "$project;$(touch_bad).ores", "/tmp/src", "$file_extra",
            "prefix:" + filename,
        ])
        self.assertEqual(len(argv), 8)

    def test_reject_nonarray_and_oversized_or_nul_arguments(self):
        invalid = (
            [], {}, 13,
            ["oreslang", ""],
            ["oreslang", "bad\0input"],
            ["oreslang", "x" * 4097],
            ["oreslang"] * 65,
        )
        for command in invalid:
            with self.subTest(command_type=type(command).__name__, size=len(command) if hasattr(command, "__len__") else -1):
                with self.assertRaisesRegex(ValueError, "cli_command must be an array"):
                    self.expand(command)
        self.assertEqual(self.expand(["oreslang", "x" * 4096]), ["oreslang", "x" * 4096])


if __name__ == "__main__":
    unittest.main()
