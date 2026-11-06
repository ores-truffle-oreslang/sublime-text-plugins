"""Legacy diagnostic parsing maintains valid records around malformed peers."""
import importlib.util
from pathlib import Path
import sys
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
    spec = importlib.util.spec_from_file_location("wave3400_legacy_plugin", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LegacyDiagnosticRecovery(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def test_mixed_invalid_coordinates_and_two_valid_legacy_syntaxes(self):
        source = "/tmp/wave3400-project/main.ores"
        message = (
            "src/日本語.ores:4:6: WARNING:  アクター🍃  \r\n"
            "src/bad.ores:2:99999999: error: discard invalid coordinate\n"
            "Oreslang parse error at 2:5: recovered after bad peer\r\n"
            "src/other.ores:8:9: info: final diagnostic\n"
        )
        records = self.plugin._parse_diagnostics(message, source)
        self.assertEqual(len(records), 3)
        self.assertEqual(
            [(x["line"], x["column"], x["end_column"], x["severity"], x["message"]) for x in records],
            [(4, 6, 7, "warning", "アクター🍃"),
             (2, 5, 6, "error", "recovered after bad peer"),
             (8, 9, 10, "info", "final diagnostic")],
        )
        self.assertEqual(records[0]["file"], "/tmp/wave3400-project/src/日本語.ores")
        self.assertEqual(records[1]["file"], source)
        self.assertEqual(records[2]["file"], "/tmp/wave3400-project/src/other.ores")

    def test_untrusted_machine_envelope_does_not_fall_back_to_legacy(self):
        source = "/tmp/wave3400-project/main.ores"
        self.assertEqual(
            self.plugin._parse_diagnostics(
                '{"version":2,"diagnostics":["file.ores:1:1: error: forged"]}', source
            ), [],
        )
        valid = self.plugin._parse_diagnostics(
            "Oreslang lexer error at 3:4: next independent diagnostic", source
        )
        self.assertEqual(len(valid), 1)
        self.assertEqual((valid[0]["line"], valid[0]["column"], valid[0]["file"]),
                         (3, 4, source))


if __name__ == "__main__":
    unittest.main()
