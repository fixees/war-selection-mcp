
import json
import time
from pathlib import Path

from ws_mcp import core, snapshots


def test_stale_game_version_when_log_older(devgame):
    ev = devgame.game_dir / "engine-version.txt"
    log = devgame.game_dir / "gen" / "log.txt"
    # make engine newer than log
    older = time.time() - 86400
    newer = time.time()
    # rewrite log with Game Version header and old mtime
    text = log.read_text(encoding="utf-8")
    if "Game Version:" not in text:
        text = "2026-10-18 05:53:01 Game Version: 264.4021.oldhash_1\n" + text
        log.write_text(text)
    import os
    os.utime(log, (older, older))
    os.utime(ev, (newer, newer))
    st = snapshots.current_state(devgame)
    assert st["game_version"] is None and st["game_version_stale"] is True
    assert "264" in (st.get("game_version_raw") or "")
    r = core.snapshot_game(devgame)
    assert r["taken"] and r["game_version_stale"] is True
    man = json.loads((Path(r["dir"]) / "manifest.json").read_text())
    assert man["game_version"] is None and man["game_version_stale"] is True
    assert man.get("warning")


def test_engine_only_change_flag(devgame):
    r1 = core.snapshot_game(devgame)
    assert r1["taken"]
    # bump engine only; leave gameplay JSON as-is
    (devgame.game_dir / "engine-version.txt").write_text("999\n")
    # clear hash cache by touching nothing else
    snapshots._hash_cache.clear()
    r2 = core.snapshot_game(devgame)
    assert r2["taken"] and r2["engine_only_change"] is True
    assert "unchanged" in r2["reason"]
    man = json.loads((Path(r2["dir"]) / "manifest.json").read_text())
    assert man["engine_only_change"] is True and man["warning"]
