"""Malformed ZIP end-of-central-directory must fail closed and restore deterministically."""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from scripts.build_sublime_package import build, verify


class ReleaseTruncatedEndDirectory(unittest.TestCase):
    def test_truncated_zip_eocd_rejected_then_canonical_rebuild_restores(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "Oreslang.sublime-package"
            pristine_hash = build(dest)
            pristine = dest.read_bytes()
            self.assertEqual(hashlib.sha256(pristine).hexdigest(), pristine_hash)
            self.assertEqual(pristine[-22:-18], b"PK\x05\x06")
            for lost in (1, 7, 22):
                with self.subTest(lost=lost):
                    dest.write_bytes(pristine[:-lost])
                    with self.assertRaises((zipfile.BadZipFile, EOFError, ValueError)):
                        verify(dest)
                    self.assertEqual(build(dest), pristine_hash)
                    self.assertEqual(dest.read_bytes(), pristine)
                    verify(dest)


if __name__ == "__main__":
    unittest.main()
