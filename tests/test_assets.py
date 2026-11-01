
import json
import struct
import zlib
from pathlib import Path

from ws_mcp import assets, console, core


def _session_dump() -> bytes:
    """Minimal engine-277-shaped session dump for inspect_console_dump tests."""
    import struct, zlib
    def u32(n): return struct.pack("<I", n)
    def u16(n): return struct.pack("<H", n)
    parts = bytearray()
    parts += u32(13) + bytes([1]) + u32(9) + bytes([0])
    mapa = b"182404b1_6"
    parts += u32(len(mapa)) + mapa
    def mod(flags, s):
        b = s.encode(); return u32(flags) + u16(len(b)) + b
    def param(s):
        b = s.encode(); return u32(len(b)) + b
    parts += mod(0, "JnHcuvqS6ga_11")
    parts += param("developer=0")
    parts += mod(0, "draft/sFiuIHRk3Qh_1")
    parts += param("res0=100,res1=250,res2=0")
    parts += b"\x00" * 8
    def kv(k, v):
        kb = k.encode(); vb = v.encode()
        return u32(len(kb)) + kb + bytes([4]) + u32(len(vb)) + vb
    parts += kv("data", '{"players":[{"abilities":"0000000000","name":"Test"}]}')
    parts += kv("creator", "0")
    parts += kv("devMode", "true")
    paths = [
        "WarSelection/made/building/1/decal",
        "WarSelection/made/building/1/temple/base",
        "WarSelection/nature/tree/1",
    ]
    zbody = bytearray()
    zbody += u32(len(paths)) + u32(0)
    p0 = paths[0].encode(); zbody += u32(len(p0)) + p0
    for i, path in enumerate(paths[1:], 1):
        b = path.encode(); zbody += u16(i) + u32(len(b)) + b
    zbody += b"\x00\x01\x02" + b"X" * 100
    parts += zlib.compress(bytes(zbody))
    return bytes(parts)



def _gemg(entries: dict[str, bytes]) -> bytes:
    body = bytearray(b"GEM1\x05")
    for name, data in entries.items():
        nb = name.encode("ascii")
        body.append(len(nb))
        body += nb
        body += struct.pack("<I", len(data))
        body += data
    return zlib.compress(bytes(body))


def test_asset_editor_absent(game):
    r = core.asset_editor_info(game)
    assert r["present"] is False


def test_asset_editor_present(game):
    d = game.game_dir / "AssetEditor"
    d.mkdir()
    (d / "AssetEditor.exe").write_bytes(b"MZ" + b"\0" * 100)
    (d / "version").write_text("20261030-084719-bdd6\n")
    (d / "engine-version.txt").write_text("277\n")
    (d / "sources.txt").write_text("client    master   abc\n")
    (d / "Shaders" / "Gl" / "Desktop3").mkdir(parents=True)
    (d / "Shaders" / "Gl" / "Desktop3" / "LitModel.jsh").write_text("{}")
    r = core.asset_editor_info(game)
    assert r["present"] and r["version"].startswith("20261030") and r["shaders"] == 1
    assert ".geasset" in r["opens"]
    gi = core.game_info(game)
    assert gi["asset_editor"]["present"] and gi["console"]["assignment"] == "="


def test_manifests_and_map_drafts(game):
    man = game.mods_dir / "manifests"
    man.mkdir()
    blobs = game.mods_dir / "blobs"
    blobs.mkdir()
    # noop
    (blobs / ("a" * 64 + ".pack")).write_bytes(b'{"x":1}')
    (man / "258jHrIFJi6_2-901c5121fdd96749.json").write_text(json.dumps({
        "code": "258jHrIFJi6", "version": 2, "format": 1, "requires": ["x"],
        "files": {"units/horde/shards/red.pack": {"sha256": "a" * 64, "size": 1}},
    }))
    r = core.list_asset_manifests(game)
    assert r["found"] and r["manifests"][0]["asset_ref"] == "asset-258jHrIFJi6_2"
    assert r["path_tops"]["units"] == 1

    draft = game.game_dir / "loadings" / "maps" / "draft"
    draft.mkdir(parents=True)
    lnd = json.dumps({"cellsize": 16384, "size": [34, 34], "passability": {"size": [10, 10]}}).encode()
    dat = json.dumps({"factions": [{"name": "A", "color": 1}], "name": "TestMap"}).encode()
    cfg = json.dumps({"modsG": [["AAAAAAAAAA1_3", ""]], "modsV": []}).encode()
    (draft / "182404b1_3.gemg").write_bytes(_gemg({
        "map.lnd": lnd, "map.trh": b"\0\0", "map.env": b"\0" * 12, "map.dat": dat, "map.cfg": cfg,
    }))
    (draft / "182404b1_3.gemv").write_bytes(zlib.compress(b"GEM1\x05"))
    maps = core.list_map_drafts(game)
    assert maps["count"] == 1
    g = maps["maps"][0]["gameplay"]
    assert g["land"]["size"] == [34, 34]
    assert g["mods_gameplay"][0][0] == "AAAAAAAAAA1_3"
    assert core.game_info(game)["map_drafts"]["count"] == 1
    assert core.game_info(game)["asset_manifests"]["count"] == 1


