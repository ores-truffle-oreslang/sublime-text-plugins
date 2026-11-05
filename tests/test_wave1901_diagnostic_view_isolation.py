"""Host integration: machine diagnostics must render only for the active view."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest


ROOT = Path(__file__).resolve().parents[1]


class Region:
    def __init__(self, a, b):
        self.a, self.b = a, b
    def __repr__(self):
        return f"Region({self.a}, {self.b})"


def load_plugin():
    sublime = types.ModuleType("sublime")
    sublime.Region = Region
    sublime.DRAW_SQUIGGLY_UNDERLINE = 1
    sublime.DRAW_NO_FILL = 2
    sublime.load_settings = lambda _name: types.SimpleNamespace(
        get=lambda _key, default=None: default)
    plugin = types.ModuleType("sublime_plugin")
    plugin.TextCommand = type("TextCommand", (), {})
    plugin.EventListener = type("EventListener", (), {})
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = plugin
    spec = importlib.util.spec_from_file_location("wave1901_diagnostic_plugin", ROOT / "oreslang.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeView:
    def __init__(self, filename, text):
        self.filename, self.text = filename, text
        self.applied, self.erased, self.status = [], [], []

    def is_valid(self):
        return True

    def file_name(self):
        return self.filename

    def size(self):
        return len(self.text)

    def text_point(self, row, column, clamp_column=True):
        lines = self.text.splitlines(keepends=True)
        if row >= len(lines):
            return len(self.text)
        start = sum(len(line) for line in lines[:row])
        return start + min(column, len(lines[row].rstrip("\r\n")))

    def word(self, point):
        return Region(point, point)

    def add_regions(self, *args, **kwargs):
        self.applied.append((args, kwargs))

    def erase_regions(self, key):
        self.erased.append(key)

    def set_status(self, key, value):
        self.status.append((key, value))


class ActiveViewDiagnostics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def test_parsed_relative_diagnostic_is_annotated_only_on_owned_view(self):
        with tempfile.TemporaryDirectory() as root:
            active = os.path.join(root, "current.ores")
            foreign = os.path.join(root, "other.ores")
            payload = {"version": 1, "diagnostics": [
                {"path": "other.ores", "severity": "error", "message": "foreign",
                 "range": {"start": {"line": 1, "column": 1}}},
                {"path": "current.ores", "severity": "warning", "message": "local",
                 "range": {"start": {"line": 1, "column": 2},
                           "end": {"line": 1, "column": 4}}},
            ]}
            parsed = self.plugin._parse_diagnostics(json.dumps(payload), active)
            self.assertEqual([item["file"] for item in parsed], [foreign, active])
            view = FakeView(active, "abcd\n")
            self.plugin._apply_diagnostics(view, parsed)
            self.assertEqual(len(view.applied), 1)
            args, options = view.applied[0]
            self.assertEqual(args[0], self.plugin.DIAGNOSTIC_KEY)
            self.assertEqual([(r.a, r.b) for r in args[1]], [(1, 3)])
            self.assertEqual(options["annotations"], ["warning: local"])
            self.assertEqual(view.status[-1][1], "Oreslang: 1 diagnostic")
            self.assertNotIn("foreign", repr(view.applied))
            self.plugin._apply_diagnostics(view, parsed[:1])
            self.assertEqual(view.erased, [self.plugin.DIAGNOSTIC_KEY])
            self.assertEqual(view.status[-1][1], "Oreslang: no diagnostics")


if __name__ == "__main__":
    unittest.main()
