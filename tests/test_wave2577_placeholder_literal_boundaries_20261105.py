"""One-pass argv substitution must not interpret filename-derived placeholders.

Source-owned host-only regression; no shell commands or guest compiler run.
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
    shim = types.ModuleType("sublime_plugin")
    shim.TextCommand = type("TextCommand", (), {})
    shim.EventListener = type("EventListener", (), {})
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = shim
    path = Path(__file__).resolve().parents[1] / "oreslang.py"
    spec = importlib.util.spec_from_file_location("wave2577_argv_plugin", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LiteralPlaceholderBoundaries(unittest.TestCase):
    def test_expanded_values_remain_single_argv_items_without_recursive_expansion(self):
        plugin = load_plugin()
        filename = "/tmp/$project-zone/δ$file_name;$(printf bad).atto"
        project = "/tmp/$file-root/editor.sublime-project"
        argv_source = [
            "atto", "check", "$file", "$file_path", "$file_name",
            "$project", "$project_path", "prefix:$file_name",
            "$unknown", "$file_suffix",
        ]

        class Settings:
            def get(self, key, default=None):
                return argv_source if key == "cli_command" else default

        class Window:
            def project_file_name(self):
                return project

        class View:
            def file_name(self):
                return filename
            def window(self):
                return Window()

        old = plugin._settings
        plugin._settings = lambda: Settings()
        try:
            actual = plugin._expand_command(View())
        finally:
            plugin._settings = old
        self.assertEqual(actual, [
            "atto", "check", filename, "/tmp/$project-zone",
            "δ$file_name;$(printf bad).atto", project, "/tmp/$file-root",
            "prefix:δ$file_name;$(printf bad).atto", "$unknown", "$file_suffix",
        ])
        self.assertEqual(len(actual), len(argv_source))


if __name__ == "__main__":
    unittest.main()
