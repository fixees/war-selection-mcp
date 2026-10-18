"""Tool implementations (pure functions, no MCP dependency) — easy to test."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
from collections import defaultdict
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

from . import apidump
from .config import Config

MOD_FILE_RE = re.compile(r"^(?P<id>[A-Za-z0-9]{11})_(?P<ver>\d+)-(?P<hash>[0-9a-fA-F]{16})\.(?P<kind>lua|prm)$")
MOD_ID_RE = re.compile(r"^[A-Za-z0-9]{11}$")
DRAFT_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$")
MAX_DRAFT_BYTES = 1_000_000
MAX_READ_BYTES = 2_000_000
LOG_NAME_RE = re.compile(r"^[A-Za-z0-9_\-]+(\.[A-Za-z0-9_\-]+)*\.(txt|log)$")


class ToolError(Exception):
    """Error with a message meant for the MCP client."""


def _read_text(path: Path, limit: int = MAX_READ_BYTES) -> str:
    with open(path, "rb") as fh:
        data = fh.read(limit + 1)
    text = data[:limit].decode("utf-8", errors="replace")
    if text.startswith("\ufeff"):
        text = text[1:]
    if len(data) > limit:
        text += f"\n... [truncated at {limit} bytes]"
    return text


def normalize_mod_id(mod_id: str) -> str:
    mid = mod_id.strip()
    if mid.lower().startswith("mod-"):
        mid = mid[4:]
    mid = mid.split("_")[0]
    if not MOD_ID_RE.match(mid):
        raise ToolError(f"Invalid mod id {mod_id!r}: expected 11 letters/digits, e.g. 'mod-6gqH17D5rDl' or '6gqH17D5rDl'.")
    return mid


# ---------------------------------------------------------------- mods cache

def scan_mods(cfg: Config) -> dict[str, dict[str, Any]]:
    """Group files in modsStorage (top level only) by mod id."""
    mods: dict[str, dict[str, Any]] = {}
    if not cfg.mods_dir.is_dir():
        return mods
    for entry in os.scandir(cfg.mods_dir):
        if not entry.is_file():
            continue
        m = MOD_FILE_RE.match(entry.name)
        if not m:
            continue
        mod = mods.setdefault(m["id"], {"id": m["id"], "files": []})
        mod["files"].append({
            "file": entry.name,
            "version": int(m["ver"]),
            "hash": m["hash"],
            "kind": m["kind"],
            "size": entry.stat().st_size,
        })
    for mod in mods.values():
        mod["files"].sort(key=lambda f: (f["version"], f["kind"]))
        mod["versions"] = sorted({f["version"] for f in mod["files"]})
        mod["latest"] = mod["versions"][-1]
        mod["kinds"] = sorted({f["kind"] for f in mod["files"]})
    return mods


def game_info(cfg: Config) -> dict[str, Any]:
    g = cfg.game_dir
    ev_file = g / "engine-version.txt"
    engine = _read_text(ev_file, 100).strip() if ev_file.is_file() else None
    mods = scan_mods(cfg)
    files = [f for m in mods.values() for f in m["files"]]
    proj = cfg.project_dir
    project_files = sorted(p.name for p in proj.iterdir()) if proj.is_dir() else []
    logs = [str(p) for p in cfg.log_candidates() if p.is_file()]
    return {
        "game_dir": str(g),
        "game_dir_exists": g.is_dir(),
        "engine_version": engine,
        "mods_dir": str(cfg.mods_dir),
        "mods_unique": len(mods),
        "mods_files_lua": sum(1 for f in files if f["kind"] == "lua"),
        "mods_files_prm": sum(1 for f in files if f["kind"] == "prm"),
        "draft_dir": str(cfg.draft_dir),
        "draft_dir_exists": cfg.draft_dir.is_dir(),
        "project_dir": str(proj),
        "project_files": project_files,
        "log_found": logs,
        "api_index": _index_status(cfg, engine),
        "note": ("Bundled index is WSUS v258.4018. Refresh it from the running game: api_dump_script, "
                 "then import_api_dump."),
    }


def _index_status(cfg: Config, engine: str | None) -> dict[str, Any]:
    st = apidump.status(cfg)
    live_ver = st.get("engine_version")
    if engine and live_ver and str(live_ver) != str(engine):
        st["stale"] = f"live index is from engine {live_ver}, game folder has {engine}: re-run the dump"
    elif engine and not live_ver:
        st["stale"] = f"only the bundled index (258) is available, game folder has {engine}"
    return st


def list_mods(cfg: Config, query: str | None = None) -> list[dict[str, Any]]:
    out = []
    for mod in sorted(scan_mods(cfg).values(), key=lambda m: m["id"].lower()):
        if query and query.lower() not in mod["id"].lower():
            continue
        latest = [f for f in mod["files"] if f["version"] == mod["latest"]]
        out.append({
            "id": mod["id"],
            "mod_ref": f"mod-{mod['id']}",
            "versions": mod["versions"],
            "latest": mod["latest"],
            "kinds": mod["kinds"],
            "latest_sizes": {f["kind"]: f["size"] for f in latest},
            "files": len(mod["files"]),
        })
    return out


def get_mod(cfg: Config, mod_id: str, version: int | None = None, kind: str = "lua",
            max_chars: int = 60_000) -> dict[str, Any]:
    mid = normalize_mod_id(mod_id)
    if kind not in ("lua", "prm"):
        raise ToolError("kind must be 'lua' or 'prm'.")
    mod = scan_mods(cfg).get(mid)
    if not mod:
        raise ToolError(f"Mod {mid} is not in the local cache {cfg.mods_dir}. It is downloaded when a map using it is started.")
    ver = mod["latest"] if version is None else int(version)
    files = [f for f in mod["files"] if f["version"] == ver and f["kind"] == kind]
    if not files:
        avail = sorted({(f["version"], f["kind"]) for f in mod["files"]})
        raise ToolError(f"No {kind} file for {mid} version {ver}. Available (version, kind): {avail}")
    f = files[0]
    code = _read_text(cfg.mods_dir / f["file"])
    truncated = len(code) > max_chars
    return {
        "id": mid,
        "version": ver,
        "kind": kind,
        "file": f["file"],
        "size": f["size"],
        "other_files": [x["file"] for x in mod["files"] if x is not f],
        "truncated": truncated,
        "code": code[:max_chars],
    }


def search_mod_code(cfg: Config, regex: str, limit: int = 50, context: int = 2,
                    latest_only: bool = True, ignore_case: bool = True) -> dict[str, Any]:
    try:
        rx = re.compile(regex, re.IGNORECASE if ignore_case else 0)
    except re.error as e:
        raise ToolError(f"Bad regex: {e}") from e
    limit = max(1, min(int(limit), 500))
    context = max(0, min(int(context), 10))
    mods = scan_mods(cfg)
    results = []
    files_scanned = 0
    for mod in sorted(mods.values(), key=lambda m: m["id"].lower()):
        files = [f for f in mod["files"] if not latest_only or f["version"] == mod["latest"]]
        for f in files:
            files_scanned += 1
            lines = _read_text(cfg.mods_dir / f["file"]).splitlines()
            for i, line in enumerate(lines):
                if rx.search(line):
                    lo, hi = max(0, i - context), min(len(lines), i + context + 1)
                    results.append({
                        "file": f["file"],
                        "mod": f"mod-{mod['id']}",
                        "version": f["version"],
                        "line": i + 1,
                        "context": "\n".join(f"{n + 1:>5}{'>' if n == i else ':'} {lines[n]}" for n in range(lo, hi)),
                    })
                    if len(results) >= limit:
                        return {"matches": results, "files_scanned": files_scanned, "truncated": True}
    return {"matches": results, "files_scanned": files_scanned, "truncated": False}


# ---------------------------------------------------------------- game JSON data

_PATH_TOKEN = re.compile(r"[^.\[\]]+|\[(\d+)\]")


def _parse_path(path: str) -> list[str | int]:
    out: list[str | int] = []
    for m in _PATH_TOKEN.finditer(path.strip()):
        tok = m.group(1) if m.group(1) is not None else m.group(0)
        out.append(int(tok) if tok.isdigit() else tok)
    return out


def _preview(value: Any, max_chars: int) -> Any:
    text = json.dumps(value, ensure_ascii=False)
    if len(text) <= max_chars:
        return value
    if isinstance(value, dict):
        return {"_type": "object", "_keys": list(value.keys())[:100], "_size": len(value), "_preview": text[:max_chars]}
    if isinstance(value, list):
        return {"_type": "array", "_length": len(value), "_preview": text[:max_chars]}
    return text[:max_chars] + "..."


def list_game_data_files(cfg: Config) -> list[str]:
    proj = cfg.project_dir
    if not proj.is_dir():
        return []
    files = [p.name for p in proj.glob("*.json")]
    files += [f"interfaces/{p.name}" for p in (proj / "interfaces").glob("*.json")]
    return sorted(files)


@lru_cache(maxsize=16)
def _load_json_cached(path: str, mtime: float) -> Any:
    with open(path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def game_data_query(cfg: Config, file: str, path: str | None = None, key_search: str | None = None,
                    limit: int = 50, max_chars: int = 4000) -> dict[str, Any]:
    allowed = list_game_data_files(cfg)
    name = file.replace("\\", "/").strip()
    if not name.endswith(".json"):
        name += ".json"
    if name not in allowed:
        raise ToolError(f"File {file!r} is not available. Allowed: {allowed}")
    full = cfg.project_dir / name
    data = _load_json_cached(str(full), full.stat().st_mtime)

    if key_search:
        try:
            rx = re.compile(key_search, re.IGNORECASE)
        except re.error as e:
            raise ToolError(f"Bad regex: {e}") from e
        hits: list[dict[str, Any]] = []

        def walk(node: Any, p: str) -> None:
            if len(hits) >= limit:
                return
            if isinstance(node, dict):
                for k, v in node.items():
                    sub = f"{p}.{k}" if p else str(k)
                    if rx.search(str(k)) or (isinstance(v, str) and rx.search(v)):
                        hits.append({"path": sub, "value": _preview(v, 300)})
                        if len(hits) >= limit:
                            return
                    walk(v, sub)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    sub = f"{p}[{i}]"
                    if isinstance(v, str) and rx.search(v):
                        hits.append({"path": sub, "value": _preview(v, 300)})
                    walk(v, sub)

        walk(data, "")
        return {"file": name, "key_search": key_search, "hits": hits, "truncated": len(hits) >= limit}

    node = data
    if path:
        for tok in _parse_path(path):
            try:
                if isinstance(node, list):
                    node = node[int(tok)]
                elif isinstance(node, dict):
                    node = node[str(tok)] if str(tok) in node else node[tok]  # type: ignore[index]
                else:
                    raise KeyError(tok)
            except (KeyError, IndexError, ValueError, TypeError):
                hint = list(node.keys())[:50] if isinstance(node, dict) else (f"array of {len(node)}" if isinstance(node, list) else type(node).__name__)
                raise ToolError(f"Path {path!r}: cannot resolve {tok!r}. Available here: {hint}") from None
    return {"file": name, "path": path or "", "value": _preview(node, max_chars)}


# ---------------------------------------------------------------- bundled API index & guide

BUNDLED_INDEX_LABEL = "WSUS tree of game 258.4018 (10.10.2026) + api-cheatsheet v4"


@lru_cache(maxsize=1)
def load_api_index() -> list[dict[str, Any]]:
    """Bundled index shipped with the package (WSUS v258.4018 + cheatsheet notes)."""
    raw = resources.files("ws_mcp").joinpath("data/api_index.json").read_text(encoding="utf-8")
    return json.loads(raw)["entries"]


_active_cache: dict[str, Any] = {"key": None, "value": None}


def active_index(cfg: Config | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Live index imported from the game (import_api_dump) with bundled entries as fallback.

    A bundled entry is dropped when the live dump covers it: the same path is live, the path was
    probed and is absent, or its parent object was expanded in the dump (so the live listing is
    authoritative for that level). Notes from the cheatsheet are always kept.
    """
    bundled = load_api_index()
    live = apidump.load_live(cfg) if cfg is not None else None
    if not live:
        return bundled, {"active": "bundled", "bundled": BUNDLED_INDEX_LABEL}
    key = apidump._live_cache["key"]
    if _active_cache["key"] != key:
        live_paths = {e["path"] for e in live["entries"]}
        expanded = set(live.get("expanded", []))
        absent = set(live.get("absent", []))
        keep = [e for e in bundled
                if e.get("kind") == "note" or not e.get("path")
                or (e["path"] not in live_paths and e["path"] not in absent
                    and apidump.parent_path(e["path"]) not in expanded)]
        meta = {"active": "live + bundled fallback", "engine_version": live.get("engine_version"),
                "live_entries": len(live["entries"]), "bundled_fallback_entries": len(keep),
                "bundled": BUNDLED_INDEX_LABEL}
        _active_cache.update(key=key, value=(live["entries"] + keep, meta))
    return _active_cache["value"]


