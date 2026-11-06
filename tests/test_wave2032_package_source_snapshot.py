"""Host-only source allowlist snapshot: Unicode paths and symlink denial."""
import tempfile
import unittest
from pathlib import Path

from tools.package_sublime import MEMBERS, ROOT, package_files


class PackageSourceSnapshot(unittest.TestCase):
    def test_nested_unicode_clone_round_trips_reviewed_source_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            clone = Path(temp) / "attō-α💠" / "safe"
            clone.mkdir(parents=True)
            for name in MEMBERS:
                (clone / name).write_bytes((ROOT / name).read_bytes())
            content = package_files(clone)
            self.assertEqual(set(content), set(MEMBERS))
            for name in MEMBERS:
                self.assertEqual(content[name], (ROOT / name).read_bytes())
            # A different source tree must never gain authority by a symlink
            # alias, even if the target bytes match the reviewed source.
            source = clone / "oreslang.py"
            source.unlink()
            source.symlink_to(ROOT / "oreslang.py")
            with self.assertRaisesRegex(ValueError, "Missing or symlinked"):
                package_files(clone)
            source.unlink()
            source.write_bytes((ROOT / "oreslang.py").read_bytes())
            self.assertEqual(package_files(clone), content)

    def test_required_grammar_identity_rejected_before_package_admission(self):
        with tempfile.TemporaryDirectory() as temp:
            clone = Path(temp)
            for name in MEMBERS:
                (clone / name).write_bytes((ROOT / name).read_bytes())
            grammar = clone / "Oreslang.sublime-syntax"
            grammar.write_bytes(grammar.read_bytes().replace(b"source.oreslang", b"source.untrusted"))
            with self.assertRaisesRegex(ValueError, "Sublime syntax must declare"):
                package_files(clone)


if __name__ == "__main__":
    unittest.main()
