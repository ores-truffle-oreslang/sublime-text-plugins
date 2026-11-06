"""Mixed-validity compiler records keep valid peer source/range authority."""
import json
import os
import unittest
from test_package import DiagnosticParserTest


class Wave3129MixedRecordAuthority(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        DiagnosticParserTest.setUpClass()
        cls.plugin = DiagnosticParserTest.plugin

    def test_malformed_range_peers_do_not_suppress_import_and_active_diagnostics(self):
        active = "/tmp/wave3129/workspace/src/main.ores"
        payload = {
            "version": 1,
            "diagnostics": [
                {"message": "invalid range list", "range": [1, 2]},
                {"path": "../shared/dependency.ores", "message": " imported ",
                 "severity": "WARNING", "range": {"start": {"line": 7, "column": 3},
                 "end": {"line": 8, "column": 1}}},
                {"message": "invalid boolean coordinate", "range": {"start": {"column": True}}},
                {"message": "invalid reversed end", "range": {"start": {"line": 9, "column": 4},
                 "end": {"line": 9, "column": 3}}},
                {"message": " active ", "path": None, "range": {
                    "start": {"line": 10000000, "column": 9999999},
                    "end": {"line": 10000000, "column": 10000000}}},
                {"message": 123, "range": {"start": {"line": 2}}},
                {"message": " terminal ", "severity": "INFO",
                 "range": {"start": {"line": 5, "column": 2},
                           "end": {"line": 6, "column": 1}}},
            ],
        }
        parsed = self.plugin._parse_diagnostics(json.dumps(payload), active)
        self.assertEqual([record["message"] for record in parsed],
                         ["imported", "active", "terminal"])
        imported = os.path.abspath("/tmp/wave3129/workspace/shared/dependency.ores")
        self.assertEqual([record["file"] for record in parsed],
                         [imported, active, active])
        self.assertEqual([
            (record["line"], record["column"], record["end_line"], record["end_column"])
            for record in parsed
        ], [(7, 3, 8, 1), (10000000, 9999999, 10000000, 10000000), (5, 2, 6, 1)])
        self.assertEqual([record["severity"] for record in parsed],
                         ["warning", "error", "info"])

    def test_unknown_machine_version_cannot_reenter_legacy_parser(self):
        payload = {"version": 2, "diagnostics": [
            {"message": "/tmp/wave3129/main.ores:3:2: error: forged"}
        ]}
        self.assertEqual(self.plugin._parse_diagnostics(
            json.dumps(payload), "/tmp/wave3129/main.ores"), [])


if __name__ == "__main__":
    unittest.main()
