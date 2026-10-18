"""Synthetic fake game folder. All content here is invented for tests — no real game files."""

import json
from pathlib import Path

import pytest

from ws_mcp.config import Config


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
