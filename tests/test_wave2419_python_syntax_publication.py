"""Sublime package source validation and deterministic archive recovery.

Host-only Python publisher evidence, not AttoLang compiler/guest parity.
"""
import importlib.util
import pathlib
import shutil
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "wave2419_sublime_publisher", ROOT / "tools" / "package_sublime.py"
)
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)


class PythonSourceSyntaxPublication(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name)
        for name in publisher.MEMBERS:
            shutil.copyfile(ROOT / name, self.root / name)
        self.dest = self.root / "output" / "Oreslang.sublime-package"
        self.dest.parent.mkdir()
        self.source = self.root / "oreslang.py"
        self.original = self.source.read_bytes()

    def test_invalid_python_source_never_replaces_verified_package(self):
        good = publisher.package_files(self.root)
        publisher.create_package(good, self.dest)
        publisher.verify_package(good, self.dest)
        baseline = self.dest.read_bytes()
        for invalid in (b"def syntactically_broken(:\n",
                        b"if True:\nreturn 4\n",
                        b"\xff\xfe"):
            with self.subTest(invalid=invalid):
                self.source.write_bytes(invalid)
                with self.assertRaises(SyntaxError):
                    publisher.package_files(self.root)
                self.assertEqual(self.dest.read_bytes(), baseline)
                self.assertEqual(sorted(self.dest.parent.iterdir()), [self.dest])

        self.source.write_bytes(self.original)
        restored = publisher.package_files(self.root)
        self.assertEqual(restored, good)
        publisher.create_package(restored, self.dest)
        publisher.verify_package(restored, self.dest)
        self.assertEqual(self.dest.read_bytes(), baseline)

    def test_validation_uses_owned_source_snapshot_not_mutable_file(self):
        good = publisher.package_files(self.root)
        self.assertEqual(good["oreslang.py"], self.original)
        self.source.write_bytes(b"def broken(:\n")
        self.assertEqual(good["oreslang.py"], self.original)
        with self.assertRaises(SyntaxError):
            publisher.package_files(self.root)
        self.source.write_bytes(self.original)
        newer = publisher.package_files(self.root)
        self.assertEqual(newer, good)
        self.assertEqual(set(newer), set(publisher.MEMBERS))


if __name__ == "__main__":
    unittest.main()
