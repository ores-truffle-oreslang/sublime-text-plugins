# Oreslang for Sublime Text

Sublime Text 4 support for Oreslang:

- `.ores` syntax highlighting;
- one canonical scope for language keywords;
- a separate scope for global control forms;
- compiler-backed error squigglies and inline annotations;
- an `Oreslang: Check File` command;
- an `oreslang check` build target.

## Color contract

Oreslang intentionally does **not** split language keywords across scopes such as
`storage.modifier`, `keyword.control`, and `storage.type`. Every syntax keyword
uses:

```
keyword.oreslang
```

That includes forms such as:

```ores
pub fnc void class module return if else elif fi case match switch try catch select
```

Global control forms use a separate scope:

```
support.function.global.oreslang
```

Currently:

```ores
recover defer throw raise
```

The package uses standard, stable Sublime scopes so it works with any color
scheme. Package Control asks language-syntax packages not to bundle a
language-specific color scheme.

If you want Oreslang's canonical colors, use **Preferences → Customize Color
Scheme** and add these rules to your user color scheme:

```json
{
  "rules": [
    {
      "scope": "keyword.oreslang",
      "foreground": "#FF00FF"
    },
    {
      "scope": "support.function.global.oreslang",
      "foreground": "#4169E1"
    }
  ]
}
```

That preserves exact magenta for language keywords and royal blue for
`recover`, `defer`, `throw`, and `raise` without making the syntax package
depend on a bundled theme.

## Compiler diagnostics

The plugin defaults to:

```text
oreslang check --format=json $file
```

Diagnostics in this shape are converted into Sublime squigglies and inline
annotations:

```text
/path/to/file.ores:12:7: error: expected expression
```

The canonical `oreslang` CLI protocol v1 JSON is preferred; plain compiler-style diagnostics remain a compatibility fallback.

By default diagnostics run after save. To enable debounced checks while typing,
customize `Oreslang.sublime-settings`:

```json
{
  "diagnostics_on_save": true,
  "diagnostics_on_change": true,
  "diagnostics_delay_ms": 650,
  "cli_command": ["oreslang", "check", "--format=json", "$file"]
}
```

The CLI command is an argument array, not a shell command. Supported
substitutions are `$file`, `$file_path`, `$file_name`, `$project`, and
`$project_path`.

## Commands

Open the command palette and use:

- **Oreslang: Check File** — run `oreslang check` immediately and show its output;
- **Oreslang: Clear Diagnostics** — remove current squigglies.

Sublime's normal **Build** command uses `oreslang check` for Oreslang files. The package never invokes `ORESoftware/ores-cli` or a command named `ores`.

## Development

Run the package contract tests with:

```bash
python -m unittest discover -s tests -v
python -m py_compile oreslang.py
```

The tests pin the requested magenta keyword set, royal-blue global set, exact
hex colors, JSON resources, and diagnostic parser formats.

### Compiler compatibility

The editor grammar tracks proposed compiler constructs without changing compiler acceptance. See [docs/compiler-pr-sync.md](docs/compiler-pr-sync.md) for the October 2026 upstream PR matrix and validation gates.
