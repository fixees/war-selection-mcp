"""Synthetic fake game folder. All content here is invented for tests — no real game files."""

import json
from pathlib import Path

import pytest

from ws_mcp.config import Config


@pytest.fixture(autouse=True)
def _isolated_data_dir(tmp_path, monkeypatch):
    """Keep the live API index of the developer machine out of the tests."""
    monkeypatch.setenv("WS_MCP_DATA_DIR", str(tmp_path / "ws-mcp-data"))


@pytest.fixture()
def game(tmp_path, monkeypatch) -> Config:
    g = tmp_path / "War Selection"
    mods = g / "modsStorage"
    proj = g / "Cache" / "Projects" / "WarSelection"
    (proj / "interfaces").mkdir(parents=True)
    mods.mkdir(parents=True)
    (g / "engine-version.txt").write_text("264\n")
    files = {
        "AAAAAAAAAA1_1-0123456789abcdef.lua": "-- v1\nfunction onStart(var)\n  log('hello')\nend\naddMod({ onStart = onStart })\n",
        "AAAAAAAAAA1_3-0123456789abcdef.lua": "-- v3\nfunction onStart(var)\n  log('hello v3')\n  root.f_recreateModifiedUnitTypes()\nend\naddMod({ onStart = onStart })\n",
        "AAAAAAAAAA1_3-0123456789abcdef.prm": "function helper()\n  return 1\nend\n",
        "BBBBBBBBBB2_7-fedcba9876543210.lua": "\ufefflocal x = root.f_random(10)\r\nlog(x)\r\n",
        "not-a-mod.txt": "ignore me",
    }
    for name, text in files.items():
        (mods / name).write_text(text, encoding="utf-8", newline="")
    (proj / "gameplay.json").write_text(json.dumps({
        "auras": [{"research": 148, "targetsTags": 8589934592}, {"research": 149, "targetsAttack": "projectile"}],
        "build": [None, {"available": True, "costBuilding": [0, 80000, 0, 0, 0], "unit": "Test/1/depot"}],
        "version": 1,
    }))
    (proj / "main.json").write_text(json.dumps({"ui": {"styles": "x"}, "version": 2}))
    (proj / "interfaces" / "commonData.json").write_text(json.dumps({"a": {"b": [1, 2, 3]}}))
    (proj / "unitTypeEmbeddings.bin").write_bytes(b"\0\1")
    for var in ("WS_LOG_PATH", "LOCALAPPDATA"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "profile"))
    monkeypatch.setenv("WS_GAME_DIR", str(g))
    return Config.from_env()


# Log excerpt in the format the engine writes (structure from public bug reports; content invented).
LOG_SAMPLE = """Log cleared in thread 1
2026-10-18 05:53:12 Using gameplay modifications: CCCCCCCCCC3_2, AAAAAAAAAA1_3
2026-10-18 05:53:19 Using visual modifications: DDDDDDDDDD4_5
2026-10-18 05:54:00 Lua program scripts/WarSelection/compiled/gameplay/initOnStart.lua run (Error) failed:
    Error occured at:
    Line:3 function:[onStart]
[string "function onStart(var)..."]:3: attempt to call a nil value (field 'f_addCircle')
2026-10-18 05:54:01 Lua program scripts/WarSelection/compiled/gameplay/initOnStart.lua run (Error) failed:
    Error occured at:
    Line:3 function:[onStart]
[string "function onStart(var)..."]:3: attempt to call a nil value (field 'f_addCircle')
2026-10-18 05:55:00 Lua program scripts/WarSelection/compiled/visual/onScriptCommand.lua run (Error) failed:
    Error occured at:
    Line:-1 function:[f_liveConstructed]
    Line:6 function:[unknown]
Value is read only: "Read only"
2026-10-18 05:56:00 Session end
"""


@pytest.fixture()
def devgame(game) -> Config:
    """`game` plus mods with several versions, legacyIds.json and a log with Lua errors."""
    mods = game.mods_dir
    files = {
        "CCCCCCCCCC3_1-1111111111111111.lua": "function onStart(var)\n  log('a')\nend\naddMod({ onStart = onStart })\n",
        "CCCCCCCCCC3_2-1111111111111111.lua": ("function onStart(var)\n  local zones = root.scene[0].landscape_zones\n"
                                               "  zones.f_addCircle(1, 2, 3)\nend\naddMod({ onStart = onStart, onTick = ontick })\n"),
        "DDDDDDDDDD4_5-2222222222222222.lua": ("local vSession = root.session_visual\nfunction onInit()\n"
                                               "  vSession.commands.f_specialCommand(0, 'command', 'x')\nend\naddMod({ onInit = onInit })\n"),
    }
    for name, text in files.items():
        (mods / name).write_text(text, encoding="utf-8", newline="")
    proj = game.project_dir
    (proj / "legacyIds.json").write_text(json.dumps({"units": {"1": "Test/1/worker", "201": "Test/5/worker", "7": "Test/1/depot"}}))
    gp = json.loads((proj / "gameplay.json").read_text())
    gp["build"][1].update({"costInit": [0, 20000, 0, 0, 0], "health": 10000})
    (proj / "gameplay.json").write_text(json.dumps(gp))
    gen = game.game_dir / "gen"
    gen.mkdir()
    (gen / "log.txt").write_text(LOG_SAMPLE, encoding="utf-8")
    return game
