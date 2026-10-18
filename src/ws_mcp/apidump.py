"""Import of WSDUMP records (written by the dump script into gen/log.txt) into a live API index.

The live index is stored in the per-user data folder (Config.data_dir), never in the game folder.
search_api and lint_mod use it in preference to the bundled WSUS v258.4018 index.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Any

from .config import Config

LIVE_FILE = "api_index_live.json"
PREV_FILE = "api_index_live.prev.json"
DIFF_FILE = "api_dump_diff.json"
LIVE_FORMAT = 1
MAX_LOG_BYTES = 300_000_000

TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} ?")
ENGINE_RE = re.compile(r"^Engine Version:\s*(\S+)")
GAME_RE = re.compile(r"^Game Version:\s*(\S+)")
RAW_LINE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*|\d+): ?(.*)$")
PATH_RE = re.compile(r"^root(\.[A-Za-z_][A-Za-z0-9_]*|\[\])*$")
NODE_TYPES = {"num", "str", "bool", "func", "obj", "arr", "nil", "err", "link"}
UNESC = {"\\": "\\", "t": "\t", "r": "\r", "n": "\n"}


class DumpError(Exception):
    pass


def _unescape(s: str) -> str:
    return re.sub(r"\\(.)", lambda m: UNESC.get(m.group(1), m.group(0)), s)


def _new_dump(did: str, line_no: int) -> dict[str, Any]:
    return {"id": did, "begin_line": None, "end_line": None, "first_line": line_no, "header": None,
            "space": None, "root": None, "options": {}, "nodes": {}, "expanded": {}, "raw": {},
            "warnings": [], "complete": False, "status": None, "count": None, "malformed": 0,
            "engine_version": None, "game_version": None}


def parse_dumps(text: str) -> list[dict[str, Any]]:
    """Parse every WSDUMP dump in a log text. Tolerates timestamps, CRLF, foreign lines,
    malformed records, interleaved dumps and dumps truncated before their END record."""
    dumps: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    engine = game = None
    raw_open: tuple[str, str] | None = None
    for no, line in enumerate(text.splitlines(), 1):
        line = line.rstrip("\r")
        body = TS_RE.sub("", line, count=1)
        if not body.startswith("WSDUMP\t"):
            if raw_open:
                m = RAW_LINE_RE.match(body)
                if m:
                    dumps[raw_open[0]]["raw"][raw_open[1]].append((m.group(1), m.group(2)))
                continue
            m = ENGINE_RE.match(body)
            if m:
                engine = m.group(1)
            m = GAME_RE.match(body)
            if m:
                game = m.group(1)
            continue
        f = body.split("\t")
        if len(f) < 3 or not re.match(r"^[A-Za-z0-9]{1,16}$", f[1]):
            continue
        did, rec, args = f[1], f[2], f[3:]
        if rec == "B" and did in dumps and dumps[did]["header"] is not None:
            # the same script was run again: keep the earlier run under a suffixed key
            n = sum(1 for k in dumps if k.split("~")[0] == did)
            old = dumps.pop(did)
            old["run"] = n
            dumps[f"{did}~{n}"] = old
            order[order.index(did)] = f"{did}~{n}"
        if did not in dumps:
            dumps[did] = _new_dump(did, no)
            order.append(did)
        d = dumps[did]
        if rec != "r" and raw_open and raw_open[0] == did:
            raw_open = None  # raw block was not closed (truncated log): close it implicitly
        if rec == "B" and len(args) >= 4:
            opts = dict(kv.split("=", 1) for kv in args[3].split(";") if "=" in kv)
            d.update(begin_line=no, header=args[0], space=args[1], root=args[2], options=opts,
                     engine_version=engine, game_version=game)
        elif rec == "N" and len(args) >= 2 and PATH_RE.match(args[0]) and args[1] in NODE_TYPES:
            d["nodes"][args[0]] = (args[1], _unescape(args[2]) if len(args) > 2 else "")
        elif rec == "X" and len(args) >= 1 and PATH_RE.match(args[0]):
            d["expanded"][args[0]] = args[1] if len(args) > 1 else "obj"
        elif rec == "R" and len(args) >= 1 and PATH_RE.match(args[0]):
            d["raw"][args[0]] = []
            raw_open = (did, args[0])
        elif rec == "r" and len(args) >= 1:
            if raw_open and raw_open[0] == did:
                d.setdefault("raw_closed", set()).add(raw_open[1])
            raw_open = None
        elif rec == "W":
            d["warnings"].append(_unescape("\t".join(args)))
        elif rec == "E" and len(args) >= 2:
            d.update(complete=True, end_line=no, count=int(args[0]) if args[0].isdigit() else None, status=args[1])
        else:
            d["malformed"] += 1
    out = []
    for did in order:
        d = dumps[did]
        d["raw_closed"] = sorted(d.get("raw_closed", set()))
        out.append(d)
    return out


# ---------------------------------------------------------------- entries

def _to_index_path(p: str, space: str) -> str:
    p = p.replace("[]", "[n]")
    return ("visual." + p) if space == "visual" else p


def _name(p: str) -> str:
    if p.endswith("[n]"):
        return "0"
    return p.rsplit(".", 1)[-1]


def parent_path(p: str) -> str:
    if p.endswith("[n]"):
        return p[:-3]
    return p.rsplit(".", 1)[0] if "." in p else ""


def _raw_type(value: str) -> tuple[str, str | None]:
    v = value.strip()
    if v.startswith("("):
        return "func", v
    if v == "{...}" or v.startswith("{"):
        return "obj", None
    if re.match(r"^\[\d*\]$", v):
        return "arr", v[1:-1]
    if v in ("true", "false"):
        return "bool", None
    if re.match(r"^-?\d+(\.\d+)?$", v):
        return "num", None
    return "str", None


def _detect_space(d: dict[str, Any]) -> str | None:
    if d.get("root") != "root":
        return None
    keys = {p.split(".")[1] for p in d["nodes"] if p.count(".") >= 1 and d["nodes"][p][0] not in ("nil", "err")}
    keys |= {k for k, _ in d["raw"].get("root", [])}
    if "unitType" in keys or "scene" in keys:
        return "gameplay"
    if "interface" in keys or "session" in keys:
        return "visual"
    return None


def dump_entries(d: dict[str, Any], space: str, source: str) -> tuple[dict[str, dict], set[str], set[str], list[str]]:
    """Return (entries by index path, expanded index paths, absent index paths, unexplored concrete paths)."""
    entries: dict[str, dict[str, Any]] = {}
    absent: set[str] = set()

    def put(path: str, tp: str, sig: str | None = None) -> None:
        ip = _to_index_path(path, space)
        name = _name(ip)
        prev = entries.get(ip) or {}
        if tp == "func":
            if sig:
                signature = f"{name}{sig}"
            else:
                signature = prev.get("signature") or f"{name}(?)"
            new: dict[str, Any] = {"kind": "function", "path": ip, "name": name, "signature": signature}
        else:
            new = {"kind": "field", "path": ip, "name": name, "type": "obj" if tp in ("arr", "link") else tp}
            if tp == "arr" or prev.get("array"):
                new["array"] = True
            if tp == "link":
                new["link"] = True
        depth = ip.count(".") - (1 if space == "visual" else 0)
        if tp == "num" and depth == 2 and ip.split(".")[-2] == "scripts":
            new["kind"] = "event"
            new["text"] = "Engine event (mod hook name), from root.scripts"
        new["source"] = source
        entries[ip] = new

    for path, (tp, val) in d["nodes"].items():
        if path == "root":
            continue
        if tp == "nil":
            absent.add(_to_index_path(path, space))
            continue
        if tp == "err":
            continue
        put(path, tp)
    for parent, lines in d["raw"].items():
        for key, value in lines:
            tp, extra = _raw_type(value)
            path = f"{parent}[]" if key.isdigit() else f"{parent}.{key}"
            if key.isdigit():
                if f"{parent}[]" in d["nodes"] or _to_index_path(path, space) in entries:
                    continue
            ip = _to_index_path(path, space)
            if tp == "func":
                put(path, "func", sig=extra)
            elif ip not in entries:
                put(path, tp)
    expanded = {_to_index_path(p, space) for p in d["expanded"]} | {_to_index_path(p, space) for p in d["raw_closed"]}
    unexplored = sorted({_to_concrete(e["path"], space) for e in entries.values()
                         if e["kind"] == "field" and e.get("type") == "obj" and not e.get("link")
                         and e["path"] not in expanded})
    absent -= set(entries)
    return entries, expanded, absent, unexplored


def _to_concrete(ip: str, space: str) -> str:
    p = ip[len("visual."):] if space == "visual" and ip.startswith("visual.") else ip
    return p.replace("[n]", "[0]")


# ---------------------------------------------------------------- diff

def _norm_sig(s: str | None) -> str:
    return re.sub(r"\s+", "", s or "")


def diff_against(bundled: list[dict[str, Any]], entries: dict[str, dict], expanded: set[str],
                 absent: set[str], scope_prefix: str) -> dict[str, list]:
    """added: live paths not in bundled; removed: bundled paths confirmed absent (probed as nil, or
    missing although the parent was expanded); changed: kind/type/signature differences.
    Only bundled paths under scope_prefix are considered."""
    def in_scope(p: str) -> bool:
        return p == scope_prefix or p.startswith(scope_prefix + ".") or p.startswith(scope_prefix + "[")

    b = {e["path"]: e for e in bundled if e.get("path") and e.get("kind") != "note" and in_scope(e["path"])}
    added = sorted(p for p in entries if p not in b and in_scope(p))
    removed, not_covered, changed = [], [], []
    for p, be in sorted(b.items()):
        le = entries.get(p)
        if le is None:
            if p in absent or parent_path(p) in expanded:
                removed.append({"path": p, "was": be.get("signature") or be.get("type") or be["kind"]})
            else:
                not_covered.append(p)
            continue
        bk = "function" if be["kind"] == "function" else "field"
        lk = "function" if le["kind"] == "function" else "field"
        if bk != lk:
            changed.append({"path": p, "field": "kind", "bundled": be["kind"], "live": le["kind"]})
        elif lk == "function":
            ls = le.get("signature", "")
            if not ls.endswith("(?)") and _norm_sig(ls) != _norm_sig(be.get("signature")):
                changed.append({"path": p, "field": "signature", "bundled": be.get("signature"), "live": ls})
        else:
            bt, lt = be.get("type"), le.get("type")
            if bt in ("num", "str", "bool", "obj") and lt and bt != lt:
                changed.append({"path": p, "field": "type", "bundled": bt, "live": lt})
    return {"added": added, "removed": removed, "changed": changed, "not_covered": not_covered}


# ---------------------------------------------------------------- storage

def live_path(cfg: Config) -> Path:
    return cfg.data_dir / LIVE_FILE


def _check_data_dir(cfg: Config) -> Path:
    d = cfg.data_dir
    try:
        dr = d.resolve()
        gr = cfg.game_dir.resolve()
    except OSError as e:
        raise DumpError(f"Cannot resolve data folder {d}: {e}") from e
    if os.path.normcase(str(dr)) == os.path.normcase(str(gr)) or os.path.normcase(str(dr)).startswith(os.path.normcase(str(gr)) + os.sep):
        raise DumpError(f"Data folder {d} is inside the game folder; refusing to write there. Set WS_MCP_DATA_DIR.")
    return d


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".ws-mcp-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


_live_cache: dict[str, Any] = {"key": None, "doc": None}


def load_live(cfg: Config) -> dict[str, Any] | None:
    p = live_path(cfg)
    try:
        st = p.stat()
    except OSError:
        return None
    key = (str(p), st.st_mtime_ns, st.st_size)
    if _live_cache["key"] == key:
        return _live_cache["doc"]
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if doc.get("format") != LIVE_FORMAT or not isinstance(doc.get("entries"), list):
            doc = None
    except (OSError, ValueError):
        doc = None
    _live_cache.update(key=key, doc=doc)
    return doc


def _read_source(cfg: Config, file: str | None, which: str) -> tuple[Path, str]:
    from .core import LOG_NAME_RE, _read_text  # local import: core imports this module
    if file:
        p = Path(file).expanduser()
        if not p.is_file():
            raise DumpError(f"File not found: {p}")
    else:
        if not LOG_NAME_RE.match(which):
            raise DumpError("which must be a plain file name like 'log.txt' or 'log_prev.txt'.")
        p = next((c for c in cfg.log_candidates(which) if c.is_file()), None)
        if p is None:
            raise DumpError(f"{which} not found. Run the dump script in the game first, or pass file=... "
                            "Set WS_LOG_PATH if the log is elsewhere.")
    return p, _read_text(p, MAX_LOG_BYTES)


def import_dump(cfg: Config, bundled: list[dict[str, Any]], file: str | None = None, which: str = "log.txt",
                dump_id: str | None = None, space: str | None = None, allow_partial: bool = False,
                reset: bool = False, dry_run: bool = False, limit: int = 200) -> dict[str, Any]:
    src, text = _read_source(cfg, file, which)
    dumps = parse_dumps(text)
    if not dumps:
        raise DumpError(f"No WSDUMP records in {src}. Run the script from api_dump_script in the game "
                        "(developer mode), then import again. The log is cleared on every game start.")
    if dump_id:
        cand = [d for d in dumps if d["id"] == dump_id and d["complete"]] or [d for d in dumps if d["id"] == dump_id]
        if not cand:
            raise DumpError(f"Dump {dump_id!r} not found. Dumps in log: {[d['id'] for d in dumps]}")
        d = cand[-1]
    else:
        complete = [d for d in dumps if d["complete"]]
        d = complete[-1] if complete else dumps[-1]
    warnings: list[str] = []
    if not d["complete"]:
        msg = (f"Dump {d['id']} has no END record (log truncated or the game stopped during the dump); "
               f"{len(d['nodes'])} node records were read.")
        if not allow_partial:
            raise DumpError(msg + " Re-run the dump, or pass allow_partial=true to import what is there.")
        warnings.append(msg)
    if d["header"] is None:
        warnings.append("BEGIN record missing; space and root are guessed.")
    if d["status"] == "truncated":
        warnings.append("Dump stopped at maxNodes; raise max_nodes or dump subtrees (root=...).")
    if d["status"] == "error":
        warnings.append("Dump script reported an error: " + "; ".join(d["warnings"][-3:]))
    if d["malformed"]:
        warnings.append(f"{d['malformed']} malformed WSDUMP record(s) skipped.")
    root = d["root"] or "root"
    detected = _detect_space(d)
    sp = space or d["space"] or detected or "gameplay"
    if space is None and detected and d["space"] and detected != d["space"]:
        warnings.append(f"Script space was '{d['space']}' but the tree looks like '{detected}'; using '{detected}'.")
        sp = detected
    if sp not in ("gameplay", "visual"):
        raise DumpError("space must be 'gameplay' or 'visual'.")
    engine = d["engine_version"] or (d["options"].get("version") or None)
    if not d["engine_version"] and engine:
        warnings.append("Engine version taken from root.version (no 'Engine Version' line before the dump).")
    source = f"live dump, engine {engine or 'unknown'}, {sp}"
    entries, expanded, absent, unexplored = dump_entries(d, sp, source)
    scope = _to_index_path(root, sp)
    diff = diff_against(bundled, entries, expanded, absent, scope)

    live = None if reset else load_live(cfg)
    reset_reason = "reset=true" if reset and live_path(cfg).exists() else None
    if live and engine and live.get("engine_version") and str(live["engine_version"]) != str(engine):
        reset_reason = f"engine changed {live['engine_version']} -> {engine}"
        live = None
    if live is None:
        live = {"format": LIVE_FORMAT, "engine_version": engine, "game_version": d["game_version"],
                "entries": [], "expanded": [], "absent": [], "dumps": []}

    def in_scope(p: str) -> bool:
        return p == scope or p.startswith(scope + ".") or p.startswith(scope + "[")

    merged = {e["path"]: e for e in live["entries"] if not in_scope(e["path"])}
    merged.update(entries)
    live_expanded = {p for p in live.get("expanded", []) if not in_scope(p)} | expanded
    live_absent = {p for p in live.get("absent", []) if not in_scope(p)} | {r["path"] for r in diff["removed"]} | absent
    live_absent -= set(merged)
    dumps_meta = [x for x in live.get("dumps", []) if x.get("scope") != scope]
    dumps_meta.append({"id": d["id"], "scope": scope, "space": sp, "file": str(src), "complete": d["complete"],
                       "status": d["status"], "nodes": len(d["nodes"]), "raw_blocks": len(d["raw"]),
                       "imported_at": time.strftime("%Y-%m-%d %H:%M:%S")})
    doc = {"format": LIVE_FORMAT, "engine_version": engine or live.get("engine_version"),
           "game_version": d["game_version"] or live.get("game_version"),
           "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "about": "Live API index imported from the game with war-selection-mcp import_api_dump. "
                    "Names, types and signatures only.",
           "count": len(merged), "dumps": dumps_meta,
           "expanded": sorted(live_expanded), "absent": sorted(live_absent),
           "entries": sorted(merged.values(), key=lambda e: e["path"])}

    lim = max(1, min(int(limit), 5000))
    report: dict[str, Any] = {
        "source": str(src), "dump_id": d["id"], "dumps_in_log": [x["id"] for x in dumps],
        "space": sp, "root": root, "complete": d["complete"], "status": d["status"],
        "engine_version": engine, "game_version": d["game_version"],
        "nodes": len(d["nodes"]), "raw_blocks": len(d["raw"]), "expanded": len(expanded),
        "entries_from_dump": len(entries),
        "diff_vs_bundled": {
            "bundled": "WSUS tree v258.4018",
            "added": len(diff["added"]), "removed": len(diff["removed"]), "changed": len(diff["changed"]),
            "not_covered": len(diff["not_covered"]),
            "added_paths": diff["added"][:lim], "removed_paths": diff["removed"][:lim],
            "changed_paths": diff["changed"][:lim],
        },
        "unexplored": unexplored[:lim], "unexplored_total": len(unexplored),
        "warnings": warnings + [w for w in d["warnings"][:20] if not w.startswith("cycle guard")],
        "cycle_guards": sum(1 for w in d["warnings"] if w.startswith("cycle guard")),
    }
    if dry_run:
        report["stored"] = None
        report["note"] = "dry_run: nothing written."
        return report
    data_dir = _check_data_dir(cfg)
    target = data_dir / LIVE_FILE
    if target.exists():
        _atomic_write(data_dir / PREV_FILE, target.read_text(encoding="utf-8"))
    _atomic_write(target, json.dumps(doc, ensure_ascii=False, indent=1))
    _atomic_write(data_dir / DIFF_FILE, json.dumps({"dump_id": d["id"], "scope": scope, "engine_version": engine,
                                                    **diff}, ensure_ascii=False, indent=1))
    report["stored"] = str(target)
    report["diff_file"] = str(data_dir / DIFF_FILE)
    report["index_entries_total"] = len(merged)
    if reset_reason:
        report["previous_index"] = f"replaced ({reset_reason}); backup in {data_dir / PREV_FILE}"
    return report


def status(cfg: Config) -> dict[str, Any]:
    live = load_live(cfg)
    p = live_path(cfg)
    if not live:
        return {"active": "bundled", "bundled": "WSUS tree v258.4018", "live_file": str(p), "live_present": False}
    return {"active": "live + bundled fallback", "live_file": str(p), "live_present": True,
            "engine_version": live.get("engine_version"), "game_version": live.get("game_version"),
            "updated_at": live.get("updated_at"), "entries": len(live["entries"]),
            "expanded": len(live.get("expanded", [])), "absent": len(live.get("absent", [])),
            "dumps": live.get("dumps", [])}
