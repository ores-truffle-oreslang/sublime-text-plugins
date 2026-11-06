"""Mixed untrusted diagnostics must retain valid cross-file machine ranges."""
import importlib.util
import json
import os
import sys
import types
import unittest
from pathlib import Path

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
    spec = importlib.util.spec_from_file_location("gpt6_wave2142_editor", ROOT / "oreslang.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MachinePeerRangeAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.editor = load_editor()

    def test_malformed_origins_and_coordinates_do_not_hide_valid_imported_peer(self):
        active = os.path.abspath("/tmp/wave2142/app.ores")
        records = [
            {"path": ["app.ores"], "message": "array-origin"},
            {"path": "app.ores\x00foreign", "message": "nul-origin"},
            {"message": "boolean-line", "range": {"start": {"line": True, "column": 1}}},
            {"message": "reversed", "range": {"start": {"line": 7, "column": 4},
                                                "end": {"line": 6, "column": 3}}},
            {"message": "overflow-default-end", "range": {"start": {"line": 3, "column": 10000000}}},
            {"path": "src/child.ores", "severity": "WARNING", "message": "  imported issue  ",
             "range": {"start": {"line": 7, "column": 3}, "end": {"line": 8, "column": 1}}},
            {"path": None, "severity": "not-a-severity", "message": "local issue",
             "range": {"start": {"line": 2, "column": 9999999}}},
        ]
        result = self.editor._parse_diagnostics(json.dumps(
            {"version": 1, "diagnostics": records}), active)
        self.assertEqual([r["message"] for r in result], ["imported issue", "local issue"])
        self.assertEqual(result[0]["file"], os.path.abspath("/tmp/wave2142/src/child.ores"))
        self.assertEqual((result[0]["line"], result[0]["column"],
                          result[0]["end_line"], result[0]["end_column"]), (7, 3, 8, 1))
        self.assertEqual(result[0]["severity"], "warning")
        self.assertEqual(result[1]["file"], active)
        self.assertEqual((result[1]["column"], result[1]["end_column"]), (9999999, 10000000))
        self.assertEqual(result[1]["severity"], "error")

    def test_unknown_protocol_version_is_not_silently_promoted(self):
        active = os.path.abspath("/tmp/wave2142/app.ores")
        for invalid in (0, 2, "1", True):
            with self.subTest(version=invalid):
                self.assertEqual(self.editor._parse_diagnostics(json.dumps(
                    {"version": invalid, "diagnostics": [
                        {"path": "app.ores", "message": "spoofed v1 record"}]}), active), [])


if __name__ == "__main__":
    unittest.main()
