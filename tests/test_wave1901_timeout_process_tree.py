"""Real host subprocess timeout must terminate the entire inherited-pipe tree.

Source-owned regression only; this does not claim a compiler-backed guest run.
"""
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_plugin():
    sublime = types.ModuleType("sublime")
    sublime.DRAW_SQUIGGLY_UNDERLINE = 1
    sublime.DRAW_NO_FILL = 2
    plugin = types.ModuleType("sublime_plugin")
    plugin.TextCommand = type("TextCommand", (), {})
    plugin.EventListener = type("EventListener", (), {})
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = plugin
    spec = importlib.util.spec_from_file_location("wave1901_timeout_plugin", ROOT / "oreslang.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CompilerTimeoutTree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def test_normal_subprocess_completes_with_both_pipes(self):
        with tempfile.TemporaryDirectory() as cwd:
            result = self.plugin._run_compiler_bounded(
                [sys.executable, "-c", "import sys;print('ok');print('note',file=sys.stderr)"],
                cwd, timeout=4, max_bytes=4096)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "ok\n")
        self.assertEqual(result.stderr, "note\n")

    @unittest.skipUnless(os.name == "posix", "POSIX process groups only")
    def test_timeout_kills_inherited_pipe_grandchild_before_side_effect(self):
        grandchild = (
            "import pathlib,sys,time\n"
            "pathlib.Path(sys.argv[1]).write_text('started')\n"
            "time.sleep(1.3)\n"
            "pathlib.Path(sys.argv[2]).write_text('escaped')\n"
        )
        parent = (
            "import subprocess,sys,time\n"
            "subprocess.Popen([sys.executable,'-c',sys.argv[3],sys.argv[1],sys.argv[2]],"
            "stdout=sys.stdout,stderr=sys.stderr)\n"
            "print('ready',flush=True)\n"
            "time.sleep(8)\n"
        )
        with tempfile.TemporaryDirectory(prefix="oreslang-wave1901-") as cwd:
            started = Path(cwd) / "child-started"
            escaped = Path(cwd) / "child-escaped"
            with self.assertRaises(subprocess.TimeoutExpired):
                self.plugin._run_compiler_bounded(
                    [sys.executable, "-c", parent, str(started), str(escaped), grandchild],
                    cwd, timeout=0.75, max_bytes=4096)
            self.assertTrue(started.is_file(), "negative control must start a real descendant")
            time.sleep(1.5)
            self.assertFalse(escaped.exists(), "grandchild escaped the timed-out process group")


if __name__ == "__main__":
    unittest.main()
