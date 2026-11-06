"""Verify rejected package manifests never truncate an existing release target."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import package_sublime as publisher


class Gpt6Wave1607PackageManifestRollback(unittest.TestCase):
    def test_rejected_manifests_keep_existing_release_bytes(self):
        baseline = publisher.package_files()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "Oreslang.sublime-package"
            sentinel = b"EXISTING-RELEASE-DO-NOT-TRUNCATE"
            invalid = []

            incomplete = dict(baseline)
            incomplete.pop("oreslang.py")
            invalid.append(incomplete)

            extra = dict(baseline)
            extra["unreviewed-script.py"] = b"print('no')\n"
            invalid.append(extra)

            mutable = dict(baseline)
            mutable["oreslang.py"] = bytearray(mutable["oreslang.py"])
            invalid.append(mutable)

            for case in invalid:
                target.write_bytes(sentinel)
                with self.assertRaisesRegex(ValueError, "reviewed byte allowlist"):
                    publisher.create_package(case, target)
                self.assertEqual(target.read_bytes(), sentinel)

            publisher.create_package(baseline, target)
            publisher.verify_package(baseline, target)
            valid_bytes = target.read_bytes()
            publisher.create_package(baseline, target)
            self.assertEqual(target.read_bytes(), valid_bytes)

    def test_invalid_archive_bytes_cannot_be_mistaken_for_verified_release(self):
        payloads = publisher.package_files()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "Oreslang.sublime-package"
            target.write_bytes(b"not-a-zip")
            with self.assertRaises(Exception):
                publisher.verify_package(payloads, target)
            publisher.create_package(payloads, target)
            publisher.verify_package(payloads, target)


if __name__ == "__main__":
    unittest.main()
