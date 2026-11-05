"""Editor diagnostic rendering isolates foreign paths and bounds visible regions.

Checks older Sublime versions without annotations, without an actual editor process.
"""
import importlib.util
from pathlib import Path
import sys
import types
import unittest


def load_plugin():
    sublime = types.ModuleType("sublime")
    sublime.DRAW_SQUIGGLY_UNDERLINE = 1
    sublime.DRAW_NO_FILL = 2

    class Region:
        def __init__(self, a, b):
            self.a, self.b = a, b

    sublime.Region = Region
    shim = types.ModuleType("sublime_plugin")
    shim.TextCommand = type("TextCommand", (), {})
    shim.EventListener = type("EventListener", (), {})
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = shim
    path = Path(__file__).resolve().parents[1] / "oreslang.py"
    spec = importlib.util.spec_from_file_location("oreslang_wave1712_regions", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeView:
    def __init__(self):
        self.calls = []
        self.regions = []
        self.status = []
        self.erased = []

    def is_valid(self):
        return True

    def file_name(self):
        return "/tmp/wave1712/main.ores"

    def size(self):
        return 32

    def text_point(self, row, column, clamp_column=True):
        return min(32, row * 10 + column)

    def add_regions(self, *args, **kwargs):
        self.calls.append(("add", bool(kwargs)))
        if "annotations" in kwargs:
            raise TypeError("old Sublime API")
        self.regions = args[1]

    def erase_regions(self, key):
        self.erased.append(key)

    def set_status(self, key, message):
        self.status.append((key, message))


class RegionAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def test_foreign_file_excluded_and_local_ranges_clamped_with_old_api(self):
        module = self.plugin
        view = FakeView()
        module._settings = lambda: types.SimpleNamespace(
            get=lambda key, default=None: default
        )
        local = dict(file=view.file_name(), line=2, column=3,
                     end_line=2, end_column=6, severity="error", message="one")
        foreign = dict(local, file="/tmp/wave1712/other.ores",
                       message="foreign")
        clipped = dict(local, line=4, column=6,
                       end_line=5, end_column=3, message="clipped")
        module._apply_diagnostics(view, [local, foreign, clipped])
        self.assertEqual(view.calls, [("add", True), ("add", False)])
        self.assertEqual([(region.a, region.b) for region in view.regions],
                         [(12, 15), (31, 32)])
        self.assertEqual(view.status[-1],
                         ("oreslang_diagnostics", "Oreslang: 2 diagnostics"))

    def test_only_foreign_diagnostics_clears_stale_regions(self):
        module = self.plugin
        view = FakeView()
        module._apply_diagnostics(view, [
            dict(file="/tmp/wave1712/elsewhere.ores", line=1, column=1,
                 end_line=1, end_column=2, severity="warning",
                 message="not this tab")
        ])
        self.assertEqual(view.regions, [])
        self.assertEqual(view.erased, [module.DIAGNOSTIC_KEY])
        self.assertEqual(view.status[-1],
                         ("oreslang_diagnostics", "Oreslang: no diagnostics"))


if __name__ == "__main__":
    unittest.main()
