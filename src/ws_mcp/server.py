"""MCP server (stdio) exposing War Selection modding tools."""

from __future__ import annotations

import threading
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import core, logwatch, modtools
from .config import Config

INSTRUCTIONS = (
    "Tools for War Selection (Glyph Worlds) Lua modding on the local PC: cached mods in modsStorage, "
    "game data JSON in Cache/Projects/WarSelection, an API index (live dump imported from the game when "
    "available, otherwise the bundled WSUS tree of game 258.4018 + community cheatsheet) and a Russian "
    "modding guide. Drafts live in modsStorage/draft/<id>_<ver>-<hash>.lua and are created by the game "
    "('Edit script'); write_draft only overwrites an existing draft. The game folder is otherwise read-only; "
    "import_api_dump, snapshot_game and diff_game_versions write only to the per-user data folder. After a game "
    "update use diff_game_versions and mod_impact. While testing a mod use watch_log_start / watch_log_poll. "
    "Never invent API names: check search_api first."
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
    """List mods: published cache in modsStorage (id, versions, latest, kinds, sizes) and developer-mode drafts in
    modsStorage/draft (`draft` field). Optional substring filter on id."""
    return _run(core.list_mods, _cfg(), query)


@mcp.tool(annotations=RO)
def get_mod(mod_id: str, version: int | None = None, kind: str = "lua", max_chars: int = 60000,
            source: str = "auto") -> dict:
    """Source of a mod. mod_id like 'mod-6gqH17D5rDl' or '6gqH17D5rDl'; version defaults to latest; kind 'lua'
    or 'prm'. source: 'auto' (developer-mode draft in modsStorage/draft if present, else published cache),
    'draft' or 'cache'."""
    return _run(core.get_mod, _cfg(), mod_id, version, kind, max_chars, source)


@mcp.tool(annotations=RO)
def search_mod_code(regex: str, limit: int = 50, context: int = 2, latest_only: bool = True,
                    include_drafts: bool = True) -> dict:
    """Regex search (case-insensitive) across cached mod code and drafts; returns file:line with context lines."""
    return _run(core.search_mod_code, _cfg(), regex, limit, context, latest_only, True, include_drafts)


@mcp.tool(annotations=RO)
def game_data_query(file: str, path: str | None = None, key_search: str | None = None,
                    limit: int = 50, max_chars: int = 4000) -> dict:
    """Query Cache/Projects/WarSelection JSON (gameplay, visual, legacyIds, preload, styles, main, render, interfaces/...).
    Use `path` like 'build[10].costBuilding' or 'auras.0', or `key_search` (regex over keys and string values)."""
    return _run(core.game_data_query, _cfg(), file, path, key_search, limit, max_chars)


@mcp.tool(annotations=RO)
def search_api(query: str, limit: int = 20, kind: str | None = None) -> dict:
    """Search the API index: the live dump imported with import_api_dump (current engine) when present,
    with the bundled index as fallback (wsunitstats.com WSUS tree v258.4018 + verified notes from the
    api-cheatsheet). kind: 'function', 'event', 'field' or 'note'. Result `index` shows which is active."""
    return _run(core.search_api, query, limit, kind, _cfg())


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
             kind: str = "auto", source: str = "auto") -> dict:
    """Static check of mod Lua code (pass `code`, or `mod_id` of a cached mod): Lua 5.4 syntax plus known
    War Selection pitfalls (math.random in gameplay mods, missing root.f_recreateModifiedUnitTypes(),
    visual mods changing game state, math.atan2, removed/renamed functions, unknown addMod events,
    undefined handlers, unknown f_* names with suggestions). kind: auto | gameplay | visual.
    With mod_id, source: auto (draft if present, else cache) | draft | cache."""
    return _run(modtools.lint_mod, _cfg(), code, mod_id, version, kind, source)


