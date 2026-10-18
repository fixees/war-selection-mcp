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
| `WS_MCP_DATA_DIR` | Папка данных сервера: живой индекс API, снимки игры, копии черновиков | `%LOCALAPPDATA%\war-selection-mcp`; на Linux `~/.local/share/war-selection-mcp` |
| `WS_MCP_AUTO_SNAPSHOT` | `0` отключает снимок игры при старте сервера | `1` |

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
| `game_info` | | Пути, версия движка, число модов, черновики, наличие логов, состояние снимков | чтение |
| `list_mods` | `query` | Моды из кэша `modsStorage` и черновики `modsStorage/draft`: id, версии, тип (lua/prm), размеры | чтение |
| `get_mod` | `mod_id`, `version`, `kind`, `source`, `max_chars` | Код мода; по умолчанию черновик, если он есть, иначе последняя версия из кэша | чтение |
| `search_mod_code` | `regex`, `limit`, `context`, `latest_only`, `include_drafts` | Поиск по коду модов и черновиков, результат в виде `файл:строка` с контекстом | чтение |
| `game_data_query` | `file`, `path`, `key_search`, `limit`, `max_chars` | Значение по пути (`build[10].costBuilding`) или поиск ключа в JSON игры | чтение |
| `search_api` | `query`, `limit`, `kind` | Поиск по индексу Lua API: живой индекс, если импортирован, иначе встроенный | чтение |
| `search_guide` | `query`, `limit` | Поиск по встроенному руководству | чтение |
| `read_log` | `tail`, `grep`, `which` | Последние строки `gen/log.txt` (или `log_prev.txt` и др.) | чтение |
| `lint_mod` | `code` или `mod_id`, `version`, `kind`, `source` | Синтаксис Lua 5.4, известные ошибки (`math.random` в gameplay, нет `f_recreateModifiedUnitTypes`, `math.atan2`, неизвестные события и обработчики), неизвестные `f_*` с подсказкой | чтение |
| `diff_mod` | `mod_id`, `v1`, `v2`, `kind`, `context`, `draft` | Unified diff между версиями мода в кэше; `draft=true`: опубликованная версия против черновика | чтение |
| `log_errors` | `which`, `tail`, `since`, `limit` | Ошибки Lua из лога: группировка повторов, привязка к модам и строкам кода | чтение |
| `find_examples` | `api_name`, `limit`, `context`, `per_mod` | Реальные вызовы API в модах из кэша, с учётом локальных псевдонимов | чтение |
| `list_events_usage` | `event` | Какие события `addMod` регистрирует каждый мод | чтение |
| `scaffold_mod` | `template`, `params` | Заготовка мода из рецептов руководства с комментариями-источниками; без аргументов выводит список шаблонов. Код возвращается, на диск не пишется | чтение |
| `unit_lookup` | `query`, `limit` | Типы юнитов по legacy id или пути (`legacyIds.json`) и правила постройки из `gameplay.json` | чтение |
| `api_dump_script` | `root`, `space`, `depth`, `max_nodes`, `array_sample`, `compact`, `seeds`, `raw`, `to_table`, `autorun` | Lua-скрипт для консоли F8 или мода: выгружает дерево `root` в `gen/log.txt` строками `WSDUMP` | чтение |
| `import_api_dump` | `file`, `which`, `dump_id`, `space`, `allow_partial`, `reset`, `dry_run`, `limit` | Разбирает выгрузку из лога, строит живой индекс в папке данных пользователя, выдаёт diff с WSUS 258 (added/removed/changed) и список нераскрытых веток | запись (только `WS_MCP_DATA_DIR`) |
| `api_index_status` | | Активный индекс, его версия движка, число записей, устарел ли он относительно `engine-version.txt` | чтение |
| `snapshot_game` | `force`, `label` | Снимок состояния игры (хэши JSON из `Cache/Projects/WarSelection`, `engine-version.txt`, нормализованное содержимое основных JSON, активный индекс API). Делается и автоматически при старте сервера, если игра изменилась | запись (только `WS_MCP_DATA_DIR`) |
| `diff_game_versions` | `a`, `b`, `limit` | Diff двух снимков: файлы, типы юнитов, правила постройки, исследования и улучшения, ауры, unitOverrides, API (добавлено/удалено/изменились сигнатуры) | запись (только `WS_MCP_DATA_DIR`) |
| `mod_impact` | `a`, `b`, `limit`, `include_drafts` | Какие моды из кэша и черновики используют изменённое между снимками, с `файл:строка` | чтение |
| `log_tail` | `cursor`, `max_lines`, `initial_lines` | Новые строки `gen/log.txt` после курсора и следующий курсор. Учитывает пересоздание лога при запуске игры и `log_prev.txt` | чтение |
| `watch_log_start` | `from_start`, `warnings` | Фоновое слежение за логом: ошибки и предупреждения Lua с привязкой к черновику или моду из кэша и фрагментом кода | чтение |
| `watch_log_poll` | `since_seq`, `limit` | Новые события слежения | чтение |
| `watch_log_stop` | | Остановить слежение | чтение |
| `write_draft` | `mod_id`, `code`, `version`, `extension` | Перезапись существующего черновика `modsStorage/draft/<id>_<версия>-<hash>.lua` с копией в `WS_MCP_DATA_DIR/draft-backups` | запись |

