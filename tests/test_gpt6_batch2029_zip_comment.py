"""The canonical package must reject out-of-band ZIP comments and recover byte-for-byte."""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts import build_sublime_package as release


class ZipArchiveCommentAdmissionTest(unittest.TestCase):
    def test_comment_cannot_impersonate_release_receipt_or_survive_rebuild(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "Oreslang.sublime-package"
            original_digest = release.build(artifact)
            original_bytes = artifact.read_bytes()
            with zipfile.ZipFile(artifact, "a") as package:
                package.comment = b"reviewed-snapshot-sha256=" + b"0" * 64
            self.assertNotEqual(artifact.read_bytes(), original_bytes)
            with zipfile.ZipFile(artifact, "r") as package:
                self.assertEqual(package.namelist(), sorted(release.FILES))
                for name in release.FILES:
                    self.assertEqual(package.read(name), (release.ROOT / name).read_bytes())
            with self.assertRaisesRegex(ValueError, "archive comment"):
                release.verify(artifact)
            self.assertEqual(release.build(artifact), original_digest)
            self.assertEqual(artifact.read_bytes(), original_bytes)
            release.verify(artifact)
            self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), original_digest)


if __name__ == "__main__":
    unittest.main()
