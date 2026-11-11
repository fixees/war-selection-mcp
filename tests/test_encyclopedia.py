
import json
from pathlib import Path

from ws_mcp import core, encyclopedia, steaminstall, modtools


def _write_encyclopedia(game, lang="en"):
    d = game.game_dir / "Cache" / "Content" / "interfaces" / "WarSelection" / "encyclopedia"
    (d / "localization").mkdir(parents=True)
    catalog = {
        "catalogVersion": 1,
        "eras": [{"id": 0, "key": "stone", "nameKey": "encEra0"}],
        "countries": [{"key": "stone", "eras": [0], "nameKey": "encCountryStone"}],
        "entities": {
            "Test/1/depot": {
                "key": "Test/1/depot", "nameKey": "encEntityDepot",
                "iconAsset": "units/Test/1/depot#icon.ktx2", "kind": "building",
            },
            "Test/1/worker": {
                "key": "Test/1/worker", "nameKey": "encEntityWorker",
                "iconAsset": "units/Test/1/worker#icon.ktx2", "kind": "unit",
            },
        },
        "rosters": [{
            "countryKey": "stone", "eraId": 0,
            "buildings": [{
                "entityKey": "Test/1/depot",
                "products": [{"entityKey": "Test/1/worker"}],
            }],
        }],
        "researches": {
            "0": {"id": 0, "nameKey": "encResearch0", "textKey": "encResearch0Text",
                  "iconAsset": "icons/upgrade0.png"},
        },
    }
    (d / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    (d / "localization" / f"{lang}.loc").write_text(
        "<*encEra0>Stone Age\n"
        "<*encCountryStone>Stone People\n"
        "<*encEntityDepot>Storehouse\n"
        "<*encEntityWorker>Villager\n"
        "<*encResearch0>Agriculture\n"
        "<*encResearch0Text>Grows food.\n",
        encoding="utf-8",
    )
    return d


def test_encyclopedia_absent(game):
    info = core.encyclopedia_info(game)
    assert info["present"] is False
    r = core.encyclopedia_lookup(game, "worker")
    assert r["found"] is False
    assert core.game_info(game)["encyclopedia"]["present"] is False


def test_encyclopedia_lookup_and_unit_enrich(devgame):
    _write_encyclopedia(devgame)
    info = core.encyclopedia_info(devgame)
    assert info["present"] and info["entities"] == 2 and info["kinds"]["unit"] == 1
    r = core.encyclopedia_lookup(devgame, "Villager")
    assert r["found"] and r["total"] >= 1
    assert r["matches"][0]["key"] == "Test/1/worker" and r["matches"][0]["name"] == "Villager"
    rs = core.encyclopedia_lookup(devgame, "Agriculture", kind="research")
    assert rs["matches"][0]["type"] == "research" and rs["matches"][0]["name"] == "Agriculture"
    # unit_lookup: path still works; encyclopedia name also matches; fields enriched
    by_path = modtools.unit_lookup(devgame, "worker")
    # still includes legacy path matches
    assert any(m["path"].endswith("worker") or "worker" in m["path"] for m in by_path["matches"])
    by_name = modtools.unit_lookup(devgame, "Storehouse")
    assert by_name["matches"] and by_name["matches"][0]["path"] == "Test/1/depot"
    assert by_name["matches"][0]["name"] == "Storehouse"
    assert by_name["matches"][0]["kind"] == "building"
    assert by_name["matches"][0]["places"][0]["country"] == "stone"


def test_steam_install_info(tmp_path, monkeypatch):
    lib = tmp_path / "library" / "steamapps"
    g = lib / "common" / "War Selection"
    g.mkdir(parents=True)
    (g / "engine-version.txt").write_text("277\n")
    (lib / "appmanifest_1022450.acf").write_text(
        """
        "AppState"
        {
            "appid"        "1022450"
            "name"        "War Selection"
            "installdir"        "War Selection"
            "LastUpdated"        "1793356626"
            "LastPlayed"        "1793554995"
            "buildid"        "26319903"
            "TargetBuildID"        "26589813"
            "BytesToDownload"        "338884192"
            "BytesDownloaded"        "0"
            "ScheduledAutoUpdate"        "1794432412"
            "StateFlags"        "6"
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setenv("WS_GAME_DIR", str(g))
    monkeypatch.setenv("WS_MCP_DATA_DIR", str(tmp_path / "data"))
    from ws_mcp.config import Config
    cfg = Config.from_env()
    info = steaminstall.steam_install_info(cfg)
    assert info["found"] and info["pending_update"] is True
    assert info["buildid"] == "26319903" and info["target_buildid"] == "26589813"
    assert info["bytes_to_download"] == 338884192
    assert info["last_updated"]  # parsed
