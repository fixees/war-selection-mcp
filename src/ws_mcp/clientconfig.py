"""Client configuration snippets for `war-selection-mcp --print-config <client>`."""

from __future__ import annotations

import json
import os
import sys

from .config import DEFAULT_GAME_DIR

SERVER_NAME = "war-selection"

CLIENTS = {
    "generic": "Any stdio MCP client (mcpServers JSON)",
    "claude-desktop": "Claude Desktop: claude_desktop_config.json",
    "claude-code": "Claude Code CLI: claude mcp add",
    "cursor": "Cursor: ~/.cursor/mcp.json or .cursor/mcp.json",
    "windsurf": "Windsurf (Cascade): mcp_config.json",
    "vscode": "VS Code: .vscode/mcp.json (servers)",
    "cline": "Cline: cline_mcp_settings.json",
    "continue": "Continue: .continue/mcpServers/war-selection.yaml",
    "zed": "Zed: settings.json (context_servers)",
    "jetbrains": "JetBrains AI Assistant: Settings | Tools | AI Assistant | MCP",
    "lmstudio": "LM Studio: mcp.json",
    "codex": "Codex CLI: ~/.codex/config.toml or codex mcp add",
    "gemini": "Gemini CLI: ~/.gemini/settings.json or gemini mcp add",
}


def _launch() -> tuple[str, list[str], dict[str, str]]:
    env = {"WS_GAME_DIR": os.environ.get("WS_GAME_DIR") or DEFAULT_GAME_DIR}
    if os.environ.get("WS_LOG_PATH"):
        env["WS_LOG_PATH"] = os.environ["WS_LOG_PATH"]
    return sys.executable, ["-m", "ws_mcp"], env


def _toml_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def render(client: str) -> str:
    if client not in CLIENTS:
        raise ValueError(f"unknown client {client!r}; choose from: {', '.join(CLIENTS)}")
    cmd, args, env = _launch()
    entry = {"command": cmd, "args": args, "env": env}
    if client in ("generic", "claude-desktop", "cursor", "windsurf", "jetbrains", "lmstudio", "gemini"):
        return json.dumps({"mcpServers": {SERVER_NAME: entry}}, indent=2, ensure_ascii=False)
    if client == "cline":
        return json.dumps({"mcpServers": {SERVER_NAME: {**entry, "disabled": False, "autoApprove": []}}},
                          indent=2, ensure_ascii=False)
    if client == "vscode":
        return json.dumps({"servers": {SERVER_NAME: {"type": "stdio", **entry}}}, indent=2, ensure_ascii=False)
    if client == "zed":
        return json.dumps({"context_servers": {SERVER_NAME: entry}}, indent=2, ensure_ascii=False)
    if client == "claude-code":
        envs = " ".join(f'--env {k}="{v}"' for k, v in env.items())
        return f'claude mcp add --transport stdio --scope user {envs} {SERVER_NAME} -- "{cmd}" {" ".join(args)}'
    if client == "codex":
        lines = [f"[mcp_servers.{SERVER_NAME}]", f"command = {_toml_str(cmd)}",
                 f"args = [{', '.join(_toml_str(a) for a in args)}]", "",
                 f"[mcp_servers.{SERVER_NAME}.env]"]
        lines += [f"{k} = {_toml_str(v)}" for k, v in env.items()]
        return "\n".join(lines)
    if client == "continue":
        lines = ["name: War Selection MCP", "version: 0.0.1", "schema: v1", "mcpServers:",
                 f"  - name: {SERVER_NAME}", "    type: stdio", f"    command: {_toml_str(cmd)}", "    args:"]
        lines += [f"      - {_toml_str(a)}" for a in args]
        lines += ["    env:"] + [f"      {k}: {_toml_str(v)}" for k, v in env.items()]
        return "\n".join(lines)
    raise AssertionError(client)
