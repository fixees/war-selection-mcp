"""Optional integration test against a copy of real game files (never committed).
Set WS_SAMPLE_DIR to a folder with modsStorage/ and Cache/Projects/WarSelection/."""

import os
from pathlib import Path

import pytest

from ws_mcp import core
from ws_mcp.config import Config

SAMPLE = os.environ.get("WS_SAMPLE_DIR")


@pytest.mark.skipif(not SAMPLE or not Path(SAMPLE).is_dir(), reason="WS_SAMPLE_DIR not set")
def test_real_sample():
    cfg = Config(game_dir=Path(SAMPLE))
    info = core.game_info(cfg)
    assert info["mods_unique"] > 0
    mods = core.list_mods(cfg)
    assert core.get_mod(cfg, mods[0]["id"], kind=mods[0]["kinds"][0])["code"]
    if (cfg.project_dir / "gameplay.json").is_file():
        assert core.game_data_query(cfg, "gameplay", path="auras")["value"]
