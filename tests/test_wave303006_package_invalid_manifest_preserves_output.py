"""Invalid caller-supplied manifests fail before touching a published artifact."""
import tempfile
import unittest
from pathlib import Path

from tools.package_sublime import MEMBERS, create_package, package_files, verify_package


class InvalidManifestTransactionTests(unittest.TestCase):
    def test_bad_manifest_does_not_truncate_existing_file_or_create_new_one(self):
        files = package_files()
        first = sorted(MEMBERS)[0]
        extra = dict(files)
        extra["../not-reviewed"] = b"hostile"
        missing = dict(files)
        del missing[first]
        wrong_type = dict(files)
        wrong_type[first] = "not bytes"
        for name, bad in (
            ("extra", extra), ("missing", missing), ("type", wrong_type),
        ):
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "existing.sublime-package"
                sentinel = b"retained original publication"
                path.write_bytes(sentinel)
                with self.assertRaisesRegex(ValueError, "reviewed byte allowlist"):
                    create_package(bad, path)
                self.assertEqual(path.read_bytes(), sentinel)
                absent = Path(tmp) / "must-not-exist.sublime-package"
                with self.assertRaisesRegex(ValueError, "reviewed byte allowlist"):
                    create_package(bad, absent)
                self.assertFalse(absent.exists())
                create_package(files, path)
                verify_package(files, path)


if __name__ == "__main__":
    unittest.main()
