import itertools
import json
import os
import re
import signal
import shlex
import subprocess
import threading
import time

import sublime
import sublime_plugin


DIAGNOSTIC_KEY = "oreslang.cli.diagnostics"
SETTINGS_FILE = "Oreslang.sublime-settings"

_STANDARD_DIAGNOSTIC = re.compile(
    r"^(.+?):(\d+):(\d+):\s*(?:(error|warning|info):\s*)?(.*)$",
    re.IGNORECASE,
)
_ORESLANG_DIAGNOSTIC = re.compile(
    r"Oreslang\s+(?:lexer|parse)\s+error\s+at\s+(\d+):(\d+):\s*(.*)$",
    re.IGNORECASE,
)

_generation_lock = threading.Lock()
_generations = {}
_generation_sequence = itertools.count(1)


class _CompilerCheckCancelled(Exception):
    """A view closed or changed while its check was running."""


def _is_oreslang(view):
    if view is None or not view.is_valid() or view.size() == 0:
        return bool(view and view.file_name() and view.file_name().endswith(".ores"))
    return view.match_selector(0, "source.oreslang")


def _next_generation(view_id):
    with _generation_lock:
        # Unique across recycled Sublime view IDs, including after on_close
        # drops obsolete generation entries to avoid leaking closed tabs.
        value = next(_generation_sequence)
        _generations[view_id] = value
        return value


def _generation_is_current(view_id, value):
    with _generation_lock:
        return _generations.get(view_id) == value


def _settings():
    return sublime.load_settings(SETTINGS_FILE)


def _expand_command(view):
    configured = _settings().get("cli_command", ["oreslang", "check", "--format=json", "$file"])
    if isinstance(configured, str):
        configured = shlex.split(configured, posix=os.name != "nt")
    if (not isinstance(configured, list) or not configured or len(configured) > 64
            or any(not isinstance(part, str) or not part or len(part) > 4096
                   or chr(0) in part for part in configured)):
        raise ValueError("cli_command must be an array of 1-64 bounded, nonempty strings")

    filename = view.file_name()
    if not filename:
        raise ValueError("save the .ores file before running oreslang check")

    window = view.window()
    project = window.project_file_name() if window else None
    values = {
        "$file": filename,
        "$file_path": os.path.dirname(filename),
        "$file_name": os.path.basename(filename),
        "$project": project or "",
        "$project_path": os.path.dirname(project) if project else os.path.dirname(filename),
    }

    # Expand tokens in one pass. Sequential str.replace() corrupts
    # $file_path/$file_name via their $file prefix, and recursively expands
    # literal $project-like text appearing inside filenames and directories.
    placeholder = re.compile(r"\$(?:file_path|file_name|project_path|project|file)(?![A-Za-z0-9_])")
    return [
        placeholder.sub(lambda match: values[match.group(0)], str(raw))
        for raw in configured
    ]


def _text_coordinate(value):
    # Bound the decimal string before int(): Python may reject extremely long
    # integers, and an editor position must never be arbitrarily large.
    if not value.isascii() or not value.isdecimal() or len(value) > 8:
        return None
    number = int(value)
    return number if 1 <= number < 10_000_000 else None


def _resolve_diagnostic_path(reported_path, active_file):
    # Diagnostics are emitted relative to the CLI working directory (the file's
    # parent), not Sublime Text's process-wide working directory.
    if os.path.isabs(reported_path):
        return os.path.abspath(reported_path)
    return os.path.abspath(os.path.join(os.path.dirname(active_file), reported_path))