@lru_cache(maxsize=1)
def load_guide() -> list[str]:
    return resources.files("ws_mcp").joinpath("data/guide-ru.md").read_text(encoding="utf-8").splitlines()


def _tokens(q: str) -> list[str]:
    return [t for t in re.split(r"[\s,;]+", q.lower()) if t]


def search_api(query: str, limit: int = 20, kind: str | None = None, cfg: Config | None = None) -> dict[str, Any]:
    toks = _tokens(query)
    if not toks:
        raise ToolError("Empty query.")
    entries, meta = active_index(cfg)
    scored = []
    for e in entries:
        if kind and e.get("kind") != kind:
            continue
        name = e.get("name", "").lower()
        path = e.get("path", "").lower()
        text = " ".join(str(e.get(k, "")) for k in ("signature", "text", "section")).lower()
        score = 0
        for t in toks:
            if t == name:
                score += 10
            elif t in name:
                score += 5
            if t in path:
                score += 3
            if t in text:
                score += 1
        if all(t in f"{name} {path} {text}" for t in toks):
            score += 4
        if score:
            scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    return {"query": query, "index": meta, "results": [e for _, e in scored[: max(1, min(limit, 100))]],
            "total_matches": len(scored)}


def search_guide(query: str, limit: int = 8, context: int = 3) -> dict[str, Any]:
    lines = load_guide()
    toks = _tokens(query)
    if not toks:
        raise ToolError("Empty query.")
    heading = ""
    headings: list[str] = []
    for line in lines:
        if line.startswith("#"):
            heading = line.lstrip("#").strip()
        headings.append(heading)
    scored = []
    for i, line in enumerate(lines):
        low = line.lower()
        s = sum(low.count(t) for t in toks)
        if s:
            s += 3 * sum(1 for t in toks if t in headings[i].lower())
            scored.append((s, i))
    scored.sort(key=lambda x: (-x[0], x[1]))
    used: set[int] = set()
    results = []
    for _, i in scored:
        if any(abs(i - j) <= context for j in used):
            continue
        used.add(i)
        lo, hi = max(0, i - context), min(len(lines), i + context + 1)
        results.append({"section": headings[i], "line": i + 1, "snippet": "\n".join(lines[lo:hi])})
        if len(results) >= limit:
            break
    return {"query": query, "results": results}


