"""Independent release-archive member authority and deterministic metadata."""
import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from scripts.build_sublime_package import build, verify, ROOT, FILES


class ReleaseOrderIdentity(unittest.TestCase):
    def test_deterministic_rebuild_preserves_member_bytes_order_and_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            first = Path(temp) / "one.sublime-package"
            second = Path(temp) / "two.sublime-package"
            digest_first = build(first)
            digest_second = build(second)
            self.assertEqual(digest_first,digest_second)
            self.assertEqual(digest_first,hashlib.sha256(first.read_bytes()).hexdigest())
            self.assertEqual(first.read_bytes(),second.read_bytes())
            for path in (first,second):
                verify(path)
                with zipfile.ZipFile(path) as archive:
                    self.assertEqual(archive.namelist(),sorted(FILES))
                    for info in archive.infolist():
                        with self.subTest(path=path.name,member=info.filename):
                            self.assertEqual(info.date_time,(1980,1,1,0,0,0))
                            self.assertEqual(info.create_system,3)
                            self.assertEqual(info.external_attr >> 16,0o100644)
                            self.assertEqual(info.compress_type,zipfile.ZIP_DEFLATED)
                            self.assertEqual(archive.read(info.filename),
                                             (ROOT / info.filename).read_bytes())

    def test_duplicate_member_injection_fails_even_if_exact_source_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"release.sublime-package"
            build(path)
            with self.assertWarns(UserWarning):
                with zipfile.ZipFile(path,"a") as archive:
                    archive.writestr("oreslang.py",(ROOT / "oreslang.py").read_bytes())
            with self.assertRaisesRegex(ValueError,"unexpected, missing or duplicate"):
                verify(path)
            build(path)
            verify(path)


if __name__ == "__main__":
    unittest.main()