`lint_mod` проверяет код статически. Неизвестные имена выдаются как предупреждения. Без живого индекса имена сверяются с WSUS 258.4018 и модами из кэша. После `import_api_dump` добавляется правило `absent-in-engine`: функция из WSUS 258, которой нет в выгрузке текущего движка.

### Обновление индекса API из игры

1. Возьмите `lua/wsdump.lua` (запуск через мод) или `lua/wsdump-oneline.lua` (консоль F8), либо сгенерируйте скрипт через `api_dump_script`.
2. Запустите его в режиме разработчика на своей карте. Выгрузка пишется в `gen/log.txt`.
3. Вызовите `import_api_dump`. Чтобы раскрыть ветки из `unexplored`, повторите шаги 1–3.

Подробно, с форматом и списком проверенного и предположений: [docs/api-dump.md](docs/api-dump.md).

### Черновики и кэш модов

Проверено по логам игроков (2023, 2025) и папке `modsStorage` на живой установке:

- Кэш опубликованных модов: `modsStorage/<id>_<версия>-<hash16>.lua` и `.prm`. `<id>` — 11 символов (`mod-<id>` в игре), `<hash16>` постоянен для мода во всех версиях.
- Черновики: `modsStorage/draft/<id>_<версия>-<hash16>.lua`. В логе они видны как `Using gameplay modifications: draft/<id>_<версия>` и `/modsStorage/draft/...lua` в ошибках.
- Создание мода в режиме разработчика происходит на сервере (`Start request "Create mod"` в логе), локальный файл при этом не появляется. Файл черновика создаёт игра при «Редактировать скрипт» или при запуске карты с этим модом. Поэтому `write_draft` только перезаписывает существующий черновик и не создаёт файлы.

### Обновления игры

При старте сервер сравнивает игру с последним снимком и при изменениях делает новый (отключается `WS_MCP_AUTO_SNAPSHOT=0`). Первый снимок — точка отсчёта; diff появится после следующего обновления игры. После патча: `diff_game_versions`, затем `mod_impact`. Подробно: [docs/game-snapshots.md](docs/game-snapshots.md).

### Ошибки в реальном времени

- В клиенте: `watch_log_start`, затем периодически `watch_log_poll(since_seq=<next_seq>)`. Или `log_tail(cursor)` для сырых строк.
- В терминале: `war-selection-mcp --watch-log` (с `--from-start` — с начала текущего лога), остановка Ctrl+C.

Форматы ошибок, что проверено и что предполагается: [docs/log-watch.md](docs/log-watch.md).

### Безопасность

