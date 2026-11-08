#!/usr/bin/env python3
"""Build a deterministic Sublime Text package from explicitly allowlisted files."""
from __future__ import annotations

import errno
import hashlib
import os
import secrets
import stat
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
    # A parent symlink redirects the temporary archive and the eventual
    # replacement into an unreviewed directory. Validate every ancestor.
    if ".." in dest.parts:
        raise ValueError("noncanonical package destination parent")
    ancestor = dest.parent
    while True:
        if ancestor.is_symlink():
            raise ValueError("symlinked package destination parent")
        parent = ancestor.parent
        if parent == ancestor:
            break
        ancestor = parent


def _secure_parent_fd(dest: Path) -> int:
    """Walk to the output directory without following any parent symlinks.

    Every directory handle stays anchored across path substitutions. Fail closed
    on platforms that cannot provide no-follow and dir_fd-relative operations.
    """
    # CPython implements replace's dir_fd support via rename, but does not
    # list os.replace itself in supports_dir_fd on Linux.
    required = (os.open, os.mkdir, os.stat, os.unlink, os.rename)
    if (os.name != "posix" or
            not all(hasattr(os, flag) for flag in ("O_DIRECTORY", "O_NOFOLLOW")) or
            not all(fn in os.supports_dir_fd for fn in required) or
            os.stat not in os.supports_follow_symlinks):
        raise ValueError("secure directory-relative package publication unsupported")
    if ".." in dest.parts or not dest.name or dest.name in (".", ".."):
        raise ValueError("noncanonical package destination parent")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    fd = os.open("/" if dest.is_absolute() else ".", flags)
    try:
        for component in dest.parent.parts:
            if component in ("/", "."):
                continue
            try:
                try:
                    child = os.open(component, flags, dir_fd=fd)
                except FileNotFoundError:
                    os.mkdir(component, dir_fd=fd)
                    child = os.open(component, flags, dir_fd=fd)
            except OSError as exc:
                if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                    raise ValueError("symlinked package destination parent") from exc
                raise
            os.close(fd)
            fd = child
        # A shared-writable final parent permits another uid to race the
        # visible staging basename. Refuse that trust boundary at admission.
        if os.fstat(fd).st_mode & 0o022:
            raise ValueError("unsafe shared-writable package destination parent")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _validate_anchored_destination(dest: Path, parent_fd: int) -> None:
    """Bind the expected parent and leaf to the pinned output directory."""
    try:
        current_parent = os.stat(dest.parent, follow_symlinks=False)
    except OSError as exc:
        raise ValueError("package destination parent moved during staging") from exc
    anchored_parent = os.fstat(parent_fd)
    if (not stat.S_ISDIR(current_parent.st_mode) or
            (current_parent.st_dev, current_parent.st_ino) !=
            (anchored_parent.st_dev, anchored_parent.st_ino)):
        raise ValueError("package destination parent moved during staging")
    try:
        leaf = os.stat(dest.name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(leaf.st_mode):
        raise ValueError("symlinked package destination")
    if not stat.S_ISREG(leaf.st_mode):
        raise ValueError("package destination is not a regular file")
    for name in MEMBERS:
        try:
            source = os.stat(ROOT / name, follow_symlinks=False)
        except FileNotFoundError:
            continue
        if (leaf.st_dev, leaf.st_ino) == (source.st_dev, source.st_ino):
            raise ValueError("package destination hardlinks a reviewed source file")
    if leaf.st_nlink > 1:
        raise ValueError("hardlinked package destination")


def create_package(files: dict[str, bytes], dest: Path = PACKAGE) -> None:
    # Reject malformed bytes/manifest and existing aliases before any I/O.
    if set(files) != set(MEMBERS) or any(type(data) is not bytes for data in files.values()):
        raise ValueError("package members must match the reviewed byte allowlist")
    _validate_destination(dest)
    parent_fd = _secure_parent_fd(dest)
    staged_name: str | None = None
    staged_identity: tuple[int, int] | None = None
    try:
        _validate_anchored_destination(dest, parent_fd)
        for _ in range(8):
            candidate = ".oreslang-release-" + secrets.token_hex(16) + ".tmp"
            try:
                stage_fd = os.open(candidate, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                                   os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
                                   0o600, dir_fd=parent_fd)
                staged_name = candidate
                try:
                    staged_stat = os.fstat(stage_fd)
                except BaseException:
                    # A descriptor can be opened successfully while its inode
                    # inspection fails. Close it. Without a trusted inode id,
                    # cleanup must not unlink a name an attacker could replace.
                    os.close(stage_fd)
                    raise
                staged_identity = (staged_stat.st_dev, staged_stat.st_ino)
                break
            except FileExistsError:
                continue
        else:
            raise ValueError("cannot reserve unique staging file")

        # A directory swap now cannot redirect the stage to another directory:
        # the temporary file is created relative to the pinned directory fd.
        # fdopen() may fail before ownership of the raw stage fd transfers
        # to a Python file object. Close it explicitly on that path; otherwise
        # the temporary file cleanup succeeds but the descriptor leaks.
        try:
            stage_stream = os.fdopen(stage_fd, "w+b")
        except BaseException:
            os.close(stage_fd)
            raise
        with stage_stream as stream:
            with zipfile.ZipFile(stream, "w") as archive:
                for name in sorted(files):
                    info = zipfile.ZipInfo(name, date_time=FIXED_DATE)
                    info.compress_type = zipfile.ZIP_STORED
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    archive.writestr(info, files[name])
            stream.flush()
            os.fsync(stream.fileno())

        # The pathname recheck is an additional fail-closed signal; the actual
        # destination and cleanup never use it. Even if swapped after this line,
        # os.replace below is anchored to the same directory on both sides.
        _validate_destination(dest)
        _validate_anchored_destination(dest, parent_fd)
        # The parent may have become shared-writable after initial admission.
        if os.fstat(parent_fd).st_mode & 0o022:
            raise ValueError("unsafe shared-writable package destination parent")
        # The temporary name must still refer to the inode written through
        # our pinned fd. An attacker with same-directory write access can
        # replace a visible staging pathname while its write fd stays open.
        try:
            staged_leaf = os.stat(staged_name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError as exc:
            raise ValueError("staged archive pathname replaced during publication") from exc
        if (not stat.S_ISREG(staged_leaf.st_mode) or staged_leaf.st_nlink != 1 or
                (staged_leaf.st_dev, staged_leaf.st_ino) != staged_identity):
            raise ValueError("staged archive pathname replaced during publication")
        os.replace(staged_name, dest.name,
                   src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
        staged_name = None
        # A pinned handle prevents redirecting this rename to a foreign
        # directory. Verify that the caller-visible destination still names
        # that parent and the exact inode written through our staging fd.
        _validate_destination(dest)
        _validate_anchored_destination(dest, parent_fd)
        if os.fstat(parent_fd).st_mode & 0o022:
            raise ValueError("unsafe shared-writable package destination parent")
        published_stat = os.stat(dest.name, dir_fd=parent_fd, follow_symlinks=False)
        if (published_stat.st_dev, published_stat.st_ino) != staged_identity:
            raise ValueError("package output changed after atomic replace")
    finally:
        try:
            if staged_name is not None:
                # Never delete a different caller-owned inode substituted for
                # our staged name. Missing stages are already gone; do not let
                # cleanup obscure the original fail-closed exception.
                try:
                    remaining = os.stat(staged_name, dir_fd=parent_fd,
                                        follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    if (remaining.st_dev, remaining.st_ino) == staged_identity:
                        try:
                            os.unlink(staged_name, dir_fd=parent_fd)
                        except FileNotFoundError:
                            pass
        finally:
            os.close(parent_fd)


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
