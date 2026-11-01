"""In-game developer console helpers.

Confirmed by the developer (Wouw, Discord, 2026-10-18): F8 console assignments use `=`, e.g.
`session.gameplay.dumpToFile=dump.txt`.

Live sample (engine 277, 2026-11-01): the argument must be a **filename only** (no directories,
no absolute path — those print `Invalid file name`). The file is written in the **game root**
(next to the executable). The payload is a binary match/session dump (map, mods, params,
tagged KV with players/devMode, then a zlib asset-path table) — **not** a Lua API tree. Use
`api_dump_script` / WSDUMP for API indexing.
"""

from __future__ import annotations

import json
import re
import struct
import zlib
from pathlib import Path
from typing import Any

from .config import Config
from .core import ToolError

SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")
PRINTABLE_RE = re.compile(rb"[\x20-\x7e]{3,}")


def console_call_syntax() -> dict[str, Any]:
    return {
        "assignment": "=",
        "example": "session.gameplay.dumpToFile=dump.txt",
        "confirmed_by": "Wouw (developer), Discord, 2026-10-18",
        "path_rule": "filename only",
        "path_rule_confirmed": "2026-11-01, engine 277 live test",
        "note": ("F8 console calls that set a field use `=` (not a function call). "
                 "dumpToFile accepts a bare filename only; absolute or nested paths are rejected "
                 "(`Invalid file name`). The file lands in the game root."),
    }


def dump_to_file_candidates(cfg: Config, filename: str = "dump.txt") -> list[str]:
    """Where a relative dump filename is most likely to appear after the console call."""
    if not SAFE_NAME_RE.match(filename) or ".." in filename or "/" in filename or "\\" in filename:
        raise ToolError("filename: 1-80 letters/digits/._- , no path separators")
    cands = [
        cfg.game_dir / filename,          # verified 2026-11-01: game root
        cfg.game_dir / "gen" / filename,
        cfg.data_dir / filename,
    ]
    return [str(p) for p in cands]


def dump_to_file_plan(cfg: Config, filename: str = "dump.txt", absolute: bool = False) -> dict[str, Any]:
    """Exact F8 console line and where to look for the file. Does not run the game.

    Default absolute=False: engine 277 rejects absolute/ nested paths (`Invalid file name`) and
    writes the bare filename into the game root (verified 2026-11-01).
    """
    if not SAFE_NAME_RE.match(filename) or "/" in filename or "\\" in filename or ".." in filename:
        raise ToolError("filename: 1-80 letters/digits/._- , no path separators (engine rejects paths)")
    search = dump_to_file_candidates(cfg, filename)
    if absolute:
        # Kept for diagnostics; the live engine rejects these.
        target = cfg.data_dir / filename
        line = f"session.gameplay.dumpToFile={target}"
        line_fwd = f"session.gameplay.dumpToFile={target.as_posix()}"
        warning = ("Live engine 277 (2026-11-01) rejects absolute paths with `Invalid file name`. "
                   "Prefer absolute=false (filename only); the file appears in the game root.")
        recommended = str(cfg.game_dir / filename)
    else:
        line = f"session.gameplay.dumpToFile={filename}"
        line_fwd = line
        target = cfg.game_dir / filename
        warning = None
        recommended = str(target)
    out = {
        **console_call_syntax(),
        "console_line": line,
        "console_line_posix": line_fwd,
        "recommended_path": recommended,
        "search_paths": search,
        "absolute_requested": bool(absolute),
        "format": "session_dump",
        "format_note": ("Verified 2026-11-01: binary match/session dump (map code, mod list including "
                        "draft/<id>_<ver>, match params, tagged KV with players/devMode, zlib asset-path "
                        "table). Not a Lua API tree — do not import_api_dump. Use api_dump_script for API."),
        "useful_for_api_index": False,
        "steps": [
            "Launch the game (developer mode / private match) so the session exists.",
            f"Open the F8 console and run: {line_fwd if not absolute else f'session.gameplay.dumpToFile={filename}'}",
            "Call inspect_console_dump with the filename (e.g. dump.txt); it resolves under the game root.",
        ],
    }
    if warning:
        out["warning"] = warning
    return out


