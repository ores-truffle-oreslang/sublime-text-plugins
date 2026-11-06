"""Required package inputs must be regular source files, not symlink aliases."""
import tempfile
import unittest
from pathlib import Path
from tools.package_sublime import (
    ROOT, MEMBERS, package_files, create_package, verify_package,
)


class ReviewedSourceAdmission(unittest.TestCase):
    def test_identical_symlink_bytes_never_acquire_source_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            source_root = Path(tmp) / "candidate"
            source_root.mkdir()
            originals = {}
            for name in MEMBERS:
                data = (ROOT / name).read_bytes()
                (source_root / name).write_bytes(data)
                originals[name] = data

            self.assertEqual(package_files(source_root), originals)
            for index, name in enumerate((MEMBERS[0], "oreslang.py", MEMBERS[-1])):
                with self.subTest(member=name):
                    reviewed_path = source_root / name
                    external = Path(tmp) / f"external-{index}.source"
                    external.write_bytes(originals[name])
                    reviewed_path.unlink()
                    reviewed_path.symlink_to(external)

                    # Identical content is not sufficient to confer trusted
                    # source-file identity on a symlink.
                    with self.assertRaisesRegex(ValueError, "Missing or symlinked package file"):
                        package_files(source_root)
                    self.assertEqual(external.read_bytes(), originals[name])

                    reviewed_path.unlink()
                    reviewed_path.write_bytes(originals[name])
                    self.assertEqual(package_files(source_root), originals)

            output = Path(tmp) / "Oreslang.sublime-package"
            create_package(package_files(source_root), output)
            verify_package(originals, output)
            self.assertEqual(set(MEMBERS), set(originals))


if __name__ == "__main__":
    unittest.main()
