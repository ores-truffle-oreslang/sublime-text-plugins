"""Real host child-process IO validates combined UTF-8 byte-accounting boundaries.

Source-owned test only; not compiler guest evidence.
"""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]


def plugin_under_test():
    sublime = types.ModuleType("sublime")
    sublime.DRAW_SQUIGGLY_UNDERLINE = 1
    sublime.DRAW_NO_FILL = 2
    plugin = types.ModuleType("sublime_plugin")
    plugin.TextCommand = type("TextCommand", (), {})
    plugin.EventListener = type("EventListener", (), {})
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = plugin
    spec = importlib.util.spec_from_file_location(
        "wave2706_unicode_pipes", ROOT / "oreslang.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class UTF8PipeAccounting(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runner = plugin_under_test()

    @staticmethod
    def command():
        # Deliberately different byte lengths and actual independent OS pipes.
        # The final 4-byte scalar is never counted as a single UTF-8 byte.
        source = "import os\nos.write(1, ('🚀'*40+'A'*7).encode('utf-8'))\n"
        source += "os.write(2, ('漢'*30+'B'*13).encode('utf-8'))\n"
        return [sys.executable, "-c", source]

    def test_exact_sum_of_utf8_bytes_accepts_and_preserves_both_pipes(self):
        size_stdout = 40 * 4 + 7
        size_stderr = 30 * 3 + 13
        with tempfile.TemporaryDirectory() as cwd:
            result = self.runner._run_compiler_bounded(
                self.command(), cwd, timeout=8, max_bytes=size_stdout + size_stderr)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "🚀" * 40 + "A" * 7)
        self.assertEqual(result.stderr, "漢" * 30 + "B" * 13)
        self.assertEqual(len(result.stdout.encode()), size_stdout)
        self.assertEqual(len(result.stderr.encode()), size_stderr)

    def test_one_byte_under_combined_cap_rejects_both_os_pipes(self):
        exact = 40 * 4 + 7 + 30 * 3 + 13
        with tempfile.TemporaryDirectory() as cwd:
            with self.assertRaisesRegex(RuntimeError, "output budget exceeded"):
                self.runner._run_compiler_bounded(
                    self.command(), cwd, timeout=8, max_bytes=exact - 1)


if __name__ == "__main__":
    unittest.main()
