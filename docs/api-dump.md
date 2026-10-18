# Live API dump / Выгрузка API из игры

[Русский](#русский) | [English](#english)

## Русский

Встроенный индекс API снят с дерева WSUS для игры 258.4018. Игра обновляется, поэтому индекс можно пересобрать из запущенной игры: скрипт на Lua обходит дерево `root` и пишет его в `gen/log.txt`, а `import_api_dump` строит из лога локальный индекс. После импорта `search_api` и `lint_mod` используют его в первую очередь; встроенный индекс остаётся запасным для тех веток, которые выгрузка не покрыла.

### Файлы

| Файл | Назначение |
|---|---|
| [`lua/wsdump.lua`](../lua/wsdump.lua) | Полный скрипт с вшитыми именами из встроенного индекса (seeds). Запускается как мод. |
| [`lua/wsdump-oneline.lua`](../lua/wsdump-oneline.lua) | Та же логика одной строкой, без seeds (около 6 КБ). Для консоли F8. |
| `api_dump_script` | Генерирует скрипт с параметрами: стартовый путь, глубина, лимиты, seeds из текущего активного индекса. |
| `war-selection-mcp --dump-script [--compact] [--dump-root PATH] [--space visual]` | То же из командной строки. |

### Запуск

1. Режим разработчика работает только на своей карте. Редактор карт, своя карта, «Модификации», «Мои модификации», `+`, создать мод, «Добавить на карту», сохранить карту, запустить её в своём лобби.
2. Вариант A, мод (размер не ограничен):
   - «Модификации», свой мод, «Редактировать скрипт»; скрипт откроется во внешнем редакторе;
   - вставьте `lua/wsdump.lua` или вывод `api_dump_script` и сохраните;
   - код верхнего уровня выполняется при сохранении и загрузке мода, выгрузка пишется сразу;
   - после выгрузки уберите скрипт из мода, иначе он будет выполняться при каждой загрузке.
3. Вариант B, консоль F8: вставьте строку из `lua/wsdump-oneline.lua` (или `api_dump_script(compact=true, seeds=false)`) и выполните.
4. Для дерева визуальной части (`root.session.visual`, `root.interface`) тот же скрипт запускается из визуального мода с `space="visual"`.
5. Импорт: `import_api_dump()` читает `gen/log.txt`. Если игру уже перезапустили, используйте `import_api_dump(which="log_prev.txt")`, потому что лог очищается при каждом запуске.
6. Повтор: в отчёте `unexplored` перечислены объекты, которые не удалось раскрыть. Сгенерируйте скрипт заново: seeds возьмутся из нового индекса, и следующий проход пойдёт глубже. Отдельную ветку можно выгрузить через `api_dump_script(root="root.unitType[0]")`. Выгрузки разных веток объединяются.

### Что делает скрипт

- Обходит дерево от `root` или от заданного пути. Каждое обращение к полю обёрнуто в `pcall`. Функции `f_*` скрипт не вызывает, только читает поля.
- Имена дочерних полей собираются из нескольких источников, потому что неизвестно, какие из них работают для объектов движка:
  - `pairs(obj)` в `pcall`;
  - `tostring(obj)`, если он возвращает листинг вида `имя: значение`;
  - `toTable(obj)` только внутри элементов массивов, кроме `root.scene*` (на больших ветках это тяжело);
  - seeds: имена из индекса для этого пути. Каждое такое имя проверяется чтением; `nil` означает, что в движке его нет.
- Для каждого раскрытого объекта вызывается `log(obj)`, и родной листинг движка (имена, сигнатуры функций, `{...}`, `[N]`) попадает в лог между маркерами `R`/`r`. Из этого листинга импорт берёт сигнатуры и имена, которые Lua не смог перечислить.
- Массивы определяются по числовому полю `size` и элементу `[0]`. Берётся `array_sample` элементов (по умолчанию первый), путь нормализуется до `[]`.
- Защита от циклов:
  - объект, уже встреченный по ссылке, пишется как `link`;
  - путь, в котором одно имя повторяется больше двух раз, дальше не раскрывается;
  - каждый нормализованный путь раскрывается один раз;
  - действуют лимиты глубины (`depth`, 12) и числа узлов (`max_nodes`, 20000).
- `math.random` и `math.atan2` не используются.

### Формат строк

Каждая запись начинается с `WSDUMP<TAB><id><TAB>`. Первая строка каждого вызова `log()` получает от движка метку времени, импорт её отбрасывает.

| Запись | Поля | Смысл |
|---|---|---|
| `B` | format, space, root, options | начало; options содержит `version=` из `root.version`, если поле читается |
| `N` | path, type, value | узел; type: `num str bool func obj arr nil err link` |
| `X` | path, obj/arr, size | узел раскрыт, его дочерние имена проверены |
| `R` ... `r` | path | между ними родной вывод `log(obj)` |
| `W` | message | предупреждение (ошибка скрипта, cycle guard) |
| `E` | count, ok/truncated/error, raw | конец |

### Импорт

- Хранилище: `%LOCALAPPDATA%\war-selection-mcp\api_index_live.json`; на Linux `$XDG_DATA_HOME/war-selection-mcp` или `~/.local/share/war-selection-mcp`; путь переопределяется через `WS_MCP_DATA_DIR`. В папку игры импорт не пишет; если `WS_MCP_DATA_DIR` указывает внутрь неё, импорт откажется.
- Версия движка берётся из строки `Engine Version:` в логе перед выгрузкой, при её отсутствии из `root.version`.
- Если версия движка отличается от уже импортированной, индекс заменяется; предыдущий сохраняется в `api_index_live.prev.json`.
- Diff со встроенным индексом пишется в `api_dump_diff.json`:
  - `added`: путей нет в WSUS 258;
  - `removed`: путь проверен и вернул `nil` или отсутствует в раскрытом родителе;
  - `changed`: другой вид, тип или сигнатура;
  - `not_covered`: родитель не раскрывался, о пути ничего не известно.
- Выгрузка без `E` (обрезанный лог, вылет игры) принимается только с `allow_partial=true`.
- `dry_run=true` показывает отчёт и ничего не пишет.

### Как индекс используется

- `search_api`: живые записи, затем записи WSUS, которых выгрузка не опровергла, затем заметки из шпаргалки. В ответе поле `index` показывает, какой индекс активен.
- `lint_mod`: правило `absent-in-engine` срабатывает для `f_*` из WSUS 258, которых нет ни в одном месте живой выгрузки (а все места, где WSUS их показывал, были раскрыты). Без живого индекса это правило не работает.
- `game_info` и `api_index_status` сравнивают версию живого индекса с `engine-version.txt` и сообщают, если индекс устарел.

### Проверено и предположения

Проверено (источник указан):

- `log(x)` пишет в консоль режима разработчика и в `gen/log.txt` (Wouw, Discord, 24.04.2023 и 18.09.2023; моды в кэше используют `log()` в gameplay- и visual-модах).
- `log(obj)` для объекта движка выводит один уровень: `имя: значение`, функции как `f_name: (сигнатура)`, вложенные объекты как `{...}`, массивы как `[N]`. Первая строка получает метку времени, остальные строки того же вызова идут без неё (лог игрока в #new-mod-creation, 19.09.2023, вывод `log(root.scene[0])`, движок 142).
- Строки лога имеют префикс `YYYY-MM-DD HH:MM:SS `, в начале лога есть `Engine Version: 264` и `Game Version: 264.4021...` (`gen/log.txt` на ПК, 18.10.2026).
- `toTable(obj)` строит Lua-таблицу из объекта движка и его потомков (IbubussI, 15.09.2023; Wouw, 30.01.2024: `log(toJson(toTable(root)))`). В выгрузке `root.researches` от IbubussI функций нет, поэтому сигнатуры берутся из `log(obj)`.
- Массивы индексируются с 0, у них есть поле `size` (`for i = 0, x.size - 1` в модах из кэша; `size` в дереве WSUS).
- `setmetatable`, `getmetatable`, `pcall`, `string.*`, `table.*` доступны: их использует базовый мод `JnHcuvqS6ga`.
- Код верхнего уровня выполняется при каждом сохранении мода (Wouw, guide 2, 6.5).
- Импорт проверен тестами на макете движка (`tests/fixtures/mock_engine.lua`, Lua 5.4): объекты без `pairs`, листинг `log(obj)`, циклы, ошибки доступа, обрезанные и испорченные строки.

Не проверено в игре 264 (предположения):

- Работает ли `pairs()` на объектах движка. Скрипт пробует и не зависит от результата.
- Возвращает ли `tostring(obj)` тот же листинг, что `log(obj)`. Если да, обход за один проход раскроет всё дерево; если нет, глубина набирается повторными проходами с seeds.
- Формат `log(obj)` в движке 264 совпадает с форматом движка 142. Если формат другой, импорт всё равно возьмёт записи `N`, но сигнатуры будут `(?)`.
- Ограничение длины строки в консоли F8 не задокументировано. Если строка обрезается, используйте вариант A (мод).
- Корень в консоли F8 может быть gameplay- или visual-корнем. Импорт определяет пространство по содержимому (`unitType`/`scene` против `interface`/`session`) и предупреждает о несовпадении с параметром `space`.
- Поля `root.version` (gameplay) и `root.buildNumber` (visual) взяты из WSUS 258; их наличие и смысл в 264 не проверены.
- Время выполнения и объём лога на полном дереве не измерены. Если игра подвисает, уменьшите `depth`/`max_nodes` или выгружайте ветки по отдельности.

## English

The bundled index comes from the WSUS tree for game 258.4018. To refresh it from the running game:

1. Generate the script with `api_dump_script`, or take `lua/wsdump.lua` (full, with seeds) or `lua/wsdump-oneline.lua` (console).
2. Run it in developer mode on your own map. Either paste it into a mod script (top-level code runs on save/load; remove it afterwards), or paste the one-line variant into the F8 console. Use a visual mod with `space="visual"` for the visual tree.
3. Call `import_api_dump`. It reads `gen/log.txt`, or `which="log_prev.txt"` after a restart, and writes the live index to the user data folder (`WS_MCP_DATA_DIR`, default `%LOCALAPPDATA%\war-selection-mcp`). It never writes to the game folder. It reports added, removed, changed and not-covered paths against WSUS 258, and lists unexplored objects.
4. Repeat to go deeper. Regenerated scripts take their seeds from the live index.

The script only reads fields under `pcall` and never calls `f_*` functions. It collects child names from `pairs`, a `tostring` listing, `toTable` (inside array elements only) and seeds from the index. It logs the native one-level `log(obj)` listing for each expanded object, so the importer can take function signatures from it. Arrays are sampled and written as `[]`. Cycles are cut by object identity, a repeated-name guard and depth/node limits.

The verified facts and the assumptions are listed in the Russian section with their sources.