@mcp.tool(annotations=RO)
def diff_mod(mod_id: str, v1: int | None = None, v2: int | None = None, kind: str = "lua",
             context: int = 3, draft: bool = False) -> dict:
    """Unified diff between two cached versions of a mod (default: previous vs latest). draft=true compares
    published version v1 (default latest) with the developer-mode draft in modsStorage/draft."""
    return _run(modtools.diff_mod, _cfg(), mod_id, v1, v2, kind, context, 60000, draft)


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


@mcp.tool(annotations=RO)
def api_dump_script(root: str = "root", space: str = "gameplay", depth: int = 12, max_nodes: int = 20000,
                    array_sample: int = 1, compact: bool = False, seeds: bool = True, raw: bool = True,
                    to_table: bool = True, autorun: bool = True) -> dict:
    """Lua script for the in-game developer console / a dev-mode mod that dumps the `root` API tree into
    gen/log.txt as WSDUMP lines (read-only: indexes fields under pcall, never calls f_* functions).
    root: start path ('root', 'root.unitType[0]', 'root.session.visual'); space: 'gameplay' (gameplay mod
    root) or 'visual' (visual mod root). seeds=true embeds known names from the active index so removed
    names are detected even if the engine does not allow pairs(). compact=true returns one line for the
    console. Arrays are sampled (array_sample elements) and written as []. Then call import_api_dump."""
    return _run(core.api_dump_script, _cfg(), root, space, depth, max_nodes, array_sample, compact, seeds,
                raw, to_table, autorun)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False))
def import_api_dump(file: str | None = None, which: str = "log.txt", dump_id: str | None = None,
                    space: str | None = None, allow_partial: bool = False, reset: bool = False,
                    dry_run: bool = False, limit: int = 200) -> dict:
    """Parse WSDUMP lines from gen/log.txt (or `which`='log_prev.txt', or an explicit `file`), build the live
    API index and report the diff against the bundled WSUS v258.4018 index (added / removed / changed paths,
    unexplored subtrees to dump next). Writes only to the per-user data folder (WS_MCP_DATA_DIR,
    default %LOCALAPPDATA%/war-selection-mcp), never to the game folder. Dumps of different subtrees are
    merged; a new engine version replaces the old index (backup kept). dry_run=true writes nothing.
    A dump without END is refused unless allow_partial=true."""
    return _run(core.import_api_dump, _cfg(), file, which, dump_id, space, allow_partial, reset, dry_run, limit)


@mcp.tool(annotations=RO)
def api_index_status() -> dict:
    """Which API index is active (live dump or bundled), its engine version, entry counts, imported dumps,
    and whether it is stale compared to engine-version.txt in the game folder."""
    return _run(core.api_index_status, _cfg())


WRITE_DATA = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)


@mcp.tool(annotations=WRITE_DATA)
def snapshot_game(force: bool = False, label: str | None = None) -> dict:
    """Store a snapshot of the game state in the user data folder (never the game folder): hashes of all
    Cache/Projects/WarSelection JSON files and engine-version.txt, normalized content of gameplay.json,
    visual.json, legacyIds.json, main.json, render.json, preload.json, and the active API index. Skipped when
    nothing changed since the latest snapshot unless force=true. Also taken automatically on server start."""
    return _run(core.snapshot_game, _cfg(), force, label)


@mcp.tool(annotations=WRITE_DATA)
def diff_game_versions(a: str | None = None, b: str | None = None, limit: int = 100) -> dict:
    """Structured diff between two snapshots (default: previous vs latest; a/b accept a snapshot id, id prefix
    or engine version). Sections: changed files, unit types (legacyIds), build rules (cost, health, ...),
    researches and upgrades, auras, unit overrides, API index added/removed/changed signatures. Takes a new
    snapshot first if the game changed. With a single snapshot it explains that the next update produces the
    diff. The full diff is written to the data folder (diffs/)."""
    return _run(core.diff_game_versions, _cfg(), a, b, limit)


