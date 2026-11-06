"""Canonical release verification must bind ZIP metadata, not just member bytes."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts import build_sublime_package as release


class ReleaseMemberMetadataAdmission(unittest.TestCase):
    def test_altered_member_metadata_is_denied_and_exact_rebuild_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            dest = Path(directory) / "Oreslang.sublime-package"
            expected_sha = release.build(dest)
            baseline = dest.read_bytes()
            with zipfile.ZipFile(dest, "r") as original:
                contents = [(name, original.read(name)) for name in sorted(release.FILES)]

            for mutation in ("stored", "member-comment", "member-extra"):
                with self.subTest(mutation=mutation):
                    with zipfile.ZipFile(dest, "w") as archive:
                        for index, (name, data) in enumerate(contents):
                            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                            info.create_system = 3
                            info.external_attr = 0o100644 << 16
                            info.compress_type = zipfile.ZIP_DEFLATED
                            if index == 0 and mutation == "stored":
                                info.compress_type = zipfile.ZIP_STORED
                            elif index == 0 and mutation == "member-comment":
                                info.comment = b"forged-per-member-attestation"
                            elif index == 0 and mutation == "member-extra":
                                info.extra = b"\xfe\xca\x00\x00"
                            archive.writestr(info, data, compress_type=info.compress_type, compresslevel=9)

                    with zipfile.ZipFile(dest, "r") as tampered:
                        self.assertEqual(tampered.namelist(), [name for name, _ in contents])
                        self.assertEqual([tampered.read(name) for name, _ in contents],
                                         [data for _, data in contents])
                    with self.assertRaisesRegex(ValueError, "noncanonical ZIP member metadata"):
                        release.verify(dest)
                    self.assertEqual(release.build(dest), expected_sha)
                    self.assertEqual(dest.read_bytes(), baseline)
                    release.verify(dest)


if __name__ == "__main__":
    unittest.main()
