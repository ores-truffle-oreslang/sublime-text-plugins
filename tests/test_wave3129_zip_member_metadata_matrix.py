"""The installable Sublime package binds every ZIP metadata field to reviewed policy."""
import tempfile
import unittest
import zipfile
from pathlib import Path
from tools.package_sublime import package_files, create_package, verify_package, MEMBERS


class Wave3129ZipMetadataMatrix(unittest.TestCase):
    def test_canonical_archive_rejects_each_member_metadata_mutation_and_recovers(self):
        files = package_files()
        target = sorted(MEMBERS)[len(MEMBERS) // 2]
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "canonical.sublime-package"
            create_package(files, output)
            verify_package(files, output)
            original = output.read_bytes()
            for mutation in ("foreign-creator", "symlink-mode", "timestamp", "deflate"):
                with self.subTest(mutation=mutation):
                    with zipfile.ZipFile(output, "r") as archive:
                        entries = [(info, archive.read(info.filename))
                                   for info in archive.infolist()]
                    with zipfile.ZipFile(output, "w") as archive:
                        for info, data in entries:
                            if info.filename == target:
                                if mutation == "foreign-creator":
                                    info.create_system = 0
                                elif mutation == "symlink-mode":
                                    info.external_attr = 0o120777 << 16
                                elif mutation == "timestamp":
                                    info.date_time = (2024, 1, 1, 0, 0, 0)
                                elif mutation == "deflate":
                                    info.compress_type = zipfile.ZIP_DEFLATED
                            archive.writestr(info, data)
                    with self.assertRaisesRegex(ValueError, "Package verification failed"):
                        verify_package(files, output)
                    create_package(files, output)
                    verify_package(files, output)
                    self.assertEqual(output.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
