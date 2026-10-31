"""Offline editor fixture validation; never fetch private compiler sources."""
import json
import pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "conformance" / "oreslang-syntax-v1.json").read_text(encoding="utf8"))
authority = manifest["authority"]
allowed = {"docs/grammar.ebnf", "src/main/java/dev/oreslang/parser/Lexer.java"}
if manifest["schema"] != "oreslang.editor-syntax-conformance/v1" or authority["repo"] != "ores-truffle-oreslang/oreslang-source.java":
    raise ValueError("invalid editor authority")
if {e["path"] for e in authority["files"]} != allowed:
    raise ValueError("invalid source paths")
if any(len(e["gitBlobSha"]) != 40 or any(c not in "0123456789abcdef" for c in e["gitBlobSha"]) for e in authority["files"]):
    raise ValueError("invalid pinned Git blob")
if len(manifest["cases"]) != 50 or len({x["id"] for x in manifest["cases"]}) != 50:
    raise ValueError("expected 50 distinct editor syntax fixtures")
print("Offline editor manifest passed; no private compiler source fetched.")
