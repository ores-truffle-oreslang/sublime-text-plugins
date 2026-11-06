"""Real release archive source-drift rejection and deterministic recovery.

All reviewed source input bytes are copied into temporary, isolated test roots.
"""
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_sublime_package as publisher


class ReleaseSourceDriftRecovery(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/"reviewed"
        self.root.mkdir()
        self.original={}
        for name in publisher.FILES:
            data=(publisher.ROOT/name).read_bytes()
            (self.root/name).write_bytes(data)
            self.original[name]=data
        self.owner=patch.object(publisher,"ROOT",self.root)
        self.owner.start()
        self.addCleanup(self.owner.stop)

    def test_each_member_drift_is_rejected_until_matching_release_rebuilt(self):
        destination=Path(self.tmp.name)/"release.zip"
        pristine_digest=publisher.build(destination)
        pristine=destination.read_bytes()
        self.assertEqual(pristine_digest,hashlib.sha256(pristine).hexdigest())
        for member in publisher.FILES:
            with self.subTest(member=member):
                source=self.root/member
                source.write_bytes(self.original[member]+b"\n#reviewed-source-drift")
                # An older signed publication must no longer verify against
                # changed source bytes, even when its ZIP is otherwise intact.
                with self.assertRaisesRegex(ValueError,"archive differs from source"):
                    publisher.verify(destination)
                new_digest=publisher.build(destination)
                publisher.verify(destination)
                self.assertNotEqual(new_digest,pristine_digest)
                self.assertNotEqual(destination.read_bytes(),pristine)
                source.write_bytes(self.original[member])
                self.assertEqual(publisher.build(destination),pristine_digest)
                self.assertEqual(destination.read_bytes(),pristine)
                publisher.verify(destination)


if __name__=="__main__":
    unittest.main()
