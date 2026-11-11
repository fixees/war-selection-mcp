"""Steam appmanifest for the installed War Selection depot (read-only)."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import Config

# Quoted ACF pairs. Enough for top-level AppState fields.
PAIR_RE = re.compile(r'"([^"]+)"\s+"([^"]*)"')


def steamapps_dir(cfg: Config) -> Path | None:
    """.../steamapps next to common/<installdir>, if the game lives in a Steam library."""
    # game: <library>/steamapps/common/War Selection
    common = cfg.game_dir.parent
    if common.name.lower() != "common":
        return None
    steamapps = common.parent
    if steamapps.name.lower() != "steamapps":
        return None
    return steamapps


def find_appmanifest(cfg: Config) -> Path | None:
    d = steamapps_dir(cfg)
    if d is None or not d.is_dir():
        return None
    want = cfg.game_dir.name.casefold()
    for p in sorted(d.glob("appmanifest_*.acf")):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fields = dict(PAIR_RE.findall(text))
        if fields.get("installdir", "").casefold() == want:
            return p
    return None


def _fmt_unix(ts: str | None) -> str | None:
    if not ts:
        return None
    try:
        n = int(ts)
    except ValueError:
        return None
    if n <= 0:
        return None
    return datetime.fromtimestamp(n).strftime("%Y-%m-%d %H:%M:%S")


def steam_install_info(cfg: Config) -> dict[str, Any]:
    manifest = find_appmanifest(cfg)
    if manifest is None:
        return {"found": False, "note": "Game folder is not under a Steam steamapps/common library, "
                                        "or no matching appmanifest_*.acf was found."}
    text = manifest.read_text(encoding="utf-8", errors="replace")
    f = dict(PAIR_RE.findall(text))
    buildid = f.get("buildid")
    target = f.get("TargetBuildID") or f.get("targetbuildid")
    try:
        to_dl = int(f.get("BytesToDownload") or 0)
        got = int(f.get("BytesDownloaded") or 0)
    except ValueError:
        to_dl, got = 0, 0
    pending = bool(target and buildid and target != buildid) or (to_dl > 0 and got < to_dl)
    return {
        "found": True,
        "appid": f.get("appid"),
        "name": f.get("name"),
        "installdir": f.get("installdir"),
        "manifest": str(manifest),
        "buildid": buildid,
        "target_buildid": target,
        "pending_update": pending,
        "bytes_to_download": to_dl,
        "bytes_downloaded": got,
        "last_updated": _fmt_unix(f.get("LastUpdated")),
        "last_played": _fmt_unix(f.get("LastPlayed")),
        "scheduled_auto_update": _fmt_unix(f.get("ScheduledAutoUpdate")),
        "state_flags": f.get("StateFlags"),
        "note": ("pending_update is true when Steam's TargetBuildID differs from the installed "
                 "buildid, or a download is incomplete. Gameplay files are the installed build; "
                 "a pending patch is not visible in Cache until Steam finishes the update."),
    }
