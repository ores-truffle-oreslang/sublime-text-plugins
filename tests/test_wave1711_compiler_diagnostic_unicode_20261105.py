"""Machine and legacy compiler diagnostics: Unicode peer isolation and clean recovery."""
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load_plugin():
    sublime = types.ModuleType("sublime")
    sublime.DRAW_SQUIGGLY_UNDERLINE = 1
    sublime.DRAW_NO_FILL = 2
    extension = types.ModuleType("sublime_plugin")
    extension.TextCommand = type("TextCommand", (), {})
    extension.EventListener = type("EventListener", (), {})
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = extension
    spec = importlib.util.spec_from_file_location("wave1711_diagnostics", ROOT / "oreslang.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UnicodeDiagnosticAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def test_machine_records_keep_valid_unicode_before_and_after_bad_peers(self):
        active = "/tmp/wave1711/main.ores"
        payload = {"version": 1, "diagnostics": [
            {"path": "src/日本語.ores", "severity": "WARNING", "message": "  葉🍃  ",
             "range": {"start": {"line": 1, "column": 3},
                       "end": {"line": 2, "column": 1}}},
            {"path": "src/invalid.ores", "message": "bad boolean",
             "range": {"start": {"line": True, "column": 2}}},
            {"path": "src/reversed.ores", "message": "bad reverse",
             "range": {"start": {"line": 6, "column": 3},
                       "end": {"line": 6, "column": 2}}},
            {"path": None, "severity": "HINT", "message": "  usable after invalid  ",
             "range": {"start": {"line": 7, "column": 1},
                       "end": {"line": 7, "column": 2}}},
        ]}
        records = self.plugin._parse_diagnostics(json.dumps(payload, ensure_ascii=False), active)
        self.assertEqual(len(records), 2)
        self.assertEqual(
            (records[0]["file"], records[0]["line"], records[0]["column"],
             records[0]["end_line"], records[0]["end_column"],
             records[0]["severity"], records[0]["message"]),
            ("/tmp/wave1711/src/日本語.ores", 1, 3, 2, 1, "warning", "葉🍃"),
        )
        self.assertEqual(
            (records[1]["file"], records[1]["line"], records[1]["column"],
             records[1]["severity"], records[1]["message"]),
            (active, 7, 1, "hint", "usable after invalid"),
        )

    def test_rejected_machine_version_does_not_poison_later_legacy_parse(self):
        active = "/tmp/wave1711/main.ores"
        invalid = {"version": True, "diagnostics": [{"message": "should not appear"}]}
        self.assertEqual(self.plugin._parse_diagnostics(json.dumps(invalid), active), [])
        text = "Oreslang parse error at 2:5: unicode 🍃 survives\n"
        self.assertEqual(self.plugin._parse_diagnostics(text, active)[0]["message"],
                         "unicode 🍃 survives")


if __name__ == "__main__":
    unittest.main()
