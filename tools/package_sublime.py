#!/usr/bin/env python3
"""Build a deterministic Sublime Text package from explicitly allowlisted files."""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
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


def _validate_destination(dest: Path) -> None:
    """Reject aliases to sources and caller-owned files before any replacement."""
    if dest.is_symlink():
        raise ValueError("symlinked package destination")
    if dest.resolve() in {ROOT / name for name in MEMBERS}:
        raise ValueError("package destination would replace a source file")
    if dest.is_file() and any((ROOT / name).exists() and dest.samefile(ROOT / name) for name in MEMBERS):
        raise ValueError("package destination hardlinks a reviewed source file; hardlinked package destination")
    if dest.exists() and dest.stat().st_nlink > 1:
        raise ValueError("hardlinked package destination")


def create_package(files: dict[str, bytes], dest: Path = PACKAGE) -> None:
    # Validate the complete archive manifest BEFORE touching the destination.
    if set(files) != set(MEMBERS) or any(type(data) is not bytes for data in files.values()):
        raise ValueError("package members must match the reviewed byte allowlist")
    _validate_destination(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)

    # ZipFile(dest, "w") used to truncate the caller's path after preflight:
    # a symlink/hardlink inserted between the check and open could overwrite
    # its target. Stage exclusively in the same directory, never writing to
    # the caller's destination inode, then atomically rename the completed ZIP.
    staged: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w+b", prefix=".oreslang-release-",
                                         suffix=".tmp", dir=dest.parent, delete=False) as stream:
            staged = Path(stream.name)
            with zipfile.ZipFile(stream, "w") as archive:
                for name in sorted(files):
                    info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
                    info.compress_type = zipfile.ZIP_STORED
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, files[name])
            stream.flush()
            os.fsync(stream.fileno())

        # A replacement race can still change the directory entry; revalidate
        # after staging. os.replace never follows a leaf symlink or writes
        # through a hardlink even if the entry changes after this last check.
        _validate_destination(dest)
        os.replace(staged, dest)
        staged = None
    finally:
        if staged is not None:
            staged.unlink(missing_ok=True)


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
