"""A successful CLI leader cannot leave a pipe-holding descendant alive.

Host-only POSIX process-group test; no compiler guest or editor launch.
"""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
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
    spec = importlib.util.spec_from_file_location("wave2032x_postexit", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@unittest.skipUnless(os.name == "posix", "POSIX process groups required")
class SuccessfulLeaderDescendantFence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def test_successful_parent_exit_retires_inherited_pipe_descendants(self):
        # A helper inherits stdout/stderr handles and tries a delayed write.
        # A completed leader must not let that helper outlive the process group.
        child = (
            "import pathlib,sys,time;"
            "time.sleep(0.75);"
            "pathlib.Path(sys.argv[1]).write_text('escaped',encoding='utf-8')"
        )
        parent = (
            "import subprocess,sys;"
            "subprocess.Popen([sys.executable,'-c',sys.argv[1],sys.argv[2]],"
            "stdout=sys.stdout,stderr=sys.stderr);"
            "print('leader-ok',flush=True)"
        )
        with tempfile.TemporaryDirectory(prefix="atto-wave2032x-") as cwd:
            marker = Path(cwd) / "escaped-side-effect"
            started = time.monotonic()
            result = self.plugin._run_compiler_bounded(
                [sys.executable, "-c", parent, child, str(marker)],
                cwd, timeout=4, max_bytes=4096,
            )
            self.assertLess(time.monotonic() - started, 3.5)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "leader-ok\n")
            self.assertEqual(result.stderr, "")
            time.sleep(0.9)
            self.assertFalse(marker.exists(),
                             "descendant survived successful leader exit")


if __name__ == "__main__":
    unittest.main()
