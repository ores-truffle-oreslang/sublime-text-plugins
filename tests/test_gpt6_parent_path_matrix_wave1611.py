"""Adversarial ancestor-path and manifest checks for the Sublime package writer.

Test-only companion to #142. Parent-symlink checks are not a substitute for
the atomic, directory-fd-pinned writer being reviewed separately in #143.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import package_sublime as publisher


class ParentPathMatrixTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.files = publisher.package_files()

    def test_relative_ancestor_aliases_do_not_write_external_bytes(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            outside = root / "external"
            outside.mkdir()
            sentinel = outside / "release.sublime-package"
            original = b"INDEPENDENT EXTERNAL FILE\n"
            sentinel.write_bytes(original)
            direct = root / "redirect"
            deep_parent = root / "trusted"
            deep_parent.mkdir()
            nested = deep_parent / "redirect"
            try:
                direct.symlink_to("external", target_is_directory=True)
                nested.symlink_to("../external", target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unsupported")
            for dest in (
                direct / sentinel.name,
                direct / "fresh.sublime-package",
                nested / sentinel.name,
                nested / "subdir" / "new.sublime-package",
            ):
                with self.subTest(destination=str(dest)):
                    with self.assertRaisesRegex(
                        ValueError, "symlinked package destination parent"
                    ):
                        publisher.create_package(self.files, dest)
                    self.assertEqual(sentinel.read_bytes(), original)
            self.assertFalse((outside / "fresh.sublime-package").exists())
            self.assertFalse((outside / "subdir").exists())

    def test_lexical_traversal_is_denied_even_when_it_resolves_to_safe_path(self):
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            safe = root / "safe"
            safe.mkdir()
            sentinel = safe / "release.sublime-package"
            sentinel.write_bytes(b"ORIGINAL BYTES\n")
            for dest in (
                root / "safe" / ".." / "safe" / sentinel.name,
                root / "missing" / ".." / "safe" / sentinel.name,
                root / "safe" / "nested" / ".." / sentinel.name,
            ):
                with self.subTest(destination=str(dest)):
                    with self.assertRaisesRegex(
                        ValueError, "noncanonical package destination parent"
                    ):
                        publisher.create_package(self.files, dest)
                    self.assertEqual(sentinel.read_bytes(), b"ORIGINAL BYTES\n")
            self.assertFalse((safe / "nested").exists())

    def test_invalid_member_set_and_nonbytes_never_create_destination(self):
        for invalid in (
            {k: v for k, v in self.files.items() if k != publisher.MEMBERS[0]},
            {**self.files, publisher.MEMBERS[0]: "not bytes"},
            {**self.files, "unreviewed.txt": b"unexpected"},
        ):
            with self.subTest(members=list(invalid)):
                with tempfile.TemporaryDirectory() as dirname:
                    dest = Path(dirname) / "not-yet-created" / "release.sublime-package"
                    with self.assertRaisesRegex(
                        ValueError, "package members must match the reviewed byte allowlist"
                    ):
                        publisher.create_package(invalid, dest)
                    self.assertFalse(dest.parent.exists())


if __name__ == "__main__":
    unittest.main()
