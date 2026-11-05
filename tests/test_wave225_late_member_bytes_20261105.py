"""Sublime release verifier must check the final allowlisted payload, not just names."""
import tempfile
import unittest
import zipfile
from pathlib import Path

from scripts.build_sublime_package import FILES, build, verify


class FinalMemberBytesTest(unittest.TestCase):
    def test_final_allowlisted_payload_is_verified_and_rebuild_recovers(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "Oreslang.sublime-package"
            original_digest = build(output)
            last_name = sorted(FILES)[-1]
            with zipfile.ZipFile(output, "r") as archive:
                members = [(entry, archive.read(entry.filename))
                           for entry in archive.infolist()]
            with zipfile.ZipFile(output, "w") as archive:
                for entry, payload in members:
                    if entry.filename == last_name:
                        payload += b"\n# hostile append not present in trusted source\n"
                    archive.writestr(entry, payload)
            with self.assertRaisesRegex(ValueError, "differs from source"):
                verify(output)
            self.assertEqual(build(output), original_digest)
            verify(output)


if __name__ == "__main__":
    unittest.main()
