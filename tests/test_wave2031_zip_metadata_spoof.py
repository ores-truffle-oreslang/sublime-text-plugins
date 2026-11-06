"""Even same-byte ZIP members cannot smuggle extra records or comments.

Focused host-side package verifier negatives with deterministic restoration.
"""
import copy
import hashlib
import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "package_sublime.py"
spec = importlib.util.spec_from_file_location("wave2031_package", SCRIPT)
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class ZIPMetadataSpoof(unittest.TestCase):
    def test_extra_member_comment_and_archive_comment_rejected_then_restored(self):
        files = package.package_files()
        with tempfile.TemporaryDirectory() as dirname:
            dest = Path(dirname) / "Oreslang.sublime-package"
            package.create_package(files, dest)
            package.verify_package(files, dest)
            original_digest = hashlib.sha256(dest.read_bytes()).hexdigest()
            for mutation in ("extra", "member-comment", "archive-comment"):
                with self.subTest(mutation=mutation):
                    package.create_package(files, dest)
                    with zipfile.ZipFile(dest, "r") as source:
                        entries = [(copy.copy(info), source.read(info.filename))
                                   for info in source.infolist()]
                    with zipfile.ZipFile(dest, "w") as output:
                        for index, (info, payload) in enumerate(entries):
                            if index == 0 and mutation == "extra":
                                info.extra = b"\xab\xcd\x04\x00test"
                            if index == 0 and mutation == "member-comment":
                                info.comment = b"unreviewed metadata"
                            output.writestr(info, payload)
                        if mutation == "archive-comment":
                            output.comment = b"unreviewed archive comment"

                    with self.assertRaisesRegex(ValueError, "Package verification failed"):
                        package.verify_package(files, dest)
                    package.create_package(files, dest)
                    package.verify_package(files, dest)
                    self.assertEqual(hashlib.sha256(dest.read_bytes()).hexdigest(),
                                     original_digest)


if __name__ == "__main__":
    unittest.main()
