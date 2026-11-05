"""Source-owned package-member symlink denial and recovery tests."""
import tempfile
import unittest
from pathlib import Path

from tools.package_sublime import MEMBERS, ROOT, package_files


class SourceMemberSymlinkTests(unittest.TestCase):
    def test_each_source_member_symlink_is_refused_and_real_file_recovers(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "package"
            root.mkdir()
            for name in MEMBERS:
                (root / name).write_bytes((ROOT / name).read_bytes())
            baseline = package_files(root)
            self.assertEqual(set(baseline), set(MEMBERS))
            sentinel = Path(folder) / "external-sentinel"
            sentinel.write_bytes(b"external content must remain intact")
            for name in MEMBERS:
                with self.subTest(member=name):
                    member = root / name
                    original = member.read_bytes()
                    member.unlink()
                    member.symlink_to(sentinel)
                    with self.assertRaisesRegex(ValueError, "symlinked package file"):
                        package_files(root)
                    self.assertEqual(sentinel.read_bytes(), b"external content must remain intact")
                    member.unlink()
                    member.write_bytes(original)
                    self.assertEqual(package_files(root), baseline)


if __name__ == "__main__":
    unittest.main()
