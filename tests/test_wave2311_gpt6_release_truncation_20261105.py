"""Host regression: terminal ZIP truncations never produce valid release receipts."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_sublime_package import build, verify


class ReleaseArchiveTruncation(unittest.TestCase):
    def test_truncated_central_directory_rejected_and_original_recovered(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "Oreslang.sublime-package"
            digest = build(target)
            original = target.read_bytes()
            self.assertGreater(len(original), 64)
            for removed in (1, 4, 16, 22):
                with self.subTest(bytes_removed=removed):
                    target.write_bytes(original[:-removed])
                    with self.assertRaises((zipfile.BadZipFile, ValueError)):
                        verify(target)
                    self.assertEqual(build(target), digest)
                    self.assertEqual(target.read_bytes(), original)
                    verify(target)


if __name__ == "__main__":
    unittest.main()
