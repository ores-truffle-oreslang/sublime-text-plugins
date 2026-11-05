"""View generation leases are unique under concurrent requests and reused IDs.

Source-owned host test; no editor application or guest compiler is launched.
"""
from concurrent.futures import ThreadPoolExecutor
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
    path = Path(__file__).resolve().parents[1] / "oreslang.py"
    spec = importlib.util.spec_from_file_location("oreslang_wave1712_generation", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GenerationConcurrency(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin = load_plugin()

    def test_concurrent_editor_requests_have_exactly_one_current_lease_per_id(self):
        module = self.plugin
        ids = (41, 42, 43, 44)
        with ThreadPoolExecutor(max_workers=12) as pool:
            leases = list(pool.map(
                lambda index: (ids[index % len(ids)],
                               module._next_generation(ids[index % len(ids)])),
                range(320),
            ))
        self.assertEqual(len({lease for _, lease in leases}), 320)
        for view_id in ids:
            per_view = [lease for owner, lease in leases if owner == view_id]
            self.assertEqual(len(per_view), 80)
            self.assertTrue(module._generation_is_current(view_id, max(per_view)))
            self.assertTrue(all(
                not module._generation_is_current(view_id, lease)
                for lease in per_view if lease != max(per_view)
            ))
        self.assertFalse(module._generation_is_current(41, max(
            lease for owner, lease in leases if owner == 42)))

    def test_close_and_reuse_of_id_never_revives_prior_generation(self):
        module = self.plugin

        class View:
            def id(self):
                return 4999

        old = module._next_generation(4999)
        module.OreslangDiagnosticsListener().on_close(View())
        self.assertNotIn(4999, module._generations)
        self.assertFalse(module._generation_is_current(4999, old))
        new = module._next_generation(4999)
        self.assertNotEqual(new, old)
        self.assertTrue(module._generation_is_current(4999, new))
        self.assertFalse(module._generation_is_current(4999, old))


if __name__ == "__main__":
    unittest.main()