def _parse_diagnostics(output, default_file):
    diagnostics = []

    try:
        payload = json.loads(output)
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = None

    if isinstance(payload, dict):
        if type(payload.get("version")) is not int or payload["version"] != 1:
            return diagnostics
        records = payload.get("diagnostics")
        if not isinstance(records, list):
            return diagnostics
        for item in records:
            if not isinstance(item, dict):
                continue
            item_range = item.get("range") or {}
            if not isinstance(item_range, dict):
                continue
            start = item_range.get("start") or {}
            end = item_range.get("end") or {}
            if not isinstance(start, dict) or not isinstance(end, dict):
                continue

            def position(value, default):
                if value is None:
                    return default
                # bool is an int subclass; reject it along with floats,
                # negative values and implausibly large editor coordinates.
                if type(value) is not int or not 1 <= value <= 10_000_000:
                    return None
                return value

            row = position(start.get("line"), 1)
            column = position(start.get("column"), 1)
            if row is None or column is None:
                continue
            end_row = position(end.get("line"), row)
            end_column = position(end.get("column"), column + 1 if end_row == row else 1)
            if (end_row is None or end_column is None or end_column > 10_000_000
                    or end_row < row or (end_row == row and end_column <= column)):
                continue
            # Absent/null machine origins are unlocated; a present but
            # malformed origin must not forge diagnostics for this editor tab.
            path = item.get("path")
            if path is None:
                path = default_file
            elif not isinstance(path, str) or not path or "\0" in path:
                continue
            message = item.get("message")
            if not isinstance(message, str) or not message.strip():
                continue
            severity = item.get("severity")
            severity = severity.lower() if isinstance(severity, str) else "error"
            if severity not in ("error", "warning", "info", "hint"):
                severity = "error"
            diagnostics.append(
                {
                    "file": _resolve_diagnostic_path(path, default_file),
                    "line": row,
                    "column": column,
                    "end_line": end_row,
                    "end_column": end_column,
                    "severity": severity,
                    "message": message.strip(),
                }
            )
        return diagnostics

    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = _STANDARD_DIAGNOSTIC.match(line)
        if match:
            path, row, column, severity, message = match.groups()
            # NUL-bearing legacy origins cannot be valid editor file paths.
            if "\x00" in path:
                continue
            row, column = _text_coordinate(row), _text_coordinate(column)
            if row is None or column is None or column == 10_000_000:
                continue
            diagnostics.append(
                {
                    "file": _resolve_diagnostic_path(path, default_file) if path else default_file,
                    "line": row,
                    "column": column,
                    "end_line": row,
                    "end_column": column + 1,
                    "severity": (severity or "error").lower(),
                    "message": message.strip(),
                }
            )
            continue

        match = _ORESLANG_DIAGNOSTIC.search(line)
        if match:
            row, column, message = match.groups()
            row, column = _text_coordinate(row), _text_coordinate(column)
            if row is None or column is None or column == 10_000_000:
                continue
            diagnostics.append(
                {
                    "file": default_file,
                    "line": row,
                    "column": column,
                    "end_line": row,
                    "end_column": column + 1,
                    "severity": "error",
                    "message": message.strip(),
                }
            )
    return diagnostics


def _region_for_diagnostic(view, diagnostic):
    row = diagnostic["line"] - 1
    column = diagnostic["column"] - 1
    point = view.text_point(row, column, clamp_column=True)
    if point >= view.size():
        point = max(0, view.size() - 1)

    end_line = diagnostic.get("end_line")
    end_column = diagnostic.get("end_column")
    if end_line is not None and end_column is not None:
        end = view.text_point(end_line - 1, end_column - 1, clamp_column=True)
        if end > point:
            return sublime.Region(point, min(view.size(), end))

    word = view.word(point)
    if word.empty():
        end = min(view.size(), point + 1)
        return sublime.Region(point, end)
    return word