# ---------------------------------------------------------------- live API dump

def api_dump_script(cfg: Config, root: str = "root", space: str = "gameplay", depth: int = 12,
                    max_nodes: int = 20000, array_sample: int = 1, compact: bool = False, seeds: bool = True,
                    raw: bool = True, to_table: bool = True, autorun: bool = True) -> dict[str, Any]:
    from . import dumpscript
    entries, meta = active_index(cfg)
    try:
        res = dumpscript.render(root=root, space=space, depth=depth, max_nodes=max_nodes,
                                array_sample=array_sample, raw=raw, seeds=seeds, to_table=to_table,
                                compact=compact, autorun=autorun, index_entries=entries)
    except ValueError as e:
        raise ToolError(str(e)) from e
    res["seeds_from"] = meta["active"]
    res["how_to_run"] = dumpscript.HOW_TO_RUN
    res["next"] = "import_api_dump (dump_id=%s)" % res["dump_id"]
    return res


def import_api_dump(cfg: Config, file: str | None = None, which: str = "log.txt", dump_id: str | None = None,
                    space: str | None = None, allow_partial: bool = False, reset: bool = False,
                    dry_run: bool = False, limit: int = 200) -> dict[str, Any]:
    try:
        return apidump.import_dump(cfg, load_api_index(), file=file, which=which, dump_id=dump_id, space=space,
                                   allow_partial=allow_partial, reset=reset, dry_run=dry_run, limit=limit)
    except apidump.DumpError as e:
        raise ToolError(str(e)) from e


