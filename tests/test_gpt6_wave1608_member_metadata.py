"""A package member's metadata is part of the release identity.

Source-owned Python packaging tests; no native editor/guest execution claim.
"""
import tempfile
import unittest
from pathlib import Path
import zipfile

from tools import package_sublime as publisher


class Gpt6Wave1608MemberMetadata(unittest.TestCase):
    def test_each_member_rejects_forged_modes_extra_and_comment_then_recovers(self):
        members = publisher.package_files()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Oreslang.sublime-package"
            publisher.create_package(members, path)
            publisher.verify_package(members, path)
            canonical = path.read_bytes()

            for victim in sorted(members):
                for mutation in ("world_writable", "extra", "comment"):
                    with self.subTest(member=victim, mutation=mutation):
                        with zipfile.ZipFile(path, "w") as archive:
                            for name in sorted(members):
                                info = zipfile.ZipInfo(name, date_time=publisher.FIXED_DATE)
                                info.create_system = 3
                                info.external_attr = 0o100644 << 16
                                info.compress_type = zipfile.ZIP_STORED
                                if name == victim:
                                    if mutation == "world_writable":
                                        info.external_attr = 0o100666 << 16
                                    elif mutation == "extra":
                                        info.extra = b"\x99\x99\x00\x00"
                                    else:
                                        info.comment = b"untrusted release annotation"
                                archive.writestr(info, members[name])
                        with self.assertRaisesRegex(ValueError, "Package verification failed"):
                            publisher.verify_package(members, path)
                        publisher.create_package(members, path)
                        publisher.verify_package(members, path)
                        self.assertEqual(path.read_bytes(), canonical)


if __name__ == "__main__":
    unittest.main()
