"""Reject out-of-allowlist ZIP members before accepting a Sublime release."""
from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from tools import package_sublime as publisher


class Gpt6Wave1607ExtraMemberProvenance(unittest.TestCase):
    def test_added_unreviewed_member_and_traversal_path_fail_closed_then_recover(self):
        reviewed = publisher.package_files()
        with tempfile.TemporaryDirectory() as directory:
            artifact = Path(directory) / "Oreslang.sublime-package"
            publisher.create_package(reviewed, artifact)
            publisher.verify_package(reviewed, artifact)
            baseline = artifact.read_bytes()
            for unreviewed_name in ("UNREVIEWED-README.txt", "../escape.txt", "test/secret.ores"):
                publisher.create_package(reviewed, artifact)
                with zipfile.ZipFile(artifact, "a") as archive:
                    archive.writestr(unreviewed_name, b"forged release member")
                with self.subTest(unreviewed_name=unreviewed_name):
                    with self.assertRaisesRegex(ValueError, "unexpected package files"):
                        publisher.verify_package(reviewed, artifact)
                    self.assertNotEqual(artifact.read_bytes(), baseline)
            publisher.create_package(reviewed, artifact)
            publisher.verify_package(reviewed, artifact)
            self.assertEqual(artifact.read_bytes(), baseline)
            self.assertEqual(len(reviewed), len(publisher.MEMBERS))


if __name__ == "__main__":
    unittest.main()
