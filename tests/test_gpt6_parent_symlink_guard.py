"""Reject release outputs redirected via a symlinked ancestor directory."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import package_sublime as publisher


class ParentSymlinkGuardTests(unittest.TestCase):
    def test_parent_and_grandparent_symlinks_never_write_external_package(self):
        files = publisher.package_files()
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            external = root / "external"
            external.mkdir()
            sentinel = external / "release.sublime-package"
            sentinel.write_bytes(b"unrelated user-owned sentinel\n")
            redirect = root / "redirect"
            (external / "subdir").mkdir()
            try:
                redirect.symlink_to(external, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unsupported")
            for destination in (
                redirect / "release.sublime-package",
                redirect / "subdir" / "release.sublime-package",
            ):
                with self.subTest(destination=str(destination)):
                    with self.assertRaisesRegex(ValueError, "symlinked package destination parent"):
                        publisher.create_package(files, destination)
                    self.assertEqual(sentinel.read_bytes(), b"unrelated user-owned sentinel\n")

            # Lexical dot-dot paths must not sidestep the ancestor walk.
            with self.assertRaisesRegex(ValueError, "noncanonical package destination parent"):
                publisher.create_package(files, root / "nested" / ".." / "redirect" / "release.sublime-package")
            self.assertEqual(sentinel.read_bytes(), b"unrelated user-owned sentinel\\n")

            # A symlinked ancestor should also be refused when the leaf is absent.
            with self.assertRaisesRegex(ValueError, "symlinked package destination parent"):
                publisher.create_package(files, redirect / "fresh.sublime-package")
            self.assertFalse((external / "fresh.sublime-package").exists())

            # Legitimate nested output directory must still work and be deterministic.
            valid = root / "nested" / "release" / "release.sublime-package"
            publisher.create_package(files, valid)
            publisher.verify_package(files, valid)
            first = valid.read_bytes()
            publisher.create_package(files, valid)
            publisher.verify_package(files, valid)
            self.assertEqual(valid.read_bytes(), first)
            self.assertEqual(sentinel.read_bytes(), b"unrelated user-owned sentinel\n")


if __name__ == "__main__":
    unittest.main()
