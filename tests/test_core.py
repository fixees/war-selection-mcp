import os
from pathlib import Path

import pytest

from ws_mcp import core
from ws_mcp.config import Config


def test_game_info(game):
    info = core.game_info(game)
    assert info["engine_version"] == "264"
    assert info["mods_unique"] == 2
    assert info["mods_files_lua"] == 3 and info["mods_files_prm"] == 1
    assert info["draft_dir_exists"] is False
    assert "gameplay.json" in info["project_files"]


def test_default_game_dir(monkeypatch):
    monkeypatch.delenv("WS_GAME_DIR", raising=False)
    assert "War Selection" in str(Config.from_env().game_dir)


def test_list_mods(game):
    mods = core.list_mods(game)
    a = next(m for m in mods if m["id"] == "AAAAAAAAAA1")
    assert a["versions"] == [1, 3] and a["latest"] == 3
    assert a["kinds"] == ["lua", "prm"]
    assert set(a["latest_sizes"]) == {"lua", "prm"}
    assert core.list_mods(game, "bbb")[0]["id"] == "BBBBBBBBBB2"


def test_get_mod_latest_and_version(game):
    m = core.get_mod(game, "mod-AAAAAAAAAA1")
    assert m["version"] == 3 and "hello v3" in m["code"]
    assert core.get_mod(game, "AAAAAAAAAA1", version=1)["code"].startswith("-- v1")
    assert "helper" in core.get_mod(game, "AAAAAAAAAA1", kind="prm")["code"]
    b = core.get_mod(game, "BBBBBBBBBB2")
    assert not b["code"].startswith("\ufeff")


def test_get_mod_errors(game):
    with pytest.raises(core.ToolError):
        core.get_mod(game, "../../etc/passwd")
    with pytest.raises(core.ToolError):
        core.get_mod(game, "ZZZZZZZZZZ9")
    with pytest.raises(core.ToolError):
        core.get_mod(game, "AAAAAAAAAA1", version=2)


def test_search_mod_code(game):
    r = core.search_mod_code(game, r"f_recreateModifiedUnitTypes")
    assert len(r["matches"]) == 1
    hit = r["matches"][0]
    assert hit["line"] == 4 and ">" in hit["context"]
    r_all = core.search_mod_code(game, r"log\(", latest_only=False)
    assert len(r_all["matches"]) == 3
    assert core.search_mod_code(game, "log", limit=1)["truncated"] is True
    with pytest.raises(core.ToolError):
        core.search_mod_code(game, "(")


def test_game_data_query(game):
    r = core.game_data_query(game, "gameplay", path="build[1].costBuilding")
    assert r["value"] == [0, 80000, 0, 0, 0]
    assert core.game_data_query(game, "gameplay.json", path="auras.1.targetsAttack")["value"] == "projectile"
    hits = core.game_data_query(game, "gameplay", key_search="research")["hits"]
    assert {h["path"] for h in hits} == {"auras[0].research", "auras[1].research"}
    assert core.game_data_query(game, "interfaces/commonData.json", path="a.b[2]")["value"] == 3
    with pytest.raises(core.ToolError):
        core.game_data_query(game, "../../secret.json")
    with pytest.raises(core.ToolError):
        core.game_data_query(game, "gameplay", path="nope.x")


def test_search_api():
    r = core.search_api("f_addCircle")
    assert r["results"][0]["name"] == "f_addCircle"
    assert "wsunitstats" in r["results"][0]["source"]
    ev = core.search_api("onUnitInZone", kind="event")
    assert ev["results"] and ev["results"][0]["kind"] == "event"
    assert core.search_api("f_recreateModifiedUnitTypes", kind="note")["results"]


def test_search_guide():
    r = core.search_guide("download_depot")
    assert r["results"] and "download_depot" in r["results"][0]["snippet"]
    assert core.search_guide("аура")["results"]


def test_read_log_missing(game):
    r = core.read_log(game)
    assert r["found"] is False and any("gen" in p for p in r["searched"])


def test_read_log_found(game):
    gen = game.game_dir / "gen"
    gen.mkdir()
    (gen / "log.txt").write_text("\n".join(f"line {i}" for i in range(1, 101)) + "\nERROR boom\n")
    r = core.read_log(game, tail=5)
    assert r["found"] and r["total_lines"] == 101 and r["lines"].endswith("ERROR boom")
    assert core.read_log(game, grep="error")["lines"] == "101: ERROR boom"


def test_read_log_override(game, tmp_path, monkeypatch):
    p = tmp_path / "custom.txt"
    p.write_text("x\n")
    monkeypatch.setenv("WS_LOG_PATH", str(p))
    assert core.read_log(Config.from_env())["path"] == str(p)


DRAFT = "EEEEEEEEEE5_2-abcdefabcdef0123.lua"


def _make_draft(game, name=DRAFT, text="-- draft v2\n"):
    game.draft_dir.mkdir(exist_ok=True)
    (game.draft_dir / name).write_text(text, encoding="utf-8")
    return game.draft_dir / name


