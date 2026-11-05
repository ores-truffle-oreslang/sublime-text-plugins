"""Release ZIP member ordering is a validated part of the portable artifact.

These host fixtures use source-owned release code, not a native release binary.
"""
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.build_sublime_package import build, verify, FILES


class ReleaseMemberOrderRoundtrip(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.dest = Path(temporary.name) / "Oreslang.sublime-package"
        build(self.dest)
        verify(self.dest)

    def test_reversed_byte_identical_members_cannot_impersonate_canonical_release(self):
        with zipfile.ZipFile(self.dest) as archive:
            entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
        self.assertEqual([info.filename for info, _ in entries], sorted(FILES))
        with zipfile.ZipFile(self.dest, "w") as archive:
            for info, contents in reversed(entries):
                archive.writestr(info, contents)
        with self.assertRaisesRegex(ValueError, "unexpected, missing or duplicate"):
            verify(self.dest)
        build(self.dest)
        verify(self.dest)
        with zipfile.ZipFile(self.dest) as archive:
            self.assertEqual(archive.namelist(), sorted(FILES))

    def test_rebuild_after_last_member_corruption_restores_verified_archive(self):
        original = self.dest.read_bytes()
        with zipfile.ZipFile(self.dest) as archive:
            entries = [(info, archive.read(info.filename)) for info in archive.infolist()]
        with zipfile.ZipFile(self.dest, "w") as archive:
            for info, contents in entries:
                if info.filename == sorted(FILES)[-1]:
                    contents += b"\n# wave911 unreviewed content\n"
                archive.writestr(info, contents)
        with self.assertRaisesRegex(ValueError, "differs from source"):
            verify(self.dest)
        build(self.dest)
        self.assertEqual(self.dest.read_bytes(), original)
        verify(self.dest)


if __name__ == "__main__":
    unittest.main()
