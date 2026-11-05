"""Reject forged release member authority and recover canonical archive bytes."""
import tempfile
import unittest
import zipfile
from pathlib import Path
from scripts.build_sublime_package import build, verify, FILES


class ReleaseMemberModeTamper(unittest.TestCase):
    def test_mid_member_platform_and_file_type_tamper_is_rejected_then_recovered(self):
        with tempfile.TemporaryDirectory() as folder:
            archive_path = Path(folder) / "Oreslang.sublime-package"
            pristine_digest = build(archive_path)
            pristine_bytes = archive_path.read_bytes()
            mid = sorted(FILES)[len(FILES) // 2]
            for name, altered_system, altered_mode in (
                ("windows-origin", 0, 0o100644),
                ("symlink-type", 3, 0o120777),
                ("world-writable", 3, 0o100666),
            ):
                with self.subTest(variant=name):
                    with zipfile.ZipFile(archive_path, "r") as source:
                        entries = [(info, source.read(info.filename))
                                   for info in source.infolist()]
                    with zipfile.ZipFile(archive_path, "w") as replacement:
                        for info, payload in entries:
                            if info.filename == mid:
                                info.create_system = altered_system
                                info.external_attr = altered_mode << 16
                            replacement.writestr(info, payload)
                    with self.assertRaisesRegex(ValueError, "nonportable archive file mode"):
                        verify(archive_path)
                    self.assertEqual(build(archive_path), pristine_digest)
                    self.assertEqual(archive_path.read_bytes(), pristine_bytes)
                    verify(archive_path)


if __name__ == "__main__":
    unittest.main()
