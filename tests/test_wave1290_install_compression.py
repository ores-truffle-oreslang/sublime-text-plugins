"""Installed Sublime packages must have canonical bytes and ZIP metadata."""
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.package_sublime import (
    FIXED_DATE, MEMBERS, create_package, package_files, verify_package,
)


class InstallableArchiveFormat(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.dest = Path(temporary.name) / "Oreslang.sublime-package"
        self.files = package_files()
        create_package(self.files, self.dest)
        self.original = self.dest.read_bytes()
        verify_package(self.files, self.dest)

    def test_modified_member_compression_and_timestamp_are_rejected(self):
        target = sorted(MEMBERS)[-1]
        for mutation in ("compression", "timestamp"):
            with self.subTest(mutation=mutation):
                with zipfile.ZipFile(self.dest, "w") as archive:
                    for name in sorted(MEMBERS):
                        info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
                        info.compress_type = (
                            zipfile.ZIP_DEFLATED
                            if name == target and mutation == "compression"
                            else zipfile.ZIP_STORED
                        )
                        if name == target and mutation == "timestamp":
                            info.date_time = (2020, 1, 1, 0, 0, 0)
                        archive.writestr(info, self.files[name])
                with self.assertRaisesRegex(ValueError, "Package verification failed"):
                    verify_package(self.files, self.dest)
                create_package(self.files, self.dest)
                verify_package(self.files, self.dest)
                self.assertEqual(self.dest.read_bytes(), self.original)


if __name__ == "__main__":
    unittest.main()
