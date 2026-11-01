"""gen/modsWorkspace — engine mod workspace mirror (verified 2026-11-01, engine 277)."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import Config
from .core import ToolError, normalize_mod_id

WS_ID_RE = re.compile(r"^\d+\.json$")


def workspace_dir(cfg: Config) -> Path:
    return cfg.game_dir / "gen" / "modsWorkspace"


def _mtime(p: Path) -> str | None:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except OSError:
        return None


def _list_workspace_files(d: Path) -> list[Path]:
    if not d.is_dir():
        return []
    return sorted(p for p in d.glob("*.json") if p.is_file() and not p.name.endswith(".operations"))


def _load_json(p: Path) -> dict[str, Any]:
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise ToolError(f"Cannot read workspace JSON {p.name}: {e}") from e
    if not isinstance(data, dict):
        raise ToolError(f"Workspace {p.name} is not a JSON object")
    return data


def _ops_path(main: Path) -> Path:
    return Path(str(main) + ".operations")


def _sources_dir(main: Path) -> Path:
    return Path(str(main) + ".sources")


def _brief_mod(m: dict[str, Any]) -> dict[str, Any]:
    src = m.get("source")
    return {
        "code": m.get("code"),
        "name": m.get("name"),
        "type": m.get("type"),
        "version": m.get("version"),
        "latestVersion": m.get("latestVersion"),
        "owned": m.get("owned"),
        "hasSource": m.get("hasSource"),
        "sourceRevision": m.get("sourceRevision"),
        "uploadedRevision": m.get("uploadedRevision"),
        "source_bytes": len(src) if isinstance(src, str) else 0,
        "units": len(m.get("units") or []) if isinstance(m.get("units"), list) else 0,
        "parameters": m.get("parameters") if isinstance(m.get("parameters"), dict) else {},
    }


def list_mods_workspace(cfg: Config, workspace_id: str | None = None) -> dict[str, Any]:
    """List gen/modsWorkspace/<id>.json (+ .operations / .sources). Read-only."""
    d = workspace_dir(cfg)
    if not d.is_dir():
        return {
            "found": False,
            "path": str(d),
            "workspaces": [],
            "note": ("No modsWorkspace folder. Appears when a developer-mode map/session prepares mods "
                     "(verified engine 277, 2026-11-01)."),
        }
    files = _list_workspace_files(d)
    if workspace_id:
        wid = workspace_id if workspace_id.endswith(".json") else f"{workspace_id}.json"
        files = [p for p in files if p.name == wid]
        if not files:
            return {"found": False, "path": str(d), "workspace_id": workspace_id, "workspaces": [],
                    "note": f"No workspace file matching {wid}."}
    out = []
    for p in files:
        try:
            data = _load_json(p)
        except ToolError as e:
            out.append({"id": p.stem, "file": p.name, "path": str(p), "error": str(e)})
            continue
        ops_p = _ops_path(p)
        src_d = _sources_dir(p)
        rev_file = src_d / "revision"
        sources = sorted(x.name for x in src_d.iterdir()) if src_d.is_dir() else []
        ops_n = 0
        if ops_p.is_file():
            try:
                ops = json.loads(ops_p.read_text(encoding="utf-8-sig"))
                ops_n = len(ops) if isinstance(ops, list) else 0
            except (OSError, ValueError):
                ops_n = -1
        attachments = data.get("attachments") or []
        mods = data.get("mods") or []
        out.append({
            "id": p.stem,
            "file": p.name,
            "path": str(p),
            "size": p.stat().st_size,
            "mtime": _mtime(p),
            "identity": data.get("identity"),
            "revision": data.get("revision"),
            "testedRevision": data.get("testedRevision"),
            "version": data.get("version"),
            "initialized": data.get("initialized"),
            "attachments": len(attachments) if isinstance(attachments, list) else 0,
            "mods": len(mods) if isinstance(mods, list) else 0,
            "owned_mods": sum(1 for m in mods if isinstance(m, dict) and m.get("owned")) if isinstance(mods, list) else 0,
            "operations_file": str(ops_p) if ops_p.is_file() else None,
            "operations_count": ops_n,
            "sources_dir": str(src_d) if src_d.is_dir() else None,
            "sources": sources,
            "sources_revision": (rev_file.read_text(encoding="utf-8", errors="replace").strip()
                                 if rev_file.is_file() else None),
            "behavior_keys": sorted((data.get("behaviors") or {}).keys()) if isinstance(data.get("behaviors"), dict) else [],
        })
    return {
        "found": True,
        "path": str(d),
        "workspaces": out,
        "count": len(out),
        "note": ("Verified 2026-11-01 (engine 277): identity is account:WarSelection:<mapHex>; "
                 "attachments list enabled mods (code/file/parameters/type); mods[] holds metadata and "
                 "inlined Lua `source`; .sources/<code>.lua are id-only copies (byte-equal to the published "
                 "cache for non-drafts; draft source may be empty). .operations is a JSON array of source-fetch "
                 "jobs (kind=source, phase/status, workspaceRevision, privateDraft, scriptErrors). "
                 "The game still loads drafts from modsStorage/draft/<id>_<ver>-<hash>.lua (see gen/log.txt "
                 "FileLoader::load); workspace is a parallel mirror, not a replacement path for write_draft."),
    }


def get_mods_workspace(cfg: Config, workspace_id: str | None = None, mod_id: str | None = None,
                       include_source: bool = False, max_source_chars: int = 60000,
                       include_operations: bool = False, operations_limit: int = 50) -> dict[str, Any]:
    """Read one modsWorkspace JSON (latest by mtime if id omitted). Optional mod filter and operations."""
    d = workspace_dir(cfg)
    files = _list_workspace_files(d)
    if not files:
        return list_mods_workspace(cfg)
    if workspace_id:
        wid = workspace_id if workspace_id.endswith(".json") else f"{workspace_id}.json"
        files = [p for p in files if p.name == wid]
        if not files:
            raise ToolError(f"No workspace {wid} under {d}")
    else:
        files = sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)

    main = files[0]
    data = _load_json(main)
    max_source_chars = max(200, min(int(max_source_chars), 500_000))
    operations_limit = max(1, min(int(operations_limit), 500))

    mods_in = data.get("mods") if isinstance(data.get("mods"), list) else []
    attachments = data.get("attachments") if isinstance(data.get("attachments"), list) else []
    mid = normalize_mod_id(mod_id) if mod_id else None

    mods_out = []
    for m in mods_in:
        if not isinstance(m, dict):
            continue
        if mid and m.get("code") != mid:
            continue
        brief = _brief_mod(m)
        if include_source:
            src = m.get("source") if isinstance(m.get("source"), str) else ""
            brief["source"] = src[:max_source_chars]
            brief["source_truncated"] = len(src) > max_source_chars
        # sidecar source file
        src_file = _sources_dir(main) / f"{m.get('code')}.lua"
        if src_file.is_file():
            brief["sources_file"] = src_file.name
            brief["sources_file_size"] = src_file.stat().st_size
        mods_out.append(brief)

    atts = [a for a in attachments if isinstance(a, dict) and (not mid or a.get("code") == mid)]

    result: dict[str, Any] = {
        "found": True,
        "id": main.stem,
        "path": str(main),
        "size": main.stat().st_size,
        "mtime": _mtime(main),
        "identity": data.get("identity"),
        "revision": data.get("revision"),
        "testedRevision": data.get("testedRevision"),
        "version": data.get("version"),
        "initialized": data.get("initialized"),
        "attachments": atts,
        "mods": mods_out,
        "behaviors": {
            k: data["behaviors"].get(k)
            for k in ("version", "initialPhase", "victoryRules")
            if isinstance(data.get("behaviors"), dict) and k in data["behaviors"]
        },
        "sources_dir": str(_sources_dir(main)) if _sources_dir(main).is_dir() else None,
        "draft_path_note": ("Game loads draft Lua from modsStorage/draft/<id>_<ver>-<hash>.lua; "
                            "workspace .sources/<id>.lua is a mirror (often empty for new drafts). "
                            "write_draft targets the modsStorage/draft file."),
    }

    if include_operations:
        ops_p = _ops_path(main)
        if ops_p.is_file():
            try:
                ops = json.loads(ops_p.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as e:
                result["operations_error"] = str(e)
                ops = []
            if not isinstance(ops, list):
                ops = []
            if mid:
                ops = [o for o in ops if isinstance(o, dict) and o.get("code") == mid]
            result["operations_total"] = len(ops)
            result["operations"] = ops[:operations_limit]
            result["operations_truncated"] = len(ops) > operations_limit
        else:
            result["operations"] = []
            result["operations_total"] = 0

    if mid and not mods_out and not atts:
        result["note"] = f"No mod {mid} in this workspace."
    return result
