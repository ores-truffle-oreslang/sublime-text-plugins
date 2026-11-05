"""Bounded editor compiler subprocess: the stdout and stderr budget is shared.

Host-only, using a real subprocess; no AttoLang guest compilation claim.
"""
import importlib.util
from pathlib import Path
import sys
import tempfile
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
    spec = importlib.util.spec_from_file_location("oreslang_wave911b_pipe", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CombinedPipeBudget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def command(self):
        # Simultaneous pipes: each remains below the individual cap, while the
        # combined output crosses a smaller aggregate cap.
        program = (
            "import os\n"
            "for _ in range(24):\n"
            " os.write(1,b'A'*4096)\n"
            " os.write(2,b'B'*4096)\n"
        )
        return [sys.executable, "-c", program]

    def test_both_pipes_are_drained_and_captured_exactly(self):
        with tempfile.TemporaryDirectory() as cwd:
            result = self.plugin._run_compiler_bounded(
                self.command(), cwd, 10, max_bytes=256 * 1024
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "A" * (24 * 4096))
        self.assertEqual(result.stderr, "B" * (24 * 4096))

    def test_output_budget_applies_to_sum_of_both_pipes(self):
        with tempfile.TemporaryDirectory() as cwd:
            with self.assertRaisesRegex(RuntimeError, "output budget exceeded"):
                self.plugin._run_compiler_bounded(
                    self.command(), cwd, 10, max_bytes=128 * 1024
                )


if __name__ == "__main__":
    unittest.main()
