"""Cross-builder snapshot tampering must never become authoritative source identity.

Host package-pipeline checks only; no editor/guest/compiler proof.
"""
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts import build_sublime_package as release
from tools import package_sublime as install


class CrossPublisherSnapshotDivergence(unittest.TestCase):
    def test_changed_install_snapshot_cannot_masquerade_as_release_source_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            release_zip = root / "release.sublime-package"
            install_zip = root / "install.sublime-package"
            snapshot = install.package_files()
            original = snapshot["Main.sublime-menu"]
            canonical = release.build(release_zip)
            release.verify(release_zip)
            install.create_package(snapshot, install_zip)
            install.verify_package(snapshot, install_zip)
            original_install_bytes = install_zip.read_bytes()

            # An internal publisher can produce a self-consistent package from an
            # untrusted snapshot: success with *that snapshot* is not proof of
            # equality to reviewed source bytes or the independent release.
            hostile_snapshot = dict(snapshot)
            hostile_snapshot["Main.sublime-menu"] = original + b"\nWAVE610-UNTRUSTED\n"
            install.create_package(hostile_snapshot, install_zip)
            install.verify_package(hostile_snapshot, install_zip)
            with self.assertRaisesRegex(ValueError, "verification failed"):
                install.verify_package(snapshot, install_zip)
            with zipfile.ZipFile(install_zip) as installer, zipfile.ZipFile(release_zip) as source:
                self.assertNotEqual(
                    installer.read("Main.sublime-menu"),
                    source.read("Main.sublime-menu"),
                )
                self.assertEqual(source.read("Main.sublime-menu"), original)
            release.verify(release_zip)
            self.assertEqual(canonical, release.build(release_zip))
            self.assertEqual(install.package_files()["Main.sublime-menu"], original)

            # Rebuild with the true captured source to prove recovery is clean.
            install.create_package(snapshot, install_zip)
            install.verify_package(snapshot, install_zip)
            self.assertEqual(install_zip.read_bytes(), original_install_bytes)


if __name__ == "__main__":
    unittest.main()
