"""Mod development tools: lint, diff, log error analysis, API usage examples, scaffolds, unit lookup.

All functions are read-only with respect to the game folder.
"""

from __future__ import annotations

import difflib
import re
from collections import Counter, defaultdict
from functools import lru_cache
from typing import Any

from . import core, lint as lint_rules
from .config import Config
from .lua_syntax import LuaSyntaxError, parse
from .scaffolds import TEMPLATES

USING_RE = re.compile(r"Using (gameplay|visual) modifications:\s*(.*)$")
MOD_TOKEN_RE = re.compile(r"\b([A-Za-z0-9]{11})_(\d+)\b")
LOG_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s?(.*)$")
LUA_FAIL_RE = re.compile(r"Lua program (?P<script>\S+) run \((?P<status>[^)]*)\) failed:?")
FRAME_RE = re.compile(r"^\s*Line:\s*(-?\d+)\s+function:\[([^\]]*)\]")
CHUNK_RE = re.compile(r'\[string "(?P<preview>.*?)(?:\.\.\.)?"\]:(?P<line>-?\d+):\s*(?P<msg>.*)')
F_NAME_RE = re.compile(r"\bf_[A-Za-z0-9_]+")
ROOT_FIELD_RE = re.compile(r"\broot[._]([A-Za-z][A-Za-z0-9]*)")


# ---------------------------------------------------------------- knowledge

def _latest_files(cfg: Config) -> list[tuple[str, int, str]]:
    out = []
    for mod in core.scan_mods(cfg).values():
        for f in mod["files"]:
            if f["kind"] == "lua" and f["version"] == mod["latest"]:
                out.append((mod["id"], f["version"], f["file"]))
    return sorted(out)


def _mods_signature(cfg: Config) -> tuple:
    d = cfg.mods_dir
    if not d.is_dir():
        return (str(d), 0, 0)
    st = d.stat()
    return (str(d), st.st_mtime, len(list(d.iterdir())))


def mod_kinds_from_log(cfg: Config) -> dict[str, str]:
    """Mod id -> 'gameplay'/'visual' from 'Using ... modifications:' lines in gen/log.txt and log_prev.txt."""
    kinds: dict[str, str] = {}
    for name in ("log_prev.txt", "log.txt"):
        path = next((p for p in cfg.log_candidates(name) if p.is_file()), None)
        if not path:
            continue
        for line in core._read_text(path, 50_000_000).splitlines():
            m = USING_RE.search(line)
            if m:
                for mid, _ in MOD_TOKEN_RE.findall(m.group(2)):
                    kinds[mid] = m.group(1)
    return kinds


@lru_cache(maxsize=4)
def _corpus(sig: tuple, game_dir: str) -> dict[str, Any]:
    cfg = Config(game_dir=__import__("pathlib").Path(game_dir))
    log_kinds = mod_kinds_from_log(cfg)
    f_names: set[str] = set()
    roots: dict[str, set[str]] = {"gameplay": set(), "visual": set()}
    events: Counter = Counter()
    per_mod: dict[str, dict[str, Any]] = {}
    for mid, ver, fname in _latest_files(cfg):
        code = core._read_text(cfg.mods_dir / fname)
        kind = log_kinds.get(mid) or lint_rules.detect_kind(code)[0]
        f_names.update(F_NAME_RE.findall(code))
        info: dict[str, Any] = {"id": mid, "version": ver, "file": fname, "kind": kind,
                                "kind_basis": "log" if mid in log_kinds else "heuristic"}
        try:
            pr = parse(code)
            keys = sorted({k for k, _, _ in pr.addmod_handlers})
            legacy = sorted({r.chain[0] for r in pr.refs if r.kind == "call" and len(r.chain) == 1
                             and r.chain[0] in lint_rules.LEGACY_REGISTER})
            for r in pr.refs:
                n = lint_rules.normalize(lint_rules._expand(r.chain, pr.aliases))
                if n.startswith("root."):
                    fld = re.split(r"[.\[]", n)[1]
                    if fld:
                        roots[kind].add(fld)
            info.update(events=keys, legacy_register=legacy, syntax_ok=True)
            events.update(keys)
        except LuaSyntaxError as e:
            info.update(events=[], legacy_register=[], syntax_ok=False, syntax_error=str(e))
        per_mod[mid] = info
    return {"f_names": f_names, "roots": roots, "events": events, "mods": per_mod, "log_kinds": log_kinds}


