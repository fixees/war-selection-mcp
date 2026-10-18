"""MCP server (stdio) exposing War Selection modding tools."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import core, modtools
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


@mcp.tool(annotations=RO)
def lint_mod(code: str | None = None, mod_id: str | None = None, version: int | None = None,
             kind: str = "auto") -> dict:
    """Static check of mod Lua code (pass `code`, or `mod_id` of a cached mod): Lua 5.4 syntax plus known
    War Selection pitfalls (math.random in gameplay mods, missing root.f_recreateModifiedUnitTypes(),
    visual mods changing game state, math.atan2, removed/renamed functions, unknown addMod events,
    undefined handlers, unknown f_* names with suggestions). kind: auto | gameplay | visual."""
    return _run(modtools.lint_mod, _cfg(), code, mod_id, version, kind)


@mcp.tool(annotations=RO)
def diff_mod(mod_id: str, v1: int | None = None, v2: int | None = None, kind: str = "lua",
             context: int = 3) -> dict:
    """Unified diff between two cached versions of a mod (default: previous vs latest)."""
    return _run(modtools.diff_mod, _cfg(), mod_id, v1, v2, kind, context)


@mcp.tool(annotations=RO)
def log_errors(which: str = "log.txt", tail: int | None = None, since: str | None = None, limit: int = 30) -> dict:
    """Parse Lua errors in gen/log.txt ('Lua program ... run (Error) failed' blocks and [string "..."]:N: lines),
    group repeats, and map them to cached mods (chunk preview match + mods active at that moment).
    `tail` limits to the last N log lines; `since` is 'YYYY-MM-DD[ HH:MM[:SS]]' in log time."""
    return _run(modtools.log_errors, _cfg(), which, tail, since, limit)


@mcp.tool(annotations=RO)
def find_examples(api_name: str, limit: int = 20, context: int = 3, per_mod: int = 2) -> dict:
    """Real usages of an API name across cached mods with file:line context, e.g. 'f_addCircle',
    'landscape.zones.f_addCircle', 'root.f_recreateModifiedUnitTypes'. Underscore paths are matched too."""
    return _run(modtools.find_examples, _cfg(), api_name, limit, context, per_mod)


@mcp.tool(annotations=RO)
def list_events_usage(event: str | None = None) -> dict:
    """Which addMod events each cached mod registers (latest versions), with totals per event.
    Optional `event` filter, e.g. 'onUnitInZone'."""
    return _run(modtools.list_events_usage, _cfg(), event)


@mcp.tool(annotations=RO)
def scaffold_mod(template: str | None = None, params: dict | None = None) -> dict | list:
    """Starter code built from guide recipes taken from working mods (returned, never written).
    Call without `template` to list templates: blank_gameplay, blank_visual, zone_trigger, unit_death,
    special_command_pair, unit_stat_tweak."""
    if not template:
        return modtools.list_templates()
    return _run(modtools.scaffold_mod, template, params)


@mcp.tool(annotations=RO)
def unit_lookup(query: str, limit: int = 20) -> dict:
    """Find unit types by legacy id or asset path substring (legacyIds.json) with their build rules from
    gameplay.json (cost, health). Example: 'worker', '201', 'airplane'."""
    return _run(modtools.unit_lookup, _cfg(), query, limit)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False))
def write_draft(mod_id: str, code: str, create: bool = False, extension: str = ".lua") -> dict:
    """WRITE: save mod code to modsStorage/draft/<mod_id>.lua (only there). Refuses if the draft folder is
    missing unless create=True; backs up an existing file to .bak first; path-traversal safe.
    Warning: Wouw warned that editing mod files outside the in-game editor can hit the release file and get you
    banned — only drafts are touched here; apply them via the in-game editor."""
    return _run(core.write_draft, _cfg(), mod_id, code, create, extension)


def main(argv: list[str] | None = None) -> None:
    import argparse

    from . import __version__, clientconfig

    parser = argparse.ArgumentParser(prog="war-selection-mcp",
                                     description="Local MCP server (stdio) for War Selection modding.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--print-config", metavar="CLIENT", choices=sorted(clientconfig.CLIENTS),
                        help="print a config snippet for CLIENT with this installation's paths and exit: "
                             + ", ".join(sorted(clientconfig.CLIENTS)))
    parser.add_argument("--list-clients", action="store_true", help="list supported --print-config clients and exit")
    ns = parser.parse_args(argv)
    if ns.list_clients:
        for k, v in clientconfig.CLIENTS.items():
            print(f"{k:15} {v}")
        return
    if ns.print_config:
        print(clientconfig.render(ns.print_config))
        return
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
