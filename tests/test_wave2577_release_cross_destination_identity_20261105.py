"""Real release packager cross-destination integrity and independent recovery.

Host-only ZIP evidence: no editor host or native compiler is executed.
"""
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.build_sublime_package import FILES, ROOT, build, verify


class CrossDestinationReleaseIdentity(unittest.TestCase):
    def test_unicode_nested_destination_is_byte_identical_and_tamper_local(self):
        with tempfile.TemporaryDirectory(prefix="atto-release-") as folder:
            base = Path(folder)
            first = base / "nested" / "日本語" / "release-one.zip"
            second = base / "different" / "release-two.zip"
            digest_one = build(first)
            digest_two = build(second)
            self.assertEqual(digest_one, digest_two)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            verify(first)
            verify(second)

            source_name = sorted(FILES)[0]
            source_before = (ROOT / source_name).read_bytes()
            with zipfile.ZipFile(second) as archive:
                original_entries = [(entry, archive.read(entry.filename))
                                    for entry in archive.infolist()]
            with zipfile.ZipFile(second, "w") as archive:
                for entry, contents in original_entries:
                    if entry.filename == source_name:
                        contents += b"\nUNREVIEWED_PAYLOAD\n"
                    archive.writestr(entry, contents)
            with self.assertRaisesRegex(ValueError, "differs from source"):
                verify(second)
            verify(first)
            self.assertEqual((ROOT / source_name).read_bytes(), source_before)
            self.assertEqual(build(second), digest_one)
            verify(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())


if __name__ == "__main__":
    unittest.main()
