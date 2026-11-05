"""Release ZIP must match reviewed source bytes despite legal ZIP metadata."""
import tempfile
import unittest
import zipfile
from pathlib import Path
from scripts.build_sublime_package import build, verify, ROOT


class Wave2331ReleaseSourceIntegrity(unittest.TestCase):
    def test_same_length_menu_mutation_denied_then_rebuilt_exactly(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "Oreslang.sublime-package"
            build(path)
            baseline = path.read_bytes()
            with zipfile.ZipFile(path) as original:
                contents = [(info, original.read(info.filename)) for info in original.infolist()]
            target = "Main.sublime-menu"
            self.assertIn(target, [info.filename for info, _ in contents])
            with zipfile.ZipFile(path, "w") as modified:
                for info, content in contents:
                    if info.filename == target:
                        self.assertTrue(content)
                        content = bytes([content[0] ^ 1]) + content[1:]
                    modified.writestr(info, content)
            with self.assertRaisesRegex(ValueError, "archive differs from source"):
                verify(path)
            build(path)
            verify(path)
            self.assertEqual(path.read_bytes(), baseline)
            with zipfile.ZipFile(path) as restored:
                self.assertEqual(restored.read(target), (ROOT / target).read_bytes())


if __name__ == "__main__":
    unittest.main()
