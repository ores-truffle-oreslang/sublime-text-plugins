"""Read-only weekly compiler-grammar drift check. No upstream code execution."""
import hashlib
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
manifest = json.loads((ROOT / "conformance" / "oreslang-syntax-v1.json").read_text())
authority = manifest["authority"]
allowed = {"docs/grammar.ebnf", "src/main/java/dev/oreslang/parser/Lexer.java"}
if (manifest["schema"] != "oreslang.editor-syntax-conformance/v1"
        or authority["repo"] != "ores-truffle-oreslang/oreslang-source.java"
        or {entry["path"] for entry in authority["files"]} != allowed):
    raise ValueError("invalid syntax authority")
for entry in authority["files"]:
    if len(entry["gitBlobSha"]) != 40 or any(ch not in "0123456789abcdef" for ch in entry["gitBlobSha"]):
        raise ValueError("invalid compiler blob SHA")
if "--live" in sys.argv:
    bad = False
    for entry in authority["files"]:
        url = "https://raw.githubusercontent.com/" + authority["repo"] + "/main/" + entry["path"]
        with urllib.request.urlopen(url, timeout=15) as response:
            content = response.read(1024 * 1024 + 1)
        if len(content) > 1024 * 1024:
            raise ValueError("upstream compiler source exceeds 1 MiB")
        got = hashlib.sha1(b"blob " + str(len(content)).encode("ascii") + b"\0" + content).hexdigest()
        print(entry["path"], "pinned", entry["gitBlobSha"], "current", got)
        if got != entry["gitBlobSha"]:
            bad = True
    if bad:
        raise SystemExit("compiler grammar drift: review and coordinate all three editor manifests")
else:
    print("Validated local compiler source pin (offline; not a live check).")
