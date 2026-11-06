"""Duplicate canonical ZIP entries must never shadow reviewed package bytes."""
from __future__ import annotations

import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

from tools import package_sublime as publisher


class Gpt6Wave1609DuplicateMemberShadowing(unittest.TestCase):
    def test_duplicate_canonical_member_fails_before_trusting_either_copy(self):
        reviewed = publisher.package_files()
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "reviewed.sublime-package"
            publisher.create_package(reviewed, artifact)
            publisher.verify_package(reviewed, artifact)
            trusted_zip = artifact.read_bytes()
            # A downstream extractor may choose first or last duplicate member.
            # Reject both byte-identical duplicates and malicious shadow copies.
            for duplicate in (reviewed["oreslang.py"], b"# forged entry\n"):
                with self.subTest(duplicate_length=len(duplicate)):
                    publisher.create_package(reviewed, artifact)
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        with zipfile.ZipFile(artifact, "a") as archive:
                            archive.writestr("oreslang.py", duplicate)
                    with zipfile.ZipFile(artifact, "r") as archive:
                        self.assertEqual(archive.namelist().count("oreslang.py"), 2)
                    with self.assertRaisesRegex(ValueError, "unexpected package files"):
                        publisher.verify_package(reviewed, artifact)
                    self.assertNotEqual(artifact.read_bytes(), trusted_zip)
            publisher.create_package(reviewed, artifact)
            publisher.verify_package(reviewed, artifact)
            self.assertEqual(artifact.read_bytes(), trusted_zip)


if __name__ == "__main__":
    unittest.main()
