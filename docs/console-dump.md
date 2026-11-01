# F8 console dumpToFile

## Confirmed syntax

Developer (Wouw), Discord, **2026-10-18**:

- Console field writes use **`=`**, not a function-call form.
- Example: `session.gameplay.dumpToFile=dump.txt`

## Path rule (verified 2026-11-01, engine 277)

- Argument must be a **filename only** (`dump.txt`). Absolute paths and nested paths print `Invalid file name`.
- The file is written in the **game root** (next to the game executable), e.g. `War Selection\dump.txt`.
- `dump_to_file_plan` defaults to `absolute=false`. Passing `absolute=true` still builds a line, but the live engine rejects it.

## On-disk format (verified 2026-11-01, live private match)

Captured sample: `dump.txt`, ~227 KiB, after F8 `session.gameplay.dumpToFile=dump.txt` during a private developer-mode match on map `182404b1` with draft mod `draft/sFiuIHRk3Qh_1`.

Sections:

1. **Match header** — map code (`182404b1_6`), enabled gameplay mods as `<id>_<ver>` or `draft/<id>_<ver>`, and match parameters (`developer=0`, `res0=100,res1=250,res2=0`, `limit=100`, …).
2. **Tagged key/value block** — keys such as `data` (JSON `players`), `creator`, `devMode` (bool), `clientReports`, `playersLocalId`.
3. **zlib blob** (magic often `x^` / `78 5e`) — expands to ~14 MiB of an **asset path table** (`WarSelection/made/...`, `WarSelection/nature/...`, …) with u16 indices, then further binary. No `root.` / `unitType` / `WSDUMP` API tree.

**Not useful for API indexing.** Keep using `api_dump_script` → `import_api_dump` (WSDUMP in `gen/log.txt`).

## MCP helpers

- `dump_to_file_plan(filename="dump.txt", absolute=false)` — exact console line; search paths prefer the game root.
- `inspect_console_dump(file)` — resolves a bare name under the game root, reports `kind_guess: session_dump` with map/mods/params/tagged/zlib summary. **Does not import** into the API index.
