-- Mock of the engine object model for testing wsdump.lua.in with a stock Lua 5.4 interpreter.
-- Engine objects are proxies: pairs() yields nothing (as for userdata without __pairs), fields are
-- reachable only by index. log(obj) prints a one-level listing like the engine does.
local TS = "2026-10-18 06:30:00 "
local function isProxy(v) return type(v) == "table" and getmetatable(v) and getmetatable(v).__data ~= nil end
local function proxy(data)
  local mt = {}
  mt.__data = data
  mt.__index = function(_, k)
    if k == "f_explode" then error("No match address \"explode\"") end
    if k == "again" and data.again then return proxy(data) end
    return data[k]
  end
  mt.__newindex = function() error("read only") end
  mt.__pairs = function() error("pairs is not supported on engine objects") end
  if MOCK_TOSTRING then mt.__tostring = function(self) return LISTING(self) end end
  return setmetatable({}, mt)
end
local function arr(items)
  local d = { size = #items, f_create = function() end, f_clear = function() end }
  for i, v in ipairs(items) do d[i - 1] = v end
  return proxy(d)
end
SIGS = { f_random = "(limit)", f_recreateModifiedUnitTypes = "()", f_newThing = "(a,b=1)",
         f_create = "(...)", f_clear = "()", f_addCircle = "(x,y,radius)" }
function LISTING(v)
    local data = getmetatable(v).__data
    local keys = {}
    for k in pairs(data) do keys[#keys + 1] = k end
    table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
    local out = {}
    for _, k in ipairs(keys) do
      local x = data[k]
      local s
      if type(x) == "function" then s = SIGS[k] or "()"
      elseif isProxy(x) then
        local d = getmetatable(x).__data
        if type(d.size) == "number" and d[0] ~= nil then s = "[" .. d.size .. "]" else s = "{...}" end
      else s = tostring(x) end
      out[#out + 1] = tostring(k) .. ": " .. s
    end
    return table.concat(out, "\n")
end
function log(v)
  if isProxy(v) then print(TS .. LISTING(v)) else print(TS .. tostring(v)) end
end
function toTable(v)
  error("toTable disabled in mock")
end
local mirrorData = { again = true, n = 1 }
local unit = proxy({ health = 100, name = "worker", f_create = function() end })
local loopHolder = {}
local looping = proxy(loopHolder)
loopHolder.self = looping
loopHolder.value = 1
root = proxy({
  version = 264,
  time = 0,
  synced = "yes",
  finished = false,
  f_random = function() end,
  f_recreateModifiedUnitTypes = function() end,
  f_newThing = function() end,
  unitType = arr({ proxy({ attack = proxy({ range = 5 }), cost = 3 }), proxy({ attack = proxy({ range = 6 }), cost = 4 }) }),
  scene = arr({ proxy({ units = arr({ unit }), landscape = proxy({ zones = proxy({ f_addCircle = function() end, size = 0 }) }) }) }),
  loop = looping,
  mirror = proxy(mirrorData),
  broken = proxy({ f_explode = true, ok = 1 }),
  scripts = proxy({ onStart = 1, onTick = 2 }),
  text = "a\tb\nc",
})