def _extract_printable(raw: bytes, start: int = 0, end: int | None = None) -> list[str]:
    chunk = raw[start:end]
    return [m.group().decode("ascii", "replace") for m in PRINTABLE_RE.finditer(chunk)]


def _parse_tagged_kv(raw: bytes, start: int, end: int) -> dict[str, Any]:
    """Best-effort parse of the tagged key/value section (u32-len key, tag 0x04, u32-len value)."""
    out: dict[str, Any] = {}
    i = start
    while i + 8 <= end:
        # find a plausible key: u32 len in 1..40 and ascii key
        if i + 4 > end:
            break
        n = struct.unpack_from("<I", raw, i)[0]
        if 1 <= n <= 40 and i + 4 + n + 1 + 4 <= end:
            key_b = raw[i + 4:i + 4 + n]
            if all(65 <= c < 123 or c in (95,) for c in key_b):  # rough A-z _
                key = key_b.decode("ascii")
                tag = raw[i + 4 + n]
                vn = struct.unpack_from("<I", raw, i + 4 + n + 1)[0]
                vstart = i + 4 + n + 1 + 4
                if tag == 4 and 0 <= vn <= 100_000 and vstart + vn <= end:
                    val_b = raw[vstart:vstart + vn]
                    try:
                        text = val_b.decode("utf-8")
                    except UnicodeDecodeError:
                        text = val_b.decode("utf-8", "replace")
                    if key == "data":
                        try:
                            out[key] = json.loads(text)
                        except ValueError:
                            out[key] = text
                    elif text in ("true", "false"):
                        out[key] = text == "true"
                    else:
                        out[key] = text
                    i = vstart + vn
                    continue
        i += 1
    return out


def _parse_zlib_paths(blob: bytes, limit: int = 200) -> dict[str, Any]:
    """Decompress zlib tail and pull WarSelection/... path strings (asset path table)."""
    try:
        dec = zlib.decompress(blob)
    except zlib.error as e:
        return {"ok": False, "error": str(e)}
    paths = [m.group().decode("ascii", "replace")
             for m in re.finditer(rb"WarSelection/[A-Za-z0-9_./-]{3,120}", dec)]
    # unique preserve order
    seen: set[str] = set()
    uniq = []
    for p in paths:
        if p not in seen:
            seen.add(p)
            uniq.append(p)
    prefixes: dict[str, int] = {}
    for p in uniq:
        seg = p.split("/", 2)[1] if p.startswith("WarSelection/") and p.count("/") >= 1 else "?"
        prefixes[seg] = prefixes.get(seg, 0) + 1
    return {
        "ok": True,
        "uncompressed_size": len(dec),
        "path_count": len(uniq),
        "path_sample": uniq[: min(30, limit)],
        "path_prefixes": dict(sorted(prefixes.items(), key=lambda kv: -kv[1])[:20]),
        "has_unitType": b"unitType" in dec,
        "has_root_dot": b"root." in dec,
        "has_session_dot": b"session." in dec,
        "has_WSDUMP": b"WSDUMP" in dec,
    }


