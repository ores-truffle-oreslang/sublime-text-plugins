"""Exercise two publisher symlink output guards against an external sentinel."""
import tempfile
import unittest
from pathlib import Path

from tools.package_sublime import create_package, verify_package, package_files
from scripts.build_sublime_package import build, verify


class ArtifactDestinationSymlinkDenial(unittest.TestCase):
    def test_symlink_outputs_do_not_overwrite_unrelated_target(self):
        files = package_files()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sentinel = root / "trusted-source.txt"
            expected = b"trusted-content-not-an-artifact\n"
            sentinel.write_bytes(expected)
            for mode in ("install", "release"):
                with self.subTest(publisher=mode):
                    destination = root / "Oreslang.sublime-package"
                    if destination.exists() or destination.is_symlink():
                        destination.unlink()
                    destination.symlink_to(sentinel)
                    if mode == "install":
                        with self.assertRaisesRegex(ValueError, "symlinked package destination"):
                            create_package(files, destination)
                    else:
                        with self.assertRaisesRegex(ValueError, "symlinked release destination"):
                            build(destination)
                    self.assertEqual(sentinel.read_bytes(), expected)
                    self.assertTrue(destination.is_symlink())
                    destination.unlink()
                    if mode == "install":
                        create_package(files, destination)
                        verify_package(files, destination)
                    else:
                        self.assertEqual(len(build(destination)), 64)
                        verify(destination)
                    self.assertFalse(destination.is_symlink())
                    self.assertEqual(sentinel.read_bytes(), expected)


if __name__ == "__main__":
    unittest.main()
