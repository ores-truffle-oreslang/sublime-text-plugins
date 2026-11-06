"""Package manifest must be fully trusted before touching any existing output.

Tests exercise the actual source-owned ZIP packager, not a guest compiler.
"""
import tempfile
import unittest
from pathlib import Path

from tools import package_sublime as publisher


class ManifestPreflightAtomicity(unittest.TestCase):
    def test_wrong_keys_and_value_types_leave_foreign_output_untouched(self):
        reviewed = publisher.package_files()
        member = publisher.MEMBERS[0]
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "dist" / "Oreslang.sublime-package"
            dest.parent.mkdir()
            foreign = b"caller-owned archive placeholder\x00\xff\n"
            dest.write_bytes(foreign)

            class BytesSubclass(bytes):
                pass

            cases = []
            missing = reviewed.copy()
            missing.pop(member)
            cases.append(("missing", missing))
            extra = reviewed.copy()
            extra["foreign.ores"] = b"bad"
            cases.append(("extra", extra))
            for name, value in (
                ("bytearray", bytearray(reviewed[member])),
                ("memoryview", memoryview(reviewed[member])),
                ("text", reviewed[member].decode("utf-8", "replace")),
                ("subclass", BytesSubclass(reviewed[member])),
                ("none", None),
            ):
                invalid = reviewed.copy()
                invalid[member] = value
                cases.append((name, invalid))

            for label, invalid in cases:
                with self.subTest(case=label):
                    for repeat in range(2):
                        with self.assertRaisesRegex(ValueError, "package members"):
                            publisher.create_package(invalid, dest)
                        self.assertEqual(dest.read_bytes(), foreign)
                        self.assertEqual(dest.stat().st_size, len(foreign))

            publisher.create_package(reviewed, dest)
            publisher.verify_package(reviewed, dest)
            canonical = dest.read_bytes()
            self.assertNotEqual(canonical, foreign)
            for label, invalid in cases:
                with self.subTest(verify=label):
                    with self.assertRaisesRegex(ValueError, "package members"):
                        publisher.verify_package(invalid, dest)
                    self.assertEqual(dest.read_bytes(), canonical)

            publisher.create_package(reviewed, dest)
            publisher.verify_package(reviewed, dest)
            self.assertEqual(dest.read_bytes(), canonical)


if __name__ == "__main__":
    unittest.main()
