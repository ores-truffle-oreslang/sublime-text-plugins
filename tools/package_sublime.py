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
    # Validate the complete archive manifest BEFORE creating/truncating a file.
    # The helper is importable by callers other than the trusted CLI entrypoint.
    if set(files) != set(MEMBERS) or any(type(data) is not bytes for data in files.values()):
        raise ValueError("package members must match the reviewed byte allowlist")
    # ZipFile opens existing leaf symlinks for writing; never let a package
    # request replace a reviewed source member or an unrelated file.
    if dest.is_symlink():
        raise ValueError("symlinked package destination")
    # A hardlink is not a symlink: ZipFile('w') would overwrite the shared
    # inode and corrupt a trusted source or caller-owned sentinel.
    if dest.exists() and dest.stat().st_nlink > 1:
        raise ValueError("hardlinked package destination")
    if dest.resolve() in {ROOT / name for name in MEMBERS}:
        raise ValueError("package destination would replace a source file")
    # An existing hardlink has a different path but the SAME inode as its source.
    # ZipFile("w") would truncate the reviewed source through that alias.
    if dest.is_file() and any(dest.samefile(ROOT / name) for name in MEMBERS):
        raise ValueError("package destination hardlinks a reviewed source file")
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w") as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, files[name])


def verify_package(files: dict[str, bytes], dest: Path = PACKAGE) -> None:
    # A partial caller-provided expectation must never self-certify an archive.
    # The same complete trusted manifest is required by create_package().
    if set(files) != set(MEMBERS) or any(type(data) is not bytes for data in files.values()):
        raise ValueError("package members must match the reviewed byte allowlist")
    with zipfile.ZipFile(dest, "r") as archive:
        # The packager emits no global ZIP comment. Reject metadata-only
        # changes even when member contents and canonical names are unchanged.
        if archive.comment:
            raise ValueError("Package verification failed: unexpected archive comment")
        if archive.namelist() != sorted(MEMBERS):
            raise ValueError("Archive contains unexpected package files")
        for name, expected in files.items():
            info = archive.getinfo(name)
            # Canonical package members must be regular Unix files. The source
            # bytes alone do not bind a ZIP entry's file type or permissions:
            # a tampered archive could otherwise advertise a symlink.
            if (info.create_system != 3 or
                    info.external_attr != (0o100644 << 16) or
                    info.compress_type != zipfile.ZIP_STORED or
                    info.date_time != FIXED_DATE or
                    info.extra or info.comment or
                    archive.read(name) != expected):
                raise ValueError("Package verification failed: " + name)


if __name__ == "__main__":
    try:
        items = package_files()
        create_package(items)
        verify_package(items)
        print(f"{PACKAGE.name} SHA-256 {hashlib.sha256(PACKAGE.read_bytes()).hexdigest()}")
    except (OSError, SyntaxError, ValueError, zipfile.BadZipFile) as exc:
        sys.exit(f"Refused to package Oreslang for Sublime: {exc}")
