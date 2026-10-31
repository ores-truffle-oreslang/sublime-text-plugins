import importlib.util
import os
import pathlib
import subprocess
import sys
import threading
import time
import types
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

def load_plugin():
    sublime = types.ModuleType('sublime')
    sublime.DRAW_SQUIGGLY_UNDERLINE = 1
    sublime.DRAW_NO_FILL = 2
    sublime.set_timeout = lambda cb, delay: cb()
    pending = []
    sublime.set_timeout_async = lambda cb, delay: pending.append(cb)
    sublime.load_settings = lambda name: types.SimpleNamespace(get=lambda key, default=None: default)
    plugin_stub = types.ModuleType('sublime_plugin')
    plugin_stub.TextCommand = type('TextCommand', (), {})
    plugin_stub.EventListener = type('EventListener', (), {})
    sys.modules['sublime'] = sublime
    sys.modules['sublime_plugin'] = plugin_stub
    spec = importlib.util.spec_from_file_location('oreslang_lifecycle_under_test', ROOT/'oreslang.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, sublime, pending

class FakeView:
    def __init__(self, view_id=19):
        self._id = view_id
        self._valid = True
        self._changes = 1
        self._dirty = False
        self.erased_regions = []
        self.erased_status = []
    def id(self): return self._id
    def size(self): return 10
    def is_valid(self): return self._valid
    def is_dirty(self): return self._dirty
    def match_selector(self, point, scope): return scope == 'source.oreslang'
    def change_count(self): return self._changes
    def file_name(self): return '/tmp/oreslang-lifecycle.ores'
    def window(self): return None
    def erase_regions(self, key): self.erased_regions.append(key)
    def erase_status(self, key): self.erased_status.append(key)
    def set_status(self, key, msg): pass

class LifecycleTests(unittest.TestCase):
    def test_edited_tab_clears_old_diagnostics_even_without_auto_cli(self):
        module, sublime, pending = load_plugin()
        view = FakeView()
        listener = module.OreslangDiagnosticsListener()
        initial = module._next_generation(view.id())
        listener.on_modified_async(view)
        self.assertFalse(module._generation_is_current(view.id(),initial))
        self.assertEqual([module.DIAGNOSTIC_KEY],view.erased_regions)
        self.assertEqual(['oreslang_diagnostics'],view.erased_status)
        self.assertEqual([],pending)

    def test_closed_view_releases_generation_and_reused_id_cannot_restore_old_result(self):
        module, _, pending = load_plugin()
        old = FakeView()
        old_gen = module._next_generation(old.id())
        module.OreslangDiagnosticsListener().on_close(old)
        self.assertNotIn(old.id(),module._generations)
        reopened = FakeView(old.id())
        next_gen = module._next_generation(reopened.id())
        self.assertNotEqual(old_gen,next_gen)
        self.assertFalse(module._generation_is_current(old.id(),old_gen))
        self.assertEqual([],pending)

    def test_live_subprocess_is_terminated_when_view_is_cancelled(self):
        module, _, _ = load_plugin()
        closed = threading.Event()
        ready = threading.Event()
        result=[]
        def worker():
            ready.set()
            try:
                module._run_compiler_bounded(
                    [sys.executable, '-c', 'import time; time.sleep(8)'],
                    str(ROOT), 7, cancelled=closed.is_set)
            except BaseException as err:
                result.append(err)
        t=threading.Thread(target=worker,daemon=True)
        t.start()
        self.assertTrue(ready.wait(timeout=1))
        time.sleep(0.15)
        closed.set()
        t.join(timeout=3)
        self.assertFalse(t.is_alive(), 'subprocess cancellation must release the worker promptly')
        self.assertEqual(1,len(result))
        self.assertIsInstance(result[0],module._CompilerCheckCancelled)

    def test_late_explicit_cli_failure_after_close_does_not_publish_diagnostics(self):
        module, sublime, pending = load_plugin()
        view=FakeView()
        calls=[]
        def fake_run(*args, **kwargs):
            self.assertIn('cancelled',kwargs)
            module.OreslangDiagnosticsListener().on_close(view)
            self.assertTrue(kwargs['cancelled']())
            raise module._CompilerCheckCancelled()
        module._run_compiler_bounded=fake_run
        module._run_check(view,force_output=True)
        self.assertEqual([],pending)
        self.assertEqual([],view.erased_regions)


    def test_posix_cancelled_compiler_cannot_leave_grandchild_writing_after_kill(self):
        if os.name != 'posix':
            self.skipTest('POSIX process groups; Windows child-only termination not verified')
        import tempfile
        module, _, _ = load_plugin()
        with tempfile.TemporaryDirectory(prefix='oreslang-tree-') as folder:
            marker = os.path.join(folder, 'escaped-child')
            worker = (
                "import subprocess,sys,time;"
                "subprocess.Popen([sys.executable,'-c',"
                "'import time,pathlib,sys;time.sleep(0.65);pathlib.Path(sys.argv[1]).write_text(\"escaped\")',"
                "sys.argv[1]],stdout=sys.stdout,stderr=sys.stderr);"
                "print('ready',flush=True);time.sleep(8)"
            )
            cancel = threading.Event()
            errors = []
            def run():
                try:
                    module._run_compiler_bounded(
                        [sys.executable,'-c',worker,marker],
                        folder, 4, cancelled=cancel.is_set)
                except BaseException as exc:
                    errors.append(exc)
            t=threading.Thread(target=run, daemon=True)
            t.start()
            time.sleep(0.3)
            cancel.set()
            t.join(timeout=3)
            self.assertFalse(t.is_alive(),'cancelled CLI worker must exit promptly')
            self.assertEqual(len(errors),1)
            self.assertIsInstance(errors[0], module._CompilerCheckCancelled)
            time.sleep(0.65)
            self.assertFalse(os.path.exists(marker),'grandchild escaped CLI process-group cancellation')

    def test_pending_debounce_is_revoked_on_close_and_delay_is_bounded(self):
        module, sublime, pending = load_plugin()
        view=FakeView()
        sublime.load_settings=lambda name: types.SimpleNamespace(
            get=lambda key, default=None: {
                'diagnostics_on_change': True,
                'diagnostics_delay_ms': 1000000000
            }.get(key, default))
        module.OreslangDiagnosticsListener().on_modified_async(view)
        self.assertEqual(len(pending),1)
        module.OreslangDiagnosticsListener().on_close(view)
        module._run_check=lambda *args, **kwargs: self.fail('stale debounced CLI executed')
        pending.pop()()
        self.assertNotIn(view.id(),module._generations)

if __name__=='__main__':
    unittest.main()
