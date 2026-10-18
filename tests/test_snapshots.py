import json

import pytest

from ws_mcp import core, snapshots
from ws_mcp.core import ToolError


def _bump(cfg, mutate_gp=None, mutate_legacy=None):
    proj = cfg.project_dir
    if mutate_gp:
        gp = json.loads((proj / "gameplay.json").read_text())
        mutate_gp(gp)
        (proj / "gameplay.json").write_text(json.dumps(gp))
    if mutate_legacy:
        lg = json.loads((proj / "legacyIds.json").read_text())
        mutate_legacy(lg)
        (proj / "legacyIds.json").write_text(json.dumps(lg))


def test_first_snapshot_and_skip(devgame):
    r = core.snapshot_game(devgame)
    assert r["taken"] and r["reason"] == "first snapshot"
    root = devgame.data_dir / "snapshots" / r["snapshot"]
    assert (root / "manifest.json").is_file() and (root / "gameplay.json.gz").is_file()
    assert (root / "api.json.gz").is_file()
    assert not any(p.name.startswith(".") for p in (devgame.data_dir / "snapshots").iterdir())
    again = core.snapshot_game(devgame)
    assert again["taken"] is False
    assert core.snapshot_game(devgame, force=True, label="manual")["taken"] is True


def test_single_snapshot_message(devgame):
    d = core.diff_game_versions(devgame)
    assert d["diff"] is None
    assert "next" in d["message"].lower()
    assert core.mod_impact(devgame)["impact"] is None


def test_no_snapshots_without_game(tmp_path, monkeypatch):
    monkeypatch.setenv("WS_GAME_DIR", str(tmp_path / "nope"))
    from ws_mcp.config import Config
    d = core.diff_game_versions(Config.from_env())
    assert d["diff"] is None


def test_status_in_game_info(devgame):
    assert core.game_info(devgame)["snapshots"]["state"] == "none"
    core.snapshot_game(devgame)
    st = core.game_info(devgame)["snapshots"]
    assert st["state"] == "current"
    (devgame.game_dir / "engine-version.txt").write_text("265\n")
    assert core.game_info(devgame)["snapshots"]["state"] == "changed"


def test_diff_after_patch(devgame):
    core.snapshot_game(devgame)

    def gp(g):
        g["build"][1]["health"] = 12000
        g["build"][1]["costBuilding"] = [0, 90000, 0, 0, 0]
        g["build"].append({"available": True, "unit": "Test/5/worker", "health": 500})
        g["auras"][0]["targetsTags"] = 1
        g["version"] = 2

    def lg(x):
        del x["units"]["201"]
        x["units"]["7"] = "Test/1/depot2"
        x["units"]["300"] = "Test/6/new"

    _bump(devgame, gp, lg)
    (devgame.game_dir / "engine-version.txt").write_text("265\n")
    d = core.diff_game_versions(devgame)
    assert d["auto_snapshot"]["taken"] and d["auto_snapshot"]["reason"] == "engine version changed"
    assert d["engine"] == {"from": "264", "to": "265"}
    g = d["gameplay"]
    assert [u["id"] for u in g["units"]["removed"]] == [201]
    assert [u["id"] for u in g["units"]["added"]] == [300]
    assert g["units"]["renamed"][0]["new"] == "Test/1/depot2"
    ops = {(b["build_id"], b["op"]) for b in g["build_rules"]}
    assert (1, "changed") in ops and (2, "added") in ops
    changed = next(b for b in g["build_rules"] if b["build_id"] == 1)
    assert any(c["path"].endswith("health") and c["new"] == 12000 for c in changed["changes"])
    assert g["auras"]
    assert "gameplay.json" in d["files"]["changed"]
    assert (devgame.data_dir / "diffs").is_dir()
    assert len(d["available"]) == 2


def test_mod_impact(devgame):
    mods = devgame.mods_dir
    (mods / "EEEEEEEEEE5_1-abcdefabcdef0123.lua").write_text(
        "local u = root.unitType[201]\n-- root.unitType[201]\nlocal b = gameplay.build[1]\nroot.f_recreateModifiedUnitTypes()\n")
    (mods / "draft").mkdir()
    (mods / "draft" / "EEEEEEEEEE5_2-abcdefabcdef0123.lua").write_text("x = 1\ny = root.unitType[7]\n")
    core.snapshot_game(devgame)
    _bump(devgame, lambda g: g["build"][1].update(health=1),
          lambda x: (x["units"].pop("201"), x["units"].update({"7": "Test/1/other"})))
    core.snapshot_game(devgame)
    r = core.mod_impact(devgame)
    hits = {(h["source"], h["file"], h["line"]) for h in r["hits"]}
    assert ("cache", "EEEEEEEEEE5_1-abcdefabcdef0123.lua", 1) in hits
    assert ("cache", "EEEEEEEEEE5_1-abcdefabcdef0123.lua", 2) not in hits  # comment
    assert ("cache", "EEEEEEEEEE5_1-abcdefabcdef0123.lua", 3) in hits
    assert ("draft", "EEEEEEEEEE5_2-abcdefabcdef0123.lua", 2) in hits
    assert "mod-EEEEEEEEEE5 (draft)" in r["mods_affected"]


def test_api_diff(devgame):
    core.snapshot_game(devgame)
    from ws_mcp import apidump  # noqa: F401
    entries, _ = core.active_index(devgame)
    removed = entries[0]["path"]
    snapshots.snapshot_game(devgame, entries[1:], "test", force=True)
    d = snapshots.diff_versions(devgame)
    assert removed in [x["path"] for x in d["api"]["removed_paths"]]


def test_large_file_hashed_not_stored(devgame, monkeypatch):
    monkeypatch.setattr(snapshots, "MAX_CONTENT_BYTES", 10)
    r = core.snapshot_game(devgame)
    root = devgame.data_dir / "snapshots" / r["snapshot"]
    assert not (root / "gameplay.json.gz").exists()
    man = json.loads((root / "manifest.json").read_text())
    assert "gameplay.json" in man["files"]


def test_refuses_data_dir_in_game(devgame, monkeypatch):
    monkeypatch.setenv("WS_MCP_DATA_DIR", str(devgame.game_dir / "x"))
    from ws_mcp.config import Config
    with pytest.raises(ToolError):
        core.snapshot_game(Config.from_env())
