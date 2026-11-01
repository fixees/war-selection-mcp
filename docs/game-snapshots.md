# Game snapshots and patch diffs

## What is stored

`<WS_MCP_DATA_DIR>/snapshots/<engine>-<YYYYmmdd-HHMMSS>-<hash8>[-label]/`:

| File | Content |
|---|---|
| `manifest.json` | engine version (`engine-version.txt`), game version from the log (or null if stale), sha256 of every `*.json` under `Cache/Projects/WarSelection` and of `engine-version.txt`, `content_hash`, `data_hash` (JSON only, without engine-version.txt), API index label/hash, `engine_only_change`, warnings |
| `*.json.gz` | normalized gameplay, visual, legacyIds, main, render, preload |
| `api.json.gz` | active API index |

## Stale game_version

`Game Version:` is read from `gen/log.txt`. Steam can update `engine-version.txt` and Cache JSON while the log still belongs to the previous session. If the log's mtime is older than `engine-version.txt`, the snapshot stores `game_version: null`, `game_version_stale: true`, and keeps the old value in `game_version_raw`. Launch the game once to refresh the log.

## Engine-only change

If `engine-version.txt` changes but every project JSON hash is unchanged vs the previous snapshot, the new snapshot sets `engine_only_change: true` and a warning: launch the game so it rebuilds Cache data, then snapshot again. Seen when an update bumps the engine file before the first run; on the 277 install the JSON files had already been rewritten on 2026-10-30, so the 264→277 diff is real data.

## Diff / mod_impact

See README. `diff_game_versions` compares two snapshots. `mod_impact` scans mods for removed/renamed unit ids and paths, build/research/upgrade indexes, and API changes.

Fixed-point note (verified against 277 patch notes): speeds in `scenes.unitOverrides.*.movement.speed_` are display_speed×16; damage values use ×1000; Improved harness `parameters add=` uses ×16 (160→144 = 10→9).
