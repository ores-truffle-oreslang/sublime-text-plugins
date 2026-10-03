import json
import os
import re
import shlex
import subprocess
import threading

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


def _is_oreslang(view):
    if view is None or not view.is_valid() or view.size() == 0:
        return bool(view and view.file_name() and view.file_name().endswith(".ores"))
    return view.match_selector(0, "source.oreslang")


def _next_generation(view_id):
    with _generation_lock:
        value = _generations.get(view_id, 0) + 1
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
    if not isinstance(configured, list) or not configured:
        raise ValueError("cli_command must be a non-empty string or array")

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

    command = []
    for raw in configured:
        value = str(raw)
        for token, replacement in values.items():
            value = value.replace(token, replacement)
        command.append(value)
    return command


def _parse_diagnostics(output, default_file):
    diagnostics = []

    try:
        payload = json.loads(output)
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = None

    if isinstance(payload, dict) and payload.get("version") == 1:
        for item in payload.get("diagnostics", []):
            if not isinstance(item, dict):
                continue
            start = (item.get("range") or {}).get("start") or {}
            path = item.get("path") or default_file
            message = str(item.get("message") or "").strip()
            if not message:
                continue
            diagnostics.append(
                {
                    "file": os.path.abspath(path),
                    "line": max(1, int(start.get("line", 1))),
                    "column": max(1, int(start.get("column", 1))),
                    "severity": str(item.get("severity") or "error").lower(),
                    "message": message,
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
            diagnostics.append(
                {
                    "file": os.path.abspath(path) if path else default_file,
                    "line": max(1, int(row)),
                    "column": max(1, int(column)),
                    "severity": (severity or "error").lower(),
                    "message": message.strip(),
                }
            )
            continue

        match = _ORESLANG_DIAGNOSTIC.search(line)
        if match:
            row, column, message = match.groups()
            diagnostics.append(
                {
                    "file": default_file,
                    "line": max(1, int(row)),
                    "column": max(1, int(column)),
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


def _run_check(view, force_output=False):
    if not _is_oreslang(view) or not view.file_name():
        return

    view_id = view.id()
    generation = _next_generation(view_id)
    filename = os.path.abspath(view.file_name())

    try:
        command = _expand_command(view)
    except ValueError as error:
        sublime.set_timeout(lambda: view.set_status("oreslang_diagnostics", str(error)), 0)
        return

    timeout_ms = int(_settings().get("diagnostics_timeout_ms", 15000))
    cwd = os.path.dirname(filename)

    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=max(1.0, timeout_ms / 1000.0),
            check=False,
        )
        output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
        diagnostics = _parse_diagnostics(output, filename)
        return_code = completed.returncode
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
        if not view.is_valid() or not _generation_is_current(view_id, generation):
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
            view.erase_regions(DIAGNOSTIC_KEY)

    def on_post_save_async(self, view):
        if _is_oreslang(view) and _settings().get("diagnostics_on_save", True):
            _run_check(view)

    def on_modified_async(self, view):
        if not _is_oreslang(view) or not _settings().get("diagnostics_on_change", False):
            return

        view_id = view.id()
        generation = _next_generation(view_id)
        delay = int(_settings().get("diagnostics_delay_ms", 650))

        def delayed():
            if view.is_valid() and _generation_is_current(view_id, generation):
                _run_check(view)

        sublime.set_timeout_async(delayed, max(0, delay))

    def on_close(self, view):
        _next_generation(view.id())
