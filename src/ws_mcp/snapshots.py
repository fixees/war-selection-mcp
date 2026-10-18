"""Per-version snapshots of game data and the API index, and structured diffs between them.

Snapshots live in <data_dir>/snapshots/<id>/ (never in the game folder):
    manifest.json       versions, file hashes, sizes
    <name>.json.gz      normalized content (sorted keys, compact) of tracked JSON files
    api.json.gz         active API index: path -> kind/type/signature
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from .config import Config

SNAP_FORMAT = 1
# Files whose content is stored and diffed semantically; other *.json under the project dir are hashed only.
CONTENT_FILES = ("gameplay.json", "visual.json", "legacyIds.json", "main.json", "render.json", "preload.json")
MAX_CONTENT_BYTES = 64_000_000
GAME_VERSION_RE = re.compile(r"Game Version:\s*(\S+)")
_hash_cache: dict[str, tuple[int, int, str]] = {}


class SnapshotError(Exception):
    pass


def snap_root(cfg: Config) -> Path:
    return cfg.data_dir / "snapshots"


def _check_outside_game(cfg: Config) -> None:
    d = os.path.normcase(str(cfg.data_dir.resolve()))
    g = os.path.normcase(str(cfg.game_dir.resolve()))
    if d == g or d.startswith(g + os.sep):
        raise SnapshotError(f"Data folder {cfg.data_dir} is inside the game folder; refusing. Set WS_MCP_DATA_DIR.")


def _sha256(path: Path) -> str:
    st = path.stat()
    key = str(path)
    c = _hash_cache.get(key)
    if c and c[0] == st.st_mtime_ns and c[1] == st.st_size:
        return c[2]
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    _hash_cache[key] = (st.st_mtime_ns, st.st_size, h.hexdigest())
    return h.hexdigest()


def _game_version(cfg: Config) -> str | None:
    for name in ("log.txt", "log_prev.txt"):
        p = next((c for c in cfg.log_candidates(name) if c.is_file()), None)
        if not p:
            continue
        with open(p, "rb") as fh:
            head = fh.read(400_000).decode("utf-8", "replace")
        m = GAME_VERSION_RE.search(head)
        if m:
            return m.group(1)
    return None


def current_state(cfg: Config) -> dict[str, Any]:
    """Hashes of tracked game files without storing anything."""
    g = cfg.game_dir
    ev = g / "engine-version.txt"
    engine = ev.read_text(encoding="utf-8", errors="replace").strip()[:40] if ev.is_file() else None
    files: dict[str, dict[str, Any]] = {}
    proj = cfg.project_dir
    if proj.is_dir():
        for p in sorted(proj.rglob("*.json")):
            if p.is_file() and not p.is_symlink():
                rel = p.relative_to(proj).as_posix()
                files[rel] = {"size": p.stat().st_size, "sha256": _sha256(p)}
    if ev.is_file():
        files["<game>/engine-version.txt"] = {"size": ev.stat().st_size, "sha256": _sha256(ev)}
    combined = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()
    return {"engine_version": engine, "game_version": _game_version(cfg), "files": files, "content_hash": combined}


def list_snapshots(cfg: Config) -> list[dict[str, Any]]:
    root = snap_root(cfg)
    out = []
    if root.is_dir():
        for d in root.iterdir():
            m = d / "manifest.json"
            if m.is_file():
                try:
                    man = json.loads(m.read_text(encoding="utf-8"))
                except ValueError:
                    continue
                if man.get("format") == SNAP_FORMAT:
                    man["dir"] = str(d)
                    out.append(man)
    out.sort(key=lambda m: (m.get("seq", 0), m.get("created", ""), m["id"]))
    return out


def _api_map(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {}
    for e in entries:
        if e.get("kind") == "note" or not e.get("path"):
            continue
        out[e["path"]] = {k: e[k] for k in ("kind", "type", "signature") if e.get(k) is not None}
    return out


def _write_gz(path: Path, obj: Any) -> None:
    data = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    with gzip.open(path, "wb", compresslevel=6) as fh:
        fh.write(data)


def _read_gz(path: Path) -> Any:
    with gzip.open(path, "rb") as fh:
        return json.loads(fh.read().decode("utf-8"))


def snapshot_game(cfg: Config, api_entries: list[dict[str, Any]], api_label: str, force: bool = False,
                  label: str | None = None) -> dict[str, Any]:
    """Store a snapshot unless the latest one has the same content hash and API index (or force=True)."""
    _check_outside_game(cfg)
    if not cfg.project_dir.is_dir():
        raise SnapshotError(f"Game data folder not found: {cfg.project_dir}. Check WS_GAME_DIR.")
    state = current_state(cfg)
    api = _api_map(api_entries)
    api_hash = hashlib.sha256(json.dumps(api, sort_keys=True).encode()).hexdigest()
    snaps = list_snapshots(cfg)
    last = snaps[-1] if snaps else None
    if last and not force and last["content_hash"] == state["content_hash"] and last.get("api_hash") == api_hash:
        return {"taken": False, "reason": "unchanged since the latest snapshot", "snapshot": last["id"],
                "snapshots": len(snaps)}
    stamp = time.strftime("%Y%m%d-%H%M%S")
    sid = f"{state['engine_version'] or 'unknown'}-{stamp}-{state['content_hash'][:8]}"
    if label:
        if not re.match(r"^[A-Za-z0-9_.-]{1,40}$", label):
            raise SnapshotError("label: 1-40 letters, digits, '_', '-', '.'")
        sid += f"-{label}"
    root = snap_root(cfg)
    root.mkdir(parents=True, exist_ok=True)
    base, n = sid, 1
    while (root / sid).exists():
        n += 1
        sid = f"{base}-{n}"
    tmp = Path(tempfile.mkdtemp(prefix=".snap-", dir=root))
    stored, skipped = [], []
    try:
        for name in CONTENT_FILES:
            p = cfg.project_dir / name
            if not p.is_file():
                continue
            if p.stat().st_size > MAX_CONTENT_BYTES:
                skipped.append({"file": name, "reason": f"larger than {MAX_CONTENT_BYTES} bytes; hash only"})
                continue
            try:
                data = json.loads(p.read_text(encoding="utf-8-sig"))
            except ValueError as e:
                skipped.append({"file": name, "reason": f"invalid JSON: {e}"})
                continue
            _write_gz(tmp / f"{name}.gz", data)
            stored.append(name)
        _write_gz(tmp / "api.json.gz", api)
        manifest = {"format": SNAP_FORMAT, "id": sid, "seq": (last.get("seq", len(snaps)) if last else 0) + 1, "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "engine_version": state["engine_version"], "game_version": state["game_version"],
                    "content_hash": state["content_hash"], "api_hash": api_hash, "api_index": api_label,
                    "api_entries": len(api), "files": state["files"], "stored": stored, "skipped": skipped}
        (tmp / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, root / sid)
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    reason = "first snapshot" if not last else (
        "engine version changed" if last.get("engine_version") != state["engine_version"] else
        "game data changed" if last["content_hash"] != state["content_hash"] else
        "API index changed" if last.get("api_hash") != api_hash else "forced")
    return {"taken": True, "reason": reason, "snapshot": sid, "dir": str(root / sid),
            "engine_version": state["engine_version"], "game_version": state["game_version"],
            "stored": stored, "skipped": skipped, "snapshots": len(snaps) + 1}


def snapshot_status(cfg: Config) -> dict[str, Any]:
    snaps = list_snapshots(cfg)
    if not snaps:
        return {"snapshots": 0, "state": "none"}
    try:
        state = current_state(cfg)
    except OSError as e:
        return {"snapshots": len(snaps), "state": f"error: {e}"}
    last = snaps[-1]
    same = last["content_hash"] == state["content_hash"]
    return {"snapshots": len(snaps), "latest": last["id"], "latest_engine": last.get("engine_version"),
            "state": "current" if same else "changed",
            "detail": None if same else ("Game files differ from the latest snapshot; the next server start, "
                                         "snapshot_game or diff_game_versions stores a new one.")}


# ---------------------------------------------------------------- diff

def _deep_diff(a: Any, b: Any, path: str, out: list[dict[str, Any]], cap: int) -> None:
    if len(out) >= cap:
        return
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            p = f"{path}.{k}" if path else str(k)
            if k not in a:
                out.append({"path": p, "op": "added", "new": _short(b[k])})
            elif k not in b:
                out.append({"path": p, "op": "removed", "old": _short(a[k])})
            else:
                _deep_diff(a[k], b[k], p, out, cap)
            if len(out) >= cap:
                return
    elif isinstance(a, list) and isinstance(b, list) and not (_is_scalar_list(a) and _is_scalar_list(b)):
        for i in range(max(len(a), len(b))):
            p = f"{path}[{i}]"
            if i >= len(a):
                out.append({"path": p, "op": "added", "new": _short(b[i])})
            elif i >= len(b):
                out.append({"path": p, "op": "removed", "old": _short(a[i])})
            else:
                _deep_diff(a[i], b[i], p, out, cap)
            if len(out) >= cap:
                return
    elif a != b:
        out.append({"path": path, "op": "changed", "old": _short(a), "new": _short(b)})


def _is_scalar_list(v: list) -> bool:
    return len(v) <= 64 and all(not isinstance(x, (dict, list)) for x in v)


def _short(v: Any, n: int = 300) -> Any:
    if isinstance(v, (dict, list)):
        s = json.dumps(v, sort_keys=True, ensure_ascii=False)
        return s if len(s) <= n else s[:n] + "..."
    if isinstance(v, str) and len(v) > n:
        return v[:n] + "..."
    return v


def _load(snap: dict[str, Any], name: str) -> Any:
    p = Path(snap["dir"]) / f"{name}.gz"
    return _read_gz(p) if p.is_file() else None


def _unit_paths(legacy: Any) -> dict[str, str]:
    return {str(k): v for k, v in ((legacy or {}).get("units") or {}).items()}


def _semantic(a: dict[str, Any], b: dict[str, Any], cap: int) -> dict[str, Any]:
    ga, gb = _load(a, "gameplay.json") or {}, _load(b, "gameplay.json") or {}
    la, lb = _load(a, "legacyIds.json") or {}, _load(b, "legacyIds.json") or {}
    ua, ub = _unit_paths(la), _unit_paths(lb)
    path_to_id = {v: k for k, v in ub.items()} | {v: k for k, v in ua.items() if v not in ub.values()}
    units = {
        "added": [{"id": int(k) if k.isdigit() else k, "unit": ub[k]} for k in sorted(set(ub) - set(ua), key=_num)],
        "removed": [{"id": int(k) if k.isdigit() else k, "unit": ua[k]} for k in sorted(set(ua) - set(ub), key=_num)],
        "renamed": [{"id": int(k) if k.isdigit() else k, "old": ua[k], "new": ub[k]}
                    for k in sorted(set(ua) & set(ub), key=_num) if ua[k] != ub[k]],
    }
    build: list[dict[str, Any]] = []
    ba, bb = ga.get("build") or [], gb.get("build") or []
    for i in range(max(len(ba), len(bb))):
        x = ba[i] if i < len(ba) else None
        y = bb[i] if i < len(bb) else None
        if x == y:
            continue
        unit = (y or x or {}).get("unit") if isinstance(y or x, dict) else None
        ch: list[dict[str, Any]] = []
        _deep_diff(x, y, "", ch, 50)
        build.append({"build_id": i, "unit": unit, "unit_id": _maybe_int(path_to_id.get(unit)),
                      "op": "added" if x is None else "removed" if y is None else "changed", "changes": ch})
        if len(build) >= cap:
            break
    res: dict[str, list] = {"researches": [], "upgrades": []}
    ra, rb = ga.get("researches") or {}, gb.get("researches") or {}
    for key, label in (("list", "researches"), ("upgrades", "upgrades")):
        xa, xb = ra.get(key) or [], rb.get(key) or []
        for i in range(max(len(xa), len(xb))):
            x = xa[i] if i < len(xa) else None
            y = xb[i] if i < len(xb) else None
            if x == y:
                continue
            ch = []
            _deep_diff(x, y, "", ch, 50)
            entry = {"id": i, "op": "added" if x is None else "removed" if y is None else "changed", "changes": ch}
            if isinstance(y or x, dict) and (y or x).get("unit"):
                entry["unit"] = (y or x)["unit"]
            res[label].append(entry)
            if len(res[label]) >= cap:
                break
    auras: list[dict[str, Any]] = []
    _deep_diff(ga.get("auras"), gb.get("auras"), "auras", auras, cap)
    overrides: list[dict[str, Any]] = []
    _deep_diff((ga.get("scenes") or {}).get("unitOverrides"), (gb.get("scenes") or {}).get("unitOverrides"),
               "scenes.unitOverrides", overrides, cap)
    scalars = []
    for k in sorted(set(ga) | set(gb)):
        if not isinstance(ga.get(k), (dict, list)) and not isinstance(gb.get(k), (dict, list)) and ga.get(k) != gb.get(k):
            scalars.append({"key": k, "old": ga.get(k), "new": gb.get(k)})
    envs = {"added": sorted(set((lb.get("envs") or {})) - set((la.get("envs") or {})), key=_num),
            "removed": sorted(set((la.get("envs") or {})) - set((lb.get("envs") or {})), key=_num)}
    return {"units": units, "build_rules": build, "researches": res["researches"], "upgrades": res["upgrades"],
            "auras": auras, "unit_overrides": overrides, "gameplay_scalars": scalars, "envs": envs}


def _num(k: Any) -> tuple:
    s = str(k)
    return (0, int(s), "") if s.isdigit() else (1, 0, s)


def _maybe_int(v: Any) -> Any:
    return int(v) if isinstance(v, str) and v.isdigit() else v


def _api_diff(a: dict[str, Any], b: dict[str, Any], cap: int) -> dict[str, Any]:
    xa, xb = _load(a, "api.json") or {}, _load(b, "api.json") or {}
    added = sorted(set(xb) - set(xa))
    removed = sorted(set(xa) - set(xb))
    changed = []
    for p in sorted(set(xa) & set(xb)):
        if xa[p] != xb[p]:
            changed.append({"path": p, "old": xa[p], "new": xb[p]})
    return {"index_a": a.get("api_index"), "index_b": b.get("api_index"),
            "added": len(added), "removed": len(removed), "changed": len(changed),
            "added_paths": added[:cap], "removed_paths": [{"path": p, **xa[p]} for p in removed[:cap]],
            "changed_paths": changed[:cap]}


def _resolve(snaps: list[dict[str, Any]], ref: str | None, default_index: int) -> dict[str, Any]:
    if ref is None:
        return snaps[default_index]
    hits = [s for s in snaps if s["id"] == ref] or [s for s in snaps if s["id"].startswith(ref)] \
        or [s for s in snaps if s.get("engine_version") == ref]
    if not hits:
        raise SnapshotError(f"Snapshot {ref!r} not found. Available: {[s['id'] for s in snaps]}")
    return hits[-1]


def diff_versions(cfg: Config, a: str | None = None, b: str | None = None, limit: int = 100,
                  write_full: bool = True) -> dict[str, Any]:
    snaps = list_snapshots(cfg)
    if len(snaps) < 2:
        return {"snapshots": len(snaps), "diff": None,
                "latest": snaps[-1]["id"] if snaps else None,
                "message": ("Only one snapshot exists. It is the baseline: the next game update (new engine or "
                            "changed game data) creates a second snapshot automatically on server start or with "
                            "snapshot_game, and diff_game_versions will compare them."
                            if snaps else "No snapshots yet. Call snapshot_game (also taken on server start).")}
    sa, sb = _resolve(snaps, a, -2), _resolve(snaps, b, -1)
    if sa["id"] == sb["id"]:
        raise SnapshotError("a and b are the same snapshot.")
    cap = max(1, min(int(limit), 5000))
    fa, fb = sa["files"], sb["files"]
    files = {"added": sorted(set(fb) - set(fa)), "removed": sorted(set(fa) - set(fb)),
             "changed": sorted(k for k in set(fa) & set(fb) if fa[k]["sha256"] != fb[k]["sha256"])}
    sem = _semantic(sa, sb, 100_000)
    generic: dict[str, Any] = {}
    for name in CONTENT_FILES:
        if name in ("gameplay.json", "legacyIds.json"):
            continue
        if name in files["changed"]:
            x, y = _load(sa, name), _load(sb, name)
            if x is None or y is None:
                generic[name] = "changed (content not stored in one of the snapshots)"
                continue
            out: list[dict[str, Any]] = []
            _deep_diff(x, y, "", out, cap)
            generic[name] = out
    api = _api_diff(sa, sb, 100_000)
    full = {"a": sa["id"], "b": sb["id"], "engine": {"from": sa.get("engine_version"), "to": sb.get("engine_version")},
            "game_version": {"from": sa.get("game_version"), "to": sb.get("game_version")}, "files": files,
            "gameplay": sem, "other_json": generic, "api": api}
    full_path = None
    if write_full:
        _check_outside_game(cfg)
        d = cfg.data_dir / "diffs"
        d.mkdir(parents=True, exist_ok=True)
        full_path = d / f"{sa['id']}__{sb['id']}.json"
        full_path.write_text(json.dumps(full, indent=1, ensure_ascii=False), encoding="utf-8")

    def cut(v: Any) -> Any:
        if isinstance(v, list):
            return v[:cap]
        if isinstance(v, dict):
            return {k: cut(x) for k, x in v.items()}
        return v

    counts = {
        "files_changed": len(files["changed"]), "units_added": len(sem["units"]["added"]),
        "units_removed": len(sem["units"]["removed"]), "units_renamed": len(sem["units"]["renamed"]),
        "build_rules_changed": len(sem["build_rules"]), "researches_changed": len(sem["researches"]),
        "upgrades_changed": len(sem["upgrades"]), "api_added": api["added"], "api_removed": api["removed"],
        "api_changed": api["changed"],
    }
    return {"snapshots": len(snaps), **cut({k: v for k, v in full.items()}), "counts": counts,
            "full_diff_file": str(full_path) if full_path else None,
            "note": "Lists are cut to `limit` entries; the full diff is in full_diff_file."}
