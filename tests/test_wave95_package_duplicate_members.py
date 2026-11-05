"""Release ZIP member authority: duplicates and unreviewed entries are refused."""
import importlib.util
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "package_sublime.py"
spec = importlib.util.spec_from_file_location("wave95_package", SCRIPT)
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class Wave95PackageMemberAdmission(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / "Oreslang.sublime-package"
        self.files = package.package_files()
        package.create_package(self.files, self.output)
        package.verify_package(self.files, self.output)

    def test_duplicate_existing_member_is_not_silently_last_wins(self):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.output, "a") as archive:
                archive.writestr("oreslang.py", self.files["oreslang.py"])
        with self.assertRaisesRegex(ValueError, "unexpected"):
            package.verify_package(self.files, self.output)

    def test_archive_path_traversal_member_rejected_before_install(self):
        with zipfile.ZipFile(self.output, "a") as archive:
            archive.writestr("../outside.py", b"raise RuntimeError('unreviewed')")
        with self.assertRaisesRegex(ValueError, "unexpected"):
            package.verify_package(self.files, self.output)


if __name__ == "__main__":
    unittest.main()
