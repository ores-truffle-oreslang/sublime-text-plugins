"""The installed Sublime ZIP manifest binds bytes and metadata across rebuilds."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools import package_sublime as package


class InstalledArchiveMetadataTest(unittest.TestCase):
    def test_manifest_permutation_and_adversarial_zip_comments(self):
        items = package.package_files()
        self.assertEqual(set(items), set(package.MEMBERS))
        with tempfile.TemporaryDirectory(prefix="atto-zip-2140-") as folder:
            root = Path(folder)
            reference = root / "approved.sublime-package"
            shuffled = root / "reordered.sublime-package"
            corrupted = root / "forged.sublime-package"

            package.create_package(items, reference)
            package.create_package(dict(reversed(list(items.items()))), shuffled)
            pristine = reference.read_bytes()
            self.assertEqual(shuffled.read_bytes(), pristine,
                             "source manifest insertion order must not change ZIP bytes")
            package.verify_package(items, reference)
            package.verify_package(items, shuffled)

            # ZIP permits global comments without changing a single member.
            with zipfile.ZipFile(shuffled, "a") as archive:
                archive.comment = b"forged-approval-sha256=" + b"0" * 64
            with self.assertRaisesRegex(ValueError, "unexpected archive comment"):
                package.verify_package(items, shuffled)
            self.assertEqual(reference.read_bytes(), pristine)

            # Per-member ZIP comments can also contain false attestations.
            with zipfile.ZipFile(corrupted, "w") as archive:
                for name in sorted(items):
                    info = zipfile.ZipInfo(name, package.FIXED_DATE)
                    info.compress_type = zipfile.ZIP_STORED
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    if name == "oreslang.py":
                        info.comment = b"unreviewed-metadata"
                    archive.writestr(info, items[name])
            with self.assertRaisesRegex(ValueError, "Package verification failed"):
                package.verify_package(items, corrupted)

            package.create_package(items, shuffled)
            package.verify_package(items, shuffled)
            self.assertEqual(shuffled.read_bytes(), pristine,
                             "clean regeneration must restore byte-for-byte canonical ZIP")
            self.assertEqual(reference.read_bytes(), pristine)


if __name__ == "__main__":
    unittest.main()
