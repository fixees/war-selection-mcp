"""Starter templates built only from recipes marked as taken from working mods or developer messages
in guide-ru.md. Placeholders: {{name}}."""

from __future__ import annotations

TEMPLATES: dict[str, dict] = {
    "blank_gameplay": {
        "description": "Gameplay mod skeleton with the standard addMod hooks.",
        "defaults": {},
        "sources": ["guide-ru.md 4.2, example 4.1 (community instruction [11])"],
        "files": [{"kind": "gameplay", "name": "gameplay.lua", "code": """\
-- Gameplay mod skeleton. Source: guide-ru.md 4.2, example 4.1.
-- Top-level code runs when the mod loads (and again on every save in the editor).

function onInit(var)
    -- earliest hook: read parameters, prepare state in var
end

function onStart(var)
    -- once at match start
end

function onTick(var, currentMoment)
    if currentMoment % 1000 ~= 0 then return end   -- once per second; currentMoment is in ms
end

function onSpecialCommand(var)
    -- commands from interfaces / visual mods: getParameter("command")
end

function onPlayerEliminate(var)
    local playerId = getParameterNumber("player")
end

addMod({ onInit = onInit, onStart = onStart, onTick = onTick,
         onSpecialCommand = onSpecialCommand, onPlayerEliminate = onPlayerEliminate })
"""}],
    },
    "blank_visual": {
        "description": "Visual mod skeleton (UI side). Must not change game state.",
        "defaults": {},
        "sources": ["guide-ru.md 5.9, visual part of mod-MHTHlA4F9Zb by IbubussI [14]", "guide-ru.md 6.2"],
        "files": [{"kind": "visual", "name": "visual.lua", "code": """\
-- Visual mod skeleton. Structure follows guide-ru.md 5.9 (mod-MHTHlA4F9Zb).
-- Visual mods run per client: never change game state here (desync, guide 6.2).
-- To act on the game, send a special command and handle it in a gameplay mod.

function onInit()
    -- add interfaces here, e.g. addInterface("placingButtons", "/project/Tools/placingButtons", nil, nil, params)
end

function onSpecialCommand()
    -- getParameter("command")
end

addMod({ onInit = onInit, onSpecialCommand = onSpecialCommand })
"""}],
    },
    "zone_trigger": {
        "description": "Circular zones around start positions and an onUnitInZone handler.",
        "defaults": {"radius": "1000000"},
        "sources": ["guide-ru.md 5.12: mod-7l4c6qjN5B9 v31 lines 778-784, 800-801 [96]",
                    "guide-ru.md 5.12: mod-eMjoqml7Qfb v36 lines 1545-1550, 1562-1563 [95]"],
        "files": [{"kind": "gameplay", "name": "gameplay.lua", "code": """\
-- Zones and enter/leave events. Source: guide-ru.md 5.12
-- (zone creation as in mod-7l4c6qjN5B9 v31, event parameters as in mod-eMjoqml7Qfb v36).

function createZones(startPositions)
    local zones = root.scene[0].landscape_zones
    for _, pos in ipairs(startPositions) do
        zones.f_addCircle(pos.x, pos.y, {{radius}})   -- radius in engine units (1000 = 1)
    end
    zones.f_updateMap()
end

function onStart(var)
    local startPositions = fromJson(root.dataStorage.startPositions)
    createZones(startPositions)
end

function onUnitInZone(var)
    local zone = getParameter("zone")          -- 0-based, order of f_addCircle calls
    local arrive = getParameter("arrive")      -- true = entered, false = left
    local factionId = getParameter("faction")
    log({ zone = zone, arrive = arrive, faction = factionId })
end

addMod({ onStart = onStart, onUnitInZone = onUnitInZone })
"""}],
    },
    "unit_death": {
        "description": "onUnitDeath handler with the known event parameters, wrapped in pcall.",
        "defaults": {},
        "sources": ["guide-ru.md 5.13: mod-98vr2B6ccl1 v10 lines 664-669 [97]", "mod-7l4c6qjN5B9 v31 lines 872-882 [96]"],
        "files": [{"kind": "gameplay", "name": "gameplay.lua", "code": """\
-- Unit death event. Source: guide-ru.md 5.13 (mod-98vr2B6ccl1 v10, mod-7l4c6qjN5B9 v31).
-- Known parameters: unitId, unitType, faction (of the dead unit), killerId, killerFaction.

function onUnitDeath(var)
    local ok, err = pcall(function()
        local deadId = tonumber(getParameter("unitId"))
        local deadType = tonumber(getParameter("unitType"))
        local faction = tonumber(getParameter("faction"))
        local killerId = tonumber(getParameter("killerId"))
        local killerFaction = tonumber(getParameter("killerFaction"))
        log({ deadId = deadId, deadType = deadType, faction = faction,
              killerId = killerId, killerFaction = killerFaction })
    end)
    if not ok then log(err) end
end

addMod({ onUnitDeath = onUnitDeath })
"""}],
    },
    "special_command_pair": {
        "description": "Visual button that sends a special command and the gameplay handler that receives it.",
        "defaults": {"command": "myCommand"},
        "sources": ["guide-ru.md 4.7: scheme and calls by Wouw [26]", "guide-ru.md 5.9: placingButtons, mod-MHTHlA4F9Zb [14]",
                    "guide-ru.md 4.7 example 4.5: getParameter/tonumber [27][11]"],
        "files": [
            {"kind": "visual", "name": "visual.lua", "code": """\
-- Visual side: a placing button sends "{{command}}" to the gameplay mod.
-- Sources: guide-ru.md 5.9 (mod-MHTHlA4F9Zb), 4.7 (Wouw [26]).

function onInit()
    local params = { "x", 30, "y", 70, "horizontalAlign", 0, "verticalAlign", 0, "text1", "{{command}}" }
    addInterface("placingButtons", "/project/Tools/placingButtons", nil, nil, params)
end

function onSpecialCommand()
    if getParameter("command") ~= "placerButton" then return end
    if getParameter("player") ~= getPlayerOfFaction(root.session.visual.currentFaction) then return end
    root.session.visual.commands.f_specialCommand(0, "command", "{{command}}",
        "x", getParameter("x"), "y", getParameter("y"), "player", getParameter("player"))
end

addMod({ onInit = onInit, onSpecialCommand = onSpecialCommand })
"""},
            {"kind": "gameplay", "name": "gameplay.lua", "code": """\
-- Gameplay side: receives "{{command}}" and changes the game state here.
-- Sources: guide-ru.md 4.7 (examples 4.5 and 4.6).

function onSpecialCommand(var)
    if getParameter("command") ~= "{{command}}" then return end
    local player = tonumber(getParameter("player"))
    local x, y = tonumber(getParameter("x")), tonumber(getParameter("y"))
    log({ command = "{{command}}", player = player, x = x, y = y })
    -- optional reply to the player's visual side (Wouw [26]):
    root.f_playerSpecialCommand(player, "command", "{{command}}Done")
end

addMod({ onSpecialCommand = onSpecialCommand })
"""},
        ],
    },
    "unit_stat_tweak": {
        "description": "Change a unit type field and apply it with root.f_recreateModifiedUnitTypes().",
        "defaults": {"unit_type_id": "315", "field": "deathability.health", "value": "500000"},
        "sources": ["guide-ru.md 2, example 2.1 (Wouw [58], [22])", "guide-ru.md 4.3"],
        "files": [{"kind": "gameplay", "name": "gameplay.lua", "code": """\
-- Unit type edit. Source: guide-ru.md example 2.1 and 4.3.
-- Values are x1000 (500000 = 500 HP). Find ids with unit_lookup or root.unitType.f_find(path).

root.unitType[{{unit_type_id}}].{{field}} = {{value}}
root.f_recreateModifiedUnitTypes()                 -- required, otherwise the edit is not applied
log(root.unitType[{{unit_type_id}}].{{field}})
"""}],
    },
}
