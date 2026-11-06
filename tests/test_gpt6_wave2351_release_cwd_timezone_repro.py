"""Real release generator must be content-addressable across cwd and locale/TZ."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

from scripts.build_sublime_package import FILES, ROOT, verify


class ReleaseEnvironmentDeterminism(unittest.TestCase):
    def test_independent_subprocesses_generate_the_exact_same_reviewed_zip(self):
        generated = []
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            for index, (timezone, language) in enumerate(
                (("UTC", "C"), ("Pacific/Auckland", "en_US.UTF-8"),
                 ("America/Lima", "C.UTF-8"))
            ):
                cwd = base / ("work dir " + str(index))
                cwd.mkdir()
                output = base / ("release " + str(index) + ".sublime-package")
                environment = dict(os.environ, TZ=timezone, LANG=language, LC_ALL="C")
                proc = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / "build_sublime_package.py"),
                     "--output", str(output)],
                    cwd=cwd, env=environment, capture_output=True, text=True,
                    timeout=40, check=True)
                self.assertIn("SHA256", proc.stdout)
                verify(output)
                generated.append(output.read_bytes())
                self.assertIn(hashlib.sha256(generated[-1]).hexdigest(), proc.stdout)
                with zipfile.ZipFile(output) as package:
                    self.assertEqual(package.namelist(), sorted(FILES))
                    for member in package.infolist():
                        self.assertEqual(package.read(member.filename),
                                         (ROOT / member.filename).read_bytes())
                        self.assertEqual(member.date_time, (1980, 1, 1, 0, 0, 0))
            self.assertEqual(generated[0], generated[1])
            self.assertEqual(generated[1], generated[2])


if __name__ == "__main__":
    unittest.main()
