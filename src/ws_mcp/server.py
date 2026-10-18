"""MCP server (stdio) exposing War Selection modding tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import core
from .config import Config

INSTRUCTIONS = (
    "Tools for War Selection (Glyph Worlds) Lua modding on the local PC: cached mods in modsStorage, "
    "game data JSON in Cache/Projects/WarSelection, a bundled API index (WSUS tree of game 258.4018 + "
    "community cheatsheet) and a Russian modding guide. Everything is read-only except write_draft, "
    "which only writes into modsStorage/draft. Never invent API names: check search_api first."
)

mcp = FastMCP("war-selection-mcp", instructions=INSTRUCTIONS)
RO = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


def _cfg() -> Config:
    return Config.from_env()


def _run(fn, *args, **kwargs) -> Any:
    try:
        return fn(*args, **kwargs)
    except core.ToolError as e:
        return {"error": str(e)}


@mcp.tool(annotations=RO)
def game_info() -> dict:
    """Game paths (WS_GAME_DIR), engine version, number of cached mods, draft folder and log presence."""
    return _run(core.game_info, _cfg())


@mcp.tool(annotations=RO)
def list_mods(query: str | None = None) -> list | dict:
    """List cached mods from modsStorage: id, versions, latest, kinds (lua/prm), sizes. Optional substring filter on id."""
    return _run(core.list_mods, _cfg(), query)


@mcp.tool(annotations=RO)
def get_mod(mod_id: str, version: int | None = None, kind: str = "lua", max_chars: int = 60000) -> dict:
    """Source of a cached mod. mod_id like 'mod-6gqH17D5rDl' or '6gqH17D5rDl'; version defaults to latest; kind 'lua' or 'prm'."""
    return _run(core.get_mod, _cfg(), mod_id, version, kind, max_chars)


@mcp.tool(annotations=RO)
def search_mod_code(regex: str, limit: int = 50, context: int = 2, latest_only: bool = True) -> dict:
    """Regex search (case-insensitive) across cached mod code; returns file:line with context lines."""
    return _run(core.search_mod_code, _cfg(), regex, limit, context, latest_only)


@mcp.tool(annotations=RO)
def game_data_query(file: str, path: str | None = None, key_search: str | None = None,
                    limit: int = 50, max_chars: int = 4000) -> dict:
    """Query Cache/Projects/WarSelection JSON (gameplay, visual, legacyIds, preload, styles, main, render, interfaces/...).
    Use `path` like 'build[10].costBuilding' or 'auras.0', or `key_search` (regex over keys and string values)."""
    return _run(core.game_data_query, _cfg(), file, path, key_search, limit, max_chars)


@mcp.tool(annotations=RO)
def search_api(query: str, limit: int = 20, kind: str | None = None) -> dict:
    """Search the bundled API index (function names/paths/signatures from wsunitstats.com WSUS tree v258.4018,
    plus verified notes from our api-cheatsheet with sources). kind: 'function', 'event', 'field' or 'note'."""
    return _run(core.search_api, query, limit, kind)


@mcp.tool(annotations=RO)
def search_guide(query: str, limit: int = 8) -> dict:
    """Search the bundled Russian modding guide (guide-ru.md); returns section, line and snippet."""
    return _run(core.search_guide, query, limit)


@mcp.tool(annotations=RO)
def read_log(tail: int = 200, grep: str | None = None, which: str = "log.txt") -> dict:
    """Tail of a game log (default gen/log.txt; also log_prev.txt, lagDiagnostics.log, ...) searched in likely
    locations; optional regex filter.
    Reports clearly where it looked if the log is missing. WS_LOG_PATH overrides the location."""
    return _run(core.read_log, _cfg(), tail, grep, which)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False))
def write_draft(mod_id: str, code: str, create: bool = False, extension: str = ".lua") -> dict:
    """WRITE: save mod code to modsStorage/draft/<mod_id>.lua (only there). Refuses if the draft folder is
    missing unless create=True; backs up an existing file to .bak first; path-traversal safe.
    Warning: Wouw warned that editing mod files outside the in-game editor can hit the release file and get you
    banned — only drafts are touched here; apply them via the in-game editor."""
    return _run(core.write_draft, _cfg(), mod_id, code, create, extension)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
