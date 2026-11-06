"""Canonical installed ZIP metadata must not be forgable even with identical source bytes."""
import tempfile
import unittest
import zipfile
from pathlib import Path
from tools.package_sublime import create_package, package_files, verify_package


class Wave2632InstallMetadataMatrix(unittest.TestCase):
    def test_payload_identical_but_metadata_tampered_is_rejected_and_restored(self):
        files = package_files()
        targeted = "oreslang.py"
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "Oreslang.sublime-package"
            create_package(files, dest)
            reference = dest.read_bytes()
            for mutation in ("timestamp", "creator", "mode", "compression"):
                with self.subTest(mutation=mutation):
                    with zipfile.ZipFile(dest, "w") as archive:
                        for name in sorted(files):
                            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                            info.create_system = 3
                            info.external_attr = 0o100644 << 16
                            info.compress_type = zipfile.ZIP_STORED
                            if name == targeted:
                                if mutation == "timestamp":
                                    info.date_time = (1981, 1, 1, 0, 0, 0)
                                elif mutation == "creator":
                                    info.create_system = 0
                                elif mutation == "mode":
                                    info.external_attr = 0o120777 << 16
                                else:
                                    info.compress_type = zipfile.ZIP_DEFLATED
                            archive.writestr(info, files[name])
                    with self.assertRaisesRegex(ValueError, "verification failed"):
                        verify_package(files, dest)
                    create_package(files, dest)
                    self.assertEqual(dest.read_bytes(), reference)
                    verify_package(files, dest)


if __name__ == "__main__":
    unittest.main()
