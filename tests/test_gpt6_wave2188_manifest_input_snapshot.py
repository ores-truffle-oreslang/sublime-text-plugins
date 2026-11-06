"""Install package builder must validate complete byte manifests before overwrite.

Native host package tests only, not AttoLang compiler/AOT evidence.
"""
import tempfile
import unittest
from pathlib import Path

from tools.package_sublime import MEMBERS, package_files, create_package, verify_package


class ManifestSnapshotAndPreflight(unittest.TestCase):
    def test_bad_caller_manifests_do_not_truncate_existing_archive(self):
        source = package_files()
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "Oreslang.sublime-package"
            sentinel = b"previous verified release bytes"
            dest.write_bytes(sentinel)
            missing = dict(source)
            missing.pop(MEMBERS[-1])
            extra = dict(source)
            extra["outside/reviewed.ores"] = b"unexpected"
            wrong_type = dict(source)
            wrong_type[MEMBERS[0]] = bytearray(wrong_type[MEMBERS[0]])
            for candidate in (missing, extra, wrong_type):
                with self.subTest(manifest=list(candidate)), self.assertRaises(ValueError):
                    create_package(candidate, dest)
                self.assertEqual(dest.read_bytes(), sentinel)

    def test_published_zip_is_immutable_when_caller_mutates_source_map(self):
        original = package_files()
        with tempfile.TemporaryDirectory() as temp:
            dest = Path(temp) / "pkg.sublime-package"
            create_package(original, dest)
            verify_package(original, dest)
            canonical = dest.read_bytes()
            mutable = dict(original)
            mutable["oreslang.py"] += b"\n# unreviewed caller mutation\n"
            # A post-publication caller mutation cannot retroactively alter
            # the already emitted immutable ZIP byte snapshot.
            self.assertEqual(dest.read_bytes(), canonical)
            verify_package(original, dest)
            with self.assertRaises(ValueError):
                verify_package(mutable, dest)
            create_package(original, dest)
            verify_package(original, dest)
            self.assertEqual(dest.read_bytes(), canonical)


if __name__ == "__main__":
    unittest.main()
