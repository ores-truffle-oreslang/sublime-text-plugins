"""Source-owned release ZIP integrity across working directories and extra members.

Tests the actual host package builder/verifier, not an AttoLang guest compiler.
"""
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.build_sublime_package import ROOT, FILES, build, verify


class ReleaseDirectoryIndependence(unittest.TestCase):
    def test_identical_release_bytes_from_distinct_working_directories(self):
        with tempfile.TemporaryDirectory() as dirname:
            tmp = Path(dirname)
            first = tmp / "a" / "Oreslang.sublime-package"
            second = tmp / "b" / "Oreslang.sublime-package"
            previous = Path.cwd()
            try:
                (tmp / "a").mkdir(exist_ok=True)
                os.chdir(tmp / "a")
                first_digest = build(first)
                (tmp / "b").mkdir(exist_ok=True)
                os.chdir(tmp / "b")
                second_digest = build(second)
            finally:
                os.chdir(previous)

            self.assertEqual(first_digest, second_digest)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            verify(first)
            verify(second)

            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), sorted(FILES))
                for member in FILES:
                    with self.subTest(member=member):
                        self.assertEqual(archive.read(member), (ROOT / member).read_bytes())

    def test_unlisted_directory_member_does_not_survive_verification_or_rebuild(self):
        with tempfile.TemporaryDirectory() as dirname:
            output = Path(dirname) / "Oreslang.sublime-package"
            original_digest = build(output)
            original = output.read_bytes()
            with zipfile.ZipFile(output, "a") as archive:
                archive.writestr("tests/unreviewed-synthetic-file.py", b"untrusted test bytes\n")
            with self.assertRaisesRegex(ValueError, "unexpected"):
                verify(output)
            self.assertNotEqual(output.read_bytes(), original)
            self.assertEqual(build(output), original_digest)
            self.assertEqual(output.read_bytes(), original)
            verify(output)


if __name__ == "__main__":
    unittest.main()
