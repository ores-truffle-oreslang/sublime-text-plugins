"""Package source snapshots are detached from later edits to staged source files."""
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.package_sublime import ROOT, MEMBERS, package_files, create_package, verify_package


class ReviewedSourceSnapshotIsolation(unittest.TestCase):
    def test_source_snapshot_stays_stable_under_late_mutation_and_stray_files(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "source"
            source.mkdir()
            for name in MEMBERS:
                shutil.copyfile(ROOT / name, source / name)
            initial = package_files(source)
            (source / "unreviewed.py").write_text("do not package", encoding="utf-8")
            (source / "Main.sublime-menu").write_bytes(b"late unreviewed mutation")
            self.assertEqual(initial["Main.sublime-menu"], (ROOT / "Main.sublime-menu").read_bytes())
            changed = package_files(source)
            self.assertNotEqual(changed["Main.sublime-menu"], initial["Main.sublime-menu"])
            self.assertEqual(set(initial), set(MEMBERS))
            first = base / "first.sublime-package"
            second = base / "second.sublime-package"
            create_package(initial, first)
            verify_package(initial, first)
            create_package(initial, second)
            verify_package(initial, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), sorted(MEMBERS))
                self.assertNotIn("unreviewed.py", archive.namelist())
                self.assertEqual(archive.read("Main.sublime-menu"), initial["Main.sublime-menu"])
            with self.assertRaises(ValueError):
                verify_package(changed, first)


if __name__ == "__main__":
    unittest.main()
