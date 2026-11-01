# Asset Editor and asset packs

## AssetEditor folder

Shipped in the Steam install under `<game>/AssetEditor/` (patch notes, modding section, 2026-10-30).

Verified on engine 277:

| Path | Role |
|---|---|
| `AssetEditor.exe` | Editor (≈39 MB) |
| `AssetEditorPreview.dll` | Preview renderer |
| `version` | Build stamp `20261030-084719-bdd6` |
| `engine-version.txt` | `277` (same as the game) |
| `sources.txt` | Git commits of extlibs/libs/render/sound/ann/client (client commit differs from the game's `sources.txt`) |
| `Shaders/Gl/Desktop3/*.jsh` | 83 JSON+GLSL shader packs |

Strings inside `AssetEditor.exe` (read-only): opens **Library, model.json, .pack or asset.geasset**; previews models, materials, animations, effects, terrain, water, grass, cubemaps, decals, billboards, lenses; script members must be `scripts/<name>.lua` inside an asset. It is an authoring tool for visual assets, not a replacement for Lua gameplay mods.

## Asset packs on disk

New with the same update:

- `modsStorage/manifests/<code>_<ver>-<hash16>.json` — format 1, fields `code`, `version`, `files` (path → sha256+size), `requires` (other `code_ver`).
- `modsStorage/blobs/<sha256>.pack` — content addressed by the manifest hashes.

`legacyIds.json` unit paths for Horde content moved from `WarSelection/horde/...` to `asset-<code>_<ver>/horde/...`, matching manifest codes. Tools: `asset_editor_info`, `list_asset_manifests`.

## Map drafts

`loadings/maps/draft/<hex>_<ver>.gemg` + `.gemv`.

Verified: both are zlib-compressed **GEM1** archives (version byte 5). `.gemg` entries observed: `map.lnd` (JSON land size/passability), `map.trh` (binary terrain), `map.env`, `map.dat` (JSON factions), `map.cfg` (JSON `modsG` / `modsV`). `.gemv` is the visual twin; full schema beyond GEM1 is not documented. Tool: `list_map_drafts`. Live map `182404b1` drafts `_5` / `_6` observed 2026-11-01 (engine 277).
