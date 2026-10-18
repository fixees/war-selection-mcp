# Client setup / Подключение клиентов

[Русский](#русский) | [English](#english)

## Русский

Сервер работает через stdio. Клиенту нужны три значения:

- команда: путь к `python` из виртуального окружения, где установлен пакет (или к `war-selection-mcp`);
- аргументы: `-m ws_mcp` (для `war-selection-mcp` аргументы не нужны);
- переменная `WS_GAME_DIR`: папка игры; при нестандартном расположении лога также `WS_LOG_PATH`.

Готовый фрагмент с путём к текущему интерпретатору:

```bash
war-selection-mcp --list-clients
war-selection-mcp --print-config vscode
```

В примерах ниже `PYTHON` обозначает полный путь к интерпретатору окружения: `C:\path\to\.venv\Scripts\python.exe` на Windows или `/path/to/.venv/bin/python` на macOS и Linux. В JSON обратные слеши удваиваются.

Форматы проверены по официальной документации клиентов 18.10.2026 (ссылки в разделе каждого клиента). Пометка **не проверено** означает, что в документации нет точного пути к файлу; в этом случае откройте файл через интерфейс клиента.

После обновления пакета перезапустите сервер в клиенте (или сам клиент), чтобы список инструментов обновился.

### Сводка

| Клиент | Файл или команда | Ключ |
|---|---|---|
| Claude Desktop | Windows `%APPDATA%\Claude\claude_desktop_config.json`; macOS `~/Library/Application Support/Claude/claude_desktop_config.json` | `mcpServers` |
| Claude Code | `claude mcp add --transport stdio --scope user --env WS_GAME_DIR=... war-selection -- PYTHON -m ws_mcp` | |
| Cursor | `~/.cursor/mcp.json` или `.cursor/mcp.json` | `mcpServers` |
| Windsurf | `~/.config/devin/mcp_config.json`; Windows `%APPDATA%\devin\mcp_config.json` | `mcpServers` |
| VS Code | `.vscode/mcp.json`; `MCP: Open User Configuration`; `code --add-mcp` | `servers` |
| Cline | панель MCP Servers, `Configure MCP Servers` (путь к файлу не проверен); CLI `~/.cline/data/settings/cline_mcp_settings.json` | `mcpServers` |
| Continue | `.continue/mcpServers/war-selection.yaml` | `mcpServers` (список) |
| Zed | файл настроек (`zed: open settings file`) | `context_servers` |
| JetBrains AI Assistant | Settings, Tools, AI Assistant, Model Context Protocol (MCP), Add | `mcpServers` |
| LM Studio | вкладка Program, Install, Edit mcp.json (путь к файлу не проверен) | `mcpServers` |
| Codex CLI | `codex mcp add ...` или `~/.codex/config.toml` | `[mcp_servers.war-selection]` |
| Gemini CLI | `gemini mcp add ...` или `~/.gemini/settings.json`, `.gemini/settings.json` | `mcpServers` |
| Другие stdio-клиенты | команда `PYTHON`, аргументы `-m ws_mcp`, переменная `WS_GAME_DIR` | |

Подробности, фрагменты конфигурации и ссылки на документацию приведены в английском разделе: пути, команды и фрагменты одинаковы для обоих языков.

## English

The server uses stdio. A client needs three values:

- command: the `python` of the virtual environment where the package is installed (or the `war-selection-mcp` executable);
- arguments: `-m ws_mcp` (none for `war-selection-mcp`);
- environment: `WS_GAME_DIR` (game folder) and optionally `WS_LOG_PATH`.

Print a ready snippet with the current interpreter path:

```bash
war-selection-mcp --list-clients
war-selection-mcp --print-config vscode
```

In the examples `PYTHON` stands for the absolute interpreter path: `C:\path\to\.venv\Scripts\python.exe` on Windows or `/path/to/.venv/bin/python` on macOS and Linux. Escape backslashes in JSON.

Formats were checked against official client documentation on 2026-10-18 (links in each section). **Unverified** marks a file location not stated in the documentation; open the file through the client UI instead.

After upgrading the package, restart the server in the client (or the client itself) to refresh the tool list.

### Common `mcpServers` block

Used by Claude Desktop, Cursor, Windsurf, JetBrains AI Assistant, LM Studio and Gemini CLI.

```json
{
  "mcpServers": {
    "war-selection": {
      "command": "PYTHON",
      "args": ["-m", "ws_mcp"],
      "env": {
        "WS_GAME_DIR": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\War Selection"
      }
    }
  }
}
```

### Claude Desktop

`--print-config claude-desktop`. Docs: https://modelcontextprotocol.io/quickstart/user

| OS | File |
|---|---|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Linux | no official build; **unverified** |

Format: common `mcpServers` block. Restart the application after editing.

### Claude Code

`--print-config claude-code`. Docs: https://code.claude.com/docs/en/mcp

```bash
claude mcp add --transport stdio --scope user --env WS_GAME_DIR="/path/to/War Selection" war-selection -- PYTHON -m ws_mcp
```

Scopes: `local` (default, current project, stored in `~/.claude.json`), `project` (`.mcp.json` in the repository root, `mcpServers` format), `user` (all projects, `~/.claude.json`). Check with `claude mcp list`.

### Cursor

`--print-config cursor`. Docs: https://cursor.com/docs/context/mcp

| Scope | File |
|---|---|
| Global | `~/.cursor/mcp.json` (Windows: `%USERPROFILE%\.cursor\mcp.json`) |
| Project | `.cursor/mcp.json` |

Format: common `mcpServers` block; `"type": "stdio"` is optional.

### Windsurf

`--print-config windsurf`. Docs: https://docs.windsurf.com/windsurf/cascade/mcp

| OS | File |
|---|---|
| macOS, Linux | `~/.config/devin/mcp_config.json` |
| Windows | `%APPDATA%\devin\mcp_config.json` |

Format: common `mcpServers` block. The current documentation lists the paths above; older releases used `~/.codeium/windsurf/mcp_config.json` (**unverified** for current versions). The file can also be opened from the MCP panel in Cascade.

### VS Code

`--print-config vscode`. Docs: https://code.visualstudio.com/docs/copilot/customization/mcp-servers

Workspace file `.vscode/mcp.json`; top-level key is `servers`, not `mcpServers`:

```json
{
  "servers": {
    "war-selection": {
      "type": "stdio",
      "command": "PYTHON",
      "args": ["-m", "ws_mcp"],
      "env": {
        "WS_GAME_DIR": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\War Selection"
      }
    }
  }
}
```

User-level configuration: command palette `MCP: Open User Configuration`, or from the shell:

```bash
code --add-mcp '{"name":"war-selection","command":"PYTHON","args":["-m","ws_mcp"],"env":{"WS_GAME_DIR":"/path/to/War Selection"}}'
```

### Cline

`--print-config cline`. Docs: https://docs.cline.bot/mcp/configuring-mcp-servers

Extension: MCP Servers panel, `Configure MCP Servers`, which opens `cline_mcp_settings.json` (the path inside the editor storage folder is **unverified**). Cline CLI: `~/.cline/data/settings/cline_mcp_settings.json`.

```json
{
  "mcpServers": {
    "war-selection": {
      "command": "PYTHON",
      "args": ["-m", "ws_mcp"],
      "env": { "WS_GAME_DIR": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\War Selection" },
      "disabled": false,
      "autoApprove": []
    }
  }
}
```

### Continue

`--print-config continue`. Docs: https://docs.continue.dev/customize/deep-dives/mcp

Create `.continue/mcpServers/war-selection.yaml` in the workspace:

```yaml
name: War Selection MCP
version: 0.0.1
schema: v1
mcpServers:
  - name: war-selection
    type: stdio
    command: PYTHON
    args:
      - "-m"
      - "ws_mcp"
    env:
      WS_GAME_DIR: "C:\\Program Files (x86)\\Steam\\steamapps\\common\\War Selection"
```

JSON files in the `mcpServers` format placed in `.continue/mcpServers/` are also accepted.

### Zed

`--print-config zed`. Docs: https://zed.dev/docs/ai/mcp

Settings, AI, MCP Servers, `Add Server`, `Add Local Server`, or add the entry manually to the settings file (command palette `zed: open settings file`):

```json
{
  "context_servers": {
    "war-selection": {
      "command": "PYTHON",
      "args": ["-m", "ws_mcp"],
      "env": { "WS_GAME_DIR": "/path/to/War Selection" }
    }
  }
}
```

### JetBrains AI Assistant

`--print-config jetbrains`. Docs: https://www.jetbrains.com/help/ai-assistant/mcp.html

Settings | Tools | AI Assistant | Model Context Protocol (MCP), `Add`, choose JSON and paste the common `mcpServers` block. `Import from Claude` copies servers from the Claude Desktop configuration.

### LM Studio

`--print-config lmstudio`. Docs: https://lmstudio.ai/docs/app/mcp

LM Studio 0.3.17 or newer: Program tab in the right sidebar, `Install`, `Edit mcp.json`; paste the common `mcpServers` block. The file location (`~/.lmstudio/mcp.json`) is **unverified**.

### Codex CLI

`--print-config codex`. Docs: https://developers.openai.com/codex/mcp

```bash
codex mcp add war-selection --env WS_GAME_DIR="/path/to/War Selection" -- PYTHON -m ws_mcp
```

Or edit `~/.codex/config.toml` (Windows: `%USERPROFILE%\.codex\config.toml`; per project: `.codex/config.toml` in trusted projects). The ChatGPT desktop app and the Codex IDE extension share this file:

```toml
[mcp_servers.war-selection]
command = "PYTHON"
args = ["-m", "ws_mcp"]

[mcp_servers.war-selection.env]
WS_GAME_DIR = "C:\\Program Files (x86)\\Steam\\steamapps\\common\\War Selection"
```

### Gemini CLI

`--print-config gemini`. Docs: https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md

```bash
gemini mcp add -s user -e WS_GAME_DIR="/path/to/War Selection" war-selection PYTHON -m ws_mcp
```

Or edit `~/.gemini/settings.json` (user) or `.gemini/settings.json` (project) with the common `mcpServers` block. Optional fields: `cwd`, `timeout`, `trust`.

### Other stdio clients

`--print-config generic`. Any client that launches a local process and speaks MCP over stdin/stdout works with:

| Field | Value |
|---|---|
| command | `PYTHON` (or the `war-selection-mcp` executable) |
| args | `-m ws_mcp` (none for the executable) |
| env | `WS_GAME_DIR`, optional `WS_LOG_PATH` |
| transport | stdio |

Manual check: `npx @modelcontextprotocol/inspector PYTHON -m ws_mcp`.