def corpus(cfg: Config) -> dict[str, Any]:
    return _corpus(_mods_signature(cfg), str(cfg.game_dir))


def _index_knowledge(cfg: Config) -> dict[str, Any]:
    entries, meta = core.active_index(cfg)
    key = (meta.get("active"), meta.get("engine_version"), meta.get("live_entries"), id(entries))
    return _index_knowledge_cached(key, entries)


_knowledge_cache: dict[Any, Any] = {}


def _index_knowledge_cached(key: tuple, entries: list[dict[str, Any]]) -> dict[str, Any]:
    if key in _knowledge_cache:
        return _knowledge_cache[key]
    fn: set[str] = set()
    live_fn: set[str] = set()
    roots: dict[str, set[str]] = {"gameplay": set(), "visual": set()}
    events: set[str] = set()
    for e in entries:
        p = e.get("path", "")
        if e.get("kind") == "function":
            fn.add(e["name"])
            if str(e.get("source", "")).startswith("live dump"):
                live_fn.add(e["name"])
        if e.get("kind") == "event":
            events.add(e["name"])
        if p.startswith("root."):
            roots["gameplay"].add(p.split(".")[1].split("[")[0])
        elif p.startswith("visual.root."):
            roots["visual"].add(p.split(".")[2].split("[")[0])
    # f_* names used in the bundled guide's verified examples (some are newer than the WSUS index)
    guide_fn = set(re.findall(r"\b(f_[A-Za-z0-9_]+)\s*\(", "\n".join(core.load_guide())))
    fn |= guide_fn
    absent: dict[str, str] = {}
    live = key[0] == "live + bundled fallback"
    if live:
        for e in core.load_api_index():
            if e.get("kind") == "function" and e["name"] not in fn and e["name"] not in guide_fn:
                absent[e["name"]] = e["path"]
    res = {"functions": fn, "roots": roots, "events": events, "absent": absent,
           "engine": key[1], "live": live}
    _knowledge_cache.clear()
    _knowledge_cache[key] = res
    return res


# ---------------------------------------------------------------- 1. lint

def lint_mod(cfg: Config, code: str | None = None, mod_id: str | None = None, version: int | None = None,
             kind: str = "auto") -> dict[str, Any]:
    if (code is None) == (mod_id is None):
        raise core.ToolError("Pass exactly one of `code` or `mod_id`.")
    if kind not in ("auto", "gameplay", "visual"):
        raise core.ToolError("kind must be 'auto', 'gameplay' or 'visual'.")
    source: dict[str, Any] = {}
    if mod_id is not None:
        m = core.get_mod(cfg, mod_id, version, "lua", max_chars=core.MAX_READ_BYTES)
        code = m["code"]
        source = {"mod": f"mod-{m['id']}", "version": m["version"], "file": m["file"]}
    assert code is not None
    basis = "argument"
    if kind == "auto":
        lk = mod_kinds_from_log(cfg) if mod_id is not None else {}
        mid = source.get("mod", "")[4:]
        if mid and mid in lk:
            kind, basis = lk[mid], "gen/log.txt ('Using ... modifications')"
        else:
            kind, basis = lint_rules.detect_kind(code)
    idx = _index_knowledge(cfg)
    c = corpus(cfg)
    functions = (idx["functions"] | c["f_names"]) - set(idx["absent"])
    roots = {k: idx["roots"][k] | c["roots"][k] for k in ("gameplay", "visual")}
    events = idx["events"] | {e for e, n in c["events"].items() if n >= 1}
    res = lint_rules.lint(code, kind, functions, roots, events, absent_functions=idx["absent"],
                          index_label=f"live dump engine {idx['engine']}" if idx["live"] else "api_index (WSUS v258.4018)")
    counts = Counter(i["severity"] for i in res["issues"])
    lines = code.splitlines()
    for i in res["issues"]:
        if i.get("line") and 0 < i["line"] <= len(lines):
            i["code"] = lines[i["line"] - 1].strip()[:200]
    return {**source, "kind": kind, "kind_basis": basis, "syntax_ok": res["syntax_ok"],
            "errors": counts.get("error", 0), "warnings": counts.get("warning", 0), "infos": counts.get("info", 0),
            "issues": res["issues"], "events": res.get("events", []),
            "api_index": (f"live dump, engine {idx['engine']} (bundled WSUS v258.4018 as fallback)" if idx["live"]
                          else "bundled WSUS v258.4018 (no live dump imported)"),
            "note": "Static checks only. Unknown names are warnings; absent-in-engine is reported only "
                    "when a live dump probed the name and the engine did not have it."}


