"""Legacy diagnostic parser preserves distinct file origins and rejects invalid coordinates.

Host-only tests: no editor process, compiler launch or guest execution.
"""
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest


def load_plugin():
    sublime = types.ModuleType("sublime")
    sublime.DRAW_SQUIGGLY_UNDERLINE = 1
    sublime.DRAW_NO_FILL = 2
    plugin_stub = types.ModuleType("sublime_plugin")
    plugin_stub.TextCommand = type("TextCommand", (), {})
    plugin_stub.EventListener = type("EventListener", (), {})
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = plugin_stub
    source = Path(__file__).resolve().parents[1] / "oreslang.py"
    spec = importlib.util.spec_from_file_location("wave1901_legacy_diagnostics", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Wave1901LegacyPeerIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def test_mixed_crlf_legacy_records_keep_distinct_file_origins(self):
        active = os.path.abspath(os.path.join("wave1901-project", "entry.ores"))
        output = (
            "src/peer.ores:3:5: warning: imported 🙂\r\n"
            "src/bad.ores:0:2: error: zero row\n"
            "src/bad.ores:1:10000000: error: excessive column\n"
            "../other.ores:4:1: error: separate file\n"
            "Oreslang parse error at 7:9: unexpected token\n"
            "src/bad.ores:123456789:2: error: too many digits\n"
        )
        got = self.plugin._parse_diagnostics(output, active)
        self.assertEqual(len(got), 3, got)
        self.assertEqual(
            (got[0]["file"], got[0]["line"], got[0]["column"],
             got[0]["severity"], got[0]["message"]),
            (os.path.abspath(os.path.join(os.path.dirname(active), "src", "peer.ores")),
             3, 5, "warning", "imported 🙂"),
        )
        self.assertEqual(got[1]["file"],
                         os.path.abspath(os.path.join(os.path.dirname(active), "..", "other.ores")))
        self.assertEqual((got[1]["line"], got[1]["column"], got[1]["severity"]),
                         (4, 1, "error"))
        self.assertEqual((got[2]["file"], got[2]["line"], got[2]["column"],
                          got[2]["message"]),
                         (active, 7, 9, "unexpected token"))


if __name__ == "__main__":
    unittest.main()
