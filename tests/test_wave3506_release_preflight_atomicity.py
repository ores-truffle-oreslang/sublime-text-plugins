"""Ensure source preflight failures cannot damage an existing release ZIP.

Host-only packaging integration regression; no compiler guest execution.
"""
import pathlib
import tempfile
import unittest

from scripts import build_sublime_package as release


class ReleaseSourcePreflightAtomicity(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="atto-release-3506-")
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name) / "source"
        self.root.mkdir()
        self.previous_root = release.ROOT
        release.ROOT = self.root
        self.addCleanup(setattr, release, "ROOT", self.previous_root)
        for name in release.FILES:
            payload = (f"canonical {name}\n").encode("utf-8")
            if name == "Oreslang.sublime-syntax":
                payload += b"scope: source.oreslang\n"
            (self.root / name).write_bytes(payload)

    def test_missing_later_member_preserves_existing_and_uncreated_destinations(self):
        destination = self.root / "build" / "release.zip"
        checksum = release.build(destination)
        original = destination.read_bytes()
        source = self.root / "oreslang.py"
        original_source = source.read_bytes()
        source.unlink()
        new_destination = self.root / "new-location" / "release.zip"

        for output in (destination, new_destination):
            with self.subTest(output=output):
                with self.assertRaisesRegex(ValueError, "missing or symlinked required release file"):
                    release.build(output)
        self.assertEqual(destination.read_bytes(), original)
        self.assertFalse(new_destination.exists())
        self.assertFalse(new_destination.parent.exists(),
                         "source failure must happen before destination parent creation")

        source.write_bytes(original_source)
        self.assertEqual(release.build(destination), checksum)
        release.verify(destination)
        self.assertEqual(destination.read_bytes(), original)

    def test_symlinked_later_member_cannot_replace_verified_destination(self):
        destination = self.root / "release.zip"
        checksum = release.build(destination)
        baseline = destination.read_bytes()
        source = self.root / "oreslang.py"
        source.unlink()
        external = self.root.parent / "untrusted-payload.py"
        external.write_bytes(b"print('untrusted')\n")
        try:
            source.symlink_to(external)
        except (OSError, NotImplementedError):
            self.skipTest("filesystem does not support symlinks")
        with self.assertRaisesRegex(ValueError, "missing or symlinked required release file"):
            release.build(destination)
        self.assertEqual(destination.read_bytes(), baseline)
        self.assertEqual(external.read_bytes(), b"print('untrusted')\n")
        source.unlink()
        source.write_bytes(b"canonical oreslang.py\n")
        self.assertEqual(release.build(destination), checksum)
        release.verify(destination)
        self.assertEqual(destination.read_bytes(), baseline)


if __name__ == "__main__":
    unittest.main()
