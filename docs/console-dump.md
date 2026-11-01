# F8 console dumpToFile

## Confirmed syntax

Developer (Wouw), Discord, **2026-10-18**:

- Console field writes use **`=`**, not a function-call form.
- Example: `session.gameplay.dumpToFile=dump.txt`

## MCP helpers

- `dump_to_file_plan(filename, absolute=true)` — exact console line. With `absolute=true` (default) the path is under `WS_MCP_DATA_DIR` so the file is easy to find and outside the game folder.
- `inspect_console_dump(file)` — reads the produced file, reports size and a coarse kind guess (`maybe_json`, `wsdump_log`, `gzip`, `gem1`, or `unknown`). **Does not import** into the API index.

## Format

**Unknown.** The binary contains a truncated `dumpToFi*` symbol and a `dumpFileName` parameter name; no on-disk schema is published. Until a real file is captured:

1. Launch the game once (also refreshes `gen/log.txt` and Cache project data).
2. F8 → run the `console_line` from `dump_to_file_plan`.
3. `inspect_console_dump` on the path.
4. Only if the kind is clearly the existing `WSDUMP` log format, use `import_api_dump`; otherwise keep the sample for a later parser.

Relative names like `dump.txt` may land in the process working directory (usually the game folder) or `gen/`; prefer an absolute path under the data dir.
