"""Release builder rejects a hardlinked archive destination without source damage.

Use a private copy of all reviewed files to avoid touching source-owned inodes.
"""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import build_sublime_package as builder


class ReleaseSourceInodeSafety(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"reviewed-source"
        self.root.mkdir()
        for name in builder.FILES:
            (self.root/name).write_bytes((builder.ROOT/name).read_bytes())
        self.owner=patch.object(builder,"ROOT",self.root)
        self.owner.start()
        self.addCleanup(self.owner.stop)

    def test_hardlinked_destination_refuses_before_truncating_any_source(self):
        output=self.root/"build"/builder.ARCHIVE_NAME
        output.parent.mkdir()
        source=self.root/builder.FILES[0]
        before=source.read_bytes()
        os.link(source,output)
        with self.assertRaisesRegex(ValueError,"hardlinked release destination"):
            builder.build(output)
        self.assertEqual(source.read_bytes(),before)
        self.assertEqual(output.read_bytes(),before)
        output.unlink()
        digest=builder.build(output)
        self.assertEqual(hashlib.sha256(output.read_bytes()).hexdigest(),digest)
        builder.verify(output)

    def test_foreign_hardlink_refusal_and_recovery_with_original_external_bytes(self):
        output=Path(self.tmp.name)/"out.sublime-package"
        sentinel=Path(self.tmp.name)/"sentinel.txt"
        sentinel.write_bytes(b"trusted external bytes")
        os.link(sentinel,output)
        with self.assertRaisesRegex(ValueError,"hardlinked release destination"):
            builder.build(output)
        self.assertEqual(sentinel.read_bytes(),b"trusted external bytes")
        output.unlink()
        digest1=builder.build(output)
        first=output.read_bytes()
        digest2=builder.build(output)
        self.assertEqual((digest1,digest2),(hashlib.sha256(first).hexdigest(),)*2)
        self.assertEqual(output.read_bytes(),first)


if __name__=="__main__":
    unittest.main()
