"""Integration denial of forged machine/legacy compiler diagnostic origins.

No native AttoLang guest is claimed: exercise the shipped editor's source parser.
"""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
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
    spec = importlib.util.spec_from_file_location(
        "wave2706_malformed_origin", ROOT / "oreslang.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MalformedDiagnosticOrigin(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.editor = load_plugin()

    def test_invalid_explicit_machine_origins_do_not_forge_active_file(self):
        with tempfile.TemporaryDirectory() as directory:
            active = os.path.join(directory, "main.ores")
            def diag(message, **kwargs):
                return dict(message=message, range={
                    "start": {"line": 2, "column": 3}}, **kwargs)
            peers = [
                diag("relative", path="lib/dep.ores"),
                diag("omitted"),
                diag("explicit null", path=None),
                diag("blank", path=""),
                diag("nul path", path="bad\x00file.ores"),
                diag("array", path=[]),
                diag("object", path={"file": active}),
                diag("numeric", path=12),
                diag("boolean", path=True),
                diag("valid last", path="main.ores"),
            ]
            result = self.editor._parse_diagnostics(
                json.dumps({"version": 1, "diagnostics": peers}), active)
            self.assertEqual(
                [item["message"] for item in result],
                ["relative", "omitted", "explicit null", "valid last"])
            self.assertEqual(
                [item["file"] for item in result],
                [os.path.join(directory, "lib", "dep.ores"), active, active, active])
            self.assertTrue(all(item["line"] == 2 and item["column"] == 3 for item in result))

    def test_legacy_nul_origin_rejected_but_valid_siblings_survive(self):
        with tempfile.TemporaryDirectory() as directory:
            active = os.path.join(directory, "main.ores")
            records = (
                "evil\x00file.ores:2:3: error: forged\n"
                "lib/valid.ores:4:2: warning: valid peer\n"
                "Oreslang parse error at 6:7: real compiler diagnostic"
            )
            result = self.editor._parse_diagnostics(records, active)
            self.assertEqual(len(result), 2)
            self.assertEqual(result[0]["message"], "valid peer")
            self.assertEqual(result[0]["file"], os.path.join(directory, "lib", "valid.ores"))
            self.assertEqual(result[1]["message"], "real compiler diagnostic")
            self.assertEqual(result[1]["file"], active)


if __name__ == "__main__":
    unittest.main()
