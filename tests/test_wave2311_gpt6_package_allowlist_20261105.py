"""Host-only Sublime install package authority and deterministic restoration."""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.package_sublime import MEMBERS, create_package, package_files, verify_package


class InstallPackageAllowlist(unittest.TestCase):
    def test_unreviewed_member_rejected_without_changing_reviewed_sources(self):
        files = package_files()
        source_digests = {name: hashlib.sha256(payload).hexdigest() for name, payload in files.items()}
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "Oreslang.sublime-package"
            create_package(files, target)
            verify_package(files, target)
            approved = target.read_bytes()
            with zipfile.ZipFile(target, "a") as archive:
                archive.writestr("tests/unreviewed.ores", b"fnc hidden() {}")
            with self.assertRaisesRegex(ValueError, "unexpected package files"):
                verify_package(files, target)
            create_package(files, target)
            verify_package(files, target)
            self.assertEqual(target.read_bytes(), approved)
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(archive.namelist(), sorted(MEMBERS))
                for name, data in files.items():
                    self.assertEqual(archive.read(name), data)
        self.assertEqual({name: hashlib.sha256(data).hexdigest() for name, data in package_files().items()}, source_digests)


if __name__ == "__main__":
    unittest.main()
