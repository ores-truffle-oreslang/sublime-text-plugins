"""A caller-provided partial expectation is not package verification authority."""
import tempfile
import unittest
from pathlib import Path

from tools.package_sublime import create_package, package_files, verify_package


class CompleteTrustedVerificationManifest(unittest.TestCase):
    def test_missing_extra_and_wrong_type_expectations_fail_before_archive_admission(self):
        trusted = package_files()
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "Oreslang.sublime-package"
            create_package(trusted, archive)
            verify_package(trusted, archive)
            original = archive.read_bytes()

            missing = dict(trusted)
            missing.pop("Main.sublime-menu")
            extra = dict(trusted)
            extra["unexpected.sublime-settings"] = b"unreviewed"
            wrong_type = dict(trusted)
            wrong_type["Main.sublime-menu"] = bytearray(trusted["Main.sublime-menu"])
            for hostile in (missing, extra, wrong_type):
                with self.subTest(keys=sorted(hostile), type=type(hostile.get("Main.sublime-menu")).__name__):
                    with self.assertRaisesRegex(ValueError, "reviewed byte allowlist"):
                        verify_package(hostile, archive)
                    self.assertEqual(archive.read_bytes(), original)
                    verify_package(trusted, archive)
            self.assertEqual(package_files(), trusted)


if __name__ == "__main__":
    unittest.main()
