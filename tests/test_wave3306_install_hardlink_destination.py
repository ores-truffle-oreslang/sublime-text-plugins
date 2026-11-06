"""Hardlinked package destinations may not overwrite a reviewed source inode."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import package_sublime as publisher


class InstallHardlinkDestination(unittest.TestCase):
    def test_existing_hardlink_to_reviewed_source_is_rejected_before_truncation(self):
        # Only temporary synthetic source files are used: a regression cannot
        # corrupt a file in the actual checked-out repository.
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "source"
            root.mkdir()
            payloads = {}
            for name in publisher.MEMBERS:
                value = (name + "\nknown reviewed source bytes\n").encode()
                (root / name).write_bytes(value)
                payloads[name] = value
            source = root / "oreslang.py"
            destination = Path(temporary) / "Oreslang.sublime-package"
            os.link(source, destination)
            baseline = {name: (root / name).read_bytes() for name in publisher.MEMBERS}
            with patch.object(publisher, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "hardlink"):
                    publisher.create_package(payloads, destination)
                self.assertEqual(source.read_bytes(), baseline["oreslang.py"])
                self.assertEqual(destination.read_bytes(), baseline["oreslang.py"])
                destination.unlink()
                publisher.create_package(payloads, destination)
                publisher.verify_package(payloads, destination)
                self.assertNotEqual(os.stat(source).st_ino, os.stat(destination).st_ino)
            self.assertEqual(
                {name: (root / name).read_bytes() for name in publisher.MEMBERS},
                baseline,
            )


if __name__ == "__main__":
    unittest.main()