def api_index_status(cfg: Config) -> dict[str, Any]:
    ev = cfg.game_dir / "engine-version.txt"
    engine = _read_text(ev, 100).strip() if ev.is_file() else None
    st = _index_status(cfg, engine)
    st["game_engine_version"] = engine
    return st


# ---------------------------------------------------------------- logs

def read_log(cfg: Config, tail: int = 200, grep: str | None = None, which: str = "log.txt") -> dict[str, Any]:
    if not LOG_NAME_RE.match(which):
        raise ToolError("which must be a plain file name like 'log.txt', 'log_prev.txt' or 'lagDiagnostics.log'.")
    cands = cfg.log_candidates(which)
    found = next((p for p in cands if p.is_file()), None)
    if not found:
        return {
            "found": False,
            "message": (f"{which} not found. It usually appears in <game>/gen/ after the game runs with "
                        "developer mode or after an error. Set WS_LOG_PATH to point to it explicitly."),
            "searched": [str(p) for p in cands],
        }
    tail = max(1, min(int(tail), 5000))
    lines = _read_text(found, 50_000_000).splitlines()
    total = len(lines)
    if grep:
        try:
            rx = re.compile(grep, re.IGNORECASE)
        except re.error as e:
            raise ToolError(f"Bad regex: {e}") from e
        lines = [f"{n + 1}: {l}" for n, l in enumerate(lines) if rx.search(l)]
    else:
        lines = [f"{n + 1}: {l}" for n, l in enumerate(lines)]
    st = found.stat()
    return {
        "found": True,
        "path": str(found),
        "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime)),
        "total_lines": total,
        "returned": min(tail, len(lines)),
        "lines": "\n".join(lines[-tail:]),
    }


