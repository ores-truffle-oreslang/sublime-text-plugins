"""Release destination symlinks may not overwrite an unrelated sentinel."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import package_sublime as publisher


class Gpt6Wave1607PackageSymlinkSentinel(unittest.TestCase):
    def test_symlink_target_preserved_and_deterministic_build_recovers(self):
        payloads = publisher.package_files()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sentinel = root / "external-sentinel.txt"
            sentinel.write_bytes(b"independent user-owned data\n")
            destination = root / "release.sublime-package"
            try:
                destination.symlink_to(sentinel)
            except (OSError, NotImplementedError):
                self.skipTest("destination symlinks not supported on this host")
            with self.assertRaisesRegex(ValueError, "symlinked package destination"):
                publisher.create_package(payloads, destination)
            self.assertEqual(sentinel.read_bytes(), b"independent user-owned data\n")
            self.assertTrue(destination.is_symlink())
            destination.unlink()
            publisher.create_package(payloads, destination)
            publisher.verify_package(payloads, destination)
            first = destination.read_bytes()
            self.assertTrue(first.startswith(b"PK"))
            publisher.create_package(payloads, destination)
            publisher.verify_package(payloads, destination)
            self.assertEqual(destination.read_bytes(), first)
            self.assertEqual(sentinel.read_bytes(), b"independent user-owned data\n")


if __name__ == "__main__":
    unittest.main()
