"""Canonical Sublime packages admit no hidden ZIP comment or extra metadata."""
import copy
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "package_sublime.py"
spec = importlib.util.spec_from_file_location("wave2032_zip_metadata", SCRIPT)
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


class ZipMetadataAdmission(unittest.TestCase):
    def test_archive_and_member_metadata_cannot_hide_unreviewed_bytes(self):
        files = packager.package_files()
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "Oreslang.sublime-package"
            packager.create_package(files, target)
            clean = target.read_bytes()
            packager.verify_package(files, target)

            for mutation in ("archive-comment", "member-comment", "member-extra"):
                with self.subTest(mutation=mutation):
                    with zipfile.ZipFile(target, "r") as original:
                        items = [(copy.copy(info), original.read(info.filename))
                                 for info in original.infolist()]
                    with zipfile.ZipFile(target, "w") as changed:
                        for info, payload in items:
                            if info.filename == "Oreslang.sublime-syntax":
                                if mutation == "member-comment":
                                    info.comment = b"unreviewed-member-note"
                                elif mutation == "member-extra":
                                    info.extra = b"\xfe\xca\x00\x00"  # custom field, zero length
                            changed.writestr(info, payload)
                        if mutation == "archive-comment":
                            changed.comment = b"unreviewed-archive-note"

                    with self.assertRaisesRegex(ValueError, "Package verification failed"):
                        packager.verify_package(files, target)

                    packager.create_package(files, target)
                    self.assertEqual(target.read_bytes(), clean)
                    packager.verify_package(files, target)


if __name__ == "__main__":
    unittest.main()
