# gen/modsWorkspace

Verified **2026-11-01**, engine **277**, after a private developer-mode match on map `182404b1` with owned draft `sFiuIHRk3Qh`.

## Layout

```
gen/modsWorkspace/
  <workspaceId>.json              # main document
  <workspaceId>.json.operations   # JSON array of source-fetch operations
  <workspaceId>.json.sources/     # per-mod Lua copies + revision file
    revision                      # integer workspace revision (text)
    <modCode>.lua                 # id-only filename (no _ver-hash)
```

Example id: `4710500292348902884`.

## Main JSON

Top-level keys: `attachments`, `behaviors`, `identity`, `initialized`, `mods`, `revision`, `testedRevision`, `version`.

| Field | Role |
| --- | --- |
| `identity` | `accountId:WarSelection:<mapHex>` (e.g. `1299314:WarSelection:182404b1`) |
| `revision` / `testedRevision` | Workspace revision counters |
| `attachments[]` | Enabled mods: `{code, file, parameters, type}` where `file` is `<code>_<ver>` and `type` is `gameplay` or `visual` |
| `mods[]` | Rich mod records: metadata, `owned`, `hasSource`, `latestVersion`, inlined Lua `source`, units/parameters |
| `behaviors` | Map behaviour blob (`initialPhase`, `victoryRules`, `items`, …) |

Owned draft example (`sFiuIHRk3Qh`): `hasSource=true`, `source=""`, `owned=true`, `sourceRevision` / `uploadedRevision` match workspace revision; attachment `file` may show `sFiuIHRk3Qh_0` while the on-disk draft is `_1`.

## `.sources`

- One `<code>.lua` per attached mod (no version/hash in the name).
- For published cache mods, bytes match `modsStorage/<code>_<ver>-<hash>.lua`.
- For a new empty draft, the sources copy is also empty (0 bytes), same as `modsStorage/draft/...lua`.

## `.operations`

JSON array of jobs, typically `kind: "source"`, with `phase`/`status`, `workspaceRevision`, `privateDraft`, `scriptErrors`, `identity`, `operationId`. Used by the engine while preparing the workspace; completed entries stay on disk.

## Relation to drafts / write_draft

The game still loads draft scripts from **`modsStorage/draft/<id>_<ver>-<hash>.lua`** (log: `FileLoader::load empty file: modsStorage/draft/sFiuIHRk3Qh_1-02dd496c5ce1c9cf.lua`; active list: `draft/sFiuIHRk3Qh_1`).

`modsWorkspace` is a **parallel mirror** for the map session, not a new write target. `write_draft` continues to overwrite the existing `modsStorage/draft/...` file only.

## MCP helpers

- `list_mods_workspace` — list workspace files and sidecar summary.
- `get_mods_workspace` — read one workspace (optional `mod_id`, `include_source`, `include_operations`).
