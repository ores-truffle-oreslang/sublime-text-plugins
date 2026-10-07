# Compiler compatibility: October 6, 2026

Update Sublime syntax and unit expectations for match/select, loop and channel vocabulary.

Upstream compiler PRs under review: [#398](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/398), [#399](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/399), [#404](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/404), [#405](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/405), [#406](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/406), [#408](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/408), [#409](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/409), [#410](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/410), [#411](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/411), [#412](https://github.com/ores-truffle-oreslang/oreslang-source.java/pull/412).

The editor grammar is deliberately liberal: syntax highlighting must not promise compiler acceptance. Both legacy `case readch input: val item { ... }` and proposed `case val item = readch(input) -> { ... }` are still highlighted without rewriting source. `const`, `val`, `let` and `mut` are orthogonal binding controls. An actor mailbox cannot carry callable references, regardless of how editor tokens are colored.

## Required follow-up
- Run editor grammar/package tests and validate nested match/select braces and comment/string boundaries.
- Surface nonfatal compiler warning `W-SELECT-RETURN` without converting it into an error.
- Keep compile/check behavior tied to a known compiler SHA. Do not silently enable unreleased features on stable users.
- Once compiler PRs merge, update language-server semantic tokens, snippets and completion separately.
