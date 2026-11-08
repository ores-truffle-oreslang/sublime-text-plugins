"""Adversarial path-admission tests for the #142 ancestor symlink guard.

This suite validates pre-existing path redirects. A concurrent directory-swap
race is NOT proved safe by these tests; the pinned-FD publication in #143 is
separate and must be integrated without losing this coverage.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import package_sublime as publisher


class DestinationAncestorMatrixTests(unittest.TestCase):
    def setUp(self):
        self.files = publisher.package_files()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.external = self.root / "external"
        self.external.mkdir()
        self.sentinel = self.external / "private.sublime-package"
        self.data = b"caller-owned sentinel must never be overwritten\n"
        self.sentinel.write_bytes(self.data)

    def link_dir(self, name: str, target: Path) -> Path:
        alias = self.root / name
        try:
            alias.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("directory symlinks unsupported")
        return alias

    def assert_denied_without_external_write(self, destination: Path, message: str) -> None:
        with self.assertRaisesRegex(ValueError, message):
            publisher.create_package(self.files, destination)
        self.assertEqual(self.sentinel.read_bytes(), self.data)
        self.assertFalse((self.external / "new.sublime-package").exists())

    def test_two_hop_symlink_chain_and_nested_parent(self):
        (self.external / "level").mkdir()
        first = self.link_dir("first", self.external)
        second = self.link_dir("second", first)
        for dest in (
            first / "new.sublime-package",
            second / "new.sublime-package",
            second / "level" / "new.sublime-package",
            second / "private.sublime-package",
        ):
            with self.subTest(dest=str(dest)):
                self.assert_denied_without_external_write(
                    dest, "symlinked package destination parent")

    def test_dangling_directory_symlink_is_still_rejected(self):
        missing = self.root / "removed"
        alias = self.link_dir("dangling", missing)
        self.assert_denied_without_external_write(
            alias / "new.sublime-package", "symlinked package destination parent")
        self.assertFalse(missing.exists())

    def test_canonicalization_cannot_hide_dot_dot_path_components(self):
        cases = (
            self.root / "out" / ".." / "private.sublime-package",
            self.root / "uncreated" / "child" / ".." / "new.sublime-package",
            self.root / ".." / self.root.name / "new.sublime-package",
        )
        for dest in cases:
            with self.subTest(dest=str(dest)):
                self.assert_denied_without_external_write(
                    dest, "noncanonical package destination parent")
        self.assertFalse((self.root / "uncreated").exists())
        self.assertFalse((self.root / "out").exists())

    def test_dot_dot_substring_is_not_a_false_positive(self):
        # Only a literal '..' path component should be rejected. Legal path
        # names containing two dots must still produce deterministic ZIP bytes.
        for component in ("..safe", "safe..", "safe...x"):
            dest = self.root / component / "nested" / "pkg.sublime-package"
            with self.subTest(name=component):
                publisher.create_package(self.files, dest)
                publisher.verify_package(self.files, dest)
                first = dest.read_bytes()
                publisher.create_package(self.files, dest)
                publisher.verify_package(self.files, dest)
                self.assertEqual(dest.read_bytes(), first)
        self.assertEqual(self.sentinel.read_bytes(), self.data)

    def test_source_directory_alias_does_not_write_new_package(self):
        alias = self.link_dir("source-alias", publisher.ROOT)
        target = publisher.ROOT / "never-write-this-sublime-package"
        self.assertFalse(target.exists(), "reviewed source tree has no fixture collision")
        self.assert_denied_without_external_write(
            alias / target.name, "symlinked package destination parent")
        self.assertFalse(target.exists())

    def test_bad_manifest_is_rejected_before_creating_nested_output(self):
        destination = self.root / "uncreated" / "nested" / "out.sublime-package"
        cases = (
            {},
            {**self.files, "unreviewed": b"extra"},
            {**self.files, next(iter(self.files)): bytearray(b"not immutable bytes")},
        )
        for bad in cases:
            with self.subTest(keys=len(bad)):
                with self.assertRaisesRegex(ValueError, "package members must match"):
                    publisher.create_package(bad, destination)
                self.assertFalse(destination.parent.exists())
        self.assertEqual(self.sentinel.read_bytes(), self.data)


if __name__ == "__main__":
    unittest.main()
