# Моддинг War Selection: руководство для начинающих и продолжающих

> **Версия игры:** 258.4018 (дерево API WSUS снято 10.10.2026: `gameplay.root.version = 4018`, `visual.root.buildNumber = 12097`) [1]
> **Дата руководства:** 18.10.2026. Все даты сообщений указаны по Екатеринбургу (UTC+5).
> **Автор сборки:** сообщество, по открытым сообщениям Discord и данным WSUS. Это не официальный документ Glyph Worlds.

### Как читать это руководство
- Номер в квадратных скобках, например **[20]**, — ссылка на источник из списка в конце.
- Короткие цитаты разработчика даны в оригинале, на английском.
- У каждого блока кода стоит статус:
  - ✅ **проверено в игре** — пока таких блоков нет. Проверка идёт по `test-checklist.md`.
  - 🟡 **из рабочего мода или сообщения.** Код взят из указанного источника. Наши добавки помечены `-- [наше]`.
  - ⚪ **не проверено** — наш вывод из дерева API. Может не работать.
- Имена функций взяты только из дерева WSUS v258.4018 или из процитированных фрагментов. Если имя менялось, это отмечено.
- **Версии источников различаются.** Дерево API WSUS снято с игры **258.4018** [1]. Моды из локального кэша `modsStorage` на ПК автора прочитаны 18.10.2026 на движке **264** (`engine-version.txt`) [95–102]. Если имя есть в коде модов кэша, оно работает на 264, даже если в WSUS выглядит иначе.
- В коде модов кэша и у Wouw встречается запись через подчёркивание: `root.scene[0].landscape_zones`, `treasury_resources`, `root.researches_list_size`, `root.session_visual_commands` [26][96][99][101]. По нашим наблюдениям, это то же самое, что запись через точку (`landscape.zones` и т. д.).

> ⚠️ **API меняется.** Разработчики сначала скрывают функцию, потом предупреждают об устаревании, потом удаляют: «On the first step we just hide functions. In the second step, we notify… In the third step, we remove» [53]. Старый код из Discord 2023–2024 годов может не работать. Сверяйтесь с WSUS [1] или с выводом `log(root)` (раздел 3).

---

