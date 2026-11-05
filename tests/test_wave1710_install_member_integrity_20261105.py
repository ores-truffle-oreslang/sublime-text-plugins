"""Roundtrip exact package members after a late-member integrity failure.

Source-owned package-builder check, not a compiler-backed guest test.
"""
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "package_sublime.py"
spec = importlib.util.spec_from_file_location("wave1710_install", SCRIPT)
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class Wave1710InstallMemberIntegrity(unittest.TestCase):
    def test_modified_last_allowlisted_member_is_rejected_then_recovers(self):
        original = package.package_files()
        member_names = sorted(package.MEMBERS)
        self.assertEqual(set(original), set(member_names))
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "Oreslang.sublime-package"
            package.create_package(original, target)
            package.verify_package(original, target)
            baseline = hashlib.sha256(target.read_bytes()).hexdigest()

            tampered = dict(original)
            last_name = member_names[-1]
            tampered[last_name] = original[last_name] + b"\n# injected late member\n"
            package.create_package(tampered, target)
            with self.assertRaisesRegex(ValueError, "Package verification failed"):
                package.verify_package(original, target)

            package.create_package(original, target)
            package.verify_package(original, target)
            self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), baseline)
            self.assertEqual(package.package_files(), original)


if __name__ == "__main__":
    unittest.main()
