"""Release ZIP creation must not truncate an existing hardlinked destination."""
import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("wave7110_release", ROOT / "scripts" / "build_sublime_package.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class Wave7110ReleaseHardlinks(unittest.TestCase):
    def test_external_hardlink_rejected_without_truncating_sentinel(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            sentinel = base / "sentinel.txt"
            sentinel.write_bytes(b"EXTERNAL-TRUSTED-DATA")
            output = base / "Oreslang.sublime-package"
            output.hardlink_to(sentinel)
            with self.assertRaisesRegex(ValueError, "hardlinked release destination"):
                release.build(output)
            self.assertEqual(sentinel.read_bytes(), b"EXTERNAL-TRUSTED-DATA")
            self.assertEqual(output.read_bytes(), sentinel.read_bytes())
            output.unlink()
            digest = release.build(output)
            self.assertEqual(len(digest), 64)
            release.verify(output)

    def test_alias_of_staged_source_member_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source_root = base / "source"
            source_root.mkdir()
            for name in release.FILES:
                shutil.copyfile(ROOT / name, source_root / name)
            sentinel = source_root / "Main.sublime-menu"
            original = sentinel.read_bytes()
            output = base / "release.zip"
            output.hardlink_to(sentinel)
            with patch.object(release, "ROOT", source_root):
                with self.assertRaisesRegex(ValueError, "hardlinked release destination"):
                    release.build(output)
            self.assertEqual(sentinel.read_bytes(), original)
            output.unlink()
            with patch.object(release, "ROOT", source_root):
                release.build(output)
                release.verify(output)


if __name__ == "__main__":
    unittest.main()
