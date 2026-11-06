"""Trusted installed package content is bound to every allowlisted byte blob.

Tests the actual byte-level ZIP writer/verifier; not compiler guest execution.
"""
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.package_sublime import MEMBERS, package_files, create_package, verify_package


class InstalledManifestPayloadBinding(unittest.TestCase):
    def test_valid_crc_replacement_of_any_member_is_detected_and_restorable(self):
        trusted = package_files()
        with tempfile.TemporaryDirectory() as root:
            target = Path(root)/"Oreslang.sublime-package"
            create_package(trusted,target)
            verify_package(trusted,target)
            pristine = target.read_bytes()
            for name in MEMBERS:
                with self.subTest(name=name):
                    forged = dict(trusted)
                    forged[name] = b"tampered:" + trusted[name]
                    create_package(forged,target)
                    # The attacker's ZIP has internally valid CRCs and modes;
                    # only comparison with the reviewed source rejects it.
                    with zipfile.ZipFile(target) as archive:
                        self.assertEqual(archive.namelist(), sorted(MEMBERS))
                        self.assertEqual(archive.read(name),forged[name])
                    self.assertNotEqual(target.read_bytes(), pristine)
                    with self.assertRaisesRegex(ValueError, "Package verification failed"):
                        verify_package(trusted,target)
                    create_package(trusted,target)
                    verify_package(trusted,target)
                    self.assertEqual(target.read_bytes(),pristine)


if __name__=="__main__":
    unittest.main()
