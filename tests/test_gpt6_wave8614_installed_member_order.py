"""Installed Sublime package verification rejects changed ZIP member order.

This exercises the actual source-owned host packager, not compiler guest output.
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("gpt6_wave8614_order_packager", ROOT / "tools/package_sublime.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class InstalledMemberOrder(unittest.TestCase):
    def test_reordering_exact_members_is_rejected_and_rebuild_restores_bytes(self):
        files = package.package_files()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "install archive.sublime-package"
            package.create_package(files, dest)
            package.verify_package(files, dest)
            canonical = dest.read_bytes()
            with zipfile.ZipFile(dest, "r") as original:
                names = original.namelist()
                assert names == sorted(package.MEMBERS)
                infos = {info.filename: info for info in original.infolist()}
                payloads = {name: original.read(name) for name in names}
            with zipfile.ZipFile(dest, "w") as changed:
                for name in reversed(names):
                    changed.writestr(infos[name], payloads[name])
            with zipfile.ZipFile(dest, "r") as tampered:
                self.assertEqual(tampered.namelist(), list(reversed(names)))
                for name in names:
                    self.assertEqual(tampered.read(name), files[name])
            with self.assertRaisesRegex(ValueError, "Archive contains unexpected package files"):
                package.verify_package(files, dest)
            self.assertNotEqual(dest.read_bytes(), canonical)
            package.create_package(files, dest)
            package.verify_package(files, dest)
            self.assertEqual(dest.read_bytes(), canonical)
