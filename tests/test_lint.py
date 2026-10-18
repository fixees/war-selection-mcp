from ws_mcp import modtools
from ws_mcp.lint import detect_kind, normalize


def rules(res):
    return {(i["severity"], i["rule"]) for i in res["issues"]}


def test_normalize():
    assert normalize(["root", "session_visual_commands", "f_specialCommand"]) == "root.session.visual.commands.f_specialCommand"
    assert normalize(["root", "scene_0", "units"]) == "root.scene[].units"
    assert normalize(["root", "unitType", "[]", "deathability"]) == "root.unitType[].deathability"


def test_detect_kind():
    assert detect_kind("local v = root.session.visual")[0] == "visual"
    assert detect_kind("addInterface('x', '/p')")[0] == "visual"
    assert detect_kind("root.unitType[1].speed = 1")[0] == "gameplay"


def test_gameplay_pitfalls(game):
    code = ("x = math.random(5)\nroot.unitType[1].speed = 2\nlocal t = math.atan2(1, 2)\n"
            "addMod({ onTik = onTick })\nfunction onTick() root.f_recreateModifedUnitTypes() end\ncreateUnits(1)\n"
            "root.scene[0].units.list[1].addBuff(1, 2)\nlocal id = root.researches.upgrades.f_create()\n")
    r = modtools.lint_mod(game, code=code, kind="gameplay")
    got = rules(r)
    assert ("error", "math-random") in got
    assert ("error", "math-atan2") in got
    assert ("error", "removed-createUnits") in got
    assert ("warning", "missing-recreate") in got
    assert ("warning", "unknown-event") in got
    assert ("warning", "unknown-function") in got
    assert ("warning", "renamed-addBuff") in got
    assert ("warning", "toplevel-f_create") in got
    unk = next(i for i in r["issues"] if i["rule"] == "unknown-function")
    assert "f_recreateModifiedUnitTypes" in unk["suggestion"]
    ev = next(i for i in r["issues"] if i["rule"] == "unknown-event")
    assert "onTick" in ev["suggestion"] and ev["code"].startswith("addMod")


def test_clean_code_and_recreate(game):
    code = ("root.unitType[315].deathability.health = 500000\nroot.f_recreateModifiedUnitTypes()\n"
            "function onStart(var) local n = root.f_random(10) end\naddMod({ onStart = onStart })\n")
    r = modtools.lint_mod(game, code=code, kind="auto")
    assert r["kind"] == "gameplay" and r["errors"] == 0 and r["warnings"] == 0, r["issues"]


def test_alias_reassignment_is_not_an_edit(game):
    code = "local unitType = root.unitType\nunitType = 8\nlocal q = root.unitType[1]\nq.speed = 2\nroot.f_recreateModifiedUnitTypes()\n"
    assert "missing-recreate" not in {i["rule"] for i in modtools.lint_mod(game, code=code, kind="gameplay")["issues"]}


def test_visual_rules(game):
    code = ("local g = root.session.gameplay.gameplay\nfunction onInit()\n  g.scene[0].faction[0].team = 2\n"
            "  g.unitType.f_create()\n  local r = math.random(3)\nend\naddMod({ onInit = onInit })\n")
    r = modtools.lint_mod(game, code=code, kind="visual")
    got = rules(r)
    assert ("warning", "visual-writes-gameplay") in got
    assert ("warning", "visual-calls-gameplay") in got
    assert "math-random" not in {x for _, x in got}


def test_undefined_handler_and_syntax(game):
    r = modtools.lint_mod(game, code="function onTick() end\naddMod({ onTick = ontick })", kind="gameplay")
    h = next(i for i in r["issues"] if i["rule"] == "undefined-handler")
    assert h["severity"] == "error" and "onTick" in h["suggestion"]
    s = modtools.lint_mod(game, code="function f(\n", kind="gameplay")
    assert s["syntax_ok"] is False and s["issues"][0]["rule"] == "syntax"


def test_lint_cached_mod_uses_log_kind(devgame):
    r = modtools.lint_mod(devgame, mod_id="mod-DDDDDDDDDD4")
    assert r["kind"] == "visual" and r["kind_basis"].startswith("gen/log.txt")
    r2 = modtools.lint_mod(devgame, mod_id="CCCCCCCCCC3")
    assert r2["kind"] == "gameplay" and any(i["rule"] == "undefined-handler" for i in r2["issues"])


def test_scaffolds_lint_clean(game):
    for t in modtools.list_templates():
        res = modtools.scaffold_mod(t["template"])
        for f in res["files"]:
            lr = modtools.lint_mod(game, code=f["code"], kind=f["kind"])
            assert lr["syntax_ok"] and lr["errors"] == 0 and lr["warnings"] == 0, (t, lr["issues"])
            assert "guide-ru.md" in f["code"]
