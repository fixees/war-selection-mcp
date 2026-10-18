# war-selection-mcp

[![tests](https://github.com/fixees/war-selection-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/fixees/war-selection-mcp/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Локальный MCP-сервер (stdio) для моддинга War Selection (Glyph Worlds) на Lua.

[Русский](#русский) | [English](#english)

Неофициальный проект, не связан с Glyph Worlds. War Selection является товарным знаком Glyph Worlds.

---

## Русский

### Обзор

Сервер даёт MCP-клиенту (Cursor, Claude Desktop и др.) доступ к локальным файлам установленной игры:

- код скачанных модов в `modsStorage`;
- игровые JSON-данные в `Cache/Projects/WarSelection`;
- лог `gen/log.txt`;
- встроенный индекс Lua API: имена и сигнатуры из дерева WSUS (игра 258.4018), а также заметки с источниками;
- встроенное руководство по моддингу на русском (`src/ws_mcp/data/guide-ru.md`).

Сетевых запросов сервер не делает.

### Требования

- Python 3.10 или новее; CI проверяет 3.13 и 3.14.
- Установленная War Selection (Windows или Linux через Steam/Proton).
- MCP-клиент с поддержкой stdio.

### Установка

```bash
python -m venv .venv
.venv/bin/pip install git+https://github.com/fixees/war-selection-mcp.git
```

На Windows: `.venv\Scripts\pip install git+https://github.com/fixees/war-selection-mcp.git`.

Пакет устанавливает команду `war-selection-mcp`; эквивалент: `python -m ws_mcp`.

### Настройка

| Переменная | Описание | По умолчанию |
|---|---|---|
| `WS_GAME_DIR` | Папка игры | `C:\Program Files (x86)\Steam\steamapps\common\War Selection` |
| `WS_LOG_PATH` | Путь к файлу лога или к папке с ним | `<WS_GAME_DIR>\gen\`, затем `%LOCALAPPDATA%` и `Documents` |

### Подключение клиента

Cursor: `%USERPROFILE%\.cursor\mcp.json` или `.cursor/mcp.json` в проекте.
Claude Desktop: `%APPDATA%\Claude\claude_desktop_config.json`.

```json
{
  "mcpServers": {
    "war-selection": {
      "command": "C:\\path\\to\\.venv\\Scripts\\war-selection-mcp.exe",
      "args": [],
      "env": {
        "WS_GAME_DIR": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\War Selection"
      }
    }
  }
}
```

Вместо exe можно указать `"command": "C:\\path\\to\\.venv\\Scripts\\python.exe"` и `"args": ["-m", "ws_mcp"]`.

### Инструменты

| Инструмент | Параметры | Описание | Доступ |
|---|---|---|---|
| `game_info` | | Пути, версия движка, число модов, наличие папки черновиков и логов | чтение |
| `list_mods` | `query` | Моды в `modsStorage`: id, версии, тип (lua/prm), размеры | чтение |
| `get_mod` | `mod_id`, `version`, `kind`, `max_chars` | Код мода; по умолчанию последняя версия | чтение |
| `search_mod_code` | `regex`, `limit`, `context`, `latest_only` | Поиск по коду модов, результат в виде `файл:строка` с контекстом | чтение |
| `game_data_query` | `file`, `path`, `key_search`, `limit`, `max_chars` | Значение по пути (`build[10].costBuilding`) или поиск ключа в JSON игры | чтение |
| `search_api` | `query`, `limit`, `kind` | Поиск по индексу Lua API | чтение |
| `search_guide` | `query`, `limit` | Поиск по встроенному руководству | чтение |
| `read_log` | `tail`, `grep`, `which` | Последние строки `gen/log.txt` (или `log_prev.txt` и др.) | чтение |
| `write_draft` | `mod_id`, `code`, `create`, `extension` | Запись `modsStorage/draft/<mod_id>.lua` | запись |

### Безопасность

- Все инструменты, кроме `write_draft`, только читают файлы и помечены `readOnlyHint`.
- `write_draft` пишет только в `modsStorage/draft`. Без `create=True` папку не создаёт. Перед перезаписью сохраняет `.bak` с меткой времени. Пути за пределами папки и симлинки отклоняет.
- Файлы игры вне `modsStorage/draft` сервер не изменяет.
- По словам разработчика (Wouw, Discord, 30.07.2023), правка файлов модов в обход внутриигрового редактора может затронуть релизную версию мода, а за это кикают из матчей и банят. Применяйте и публикуйте моды через редактор в режиме разработчика. `write_draft` используется на свой риск.

### Разработка

```bash
git clone https://github.com/fixees/war-selection-mcp.git
cd war-selection-mcp
python -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest -q
```

Тесты работают на синтетической папке игры. Чтобы прогнать дополнительный тест на реальных файлах, задайте `WS_SAMPLE_DIR`. Индекс API пересобирается скриптом `scripts/build_api_index.py`. Не коммитьте файлы игры (`modsStorage`, `Cache`, логи, `*.pack`); они перечислены в `.gitignore`.

### Благодарности

- [wsunitstats.com](https://wsunitstats.com/en/modding): дерево API WSUS.
- [AdrienRmd/War_Selection_Modding](https://github.com/AdrienRmd/War_Selection_Modding).
- Сообщество War Selection на английском и СНГ Discord-серверах.

### Лицензия

MIT, см. [LICENSE](LICENSE).

---

## English

### Overview

Local stdio MCP server for War Selection (Glyph Worlds) Lua modding. It gives an MCP client (Cursor, Claude Desktop, etc.) access to local game files:

- cached mod source in `modsStorage`;
- game data JSON in `Cache/Projects/WarSelection`;
- the game log `gen/log.txt`;
- a bundled Lua API index: names and signatures from the WSUS tree (game 258.4018) plus sourced notes;
- a bundled Russian modding guide (`src/ws_mcp/data/guide-ru.md`).

The server makes no network requests.

### Requirements

- Python 3.10+; CI runs 3.13 and 3.14.
- An installed copy of War Selection (Windows, or Linux via Steam/Proton).
- An MCP client with stdio support.

### Installation

```bash
python -m venv .venv
.venv/bin/pip install git+https://github.com/fixees/war-selection-mcp.git
```

On Windows use `.venv\Scripts\pip`. The package installs the `war-selection-mcp` command; `python -m ws_mcp` is equivalent.

### Configuration

| Variable | Description | Default |
|---|---|---|
| `WS_GAME_DIR` | Game directory | `C:\Program Files (x86)\Steam\steamapps\common\War Selection` |
| `WS_LOG_PATH` | Log file or directory containing it | `<WS_GAME_DIR>\gen\`, then `%LOCALAPPDATA%` and `Documents` |

### Client setup

Cursor: `%USERPROFILE%\.cursor\mcp.json` or project-level `.cursor/mcp.json`.
Claude Desktop: `%APPDATA%\Claude\claude_desktop_config.json`.
Use the JSON from the Russian section above; other stdio clients take the same command and env.

### Tools

| Tool | Parameters | Description | Access |
|---|---|---|---|
| `game_info` | | Paths, engine version, mod counts, draft folder and log presence | read |
| `list_mods` | `query` | Mods in `modsStorage`: id, versions, kind (lua/prm), sizes | read |
| `get_mod` | `mod_id`, `version`, `kind`, `max_chars` | Mod source; latest version by default | read |
| `search_mod_code` | `regex`, `limit`, `context`, `latest_only` | Regex search across mod code with `file:line` context | read |
| `game_data_query` | `file`, `path`, `key_search`, `limit`, `max_chars` | Value at a path (`build[10].costBuilding`) or key search in game JSON | read |
| `search_api` | `query`, `limit`, `kind` | Search the Lua API index | read |
| `search_guide` | `query`, `limit` | Search the bundled guide | read |
| `read_log` | `tail`, `grep`, `which` | Tail of `gen/log.txt` (or `log_prev.txt`, etc.) | read |
| `write_draft` | `mod_id`, `code`, `create`, `extension` | Write `modsStorage/draft/<mod_id>.lua` | write |

### Safety notes

- All tools except `write_draft` are read-only and annotated with `readOnlyHint`.
- `write_draft` writes only to `modsStorage/draft`, does not create the folder unless `create=True`, keeps a timestamped `.bak` before overwriting, and rejects path traversal and symlinks.
- The server does not modify game files outside `modsStorage/draft`.
- According to the developer (Wouw, Discord, 2023-07-30), editing mod files outside the in-game editor can affect the released mod version and may result in kicks and bans. Apply and publish mods through the editor in developer mode. Use `write_draft` at your own risk.

### Development

```bash
pip install -e ".[test]"
pytest -q
```

Tests use a synthetic game directory; set `WS_SAMPLE_DIR` to run the optional test against real files. Rebuild the API index with `scripts/build_api_index.py`. Do not commit game files; they are listed in `.gitignore`.

### Credits

- [wsunitstats.com](https://wsunitstats.com/en/modding) for the WSUS API tree.
- [AdrienRmd/War_Selection_Modding](https://github.com/AdrienRmd/War_Selection_Modding).
- The War Selection community on the English and CIS Discord servers.

### License

MIT, see [LICENSE](LICENSE).

Unofficial project, not affiliated with Glyph Worlds. War Selection is a trademark of Glyph Worlds.
