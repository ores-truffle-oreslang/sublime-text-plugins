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

For safety, compiler subprocesses do not run automatically by default: Sublime Text does not provide a VS Code-style workspace trust gate. Use **Oreslang: Check File** manually, or explicitly enable checks after saving a trusted project. To opt into save-time and debounced checks,
customize `Oreslang.sublime-settings`:

```json
{
  "diagnostics_on_save": true,
  "diagnostics_on_change": true,
  "diagnostics_delay_ms": 650,
  "cli_command": ["oreslang", "check", "--format=json", "$file"]
}
```

The CLI command is an argument array, not a shell command. Compiler results are discarded when a buffer changes during a run; command timeouts and output are bounded. Supported
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

## Cross-editor syntax fixtures and grammar drift

`conformance/oreslang-syntax-v1.json` is the byte-identical lexical fixture
manifest copied to the VS Code and HTML highlighter repositories.
`tests/test_conformance.py` checks keywords, exclusions, hash Symbols,
compound keywords, grammar precedence, and removed operator scopes using
standard-library Python. It cannot run Sublime's actual syntax engine,
and must not be reported as editor UI testing or guest compilation.

The fixture pins concrete blob hashes from the Java lexer and EBNF.
The pinned compiler still recognizes `isoactor`, `null`, `%` and `^`;
the forward-looking editor target does not. This is an unresolved semantic
parity delta, not authority to change the compiler automatically.

The shared suite now includes **50 adversarial editor fixtures**.

**Privacy boundary:** The compiler source repository is private.
Unauthenticated raw.githubusercontent.com requests cannot verify it.
Public editor workflows must not clone, mirror, or fetch private sources.
The scheduled watcher was removed; compiler-side lexer/parser proof is
staged separately in private oreslang-source.java PR #2350 and currently
has zero executed CI steps. Source-only grammar host tests are not evidence
of actual Sublime engine behavior or Oreslang guest acceptance.

## Sublime native syntax test fixture

Install the package as `Packages/Oreslang`, open `syntax_test_oreslang.ores` in Sublime Text, and invoke **Tools → Build** to run Sublime's native Syntax Tests. The fixture contains scope assertions for opaque comments, templates, Symbols, compound keywords and contextual comparisons. CI presently checks only fixture integrity; **no real Sublime Text binary executed this fixture in GitHub Actions**.

### Real Sublime syntax engine CI

The `sublime-syntax-engine` job uses the pinned `SublimeText/syntax-test-action` v2.5.1 implementation with a stable Sublime syntax test binary and `package_name: Oreslang`. Unlike Python fixture-inventory tests, this job executes the `syntax_test_oreslang.ores` scope selectors using the native Sublime syntax engine. Treat it as proven only after the dedicated job reports nonzero executed steps and a successful result.

## Explicit compiler-current default and language-target preview

`Oreslang.sublime-syntax` remains the current compiler-lexer compatibility grammar. `Preview.sublime-syntax` is a distinct **test-only** proposal (file extension `.ores-target-preview`), and the native `syntax_test_oreslang.ores` now selects it explicitly so its contextual-operator and deprecated-token expectations cannot silently override regular `.ores` syntax. The two profiles are pinned in `contracts/editor-syntax/v1/profile-reconciliation.json`; compiler JUnit/guest evidence is still unavailable and independent review remains required.

## Installing the verified Sublime package

Successful CI runs upload an **oreslang-sublime-package** Actions artifact. Download the artifact, unzip the outer GitHub artifact ZIP, and copy its **Oreslang.sublime-package** file (without further extraction) into the Sublime Text `Installed Packages` folder:

- Windows: `%APPDATA%\Sublime Text\Installed Packages`
- macOS: `~/Library/Application Support/Sublime Text/Installed Packages/`
- Linux: `~/.config/sublime-text/Installed Packages/`

Restart Sublime Text and open a `.ores` file. The native syntax and the package's Python diagnostics are included, but compiler diagnostics still require an installed, trusted `oreslang` CLI. GitHub Actions packaging tests do **not** substitute for real Sublime Text host validation.

To build locally:

~~~sh
python -m unittest discover -s tests -v
python tools/package_sublime.py
~~~

The package is created deterministically in `dist/Oreslang.sublime-package`, with a fixed file allowlist and byte-by-byte verification. No compiler source or credentials are copied into the package.

## Repository ownership and migration (2026-11-08)

**AttoLang** is the public language name; the current repository is still `ores-truffle-oreslang/sublime-text-plugins` (legacy namespace). Preserve existing `oreslang-*` identifiers, old commands and `.ores` compatibility until migration and feature support are independently verified.

- **Belongs here:** Sublime Text grammar/highlighting and developer integration.
- **Does not belong here:** language runtime implementation or AttoCo cloud billing.
- **Ownership:** [`atto-lang`](https://github.com/atto-lang) owns language, compiler, tooling, portable core/std, conformance and developer ecosystem; [`atto-co`](https://github.com/atto-co) owns separately governed hosted runtime, deployment, identity, billing and cloud operations. An existing similarly named `atto-*` repo does not automatically contain this repo's code or retain its numeric identity.
- **Proposed first destination:** `atto-lang/sublime-text-plugins` via an approved *GitHub repository transfer* preserving numeric ID/history/name. The existing plan authorizes **no** direct legacy-org transfer to `atto-co`; future product spinouts need their own approval.

**Cutover instructions:** coordinate in [migration issue #26](https://github.com/ores-truffle-oreslang/.github/issues/26) and consult the private [runbook draft #25](https://github.com/ores-truffle-oreslang/.github/pull/25). Require named source/target admins and independent security reviewer, exact head SHA/tree, target protection/rulesets, permissions, Actions and actual executed steps, secrets, releases, Pages, packages, apps, webhooks, open PRs, consumers and rollback owner before any transfer; never mirror private code without separate authorization. Verify unchanged GitHub ID/tree and control parity afterward, update clients separately, and execute exact-head tests. Zero-step Actions are `NOT_EXECUTED`; host-only checks are not compiled-guest evidence. No forced language/CLI rename or production capability claims.
