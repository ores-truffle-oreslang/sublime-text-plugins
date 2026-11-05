"""The release package builder must never replace an allowlisted source file."""
import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts.build_sublime_package import build, verify, ROOT, FILES


class ReleaseSourcePreservationWave600(unittest.TestCase):
    def test_all_source_destinations_fail_without_modifying_source_bytes(self):
        for member in FILES:
            source = ROOT / member
            before = source.read_bytes()
            digest = hashlib.sha256(before).hexdigest()
            with self.subTest(member=member):
                with self.assertRaisesRegex(ValueError, "source file"):
                    build(source)
                self.assertEqual(source.read_bytes(), before)
                self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), digest)

    def test_independent_external_package_still_succeeds(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "release.sublime-package"
            digest = build(out)
            self.assertEqual(digest, hashlib.sha256(out.read_bytes()).hexdigest())
            verify(out)


if __name__ == "__main__":
    unittest.main()