@mcp.tool(annotations=RO)
def mod_impact(a: str | None = None, b: str | None = None, limit: int = 200, include_drafts: bool = True) -> dict:
    """Which cached mods and drafts reference what changed between two snapshots: removed/renamed unit type
    ids (unitType[id]), changed build rules (build[i]), researches/upgrades ([i]), removed or changed API
    functions and fields. Returns file:line with the code line and the reason."""
    return _run(core.mod_impact, _cfg(), a, b, limit, include_drafts)


@mcp.tool(annotations=RO)
def log_tail(cursor: str | None = None, max_lines: int = 500, initial_lines: int = 50) -> dict:
    """Follow gen/log.txt: returns lines written since `cursor` and `next_cursor` for the next call. Without a
    cursor returns the last `initial_lines` lines. Detects the log being recreated at game start
    (rotated=true) and first returns the unread rest of the old session from log_prev.txt."""
    return _run(logwatch.tail, _cfg(), cursor, max_lines, initial_lines)


_watcher: logwatch.Watcher | None = None
_watch_lock = threading.Lock()


def _enrich(ev: dict) -> dict:
    cfg = _cfg()
    ev["source"] = modtools.resolve_source(cfg, ev, excerpt=True) if ev["kind"] in ("lua_error", "compile_error") else []
    ev.pop("active_gameplay", None)
    ev.pop("active_visual", None)
    return ev


@mcp.tool(annotations=RO)
def watch_log_start(from_start: bool = False, warnings: bool = True) -> dict:
    """Start a background watcher on gen/log.txt (from the current end, or from_start=true). It parses Lua
    run/compile errors and engine warnings, maps them to the draft or cached mod source (explicit
    /modsStorage path or [string "..."] chunk preview) with a code excerpt, and survives log recreation at
    game start. Read events with watch_log_poll."""
    global _watcher
    with _watch_lock:
        if _watcher and _watcher.running:
            return {"running": True, "already_running": True, "started_at": _watcher.started_at,
                    "next_seq": _watcher.seq}
        _watcher = logwatch.Watcher(_cfg(), enrich=_enrich, warnings=warnings)
        _watcher.start(from_start=from_start)
        return {"running": True, "started_at": _watcher.started_at, "cursor": _watcher.cursor,
                "next": "watch_log_poll(since_seq=0)"}


@mcp.tool(annotations=RO)
def watch_log_poll(since_seq: int = 0, limit: int = 100) -> dict:
    """New watcher events after `since_seq` (use next_seq from the previous call). Each event: seq, kind
    (lua_error, compile_error, warning, engine_error), time, script, message, frames, source (mod, draft/cache,
    file, line, excerpt)."""
    if _watcher is None:
        return {"running": False, "events": [], "next_seq": since_seq, "message": "Call watch_log_start first."}
    return _watcher.poll(since_seq, limit)


@mcp.tool(annotations=RO)
def watch_log_stop() -> dict:
    """Stop the background log watcher. Collected events stay available to watch_log_poll."""
    if _watcher is None:
        return {"running": False}
    _watcher.stop()
    return {"running": False, "events_total": _watcher.seq, "lines_read": _watcher.lines_read}


def _auto_snapshot() -> None:
    import os
    if os.environ.get("WS_MCP_AUTO_SNAPSHOT", "1").strip() in ("0", "false", "no"):
        return
    cfg = _cfg()
    if not cfg.project_dir.is_dir():
        return
    try:
        core.snapshot_game(cfg)
    except Exception:  # never block or crash the server because of a snapshot
        pass


def _watch_cli(from_start: bool, interval: float = 0.5) -> None:
    import sys
    import time
    w = logwatch.Watcher(_cfg(), enrich=_enrich)
    cur = w.cfg
    if from_start:
        p, _ = logwatch._log_paths(cur)
        w.cursor = logwatch.make_cursor(logwatch._file_id(p), 0) if p else None
    else:
        w.cursor = logwatch.tail(cur, None, initial_lines=0)["next_cursor"]
    print(f"watching {next((str(p) for p in cur.log_candidates() if p.is_file()), 'gen/log.txt (not found yet)')}"
          " - Ctrl+C to stop", file=sys.stderr)
    seq = 0
    try:
        while True:
            while w.step() >= 20_000:
                pass
            r = w.poll(seq, 1000)
            for ev in r["events"]:
                print(format_event(ev), flush=True)
            seq = r["next_seq"]
            time.sleep(interval)
    except KeyboardInterrupt:
        w.parser.flush()
        for ev in w.poll(seq, 1000)["events"]:
            print(format_event(ev), flush=True)


