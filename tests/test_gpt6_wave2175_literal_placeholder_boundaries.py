"""Sublime CLI argument expansion must remain single-pass and bounded, not a shell."""
import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_editor():
    sublime = types.ModuleType("sublime")
    sublime.DRAW_SQUIGGLY_UNDERLINE = 1
    sublime.DRAW_NO_FILL = 2
    plugin = types.ModuleType("sublime_plugin")
    plugin.TextCommand = type("TextCommand", (), {})
    plugin.EventListener = type("EventListener", (), {})
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = plugin
    spec = importlib.util.spec_from_file_location("gpt6_wave2175_editor", ROOT / "oreslang.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StubView:
    def __init__(self, filename, project):
        self.filename = filename
        self.project = project

    def file_name(self):
        return self.filename

    def window(self):
        return types.SimpleNamespace(project_file_name=lambda: self.project)


class LiteralPlaceholderBoundary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.editor = load_editor()

    def expand(self, view, command):
        settings = types.SimpleNamespace(get=lambda key, default=None: command)
        with patch.object(self.editor, "_settings", return_value=settings):
            return self.editor._expand_command(view)

    def test_longest_placeholder_substitution_is_single_pass_with_literal_hostile_paths(self):
        filename = os.path.abspath("/tmp/wave2175/$project-literal/my $file.ores")
        project = os.path.abspath("/tmp/wave2175/$file-literal/workspace.sublime-project")
        view = StubView(filename, project)
        args = [
            "oreslang", "check", "$file", "$file_path", "$file_name",
            "$project", "$project_path", "prefix=$file:suffix",
            "$file_name_extra", "$fileX", "literal ; && $(touch /tmp/not-created)",
        ]
        actual = self.expand(view, args)
        expected = [
            "oreslang", "check", filename, os.path.dirname(filename),
            os.path.basename(filename), project, os.path.dirname(project),
            "prefix=" + filename + ":suffix", "$file_name_extra", "$fileX",
            "literal ; && $(touch /tmp/not-created)",
        ]
        self.assertEqual(actual, expected)
        self.assertIn("$project", actual[2], "filename content must never expand recursively")
        self.assertIn("$file", actual[5], "project path content must never expand recursively")
        self.assertEqual(args[2], "$file", "caller's configured argv must remain unchanged")

    def test_bad_argv_shape_length_and_nul_are_rejected_before_process_invocation(self):
        view = StubView("/tmp/wave2175/a.ores", None)
        for invalid in ([], ["oreslang"] * 65, ["oreslang", "x" * 4097],
                        ["oreslang", "bad\x00arg"], ["oreslang", ""], ["oreslang", 10]):
            with self.subTest(command=repr(invalid)[:60]):
                with self.assertRaisesRegex(ValueError, "cli_command"):
                    self.expand(view, invalid)
        missing = StubView(None, None)
        with self.assertRaisesRegex(ValueError, "save the"):
            self.expand(missing, ["oreslang", "$file"])


if __name__ == "__main__":
    unittest.main()
