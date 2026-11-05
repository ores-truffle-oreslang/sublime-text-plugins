"""Host-only immutable release-source admission; no editor/guest execution proof."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_sublime_package as publisher


class ReleaseInputIdentity(unittest.TestCase):
    def test_byte_identical_external_symlink_is_denied_then_restored(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work) / "source"
            root.mkdir()
            for name in publisher.FILES:
                (root / name).write_bytes((publisher.ROOT / name).read_bytes())
            target = root / "oreslang.py"
            original = target.read_bytes()
            outside = Path(work) / "outside.py"
            outside.write_bytes(original)
            output = Path(work) / "release.sublime-package"

            # Only module-local ROOT changes; no real checkout or shared source is edited.
            with patch.object(publisher, "ROOT", root):
                digest = publisher.build(output)
                publisher.verify(output)
                self.assertEqual(len(digest), 64)
                target.unlink()
                target.symlink_to(outside)
                with self.assertRaisesRegex(ValueError, "symlinked required release file"):
                    publisher.build(output)
                self.assertEqual(outside.read_bytes(), original)
                target.unlink()
                target.write_bytes(original)
                self.assertEqual(publisher.build(output), digest)
                publisher.verify(output)


if __name__ == "__main__":
    unittest.main()
