"""Fail-closed installed Sublime package manifest and no-clobber contracts.

Source-owned Python host tests, not AttoLang guest compiler evidence.
"""
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("gpt6_wave8614_installed_pkg", ROOT / "tools/package_sublime.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class ReviewedPackageManifestPreflight(unittest.TestCase):
    def test_invalid_manifests_preserve_prior_artifact_and_valid_rebuild(self):
        files = package.package_files()
        self.assertEqual(set(files), set(package.MEMBERS))
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "installed archive with spaces.sublime-package"
            sentinel = b"prior verified package must stay intact\n"
            dest.write_bytes(sentinel)
            bad = []
            missing = dict(files)
            missing.pop(next(iter(files)))
            bad.append(missing)
            extra = dict(files)
            extra["unreviewed.py"] = b"forged source"
            bad.append(extra)
            member = next(iter(files))
            for wrong in (bytearray(files[member]), memoryview(files[member]), str(files[member])):
                changed = dict(files)
                changed[member] = wrong
                bad.append(changed)
            for manifest in bad:
                with self.subTest(manifest=sorted(manifest), type=type(manifest.get(member)).__name__):
                    with self.assertRaisesRegex(ValueError, "reviewed byte allowlist"):
                        package.create_package(manifest, dest)
                    self.assertEqual(dest.read_bytes(), sentinel)
                    with self.assertRaisesRegex(ValueError, "reviewed byte allowlist"):
                        package.verify_package(manifest, dest)
                    self.assertEqual(dest.read_bytes(), sentinel)

            package.create_package(files, dest)
            package.verify_package(files, dest)
            first = dest.read_bytes()
            self.assertNotEqual(first, sentinel)
            package.create_package(files, dest)
            package.verify_package(files, dest)
            self.assertEqual(dest.read_bytes(), first)
