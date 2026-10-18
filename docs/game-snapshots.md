# Game snapshots and patch diffs

## What is stored

`<WS_MCP_DATA_DIR>/snapshots/<engine>-<YYYYmmdd-HHMMSS>-<hash8>[-label]/`:

| File | Content |
|---|---|
| `manifest.json` | engine version (`engine-version.txt`), game version (`Game Version:` line of `gen/log.txt`), sha256 and size of every `*.json` under `Cache/Projects/WarSelection` (recursive) and of `engine-version.txt`, combined content hash, API index label and hash |
| `gameplay.json.gz`, `visual.json.gz`, `legacyIds.json.gz`, `main.json.gz`, `render.json.gz`, `preload.json.gz` | normalized content (sorted keys, compact) |
| `api.json.gz` | active API index: `path -> {kind, type, signature}` (live index from `import_api_dump` merged with the bundled one) |

Files above 64 MB, or that fail to parse, are recorded by hash only and listed under `skipped`. Other JSON files (interfaces, localization, styles) are tracked by hash; a change shows up in `files.changed`.

On the reference install the content files are 1-150 KB (gameplay.json 98 KB, preload.json 152 KB); a snapshot is about 100 KB compressed. A synthetic 7.5 MB gameplay.json with 20000 build rules takes 0.3 s to snapshot and 2 s to diff.

Snapshots are written to a temporary folder and renamed, so an interrupted write leaves no partial snapshot. Nothing is written to the game folder; if `WS_MCP_DATA_DIR` points inside it, the tools refuse.

## When snapshots are taken

- On server start in a background thread, if the content hash or the API index differs from the latest snapshot. Disable with `WS_MCP_AUTO_SNAPSHOT=0`.
- By `diff_game_versions` without arguments, before comparing.
- By `snapshot_game` (`force=true` stores one even if nothing changed; `label` is appended to the id).
- `war-selection-mcp --snapshot` from a terminal.

`game_info` reports `snapshots.state`: `none`, `current`, or `changed` (game files differ from the latest snapshot). It does not write anything.

## Diff

`diff_game_versions(a, b, limit)`: default `a` = previous snapshot, `b` = latest. `a`/`b` accept a snapshot id, an id prefix, or an engine version (the latest snapshot of that version).

With one snapshot it returns `diff: null` and a message: the first snapshot is the baseline and the next game update produces the diff.

Sections:

| Key | Source | Content |
|---|---|---|
| `files` | manifest hashes | added, removed, changed files |
| `gameplay.units` | `legacyIds.json` `units` | unit type ids added, removed, renamed (path changed) |
| `gameplay.build_rules` | `gameplay.json` `build[i]` | per index: unit path, unit type id, op, field changes (`costBuilding`, `health`, ...) |
| `gameplay.researches`, `gameplay.upgrades` | `researches.list[i]`, `researches.upgrades[i]` | per index: op and field changes |
| `gameplay.auras`, `gameplay.unit_overrides` | `auras`, `scenes.unitOverrides` | path-level changes |
| `gameplay.gameplay_scalars`, `gameplay.envs` | top-level scalars, `legacyIds.envs` | changes |
| `other_json` | visual, main, render, preload | path-level changes |
| `api` | `api.json.gz` | counts, added paths, removed paths, changed kind/type/signature |

Lists in the response are cut to `limit`; the full diff is written to `<WS_MCP_DATA_DIR>/diffs/<a>__<b>.json` (`full_diff_file`).

Arrays of up to 64 scalars (cost vectors, tag lists) are compared as a whole; longer arrays and arrays of objects per index. Index-based comparison reports an insertion in the middle of `build` as changes of every following index; the unit path in each entry makes this visible.

## mod_impact

Scans the latest cached version of every mod and every draft (`include_drafts`), skipping comment lines, for:

| Pattern | Matched against |
|---|---|
| `unitType[<id>]` | removed or renamed unit type ids, unit ids of changed build rules |
| `build[<i>]` | changed build rule indexes |
| `researches[<i>]`, `researches.list[<i>]` | changed research indexes |
| `upgrades[<i>]` | changed upgrade indexes |
| `f_<name>` | API functions removed or with a changed signature |
| `<parent>.<field>` | last two segments of removed API fields |

Output: `file:line`, code line, reason, list of affected mods. This is a static text match: ids computed at runtime or passed through variables are not found.

Assumption: `root.unitType[<id>]` is indexed by the keys of `legacyIds.json` `units`. Not verified against the engine; the API dump of `root.unitType` can confirm it.
