"""Source-owned malformed-neighbor and boundary coverage for machine diagnostics."""
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest


def _load_plugin():
    sublime = types.ModuleType("sublime")
    sublime.DRAW_SQUIGGLY_UNDERLINE = 1
    sublime.DRAW_NO_FILL = 2
    plugin_stub = types.ModuleType("sublime_plugin")
    plugin_stub.TextCommand = type("TextCommand", (), {})
    plugin_stub.EventListener = type("EventListener", (), {})
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = plugin_stub
    spec = importlib.util.spec_from_file_location(
        "wave231211_machine_diagnostics", Path(__file__).resolve().parents[1] / "oreslang.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Wave231211MachineRangeAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = _load_plugin()

    def test_malformed_neighbors_do_not_drop_boundary_valid_diagnostics(self):
        root = "/tmp/wave231211/main.ores"
        payload = {"version": 1, "diagnostics": [
            {"path": "src/nested.ores", "severity": "WARNING", "message": "  🌐 first  ",
             "range": {"start": {"line": 1, "column": 1},
                       "end": {"line": 2, "column": 1}}},
            {"message": "bad boolean row", "range": {"start": {"line": True, "column": 1}}},
            {"message": "bad float", "range": {"start": {"line": 4.5, "column": 2}}},
            {"message": "reversed", "range": {"start": {"line": 4, "column": 8},
                                             "end": {"line": 4, "column": 7}}},
            {"message": "oversized explicit end", "range": {"start": {"line": 2, "column": 4}, "end": {"line": 2, "column": 10000001}}},
            {"message": "last valid boundary", "severity": "HINT",
             "range": {"start": {"line": 10000000, "column": 9999999},
                       "end": {"line": 10000000, "column": 10000000}}},
            {"message": "  unknown severity falls back  ", "severity": "PANIC",
             "range": {"start": {"line": 2, "column": 4}}},
        ]}
        expected = [
            {"file": "/tmp/wave231211/src/nested.ores", "line": 1, "column": 1,
             "end_line": 2, "end_column": 1, "severity": "warning", "message": "🌐 first"},
            {"file": root, "line": 10000000, "column": 9999999,
             "end_line": 10000000, "end_column": 10000000, "severity": "hint",
             "message": "last valid boundary"},
            {"file": root, "line": 2, "column": 4, "end_line": 2, "end_column": 5,
             "severity": "error", "message": "unknown severity falls back"},
        ]
        for _ in range(3):
            self.assertEqual(
                self.plugin._parse_diagnostics(json.dumps(payload, ensure_ascii=False), root),
                expected)

    def test_json_protocol_rejects_invalid_version_without_falling_into_legacy(self):
        root = "/tmp/wave231211/main.ores"
        valid = {"message": "preserve", "range": {"start": {"line": 3, "column": 2}}}
        for version in (True, "1", 1.0, 0, 2, None):
            with self.subTest(version=repr(version)):
                self.assertEqual(
                    self.plugin._parse_diagnostics(json.dumps({
                        "version": version,
                        "diagnostics": [valid]}), root),
                    [])


if __name__ == "__main__":
    unittest.main()
