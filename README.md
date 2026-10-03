# Oreslang for Sublime Text

Sublime Text 4 support for Oreslang:

- `.ores` syntax highlighting;
- one canonical scope for language keywords;
- a separate scope for global control forms;
- compiler-backed error squigglies and inline annotations;
- an `Oreslang: Check File` command;
- an `ores --check` build target.

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

The bundled **Oreslang Magenta** color scheme pins those scopes to:

- keywords: magenta `#FF00FF`;
- global controls: royal blue `#4169E1`.

Select it with **Preferences → Select Color Scheme → Oreslang Magenta** when you
want the exact canonical colors. Other Sublime color schemes still receive the
stable Oreslang scopes and may style them differently.

## Compiler diagnostics

The plugin defaults to:

```text
ores --check $file
```

Diagnostics in this shape are converted into Sublime squigglies and inline
annotations:

```text
/path/to/file.ores:12:7: error: expected expression
```

The Oreslang compiler's native lexer/parser messages are also recognized.

By default diagnostics run after save. To enable debounced checks while typing,
customize `Oreslang.sublime-settings`:

```json
{
  "diagnostics_on_save": true,
  "diagnostics_on_change": true,
  "diagnostics_delay_ms": 650,
  "compiler_command": ["ores", "--check", "$file"]
}
```

The compiler command is an argument array, not a shell command. Supported
substitutions are `$file`, `$file_path`, `$file_name`, `$project`, and
`$project_path`.

## Commands

Open the command palette and use:

- **Oreslang: Check File** — run the compiler immediately and show its output;
- **Oreslang: Clear Diagnostics** — remove current squigglies.

Sublime's normal **Build** command also uses `ores --check` for Oreslang files.

## Development

Run the package contract tests with:

```bash
python -m unittest discover -s tests -v
python -m py_compile oreslang.py
```

The tests pin the requested magenta keyword set, royal-blue global set, exact
hex colors, JSON resources, and diagnostic parser formats.
