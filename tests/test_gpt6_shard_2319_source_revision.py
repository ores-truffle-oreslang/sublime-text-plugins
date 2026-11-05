"""Archive evidence follows real source changes and returns to the original digest."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_sublime_package as release


class SourceRevisionIdentityTest(unittest.TestCase):
    def test_source_edit_invalidates_existing_release_then_recovers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "isolated-source"
            root.mkdir()
            for name in release.FILES:
                (root / name).write_bytes((release.ROOT / name).read_bytes())
            destination = Path(directory) / "artifacts" / "Oreslang.sublime-package"
            with patch.object(release, "ROOT", root):
                pristine_digest = release.build(destination)
                pristine_bytes = destination.read_bytes()
                source = root / "Main.sublime-menu"
                original = source.read_bytes()
                source.write_bytes(original + b"\n")
                with self.assertRaisesRegex(ValueError, "archive differs from source"):
                    release.verify(destination)
                changed_digest = release.build(destination)
                release.verify(destination)
                self.assertNotEqual(changed_digest, pristine_digest)
                self.assertNotEqual(destination.read_bytes(), pristine_bytes)
                source.write_bytes(original)
                restored_digest = release.build(destination)
                release.verify(destination)
                self.assertEqual(restored_digest, pristine_digest)
                self.assertEqual(destination.read_bytes(), pristine_bytes)


if __name__ == "__main__":
    unittest.main()
