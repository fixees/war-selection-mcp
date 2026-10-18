# war-selection-mcp

[![tests](https://github.com/fixees/war-selection-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/fixees/war-selection-mcp/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Локальный MCP-сервер (stdio) для моддинга War Selection (Glyph Worlds) на Lua.

[Русский](#русский) | [English](#english) | [Client setup / Подключение клиентов](docs/clients.md) | [API dump / Выгрузка API](docs/api-dump.md) | [Changelog](CHANGELOG.md)

Неофициальный проект, не связан с Glyph Worlds. War Selection является товарным знаком Glyph Worlds.

---

## Русский

### Обзор

Сервер даёт MCP-клиенту доступ к локальным файлам установленной игры:

- код скачанных модов в `modsStorage`;
- игровые JSON-данные в `Cache/Projects/WarSelection`;
- лог `gen/log.txt`;
- индекс Lua API: встроенный (имена и сигнатуры из дерева WSUS, игра 258.4018, плюс заметки с источниками) и живой, выгруженный из запущенной игры скриптом из `lua/` ([docs/api-dump.md](docs/api-dump.md));
- встроенное руководство по моддингу на русском (`src/ws_mcp/data/guide-ru.md`).

Кроме чтения, сервер проверяет код модов статически (синтаксис Lua 5.4 и известные ошибки), сравнивает версии модов, разбирает ошибки Lua в логе и выдаёт заготовки модов. Сетевых запросов сервер не делает.

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

Обновление: та же команда с `--upgrade`. Пакет устанавливает команду `war-selection-mcp`; эквивалент: `python -m ws_mcp`.

### Настройка

| Переменная | Описание | По умолчанию |
|---|---|---|
| `WS_GAME_DIR` | Папка игры | `C:\Program Files (x86)\Steam\steamapps\common\War Selection` |
| `WS_LOG_PATH` | Путь к файлу лога или к папке с ним | `<WS_GAME_DIR>\gen\`, затем `%LOCALAPPDATA%` и `Documents` |
| `WS_MCP_DATA_DIR` | Папка для живого индекса API | `%LOCALAPPDATA%\war-selection-mcp`; на Linux `~/.local/share/war-selection-mcp` |

### Подключение клиента

Большинство клиентов принимают блок `mcpServers`:

```json
{
  "mcpServers": {
    "war-selection": {
      "command": "C:\\path\\to\\.venv\\Scripts\\python.exe",
      "args": ["-m", "ws_mcp"],
      "env": {
        "WS_GAME_DIR": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\War Selection"
      }
    }
  }
}
```

Готовый фрагмент с путём к текущему интерпретатору печатает `war-selection-mcp --print-config <client>`; список клиентов: `--list-clients`. Пути к файлам конфигурации и форматы для конкретных клиентов: [docs/clients.md](docs/clients.md).

| Клиент | `--print-config` | Формат |
|---|---|---|
| Claude Desktop | `claude-desktop` | JSON `mcpServers` |
| Claude Code | `claude-code` | команда `claude mcp add` |
| Cursor | `cursor` | JSON `mcpServers` |
| Windsurf | `windsurf` | JSON `mcpServers` |
| VS Code | `vscode` | JSON `servers` |
| Cline | `cline` | JSON `mcpServers` |
| Continue | `continue` | YAML |
| Zed | `zed` | JSON `context_servers` |
| JetBrains AI Assistant | `jetbrains` | JSON `mcpServers` |
| LM Studio | `lmstudio` | JSON `mcpServers` |
| Codex CLI | `codex` | TOML `[mcp_servers]` |
| Gemini CLI | `gemini` | JSON `mcpServers` |
| Другие stdio-клиенты | `generic` | JSON `mcpServers` |

После обновления пакета перезапустите сервер в клиенте, чтобы получить новый список инструментов.

### Инструменты

| Инструмент | Параметры | Описание | Доступ |
|---|---|---|---|
| `game_info` | | Пути, версия движка, число модов, наличие папки черновиков и логов | чтение |
| `list_mods` | `query` | Моды в `modsStorage`: id, версии, тип (lua/prm), размеры | чтение |
| `get_mod` | `mod_id`, `version`, `kind`, `max_chars` | Код мода; по умолчанию последняя версия | чтение |
| `search_mod_code` | `regex`, `limit`, `context`, `latest_only` | Поиск по коду модов, результат в виде `файл:строка` с контекстом | чтение |
| `game_data_query` | `file`, `path`, `key_search`, `limit`, `max_chars` | Значение по пути (`build[10].costBuilding`) или поиск ключа в JSON игры | чтение |
| `search_api` | `query`, `limit`, `kind` | Поиск по индексу Lua API: живой индекс, если импортирован, иначе встроенный | чтение |
| `search_guide` | `query`, `limit` | Поиск по встроенному руководству | чтение |
| `read_log` | `tail`, `grep`, `which` | Последние строки `gen/log.txt` (или `log_prev.txt` и др.) | чтение |
| `lint_mod` | `code` или `mod_id`, `version`, `kind` | Синтаксис Lua 5.4, известные ошибки (`math.random` в gameplay, нет `f_recreateModifiedUnitTypes`, `math.atan2`, неизвестные события и обработчики), неизвестные `f_*` с подсказкой | чтение |
| `diff_mod` | `mod_id`, `v1`, `v2`, `kind`, `context` | Unified diff между версиями мода в кэше | чтение |
| `log_errors` | `which`, `tail`, `since`, `limit` | Ошибки Lua из лога: группировка повторов, привязка к модам и строкам кода | чтение |
| `find_examples` | `api_name`, `limit`, `context`, `per_mod` | Реальные вызовы API в модах из кэша, с учётом локальных псевдонимов | чтение |
| `list_events_usage` | `event` | Какие события `addMod` регистрирует каждый мод | чтение |
| `scaffold_mod` | `template`, `params` | Заготовка мода из рецептов руководства с комментариями-источниками; без аргументов выводит список шаблонов. Код возвращается, на диск не пишется | чтение |
| `unit_lookup` | `query`, `limit` | Типы юнитов по legacy id или пути (`legacyIds.json`) и правила постройки из `gameplay.json` | чтение |
| `api_dump_script` | `root`, `space`, `depth`, `max_nodes`, `array_sample`, `compact`, `seeds`, `raw`, `to_table`, `autorun` | Lua-скрипт для консоли F8 или мода: выгружает дерево `root` в `gen/log.txt` строками `WSDUMP` | чтение |
| `import_api_dump` | `file`, `which`, `dump_id`, `space`, `allow_partial`, `reset`, `dry_run`, `limit` | Разбирает выгрузку из лога, строит живой индекс в папке данных пользователя, выдаёт diff с WSUS 258 (added/removed/changed) и список нераскрытых веток | запись (только `WS_MCP_DATA_DIR`) |
| `api_index_status` | | Активный индекс, его версия движка, число записей, устарел ли он относительно `engine-version.txt` | чтение |
| `write_draft` | `mod_id`, `code`, `create`, `extension` | Запись `modsStorage/draft/<mod_id>.lua` | запись |

`lint_mod` проверяет код статически. Неизвестные имена выдаются как предупреждения. Без живого индекса имена сверяются с WSUS 258.4018 и модами из кэша. После `import_api_dump` добавляется правило `absent-in-engine`: функция из WSUS 258, которой нет в выгрузке текущего движка.

### Обновление индекса API из игры

1. Возьмите `lua/wsdump.lua` (запуск через мод) или `lua/wsdump-oneline.lua` (консоль F8), либо сгенерируйте скрипт через `api_dump_script`.
2. Запустите его в режиме разработчика на своей карте. Выгрузка пишется в `gen/log.txt`.
3. Вызовите `import_api_dump`. Чтобы раскрыть ветки из `unexplored`, повторите шаги 1–3.

Подробно, с форматом и списком проверенного и предположений: [docs/api-dump.md](docs/api-dump.md).

### Безопасность

- Все инструменты, кроме `write_draft` и `import_api_dump`, только читают файлы и помечены `readOnlyHint`.
- `import_api_dump` пишет только в `WS_MCP_DATA_DIR` (`api_index_live.json`, `.prev.json`, `api_dump_diff.json`). Если эта папка оказалась внутри папки игры, импорт отказывается.
- Скрипт выгрузки только читает поля движка внутри `pcall` и не вызывает функции `f_*`.
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

Тесты работают на синтетической папке игры. Чтобы прогнать дополнительный тест на реальных файлах, задайте `WS_SAMPLE_DIR`. Если в `PATH` есть `lua5.4`, скрипт выгрузки прогоняется на макете движка (`tests/fixtures/mock_engine.lua`). Встроенный индекс API пересобирается скриптом `scripts/build_api_index.py`, файлы в `lua/` скриптом `scripts/build_lua.py`, тестовая выгрузка скриптом `scripts/make_dump_fixture.py`. Не коммитьте файлы игры (`modsStorage`, `Cache`, логи, `*.pack`); они перечислены в `.gitignore`.

### Благодарности

- [wsunitstats.com](https://wsunitstats.com/en/modding): дерево API WSUS.
- [AdrienRmd/War_Selection_Modding](https://github.com/AdrienRmd/War_Selection_Modding).
- Сообщество War Selection на английском и СНГ Discord-серверах.

### Лицензия

MIT, см. [LICENSE](LICENSE).

---

## English

### Overview

Local stdio MCP server for War Selection (Glyph Worlds) Lua modding. It gives an MCP client access to local game files:

- cached mod source in `modsStorage`;
- game data JSON in `Cache/Projects/WarSelection`;
- the game log `gen/log.txt`;
- a Lua API index: bundled (names and signatures from the WSUS tree, game 258.4018, plus sourced notes) and a live one dumped from the running game with the script in `lua/` ([docs/api-dump.md](docs/api-dump.md));
- a bundled Russian modding guide (`src/ws_mcp/data/guide-ru.md`).

It also lints mod code (Lua 5.4 syntax and known pitfalls), diffs mod versions, parses Lua errors from the log and returns mod scaffolds. The server makes no network requests.

### Requirements

- Python 3.10+; CI runs 3.13 and 3.14.
- An installed copy of War Selection (Windows, or Linux via Steam/Proton).
- An MCP client with stdio support.

### Installation

```bash
python -m venv .venv
.venv/bin/pip install git+https://github.com/fixees/war-selection-mcp.git
```

On Windows use `.venv\Scripts\pip`. Upgrade with the same command plus `--upgrade`. The package installs the `war-selection-mcp` command; `python -m ws_mcp` is equivalent.

### Configuration

| Variable | Description | Default |
|---|---|---|
| `WS_GAME_DIR` | Game directory | `C:\Program Files (x86)\Steam\steamapps\common\War Selection` |
| `WS_LOG_PATH` | Log file or directory containing it | `<WS_GAME_DIR>\gen\`, then `%LOCALAPPDATA%` and `Documents` |
| `WS_MCP_DATA_DIR` | Folder for the live API index | `%LOCALAPPDATA%\war-selection-mcp`; on Linux `~/.local/share/war-selection-mcp` |

### Client setup

Use the `mcpServers` JSON from the Russian section. `war-selection-mcp --print-config <client>` prints a ready snippet with the current interpreter path; `--list-clients` lists the supported names. Per-client file locations and formats are in [docs/clients.md](docs/clients.md); the client table above applies. Restart the server in your client after upgrading so it picks up the new tool list.

### Tools

| Tool | Parameters | Description | Access |
|---|---|---|---|
| `game_info` | | Paths, engine version, mod counts, draft folder and log presence | read |
| `list_mods` | `query` | Mods in `modsStorage`: id, versions, kind (lua/prm), sizes | read |
| `get_mod` | `mod_id`, `version`, `kind`, `max_chars` | Mod source; latest version by default | read |
| `search_mod_code` | `regex`, `limit`, `context`, `latest_only` | Regex search across mod code with `file:line` context | read |
| `game_data_query` | `file`, `path`, `key_search`, `limit`, `max_chars` | Value at a path (`build[10].costBuilding`) or key search in game JSON | read |
| `search_api` | `query`, `limit`, `kind` | Search the Lua API index: the live index if imported, otherwise the bundled one | read |
| `search_guide` | `query`, `limit` | Search the bundled guide | read |
| `read_log` | `tail`, `grep`, `which` | Tail of `gen/log.txt` (or `log_prev.txt`, etc.) | read |
| `lint_mod` | `code` or `mod_id`, `version`, `kind` | Lua 5.4 syntax, known pitfalls (`math.random` in gameplay, missing `f_recreateModifiedUnitTypes`, `math.atan2`, unknown events and handlers), unknown `f_*` names with suggestions | read |
| `diff_mod` | `mod_id`, `v1`, `v2`, `kind`, `context` | Unified diff between cached mod versions | read |
| `log_errors` | `which`, `tail`, `since`, `limit` | Lua errors from the log, grouped and mapped to mods and source lines | read |
| `find_examples` | `api_name`, `limit`, `context`, `per_mod` | Real API usages in cached mods, including local aliases | read |
| `list_events_usage` | `event` | `addMod` events registered by each mod | read |
| `scaffold_mod` | `template`, `params` | Starter code from guide recipes with source comments; lists templates when called without arguments. Returns code, writes nothing | read |
| `unit_lookup` | `query`, `limit` | Unit types by legacy id or path (`legacyIds.json`) with build rules from `gameplay.json` | read |
| `api_dump_script` | `root`, `space`, `depth`, `max_nodes`, `array_sample`, `compact`, `seeds`, `raw`, `to_table`, `autorun` | Lua script for the F8 console or a mod; dumps the `root` tree into `gen/log.txt` as `WSDUMP` lines | read |
| `import_api_dump` | `file`, `which`, `dump_id`, `space`, `allow_partial`, `reset`, `dry_run`, `limit` | Parses the dump from the log, builds the live index in the user data folder, reports the diff against WSUS 258 (added/removed/changed) and unexplored subtrees | write (`WS_MCP_DATA_DIR` only) |
| `api_index_status` | | Active index, its engine version, entry counts, staleness against `engine-version.txt` | read |
| `write_draft` | `mod_id`, `code`, `create`, `extension` | Write `modsStorage/draft/<mod_id>.lua` | write |

`lint_mod` is static analysis. Unknown names are warnings. Without a live index, names are checked against WSUS 258.4018 and cached mods. After `import_api_dump` the `absent-in-engine` rule reports WSUS 258 functions that the current engine does not have.

### Refreshing the API index from the game

1. Take `lua/wsdump.lua` (run as a mod) or `lua/wsdump-oneline.lua` (F8 console), or generate one with `api_dump_script`.
2. Run it in developer mode on your own map. The dump goes to `gen/log.txt`.
3. Call `import_api_dump`. Repeat steps 1-3 to expand the subtrees listed in `unexplored`.

Details, record format, and what is verified versus assumed: [docs/api-dump.md](docs/api-dump.md).

### Safety notes

- All tools except `write_draft` and `import_api_dump` are read-only and annotated with `readOnlyHint`.
- `import_api_dump` writes only to `WS_MCP_DATA_DIR` (`api_index_live.json`, `.prev.json`, `api_dump_diff.json`) and refuses if that folder is inside the game folder.
- The dump script only reads engine fields inside `pcall` and never calls `f_*` functions.
- `write_draft` writes only to `modsStorage/draft`, does not create the folder unless `create=True`, keeps a timestamped `.bak` before overwriting, and rejects path traversal and symlinks.
- The server does not modify game files outside `modsStorage/draft`.
- According to the developer (Wouw, Discord, 2023-07-30), editing mod files outside the in-game editor can affect the released mod version and may result in kicks and bans. Apply and publish mods through the editor in developer mode. Use `write_draft` at your own risk.

### Development

```bash
pip install -e ".[test]"
pytest -q
```

Tests use a synthetic game directory; set `WS_SAMPLE_DIR` to run the optional test against real files. With `lua5.4` on `PATH` the dump script is also run against an engine mock (`tests/fixtures/mock_engine.lua`). Rebuild the bundled index with `scripts/build_api_index.py`, the files in `lua/` with `scripts/build_lua.py`, and the dump fixture with `scripts/make_dump_fixture.py`. Do not commit game files; they are listed in `.gitignore`.

### Credits

- [wsunitstats.com](https://wsunitstats.com/en/modding) for the WSUS API tree.
- [AdrienRmd/War_Selection_Modding](https://github.com/AdrienRmd/War_Selection_Modding).
- The War Selection community on the English and CIS Discord servers.

### License

MIT, see [LICENSE](LICENSE).

Unofficial project, not affiliated with Glyph Worlds. War Selection is a trademark of Glyph Worlds.
