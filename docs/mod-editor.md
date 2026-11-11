# Developer-mode "Edit script" (modificationsEdit)

## `fromBase62` overflow (verified 2026-11-01, engine 277)

Opening a owned draft with **Edit script** can fail with:

```
Lua program Content/interfaces/common/modificationsEdit/scripts/20(releaseInner).lua run (Error) failed:
.../20(releaseInner).lua:8: Unsigned editor integer does not fit Lua signed 64-bit integer
Rethrow ... Address: fromBase62
  function:[f_fromBase62]
```

The on-disk UI script (inside `Cache/Content/interfaces/common/modificationsEdit/interface.pack`, GEMPACK format, pack dated 2026-10-30) is:

```lua
local hex = root.functions_transcoding.f_toHex(root.functions_transcoding.f_fromBase62(code))
```

`code` is the 11-character mod id parsed from the draft file name. Eleven base-62 digits can exceed a signed 64-bit integer (`62^11 > 2^63`), so `f_fromBase62` raises on some ids. The script then cannot compute `modsStorage/draft/<id>_<ver>-<hex>.lua`.

This was logged six times on **2026-11-01** (engine 277 session). `log_prev.txt` (2026-10-18) has no such line.

Whether a later game patch changes this script can only be checked after that patch is **installed** and the game has been launched (or by comparing the packed `20(releaseInner).lua`).
