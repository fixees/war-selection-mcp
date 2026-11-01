"""In-game developer console helpers.

Confirmed by the developer (Wouw, Discord, 2026-10-18): F8 console assignments use `=`, e.g.
`session.gameplay.dumpToFile=dump.txt`. The exact on-disk format of that dump is not published;
this module only prepares the console line, finds candidate output paths, and inspects a produced
file without guessing a schema.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .config import Config
from .core import ToolError

SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


def console_call_syntax() -> dict[str, Any]:
    return {
        "assignment": "=",
        "example": "session.gameplay.dumpToFile=dump.txt",
        "confirmed_by": "Wouw (developer), Discord, 2026-10-18",
        "note": ("F8 console calls that set a field use `=` (not a function call). "
                 "Other dump/call forms are not covered here."),
    }


def dump_to_file_candidates(cfg: Config, filename: str = "dump.txt") -> list[str]:
    """Where a relative dump filename is most likely to appear after the console call."""
    if not SAFE_NAME_RE.match(filename) or ".." in filename or "/" in filename or "\\" in filename:
        raise ToolError("filename: 1-80 letters/digits/._- , no path separators")
    cands = [
        cfg.game_dir / filename,
        cfg.game_dir / "gen" / filename,
        cfg.data_dir / filename,
    ]
    # also absolute suggestion under data_dir
    return [str(p) for p in cands]


def dump_to_file_plan(cfg: Config, filename: str = "dump.txt", absolute: bool = True) -> dict[str, Any]:
    """Exact F8 console line and where to look for the file. Does not run the game."""
    if absolute:
        target = cfg.data_dir / filename
        # console likely wants forward or backslashes; give both, prefer abs path under data_dir
        # Use forward slashes; Windows game accepts them in many Glyph paths. Also give native.
        console_path = str(target)
        line = f"session.gameplay.dumpToFile={console_path}"
        line_fwd = f"session.gameplay.dumpToFile={target.as_posix()}"
    else:
        if not SAFE_NAME_RE.match(filename):
            raise ToolError("filename: 1-80 letters/digits/._-")
        line = f"session.gameplay.dumpToFile={filename}"
        line_fwd = line
        target = None
    return {
        **console_call_syntax(),
        "console_line": line,
        "console_line_posix": line_fwd,
        "recommended_path": str(target) if target else filename,
        "search_paths": dump_to_file_candidates(cfg, filename if not absolute else Path(filename).name),
        "format": "unknown",
        "format_note": ("Output format is not documented. After the file appears, call "
                        "inspect_console_dump with its path; import into the API index only once "
                        "the layout is identified. Do not assume WSDUMP or JSON."),
        "steps": [
            "Launch the game (developer mode) so Cache/Projects and the log refresh.",
            f"Open the F8 console and run: {line_fwd}",
            "Call inspect_console_dump on the produced file (search_paths if relative name).",
        ],
    }


def inspect_console_dump(cfg: Config, file: str, max_chars: int = 4000) -> dict[str, Any]:
    """Read a file produced by dumpToFile (or any path) and describe it without parsing as API."""
    p = Path(file)
    if not p.is_file():
        # try candidates
        name = p.name
        tried = [str(p)]
        for c in dump_to_file_candidates(cfg, name if SAFE_NAME_RE.match(name) else "dump.txt"):
            tried.append(c)
            if Path(c).is_file():
                p = Path(c)
                break
        else:
            return {"found": False, "tried": tried,
                    "message": "File not found. Run the console line from dump_to_file_plan, then retry."}
    raw = p.read_bytes()[: max(1, min(int(max_chars) * 4, 2_000_000))]
    text = raw.decode("utf-8", "replace")
    head = text[: max(1, min(int(max_chars), 100_000))]
    kind = "unknown"
    if text.lstrip().startswith("{") or text.lstrip().startswith("["):
        kind = "maybe_json"
    elif "WSDUMP" in text[:2000]:
        kind = "wsdump_log"
    elif text.startswith("\x1f\x8b") or raw[:2] == b"\x1f\x8b":
        kind = "gzip"
    elif raw[:4] == b"GEM1":
        kind = "gem1"
    return {
        "found": True, "path": str(p), "size": p.stat().st_size, "kind_guess": kind,
        "head": head, "format": "unknown",
        "note": ("Format not identified for automatic import. If kind_guess is wsdump_log, use "
                 "import_api_dump on the log instead. Otherwise keep the file and compare with a "
                 "future known sample."),
        **console_call_syntax(),
    }