def _apply_diagnostics(view, diagnostics):
    if not view.is_valid():
        return

    current_file = os.path.abspath(view.file_name() or "")
    local = [
        item
        for item in diagnostics
        if not item["file"] or os.path.abspath(item["file"]) == current_file
    ]

    regions = [_region_for_diagnostic(view, item) for item in local]
    annotations = [
        "{}: {}".format(item["severity"], item["message"]) for item in local
    ]

    if not regions:
        view.erase_regions(DIAGNOSTIC_KEY)
        view.set_status("oreslang_diagnostics", "Oreslang: no diagnostics")
        return

    flags = sublime.DRAW_SQUIGGLY_UNDERLINE | sublime.DRAW_NO_FILL
    show_annotations = bool(_settings().get("show_diagnostic_annotations", True))

    try:
        view.add_regions(
            DIAGNOSTIC_KEY,
            regions,
            "invalid.illegal.oreslang",
            "",
            flags,
            annotations=annotations if show_annotations else [],
        )
    except TypeError:
        # Compatibility with older Sublime builds that predate annotations.
        view.add_regions(
            DIAGNOSTIC_KEY,
            regions,
            "invalid.illegal.oreslang",
            "",
            flags,
        )

    view.set_status(
        "oreslang_diagnostics",
        "Oreslang: {} diagnostic{}".format(len(regions), "" if len(regions) == 1 else "s"),
    )


def _show_output(view, command, return_code, output):
    window = view.window()
    if not window:
        return
    panel = window.create_output_panel("oreslang")
    panel.set_read_only(False)
    panel.run_command(
        "append",
        {
            "characters": "$ {}\nexit: {}\n\n{}\n".format(
                " ".join(shlex.quote(part) for part in command),
                return_code,
                output.rstrip(),
            )
        },
    )
    panel.set_read_only(True)
    window.run_command("show_panel", {"panel": "output.oreslang"})


def _terminate_process_tree(process):
    """Stop the POSIX CLI process group, including inherited-pipe helpers."""
    if os.name == 'posix' and process.pid:
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except ProcessLookupError:
            return
        except OSError:
            pass
    try:
        process.kill()
    except OSError:
        pass


def _run_compiler_bounded(argv, cwd, timeout, max_bytes=1024 * 1024, cancelled=None):
    if timeout <= 0 or max_bytes <= 0:
        raise ValueError('positive timeout and output budget required')
    process = subprocess.Popen(argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               start_new_session=(os.name == 'posix'))
    chunks = [bytearray(), bytearray()]
    lock = threading.Lock()
    exceeded = threading.Event()
    total = 0

    def drain(pipe, slot):
        nonlocal total
        try:
            while True:
                block = pipe.read(8192)
                if not block:
                    break
                with lock:
                    remaining = max_bytes - total
                    chunks[slot].extend(block[:max(0, remaining)])
                    total += len(block)
                    if total > max_bytes:
                        exceeded.set()
                        _terminate_process_tree(process)
        finally:
            pipe.close()

    readers = [threading.Thread(target=drain, args=(pipe, i), daemon=True)
               for i, pipe in enumerate((process.stdout, process.stderr))]
    for reader in readers:
        reader.start()
    deadline = time.monotonic() + timeout
    try:
        while True:
            if cancelled is not None and cancelled():
                _terminate_process_tree(process)
                process.wait()
                raise _CompilerCheckCancelled()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _terminate_process_tree(process)
                process.wait()
                raise subprocess.TimeoutExpired(argv, timeout)
            try:
                process.wait(timeout=min(0.05, remaining))
                break
            except subprocess.TimeoutExpired:
                continue
    finally:
        # Even a successful leader exit may leave helpers holding open pipes.
        _terminate_process_tree(process)
        for reader in readers:
            reader.join(timeout=1)
    if any(reader.is_alive() for reader in readers):
        raise RuntimeError('compiler output pipes remained open after process exit')
    if exceeded.is_set():
        raise RuntimeError('compiler output budget exceeded')
    return subprocess.CompletedProcess(argv, process.returncode,
                                       chunks[0].decode('utf-8'), chunks[1].decode('utf-8'))