# ---------------------------------------------------------------- 2. diff

def diff_mod(cfg: Config, mod_id: str, v1: int | None = None, v2: int | None = None, kind: str = "lua",
             context: int = 3, max_chars: int = 60_000) -> dict[str, Any]:
    mid = core.normalize_mod_id(mod_id)
    mod = core.scan_mods(cfg).get(mid)
    if not mod:
        raise core.ToolError(f"Mod {mid} is not in the local cache.")
    vers = sorted({f["version"] for f in mod["files"] if f["kind"] == kind})
    if not vers:
        raise core.ToolError(f"No {kind} files for {mid}.")
    if v2 is None:
        v2 = vers[-1]
    if v1 is None:
        older = [v for v in vers if v < v2]
        if not older:
            raise core.ToolError(f"Only one cached {kind} version ({v2}) of {mid}; nothing to diff. Versions: {vers}")
        v1 = older[-1]
    a = core.get_mod(cfg, mid, v1, kind, max_chars=core.MAX_READ_BYTES)
    b = core.get_mod(cfg, mid, v2, kind, max_chars=core.MAX_READ_BYTES)
    al, bl = a["code"].splitlines(), b["code"].splitlines()
    context = max(0, min(int(context), 20))
    diff = list(difflib.unified_diff(al, bl, fromfile=a["file"], tofile=b["file"], n=context, lineterm=""))
    added = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
    text = "\n".join(diff)
    return {"mod": f"mod-{mid}", "kind": kind, "from_version": v1, "to_version": v2, "versions": vers,
            "identical": not diff, "added": added, "removed": removed,
            "truncated": len(text) > max_chars, "diff": text[:max_chars]}


# ---------------------------------------------------------------- 3. log errors

