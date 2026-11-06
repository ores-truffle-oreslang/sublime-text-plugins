"""A release-only archive is determined by its allowlist, not stray tree files."""
import importlib.util
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("wave6207_release_package", ROOT / "scripts" / "build_sublime_package.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class Wave6207ReleaseAllowlist(unittest.TestCase):
    def test_extra_source_tree_files_do_not_enter_release_and_rebuild_is_identical(self):
        with tempfile.TemporaryDirectory() as folder:
            tree = Path(folder) / "sources"
            tree.mkdir()
            for name in release.FILES:
                shutil.copyfile(ROOT / name, tree / name)
            output = Path(folder) / "release.zip"
            with patch.object(release, "ROOT", tree):
                expected_digest = release.build(output)
                expected_bytes = output.read_bytes()
                release.verify(output)
                (tree / "Preview.sublime-syntax").write_text("untrusted")
                (tree / ".github").mkdir()
                (tree / ".github" / "token").write_text("not a release member")
                (tree / "tests").mkdir()
                (tree / "tests" / "malicious.py").write_text("raise RuntimeError('not distributable')")
                self.assertEqual(release.build(output), expected_digest)
                self.assertEqual(output.read_bytes(), expected_bytes)
                release.verify(output)
                with zipfile.ZipFile(output) as archive:
                    self.assertEqual(archive.namelist(), sorted(release.FILES))
                    self.assertEqual(len(archive.namelist()), len(set(archive.namelist())))

                # An extra member added after the trusted build must be
                # rejected, and rebuilding must restore exact bytes.
                with zipfile.ZipFile(output, "a") as archive:
                    archive.writestr("tests/malicious.py", b"raise RuntimeError('bad')")
                with self.assertRaisesRegex(ValueError, "unexpected"):
                    release.verify(output)
                self.assertEqual(release.build(output), expected_digest)
                self.assertEqual(output.read_bytes(), expected_bytes)
                release.verify(output)


if __name__ == "__main__":
    unittest.main()
