"""Build src/ws_mcp/data/api_index.json (dev-time only).

Inputs (not shipped): our api-cheatsheet.md and a local copy of the public WSUS tree
(https://wsunitstats.com/en/modding, snapshot of game 258.4018). Only names, paths and
signatures are taken from WSUS (no values / game data); notes come from our own cheatsheet.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

WSUS_ATTR = "wsunitstats.com WSUS API tree, game 258.4018 (10.10.2026) — https://wsunitstats.com/en/modding"


def walk(node, path, out):
    k = str(node.get("k"))
    seg = "[n]" if k.isdigit() else k
    p = (f"{path}{seg}" if seg == "[n]" else f"{path}.{seg}") if path else seg
    tp = node.get("tp")
    if tp == "func":
        out.setdefault(p, {"kind": "function", "path": p, "name": k, "signature": f"{k}{node.get('v', '')}"})
    elif tp not in ("root", "folder", "home"):
        out.setdefault(p, {"kind": "field", "path": p, "name": k, "type": tp})
    for c in node.get("ch") or []:
        if str(c.get("k")).isdigit() and int(c["k"]) > 0:
            continue  # array elements: keep only the first as [n]
        walk(c, p, out)


def wsus_entries(wsus_dir: Path):
    out: dict[str, dict] = {}
    for f in sorted(wsus_dir.glob("*.json")):
        if f.name == "home.json":
            continue
        base = f.stem.replace("gameplay.root.", "root.").replace("visual.root.", "visual.root.")
        data = json.loads(f.read_text(encoding="utf-8"))
        for n in data if isinstance(data, list) else [data]:
            walk(n, base, out)
    home = json.loads((wsus_dir / "home.json").read_text(encoding="utf-8"))
    for folder in home["ch"]:
        prefix = "root" if folder["k"] == "gameplay" else "visual.root"
        for n in folder["ch"][0]["ch"]:
            walk(n, prefix, out)
    entries = list(out.values())
    for e in entries:
        e["source"] = WSUS_ATTR
        if e["path"].startswith("root.scripts.") and e.get("type") == "num" and e["path"].count(".") == 2:
            e["kind"] = "event"
            e["text"] = "Engine event (mod hook name), from root.scripts"
    return entries


def cheatsheet_entries(md: Path):
    entries, section = [], ""
    for line in md.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            section = line.lstrip("#").strip()
            continue
        s = line.strip()
        if s.startswith(("- ", "* ")) or re.match(r"^\d+\. ", s):
            text = re.sub(r"^(- |\* |\d+\. )", "", s)
            if len(text) < 15:
                continue
            names = re.findall(r"`([^`]+)`", text)
            entries.append({
                "kind": "note",
                "name": names[0] if names else "",
                "path": "",
                "section": section,
                "text": text,
                "source": "api-cheatsheet.md (war-selection research, sources in [D: #channel, date] tags)",
            })
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cheatsheet", default="../api-cheatsheet.md")
    ap.add_argument("--wsus", default="../discord/ext/wsus")
    ap.add_argument("--out", default="src/ws_mcp/data/api_index.json")
    a = ap.parse_args()
    entries = wsus_entries(Path(a.wsus)) + cheatsheet_entries(Path(a.cheatsheet))
    doc = {
        "about": "API index for war-selection-mcp. WSUS names/signatures with attribution; notes are ours.",
        "wsus_attribution": WSUS_ATTR,
        "count": len(entries),
        "entries": entries,
    }
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    kinds = {}
    for e in entries:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    print(a.out, kinds)


if __name__ == "__main__":
    main()
