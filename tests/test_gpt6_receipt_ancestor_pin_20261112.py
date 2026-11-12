"""Source-bound receipt paths may not traverse a symlink at any depth."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.source_bound_release_receipt_v1 import ReceiptDenied, _safe_path


class ReceiptAncestorIdentityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        (self.root / "dist").mkdir()
        (self.root / "real").mkdir()
        (self.root / "real" / "nested").mkdir()

    def test_nested_ordinary_directories_are_valid(self):
        (self.root / "dist" / "genuine").mkdir()
        (self.root / "dist" / "genuine" / "nested").mkdir()
        path = _safe_path(self.root, "dist/genuine/nested/receipt.json")
        self.assertEqual(path, self.root / "dist/genuine/nested/receipt.json")

    def test_nested_symlink_back_into_same_checkout_is_denied(self):
        (self.root / "dist" / "redirect").symlink_to(
            self.root / "real", target_is_directory=True)
        for path in ("dist/redirect/receipt.json", "dist/redirect/nested/receipt.json"):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ReceiptDenied, "UNSAFE_ARTIFACT_PARENT"):
                    _safe_path(self.root, path)
        self.assertFalse((self.root / "real" / "receipt.json").exists())

    def test_regular_file_as_intermediate_component_is_denied(self):
        (self.root / "dist" / "regular").write_text("sentinel")
        with self.assertRaisesRegex(ReceiptDenied, "UNSAFE_ARTIFACT_PARENT"):
            _safe_path(self.root, "dist/regular/out.json")
        self.assertEqual((self.root / "dist" / "regular").read_text(), "sentinel")

    def test_symlinked_final_parent_and_absolute_or_traversal_are_denied(self):
        (self.root / "dist" / "redirection").symlink_to(
            self.root / "real", target_is_directory=True)
        for value in ("dist/redirection/out.json", "../out.json", "/tmp/out.json"):
            with self.subTest(path=value):
                with self.assertRaises(ReceiptDenied):
                    _safe_path(self.root, value)


if __name__ == "__main__":
    unittest.main()
