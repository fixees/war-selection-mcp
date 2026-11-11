# Encyclopedia catalog

On disk since **engine 277** (folder timestamp **2026-10-30**), under:

```
Cache/Content/interfaces/WarSelection/encyclopedia/
  catalog.json
  localization/<lang>.loc
  interface.pack
```

## What it contains

`catalog.json` (`catalogVersion` 1) is the authored structure:

- `eras` — Stone … Industrial 2
- `countries` — culture keys (stone, europe, britain, …) with era lists
- `entities` — unit and building asset paths (`WarSelection/1/worker`, …) with `kind`, `nameKey`, `iconAsset`
- `rosters` — per country/era build trees (`buildings` → `products` / upgrades)
- `researches` — numeric ids with `nameKey` / `textKey` / icon (these keys are labels, not a second copy of gameplay research tables)

`localization/*.loc` holds `<*nameKey>Localized text` records.

The runtime `interface.pack` embeds a snapshot of the same catalog in `customData`. It still has **no combat stats or prices**.

## What it does not contain

Health, damage, cost and other balance numbers live in `Cache/Projects/WarSelection/gameplay.json` (and are what `unit_lookup` already reports, with costs ×1000). The in-game encyclopedia UI can show those figures by reading live gameplay data; they are not stored in the catalog.

## MCP

- `encyclopedia_info` — presence, counts, languages.
- `encyclopedia_lookup(query, lang, kind)` — search by path, localized name, research or country.
- `unit_lookup` also matches encyclopedia names and adds `name`, `kind`, `places` (country/era) when the catalog is present.

Patch notes for a later menu update mention an in-menu encyclopedia with stats, prices and a 3D viewer. That UI was not verified here against a newer installed build; the catalog files above were already in the 277 depot.
