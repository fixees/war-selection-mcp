# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

## 0.4.0 - 2026-10-18

### Added

- Drafts: `list_mods`, `get_mod`, `search_mod_code`, `lint_mod`, `log_errors` and `game_info` read `modsStorage/draft/<id>_<version>-<hash16>.lua` next to the published cache. `get_mod` and `lint_mod` take `source` (`auto`, `draft`, `cache`); `auto` prefers the draft. `diff_mod(draft=true)` compares the published version with the draft.
- `snapshot_game`: stores hashes of all `Cache/Projects/WarSelection` JSON files and `engine-version.txt`, normalized content of gameplay, visual, legacyIds, main, render and preload JSON, and the active API index in `WS_MCP_DATA_DIR/snapshots`. Taken on server start when the game changed (`WS_MCP_AUTO_SNAPSHOT=0` disables it) and by `--snapshot`.
- `diff_game_versions`: diff of two snapshots by sections: files, unit types (legacyIds), build rules, researches, upgrades, auras, unit overrides, scalars, other JSON, API added/removed/changed signatures. Full diff in `WS_MCP_DATA_DIR/diffs`. With one snapshot it explains that the next update produces the diff.
- `mod_impact`: cached mods and drafts that reference removed or renamed unit type ids, changed build rules, researches, upgrades, removed or changed API functions and fields, with `file:line`.
- `log_tail`: cursor-based reading of `gen/log.txt`; detects recreation and truncation at game start and reads the rest of the old session from `log_prev.txt`.
- `watch_log_start`, `watch_log_poll`, `watch_log_stop`: background watcher for Lua run and compile errors, warnings and engine errors, mapped to the draft or cached mod file with a code excerpt.
- CLI: `--watch-log [--from-start]` prints errors live; `--snapshot`.
- Log parser: `Error: Lua program /modsStorage/draft/... run failed:`, `Lua compilation error for: ...`, `Using obsolete parameter`, `Obsolete interface address`, `Global exception`, `Code panic`; `draft/` entries in `Using ... modifications`.
- `docs/game-snapshots.md`, `docs/log-watch.md`.

### Changed

- `write_draft` overwrites only an existing draft `modsStorage/draft/<id>_<version>-<hash16>.lua` (latest version or `version`) with an atomic replace. The game creates draft files itself ("Edit script"), so the tool no longer creates files or folders.
- `log_errors` maps errors with an explicit `/modsStorage[/draft]` path directly to that file and matches chunk previews against drafts too.

### Removed

- `write_draft` parameter `create` and the `modsStorage/draft/<mod_id>.lua` naming. Backups are written to `WS_MCP_DATA_DIR/draft-backups` instead of `.bak` files next to the draft.

## 0.3.0 - 2026-10-18

### Added

- `api_dump_script`: Lua script for the in-game developer console or a dev-mode mod that dumps the `root` tree into `gen/log.txt` as `WSDUMP` records. Fields are read under `pcall` and `f_*` functions are never called. Child names come from `pairs`, a `tostring` listing, `toTable` (array elements only) and seeds from the active index. The native `log(obj)` listing of every expanded object is captured for function signatures. Arrays are sampled and written as `[]`. Cycles are cut by object identity, a repeated-name guard and depth/node limits. Options: start path, gameplay/visual space, depth, node limit, compact one-line form.
- `lua/wsdump.lua` and `lua/wsdump-oneline.lua`: pre-generated scripts.
- `import_api_dump`: parses dumps from `gen/log.txt`, `log_prev.txt` or a file. It tolerates timestamps, CRLF, foreign lines, malformed records, reruns with the same id and dumps without END (with `allow_partial`). It builds the live index in the user data folder (`WS_MCP_DATA_DIR`) and records the engine version from the log. It reports added, removed, changed and not-covered paths against the bundled WSUS 258 index, plus unexplored subtrees. Subtree dumps are merged. A new engine version replaces the index and keeps a backup. `dry_run` is supported.
- `api_index_status`: active index, engine version, staleness against `engine-version.txt`.
- `lint_mod` rule `absent-in-engine`: a WSUS 258 function that the live dump confirmed missing.
- CLI: `--dump-script [--compact] [--dump-root PATH] [--space visual]`, `--import-dump [FILE]`.
- `docs/api-dump.md`: procedure, record format, verified facts and assumptions with sources.
- Tests: dump parser and importer on fixture logs (malformed lines, truncated dump, cycles, reruns, merge, engine change). The script runs against a Lua 5.4 engine mock; CI installs `lua5.4`.

### Changed

- `search_api`, `lint_mod`, `find_examples` and `game_info` use the live index first; bundled entries remain as fallback where the dump did not cover a path. `search_api` results include the active `index`.
- `game_info` reports `api_index` status instead of a fixed index label.

## 0.2.0 - 2026-10-18

### Added

- `lint_mod`: Lua 5.4 syntax check with luac-style messages and War Selection rules: `math.random` in gameplay mods, missing `root.f_recreateModifiedUnitTypes()`, `math.atan2`, removed `createUnits`, renamed `addBuff`, `f_create` at top level, unknown `addMod` events, undefined handlers, gameplay writes from visual mods, unknown `f_*` names and root fields with suggestions. Mod kind is taken from `gen/log.txt` when available.
- `diff_mod`: unified diff between cached mod versions.
- `log_errors`: parser for `Lua program ... run (Error) failed` blocks; groups repeats and maps errors to cached mods and source lines.
- `find_examples`: API usages across cached mods, including local aliases and underscore paths.
- `list_events_usage`: `addMod` events per mod with totals.
- `scaffold_mod`: templates `blank_gameplay`, `blank_visual`, `zone_trigger`, `unit_death`, `special_command_pair`, `unit_stat_tweak`; code only, with source comments.
- `unit_lookup`: unit types from `legacyIds.json` with build rules from `gameplay.json`.
- CLI: `--version`, `--list-clients`, `--print-config <client>`.
- `docs/clients.md`: configuration for common MCP clients.

### Changed

- All new tools are read-only (`readOnlyHint`); `write_draft` remains the only write tool.

## 0.1.0 - 2026-10-18

### Added

- Initial release: `game_info`, `list_mods`, `get_mod`, `search_mod_code`, `game_data_query`, `search_api`, `search_guide`, `read_log`, `write_draft`.
- Bundled Lua API index (WSUS 258.4018) and Russian modding guide.