def _parse_log_errors(lines: list[str]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    active = {"gameplay": [], "visual": []}
    i, n = 0, len(lines)
    while i < n:
        raw = lines[i]
        m_ts = LOG_TS_RE.match(raw)
        ts, body = (m_ts.group(1), m_ts.group(2)) if m_ts else (None, raw)
        mu = USING_RE.search(body)
        if mu:
            active[mu.group(1)] = [f"{a}_{b}" for a, b in MOD_TOKEN_RE.findall(mu.group(2))]
            i += 1
            continue
        mf = LUA_FAIL_RE.search(body)
        if mf:
            err = {"line_no": i + 1, "time": ts, "script": mf.group("script"), "status": mf.group("status"),
                   "frames": [], "message": None, "chunk_preview": None, "chunk_line": None,
                   "active_gameplay": list(active["gameplay"]), "active_visual": list(active["visual"])}
            j = i + 1
            while j < n and j <= i + 60:
                l = lines[j]
                if re.match(r"^\s*Error occur+ed at:?", l):
                    j += 1
                    continue
                fm = FRAME_RE.match(l)
                if fm:
                    err["frames"].append({"line": int(fm.group(1)), "function": fm.group(2)})
                    j += 1
                    continue
                if not l.strip():
                    j += 1
                    if err["message"]:
                        break
                    continue
                if LOG_TS_RE.match(l) and err["message"] is None and not CHUNK_RE.search(l):
                    break
                cm = CHUNK_RE.search(l)
                if cm:
                    err["chunk_preview"] = cm.group("preview")
                    err["chunk_line"] = int(cm.group("line"))
                    err["message"] = cm.group("msg").strip()
                else:
                    err["message"] = l.strip()
                j += 1
                break
            errors.append(err)
            i = j
            continue
        cm = CHUNK_RE.search(body)
        if cm:
            errors.append({"line_no": i + 1, "time": ts, "script": None, "status": None, "frames": [],
                           "message": cm.group("msg").strip(), "chunk_preview": cm.group("preview"),
                           "chunk_line": int(cm.group("line")),
                           "active_gameplay": list(active["gameplay"]), "active_visual": list(active["visual"])})
        i += 1
    return errors


def _map_chunk(cfg: Config, preview: str, line: int | None, active: list[str]) -> list[dict[str, Any]]:
    """Find cached mod files whose text starts with the chunk preview."""
    pv = preview.strip()
    if len(pv) < 8:
        return []
    out = []
    mods = core.scan_mods(cfg)
    active_ids = {a.split("_")[0]: int(a.split("_")[1]) for a in active}
    for mod in mods.values():
        for f in mod["files"]:
            if f["kind"] != "lua":
                continue
            if active_ids and mod["id"] in active_ids and f["version"] != active_ids[mod["id"]]:
                continue
            head = core._read_text(cfg.mods_dir / f["file"], 4096).lstrip()
            if head.startswith(pv):
                hit = {"mod": f"mod-{mod['id']}", "version": f["version"], "file": f["file"],
                       "active": mod["id"] in active_ids}
                if line and line > 0:
                    code_lines = core._read_text(cfg.mods_dir / f["file"]).splitlines()
                    if line <= len(code_lines):
                        hit["code"] = code_lines[line - 1].strip()[:200]
                out.append(hit)
    out.sort(key=lambda h: (not h["active"], h["mod"], -h["version"]))
    return out[:5]


def log_errors(cfg: Config, which: str = "log.txt", tail: int | None = None, since: str | None = None,
               limit: int = 30) -> dict[str, Any]:
    if not core.LOG_NAME_RE.match(which):
        raise core.ToolError("which must be a plain file name like 'log.txt' or 'log_prev.txt'.")
    path = next((p for p in cfg.log_candidates(which) if p.is_file()), None)
    if not path:
        return {"found": False, "searched": [str(p) for p in cfg.log_candidates(which)],
                "message": f"{which} not found. Set WS_LOG_PATH or run the game once."}
    if since and not re.match(r"^\d{4}-\d{2}-\d{2}( \d{2}:\d{2}(:\d{2})?)?$", since):
        raise core.ToolError("since must look like 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM[:SS]' (log time).")
    lines = core._read_text(path, 50_000_000).splitlines()
    offset = 0
    if tail:
        tail = max(1, min(int(tail), 1_000_000))
        offset = max(0, len(lines) - tail)
    errs = _parse_log_errors(lines[offset:])
    for e in errs:
        e["line_no"] += offset
    if since:
        errs = [e for e in errs if e["time"] and e["time"] >= since]
    groups: dict[tuple, dict[str, Any]] = {}
    for e in errs:
        key = (e["script"], e["chunk_preview"], e["chunk_line"], re.sub(r"\d+", "N", e["message"] or ""))
        g = groups.get(key)
        if not g:
            g = groups[key] = {**e, "count": 0, "first_time": e["time"], "first_line_no": e["line_no"]}
        g["count"] += 1
        g["last_time"], g["last_line_no"] = e["time"], e["line_no"]
    out = []
    for g in sorted(groups.values(), key=lambda g: -(g["last_line_no"])):
        kind = "visual" if g["script"] and re.search(r"/(visual|interfaces|Tools)/", g["script"]) else "gameplay"
        active = g["active_visual"] if kind == "visual" else g["active_gameplay"]
        g["script_kind"] = kind if g["script"] else None
        g["candidates"] = _map_chunk(cfg, g["chunk_preview"], g["chunk_line"], active) if g["chunk_preview"] else []
        g["active_mods"] = active
        for k in ("active_gameplay", "active_visual", "time", "line_no"):
            g.pop(k, None)
        out.append(g)
    return {"found": True, "path": str(path), "total_lines": len(lines), "errors_total": len(errs),
            "groups": out[: max(1, min(int(limit), 200))], "truncated": len(out) > limit,
            "note": "Mod mapping: 'candidates' match the [string \"...\"] chunk preview against cached mod files; "
                    "'active_mods' are the mods loaded at that point per 'Using ... modifications'. "
                    "Times are as written in the log."}


# ---------------------------------------------------------------- 4. examples / events

def _api_regex(api_name: str) -> re.Pattern:
    name = api_name.strip()
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_.\[\]]*$", name):
        raise core.ToolError("api_name must be an identifier or dotted path, e.g. 'f_addCircle' or 'landscape.zones'.")
    segs = [s for s in re.split(r"[.\[\]]+", name) if s and not s.isdigit()]
    sep = r"(?:\s*\[[^\]]*\]\s*)*[._:]"
    pat = sep.join(re.escape(s) for s in segs)
    return re.compile(rf"(?<![A-Za-z0-9_]){pat}(?![A-Za-z0-9_])")


