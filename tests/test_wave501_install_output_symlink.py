"""Installable Sublime package writer must preserve unrelated and source bytes."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import tools.package_sublime as package


class InstallableOutputDestinationTrust(unittest.TestCase):
    def test_symlink_target_and_source_member_are_never_overwritten(self):
        files = package.package_files()
        with tempfile.TemporaryDirectory() as dirname:
            root = Path(dirname)
            sentinel = root / "sentinel.txt"
            sentinel.write_bytes(b"prior content must survive\n")
            alias = root / "alias.sublime-package"
            try:
                alias.symlink_to(sentinel)
            except (NotImplementedError, OSError):
                self.skipTest("symlinks unavailable")

            with self.assertRaisesRegex(ValueError, "symlinked package destination"):
                package.create_package(files, alias)
            self.assertEqual(sentinel.read_bytes(), b"prior content must survive\n")
            self.assertTrue(alias.is_symlink())

            faux_member = root / "oreslang.py"
            faux_member.write_bytes(b"reviewed plugin bytes\n")
            with patch.object(package, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "replace a source file"):
                    package.create_package(files, faux_member)
            self.assertEqual(faux_member.read_bytes(), b"reviewed plugin bytes\n")

            safe = root / "safe.sublime-package"
            package.create_package(files, safe)
            package.verify_package(files, safe)


if __name__ == "__main__":
    unittest.main()
