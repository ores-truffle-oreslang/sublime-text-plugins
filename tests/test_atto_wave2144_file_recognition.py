"""AttoLang extension handling in the actual Sublime syntax and Python editor guard."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]

def load_plugin():
    sublime = types.ModuleType("sublime")
    sublime.DRAW_SQUIGGLY_UNDERLINE = 1
    sublime.DRAW_NO_FILL = 2
    shim = types.ModuleType("sublime_plugin")
    shim.TextCommand = type("TextCommand", (), {})
    shim.EventListener = type("EventListener", (), {})
    sys.modules["sublime"] = sublime
    sys.modules["sublime_plugin"] = shim
    spec = importlib.util.spec_from_file_location("atto_wave2144_plugin", ROOT / "oreslang.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class AttoRecognition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def test_syntax_resource_maps_both_extensions_to_one_legacy_scope(self):
        text = (ROOT / "Oreslang.sublime-syntax").read_text(encoding="utf-8")
        header = text.split("variables:", 1)[0]
        self.assertIn("file_extensions:\n  - ores\n  - atto\n", header)
        self.assertIn("scope: source.oreslang", header)

    def test_empty_view_path_recognition_accepts_atto_and_ores_not_forged_suffixes(self):
        class View:
            def __init__(self, name):
                self.name = name
            def is_valid(self):
                return True
            def size(self):
                return 0
            def file_name(self):
                return self.name
            def match_selector(self, *_):
                raise AssertionError("empty view must select by filename")
        for name in ("/tmp/main.atto", "/tmp/main.ores"):
            self.assertTrue(self.plugin._is_oreslang(View(name)), name)
        for name in ("/tmp/main.atto.bak", "/tmp/main.ores.bak", "/tmp/main.txt", None):
            self.assertFalse(self.plugin._is_oreslang(View(name)), str(name))

    def test_nonempty_views_continue_to_respect_syntax_selector(self):
        class View:
            def is_valid(self):
                return True
            def size(self):
                return 6
            def match_selector(self, pos, selector):
                self.selection = (pos, selector)
                return selector == "source.oreslang"
        view = View()
        self.assertTrue(self.plugin._is_oreslang(view))
        self.assertEqual(view.selection, (0, "source.oreslang"))

if __name__ == "__main__":
    unittest.main()
