"""Source allowlist, symlink denial, and archive tamper/restoration host tests."""
import os
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.package_sublime import MEMBERS, ROOT, create_package, package_files, verify_package


class PackageInventoryAdmission(unittest.TestCase):
    def test_extra_unreviewed_files_stay_out_and_symlinked_source_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            for member in MEMBERS:
                (folder / member).write_bytes((ROOT / member).read_bytes())
            (folder / "private.key").write_text("must never package", encoding="utf-8")
            files = package_files(folder)
            self.assertEqual(set(files), set(MEMBERS))
            output = folder / "out.sublime-package"
            create_package(files, output)
            verify_package(files, output)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.namelist(), sorted(MEMBERS))
                self.assertNotIn("private.key", archive.namelist())
            if not hasattr(os, "symlink"):
                return
            source = folder / "Oreslang.sublime-syntax"
            source.unlink()
            try:
                source.symlink_to(folder / "private.key")
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable on this host")
            with self.assertRaisesRegex(ValueError, "symlinked package file"):
                package_files(folder)
            source.unlink()
            source.write_bytes((ROOT / source.name).read_bytes())
            self.assertEqual(package_files(folder), files)
            verify_package(files, output)

    def test_late_archive_payload_tampering_is_rejected_then_restored(self):
        files = package_files()
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "out.sublime-package"
            create_package(files, output)
            verify_package(files, output)
            changed = dict(files)
            target = sorted(MEMBERS)[-1]
            changed[target] += b"\n# injected payload\n"
            # Create a structurally normal archive with a corrupted source member.
            create_package(changed, output)
            with self.assertRaisesRegex(ValueError, "Package verification failed"):
                verify_package(files, output)
            create_package(files, output)
            verify_package(files, output)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read(target), files[target])


if __name__ == "__main__":
    unittest.main()
