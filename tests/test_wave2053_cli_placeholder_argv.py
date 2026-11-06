"""Source-owned host test: arguments remain single, nonrecursive, shell-free argv."""
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest


def plugin_under_test():
    sublime = types.ModuleType("sublime")
    sublime.DRAW_SQUIGGLY_UNDERLINE = 1
    sublime.DRAW_NO_FILL = 2
    stub = types.ModuleType("sublime_plugin")
    stub.TextCommand = type("TextCommand", (), {})
    stub.EventListener = type("EventListener", (), {})
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = stub
    source = Path(__file__).resolve().parents[1] / "oreslang.py"
    spec = importlib.util.spec_from_file_location("wave2053_sublime", source)
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)
    return plugin


class CompilerArgvAdmission(unittest.TestCase):
    def test_hostile_filename_and_project_are_not_resplit_or_recursively_expanded(self):
        plugin = plugin_under_test()
        filename = '/tmp/space dir/δ$file_name;"quoted".atto'
        project = '/tmp/$file-root/work space/project.sublime-project'
        configured = [
            "atto", "check", "--file=$file", "--directory=$file_path",
            "--basename=$file_name", "--project=$project",
            "--project-dir=$project_path", "--unknown=$file_suffix",
            "--repeat=$file_name:$file_name",
        ]

        class View:
            def file_name(self):
                return filename
            def window(self):
                return types.SimpleNamespace(project_file_name=lambda: project)

        plugin._settings = lambda: types.SimpleNamespace(
            get=lambda key, default=None: configured if key == "cli_command" else default)
        argv = plugin._expand_command(View())
        self.assertEqual(argv, [
            "atto", "check", "--file=" + filename,
            "--directory=" + os.path.dirname(filename),
            "--basename=" + os.path.basename(filename),
            "--project=" + project,
            "--project-dir=" + os.path.dirname(project),
            "--unknown=$file_suffix",
            "--repeat=" + os.path.basename(filename) + ":" + os.path.basename(filename),
        ])
        self.assertEqual(len(argv), len(configured))

    def test_nul_tainted_option_fails_before_view_or_command_launch(self):
        plugin = plugin_under_test()
        plugin._settings = lambda: types.SimpleNamespace(
            get=lambda key, default=None: ["atto", "--invalid=\x00"] if key == "cli_command" else default)
        class UnusedView:
            def file_name(self):
                self.fail("validation must occur before filename access")
        with self.assertRaisesRegex(ValueError, "bounded, nonempty strings"):
            plugin._expand_command(UnusedView())


if __name__ == "__main__":
    unittest.main()