def test_write_draft_requires_existing_draft(game):
    with pytest.raises(core.ToolError, match="edit script"):
        core.write_draft(game, "AAAAAAAAAA1", "print(1)")
    assert not game.draft_dir.exists()
    game.draft_dir.mkdir()
    with pytest.raises(core.ToolError, match="No draft"):
        core.write_draft(game, "AAAAAAAAAA1", "print(1)")
    assert list(game.draft_dir.iterdir()) == []


def test_write_draft_overwrites_latest_draft_with_backup(game):
    _make_draft(game, "EEEEEEEEEE5_1-abcdefabcdef0123.lua", "-- old v1\n")
    target = _make_draft(game)
    r = core.write_draft(game, "mod-EEEEEEEEEE5", "print(1)")
    assert Path(r["written"]) == target.resolve() and r["version"] == 2
    assert target.read_text() == "print(1)"
    backup = Path(r["backup"])
    assert backup.read_text() == "-- draft v2\n" and backup.parent == game.data_dir / "draft-backups"
    assert sorted(p.name for p in game.draft_dir.iterdir()) == ["EEEEEEEEEE5_1-abcdefabcdef0123.lua", DRAFT]
    r1 = core.write_draft(game, "EEEEEEEEEE5", "print(0)", version=1)
    assert (game.draft_dir / "EEEEEEEEEE5_1-abcdefabcdef0123.lua").read_text() == "print(0)" and r1["version"] == 1
    # published files in modsStorage root are never touched
    assert (game.mods_dir / "AAAAAAAAAA1_3-0123456789abcdef.lua").read_text(encoding="utf-8").startswith("-- v3")
    assert "draft" in r["warning"]


@pytest.mark.parametrize("bad", ["../evil", "..\\evil", "a/b", "C:\\x", "", "x" * 65, ".hidden", "a b"])
def test_write_draft_rejects_bad_ids(game, bad):
    _make_draft(game)
    with pytest.raises(core.ToolError):
        core.write_draft(game, bad, "x")
    assert [p.name for p in game.draft_dir.iterdir()] == [DRAFT]


def test_write_draft_bad_extension_and_size(game):
    _make_draft(game)
    with pytest.raises(core.ToolError):
        core.write_draft(game, "EEEEEEEEEE5", "x", extension=".exe")
    with pytest.raises(core.ToolError):
        core.write_draft(game, "EEEEEEEEEE5", "x" * (core.MAX_DRAFT_BYTES + 1))
    with pytest.raises(core.ToolError, match="No prm draft"):
        core.write_draft(game, "EEEEEEEEEE5", "x", extension=".prm")


def test_write_draft_refuses_backup_dir_in_game_folder(game, monkeypatch):
    _make_draft(game)
    monkeypatch.setenv("WS_MCP_DATA_DIR", str(game.game_dir / "gen" / "x"))
    with pytest.raises(core.ToolError, match="inside the game folder"):
        core.write_draft(Config.from_env(), "EEEEEEEEEE5", "x")
    assert (game.draft_dir / DRAFT).read_text() == "-- draft v2\n"


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs privileges on Windows")
def test_write_draft_symlink_target(game, tmp_path):
    game.draft_dir.mkdir()
    outside = tmp_path / "outside.lua"
    outside.write_text("keep")
    (game.draft_dir / DRAFT).symlink_to(outside)
    with pytest.raises(core.ToolError):
        core.write_draft(game, "EEEEEEEEEE5", "pwn")
    assert outside.read_text() == "keep"


def test_drafts_in_list_get_search(game):
    _make_draft(game, "AAAAAAAAAA1_4-0123456789abcdef.lua", "-- draft of A\nfunction onStart() end\n")
    _make_draft(game)
    mods = {m["id"]: m for m in core.list_mods(game)}
    assert mods["AAAAAAAAAA1"]["latest"] == 3 and mods["AAAAAAAAAA1"]["draft"]["latest"] == 4
    assert mods["EEEEEEEEEE5"]["versions"] == [] and mods["EEEEEEEEEE5"]["draft"]["latest"] == 2
    assert mods["BBBBBBBBBB2"]["draft"] is None
    g = core.get_mod(game, "AAAAAAAAAA1")
    assert g["source"] == "draft" and g["version"] == 4 and g["code"].startswith("-- draft of A")
    c = core.get_mod(game, "AAAAAAAAAA1", source="cache")
    assert c["source"] == "cache" and c["version"] == 3
    assert core.get_mod(game, "AAAAAAAAAA1", version=3)["source"] == "cache"
    with pytest.raises(core.ToolError, match="draft folder"):
        core.get_mod(game, "BBBBBBBBBB2", source="draft")
    hits = core.search_mod_code(game, "draft of A")["matches"]
    assert hits and hits[0]["source"] == "draft"
    assert not core.search_mod_code(game, "draft of A", include_drafts=False)["matches"]
    assert core.game_info(game)["drafts"] == ["AAAAAAAAAA1_4", "EEEEEEEEEE5_2"]


def test_read_log_other_names(game):
    (game.game_dir / "gen").mkdir()
    (game.game_dir / "gen" / "lagDiagnostics.log").write_text("lag 1\n")
    assert core.read_log(game, which="lagDiagnostics.log")["found"]
    for bad in ("../x.txt", "gen/log.txt", "a.exe", "..\\x.log"):
        with pytest.raises(core.ToolError):
            core.read_log(game, which=bad)
