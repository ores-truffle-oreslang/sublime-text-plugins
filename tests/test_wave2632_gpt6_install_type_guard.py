"""Reject mutable or masquerading member payloads before replacing an installed package."""
import tempfile
import unittest
from pathlib import Path
from tools.package_sublime import create_package, package_files, verify_package


class DerivedBytes(bytes):
    pass


class Wave2632InstallMappingTypeGate(unittest.TestCase):
    def test_invalid_payload_types_preserve_previous_archive_and_rebuild_exactly(self):
        canonical = package_files()
        with tempfile.TemporaryDirectory() as root:
            dest = Path(root) / "Oreslang.sublime-package"
            create_package(canonical, dest)
            reference = dest.read_bytes()
            for replacement in (
                bytearray(canonical["oreslang.py"]),
                memoryview(canonical["oreslang.py"]),
                DerivedBytes(canonical["oreslang.py"]),
                "fake module source",
            ):
                with self.subTest(type=type(replacement).__name__):
                    invalid = dict(canonical)
                    invalid["oreslang.py"] = replacement
                    with self.assertRaisesRegex(ValueError, "reviewed byte allowlist"):
                        create_package(invalid, dest)
                    self.assertEqual(dest.read_bytes(), reference)
                    verify_package(canonical, dest)

            create_package(canonical, dest)
            self.assertEqual(dest.read_bytes(), reference)
            verify_package(canonical, dest)


if __name__ == "__main__":
    unittest.main()
