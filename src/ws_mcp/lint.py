"""Static checks for War Selection mods: Lua syntax plus known pitfalls.

Rules cite the bundled guide (guide-ru.md) section and the original source.
Unknown-name checks are warnings only. The API index is the live dump imported from the
game when present (import_api_dump), otherwise the bundled WSUS v258.4018 tree; names seen in
cached mods are accepted as known unless the live dump confirmed they are absent.
"""

from __future__ import annotations

import difflib
import re
from typing import Any, Iterable

from .lua_syntax import LuaSyntaxError, ParseResult, Ref, parse

# Events documented in WSUS (root.scripts) plus addMod keys observed in cached mods (engine 264).
KNOWN_EVENTS = {
    "init", "onInit", "onStart", "onTick", "onDump", "onDumpStart", "onDumpCreate", "beforeDumpCreate",
    "afterTick", "onSpecialCommand", "onUnitDeath", "onClose", "onPlayerEliminate", "onResearch",
    "onResearchDone", "onUnitInZone", "onUnitCustomAbility", "onWork", "onUnitCommand", "onServerWinData",
    "onDamage",
}
LEGACY_REGISTER = {"addStartFunction", "addTickFunction", "addScriptFunction"}
GAMEPLAY_MUTATOR_RE = re.compile(r"^f_(create|copy|remove|clear|add|set|change|eliminate|recreate|research|player)", re.I)
VISUAL_HINTS = ("root.session.visual", "root.interface", "root.session.render")


def normalize(chain: list[str]) -> str:
    """root.session_visual_commands -> root.session.visual.commands; keeps f_* segments intact."""
    out: list[str] = []
    for seg in chain:
        if seg == "[]" or seg.startswith("f_"):
            out.append(seg)
            continue
        parts = seg.split("_")
        for p in parts:
            if p == "":
                continue
            out.append("[]" if p.isdigit() else p)
    s = ".".join(out)
    return s.replace(".[]", "[]")


def _expand(chain: list[str], aliases: dict[str, list[str]], seen: int = 0) -> list[str]:
    """Resolve `local x = root.a.b` aliases when x is used as a base (x.c, x[i]); a bare `x` is left alone."""
    if len(chain) < 2:
        return chain
    head = chain[0]
    if head in aliases and seen < 5 and aliases[head] and aliases[head][0] != head and aliases[head] != ["<function>"]:
        return _expand(aliases[head] + chain[1:], aliases, seen + 1)
    return chain


def _suggest(name: str, pool: Iterable[str], n: int = 3) -> list[str]:
    return difflib.get_close_matches(name, sorted(set(pool)), n=n, cutoff=0.75)


def detect_kind(code: str) -> tuple[str, str]:
    low = code
    if re.search(r"root\.session[._]visual|root\.interface\b|root\.interface_|addInterface\s*\(", low):
        return "visual", "heuristic: code uses root.session.visual / root.interface / addInterface"
    return "gameplay", "heuristic: no visual-only API found"


def _issue(sev: str, rule: str, line: int | None, msg: str, source: str, suggestion: str | None = None) -> dict[str, Any]:
    d: dict[str, Any] = {"severity": sev, "rule": rule, "line": line, "message": msg, "source": source}
    if suggestion:
        d["suggestion"] = suggestion
    return d


