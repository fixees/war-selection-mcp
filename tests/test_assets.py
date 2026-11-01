
import json
import struct
import zlib
from pathlib import Path

from ws_mcp import assets, console, core


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
    plan = core.dump_to_file_plan(game, "dump.txt", absolute=True)
    assert plan["console_line"].startswith("session.gameplay.dumpToFile=")
    assert plan["assignment"] == "="
    assert plan["format"] == "unknown"
    assert "2026-10-18" in plan["confirmed_by"]
    missing = core.inspect_console_dump(game, "no-such-dump.txt")
    assert missing["found"] is False
    target = Path(plan["recommended_path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('{"hello":1}\n')
    got = core.inspect_console_dump(game, str(target))
    assert got["found"] and got["kind_guess"] == "maybe_json" and got["format"] == "unknown"
