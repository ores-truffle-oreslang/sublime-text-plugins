"""Each allowlisted install package member is bound to trusted source bytes.

Host packaging verifier proof only; no compiler-backed AttoLang guest execution.
"""
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.package_sublime import MEMBERS, package_files, create_package, verify_package


class PackageMemberMutationMatrix(unittest.TestCase):
    def test_all_members_reject_canonical_metadata_but_modified_payload(self):
        trusted = package_files()
        self.assertEqual(set(trusted), set(MEMBERS))
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "Oreslang.sublime-package"
            create_package(trusted, output)
            verify_package(trusted, output)
            pristine = output.read_bytes()
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.namelist(), sorted(MEMBERS))
            for member in MEMBERS:
                with self.subTest(member=member):
                    tampered = dict(trusted)
                    tampered[member] = trusted[member] + b"\x00"
                    # Writing with the public packager recomputes ZIP CRC and
                    # preserves canonical modes, timestamps, member ordering.
                    # A simple corrupt-CRC negative would not establish that
                    # trusted contents are independently checked.
                    create_package(tampered, output)
                    self.assertNotEqual(output.read_bytes(), pristine)
                    with zipfile.ZipFile(output) as archive:
                        self.assertEqual(archive.namelist(), sorted(MEMBERS))
                        self.assertEqual(archive.read(member), tampered[member])
                    with self.assertRaisesRegex(ValueError, "Package verification failed"):
                        verify_package(trusted, output)
                    create_package(trusted, output)
                    verify_package(trusted, output)
                    self.assertEqual(output.read_bytes(), pristine)


if __name__ == "__main__":
    unittest.main()