def lint(code: str, kind: str, known_functions: set[str], known_root_fields: dict[str, set[str]],
         known_events: set[str] | None = None, absent_functions: dict[str, str] | None = None,
         index_label: str = "api_index (WSUS v258.4018)") -> dict[str, Any]:
    """kind: 'gameplay' or 'visual'. Returns syntax status and a list of issues."""
    issues: list[dict[str, Any]] = []
    try:
        pr: ParseResult = parse(code)
    except LuaSyntaxError as e:
        issues.append(_issue("error", "syntax", e.line, e.message, "Lua 5.4 grammar"))
        return {"syntax_ok": False, "issues": issues}

    events = set(KNOWN_EVENTS) | set(known_events or ())
    refs = [(r, normalize(_expand(r.chain, pr.aliases))) for r in pr.refs]
    calls = [(r, n) for r, n in refs if r.kind == "call"]
    assigns = [(r, n) for r, n in refs if r.kind == "assign"]

    def last(r: Ref) -> str:
        return r.chain[-1]

    # --- removed / renamed / unavailable functions
    for r, n in refs:
        if n in ("math.atan2",):
            issues.append(_issue("error", "math-atan2", r.line, "math.atan2 is not available in mods.",
                                 "guide 6.10; #bug-reports, Chenxi, 28.11.2025", "use math.atan(y, x)"))
    for r, n in calls:
        name = last(r)
        if name == "createUnits":
            issues.append(_issue("error", "removed-createUnits", r.line, "createUnits was removed from the engine.",
                                 "guide 5.8; Wouw, 06.10.2023",
                                 "root.scene[0].units.f_create(typeId, number, faction, x, y, direction)"))
        elif name == "addBuff":
            issues.append(_issue("warning", "renamed-addBuff", r.line,
                                 "addBuff is named f_addBuff in the WSUS v258.4018 tree.",
                                 "guide 5.16; WSUS gameplay.root.scene", "units.list[id].f_addBuff(researchId, finishTime)"))
        elif name in LEGACY_REGISTER and len(r.chain) == 1:
            issues.append(_issue("info", "legacy-register", r.line,
                                 f"{name} is the old registration API; new code should use addMod.", "guide 4.2",
                                 "addMod({ onStart = ..., onTick = ... })"))
        elif name in ("toTable", "fromTable") and len(r.chain) == 1:
            issues.append(_issue("info", "toTable", r.line, f"{name} is not recommended by the developers.",
                                 "guide 3; Wouw", "use toJson/fromJson or direct field access"))

    # --- determinism (gameplay)
    if kind == "gameplay":
        for r, n in refs:
            if n in ("math.random", "math.randomseed"):
                issues.append(_issue("error", "math-random", r.line,
                                     f"{n} in a gameplay mod gives different results per client (desync).",
                                     "guide 4.6; Wouw, 19.01.2024: 'f_random is safe... math.random is unsafe'",
                                     "root.f_random(limit)"))

    # --- unit type edits need f_recreateModifiedUnitTypes
    if kind == "gameplay":
        ut_edits = [(r, n) for r, n in assigns if n.startswith("root.unitType[") or n.startswith("root.unitType.")]
        has_recreate = any(last(r) == "f_recreateModifiedUnitTypes" for r, _ in calls)
        if ut_edits and not has_recreate:
            issues.append(_issue("warning", "missing-recreate", ut_edits[0][0].line,
                                 f"{len(ut_edits)} assignment(s) to root.unitType without root.f_recreateModifiedUnitTypes().",
                                 "guide 4.3; Wouw, 08.10.2023: 'maybe you forgot root.f_recreateModifiedUnitTypes()'",
                                 "call root.f_recreateModifiedUnitTypes() after the edits"))
        for r, n in calls:
            if n in ("root.unitType.f_create", "root.unitType.f_copy"):
                issues.append(_issue("info", "unit-type-visual-pair", r.line,
                                     "A new gameplay unit type also needs a matching visual unit type "
                                     "(root.session.visual.unitType) created by a visual mod, otherwise the game crashes.",
                                     "guide 6.3"))

    # --- f_create at top level runs again on every save
    for r, n in calls:
        if last(r) == "f_create" and r.depth == 0:
            issues.append(_issue("warning", "toplevel-f_create", r.line,
                                 "f_create() at top level runs again every time the mod is saved and adds duplicate entries.",
                                 "guide 2, 6.5; Wouw: 'Every time you save the mod it is executed again'",
                                 "move it into onInit/onStart"))

    # --- visual mods must not change game state
    if kind == "visual":
        for r, n in assigns:
            if n.startswith("root.session.gameplay"):
                issues.append(_issue("warning", "visual-writes-gameplay", r.line,
                                     f"Visual mod assigns gameplay state ({n}); in multiplayer this desyncs the match.",
                                     "guide 4.7, 6.2",
                                     "send a special command (root.session.visual.commands.f_specialCommand) and change state in a gameplay mod"))
        for r, n in calls:
            if n.startswith("root.session.gameplay") and GAMEPLAY_MUTATOR_RE.match(last(r)) and not last(r).startswith("f_find"):
                issues.append(_issue("warning", "visual-calls-gameplay", r.line,
                                     f"Visual mod calls a gameplay function that may change state ({n}).",
                                     "guide 4.7, 6.2", "use a special command handled by a gameplay mod"))
    else:
        hits = [(r, n) for r, n in refs if n.startswith(VISUAL_HINTS)]
        if hits:
            issues.append(_issue("info", "visual-api-in-gameplay", hits[0][0].line,
                                 f"Code references {hits[0][1].split('[')[0]}, which belongs to visual mods. Check kind.",
                                 "guide 1, 4.7"))

    # --- addMod handlers
    defined = pr.defined | pr.defined_fields
    for key, handler, line in pr.addmod_handlers:
        if key not in events:
            s = _suggest(key, events)
            issues.append(_issue("warning", "unknown-event", line, f"addMod key '{key}' is not a known event.",
                                 "WSUS root.scripts; addMod keys in cached mods",
                                 f"did you mean {', '.join(s)}?" if s else None))
        if handler and handler != "<function>" and handler not in defined:
            s = _suggest(handler, defined)
            issues.append(_issue("error", "undefined-handler", line,
                                 f"Handler '{handler}' for '{key}' is not defined in this file (it will be nil).",
                                 "Lua semantics", f"did you mean {', '.join(s)}?" if s else None))

    # --- names the live engine dump confirmed absent
    absent = absent_functions or {}
    seen: set[tuple[str, int]] = set()
    for r, n in calls:
        name = last(r)
        if name in absent and name not in defined and (name, r.line) not in seen:
            seen.add((name, r.line))
            s = _suggest(name, known_functions)
            issues.append(_issue("warning", "absent-in-engine", r.line,
                                 f"{name} ({absent[name]} in WSUS v258.4018) does not exist in the live engine dump.",
                                 index_label,
                                 f"did you mean {', '.join(s)}?" if s else "search_api for the current name"))

    # --- unknown names (warnings)
    for r, n in calls:
        name = last(r)
        if not name.startswith("f_") or name in known_functions or name in defined or name in absent:
            continue
        if (name, r.line) in seen:
            continue
        seen.add((name, r.line))
        s = _suggest(name, known_functions)
        issues.append(_issue("warning", "unknown-function", r.line,
                             f"{name} is not in the API index or in cached mods.",
                             f"{index_label} + cached mods",
                             f"did you mean {', '.join(s)}?" if s else "verify with log(<object>) in the console"))
    root_pool = known_root_fields.get(kind, set())
    if root_pool:
        reported: set[str] = set()
        for r, n in refs:
            if not n.startswith("root.") or r.kind == "assign" and len(n.split(".")) == 2:
                continue
            fld = re.split(r"[.\[]", n)[1]
            if not fld or fld in root_pool or fld.startswith("f_") or fld in reported:
                continue
            reported.add(fld)
            s = _suggest(fld, root_pool)
            issues.append(_issue("warning", "unknown-root-field", r.line,
                                 f"root.{fld} is not in the API index or in cached {kind} mods.",
                                 f"{index_label} + cached mods",
                                 f"did you mean {', '.join('root.' + x for x in s)}?" if s else None))

    if pr.addmod_calls == 0 and not any(last(r) in LEGACY_REGISTER for r, _ in calls) and pr.addmod_handlers == []:
        if pr.defined & KNOWN_EVENTS:
            issues.append(_issue("warning", "no-addMod", None,
                                 "Event handler functions are defined but never registered with addMod.",
                                 "guide 4.2", "addMod({ onStart = onStart, ... })"))

    order = {"error": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda i: (order[i["severity"]], i["line"] or 0))
    return {"syntax_ok": True, "issues": issues,
            "events": [k for k, _, _ in pr.addmod_handlers]}