def find_examples(cfg: Config, api_name: str, limit: int = 20, context: int = 3, per_mod: int = 2,
                  latest_only: bool = True) -> dict[str, Any]:
    """Usages of an API name across cached mods. A dotted path is matched exactly first; lines that only
    match its last segment (e.g. through a local alias) are included with exact_path=false."""
    strict = _api_regex(api_name)
    last_seg = [s for s in re.split(r"[.\[\]]+", api_name.strip()) if s and not s.isdigit()][-1]
    loose = _api_regex(last_seg)
    limit = max(1, min(int(limit), 200))
    per_mod = max(1, min(int(per_mod), 20))
    context = max(0, min(int(context), 10))
    mods = core.scan_mods(cfg)
    hits: list[tuple[bool, str, dict, list[str], int]] = []
    mods_using: dict[str, int] = {}
    for mod in sorted(mods.values(), key=lambda m: m["id"].lower()):
        files = [f for f in mod["files"] if f["kind"] == "lua" and (not latest_only or f["version"] == mod["latest"])]
        for f in files:
            lines = core._read_text(cfg.mods_dir / f["file"]).splitlines()
            for i, line in enumerate(lines):
                code_part = line.split("--", 1)[0]
                if not loose.search(code_part):
                    continue
                exact = bool(strict.search(code_part))
                hits.append((exact, mod["id"], f, lines, i))
                mods_using[mod["id"]] = mods_using.get(mod["id"], 0) + 1
    hits.sort(key=lambda h: (not h[0], h[1].lower()))
    examples, taken = [], Counter()
    for exact, mid, f, lines, i in hits:
        if taken[mid] >= per_mod or len(examples) >= limit:
            continue
        taken[mid] += 1
        lo, hi = max(0, i - context), min(len(lines), i + context + 1)
        examples.append({"mod": f"mod-{mid}", "version": f["version"], "file": f["file"], "line": i + 1,
                         "exact_path": exact,
                         "context": "\n".join(f"{k + 1:>5}{'>' if k == i else ':'} {lines[k]}" for k in range(lo, hi))})
    api = core.search_api(last_seg, limit=3, cfg=cfg)
    return {"api_name": api_name, "total_hits": len(hits), "exact_path_hits": sum(1 for h in hits if h[0]),
            "mods_using": [{"mod": f"mod-{k}", "hits": v} for k, v in sorted(mods_using.items(), key=lambda kv: -kv[1])],
            "examples": examples, "index_entries": api["results"],
            "note": "Underscore paths (root.scene_0, landscape_zones) and [n] indices are matched; comment-only lines are skipped."}


