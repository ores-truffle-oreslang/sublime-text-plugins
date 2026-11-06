"""Verify each ZIP metadata field is bound to the reviewed canonical package contract.

This exercises the actual source-owned packager; it is not an AttoLang compiler test.
"""
import tempfile
import unittest
import zipfile
from pathlib import Path
from tools import package_sublime as publisher


class CanonicalMetadataMatrix(unittest.TestCase):
    def test_each_metadata_mutation_is_detected_then_recovers_canonical_bytes(self):
        reviewed = publisher.package_files()
        target_member = publisher.MEMBERS[0]
        cases = ("date", "mode", "platform", "extra", "comment", "compression")
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "Oreslang.sublime-package"
            publisher.create_package(reviewed, archive_path)
            publisher.verify_package(reviewed, archive_path)
            canonical = archive_path.read_bytes()
            for change in cases:
                with self.subTest(change=change):
                    with zipfile.ZipFile(archive_path, "w") as archive:
                        for name in sorted(reviewed):
                            info = zipfile.ZipInfo(name, date_time=publisher.FIXED_DATE)
                            info.create_system = 3
                            info.external_attr = 0o100644 << 16
                            info.compress_type = zipfile.ZIP_STORED
                            if name == target_member:
                                if change == "date":
                                    info.date_time = (1982, 1, 1, 0, 0, 0)
                                elif change == "mode":
                                    info.external_attr = 0o100600 << 16
                                elif change == "platform":
                                    info.create_system = 0
                                elif change == "extra":
                                    info.extra = b"NO\x00\x00"
                                elif change == "comment":
                                    info.comment = b"unreviewed metadata"
                                elif change == "compression":
                                    info.compress_type = zipfile.ZIP_DEFLATED
                            archive.writestr(info, reviewed[name])
                    self.assertNotEqual(archive_path.read_bytes(), canonical)
                    with self.assertRaisesRegex(ValueError, "Package verification failed"):
                        publisher.verify_package(reviewed, archive_path)
                    publisher.create_package(reviewed, archive_path)
                    publisher.verify_package(reviewed, archive_path)
                    self.assertEqual(archive_path.read_bytes(), canonical)

    def test_global_comment_alone_cannot_certify_archive(self):
        reviewed = publisher.package_files()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Oreslang.sublime-package"
            publisher.create_package(reviewed, path)
            original = path.read_bytes()
            with zipfile.ZipFile(path, "a") as archive:
                archive.comment = b"unreviewed suffix"
            with self.assertRaisesRegex(ValueError, "Package verification failed"):
                publisher.verify_package(reviewed, path)
            publisher.create_package(reviewed, path)
            publisher.verify_package(reviewed, path)
            self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
