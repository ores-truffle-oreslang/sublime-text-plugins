#!/usr/bin/env python3
"""Build a deterministic Sublime Text package from explicitly allowlisted files."""
from __future__ import annotations

import hashlib
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "dist" / "Oreslang.sublime-package"
MEMBERS = (
    "Default.sublime-commands",
    "Main.sublime-menu",
    "Oreslang.sublime-build",
    "Oreslang.sublime-settings",
    "Oreslang.sublime-syntax",
    "oreslang.py",
)
FIXED_DATE = (1980, 1, 1, 0, 0, 0)


def package_files(root: Path = ROOT) -> dict[str, bytes]:
    content = {}
    for name in MEMBERS:
        file = root / name
        if file.is_symlink() or not file.is_file():
            raise ValueError("Missing or symlinked package file: " + name)
        content[name] = file.read_bytes()
    if b"source.oreslang" not in content["Oreslang.sublime-syntax"] or \
       b"  - ores" not in content["Oreslang.sublime-syntax"]:
        raise ValueError("Sublime syntax must declare source.oreslang and .ores")
    compile(content["oreslang.py"], "oreslang.py", "exec")
    return content


def create_package(files: dict[str, bytes], dest: Path = PACKAGE) -> None:
    # ZipFile opens existing leaf symlinks for writing; never let a package
    # request replace a reviewed source member or an unrelated file.
    if dest.is_symlink():
        raise ValueError("symlinked package destination")
    if dest.resolve() in {ROOT / name for name in MEMBERS}:
        raise ValueError("package destination would replace a source file")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w") as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, files[name])


def verify_package(files: dict[str, bytes], dest: Path = PACKAGE) -> None:
    with zipfile.ZipFile(dest, "r") as archive:
        if archive.namelist() != sorted(MEMBERS):
            raise ValueError("Archive contains unexpected package files")
        for name, expected in files.items():
            info = archive.getinfo(name)
            if info.compress_type != zipfile.ZIP_STORED or \
               info.date_time != FIXED_DATE or archive.read(name) != expected:
                raise ValueError("Package verification failed: " + name)


if __name__ == "__main__":
    try:
        items = package_files()
        create_package(items)
        verify_package(items)
        print(f"{PACKAGE.name} SHA-256 {hashlib.sha256(PACKAGE.read_bytes()).hexdigest()}")
    except (OSError, SyntaxError, ValueError, zipfile.BadZipFile) as exc:
        sys.exit(f"Refused to package Oreslang for Sublime: {exc}")
