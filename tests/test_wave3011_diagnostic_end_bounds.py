"""Compiler diagnostics must never synthesize editor coordinates above the cap."""
import json
import unittest
from test_package import DiagnosticParserTest


class Wave3011DiagnosticEndBounds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        DiagnosticParserTest.setUpClass()
        cls.plugin = DiagnosticParserTest.plugin

    def test_inferred_machine_end_column_is_validated(self):
        payload = {
            "version": 1,
            "diagnostics": [
                {"message": "invalid machine terminal", "range": {
                    "start": {"line": 4, "column": 10000000}}},
                {"message": "valid machine neighbor", "range": {
                    "start": {"line": 4, "column": 9999999}}},
                {"message": "valid other-line range", "range": {
                    "start": {"line": 5, "column": 10000000},
                    "end": {"line": 6, "column": 1}}},
            ],
        }
        items = self.plugin._parse_diagnostics(json.dumps(payload), "/tmp/main.ores")
        self.assertEqual([x["message"] for x in items],
                         ["valid machine neighbor", "valid other-line range"])
        self.assertEqual([(x["line"], x["column"], x["end_line"], x["end_column"])
                          for x in items],
                         [(4, 9999999, 4, 10000000), (5, 10000000, 6, 1)])

    def test_legacy_stdout_and_oreslang_parse_error_boundary(self):
        output = "\n".join([
            "/tmp/main.ores:5:10000000: error: forged standard end",
            "Oreslang parse error at 6:10000000: forged parser end",
            "/tmp/main.ores:7:9999999: warning: valid boundary",
            "Oreslang parse error at 8:1: valid parser record",
        ])
        items = self.plugin._parse_diagnostics(output, "/tmp/main.ores")
        self.assertEqual([x["message"] for x in items],
                         ["valid boundary", "valid parser record"])
        self.assertEqual(items[0]["end_column"], 10000000)
        self.assertEqual(items[1]["end_column"], 2)


if __name__ == "__main__":
    unittest.main()
