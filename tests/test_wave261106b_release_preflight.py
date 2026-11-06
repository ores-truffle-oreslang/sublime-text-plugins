"""Invalid package source input must not truncate the previous release artifact."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_sublime_package as release


class ReleasePreflightWave261106B(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.artifact = self.root / "Oreslang.sublime-package"
        release.build(self.artifact)
        release.verify(self.artifact)
        self.previous = self.artifact.read_bytes()
        self.fake_root = self.root / "source"
        self.fake_root.mkdir()
        for name in release.FILES:
            (self.fake_root / name).write_bytes((release.ROOT / name).read_bytes())

    def test_missing_late_member_does_not_truncate_previous_release(self):
        (self.fake_root / "oreslang.py").unlink()
        with patch.object(release, "ROOT", self.fake_root):
            with self.assertRaisesRegex(ValueError, "missing or symlinked"):
                release.build(self.artifact)
        self.assertEqual(self.artifact.read_bytes(), self.previous)
        release.verify(self.artifact)

    def test_symlinked_member_does_not_truncate_previous_release(self):
        target = self.fake_root / "Oreslang.sublime-settings"
        target.unlink()
        try:
            target.symlink_to(self.fake_root / "Oreslang.sublime-syntax")
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable on host")
        with patch.object(release, "ROOT", self.fake_root):
            with self.assertRaisesRegex(ValueError, "missing or symlinked"):
                release.build(self.artifact)
        self.assertEqual(self.artifact.read_bytes(), self.previous)
        release.verify(self.artifact)


if __name__ == "__main__":
    unittest.main()
