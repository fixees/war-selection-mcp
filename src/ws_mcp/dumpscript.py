"""Generator for the in-game Lua script that dumps the `root` API tree into gen/log.txt.

The script is read-only on the engine side: it indexes fields (wrapped in pcall) and never calls
f_* functions. Output format (one record per log line, tab separated, see docs/api-dump.md):

    WSDUMP <id> B <format> <space> <root> <options>     begin
    WSDUMP <id> N <path> <type> <value>                 node (type: num str bool func obj arr nil err)
    WSDUMP <id> X <path> <obj|arr> <size>               node was expanded (its children were probed)
    WSDUMP <id> R <path>  ... native log(obj) ...  WSDUMP <id> r <path>
    WSDUMP <id> W <message>                             warning
    WSDUMP <id> E <count> <ok|truncated|error> <raw>    end

Array elements are sampled (index 0 by default) and written as `[]`.
"""

from __future__ import annotations

import re
import secrets
from importlib import resources
from typing import Any, Iterable


FORMAT = "1"
SHIPPED_ID = "wsdump01"
ROOT_PATH_RE = re.compile(r"^root(\.[A-Za-z_][A-Za-z0-9_]*|\[\d+\])*$")
DEFAULT_TOTABLE_SKIP = ("root.scene", "root.session.visual.scene")
SPACES = ("gameplay", "visual")


def _version() -> str:
    from . import __version__
    return __version__


def _lua_str(s: str) -> str:
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _template() -> str:
    return resources.files("ws_mcp").joinpath("data/wsdump.lua.in").read_text(encoding="utf-8")


def seeds_from_index(entries: Iterable[dict[str, Any]], space: str, root: str = "root") -> dict[str, list[str]]:
    """Known child names per normalized parent path, from API index entries of one space.

    Seeds make the script probe every known name even when the engine does not allow pairs()
    on its objects, so names missing in the live engine are reported as nil (removed).
    """
    prefix = "visual." if space == "visual" else ""
    nroot = re.sub(r"\[\d+\]", "[]", root)
    out: dict[str, set[str]] = {}
    for e in entries:
        p = e.get("path") or ""
        if e.get("kind") == "note" or not p:
            continue
        if prefix:
            if not p.startswith("visual.root"):
                continue
            p = p[len(prefix):]
        elif not p.startswith("root"):
            continue
        p = p.replace("[n]", "[]")
        if p.endswith("[]"):
            continue
        parent, _, name = p.rpartition(".")
        if not parent or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name):
            continue
        if parent != nroot and not parent.startswith(nroot + ".") and not parent.startswith(nroot + "["):
            continue
        out.setdefault(parent, set()).add(name)
    return {k: sorted(v) for k, v in sorted(out.items())}


def _cfg_literal(cfg: dict[str, Any]) -> str:
    parts = []
    for k, v in cfg.items():
        if isinstance(v, bool):
            val = "true" if v else "false"
        elif isinstance(v, (int, float)):
            val = str(v)
        elif isinstance(v, (list, tuple)):
            val = "{" + ", ".join(_lua_str(x) for x in v) + "}"
        else:
            val = _lua_str(str(v))
        parts.append(f"{k} = {val}")
    return "{ " + ", ".join(parts) + " }"


def _seeds_literal(seeds: dict[str, list[str]], compact: bool) -> str:
    if not seeds:
        return "{}"
    sep = " " if compact else "\n"
    body = ("," + sep).join(f"[{_lua_str(k)}] = {_lua_str(','.join(v))}" for k, v in seeds.items())
    return "{" + sep + body + sep + "}"


def compact_lua(src: str) -> str:
    """Strip full-line comments and indentation and join into one line.

    Safe for the bundled template only: it has no long strings, no trailing comments and
    no line that starts with '(' (which would merge with the previous expression).
    """
    lines = []
    for line in src.splitlines():
        s = line.strip()
        if not s or s.startswith("--"):
            continue
        lines.append(s)
    return " ".join(lines)


def render(root: str = "root", space: str = "gameplay", depth: int = 12, max_nodes: int = 20000,
           array_sample: int = 1, raw: bool = True, max_raw: int = 4000, raw_array_max: int = 64,
           seeds: bool = True, to_table: bool = True, tostring_keys: bool = True, compact: bool = False, autorun: bool = True,
           batch: int = 20, dump_id: str | None = None,
           index_entries: Iterable[dict[str, Any]] | None = None) -> dict[str, Any]:
    if not ROOT_PATH_RE.match(root):
        raise ValueError("root must look like 'root', 'root.unitType[0]' or 'root.session.visual'.")
    if space not in SPACES:
        raise ValueError("space must be 'gameplay' or 'visual'.")
    if dump_id is not None and not re.match(r"^[A-Za-z0-9]{1,16}$", dump_id):
        raise ValueError("dump_id: 1-16 letters/digits.")
    did = dump_id or secrets.token_hex(4)
    cfg = {
        "format": FORMAT,
        "id": did,
        "root": root,
        "space": space,
        "depth": max(1, min(int(depth), 40)),
        "maxNodes": max(10, min(int(max_nodes), 500_000)),
        "arraySample": max(1, min(int(array_sample), 16)),
        "raw": bool(raw),
        "maxRaw": max(0, min(int(max_raw), 100_000)),
        "rawArrayMax": max(0, min(int(raw_array_max), 10_000)),
        "toTable": bool(to_table),
        "toTableSkip": list(DEFAULT_TOTABLE_SKIP),
        "seeds": bool(seeds),
        "tostringKeys": bool(tostring_keys),
        "batch": max(1, min(int(batch), 200)),
        "maxValue": 160,
        "maxRepeat": 2,
    }
    seed_map = seeds_from_index(index_entries or [], space, root) if seeds else {}
    src = (_template()
           .replace("@@VERSION@@", _version())
           .replace("@@CFG@@", _cfg_literal(cfg))
           .replace("@@SEEDS@@", _seeds_literal(seed_map, compact))
           .replace("@@AUTORUN@@", "wsdump()" if autorun else "-- call WSDUMP_RUN() or WSDUMP_RUN(\"root.unitType[0]\") to run"))
    if compact:
        src = compact_lua(src)
    return {
        "dump_id": did,
        "space": space,
        "root": root,
        "compact": compact,
        "seed_parents": len(seed_map),
        "seed_names": sum(len(v) for v in seed_map.values()),
        "bytes": len(src.encode("utf-8")),
        "lines": src.count("\n") + 1,
        "script": src,
    }


HOW_TO_RUN = [
    "Developer mode works only on your own map: map editor -> your map -> modifications -> add a "
    "modification (gameplay for space=gameplay, visual for space=visual) -> start the map.",
    "Variant A (mod, any size): modifications -> your mod -> edit script, paste the full script, save. "
    "Top-level code runs when the mod is saved/loaded, so the dump is written immediately. Remove the "
    "script from the mod afterwards: it runs again on every load.",
    "Variant B (console, F8): paste the compact one-line variant (compact=true, seeds=false keeps it short). "
    "Console line length limits are not documented; if the paste is cut, use variant A.",
    "Then call import_api_dump (reads gen/log.txt, never writes to the game folder).",
]
