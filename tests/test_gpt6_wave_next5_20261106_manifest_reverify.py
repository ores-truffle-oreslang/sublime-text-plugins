"""Every reviewed package payload must be individually authenticated on re-verification.

Host-only source regression: never claims AttoLang compiler or guest execution.
"""
import tempfile
import unittest
from pathlib import Path

from tools import package_sublime as publisher


class PackageExpectedPayloadReverify(unittest.TestCase):
    def test_member_by_member_mismatch_preserves_archive_and_rebuild_is_identical(self):
        original = publisher.package_files()
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "dist" / "Oreslang.sublime-package"
            publisher.create_package(original, dest)
            publisher.verify_package(original, dest)
            golden = dest.read_bytes()
            self.assertGreater(len(golden), 100)
            for member in publisher.MEMBERS:
                with self.subTest(member=member):
                    changed = dict(original)
                    payload = changed[member]
                    self.assertTrue(payload)
                    changed[member] = payload[:-1] + bytes([payload[-1] ^ 1])
                    with self.assertRaisesRegex(ValueError, "Package verification failed"):
                        publisher.verify_package(changed, dest)
                    self.assertEqual(dest.read_bytes(), golden)
                    publisher.verify_package(original, dest)
            publisher.create_package(original, dest)
            publisher.verify_package(original, dest)
            self.assertEqual(dest.read_bytes(), golden)

    def test_unreviewed_or_incomplete_expectations_never_certify_archive(self):
        original = publisher.package_files()
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "Oreslang.sublime-package"
            publisher.create_package(original, dest)
            golden = dest.read_bytes()
            incomplete = dict(original)
            incomplete.pop(publisher.MEMBERS[0])
            foreign = dict(original)
            foreign["foreign.ores"] = b"unreviewed"
            wrong_type = dict(original)
            wrong_type[publisher.MEMBERS[-1]] = bytearray(wrong_type[publisher.MEMBERS[-1]])
            for invalid in (incomplete, foreign, wrong_type):
                with self.assertRaisesRegex(ValueError, "package members"):
                    publisher.verify_package(invalid, dest)
                self.assertEqual(dest.read_bytes(), golden)


if __name__ == "__main__":
    unittest.main()