# ---------------------------------------------------------------- write

WRITE_WARNING = (
    "Wouw (#existing-mods-customize-help, 30.07.2023): editing mod files bypassing the in-game editor "
    "may hit the release file instead of the draft and lead to kicks/bans. This tool writes ONLY to "
    "modsStorage/draft; open the mod in the in-game editor (developer mode) to apply/release it."
)


def write_draft(cfg: Config, mod_id: str, code: str, create: bool = False, extension: str = ".lua") -> dict[str, Any]:
    name = mod_id.strip()
    if name.lower().startswith("mod-"):
        name = name[4:]
    if not DRAFT_NAME_RE.match(name):
        raise ToolError("mod_id may contain only letters, digits, '_' and '-' (max 64 chars), no paths.")
    if extension not in (".lua", ".prm"):
        raise ToolError("extension must be '.lua' or '.prm'.")
    data = code.encode("utf-8")
    if len(data) > MAX_DRAFT_BYTES:
        raise ToolError(f"Code is too large ({len(data)} bytes, max {MAX_DRAFT_BYTES}).")
    if not cfg.mods_dir.is_dir():
        raise ToolError(f"modsStorage not found at {cfg.mods_dir}. Check WS_GAME_DIR.")
    draft = cfg.draft_dir
    if draft.is_symlink():
        raise ToolError("draft folder is a symlink; refusing to write.")
    if not draft.is_dir():
        if not create:
            raise ToolError(f"Draft folder {draft} does not exist. It is normally created by the game when you edit a mod "
                            "in developer mode. Pass create=True to create it anyway.")
        draft.mkdir(parents=False, exist_ok=True)
    root = draft.resolve()
    target = (draft / f"{name}{extension}").resolve()
    if os.path.normcase(str(target.parent)) != os.path.normcase(str(root)):
        raise ToolError("Resolved path escapes the draft folder; refusing.")
    if target.exists() and (target.is_symlink() or not target.is_file()):
        raise ToolError("Target exists and is not a regular file; refusing.")

    backup = None
    if target.exists():
        stamp = time.strftime("%Y%m%d-%H%M%S")
        backup = target.with_name(f"{target.name}.{stamp}.bak")
        n = 1
        while backup.exists():
            backup = target.with_name(f"{target.name}.{stamp}-{n}.bak")
            n += 1
        shutil.copy2(target, backup)

    fd, tmp = tempfile.mkstemp(prefix=".ws-mcp-", suffix=".tmp", dir=root)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, target)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return {
        "written": str(target),
        "bytes": len(data),
        "backup": str(backup) if backup else None,
        "warning": WRITE_WARNING,
    }
