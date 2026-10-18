# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

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
