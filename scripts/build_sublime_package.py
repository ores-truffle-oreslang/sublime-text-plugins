#!/usr/bin/env python3
"""Build the release-only Oreslang.sublime-package from a fixed allowlist."""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "Default.sublime-commands",
    "Main.sublime-menu",
    "Oreslang.sublime-build",
    "Oreslang.sublime-settings",
    "Oreslang.sublime-syntax",
    "oreslang.py",
)
ARCHIVE_NAME = "Oreslang.sublime-package"

def build(dest: Path) -> str:
    # Refuse alias destinations: ZipFile("w") follows leaf symlinks and could
    # overwrite a trusted source file or an unrelated external sentinel.
    if dest.is_symlink():
        raise ValueError("symlinked release destination")
    # A regular-looking output may also be a hardlink to a trusted source or
    # unrelated file. Writing ZipFile('w') would truncate every such alias.
    if dest.exists() and dest.stat().st_nlink > 1:
        raise ValueError("hardlinked release destination")
    resolved = dest.resolve()
    if resolved.is_relative_to(ROOT) and resolved.name in FILES:
        raise ValueError("archive cannot replace a source file")
    # The resolved path alone misses a distinct hardlink to a reviewed source inode.
    # Check before opening ZipFile("w"), which would truncate the source itself.
    if dest.is_file() and any(dest.samefile(ROOT / name) for name in FILES):
        raise ValueError("release destination hardlinks a source file")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if len(FILES) != len(set(FILES)):
        raise ValueError("duplicate package paths")
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9, strict_timestamps=True) as archive:
        for name in sorted(FILES):
            source = ROOT / name
            if not source.is_file() or source.is_symlink():
                raise ValueError(f"missing or symlinked required release file: {name}")
            entry = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, source.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    verify(dest)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    return sha

def verify(dest: Path) -> None:
    with zipfile.ZipFile(dest) as archive:
        # Out-of-band ZIP comments are not emitted by the reproducible builder.
        # They can carry forged release attestations despite identical member bytes.
        if archive.comment:
            raise ValueError("unexpected ZIP archive comment")
        names = archive.namelist()
        if names != sorted(FILES):
            raise ValueError("release archive contains unexpected, missing or duplicate files")
        for entry in archive.infolist():
            # Canonical release ZIPs never emit per-member extras/comments and
            # every member uses DEFLATE. Matching payload bytes alone is not
            # enough to bind the reviewed, reproducible archive metadata.
            if entry.compress_type != zipfile.ZIP_DEFLATED or entry.extra or entry.comment:
                raise ValueError("noncanonical ZIP member metadata")
            if entry.date_time != (1980, 1, 1, 0, 0, 0):
                raise ValueError("nonreproducible archive timestamp")
            if entry.create_system != 3 or (entry.external_attr >> 16) != 0o100644:
                raise ValueError("nonportable archive file mode")
            if archive.read(entry.filename) != (ROOT / entry.filename).read_bytes():
                raise ValueError("archive differs from source")
        if b"source.oreslang" not in archive.read("Oreslang.sublime-syntax"):
            raise ValueError("installed compiler-current grammar missing")
        for forbidden in ("Preview.sublime-syntax", "conformance/", "contracts/",
                          "tests/", "syntax_test_", "foo.ores", ".github/"):
            if any(name.startswith(forbidden) for name in names):
                raise ValueError("preview/test/private source included")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("dist") / ARCHIVE_NAME)
    args = parser.parse_args()
    digest = build(args.output)
    print(f"SHA256 {digest} {args.output}")
