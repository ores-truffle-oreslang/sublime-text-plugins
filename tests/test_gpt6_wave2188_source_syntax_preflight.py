"""Host-source preflight: invalid Python cannot pass package_files admission.

The reviewed source tree is copied into an isolated temporary root; no real
package contents, compiler guest, or production files are modified.
"""
import tempfile
import unittest
from pathlib import Path

from tools.package_sublime import MEMBERS, ROOT, package_files, create_package, verify_package


class PythonSourcePreflight(unittest.TestCase):
    def test_syntax_invalid_source_never_replaces_prior_published_archive(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source-copy"
            root.mkdir()
            for name in MEMBERS:
                (root / name).write_bytes((ROOT / name).read_bytes())
            expected = package_files(root)
            dest = Path(temp) / "Oreslang.sublime-package"
            create_package(expected, dest)
            verify_package(expected, dest)
            original = dest.read_bytes()

            # The standard packager's input validator compiles the *real*
            # copied source. A malformed Python file must not be admitted.
            python = root / "oreslang.py"
            python.write_bytes(b"def malformed(:\n    pass\n")
            with self.assertRaises(SyntaxError):
                package_files(root)
            self.assertEqual(dest.read_bytes(), original)
            self.assertEqual((ROOT / "oreslang.py").read_bytes(), expected["oreslang.py"])

            # Restoring source bytes recovers the deterministic publication.
            python.write_bytes(expected["oreslang.py"])
            restored = package_files(root)
            self.assertEqual(restored, expected)
            create_package(restored, dest)
            verify_package(restored, dest)
            self.assertEqual(dest.read_bytes(), original)

    def test_grammar_identity_rejection_cannot_poison_stable_copy(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "source-copy"
            root.mkdir()
            for name in MEMBERS:
                (root / name).write_bytes((ROOT / name).read_bytes())
            expected = package_files(root)
            grammar = root / "Oreslang.sublime-syntax"
            grammar.write_bytes(grammar.read_bytes().replace(b"source.oreslang", b"source.unreviewed"))
            with self.assertRaisesRegex(ValueError, "Sublime syntax must declare"):
                package_files(root)
            grammar.write_bytes(expected["Oreslang.sublime-syntax"])
            self.assertEqual(package_files(root), expected)


if __name__ == "__main__":
    unittest.main()
