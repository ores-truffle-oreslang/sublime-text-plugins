"""Every reviewed Sublime package member must reject symlink source aliases.

Only ephemeral synthetic test files are touched; no guest compiler execution.
"""
import tempfile
import unittest
from pathlib import Path

from tools import package_sublime as publisher


class AllowlistedMemberSymlinkMatrix(unittest.TestCase):
    def test_all_members_reject_external_source_symlink_and_recover(self):
        reviewed = publisher.package_files()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "source"
            root.mkdir()
            external = Path(directory) / "unreviewed-sentinel.txt"
            sentinel = b"foreign bytes must never become package source\n"
            external.write_bytes(sentinel)
            for name in publisher.MEMBERS:
                (root / name).write_bytes(reviewed[name])
            target = Path(directory) / "Oreslang.sublime-package"

            for name in publisher.MEMBERS:
                with self.subTest(member=name):
                    member = root / name
                    before = member.read_bytes()
                    member.unlink()
                    member.symlink_to(external)
                    with self.assertRaisesRegex(ValueError, "symlinked package file"):
                        publisher.package_files(root)
                    self.assertEqual(external.read_bytes(), sentinel)
                    self.assertFalse(target.exists())
                    member.unlink()
                    member.write_bytes(before)
                    self.assertEqual(publisher.package_files(root), reviewed)
                    publisher.create_package(publisher.package_files(root), target)
                    publisher.verify_package(reviewed, target)
                    target.unlink()

            self.assertEqual(external.read_bytes(), sentinel)
            self.assertEqual(publisher.package_files(root), reviewed)


if __name__ == "__main__":
    unittest.main()
