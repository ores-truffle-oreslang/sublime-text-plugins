"""A forged archive comment cannot certify a deterministic Sublime release."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import zipfile

from tools import package_sublime as publisher


class Gpt6Wave1606ReleaseCommentRecovery(unittest.TestCase):
    def test_archive_comment_rejected_then_deterministic_rebuild_recovers(self):
        payloads = publisher.package_files()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "Oreslang.sublime-package"
            publisher.create_package(payloads, destination)
            publisher.verify_package(payloads, destination)
            baseline = destination.read_bytes()

            # zipfile append writes central-directory metadata without changing
            # member content: a forged provenance note must still be rejected.
            with zipfile.ZipFile(destination, "a") as archive:
                archive.comment = b"APPROVED: not a trusted release attestation"
            with self.assertRaisesRegex(ValueError, "unexpected archive comment"):
                publisher.verify_package(payloads, destination)

            publisher.create_package(payloads, destination)
            publisher.verify_package(payloads, destination)
            self.assertEqual(destination.read_bytes(), baseline)
            self.assertEqual(set(payloads), set(publisher.MEMBERS))

    def test_partial_caller_manifest_cannot_verify_an_existing_package(self):
        payloads = publisher.package_files()
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "Oreslang.sublime-package"
            publisher.create_package(payloads, destination)
            partial = dict(payloads)
            partial.pop("oreslang.py")
            with self.assertRaisesRegex(ValueError, "reviewed byte allowlist"):
                publisher.verify_package(partial, destination)
            publisher.verify_package(payloads, destination)


if __name__ == "__main__":
    unittest.main()
