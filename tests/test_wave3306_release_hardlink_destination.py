"""The release builder must reject a hardlink to any reviewed source."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import build_sublime_package as release


class ReleaseHardlinkDestination(unittest.TestCase):
    def test_hardlinked_source_target_fails_without_mutation_then_recovers(self):
        # Entire fixture is temporary: even a broken publisher cannot truncate
        # the repository's actual source files.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            for name in release.FILES:
                data = b"source.oreslang\n" if name == "Oreslang.sublime-syntax" else (
                    name + "\nrelease fixture contents\n"
                ).encode()
                (root / name).write_bytes(data)
            baseline = {name: (root / name).read_bytes() for name in release.FILES}
            source = root / "Oreslang.sublime-syntax"
            dest = Path(temporary) / "reviewed-release.sublime-package"
            os.link(source, dest)
            with patch.object(release, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "hardlinks a source"):
                    release.build(dest)
                self.assertEqual(source.read_bytes(), baseline["Oreslang.sublime-syntax"])
                self.assertEqual(dest.read_bytes(), baseline["Oreslang.sublime-syntax"])
                dest.unlink()
                digest = release.build(dest)
                self.assertEqual(len(digest), 64)
                release.verify(dest)
                self.assertNotEqual(os.stat(source).st_ino, os.stat(dest).st_ino)
                self.assertEqual(release.build(dest), digest)
            self.assertEqual(
                {name: (root / name).read_bytes() for name in release.FILES},
                baseline,
            )


if __name__ == "__main__":
    unittest.main()
