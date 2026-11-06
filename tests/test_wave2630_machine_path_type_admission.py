"""Explicit malformed machine diagnostic paths must never be attributed to the active file."""
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest


def load_plugin():
    sublime = types.ModuleType("sublime")
    sublime.DRAW_SQUIGGLY_UNDERLINE = 1
    sublime.DRAW_NO_FILL = 2
    stub = types.ModuleType("sublime_plugin")
    stub.TextCommand = type("TextCommand", (), {})
    stub.EventListener = type("EventListener", (), {})
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = stub
    spec = importlib.util.spec_from_file_location(
        "wave2630_path_admission", Path(__file__).resolve().parents[1] / "oreslang.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Wave2630MachinePathAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def test_invalid_explicit_origins_cannot_impersonate_active_file(self):
        active = "/tmp/wave2630/src/main.ores"
        def record(origin, message):
            return {"path": origin, "line": 3, "column": 2, "message": message}

        examples = [
            {"line": 1, "column": 2, "message": "unlocated absent"},
            record(None, "unlocated null"),
            record("other.ores", "separate imported source"),
            *[record(origin, "invalid") for origin in
              (0, False, True, 1.5, [], {}, "", "bad\0path.ores")],
            record("src/ok.ores", "relative owner"),
        ]
        result = self.plugin._parse_diagnostics(
            json.dumps({"version": 1, "diagnostics": examples}), active)
        self.assertEqual(
            [(x["file"], x["message"], x["line"], x["column"]) for x in result],
            [(active, "unlocated absent", 1, 2),
             (active, "unlocated null", 3, 2),
             ("/tmp/wave2630/src/other.ores", "separate imported source", 3, 2),
             ("/tmp/wave2630/src/src/ok.ores", "relative owner", 3, 2)])
        self.assertEqual(len(result), 4)

    def test_valid_absolute_origin_and_malformed_neighbor_isolation(self):
        active = "/tmp/wave2630/src/main.ores"
        records = [
            {"path": {}, "message": "forge"},
            {"path": active, "message": "  intact  ", "severity": "WARNING",
             "range": {"start": {"line": 2, "column": 4},
                       "end": {"line": 2, "column": 7}}},
            {"path": "\0", "message": "bad"},
        ]
        expected = [{"file": active, "line": 2, "column": 4, "end_line": 2,
                     "end_column": 7, "severity": "warning", "message": "intact"}]
        for _ in range(3):
            self.assertEqual(
                self.plugin._parse_diagnostics(json.dumps(
                    {"version": 1, "diagnostics": records}), active),
                expected)


if __name__ == "__main__":
    unittest.main()
