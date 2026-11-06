"""Reject per-member archive metadata hidden beside exact reviewed source bytes."""
import tempfile
import unittest
import zipfile
from pathlib import Path
from tools.package_sublime import package_files, create_package, verify_package, MEMBERS


class MemberExtraAndCommentRejection(unittest.TestCase):
    def test_member_extra_fields_and_comments_never_survive_package_verification(self):
        members=package_files()
        names=[sorted(MEMBERS)[0],sorted(MEMBERS)[len(MEMBERS)//2],sorted(MEMBERS)[-1]]
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/"Oreslang.sublime-package"
            create_package(members,output)
            verify_package(members,output)
            canonical=output.read_bytes()
            for name in names:
                for variant in ("extra","comment"):
                    with self.subTest(name=name,variant=variant):
                        with zipfile.ZipFile(output,"r") as archive:
                            entries=[(info,archive.read(info.filename)) for info in archive.infolist()]
                        with zipfile.ZipFile(output,"w") as archive:
                            for info,payload in entries:
                                if info.filename==name:
                                    if variant=="extra":
                                        info.extra=b"\xfe\xca\x02\x00OK"
                                    else:
                                        info.comment=b"forged release proof"
                                archive.writestr(info,payload)
                        with self.assertRaisesRegex(ValueError,"Package verification failed"):
                            verify_package(members,output)
                        create_package(members,output)
                        verify_package(members,output)
                        self.assertEqual(output.read_bytes(),canonical)


if __name__ == "__main__":
    unittest.main()
