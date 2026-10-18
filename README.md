<div align="center">

# ⚔️ War Selection MCP

**MCP-сервер для моддинга War Selection: ИИ-ассистент видит моды, данные игры, Lua API и логи прямо на вашем ПК**

*An MCP server for War Selection modding: your AI assistant can read cached mods, game data, the Lua API index and logs on your PC*

[![tests](https://github.com/fixees/war-selection-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/fixees/war-selection-mcp/actions/workflows/tests.yml)
[![Python](https://img.shields.io/badge/python-3.13%20%7C%203.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-stdio%20server-6E56CF)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)](#-быстрый-старт)
[![Unofficial](https://img.shields.io/badge/status-unofficial%20fan%20project-orange)](#-дисклеймер)

[Русский](#-русский) · [English](#-english)

</div>

---

## 🇷🇺 Русский

### 📖 Что это

**War Selection MCP** — локальный [MCP](https://modelcontextprotocol.io/)-сервер для моддинга RTS **War Selection** от Glyph Worlds. Он подключается к Cursor, Claude Desktop или другому MCP-клиенту и даёт ассистенту инструменты для работы с файлами игры, которые уже лежат у вас на диске. Скриншоты и копирование текста из игры больше не нужны.

- 🔎 поиск по коду всех скачанных модов из `modsStorage`: живая библиотека примеров на Lua;
- 📊 запросы к игровым JSON-данным (`Cache/Projects/WarSelection`);
- 📚 встроенный индекс Lua API (863 записи из дерева WSUS v258.4018 и наши заметки с источниками);
- 🇷🇺 встроенный русский гайд по моддингу со ссылками на источники у каждого факта;
- 📜 чтение лога игры `gen/log.txt`, то есть вывода консоли разработчика;
- ✍️ запись черновика мода, но только в `modsStorage/draft` и с бэкапом.

Сервер работает локально через stdio. Он ничего не отправляет в сеть и не трогает исполняемые файлы игры.

### 🧰 Инструменты

| Инструмент | Что делает | Доступ |
|---|---|:---:|
| `game_info` | Пути, версия движка (`engine-version.txt`), число модов, наличие папки черновиков и логов | 👁️ чтение |
| `list_mods` | Скачанные моды: id, версии, последняя версия, тип файлов (lua/prm), размеры | 👁️ чтение |
| `get_mod` | Код мода по ID (`mod-XXXX`), по умолчанию последняя версия | 👁️ чтение |
| `search_mod_code` | Поиск по коду модов регулярным выражением, результат `файл:строка` с контекстом | 👁️ чтение |
| `game_data_query` | Запрос к JSON игры по пути (`build[10].costBuilding`) или поиск ключа | 👁️ чтение |
| `search_api` | Поиск по индексу Lua API: функции, поля, события, сигнатуры | 👁️ чтение |
| `search_guide` | Поиск по встроенному русскому гайду (`guide-ru.md`) | 👁️ чтение |
| `read_log` | Последние N строк `gen/log.txt` (а также `log_prev.txt` и др.) с фильтром по regex | 👁️ чтение |
| `write_draft` | Запись `modsStorage/draft/<mod_id>.lua`, с `.bak` перед перезаписью | ✍️ запись |

### 🚀 Быстрый старт

Нужны Python 3.10 или новее (проверено на 3.13 и 3.14) и MCP-клиент.

**Windows (cmd):**
```bat
py -m venv %USERPROFILE%\war-selection-mcp
%USERPROFILE%\war-selection-mcp\Scripts\python -m pip install git+https://github.com/fixees/war-selection-mcp.git
```

**Linux:**
```bash
python3 -m venv ~/war-selection-mcp
~/war-selection-mcp/bin/pip install git+https://github.com/fixees/war-selection-mcp.git
```

Из исходников:
```bash
git clone https://github.com/fixees/war-selection-mcp.git
cd war-selection-mcp
python -m venv .venv
.venv/bin/pip install -e ".[test]"     # Windows: .venv\Scripts\pip install -e ".[test]"
.venv/bin/pytest -q
```

### 🔌 Подключение

**Cursor** — `%USERPROFILE%\.cursor\mcp.json` (глобально) или `.cursor\mcp.json` в проекте. Замените `<USER>` на имя пользователя Windows:

```json
{
  "mcpServers": {
    "war-selection": {
      "command": "C:\\Users\\<USER>\\war-selection-mcp\\Scripts\\war-selection-mcp.exe",
      "args": [],
      "env": {
        "WS_GAME_DIR": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\War Selection"
      }
    }
  }
}
```

Можно и без exe: `"command": "C:\\Users\\<USER>\\war-selection-mcp\\Scripts\\python.exe"`, `"args": ["-m", "ws_mcp"]`. После правки перезапустите Cursor или нажмите «Refresh» в Settings → MCP.

**Claude Desktop** — `%APPDATA%\Claude\claude_desktop_config.json`, тот же блок `mcpServers`. **Другие клиенты** (VS Code, Windsurf, Cline и т. д.) — любой клиент с поддержкой stdio-серверов: команда `war-selection-mcp` или `python -m ws_mcp`.

### ⚙️ Настройки

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `WS_GAME_DIR` | Папка игры | `C:\Program Files (x86)\Steam\steamapps\common\War Selection` |
| `WS_LOG_PATH` | Явный путь к логу или к папке с ним | ищет в `<игра>\gen\`, `%LOCALAPPDATA%`, `Documents` |

На Linux (Steam/Proton) укажите `WS_GAME_DIR`, например `~/.steam/steam/steamapps/common/War Selection`.

### 🛡️ Безопасность

- **По умолчанию только чтение.** Восемь из девяти инструментов ничего не пишут и помечены MCP-аннотацией `readOnlyHint`.
- **`write_draft` пишет только в `modsStorage/draft`.** Без `create=True` он не создаёт папку, перед перезаписью делает `.bak` с меткой времени, а выход из папки и симлинки отклоняет.
- **Исполняемые файлы и ресурсы игры** (`*.pack`, `*.bin`, `Cache`) сервер не изменяет.
- ⚠️ **Риск бана.** Разработчик Wouw предупреждал (#existing-mods-customize-help, 30.07.2023): правка файлов модов в обход внутриигрового редактора может задеть релизный файл вместо черновика, а за это кикают из матчей и банят. Применяйте и публикуйте моды только через редактор в режиме разработчика. `write_draft` используйте на свой риск.

### 🗂️ Структура проекта

```
war-selection-mcp/
├── src/ws_mcp/
│   ├── server.py          # FastMCP-сервер, регистрация инструментов
│   ├── core.py            # логика: моды, JSON, поиск, логи, черновики
│   ├── config.py          # пути и переменные окружения
│   └── data/
│       ├── api_index.json # индекс Lua API (WSUS v258.4018 + шпаргалка)
│       └── guide-ru.md    # русский гайд по моддингу
├── scripts/build_api_index.py  # пересборка индекса API (для разработчиков)
├── tests/                 # pytest на синтетической папке игры
└── .github/workflows/     # CI
```

### 🤝 Участие

Issues и pull request приветствуются: новые инструменты, исправления в гайде, проверенные в игре примеры кода.

- Тесты используют синтетическую папку игры: `pytest -q`. Для прогона на реальных файлах задайте `WS_SAMPLE_DIR`.
- **Никогда не коммитьте файлы игры** (`modsStorage`, `Cache`, логи, `*.pack`), они уже в `.gitignore`.
- Чужой код из модов в репозиторий не кладём. Короткие фрагменты в гайде даны с указанием источника.

### 🙏 Благодарности

- [wsunitstats.com](https://wsunitstats.com/en/modding): дерево Lua API (WSUS), из него взяты имена и сигнатуры с указанием источника.
- [AdrienRmd/War_Selection_Modding](https://github.com/AdrienRmd/War_Selection_Modding): английский гайд с примерами модов.
- Сообщество War Selection, англоязычный и СНГ Discord-серверы: моддеры и разработчики, чьи ответы процитированы в гайде.

### ⚖️ Дисклеймер

Неофициальный фанатский проект, не связан с Glyph Worlds и не одобрен ими. War Selection — товарный знак Glyph Worlds. Все права на игру и её ресурсы принадлежат правообладателям.

### 📄 Лицензия

[MIT](LICENSE) © 2026 Artur Roman ([@fixees](https://github.com/fixees))

---

## 🇬🇧 English

### 📖 About

**War Selection MCP** is a local [Model Context Protocol](https://modelcontextprotocol.io/) server for modding the RTS **War Selection** by Glyph Worlds. Plug it into Cursor, Claude Desktop or any MCP client, and your assistant gets tools that work with the game files already on your disk: no more screenshots or copy-pasting from the game.

It runs locally over stdio, makes no network calls and never modifies game binaries.

### 🧰 Tools

| Tool | What it does | Access |
|---|---|:---:|
| `game_info` | Game paths, engine version, mod counts, draft folder and log presence | 👁️ read |
| `list_mods` | Cached mods in `modsStorage`: id, versions, latest, lua/prm, sizes | 👁️ read |
| `get_mod` | Mod source by ID (`mod-XXXX`), latest version by default | 👁️ read |
| `search_mod_code` | Case-insensitive regex search across mod code with `file:line` context | 👁️ read |
| `game_data_query` | Query `Cache/Projects/WarSelection/*.json` by path or key search | 👁️ read |
| `search_api` | Bundled Lua API index: names and signatures from the public WSUS tree (game 258.4018) plus our notes | 👁️ read |
| `search_guide` | Search the bundled Russian modding guide | 👁️ read |
| `read_log` | Tail of `gen/log.txt` (or `log_prev.txt`, …) with regex filter | 👁️ read |
| `write_draft` | Writes only `modsStorage/draft/<mod_id>.lua`, keeps a timestamped `.bak` | ✍️ write |

### 🚀 Quick start

Requires Python 3.10+ (tested on 3.13 and 3.14).

```bat
:: Windows
py -m venv %USERPROFILE%\war-selection-mcp
%USERPROFILE%\war-selection-mcp\Scripts\python -m pip install git+https://github.com/fixees/war-selection-mcp.git
```
```bash
# Linux
python3 -m venv ~/war-selection-mcp
~/war-selection-mcp/bin/pip install git+https://github.com/fixees/war-selection-mcp.git
```

### 🔌 Client setup

**Cursor:** add to `%USERPROFILE%\.cursor\mcp.json` (replace `<USER>`):

```json
{
  "mcpServers": {
    "war-selection": {
      "command": "C:\\Users\\<USER>\\war-selection-mcp\\Scripts\\war-selection-mcp.exe",
      "args": [],
      "env": {
        "WS_GAME_DIR": "C:\\Program Files (x86)\\Steam\\steamapps\\common\\War Selection"
      }
    }
  }
}
```

**Claude Desktop:** the same `mcpServers` block in `%APPDATA%\Claude\claude_desktop_config.json`. **Other clients:** any stdio-capable client, using the command `war-selection-mcp` or `python -m ws_mcp`.

### ⚙️ Configuration

| Variable | Purpose | Default |
|---|---|---|
| `WS_GAME_DIR` | Game folder | `C:\Program Files (x86)\Steam\steamapps\common\War Selection` |
| `WS_LOG_PATH` | Explicit log file or folder | searches `<game>\gen\`, `%LOCALAPPDATA%`, `Documents` |

### 🛡️ Safety

- **Read-only by default.** Eight of nine tools never write and carry the MCP `readOnlyHint` annotation.
- **`write_draft` only writes into `modsStorage/draft`.** It refuses to create the folder unless `create=True`, keeps a timestamped `.bak`, and rejects path traversal and symlinks.
- **Never touches game binaries or assets** (`*.pack`, `*.bin`, `Cache`).
- ⚠️ **Ban risk.** Developer Wouw warned (30 Jul 2023) that editing mod files outside the in-game editor can hit the release file instead of the draft, and that gets players kicked and banned. Apply and publish mods through the editor in developer mode only. Use `write_draft` at your own risk.

### 🤝 Contributing

Issues and PRs welcome. Run `pytest -q` (tests use a synthetic game folder; set `WS_SAMPLE_DIR` for an optional run against real files). Never commit game files: they are already covered by `.gitignore`.

### 🙏 Credits

[wsunitstats.com](https://wsunitstats.com/en/modding) (WSUS API tree), [AdrienRmd/War_Selection_Modding](https://github.com/AdrienRmd/War_Selection_Modding), and the War Selection community on the English and CIS Discord servers.

### ⚖️ Disclaimer

Unofficial fan project, not affiliated with or endorsed by Glyph Worlds. War Selection is a trademark of Glyph Worlds. All game rights and assets belong to their respective owners.

### 📄 License

[MIT](LICENSE) © 2026 Artur Roman ([@fixees](https://github.com/fixees))
