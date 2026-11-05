"""Every allowlisted release member is bound to its exact source bytes."""
import tempfile
import unittest
import zipfile
from pathlib import Path
from scripts.build_sublime_package import build, verify, FILES


class EveryMemberMustMatchSource(unittest.TestCase):
    def test_each_modified_release_payload_is_rejected_and_canonical_rebuild_restores_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "Oreslang.sublime-package"
            expected_digest = build(output)
            original = output.read_bytes()
            for target in sorted(FILES):
                with self.subTest(member=target):
                    with zipfile.ZipFile(output, "r") as source:
                        entries = [(info, source.read(info.filename))
                                   for info in source.infolist()]
                    with zipfile.ZipFile(output, "w") as destination:
                        for info, payload in entries:
                            if info.filename == target:
                                self.assertGreater(len(payload), 0)
                                replacement = (payload[0] ^ 1).to_bytes(1, "big") + payload[1:]
                                self.assertNotEqual(replacement, payload)
                                payload = replacement
                            destination.writestr(info, payload)
                    with self.assertRaisesRegex(ValueError, "archive differs from source"):
                        verify(output)
                    self.assertEqual(build(output), expected_digest)
                    self.assertEqual(output.read_bytes(), original)
                    verify(output)


if __name__ == "__main__":
    unittest.main()