def test_dump_to_file_plan_and_inspect(game, tmp_path):
    plan = core.dump_to_file_plan(game, "dump.txt", absolute=False)
    assert plan["console_line"] == "session.gameplay.dumpToFile=dump.txt"
    assert plan["assignment"] == "="
    assert plan["format"] == "session_dump"
    assert plan["useful_for_api_index"] is False
    assert "2026-10-18" in plan["confirmed_by"]
    assert str(game.game_dir / "dump.txt") in plan["search_paths"]
    abs_plan = core.dump_to_file_plan(game, "dump.txt", absolute=True)
    assert "warning" in abs_plan
    missing = core.inspect_console_dump(game, "no-such-dump.txt")
    assert missing["found"] is False
    # bare name resolves under game root
    dest = game.game_dir / "dump.txt"
    dest.write_bytes(_session_dump())
    got = core.inspect_console_dump(game, "dump.txt")
    assert got["found"] and got["kind_guess"] == "session_dump"
    assert got["useful_for_api_index"] is False
    assert got["session"]["map"] == "182404b1_6"
    assert "draft/sFiuIHRk3Qh_1" in got["session"]["mods"]
    assert got["session"]["zlib"]["ok"] is True
    assert got["session"]["zlib"]["path_count"] >= 1


def test_mods_workspace_list_and_get(game):
    ws = game.game_dir / "gen" / "modsWorkspace"
    ws.mkdir(parents=True)
    main = ws / "4710500292348902884.json"
    data = {
        "attachments": [
            {"code": "sFiuIHRk3Qh", "file": "sFiuIHRk3Qh_0", "parameters": "", "type": "gameplay"},
            {"code": "6gqH17D5rDl", "file": "6gqH17D5rDl_5", "parameters": "", "type": "gameplay"},
        ],
        "behaviors": {"version": 1, "initialPhase": 0, "victoryRules": [], "items": [], "customTemplates": []},
        "identity": "1299314:WarSelection:182404b1",
        "initialized": True,
        "mods": [
            {"code": "sFiuIHRk3Qh", "name": "test-game-modification", "type": "gameplay", "version": 1,
             "latestVersion": 1, "owned": True, "hasSource": True, "source": "", "sourceRevision": 28,
             "uploadedRevision": 28, "units": [], "parameters": {}},
            {"code": "6gqH17D5rDl", "name": "6gqH17D5rDl", "type": "gameplay", "version": 5,
             "latestVersion": 5, "owned": False, "hasSource": True, "source": "log(1)\n",
             "units": [], "parameters": {}},
        ],
        "revision": 28, "testedRevision": 0, "version": 1,
    }
    main.write_text(json.dumps(data), encoding="utf-8")
    (Path(str(main) + ".operations")).write_text(json.dumps([
        {"account": "1299314", "code": "sFiuIHRk3Qh", "kind": "source", "phase": "finished",
         "status": "completed", "workspaceRevision": 28, "privateDraft": True, "scriptErrors": [],
         "identity": "1299314:WarSelection:182404b1", "operationId": "1-2-3"},
    ]), encoding="utf-8")
    src = Path(str(main) + ".sources")
    src.mkdir()
    (src / "revision").write_text("28\n")
    (src / "sFiuIHRk3Qh.lua").write_text("")
    (src / "6gqH17D5rDl.lua").write_text("log(1)\n")

    listed = core.list_mods_workspace(game)
    assert listed["found"] and listed["count"] == 1
    assert listed["workspaces"][0]["identity"].endswith(":182404b1")
    assert listed["workspaces"][0]["revision"] == 28
    assert listed["workspaces"][0]["operations_count"] == 1
    assert "sFiuIHRk3Qh.lua" in listed["workspaces"][0]["sources"]

    one = core.get_mods_workspace(game, mod_id="sFiuIHRk3Qh", include_source=True, include_operations=True)
    assert one["found"] and one["mods"][0]["code"] == "sFiuIHRk3Qh" and one["mods"][0]["owned"] is True
    assert one["mods"][0]["source"] == ""
    assert one["operations_total"] == 1
    assert core.game_info(game)["mods_workspace"]["present"] is True