- Все инструменты, кроме `write_draft`, `import_api_dump`, `snapshot_game` и `diff_game_versions`, только читают файлы и помечены `readOnlyHint`.
- `import_api_dump`, `snapshot_game` и `diff_game_versions` пишут только в `WS_MCP_DATA_DIR` (`api_index_live.json`, `snapshots/`, `diffs/`). Если эта папка оказалась внутри папки игры, они отказываются.
- Скрипт выгрузки только читает поля движка внутри `pcall` и не вызывает функции `f_*`.
- `write_draft` перезаписывает только существующий файл в `modsStorage/draft` (атомарно). Копия прежнего файла сохраняется в `WS_MCP_DATA_DIR/draft-backups`, в папке игры лишних файлов не появляется. Пути за пределами папки и симлинки отклоняет.
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
| `WS_MCP_DATA_DIR` | Server data folder: live API index, game snapshots, draft backups | `%LOCALAPPDATA%\war-selection-mcp`; on Linux `~/.local/share/war-selection-mcp` |
| `WS_MCP_AUTO_SNAPSHOT` | `0` disables the game snapshot on server start | `1` |

### Client setup

Use the `mcpServers` JSON from the Russian section. `war-selection-mcp --print-config <client>` prints a ready snippet with the current interpreter path; `--list-clients` lists the supported names. Per-client file locations and formats are in [docs/clients.md](docs/clients.md); the client table above applies. Restart the server in your client after upgrading so it picks up the new tool list.

### Tools

| Tool | Parameters | Description | Access |
|---|---|---|---|
| `game_info` | | Paths, engine version, mod counts, drafts, log presence, snapshot state | read |
| `list_mods` | `query` | Cached mods in `modsStorage` and drafts in `modsStorage/draft`: id, versions, kind (lua/prm), sizes | read |
| `get_mod` | `mod_id`, `version`, `kind`, `source`, `max_chars` | Mod source; the draft if one exists, otherwise the latest cached version | read |
| `search_mod_code` | `regex`, `limit`, `context`, `latest_only`, `include_drafts` | Regex search across cached mods and drafts with `file:line` context | read |
| `game_data_query` | `file`, `path`, `key_search`, `limit`, `max_chars` | Value at a path (`build[10].costBuilding`) or key search in game JSON | read |
| `search_api` | `query`, `limit`, `kind` | Search the Lua API index: the live index if imported, otherwise the bundled one | read |
| `search_guide` | `query`, `limit` | Search the bundled guide | read |
| `read_log` | `tail`, `grep`, `which` | Tail of `gen/log.txt` (or `log_prev.txt`, etc.) | read |
| `lint_mod` | `code` or `mod_id`, `version`, `kind`, `source` | Lua 5.4 syntax, known pitfalls (`math.random` in gameplay, missing `f_recreateModifiedUnitTypes`, `math.atan2`, unknown events and handlers), unknown `f_*` names with suggestions | read |
| `diff_mod` | `mod_id`, `v1`, `v2`, `kind`, `context`, `draft` | Unified diff between cached versions; `draft=true` compares the published version with the draft | read |
| `log_errors` | `which`, `tail`, `since`, `limit` | Lua errors from the log, grouped and mapped to mods and source lines | read |
| `find_examples` | `api_name`, `limit`, `context`, `per_mod` | Real API usages in cached mods, including local aliases | read |
| `list_events_usage` | `event` | `addMod` events registered by each mod | read |
| `scaffold_mod` | `template`, `params` | Starter code from guide recipes with source comments; lists templates when called without arguments. Returns code, writes nothing | read |
| `unit_lookup` | `query`, `limit` | Unit types by legacy id or path (`legacyIds.json`) with build rules from `gameplay.json` | read |
| `api_dump_script` | `root`, `space`, `depth`, `max_nodes`, `array_sample`, `compact`, `seeds`, `raw`, `to_table`, `autorun` | Lua script for the F8 console or a mod; dumps the `root` tree into `gen/log.txt` as `WSDUMP` lines | read |
| `import_api_dump` | `file`, `which`, `dump_id`, `space`, `allow_partial`, `reset`, `dry_run`, `limit` | Parses the dump from the log, builds the live index in the user data folder, reports the diff against WSUS 258 (added/removed/changed) and unexplored subtrees | write (`WS_MCP_DATA_DIR` only) |
| `api_index_status` | | Active index, its engine version, entry counts, staleness against `engine-version.txt` | read |
| `snapshot_game` | `force`, `label` | Snapshot of the game state (hashes of `Cache/Projects/WarSelection` JSON, `engine-version.txt`, normalized content of the main JSON files, active API index). Also taken on server start when the game changed | write (`WS_MCP_DATA_DIR` only) |
| `diff_game_versions` | `a`, `b`, `limit` | Diff of two snapshots: files, unit types, build rules, researches and upgrades, auras, unitOverrides, API added/removed/changed signatures | write (`WS_MCP_DATA_DIR` only) |
| `mod_impact` | `a`, `b`, `limit`, `include_drafts` | Cached mods and drafts that reference what changed between snapshots, with `file:line` | read |
| `log_tail` | `cursor`, `max_lines`, `initial_lines` | New `gen/log.txt` lines since a cursor plus the next cursor. Handles log recreation at game start and `log_prev.txt` | read |
| `watch_log_start` | `from_start`, `warnings` | Background log watcher: Lua errors and warnings mapped to the draft or cached mod with a code excerpt | read |
| `watch_log_poll` | `since_seq`, `limit` | New watcher events | read |
| `watch_log_stop` | | Stop the watcher | read |
| `write_draft` | `mod_id`, `code`, `version`, `extension` | Overwrite an existing draft `modsStorage/draft/<id>_<version>-<hash>.lua`, backup in `WS_MCP_DATA_DIR/draft-backups` | write |

