"""Installed ZIP integration contract: menu, commands, build, settings and grammar."""
import ast
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.package_sublime import MEMBERS, create_package, package_files, verify_package


class InstalledCommandWiring(unittest.TestCase):
    def test_installed_public_commands_match_real_plugin_classes_and_editor_settings(self):
        trusted = package_files()
        with tempfile.TemporaryDirectory() as folder:
            archive_path = Path(folder) / "Oreslang.sublime-package"
            create_package(trusted, archive_path)
            verify_package(trusted, archive_path)
            with zipfile.ZipFile(archive_path) as archive:
                self.assertEqual(archive.namelist(), sorted(MEMBERS))
                self.assertEqual({name: archive.read(name) for name in MEMBERS}, trusted)
                palette = json.loads(archive.read("Default.sublime-commands"))
                menu = json.loads(archive.read("Main.sublime-menu"))
                build = json.loads(archive.read("Oreslang.sublime-build"))
                settings = json.loads(archive.read("Oreslang.sublime-settings"))
                grammar = archive.read("Oreslang.sublime-syntax").decode("utf-8")
                python_source = archive.read("oreslang.py").decode("utf-8")

        self.assertEqual([item["command"] for item in palette],
                         ["oreslang_check_file", "oreslang_clear_diagnostics", "edit_settings"])
        names = {node.name for node in ast.parse(python_source).body
                 if isinstance(node, ast.ClassDef)}
        self.assertTrue({"OreslangCheckFileCommand", "OreslangClearDiagnosticsCommand",
                         "OreslangDiagnosticsListener"} <= names)

        def leaf_commands(nodes):
            for node in nodes:
                if "command" in node:
                    yield node
                yield from leaf_commands(node.get("children", []))

        menu_commands = list(leaf_commands(menu))
        self.assertEqual([item["command"] for item in menu_commands], ["edit_settings"])
        pref = "${packages}/Oreslang/Oreslang.sublime-settings"
        self.assertEqual(palette[-1]["args"]["base_file"], pref)
        self.assertEqual(menu_commands[0]["args"]["base_file"], pref)
        self.assertEqual(build["selector"], "source.oreslang")
        self.assertEqual(build["cmd"], ["oreslang", "check", "$file"])
        self.assertEqual(build["working_dir"], "$file_path")
        self.assertEqual(settings["cli_command"], ["oreslang", "check", "--format=json", "$file"])
        self.assertIn("scope: source.oreslang", grammar)
        self.assertIn("  - ores\n", grammar)
        self.assertIn("  - atto\n", grammar)


if __name__ == "__main__":
    unittest.main()
