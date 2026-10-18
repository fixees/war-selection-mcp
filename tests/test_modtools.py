import pytest

from ws_mcp import core, modtools


def test_diff_mod(devgame):
    d = modtools.diff_mod(devgame, "CCCCCCCCCC3")
    assert d["from_version"] == 1 and d["to_version"] == 2 and d["versions"] == [1, 2]
    assert "+  zones.f_addCircle(1, 2, 3)" in d["diff"] and d["added"] >= 2
    assert modtools.diff_mod(devgame, "CCCCCCCCCC3", 2, 2)["identical"] is True
    with pytest.raises(core.ToolError, match="Only one"):
        modtools.diff_mod(devgame, "BBBBBBBBBB2")


def test_log_errors(devgame):
    r = modtools.log_errors(devgame)
    assert r["found"] and r["errors_total"] == 3 and len(r["groups"]) == 2
    g = next(x for x in r["groups"] if x["chunk_preview"])
    assert g["count"] == 2 and g["chunk_line"] == 3 and g["script_kind"] == "gameplay"
    assert "f_addCircle" in g["message"]
    assert g["candidates"][0]["mod"] == "mod-CCCCCCCCCC3" and g["candidates"][0]["version"] == 2
    assert g["candidates"][0]["active"] and "f_addCircle" in g["candidates"][0]["code"]
    v = next(x for x in r["groups"] if not x["chunk_preview"])
    assert v["script_kind"] == "visual" and v["active_mods"] == ["DDDDDDDDDD4_5"]
    assert v["frames"][1] == {"line": 6, "function": "unknown"}
    assert modtools.log_errors(devgame, since="2026-10-18 05:54:30")["errors_total"] == 1
    assert modtools.log_errors(devgame, tail=6)["errors_total"] == 1
    with pytest.raises(core.ToolError):
        modtools.log_errors(devgame, since="yesterday")


def test_log_errors_missing(game):
    assert modtools.log_errors(game)["found"] is False


def test_find_examples(devgame):
    r = modtools.find_examples(devgame, "landscape.zones.f_addCircle")
    assert r["total_hits"] == 1 and r["exact_path_hits"] == 0
    assert r["examples"][0]["mod"] == "mod-CCCCCCCCCC3" and ">" in r["examples"][0]["context"]
    r2 = modtools.find_examples(devgame, "root.scene.landscape_zones")
    assert r2["exact_path_hits"] == 1
    assert modtools.find_examples(devgame, "f_recreateModifiedUnitTypes")["total_hits"] == 1
    with pytest.raises(core.ToolError):
        modtools.find_examples(devgame, "a;b")


def test_list_events_usage(devgame):
    r = modtools.list_events_usage(devgame)
    assert r["events"]["onStart"] == 2 and r["events"]["onInit"] == 1
    kinds = {m["mod"]: m["kind"] for m in r["mods"]}
    assert kinds["mod-DDDDDDDDDD4"] == "visual" and kinds["mod-CCCCCCCCCC3"] == "gameplay"
    assert [m["mod"] for m in modtools.list_events_usage(devgame, "onTick")["mods"]] == ["mod-CCCCCCCCCC3"]


def test_scaffold(game):
    names = {t["template"] for t in modtools.list_templates()}
    assert {"blank_gameplay", "blank_visual", "zone_trigger", "unit_death", "special_command_pair",
            "unit_stat_tweak"} <= names
    r = modtools.scaffold_mod("unit_stat_tweak", {"unit_type_id": "201", "value": "100000"})
    assert "root.unitType[201].deathability.health = 100000" in r["files"][0]["code"]
    pair = modtools.scaffold_mod("special_command_pair", {"command": "giveGold"})
    assert [f["kind"] for f in pair["files"]] == ["visual", "gameplay"]
    assert all("giveGold" in f["code"] for f in pair["files"])
    with pytest.raises(core.ToolError):
        modtools.scaffold_mod("nope")
    with pytest.raises(core.ToolError):
        modtools.scaffold_mod("unit_stat_tweak", {"value": "1; os.exit()"})
    with pytest.raises(core.ToolError):
        modtools.scaffold_mod("blank_gameplay", {"x": "1"})


def test_unit_lookup(devgame):
    r = modtools.unit_lookup(devgame, "worker")
    assert [m["id"] for m in r["matches"]] == [1, 201]
    d = modtools.unit_lookup(devgame, "7")["matches"][0]
    assert d["path"] == "Test/1/depot" and d["build_rules"][0]["costBuilding_display"][1] == 80.0
    assert d["build_rules"][0]["health"] == 10000
    assert modtools.unit_lookup(devgame, "999")["matches"] == []


def test_unit_lookup_missing(game):
    with pytest.raises(core.ToolError):
        modtools.unit_lookup(game, "worker")
