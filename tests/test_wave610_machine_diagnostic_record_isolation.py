"""Mixed machine diagnostic inputs preserve valid origin and positioning."""
import importlib.util
import json
import pathlib
import sys
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_plugin():
    sublime = types.ModuleType("sublime")
    sublime.DRAW_SQUIGGLY_UNDERLINE = 1
    sublime.DRAW_NO_FILL = 2
    shim = types.ModuleType("sublime_plugin")
    shim.TextCommand = type("TextCommand", (), {})
    shim.EventListener = type("EventListener", (), {})
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = shim
    spec = importlib.util.spec_from_file_location("wave610_diagnostic_plugin", ROOT / "oreslang.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Wave610MachineRecordIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def test_invalid_peers_do_not_drop_valid_multiline_or_relative_origins(self):
        source = "/tmp/wave610-project/main.ores"
        payload = {
            "version": 1,
            "diagnostics": [
                {
                    "path": "src/unicode.ores",
                    "message": "  一番目  ",
                    "severity": "WARNING",
                    "range": {
                        "start": {"line": 3, "column": 2},
                        "end": {"line": 3, "column": 6},
                    },
                },
                {"message": "bad boolean", "range": {"start": {"line": True}}},
                {"message": "reversed", "range": {
                    "start": {"line": 9, "column": 4},
                    "end": {"line": 8, "column": 10},
                }},
                {
                    "message": "  final line  ",
                    "severity": "HINT",
                    "range": {
                        "start": {"line": 4, "column": 1},
                        "end": {"line": 5, "column": 2},
                    },
                },
            ],
        }
        result = self.plugin._parse_diagnostics(json.dumps(payload), source)
        self.assertEqual(len(result), 2)
        self.assertEqual(
            (result[0]["file"], result[0]["message"], result[0]["severity"],
             result[0]["line"], result[0]["column"], result[0]["end_line"], result[0]["end_column"]),
            ("/tmp/wave610-project/src/unicode.ores", "一番目", "warning", 3, 2, 3, 6),
        )
        self.assertEqual(
            (result[1]["file"], result[1]["message"], result[1]["severity"],
             result[1]["line"], result[1]["column"], result[1]["end_line"], result[1]["end_column"]),
            (source, "final line", "hint", 4, 1, 5, 2),
        )

    def test_version_one_is_required_even_for_otherwise_valid_records(self):
        item = {"path": "src/dependency.ores", "message": "message"}
        for version in (True, 0, "1", 1.0):
            with self.subTest(version=version):
                self.assertEqual(
                    self.plugin._parse_diagnostics(
                        json.dumps({"version": version, "diagnostics": [item]}),
                        "/tmp/wave610-project/main.ores",
                    ),
                    [],
                )


if __name__ == "__main__":
    unittest.main()
