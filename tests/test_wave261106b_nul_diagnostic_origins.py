"""Refuse machine and legacy compiler diagnostic origins containing NUL bytes."""
import json
import os
import unittest
from test_lifecycle import load_plugin


class DiagnosticOriginNulWave261106B(unittest.TestCase):
    def setUp(self):
        self.plugin, _, _ = load_plugin()
        self.active = os.path.abspath("/tmp/atto-wave261106b/main.ores")

    def test_machine_json_nul_origin_is_denied_without_losing_valid_siblings(self):
        output = json.dumps({
            "version": 1,
            "diagnostics": [
                {"path": "imports/bad\u0000.ores", "message": "forged",
                 "range": {"start": {"line": 1, "column": 2}}},
                {"path": "imports/valid.ores", "severity": "warning",
                 "message": "valid peer",
                 "range": {"start": {"line": 3, "column": 4}}},
            ]
        })
        items = self.plugin._parse_diagnostics(output, self.active)
        self.assertEqual([x["message"] for x in items], ["valid peer"])
        self.assertEqual(items[0]["file"],
                         os.path.abspath("/tmp/atto-wave261106b/imports/valid.ores"))

    def test_stderr_nul_origin_is_denied_without_losing_valid_siblings(self):
        output = (
            "imports/bad\x00.ores:1:2: error: forged\n"
            "imports/valid.ores:4:5: warning: valid peer\n"
        )
        items = self.plugin._parse_diagnostics(output, self.active)
        self.assertEqual([x["message"] for x in items], ["valid peer"])
        self.assertEqual(items[0]["column"], 5)
        self.assertEqual(items[0]["severity"], "warning")


if __name__ == "__main__":
    unittest.main()