def format_event(ev: dict) -> str:
    head = f"[{ev.get('time') or '-'}] {ev['kind']}"
    src = (ev.get("source") or [None])[0]
    if src:
        loc = f"{src['mod']} {src['source']}/{src['file']}" + (f":{src['line']}" if src.get("line") else "")
        head += f" {loc}"
    elif ev.get("script"):
        head += f" {ev['script']}"
    elif ev.get("chunk_preview"):
        head += f' [string "{ev["chunk_preview"]}"]:{ev.get("chunk_line")}'
    out = [head, f"    {ev.get('message') or ''}".rstrip()]
    for fr in ev.get("frames", [])[:6]:
        out.append(f"    at line {fr['line']} in {fr['function']}")
    if src and src.get("excerpt"):
        out += ["    " + l for l in src["excerpt"].splitlines()]
    return "\n".join(out)


@mcp.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False))
def write_draft(mod_id: str, code: str, version: int | None = None, extension: str = ".lua") -> dict:
    """WRITE: overwrite the existing draft modsStorage/draft/<id>_<version>-<hash>.lua of a mod (latest draft
    version by default). The game creates that file when the mod script is opened with 'edit script' in
    developer mode; this tool never creates files and never touches published files in modsStorage.
    The previous content is backed up to the user data folder (draft-backups). Save/apply in the game."""
    return _run(core.write_draft, _cfg(), mod_id, code, version, extension)


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
    parser.add_argument("--dump-script", action="store_true",
                        help="print the in-game API dump script (Lua) and exit")
    parser.add_argument("--compact", action="store_true", help="with --dump-script: one line, no seeds")
    parser.add_argument("--dump-root", default="root", help="with --dump-script: start path (default root)")
    parser.add_argument("--space", choices=["gameplay", "visual"], default="gameplay",
                        help="with --dump-script: gameplay or visual mod root")
    parser.add_argument("--watch-log", action="store_true",
                        help="follow gen/log.txt and print Lua errors with mod source excerpts until Ctrl+C")
    parser.add_argument("--from-start", action="store_true", help="with --watch-log: read the current log from the start")
    parser.add_argument("--snapshot", action="store_true", help="take a game state snapshot (if changed) and exit")
    parser.add_argument("--import-dump", nargs="?", const="", metavar="FILE",
                        help="import WSDUMP lines from FILE (default: gen/log.txt) into the live API index and exit")
    ns = parser.parse_args(argv)
    if ns.watch_log:
        _watch_cli(ns.from_start)
        return
    if ns.snapshot:
        import json
        print(json.dumps(_run(core.snapshot_game, _cfg()), ensure_ascii=False, indent=1))
        return
    if ns.dump_script:
        res = core.api_dump_script(_cfg(), root=ns.dump_root, space=ns.space, compact=ns.compact,
                                   seeds=not ns.compact)
        print(res["script"])
        return
    if ns.import_dump is not None:
        import json
        import sys
        try:
            res = core.import_api_dump(_cfg(), file=ns.import_dump or None, limit=50)
        except core.ToolError as e:
            print(f"error: {e}", file=sys.stderr)
            raise SystemExit(1) from None
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return
    if ns.list_clients:
        for k, v in clientconfig.CLIENTS.items():
            print(f"{k:15} {v}")
        return
    if ns.print_config:
        print(clientconfig.render(ns.print_config))
        return
    threading.Thread(target=_auto_snapshot, name="ws-auto-snapshot", daemon=True).start()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
