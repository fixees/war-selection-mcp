import asyncio
import json
import sys

import pytest

from ws_mcp import server

EXPECTED = {"game_info", "list_mods", "get_mod", "search_mod_code", "game_data_query",
            "search_api", "search_guide", "read_log", "write_draft"}


def test_tools_registered():
    tools = asyncio.run(server.mcp.list_tools())
    names = {t.name for t in tools}
    assert EXPECTED <= names
    wd = next(t for t in tools if t.name == "write_draft")
    assert wd.annotations.readOnlyHint is False
    assert all(t.annotations.readOnlyHint for t in tools if t.name != "write_draft")


def test_tool_call_and_error(game):
    res = asyncio.run(server.mcp.call_tool("list_mods", {}))
    text = json.dumps([c.model_dump() if hasattr(c, "model_dump") else c for c in (res[0] if isinstance(res, tuple) else res)], default=str)
    assert "AAAAAAAAAA1" in text
    err = server.get_mod("../x")
    assert "error" in err


def test_stdio_roundtrip(game):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    import os

    async def run():
        params = StdioServerParameters(command=sys.executable, args=["-m", "ws_mcp"], env=dict(os.environ))
        async with stdio_client(params) as (r, w):
            async with ClientSession(r, w) as s:
                await s.initialize()
                tools = await s.list_tools()
                assert EXPECTED <= {t.name for t in tools.tools}
                out = await s.call_tool("game_info", {})
                return out.content[0].text

    text = asyncio.run(run())
    assert '"engine_version": "264"' in text or '"264"' in text
