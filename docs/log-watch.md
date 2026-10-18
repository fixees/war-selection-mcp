# Live log and error watcher

## Log file

`<WS_GAME_DIR>/gen/log.txt`, override with `WS_LOG_PATH`.

Verified on a live install (engine 264):

- The game recreates the file on start. The first line is `Log cleared in thread <n> at <zone> timezone <local date>`.
- Every line written by the engine starts with `YYYY-MM-DD HH:MM:SS ` in UTC. Continuation lines of a multi-line message have no timestamp.
- The header contains `Engine Version: 264` and `Game Version: 264.4021.<hash>_<n>`.
- `log_prev.txt` (previous session) is mentioned in player reports; it did not exist on the reference install at the time of writing. When present it is used for rotation, otherwise the new file is read from the start.

## log_tail

`log_tail(cursor=None, max_lines=500, initial_lines=50)` returns `lines`, `next_cursor`, `rotated`, `more`.

- Cursor: `<id>:<byte offset>`, where `<id>` is a hash of the first line of the file. The first line holds the clear time, so a new session gets a new id.
- Without a cursor: the last `initial_lines` lines and a cursor at the end of the file.
- Only complete lines are returned; a line being written is delivered on the next call.
- If the id differs or the offset is past the end of the file (recreated or truncated), `rotated` is true. If `log_prev.txt` starts with the old id, its unread rest is returned first (`from_prev`), then the new file from the start.
- Up to 2 MB per call; `more` is true if there is more to read.
- Invalid UTF-8 is replaced, CRLF is accepted.

## Watcher

`watch_log_start(from_start=False, warnings=True)` starts a daemon thread that polls the log every 0.5 s with the same cursor logic. `watch_log_poll(since_seq, limit)` returns events with `seq`; pass the returned `next_seq` next time. The last 1000 events are kept (`dropped_before` reports a gap). `watch_log_stop()` stops the thread; events stay readable.

A pending error block is emitted when the next timestamped line or a blank line arrives, or after 1.5 s without new lines.

Event fields: `seq`, `kind`, `time` (log time, UTC), `line_no` (since watcher start), `script`, `status`, `message`, `frames` (`[{line, function}]`), `chunk_preview`, `chunk_line`, `mod_file`, `source`.

`source` is a list of candidates `{mod, version, file, source: draft|cache, path, active, line, code, excerpt}`:

1. An explicit `/modsStorage/[draft/]<id>_<ver>-<hash>.lua` in the error header maps directly to that file.
2. Otherwise the `[string "<preview>..."]` chunk name is matched against the beginning of cached mod files and drafts; mods listed in the latest `Using gameplay|visual modifications:` line are marked `active` and ranked first.

The line is `chunk_line`, or the first frame with a positive line. The excerpt is up to 3 lines on each side, the error line marked with `>`.

Terminal: `war-selection-mcp --watch-log [--from-start]`, output per event:

```
[2026-10-18 05:54:00] lua_error mod-EEEEEEEEEE5 draft/EEEEEEEEEE5_2-abcdefabcdef0123.lua:3
    attempt to index a nil value (global 'zones')
    at line 3 in onStart
        1: function onStart(var)
        2:   local a = 1
        3>   zones.f_addCircle(1, 2, 3)
        4: end
```

## Formats

Verified: seen in player logs attached to Discord (#new-mod-creation 2023-09, bug reports 2024-11 and 2025-02) or in `gen/log.txt` of the reference install.

| Kind | Format | Status |
|---|---|---|
| lua_error | `Lua program <script> run (Error) failed:` | verified (2023, 2025) |
| lua_error | `Error: Lua program /modsStorage/draft/<id>_<ver>-<hash>.lua run failed:` | verified (2023) |
| compile_error | `Lua compilation error for: /modsStorage/draft/<file>.lua` followed by `\t[string "..."]:<n>: <msg>` | verified (2023) |
| frames | `\tError occured at:` then `\tLine:<n> function:[<name>]`, `Line:-1` for native frames | verified |
| message | plain text or `[string "<preview>..."]:<n>: <msg>`; block ends with a blank line or the next timestamped line | verified |
| active mods | `Using gameplay modifications: <id>_<ver>, draft/<id>_<ver>`, same for `visual` | verified (2023, 2025) |
| warning | `Obsolete interface address: ...` | verified (reference install) |
| warning | `Using obsolete parameter '<old>'. Use '<new>' instead` | verified (2023) |
| warning | `Value is read only...` as a standalone line | assumed; seen only as an error message |
| engine_error | `Global exception: ...`, `Code panic at ...` | verified (2023, 2024); engine failures, may follow a mod error |
| lua_error | standalone `[string "..."]:<n>: <msg>` line with a timestamp (from `log()`/`error()` output) | assumed |

Not handled: errors printed by mods through `log()` in a custom format, and `Rethrow unknown exception at:` / `Scene manager program ... error ...` lines (engine internals without a script reference).

Assumed: chunk previews are the first characters of the mod file (seen in all collected samples, not documented). Drafts are matched by the same rule.
