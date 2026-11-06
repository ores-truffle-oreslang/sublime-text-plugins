"""Real release ZIP builder repeatability and comment-tampering recovery.

Source-owned host/package evidence only; not compiled AttoLang guest proof.
"""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("gpt6_wave8614_release_pkg", ROOT / "scripts/build_sublime_package.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class SublimeReleaseRepeatability(unittest.TestCase):
    def test_distinct_paths_reproduce_bytes_and_reject_comment_spoofing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "path with spaces" / "build one.sublime-package"
            second = root / "second archive.sublime-package"
            first_digest = release.build(first)
            second_digest = release.build(second)
            canonical = first.read_bytes()
            self.assertEqual(canonical, second.read_bytes())
            self.assertEqual(first_digest, second_digest)
            self.assertEqual(first_digest, hashlib.sha256(canonical).hexdigest())
            release.verify(first)
            release.verify(second)

            # Alter only the ZIP global comment; keep original member bytes.
            with zipfile.ZipFile(first, "a") as archive:
                archive.comment = b"\nUNTRUSTED provenance: forged-release\n"
            with zipfile.ZipFile(first, "r") as archive:
                self.assertEqual(archive.namelist(), sorted(release.FILES))
                self.assertTrue(archive.comment)
            with self.assertRaisesRegex(ValueError, "unexpected ZIP archive comment"):
                release.verify(first)
            self.assertEqual(second.read_bytes(), canonical)
            self.assertNotEqual(first.read_bytes(), canonical)

            self.assertEqual(release.build(first), first_digest)
            release.verify(first)
            self.assertEqual(first.read_bytes(), canonical)
            self.assertEqual(second.read_bytes(), canonical)