def _run_check(view, force_output=False):
    if not _is_oreslang(view) or not view.file_name():
        return

    view_id = view.id()
    generation = _next_generation(view_id)
    if view.is_dirty():
        sublime.set_timeout(lambda: view.set_status(
            "oreslang_diagnostics", "Save the .ores file before running compiler checks"), 0)
        return
    starting_change = view.change_count()
    filename = os.path.abspath(view.file_name())

    try:
        command = _expand_command(view)
    except ValueError as error:
        sublime.set_timeout(lambda: view.set_status("oreslang_diagnostics", str(error)), 0)
        return

    try:
        timeout_ms = max(100, min(60000, int(_settings().get("diagnostics_timeout_ms", 15000))))
    except (ValueError, TypeError, OverflowError):
        timeout_ms = 15000
    cwd = os.path.dirname(filename)

    try:
        completed = _run_compiler_bounded(
            command, cwd, max(1.0, timeout_ms / 1000.0),
            cancelled=lambda: (not view.is_valid()
                or not _generation_is_current(view_id, generation)
                or view.change_count() != starting_change or view.is_dirty()
                or os.path.abspath(view.file_name() or "") != filename)
        )
        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        diagnostics = _parse_diagnostics(output, filename)
        return_code = completed.returncode
    except _CompilerCheckCancelled:
        # A closed/edited tab must not publish a stale error or open a panel.
        return
    except FileNotFoundError:
        output = "Oreslang CLI not found: {}".format(command[0])
        diagnostics = []
        return_code = 127
    except subprocess.TimeoutExpired:
        output = "oreslang check timed out after {} ms".format(timeout_ms)
        diagnostics = []
        return_code = 124
    except Exception as error:
        output = "Failed to run oreslang check: {}".format(error)
        diagnostics = []
        return_code = 1

    def finish():
        if (not view.is_valid() or not _generation_is_current(view_id, generation)
                or view.change_count() != starting_change or view.is_dirty()
                or os.path.abspath(view.file_name() or "") != filename):
            return
        _apply_diagnostics(view, diagnostics)

        show_on_error = bool(_settings().get("show_compiler_output_on_error", False))
        if force_output or (return_code != 0 and show_on_error):
            _show_output(view, command, return_code, output)

        if return_code != 0 and not diagnostics:
            view.set_status(
                "oreslang_diagnostics",
                "oreslang check failed; run Oreslang: Check File for output",
            )

    sublime.set_timeout(finish, 0)


class OreslangCheckFileCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        sublime.set_timeout_async(lambda: _run_check(self.view, force_output=True), 0)

    def is_enabled(self):
        return _is_oreslang(self.view) and bool(self.view.file_name())


class OreslangClearDiagnosticsCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        _next_generation(self.view.id())
        self.view.erase_regions(DIAGNOSTIC_KEY)
        self.view.erase_status("oreslang_diagnostics")


class OreslangDiagnosticsListener(sublime_plugin.EventListener):
    def on_load_async(self, view):
        if _is_oreslang(view):
            _next_generation(view.id())
            view.erase_regions(DIAGNOSTIC_KEY)
            view.erase_status("oreslang_diagnostics")

    def on_post_save_async(self, view):
        if _is_oreslang(view) and _settings().get("diagnostics_on_save", False):
            _run_check(view)

    def on_modified_async(self, view):
        if not _is_oreslang(view):
            return

        view_id = view.id()
        generation = _next_generation(view_id)
        # Even with automatic checks disabled, edits revoke old squigglies
        # and invalidate an explicit CLI check already running.
        view.erase_regions(DIAGNOSTIC_KEY)
        view.erase_status("oreslang_diagnostics")
        if not _settings().get("diagnostics_on_change", False):
            return
        try:
            delay = int(_settings().get("diagnostics_delay_ms", 650))
        except (ValueError, OverflowError, TypeError):
            delay = 650
        delay = max(0, min(5000, delay))

        def delayed():
            if view.is_valid() and _generation_is_current(view_id, generation):
                _run_check(view)

        sublime.set_timeout_async(delayed, max(0, delay))

    def on_close(self, view):
        with _generation_lock:
            _generations.pop(view.id(), None)
