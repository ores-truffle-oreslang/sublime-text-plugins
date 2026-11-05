"""Source-owned release verifier must reject altered ZIP member timestamps."""
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.build_sublime_package import build, verify, FILES


class ReleaseTimestampIntegrity(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.dest = Path(temporary.name) / "Oreslang.sublime-package"
        self.digest = build(self.dest)
        self.original = self.dest.read_bytes()

    def test_first_and_last_member_timestamp_mutations_fail_closed(self):
        for target in (sorted(FILES)[0], sorted(FILES)[-1]):
            with self.subTest(target=target):
                with zipfile.ZipFile(self.dest) as archive:
                    entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
                with zipfile.ZipFile(self.dest, "w") as archive:
                    for info, contents in entries:
                        if info.filename == target:
                            info.date_time = (2024, 1, 1, 0, 0, 0)
                        archive.writestr(info, contents)
                with self.assertRaisesRegex(ValueError, "nonreproducible archive timestamp"):
                    verify(self.dest)
                self.assertEqual(build(self.dest), self.digest)
                self.assertEqual(self.dest.read_bytes(), self.original)
                verify(self.dest)


if __name__ == "__main__":
    unittest.main()
