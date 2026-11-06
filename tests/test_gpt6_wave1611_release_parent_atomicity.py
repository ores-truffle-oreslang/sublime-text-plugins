"""Invalid release inputs must not create directories or replace a reviewed ZIP."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_sublime_package as release


class ReleaseParentAtomicity(unittest.TestCase):
    def test_late_missing_input_has_no_output_side_effect_then_recovers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            for name in release.FILES:
                (root / name).write_bytes((release.ROOT / name).read_bytes())
            dest = Path(temporary) / "absent" / "nested" / release.ARCHIVE_NAME
            missing = root / "oreslang.py"
            prior = missing.read_bytes()
            missing.unlink()
            with patch.object(release, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "missing or symlinked"):
                    release.build(dest)
                self.assertFalse(dest.parent.exists(), "failed preflight created output tree")
                missing.write_bytes(prior)
                digest = release.build(dest)
                release.verify(dest)
                original = dest.read_bytes()
                self.assertEqual(len(digest), 64)
                self.assertTrue(original.startswith(b"PK"))
                missing.unlink()
                with self.assertRaisesRegex(ValueError, "missing or symlinked"):
                    release.build(dest)
                self.assertEqual(dest.read_bytes(), original, "failed preflight replaced verified ZIP")
                missing.write_bytes(prior)
                self.assertEqual(release.build(dest), digest)
                self.assertEqual(dest.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
