"""Adversarial package-file mappings must fail before opening a ZIP destination."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "package_sublime.py"
spec = importlib.util.spec_from_file_location("wave3011_package", SCRIPT)
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class Wave3011ArchiveManifestPreflight(unittest.TestCase):
    def test_invalid_manifest_never_replaces_existing_publication(self):
        files = package.package_files()
        with tempfile.TemporaryDirectory() as dirname:
            output = Path(dirname) / "Oreslang.sublime-package"
            for mutated in (
                {**files, "unreviewed.txt": b"injected"},
                {key: data for key, data in files.items() if key != "oreslang.py"},
                {**files, "oreslang.py": "text instead of bytes"},
            ):
                with self.subTest(entries=list(mutated)):
                    output.write_bytes(b"retain existing package bytes")
                    with self.assertRaisesRegex(ValueError, "reviewed byte allowlist"):
                        package.create_package(mutated, output)
                    self.assertEqual(output.read_bytes(), b"retain existing package bytes")

            package.create_package(files, output)
            package.verify_package(files, output)
            self.assertNotEqual(output.read_bytes(), b"retain existing package bytes")


if __name__ == "__main__":
    unittest.main()