def parse_session_dump(raw: bytes) -> dict[str, Any]:
    """Describe a dumpToFile session dump (engine 277 sample)."""
    tokens = _extract_printable(raw, 0, min(len(raw), 4096))
    map_code = next((t for t in tokens if re.fullmatch(r"[0-9a-fA-F]+_\d+", t)), None)
    mods = [t for t in tokens if re.fullmatch(r"(?:draft/)?[A-Za-z0-9]{11}_\d+", t)]
    params = [t for t in tokens if "=" in t and not t.startswith("{")]
    drafts = [t for t in mods if t.startswith("draft/")]

    # zlib offset: first zlib header 78 9C / 78 01 / 78 DA / 78 5E (x^)
    zoff = None
    for magic in (b"x\x9c", b"x\x01", b"x\xda", b"x^", b"x\x5e"):
        at = raw.find(magic)
        if at >= 0 and (zoff is None or at < zoff):
            # prefer late offset after header (sample @1128); skip tiny early false positives
            if at >= 64:
                zoff = at
    zlib_info: dict[str, Any] | None = None
    if zoff is not None:
        zlib_info = _parse_zlib_paths(raw[zoff:])
        zlib_info["offset"] = zoff

    # tagged KV: look for 'data' key near first '{'
    j0 = raw.find(b"{")
    tagged: dict[str, Any] = {}
    if j0 >= 0:
        # scan a window before JSON through a bit after
        tagged = _parse_tagged_kv(raw, max(0, j0 - 40), min(len(raw), (zoff or len(raw))))

    kind = "session_dump"
    api_useful = False
    if zlib_info and zlib_info.get("has_WSDUMP"):
        kind = "wsdump_embedded"
        api_useful = True
    elif raw[:4] == b"GEM1" or (len(raw) >= 2 and raw[:2] == b"\x1f\x8b"):
        kind = "other_binary"

    return {
        "kind": kind,
        "size": len(raw),
        "map": map_code,
        "mods": mods,
        "draft_mods": drafts,
        "params": params,
        "tagged": tagged,
        "zlib": zlib_info,
        "useful_for_api_index": api_useful,
        "summary": ("Match/session binary: map + enabled mods (incl. draft/) + params + tagged "
                    "players/devMode + zlib asset-path table. Not a Lua API dump."),
    }


def inspect_console_dump(cfg: Config, file: str, max_chars: int = 4000) -> dict[str, Any]:
    """Read a file produced by dumpToFile (or any path) and describe it without importing as API."""
    p = Path(file)
    tried: list[str] = []
    if not p.is_file():
        name = p.name
        tried.append(str(p))
        cand_name = name if SAFE_NAME_RE.match(name) else "dump.txt"
        for c in dump_to_file_candidates(cfg, cand_name):
            tried.append(c)
            if Path(c).is_file():
                p = Path(c)
                break
        else:
            return {"found": False, "tried": tried,
                    "message": ("File not found. Use dump_to_file_plan(absolute=false) and run the "
                                "filename-only F8 line; the file appears in the game root.")}
    raw_full = p.read_bytes()
    size = len(raw_full)
    # parse uses up to 2MB head + full file for zlib (file is ~200KB typically; cap 8MB)
    parse_raw = raw_full if size <= 8_000_000 else raw_full[:8_000_000]
    parsed = parse_session_dump(parse_raw)

    head_n = max(1, min(int(max_chars), 100_000))
    # text head for display: prefer printable tokens over mojibake
    text_head = raw_full[: min(size, head_n * 4)].decode("utf-8", "replace")[:head_n]

    kind = parsed["kind"]
    # keep legacy guesses when not a session dump
    if kind == "session_dump":
        kind_guess = "session_dump"
    elif text_head.lstrip().startswith("{") or text_head.lstrip().startswith("["):
        kind_guess = "maybe_json"
    elif "WSDUMP" in text_head[:2000]:
        kind_guess = "wsdump_log"
    elif raw_full[:2] == b"\x1f\x8b":
        kind_guess = "gzip"
    elif raw_full[:4] == b"GEM1":
        kind_guess = "gem1"
    else:
        kind_guess = "unknown"

    return {
        "found": True,
        "path": str(p),
        "size": size,
        "kind_guess": kind_guess,
        "format": kind_guess if kind_guess == "session_dump" else "unknown",
        "session": parsed if kind_guess == "session_dump" else None,
        "useful_for_api_index": parsed.get("useful_for_api_index", False),
        "head": text_head if kind_guess != "session_dump" else None,
        "note": ("session_dump (verified 2026-11-01): use for match setup / asset path inventory only. "
                 "For Lua API indexing run api_dump_script and import_api_dump (WSDUMP), not this file."
                 if kind_guess == "session_dump" else
                 ("Format not identified for automatic import. If kind_guess is wsdump_log, use "
                  "import_api_dump on the log instead.")),
        **console_call_syntax(),
    }
