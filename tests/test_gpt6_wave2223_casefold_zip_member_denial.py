"""Reject ZIP members that visually masquerade as allowed package paths.

Exercises both real host publishers/verifiers; no guest compilation.
"""
import copy
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts import build_sublime_package as release
from tools import package_sublime as installed


class CasefoldAndConfusableMemberDenial(unittest.TestCase):
    def test_both_formats_deny_casefold_and_unicode_member_spoofing(self):
        inputs = installed.package_files()
        with tempfile.TemporaryDirectory(prefix="ores-zip-names-") as tmp:
            parent = Path(tmp)
            implementations = [
                ("installed", lambda path: installed.create_package(inputs, path),
                 lambda path: installed.verify_package(inputs, path)),
                ("release", release.build, release.verify),
            ]
            for label, build, verify in implementations:
                path = parent / (label + ".sublime-package")
                build(path)
                verify(path)
                original = path.read_bytes()
                for target, renamed in [
                    ("Oreslang.sublime-settings", "oreslang.sublime-settings"),
                    ("Oreslang.sublime-syntax", "Oreslang.sublime\u2010syntax"),
                ]:
                    with self.subTest(publisher=label, target=target, impostor=renamed):
                        with zipfile.ZipFile(path) as archive:
                            entries = [(copy.copy(info), archive.read(info.filename))
                                       for info in archive.infolist()]
                        with zipfile.ZipFile(path, "w") as archive:
                            for info, content in entries:
                                if info.filename == target:
                                    info.filename = renamed
                                archive.writestr(info, content)
                        with self.assertRaisesRegex(ValueError, "unexpected|Archive contains"):
                            verify(path)
                        build(path)
                        verify(path)
                        self.assertEqual(path.read_bytes(), original,
                                         "verified rebuild must recover original bytes")


if __name__ == "__main__":
    unittest.main()