## Оглавление
1. [Что такое моды](#1-что-такое-моды)
2. [Первый мод за 10 минут](#2-первый-мод-за-10-минут)
3. [Отладка](#3-отладка)
4. [Основы API](#4-основы-api)
5. [Готовые рецепты](#5-готовые-рецепты)
6. [Частые ошибки](#6-частые-ошибки)
7. [Текущие баги редактора и обходы](#7-текущие-баги-редактора-и-обходы)
8. [Правила: что можно и за что банят](#8-правила-что-можно-и-за-что-банят)
9. [Где спрашивать, готовые моды, ссылки](#9-где-спрашивать-готовые-моды-ссылки)
10. [Источники](#источники)

---

## 1. Что такое моды

**Мод (модификация)** — это скрипт на Lua, подключённый к карте.
- Файлами в папку игры моды не ставятся. Мод создают в редакторе карт, привязывают к карте, а код пишут во внутриигровом редакторе скриптов [10].
- Моды работают **только на заранее созданных (пользовательских) картах**. К случайным картам и рейтинговым режимам их не подключить: «mods can only be applied to pre-created maps» [44]; «currently you cannot apply mods to matches on random maps» [44].

### 1.1 Игровые (gameplay) и визуальные (visual) моды

| | Игровой мод | Визуальный мод |
|---|---|---|
| Что меняет | Состояние игры: характеристики, ресурсы, юниты, победу и поражение | Интерфейс, кнопки, чат, отображение |
| Корень данных | `root` (`root.unitType`, `root.scene[0]`…) [1] | `root.session.visual…`, `root.interface…` [14][26] |
| Может менять игру? | Да | **Нет.** «it is strictly forbidden to modify the data in the root.session.gameplay from a visual mod. it can lead to errors and unsynchronization» [20] |
| Как общаются | Ловит особые команды в `onSpecialCommand` | Отправляет особые команды (раздел 4.7) [26] |

- **Новый тип юнита** надо создавать в обоих модах. Wouw: «The problem is that you created a new unit type in gameplay, but didn't create a new unit type in visual» [42]. Готовый образец пары `gameplay.lua` + `visual.lua` — у IbubussI [15].

### 1.2 Редактор карт и коды
- Карты и моды хранятся на серверах игры.
  - У карты есть код вида `map-xxxxxxxx`.
  - У мода есть ID вида `mod-XXXXXXXXXXX`, например `mod-fBB0HwHlfzd` [10].
  - Чужой готовый мод подключается в редакторе: Modifications → **Add a modification** → вставить ID [10].
- **Наблюдение:** в данных карты WSUS моды записаны с суффиксом, например `"KgbndOUtoob_10"` или `"fIoO5t44ONj_9"` [8]. Скорее всего, суффикс — это версия мода. Это наш вывод.
- Встроенные моды разработчиков настраиваются параметрами в формате `ключ=значение,ключ=значение`. Пример из данных карты: `["KgbndOUtoob_10","res0=1000000,res1=1000000,res2=1000000"]` [8]. С 09.04.2025 параметры задаются через отдельный интерфейс [84].
- Скачанные моды лежат на диске. Их код можно читать как пример: «navigate to `C:\Program Files (x86)\Steam\steamapps\common\War Selection\modsStorage` and look for that mods id» [70].

**Шпаргалка встроенных модов** (публиковал Roman (@4a_yok), 26.04.2023 [75]; подтверждено данными карты WSUS [8]):

| ID | Параметры | Что делает |
|---|---|---|
| `mod-KgbndOUtoob` | `res0=100,res1=250,res2=0` | Стартовые ресурсы |
| `mod-fIoO5t44ONj` | `limit=100` | Лимит населения, % |
| `mod-Rgi6rNgLAmd` | — | Поражение, если нет главного здания |
| `mod-BkorbliOBbj` | `updatePeriod=5000,blockLevels=10,unitTag=7,territorySize=10000` | Границы фракций |
| `mod-osemAL0QGYe` | `waitingTime=180000` | Ожидание переподключения |
| `mod-X6OqsoSYnB2` | (в WSUS: `onlyAllies=false`) | Передача ресурсов союзникам |
| `mod-lFMtjJTcyml` | — | Косметика из магазина |
| `mod-caKgiwj8lh8` | — | Поражение при смерти короля |
| `mod-QmBfycUvwsi` | `timeToWin=100,minWinMoment=100` | Чудо света |
| `mod-4Kdob459gog` | — | Запрет выхода в Чудо |
| `mod-coz0zyLx4Md` | `finalAge=6` | Максимальная эра |

- В данных стандартной карты WSUS есть ещё `IOGEe1vh385_4` и `325s8mFhB5f_3`, у обоих `percent=30000` [8].
  - fojo (@stalinppp) описывает их так: `mod-325s8mFhB5f` — «скорость производства в зданиях (в процентах)», `mod-IOGEe1vh385` — «скорость строительства (в процентах)» [91].
  - Полный список встроенных модов был на `help-mod.warselect.io/doku.php?id=mods_list` [75]. Сейчас сайт недоступен, есть копия в Wayback Machine (раздел 9).

---

## 2. Первый мод за 10 минут

Порядок шагов взят из инструкции сообщества [10] и ответов в Discord [47][48].

1. Откройте **редактор карт** и создайте новую карту или откройте свою.
   - Для запуска карты нужны минимум 2 команды и главное здание у каждой фракции: «Make at least 2 teams, make at least 1 faction for each team, per faction make 1 main-building (altar, elderhouse etc.)» [89].
2. Откройте **Modifications → My modifications** и нажмите **«+»** у игрового мода (gameplay) [10].
3. Дайте моду имя и описание. Код на этом шаге не вводится. Игрок пожаловался: «it just lets me name it and add a description» [90]. Austin ответил: «you need to add your mod to the map, and edit it in the Private match with developer mode» [90].
4. Нажмите на мод → **добавить на карту** → сохраните карту и выйдите [10][47].
5. **Приватный матч → Создать →** выберите свою карту и поставьте галочку **«Enable developer mode in the match»** [10].
   - Режим разработчика работает только на ваших картах: «you can only use dev mode with maps created by you» [48].
6. В матче появятся пункты **Modifications** и **Console** [10]. Откройте Modifications → ваш мод → **Edit script** [10].
7. Вставьте код ниже, сохраните и **перезапустите карту** [10].

**Пример 2.1 — «живучий юнит».** 🟡 Основная строка от Wouw [58], `f_recreateModifiedUnitTypes` по [22], `log` по [38][61].
```lua
-- Меняем здоровье типа юнита 315 (1000 = 1 единица HP, раздел 4.1)
root.unitType[315].deathability.health = 500000   -- Wouw [58]
root.f_recreateModifiedUnitTypes()                -- без этого правка не применится [22]
log(root.unitType[315].deathability.health)       -- [наше] проверка в консоли
```
- **Что должно получиться:** в консоли выводится `500000`, а у юнитов типа 315 становится 500 HP (500000 / 1000, раздел 4.1).
- **ID юнитов** можно узнать так:
  - в файлах локализации `…\War Selection\Cache\project\WarSelection\localization\` [63];
  - на wsunitstats.com: IbubussI (@ibubussi) советует `https://wsunitstats.com/en/unit/180/index` [81].
- **Дальше цикл такой:** правка скрипта → сохранить → перезапустить карту → смотреть консоль [10].
- ⚠️ **Мод выполняется заново при каждом сохранении.** Wouw: «Every time you save the mod it is executed again» [37]. Если в коде на верхнем уровне стоит `f_create()`, каждое сохранение создаёт ещё одну запись.

---

## 3. Отладка

- **Консоль.** В матче с режимом разработчика есть **Console** с ошибками скриптов и выводом `print()` [10][13].
  - С патча 27.01.2025 консоль доступа к данным в режиме разработчика открывается по **F8** [82].
  - Интерфейс логов и ошибок модов улучшен 24.04.2023: «Just run the map in developer mode, and you'll see it» [38].
- **`log(x)` и `print(x)`.** Обе функции встречаются в рабочем коде: `log` в [16][61], `print` в [13]. `log(root)` показывает содержимое движка: Wouw прямо советовал `log(root)` [61].
- **Все параметры события:** `getParameters()`. IbubussI использует его для отладки событий [45]. Этот приём пригодится для событий без документации (разделы 4.8–4.9).
- **Не используйте в рабочем коде `toTable`/`fromTable`:** «Recommendation: don't use toTable and fromTable» [62].
- **Консольные функции** (с обновления после 26.02.2024) [60]:
  - `editorGet("unitType.0.deathability.health")` возвращает сохранённое значение;
  - `editorExecute("unitType.0.deathability.health=100000")` задаёт значение или вызывает функцию.
- **Логи на диске:**
  - Wouw для разбора ошибок просит `gen/log.txt` [39] и `gen/log_prev.txt` [39].
  - Сотрудник alekzander2017 советует закрыть игру и только потом собирать логи, иначе важное не попадёт в `gen.zip` [52].
- **Ошибка, но не вылет.** Wouw: «The engine should not crash under any circumstances. If it goes down, it must be fixed. That's why we ask to report such cases» [42]. О вылетах пишите в #bug-reports.

**Пример 3.1 — разведка API.** 🟡 `log(root)` по [61], `getParameters` по [45].
```lua
log(root)                        -- Wouw [61]: показывает дерево движка
log(root.unitType[315])          -- [наше] углубляемся в конкретный объект

function onSpecialCommand(var)
    log(getParameters())         -- IbubussI [45]: все параметры пришедшего события
end
addMod({ onSpecialCommand = onSpecialCommand })
```

---

## 4. Основы API

### 4.1 Единицы
- **1000 = 1** (HP, урон, ресурс, расстояние). Время — в миллисекундах [11]. Пример: в `starting_resources.lua` стоит `getParameterNumber("res0", …) * 1000` [12].
- **Индексы часто считаются с 0:** «the index of faction 15 is faction number 16» [65].

### 4.2 `root` и хуки `addMod`
- Код на верхнем уровне файла выполняется при загрузке, до старта матча. Это место для правок характеристик [11].
- Остальной код регистрируется через `addMod` [11].

**Пример 4.1 — скелет мода.** 🟡 [11]
```lua
function onInit(var) end                  -- самое раннее: чтение параметров, подготовка
function onStart(var) end                 -- один раз при старте матча
function onTick(var, currentMoment)       -- постоянно; currentMoment в мс
    if currentMoment % 1000 ~= 0 then return end   -- раз в секунду
end
function onSpecialCommand(var) end        -- особые команды (кнопки, интерфейс)
function onPlayerEliminate(var)           -- выбыл игрок
    local playerId = getParameterNumber("player")
end
addMod({ onInit = onInit, onStart = onStart, onTick = onTick,
         onSpecialCommand = onSpecialCommand, onPlayerEliminate = onPlayerEliminate })
```
- **Полный список событий движка** [2]: `init, onStart, onDump, beforeDumpCreate, afterTick, onSpecialCommand, onUnitDeath, onClose, onPlayerEliminate, onResearch, onUnitInZone, onUnitCustomAbility`. Рабочие примеры для `onUnitInZone` и `onUnitDeath` есть в модах из кэша (рецепты 5.12 и 5.13) [95–98]. Для `onResearch` и `onUnitCustomAbility` примеров мы не нашли. В модах кэша встречаются и другие ключи `addMod`: `onDumpStart`, `onDumpCreate`, `onWork`, `onUnitCommand` [95][96][98].
- **Храните состояние в `var`:** «Use the 'var' object, it's always actual» [46]. Локальные переменные между хуками так не передаются: «use var to store a state that needs to be shared across different parts of the mod» [45].
- **`onDump`** срабатывает, когда сессия стартует не с начала: «Reconnect or loading saved game» [69].
- **Старые способы регистрации** `addStartFunction`, `addTickFunction`, `addScriptFunction` встречаются в рабочих модах [11][12][59]. Для нового кода используйте `addMod` [11].
- **Параметры мода, заданные в редакторе** [11]: `getParameterNumber(name, default, min, max)`, `getParameterBool(name, default)`, `getParameter(name)`. `getParameterString` есть в рабочем коде [14].
  - Значения команд приходят строками, числа переводите через `tonumber` [11].

### 4.3 Типы юнитов и `root.f_recreateModifiedUnitTypes()`
- `root.unitType` содержит 423 типа [1].
- Функции контейнера: `f_create([index])`, `f_copy(fromId,toId)`, `f_find(address)`, `f_remove(index)` [1].
- **После правки `root.unitType[...]` вызывайте `root.f_recreateModifiedUnitTypes()`** — функция есть в WSUS [1]. Wouw на вопрос «почему не работает»: «maybe you forgot root.f_recreateModifiedUnitTypes()» [22].
- **Индекс нового элемента берите из `f_create()`**, а не считайте вручную [43]:

**Пример 4.2.** 🟡 [43]
```lua
local newUpgradeId = root.researches.upgrades.f_create()
root.researches.upgrades[newUpgradeId].unit = 32
```

**Пример 4.3 — дальность стрельбы.** 🟡 Пример MGracz (@.mgracz) [57]
```lua
root.unitType[285].attack.weapon[0].distanceMin = 0        -- [наше] подставьте значения
root.unitType[285].attack.weapon[0].distanceMax = 100000
root.unitType[285].attack.weapon[0].distanceStop = 100000
root.f_recreateModifiedUnitTypes()
```

### 4.4 Фракции и игроки
- **`root.faction[n]` — правила фракции** [7]:
  - `build` (планы построек; в WSUS помечено как ссылка на `gameplay.root.build`), `researchState`, `statistics`, `externalData`;
  - функции `f_researchAdd(researchId)`, `f_researchRemove(researchId)`, `f_calcUnitsByTags(tags)`.
- **`root.scene[0].faction[n]` — состояние фракции в матче** [3]: `team`, `treasury` (`resources`, `limits`, `processed`), `supply`, `territorySize`.
- **Вспомогательные функции** из рабочего кода:
  - `forEachControlledFaction(func)` [12];
  - `forEachPlayerLive`, `forEachPlayerFaction` [16];
  - `getPlayerOfFaction` [14];
  - `getFactionOfPlayer` [27].
- **Отношения:**
  - рабочий код: `root.scene[0].relation[p][p1].value = 1/2/3`. По коду Imaginary (@_.op) [27]: 1 = союз, 2 = война, 3 = мир;
  - в WSUS есть `relation.f_set(faction1,faction2,value)`, `f_get`, `f_enemies`, `f_friendly` [3].
- **Выбить игрока:** `root.f_eliminatePlayer(player, reason(0-lose,1-win,2-draw))` [1].

### 4.5 Ресурсы `res0`–`res2`
- «res0 food res1 wood res2 iron res3,4 nothing» [55].
- **Казна фракции:** `root.scene[0].faction[n].treasury.resources[i]`, лимиты в `treasury.limits[i]` [3][12].

### 4.6 Случайные числа: только `root.f_random`
- `root.f_random(limit)` есть в WSUS [1]. Wouw: «f_random is safe (use it) math.random is unsafe (dont use it in gameplay mod)» [21].
- `math.random` в игровом моде даст разный результат у разных игроков, то есть рассинхрон. Это наш вывод из [21].

### 4.7 Особые команды: связь интерфейса и игровой логики
Схема Wouw [26]:
1. Визуальный мод или интерфейс отправляет особую команду.
2. Игровой мод ловит её в `onSpecialCommand`.
3. Игровой мод выполняет действие.
4. Игровой мод сообщает о результате.

**Пример 4.4 — визуальный мод отправляет команду.** 🟡 [26]
```lua
-- Wouw [26]; в другом сообщении тот же вызов записан как root.session.visual.commands.f_specialCommand
root.session_visual_commands.f_specialCommand(0, "command", "Diplomacy",
    "action", currentAction, "player1", currentP1, "player2", currentP2)
```

**Пример 4.5 — игровой мод принимает команду.** 🟡 Код Imaginary (@_.op) [27], `tonumber` по [11]
```lua
function Diplomacy(var)
    if getParameter("command") == "Diplomacy" then
        local player1 = tonumber(getParameter("player1"))   -- tonumber: [11]
        local player2 = tonumber(getParameter("player2"))
        local action  = tonumber(getParameter("action"))
        if action == 1 then          -- союз
            root.scene[0].relation[player1][player2].value = 1
            root.scene[0].relation[player2][player1].value = 1
        end
    end
end
addMod({ onSpecialCommand = Diplomacy })
```

**Пример 4.6 — игровой мод отвечает визуальному.** 🟡 Wouw [26]
```lua
root.f_playerSpecialCommand(player, "command", "peaceDone", "player1", player, "player2", player1)
```
- Функция `f_playerSpecialCommand(player,parameter1,value1[,...])` есть в WSUS [1].
- **Кнопки с выбором места на карте** — интерфейс `placingButtons`.
  - Подключение: `addInterface("placingButtons", "/project/Tools/placingButtons", nil, nil, params)` [14].
  - Клик приходит событием `placerButton` с параметрами `player`, `x`, `y` [14][17].

### 4.8 Зоны (новое в 2026)
- Патч 10.10.2026: «зоны на карте с событиями входа и выхода юнитов» [83].
- **В WSUS** [3]:
  - `root.scene[0].landscape.zones` с функциями `f_addCircle(x,y,radius)`, `f_addRectangle(left,top,right,bottom)`, `f_getInfo(zone)`, `f_getZonesAtPosition(x,y)`, `f_isPositionInZone(zone,x,y)`, `f_list(mapOnly=false)`, `f_updateMap()`;
  - событие `onUnitInZone` [2];
  - у каждого юнита есть флаг `units.list[n].zoneEventEnabled` [3].
- **Рабочий пример есть** в официальном моде «Перетягивание каната» `mod-eMjoqml7Qfb` (версии 27–36) [95].
  - Событие получает `getParameter("zone")` (номер зоны, считается с 0), `getParameter("arrive")` (true при входе, false при выходе) и `getParameter("faction")`.
  - Номер зоны, по всей видимости, совпадает с порядком вызовов `f_addCircle`/`f_addRectangle`. Это наш вывод.
  - См. рецепт 5.12.

### 4.9 Ауры (новое в 2026)
- Анонс, #игровые-обновления, 24.03.2026: «Создана система аур: ауры можно прикреплять к типам юнитов, они дают положительное или отрицательное влияние на характеристики союзных или вражеских юнитов в зоне действия» [73].
- **Контейнер `root.auraTypes`** [4]: `f_create(null/id)`, `f_copy`, `f_remove`, `f_clear`. Поля: `affectsAlly`, `affectsEnemy`, `affectsNeutral`, `research`, `targetsAttack`, `targetsTags`.
- **Цепочка в данных:** `auraTypes[i].research` → `researches.list[r].upgrades[k].id` → `researches.upgrades[id]` = `{parameters, program}` [4][5].
- **6 ванильных аур** сопоставлены с патчноутом 13.08.2026 [74]:

| Аура | Исследование → улучшение | `program`: `parameters` | Цели | Что в игре [74] |
|---|---|---|---|---|
| 0 | 148 → 109 | 0: `mult=140,multRotation=140` | теги {33} | Гнев Дурги: тигры +40% [73] |
| 1 | 149 → 294, 295 | 4: `mult=90` / `turret=-1,mult=90` | `targetsAttack=2` | «Наведение» (радар) |
| 2 | 150 → 296 | 19: `add=100` | теги {24} | «Полевая помощь» (медик), +2 HP/с |
| 3 | 151 → 297 | 0: `mult=140,multRotation=140` | теги {3,15} | «Махуд» (слон): рабочие +40% |
| 4 | 152 → 298 | 19: `add=250` | теги {6,16} | «Плавучий док»: +5 HP/с судам |
| 5 | 153 → 299 | 35: `mult=40`, `affectsEnemy` | теги {14} | «Радиомолчание» (Ямато): обзор вражеской авиации |

- ⚪ **Значения `program` — наш вывод** по совпадению с патчноутом: 0 — скорость движения и поворота, 4 — разброс/точность, 19 — регенерация, 35 — обзор.
- **Неизвестно:** каким полем тип юнита ссылается на ауру и где задаётся радиус. В модах кэша `auraTypes` не используется.
- Улучшения можно создавать и из мода. Официальный мод «Перетягивание каната» создаёт своё исследование и улучшения: `upg.program = 34`, `upg.parameters = "mult=".. (100 + процент)` [95]. Отсюда видно, что `parameters` — записываемая строка, а `mult` задаётся в процентах. То, что program 34 означает урон, — вывод из имён переменных `damageUpgValue` и `upgradeDamagePercent` [95].

### 4.10 Теги урона (новое в 2026)
- Патч 07.08.2026: «В свойствах урона появилось поле исключения целей по тегам: бафф или дебафф можно не применять к выбранным типам целей» и «Тяжёлая техника получила отдельный тег Heavy vehicle» [74].
- Имя поля и номер тега в нашей копии WSUS не найдены: ветка `unitType` в ней не развёрнута. Ищите их через `log(root.unitType[N].attack)`.

---

## 5. Готовые рецепты

> В примерах `[наше]` — подставьте свои ID и значения. После правок `root.unitType` всегда вызывайте `root.f_recreateModifiedUnitTypes()` [22].

### 5.1 Время перехода в следующую эпоху
🟡 Путь дал Wouw [56]; `recreate` по [22]
```lua
root.unitType[10].ability.work[0].makeTime = 30000   -- мс; значение [наше]
root.f_recreateModifiedUnitTypes()
```
- Это ответ Wouw на вопрос о времени перехода в следующую эпоху [56]. Для других культур ID и индекс работы, вероятно, другие. Это наш вывод.

### 5.2 Время исследования или найма
🟡 MGracz (@.mgracz) [57]: «X — identifier of the entity conducting this research… Y — the place where the research is located»
```lua
root.unitType[X].ability.work[Y].makeTime = 5000     -- X, Y, значение [наше]
root.f_recreateModifiedUnitTypes()
```

### 5.3 Время строительства
**Вариант А: глобальная скорость стройки.** 🟡 Встроенный мод `mod-IOGEe1vh385`, версия 5, целиком [100]
```lua
addMod({ onInit = function()
	local percent = getParameterNumber("percent", 100, 1, 50000)
	root.unitsBuildSpeedRatio = percent
end })
```
- Так же устроен мод скорости производства `mod-325s8mFhB5f` (версия 4): там `root.unitsWorkSpeedRatio = percent` [100].
- Оба поля есть в WSUS [1]. В стандартной карте WSUS оба мода подключены с `percent=30000` [8]. Как именно `percent` переводится в скорость, не проверено.

**Вариант Б: стройка конкретным рабочим.** ⚪ Путь от IbubussI (@ibubussi) [25]; умножение — наше
```lua
-- IbubussI [25]: «to change construction time you need to edit a property of a worker»
local b = root.unitType[201].movement.building[24]     -- 201 = рабочий, 24 = постройка (из примера [25])
b.tickProgress = b.tickProgress * 2                    -- [наше] предположение: больше = быстрее
b.tickProgressTerritory = b.tickProgressTerritory * 2
root.f_recreateModifiedUnitTypes()
```

### 5.4 Лимит построек
🟡 Wouw [23]
```lua
local factions = root.faction
for factionId = 0, factions.size - 1 do
    factions[factionId].build[102].requirements.unit[2].max = 3
end
```
- Поля `requirements` (`researchAll`, `researchAny`, `unit`, `unitsAll`) есть в WSUS [6].

### 5.5 Перенастройка панели строительства (`buildReconfigure`)
🟡 Wouw [24]. Это не код, а строка параметра для встроенного мода интерфейса `mod-wFs1okaN4Ng`:
```
buildReconfigure="[[1,7,10],[3,9,25]]"
```
- Формат: `[культура, кнопка, номер постройки]`. «for culture 1 (stone age) on the build button 7 will be set to build number 10» [24].
- Если интерфейс сессии создаёт ваш собственный мод, добавьте этот параметр в него [24].

### 5.6 Стартовые ресурсы для всех
🟡 Мод `starting_resources.lua` [12]
```lua
initResourcesA = {
    getParameterNumber("res0", 100, 0, 1000000) * 1000,
    getParameterNumber("res1", 250, 0, 1000000) * 1000,
    getParameterNumber("res2", 0, 0, 1000000) * 1000,
    getParameterNumber("res3", 0, 0, 1000000) * 1000,
    getParameterNumber("res4", 0, 0, 1000000) * 1000
}
function initOnStartResourcesInit()
    local factions = root.scene[0].faction
    local function func(factionId)
        local treasury = factions[factionId].treasury
        for i = 0, 4 do
            treasury.limits[i] = 4000000000
            treasury.resources[i] = initResourcesA[i + 1]
        end
    end
    forEachControlledFaction(func)
end
addStartFunction(initOnStartResourcesInit, "initOnStartResourcesInit")
```
- Без кода то же делает встроенный `mod-KgbndOUtoob` [75].

### 5.7 Выдать ресурсы одному игроку
🟡 Встроенный мод передачи ресурсов `mod-X6OqsoSYnB2`, версия 16, строки 46–59 (сокращено) [99]
```lua
local factions = root.scene[0].faction
local resFrom = factions[data.fromFaction].treasury_resources
local resTo = factions[data.toFaction].treasury_resources
resFrom[0] = resFrom[0] - data.r0
resTo[0] = resTo[0] + math.floor(data.r0 * data.percent // 100)
-- ... то же для индексов 1–4
```
Минимальный вариант для одного игрока. ⚪ Собран по образцу [99], `getFactionOfPlayer` по [27]
```lua
function onStart(var)
    local faction = getFactionOfPlayer(0)                         -- игрок 0 [наше]
    local res = root.scene[0].faction[faction].treasury_resources
    res[1] = res[1] + 5000 * 1000                                 -- +5000 дерева (res1 [55])
end
addMod({ onStart = onStart })
```
- У fojo (@stalinppp) был рабочий мод, выдающий ресурсы конкретному игроку. Код он не публиковал [72].

### 5.8 Создать юнитов по клику на карте
🟡 Imaginary (@_.op): «thats actually working» [17]. Кнопку `placingButtons` должен добавить визуальный мод, см. 5.9 [14].
```lua
function onSpecialCommand()
    if (getParameter("command") == "placerButton") then
        root.scene_0.units.f_create(11, 1, getFactionOfPlayer(getParameter("player")),
                                    getParameter("x"), getParameter("y"), 0)
    end
end
addMod({ onSpecialCommand = onSpecialCommand })
```
- Полная сигнатура: `units.f_create(typeId,number,faction,x,y,direction,addPlacingSize=0,…)` [3].
- Старая `createUnits` удалена: «Now we've finally removed it» [64].

### 5.9 Передача выбранных юнитов союзнику («Sending Units»)
Визуальная часть — 🟡 файл мода `mod-MHTHlA4F9Zb`, автор IbubussI [14] (сокращено):
```lua
function onInit()
    local params = { "x", 30, "y", 70, "horizontalAlign", 0, "verticalAlign", 0, "text1", "SEND" }
    addInterface("placingButtons", "/project/Tools/placingButtons", nil, nil, params)
end
function onSpecialCommand()
    if getParameter("command") ~= "placerButton" then return end
    if getParameter("player") ~= getPlayerOfFaction(root.session.visual.currentFaction) then return end
    local vSession = root.session.visual
    local selected = vSession.scene[0].selection.units.list
    local selection = {}
    for i = 0, selected.size - 1 do selection[i + 1] = selected[i].id end
    vSession.commands.f_specialCommand(0, "command", "share_selected_units", "selection", toJson(selection),
        "x", getParameter("x"), "y", getParameter("y"), "player", getParameter("player"))
end
addMod({ onInit = onInit, onSpecialCommand = onSpecialCommand })
```
Игровая часть — ⚪. Это **наша** реконструкция: оригинального `mod-1hKmUgkzMZk` нет ни в Discord, ни в кэше модов. `f_changeFaction` в кэше не встречается ни разу [95–102]. Функции взяты из WSUS [3].
```lua
function onSpecialCommand(var)
    if getParameter("command") ~= "share_selected_units" then return end
    local ids    = fromJson(getParameter("selection"))
    local x, y   = tonumber(getParameter("x")), tonumber(getParameter("y"))
    local from   = getFactionOfPlayer(tonumber(getParameter("player")))
    local target = root.scene[0].landscape.f_getFaction(x, y)          -- чья территория под кликом
    local units  = root.scene[0].units
    for _, id in ipairs(ids) do
        if units.list[id].faction == from and target ~= from then
            units.operation.f_changeFaction(id, target)
        end
    end
end
addMod({ onSpecialCommand = onSpecialCommand })
```
- ⚠️ «every unit has 2 id. Base id and instance id» [92]. Совпадает ли `selection…id` с индексом `units.list`, не проверено.

### 5.10 Сообщение в чат из игрового мода
🟡 firco7 (@firco7) [59]
```lua
function say(msg)
    local str = "World: " .. msg
    root.f_playerSpecialCommand(0, "command", "chat", "text", str, "destination", "all", "font", "Neucha-Regular")
end
```
- Визуальный вариант (системное сообщение), Wouw [26]:
```lua
-- 🟡 Wouw [26]. В WSUS v258.4018 у root.interface есть f_sendEvent(name,data) [9]; вызов через .chat — как у Wouw
local data = { player = 0, system = true, text = "alert!", font = "Roboto-Medium" }
root.interface.chat.f_sendEvent("chatMessage", toJson(data))
```

### 5.11 Мгновенно выдать исследование
🟡 Мод `mod-tZJ6M1Yrbn2`, версия 21, строки 129–133 [101]
```lua
local reses = root.researches_list_size
local fac2 = root.faction[2]
fac2.f_researchAdd(reses - 1)
fac2.f_researchAdd(reses - 2)
-- ...
```
- В том же моде есть `root.faction[2].f_researchRemove(...)` [101]. Функции есть и в WSUS [7].
- Там же видно, что `units.f_create(...)` возвращает список ID новых юнитов: `local ids = units.f_create(type, 5, 3, x + 10000, y, 0)`, затем `for _, id in ipairs(ids)` [101].

### 5.12 Зона и событие входа или выхода
**Создание зон.** 🟡 Официальный мод «Перетягивание каната» `mod-eMjoqml7Qfb`, версия 36, строки 1327–1336 (сокращено) [95]
```lua
function initZones()
	local landscape = root.scene[0].landscape
	local zones = landscape.zones
	local szx = landscape.size_x
	local szy = landscape.size_y
	local mid = szx // 2
	zones.f_addRectangle(0, 0, mid - 50000, szy)
	zones.f_addRectangle(mid + 50000, 0, szx, szy)
end
```
Круглые зоны вокруг стартовых позиций. 🟡 Мод `mod-7l4c6qjN5B9`, версия 31, строки 778–784 и 800–801 [96]
```lua
function createBuildingZones(startPositions)
	local zones = root.scene[0].landscape_zones
	for _, pos in ipairs(startPositions) do
		zones.f_addCircle(pos.x, pos.y, 1000000)
	end
	zones.f_updateMap()
end
-- в onStart:
local startPositions = fromJson(root.dataStorage.startPositions)
createBuildingZones(startPositions)
```
**Событие.** 🟡 `mod-eMjoqml7Qfb`, версия 36, строки 1545–1550 и 1562–1563 (то же в версиях 27, 29, 30, 35) [95]
```lua
function onUnitInZone(var)
	local zone = getParameter("zone") + 1      -- номер зоны с 0
	if zone > 2 then return end
	local arrive = getParameter("arrive")      -- true = вошёл, false = вышел
	local factionId = getParameter("faction")
	-- ...
	local add = -1
	if arrive then add = 1 end
end
addMod({ onStart = onStart, onUnitInZone = onUnitInZone })   -- в оригинале + onInit, onTick и др.
```
- Создавать ли зоны в `onStart` или `onInit`: у `7l4c6qjN5B9` это `onStart` [96], у `eMjoqml7Qfb` — функция `initZones()`, место вызова мы не смотрели [95].
- Флаг `units.list[n].zoneEventEnabled` есть в WSUS [3]. В модах кэша он не используется.

### 5.13 Событие смерти юнита
🟡 Мод `mod-98vr2B6ccl1`, версия 10, строки 664–669 [97]
```lua
function onUnitDeath(var)
	local ok, err = pcall(function()
		local deadId = tonumber(getParameter("unitId"))
		local deadType = tonumber(getParameter("unitType"))
		local killerId = tonumber(getParameter("killerId"))
		local killerFaction = tonumber(getParameter("killerFaction"))
		-- ...
	end)
end
```
🟡 Мод `mod-7l4c6qjN5B9`, версия 31, строки 872–878 и 882 [96]
```lua
function onUnitDeathMain()
	if root.unitType[getParameter("unitType")].movement_enabled then return end   -- только здания
	local factionId = getParameter("faction")
	-- ...
end
addMod({ onInit = onInit, onUnitDeath = onUnitDeathMain, onStart = initOnStartMain })   -- сокращено
```
- **Известные параметры:** `unitId`, `unitType`, `faction` (фракция погибшего), `killerId`, `killerFaction` [96][97].
- Ещё один пример — учебный мод `mod-2ls0S3tKDXf`, версия 26: `getParameter("unitType")` сравнивается с ID животных [98].
- Обёртка `pcall` в [97] страхует от падения всего мода при ошибке.

### 5.14 Усилить ауру «Полевая помощь»
⚪ Наш вывод из [4][5][74]. Что `upgrade.parameters` можно записывать, видно по официальному моду [95]. Влияние на ауру не проверено
```lua
log(root.auraTypes[2])                  -- affectsAlly, research=150, targetsTags {24}
log(root.researches.upgrades[296])      -- parameters "add=100", program 19
root.researches.upgrades[296].parameters = "add=200"   -- [наше] ожидаем ~4 HP/с вместо 2
root.f_recreateModifiedUnitTypes()      -- нужно ли здесь — неизвестно
```

### 5.15 Изменить стоимость постройки — ЭКСПЕРИМЕНТ
⚪ Поля есть в WSUS [6], но **у нескольких игроков правка `buildCost`/`initCost` не сработала**: `root.build[9].initCost[2]=…` «dont work» [93]; `root.build[112].initCost` и `root.scene[0].faction[…].build[112].buildCost` «does not work» [94]. Вариант через `root.faction[n]`, как в 5.4, в Discord не проверяли.
- В модах кэша `initCost` только **читают**: `gameplay.build[ruleId].initCost` в `mod-HcFggfH8NV0`, версия 26 [102]. Значит, на движке 264 поле называется `initCost`, хотя в `Cache/Projects/WarSelection/gameplay.json` оно записано как `costInit`/`costBuilding`.
- Рабочего примера изменения стоимости нет.
```lua
for factionId = 0, root.faction.size - 1 do
    root.faction[factionId].build[10].buildCost[1] = 100000   -- 100 дерева [наше]
end
log(root.faction[0].build[10].buildCost[1])
```

### 5.16 Бафф одному юниту
🟡 Wouw [68]. **Переименование:** в WSUS v258.4018 функция называется `units.list[n].f_addBuff(researchId, finishTime)` [3].
```lua
root.scene[0].units.list[unitId].addBuff(researchId, 10000000)   -- как у Wouw (2024)
-- root.scene[0].units.list[unitId].f_addBuff(researchId, 10000000)  -- имя в v258.4018 [3]
```

### 5.17 Своё исследование с улучшением урона
🟡 Официальный мод «Перетягивание каната» `mod-eMjoqml7Qfb`, версия 36, строки 1571–1608 (сокращено) [95]
```lua
local upgs = root.researches_upgrades
local rese = root.researches_list
damageResearchId = rese.f_create()
local res = rese[damageResearchId]
local researchUpgs = res.upgrades
res.quantity = 10000
local uMain = upgs.f_create()
local upg = upgs[uMain]
upg.unit = unitId
upg.program = 34
upg.parameters = "mult=" .. damageUpgValue        -- damageUpgValue = 100 + upgradeDamagePercent
researchUpgs[researchUpgs.f_create()].id = uMain
```
- То же самое для турелей: `upg.parameters = "turret=-1,mult=" .. damageUpgValue` [95].

---

## 6. Частые ошибки

1. **Забыли `root.f_recreateModifiedUnitTypes()`** после правки типов [22].
2. **Меняют игру из визуального мода** — будет рассинхрон [20].
3. **Создали игровой тип юнита без визуального** [42].
4. **Посчитали индекс нового элемента вручную**, а не взяли из `f_create()` [43].
5. **`f_create()` на верхнем уровне** при каждом сохранении плодит пустые записи [37].
6. **`math.random` вместо `root.f_random`** [21].
7. **Код от нейросети с выдуманными функциями.** Wouw о таком «моде»: «completely inconsistent with the engine's mod system» [40]. Каждое имя сверяйте с WSUS [1].
8. **Устаревшие моды на карте.** «All connected mods are updated to the latest version» [65].
9. **Интерфейс сессии создан дважды:** «Find and remove one of the mods that create this interface» [54].
10. **`math.atan2` недоступна в модах** [66].
11. **Тяжёлая работа каждый тик.** Ограничивайте частоту через `% 1000` [11]. Моды, которые каждую секунду сканируют юнитов, дают лаги [67].
12. **Старые рецепты из чатов.** Например, `mods/special/supplyInit.lua` с `supply=512` «На новой версии не работает» [76]. Устаревший способ правки моды тоже ломает: fojo (@stalinppp) жаловался, что игра выдаёт ошибки, «as if the game's byte code is cached» [72].

---

## 7. Текущие баги редактора и обходы

Состояние на сентябрь–октябрь 2026:
- Не сохраняются новые карты: «map editor can't save new maps» [86].
- Вылет при входе на карту с включённым режимом разработчика [87].
- Добавление нового мода ломает карту: «Can't even open the map in the editor» [88].

**Обход 1 — предыдущий билд через бету Steam.**
- «Looks like the map editor still works on the previous build. Reverted to the last build, made the map + saved it then changed back to the new version. works fine» [50].
- Ещё один игрок: «fixed by downgrading game version» [51].
- Путь: Steam → свойства War Selection → бета-версии → предыдущий билд. Конкретный путь в меню в источниках не описан. Это общая функция Steam.

**Обход 2 — старый билд через консоль Steam** [49]. Скачайте и контент, и движок. 🟡 Команды Astator [49]:
```
download_depot 1022450 1022451 610954136867462537
download_depot 1022450 1022452 4732527871803438524
```
- «Make sure you uses the console to update both the content and the corresponding OS-specific engine» [49]. Номера манифестов берут на steamdb.info [49].
- Как открыть консоль Steam и куда складываются скачанные файлы, в наших источниках не описано.

**После отката:** сделайте и сохраните карту, затем вернитесь на текущую версию [50]. Если что-то упало, закройте игру и только потом соберите `gen.zip` [52].

---

## 8. Правила: что можно и за что банят

**Банят за:**
- **Доступ к платному контенту:**
  - «providing access to paid content may result in a ban» [32];
  - об открытии платных стран: «if we find it being used, we will ban for it. Just a month ago I banned about 20 accounts» [31];
  - «все нации» на ивентах — «Это не мод, а специальный аккаунт… единственный законный способ запустить такую игру» [77].
- **Свой код в файлах обычных режимов:** «Yes, this is cheating. If you continue to do this, your account will be banned» [34].
- **Правку файлов модов в обход редактора.** Можно задеть релизный файл вместо черновика: «will result in the user being kicked out of matches and further banned for cheating» [33].
- **Чит-моды в сетевой игре:** например, снятие тумана войны. «using such a mod in multiplayer games will trigger the cheat detection system and your account could be banned» [35].

**Можно:** патчить игру (например, переводы), если это «doesn't interfere with revenue from game sales, doesn't violate laws, doesn't interfere with game marketing, and generally doesn't cause harm» [36].

**Ассеты (модели, текстуры, звуки):**
- «The game does not support modding of assets» [28]. «game modifications do not allow you to replace assets. However… you can try making your own game on the War Selection engine» [29].
- Формат моделей закрытый, но «we provide utilities, instructions and support for model conversion tasks. You can distribute such an asset, but you cannot make a universal mod with your own asset» [30].

**Локальная замена файлов (озвучки):**
- Русские озвучки распространяют архивами, которые копируют в папку игры. Пример — пак KlimA™ [78].
- Такая замена видна только вам. После обновлений её надо повторять: «Если озвучка слетает, то файлы нужно заменить по новой, это может быть связано с обновлениями игры» [78].
- ⚠️ Наш вывод: не подменяйте так Lua-скрипты режимов, это подпадает под [34].

---

## 9. Где спрашивать, готовые моды, ссылки

**Где спрашивать:**
- Английский Discord War Selection: #new-mod-creation (там отвечает Wouw), #existing-mods-customize-help, #editor-chat, форум #mod-collection, #bug-reports (сбои).
- Русский сервер «War Selection – СНГ»: #мод-творчество, #креативный-чат.
- Wouw просит присылать **текст** кода и `gen/log.txt`, а не скриншоты [39].
- Русского гайда по моддингу до этого документа не было (см. `discord-findings.md` §13.7).

**Готовые моды и коды:**

| Мод | ID | Источник |
|---|---|---|
| Sending Units (IbubussI) | gameplay `mod-1hKmUgkzMZk`, visual `mod-MHTHlA4F9Zb` | [14] |
| UI-библиотека (alekzander2017), демо-тетрис | `LLpBr4R6K0g`, `pcroaXCYGV5` | [71] |
| Дипломатия (fojo) | `mod-P1ZHNbwTYBh mod-0xwmpTvt3B4 mod-LLpBr4R6K0g` | [79] |
| Максимальная эра (встроенный) | `mod-coz0zyLx4Md` (`finalAge=`) | [75][80] |
| Перенастройка панели постройки | `mod-wFs1okaN4Ng` | [24] |
| Общая казна команды (IbubussI) | файл `WS_SharedResources.lua` | [16] |

**Ссылки:**
- Дерево API (главный справочник): `https://wsunitstats.com/en/modding` [1]. Официального полного описания нет: «There is no description of all functions of the engine» [41].
- Репозиторий сообщества AdrienRmd/War_Selection_Modding (MIT): `https://github.com/AdrienRmd/War_Selection_Modding` [10][11].
- Старая вики разработчиков: `help-mod.warselect.io` (сейчас недоступна), архив: `http://web.archive.org/web/20260130141349/https://help-mod.warselect.io/doku.php` [75].
- Справочник юнитов: `https://wsunitstats.com/en/units` [81].

---

## Источники

**WSUS (дерево API, игра 258.4018, снято 10.10.2026; локальная копия `discord/ext/wsus/`)**
1. `home.json` — `gameplay.root`: `f_random`, `f_recreateModifiedUnitTypes`, `f_playerSpecialCommand`, `f_eliminatePlayer`, `unitType`, `version=4018`; `visual.root.buildNumber=12097`.
2. `gameplay.root.scripts.json` — список событий движка.
3. `gameplay.root.scene.json` — `units.f_create`, `units.list[n]` (`faction`, `zoneEventEnabled`, `f_addBuff`), `units.operation.f_changeFaction`, `landscape.f_getFaction`, `landscape.zones.*`, `relation.*`, `faction[n].treasury`.
4. `gameplay.root.auraTypes.json` — 6 аур и их поля.
5. `gameplay.root.researches.json` — `list[148–153]`, `upgrades[109, 294–299]`.
6. `gameplay.root.build.json` — `build[n]`: `available`, `buildCost`, `initCost`, `requirements`, `unit`.
7. `gameplay.root.faction.json` — `f_researchAdd`, `f_researchRemove`, `f_calcUnitsByTags`, `build`.
8. `gameplay.root.dataStorage.json` — `mapData` (`modsG`/`modsV` стандартной карты с параметрами).
9. `visual.root.interface.json` — `f_sendEvent(name,data)`.

**Репозиторий AdrienRmd/War_Selection_Modding (локально `discord/ext/wsm/`)**

10. `docs/modding-guide/installation.md`.
11. `docs/modding-guide/lifecycle-and-events.md`.
12. `mods/starting_resources/starting_resources.lua`.
13. `docs/modding-guide/lua-basics.md` (`print()` в консоль).

**Файлы модов из Discord (локально `discord/ext/att/`)**

14. `MHTHlA4F9Zb_9-…lua` — визуальная часть Sending Units [EN #new-mod-creation, IbubussI (@ibubussi), 31.12.2024].
15. `gameplay.lua` / `visual.lua` — образец нового юнита [EN #new-mod-creation, IbubussI (@ibubussi), 12.12.2023].
16. `WS_SharedResources.lua` [EN #existing-mods-customize-help, IbubussI (@ibubussi), 07.09.2024].
17. [EN #new-mod-creation, Imaginary (@_.op), 23.04.2024] — код `placerButton` → `f_create`, «thats actually working».

**Discord: английский сервер (EN)**

20. [EN #existing-mods-customize-help, Wouw (@.wouw), 22.04.2023] «strictly forbidden to modify… root.session.gameplay from a visual mod».
21. [EN #new-mod-creation, Wouw (@.wouw), 19.01.2024] «f_random is safe… math.random is unsafe».
22. [EN #new-mod-creation, Wouw (@.wouw), 08.10.2023] «maybe you forgot root.f_recreateModifiedUnitTypes()».
23. [EN #new-mod-creation, Wouw (@.wouw), 28.05.2025] цикл `requirements.unit[2].max = 3`.
24. [EN #new-mod-creation, Wouw (@.wouw), 23.02.2025] `buildReconfigure`, `mod-wFs1okaN4Ng`.
25. [EN #new-mod-creation, IbubussI (@ibubussi), 21.07.2026] `movement.building[24].tickProgress`.
26. [EN #new-mod-creation, Wouw (@.wouw), 30.01.2024] схема особых команд, `f_specialCommand`, `f_playerSpecialCommand`, `interface.chat.f_sendEvent`.
27. [EN #new-mod-creation, Imaginary (@_.op), 30.01.2024] обработчик `Diplomacy`, `relation[...].value`, `getFactionOfPlayer`.
28. [EN #new-mod-creation, Wouw (@.wouw), 28.06.2024] «The game does not support modding of assets».
29. [EN #new-mod-creation, Wouw (@.wouw), 15.12.2025] ассеты нельзя заменить, «own game on the War Selection engine».
30. [EN #new-mod-creation, Wouw (@.wouw), 30.09.2024] формат моделей, утилиты конвертации.
31. [EN #new-mod-creation, Wouw (@.wouw), 08.04.2025] «banned about 20 accounts».
32. [EN #new-mod-creation, Wouw (@.wouw), 20.06.2025] «providing access to paid content may result in a ban».
33. [EN #existing-mods-customize-help, Wouw (@.wouw), 30.07.2023] правка файлов в обход редактора.
34. [EN #new-mod-creation, Wouw (@.wouw), 17.09.2024] «Yes, this is cheating…» (свой код в Lua-файлах командного режима).
35. [EN #existing-mods-customize-help, Wouw (@.wouw), 05.07.2023] чит-моды в сетевой игре.
36. [EN #new-mod-creation, Wouw (@.wouw), 23.02.2025] когда патчинг не банят.
37. [EN #new-mod-creation, Wouw (@.wouw), 19.09.2023] «Every time you save the mod it is executed again».
38. [EN #existing-mods-customize-help, Wouw (@.wouw), 24.04.2023] логи и ошибки модов в режиме разработчика.
39. [EN #new-mod-creation, Wouw (@.wouw), 18.09.2023 и 12.02.2025] `gen/log.txt`, `gen/log_prev.txt`.
40. [EN #new-mod-creation, Wouw (@.wouw), 08.06.2025] «completely inconsistent with the engine's mod system».
41. [EN #new-mod-creation, Wouw (@.wouw), 30.09.2024] «There is no description of all functions of the engine».
42. [EN #new-mod-creation, Wouw (@.wouw), 11.02.2025] нужен визуальный тип; «The engine should not crash…».
43. [EN #new-mod-creation, Wouw (@.wouw), 27.08.2023] `newUpgradeId = …f_create()`.
44. [EN #existing-mods-customize-help, Wouw (@.wouw), 19.01.2024 и 05.08.2024] моды только на созданных картах.
45. [EN #new-mod-creation, IbubussI (@ibubussi), 11.02.2025] `var`, `getParameters()`.
46. [EN #new-mod-creation, Wouw (@.wouw), 29.12.2023] «Use the 'var' object, it's always actual».
47. [EN #editor-chat, Austin (@_austinliu), 14.06.2026] порядок: мод → карта → приватный матч в режиме разработчика.
48. [EN #existing-mods-customize-help, Chenxi (@chenxi008), 20.02.2026] «you can only use dev mode with maps created by you».
49. [EN #public-help, Astator (@astator), 17.10.2026] `download_depot`.
50. [EN #editor-chat, JohnMcCain (@johnmccain1936), 12.09.2026] откат на предыдущий билд.
51. [EN #public-help, ShanTri (@shantri_), 04.10.2026] «fixed by downgrading game version».
52. [EN #bug-reports, alekzander2017, 26.08.2025] сначала закрыть игру, потом собирать `gen.zip`.
53. [EN #new-mod-creation, Wouw (@.wouw), 26.12.2023] три этапа устаревания функций.
54. [EN #new-mod-creation, Wouw (@.wouw), 13.06.2025] интерфейс сессии дважды.
55. [EN #editor-chat, Pagoda (@_htop), 12.06.2024] «res0 food res1 wood res2 iron res3,4 nothing».
56. [EN #new-mod-creation, Wouw (@.wouw), 29.04.2024] `root.unitType[10].ability.work[0].makeTime`.
57. [EN #new-mod-creation, MGracz (@.mgracz), 01.05.2024] `distanceMin/Max/Stop`; `makeTime` X/Y.
58. [EN #new-mod-creation, Wouw (@.wouw), 29.09.2023] `root.unitType[315].deathability.health = 500000`.
59. [EN #new-mod-creation, firco7 (@firco7), 04.01.2024] функция `say()` через `f_playerSpecialCommand`.
60. [EN #new-mod-creation, Wouw (@.wouw), 26.02.2024] `editorGet` / `editorExecute`.
61. [EN #new-mod-creation, Wouw (@.wouw), 29.01.2024] `log(root)`.
62. [EN #new-mod-creation, Wouw (@.wouw), 21.03.2025] «don't use toTable and fromTable».
63. [EN #new-mod-creation, Wouw (@.wouw), 02.09.2025] путь к файлам локализации.
64. [EN #new-mod-creation, Wouw (@.wouw), 06.10.2023] `createUnits` удалена.
65. [EN #existing-mods-customize-help, Wouw (@.wouw), 25.04.2023] обновлять моды; индексы с 0.
66. [EN #bug-reports, Chenxi (@chenxi008), 28.11.2025] «Cant use lua math.atan2 function in mods».
67. [EN #public-help, Austin (@_austinliu), 15.08.2026] лаги от модов, сканирующих юнитов.
68. [EN #new-mod-creation, Wouw (@.wouw), 17.11.2024] `units.list[unitId].addBuff(researchId, 10000000)`.
69. [EN #new-mod-creation, Wouw (@.wouw), 23.12.2023] «onDump runs when session starts not from beginning».
70. [EN #new-mod-creation, Pagoda (@_htop), 16.11.2024] папка `modsStorage`.
71. [EN #new-mod-creation, alekzander2017, 08.09.2023] UI-мод `LLpBr4R6K0g`, тетрис `pcroaXCYGV5`.
72. [EN #new-mod-creation, fojo (@stalinppp), 10.07.2026] мод ресурсов для одного игрока; «byte code is cached».

**Discord: русский сервер «War Selection – СНГ»**

73. [СНГ #игровые-обновления, Менталист (@avanturist01), 24.03.2026] система аур; Гнев Дурги +40%.
74. [СНГ #блог-разработчиков, Менталист (@avanturist01), 07.08.2026 и 13.08.2026] теги урона, Heavy vehicle; ауры «Махуд», «Наведение», «Полевая помощь», «Плавучий док», «Радиомолчание».
75. [СНГ #креативный-чат, Roman (@4a_yok), 26.04.2023] коды встроенных модов, ссылка на mods_list.
76. [СНГ #креативный-чат, Roman (@4a_yok), 17.04.2023] `supplyInit.lua` «На новой версии не работает».
77. [СНГ #мод-творчество, IbubussI (@ibubussi), 17.10.2026] «Это не мод, а специальный аккаунт…».
78. [СНГ #мод-творчество, KlimA™ (@klima_tm), 26.07.2025] озвучка, «файлы нужно заменить по новой».
79. [СНГ #мод-творчество, fojo (@stalinppp), 25.09.2025] дипломатия, новая версия.
80. [СНГ #креативный-чат, fojo (@stalinppp), 16.04.2026] «специальный мод и вводишь там какой век максимальный».
81. [СНГ #креативный-чат, IbubussI (@ibubussi), 28.07.2023] где брать ID юнитов, wsunitstats.

**Патчноуты Steam** (лента `https://steamcommunity.com/app/1022450/announcements/`, сводка в `research.md` §2.2)

82. 27.01.2025 — консоль в режиме разработчика по F8.
83. 10.10.2026 («Automatic Gates…») — зоны с событиями входа и выхода юнитов.
84. 09.04.2025 — параметры модов через отдельный интерфейс, `f_copy` в контейнерах.

**Discord: баги 2026 (EN)**

86. [EN #bug-reports, Austin (@_austinliu), 18.09.2026] «map editor can't save new maps» (также #editor-chat, JohnMcCain (@johnmccain1936), 11.09.2026).
87. [EN #bug-reports, Austin (@_austinliu), 22.09.2026] «The game crashes after entering the map with Developer Mode enabled».
88. [EN #bug-reports, Austin (@_austinliu), 29.09.2026] новый мод ломает карту.

**Discord: дополнительные**

89. [EN #editor-chat, firco7 (@firco7), 15.06.2023] минимум для запуска карты.
90. [EN #new-mod-creation, Zyro (@zyromate), 25.06.2026; ответ Austin (@_austinliu), 27.06.2026] мод создаётся без кода, код редактируется в приватном матче.
91. [СНГ #мод-творчество, fojo (@stalinppp), 20.05.2026] `mod-325s8mFhB5f`, `mod-IOGEe1vh385`.
92. [EN #new-mod-creation, Wouw (@.wouw), 19.01.2024] «every unit has 2 id. Base id and instance id».
93. [EN #new-mod-creation, Matim (@matim14pk), 16.08.2023] `initCost` не работает.
94. [EN #new-mod-creation, l66b (@l66b), 21.07.2026 и 24.07.2026] `initCost`/`buildCost` «does not work».

**Кэш модов на ПК автора** (`modsStorage`, движок 264, прочитано 18.10.2026; автор мода указан, только если известен)

95. `eMjoqml7Qfb_36-…lua` — официальный мод «Перетягивание каната» (`mod-eMjoqml7Qfb` в списке модов разработчиков, см. `research.md` §2.3): `initZones` (стр. 1327–1351), `onUnitInZone` (стр. 1545–1566; так же в версиях 27, 29, 30, 35), исследование с улучшениями (стр. 1571–1608), `addMod` (стр. 1616).
96. `7l4c6qjN5B9_31-…lua` — `createBuildingZones` (стр. 778–784), вызов в `onStart` (стр. 800–801), `onUnitDeathMain` (стр. 872–878), `addMod` (стр. 882); `treasury_resources` (стр. 244 и др.).
97. `98vr2B6ccl1_10-…lua` — `onUnitDeath` с параметрами `unitId`, `unitType`, `killerId`, `killerFaction` (стр. 664–669).
98. `2ls0S3tKDXf_26-…lua` — учебный мод: `onUnitDeath` и `getParameter("unitType")` (стр. 31–32), `addMod` с `onWork` и `onUnitCommand` (стр. 325).
99. `X6OqsoSYnB2_16-…lua` — встроенный мод передачи ресурсов: списание и зачисление через `treasury_resources` (стр. 46–59).
100. `IOGEe1vh385_5-…lua` (`root.unitsBuildSpeedRatio`) и `325s8mFhB5f_4-…lua` (`root.unitsWorkSpeedRatio`) — встроенные моды скорости стройки и производства (по 4 строки).
101. `tZJ6M1Yrbn2_21-…lua` — `units.f_create` → список ID (стр. 122–126), `f_researchAdd` (стр. 129–139), `f_researchRemove` (стр. 188).
102. `HcFggfH8NV0_26-…lua` — чтение `gameplay.build[ruleId].initCost` (стр. 159–171).