`lint_mod` is static analysis. Unknown names are warnings. Without a live index, names are checked against WSUS 258.4018 and cached mods. After `import_api_dump` the `absent-in-engine` rule reports WSUS 258 functions that the current engine does not have.

### Refreshing the API index from the game

1. Take `lua/wsdump.lua` (run as a mod) or `lua/wsdump-oneline.lua` (F8 console), or generate one with `api_dump_script`.
2. Run it in developer mode on your own map. The dump goes to `gen/log.txt`.
3. Call `import_api_dump`. Repeat steps 1-3 to expand the subtrees listed in `unexplored`.

Details, record format, and what is verified versus assumed: [docs/api-dump.md](docs/api-dump.md).

### Drafts and the mod cache

Verified from player logs (2023, 2025) and the `modsStorage` folder of a live install:

- Published mod cache: `modsStorage/<id>_<version>-<hash16>.lua` and `.prm`. `<id>` has 11 characters (`mod-<id>` in game); `<hash16>` stays the same for a mod across versions.
- Drafts: `modsStorage/draft/<id>_<version>-<hash16>.lua`. The log shows them as `Using gameplay modifications: draft/<id>_<version>` and as `/modsStorage/draft/...lua` in errors.
- Creating a mod in developer mode is a server request (`Start request "Create mod"` in the log); no local file appears. The game writes the draft file on "Edit script" or when a map with the mod is started. `write_draft` therefore only overwrites an existing draft and never creates files.

### Game updates

On start the server compares the game with the latest snapshot and stores a new one if it changed (disable with `WS_MCP_AUTO_SNAPSHOT=0`). The first snapshot is the baseline; a diff becomes available after the next game update. After a patch: `diff_game_versions`, then `mod_impact`. Details: [docs/game-snapshots.md](docs/game-snapshots.md).

### Live errors

- In a client: `watch_log_start`, then `watch_log_poll(since_seq=<next_seq>)` periodically, or `log_tail(cursor)` for raw lines.
- In a terminal: `war-selection-mcp --watch-log` (`--from-start` reads the current log from the beginning); stop with Ctrl+C.

Error formats, verified and assumed: [docs/log-watch.md](docs/log-watch.md).

### Safety notes

- All tools except `write_draft`, `import_api_dump`, `snapshot_game` and `diff_game_versions` are read-only and annotated with `readOnlyHint`.
- `import_api_dump`, `snapshot_game` and `diff_game_versions` write only to `WS_MCP_DATA_DIR` (`api_index_live.json`, `snapshots/`, `diffs/`) and refuse if that folder is inside the game folder.
- The dump script only reads engine fields inside `pcall` and never calls `f_*` functions.
- `write_draft` only overwrites an existing file in `modsStorage/draft` (atomic replace). The previous content is copied to `WS_MCP_DATA_DIR/draft-backups`, so no extra files appear in the game folder. Path traversal and symlinks are rejected.
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