def list_events_usage(cfg: Config, event: str | None = None) -> dict[str, Any]:
    c = corpus(cfg)
    mods = sorted(c["mods"].values(), key=lambda m: m["id"].lower())
    if event:
        mods = [m for m in mods if event in m["events"]]
    return {"events": dict(c["events"].most_common()),
            "mods": [{"mod": f"mod-{m['id']}", "version": m["version"], "kind": m["kind"], "kind_basis": m["kind_basis"],
                      "events": m["events"], "legacy_register": m["legacy_register"], "syntax_ok": m["syntax_ok"]}
                     for m in mods],
            "note": "Events are the keys of addMod({...}) tables in the latest cached version of each mod."}


# ---------------------------------------------------------------- 5. scaffold

def scaffold_mod(template: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    if template not in TEMPLATES:
        raise core.ToolError(f"Unknown template {template!r}. Available: {sorted(TEMPLATES)}")
    t = TEMPLATES[template]
    values = {**t["defaults"], **{k: v for k, v in (params or {}).items()}}
    unknown = set(params or {}) - set(t["defaults"])
    if unknown:
        raise core.ToolError(f"Unknown params {sorted(unknown)}. Template params: {t['defaults']}")
    for k, v in values.items():
        if not re.match(r"^[A-Za-z0-9_.\-]{1,64}$", str(v)):
            raise core.ToolError(f"Param {k}={v!r}: use letters, digits, '_', '.', '-' only.")
    files = []
    for f in t["files"]:
        code = f["code"]
        for k, v in values.items():
            code = code.replace("{{" + k + "}}", str(v))
        files.append({"kind": f["kind"], "name": f["name"], "code": code})
    return {"template": template, "description": t["description"], "params": values, "files": files,
            "sources": t["sources"],
            "note": "Returned only, nothing is written. Paste into the in-game editor (developer mode) and test."}


def list_templates() -> list[dict[str, Any]]:
    return [{"template": k, "description": v["description"], "params": v["defaults"]} for k, v in sorted(TEMPLATES.items())]


# ---------------------------------------------------------------- 6. unit lookup

def unit_lookup(cfg: Config, query: str, limit: int = 20) -> dict[str, Any]:
    q = str(query).strip()
    if not q:
        raise core.ToolError("Empty query.")
    proj = cfg.project_dir
    legacy_p, gameplay_p = proj / "legacyIds.json", proj / "gameplay.json"
    if not legacy_p.is_file():
        raise core.ToolError(f"{legacy_p} not found. Check WS_GAME_DIR.")
    units = core._load_json_cached(str(legacy_p), legacy_p.stat().st_mtime).get("units", {})
    build = []
    if gameplay_p.is_file():
        build = core._load_json_cached(str(gameplay_p), gameplay_p.stat().st_mtime).get("build", []) or []
    if q.isdigit():
        matches = [(q, units[q])] if q in units else []
    else:
        ql = q.lower()
        matches = sorted(((k, v) for k, v in units.items() if ql in v.lower()), key=lambda kv: int(kv[0]))
    out = []
    for uid, path in matches[: max(1, min(int(limit), 200))]:
        rules = []
        for bi, b in enumerate(build):
            if isinstance(b, dict) and b.get("unit") == path:
                r = {"build_index": bi, "available": b.get("available")}
                for key in ("costBuilding", "costInit"):
                    if isinstance(b.get(key), list):
                        r[key] = b[key]
                        r[key + "_display"] = [x / 1000 for x in b[key]]
                if "health" in b:
                    r["health"] = b["health"]
                rules.append(r)
        out.append({"id": int(uid), "path": path, "build_rules": rules})
    return {"query": q, "matches": out, "total": len(matches),
            "note": "id is the legacy unit id from legacyIds.json; in known examples it matches the "
                    "root.unitType index (201 worker, 285 Big Bertha). At runtime prefer "
                    "root.unitType.f_find(path). Costs are x1000 (res0 food, res1 wood, res2 iron)."}
