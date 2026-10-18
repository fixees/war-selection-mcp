import json
import subprocess
import sys

import pytest

from ws_mcp import clientconfig


@pytest.mark.parametrize("client", sorted(clientconfig.CLIENTS))
def test_render_all(client, monkeypatch):
    monkeypatch.setenv("WS_GAME_DIR", "/games/War Selection")
    out = clientconfig.render(client)
    assert sys.executable in out and "ws_mcp" in out and "/games/War Selection" in out
    if out.lstrip().startswith("{"):
        data = json.loads(out)
        key = {"vscode": "servers", "zed": "context_servers"}.get(client, "mcpServers")
        entry = data[key]["war-selection"]
        assert entry["command"] == sys.executable and entry["args"] == ["-m", "ws_mcp"]
        assert entry["env"]["WS_GAME_DIR"] == "/games/War Selection"


def test_codex_toml_parses():
    tomllib = pytest.importorskip("tomllib")
    data = tomllib.loads(clientconfig.render("codex"))
    assert data["mcp_servers"]["war-selection"]["args"] == ["-m", "ws_mcp"]


def test_cli_print_config():
    out = subprocess.run([sys.executable, "-m", "ws_mcp", "--print-config", "generic"],
                         capture_output=True, text=True, check=True).stdout
    assert json.loads(out)["mcpServers"]["war-selection"]["command"] == sys.executable
    lst = subprocess.run([sys.executable, "-m", "ws_mcp", "--list-clients"], capture_output=True, text=True, check=True).stdout
    assert "claude-desktop" in lst and "vscode" in lst
    bad = subprocess.run([sys.executable, "-m", "ws_mcp", "--print-config", "nope"], capture_output=True, text=True)
    assert bad.returncode != 0
