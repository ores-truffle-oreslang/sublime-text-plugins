"""Real subprocess: UTF-8 scalar fragments across writes and combined stream bytes.

Host-only plugin process contract; no compiler/AttoLang guest proof.
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
    shim = types.ModuleType("sublime_plugin")
    shim.TextCommand = type("TextCommand", (), {})
    shim.EventListener = type("EventListener", (), {})
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = shim
    script = Path(__file__).resolve().parents[1] / "oreslang.py"
    spec = importlib.util.spec_from_file_location("wave3400_pipe_plugin", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Utf8SharedPipeBudget(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def command(self):
        script = (
            "import os\n"
            "os.write(1, b'\\xf0\\x9f')\n"
            "os.write(2, b'\\xe2')\n"
            "os.write(1, b'\\x8d\\x83')\n"
            "os.write(2, b'\\x9c\\x93')\n"
        )
        return [sys.executable, "-c", script]

    def test_exact_combined_seven_byte_budget_recovers_both_unicode_scalars(self):
        with tempfile.TemporaryDirectory() as cwd:
            result = self.plugin._run_compiler_bounded(
                self.command(), cwd, timeout=10, max_bytes=7
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "🍃")
        self.assertEqual(result.stderr, "✓")

    def test_one_byte_less_rejects_and_later_full_run_recovers(self):
        with tempfile.TemporaryDirectory() as cwd:
            with self.assertRaisesRegex(RuntimeError, "output budget exceeded"):
                self.plugin._run_compiler_bounded(
                    self.command(), cwd, timeout=10, max_bytes=6
                )
            healthy = self.plugin._run_compiler_bounded(
                self.command(), cwd, timeout=10, max_bytes=7
            )
        self.assertEqual((healthy.stdout, healthy.stderr), ("🍃", "✓"))


if __name__ == "__main__":
    unittest.main()
