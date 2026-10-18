import pytest

from ws_mcp.lua_syntax import LuaSyntaxError, check, parse, tokenize


@pytest.mark.parametrize("src", [
    "local x <const> = 5\nlocal y <close> = nil",
    "x = y // 2 & 3 ~ 1 << 2 | 4 >> 1\ngoto done\n::done::",
    "local s = [==[a]]b]==] .. [[\nmulti]] .. 'q\\'' .. \"\\x41\\u{48}\\z\n   x\"",
    "print(0x1p4, 0xA.8, 3e-2, .5, 1e10)",
    "a.b:c 'x' {1} (2)",
    "local t = {1, 2; x = 3, ['y'] = 4,}",
    "local function f(...) return ... end",
    "return",
    "for k, v in pairs(t) do if v then break end end",
    "repeat local z = 1 until z",
    "#!/usr/bin/lua\nprint(1)",
    "--[==[ long\ncomment ]==] print(1)",
])
def test_valid(src):
    assert check(src) == {"ok": True}


@pytest.mark.parametrize("src,line,fragment", [
    ("function f()\n  if x then\n    print(x)\nend\n", 5, "'end' expected (to close 'function' at line 1)"),
    ("local a = = 2", 1, "unexpected symbol near '='"),
    ("print(t.a))", 1, "unexpected symbol near ')'"),
    ("for i=1,2 do\nend end", 2, "'<eof>' expected near 'end'"),
    ("f() = 1", 1, "syntax error near '='"),
    ("x", 1, "syntax error near <eof>"),
    ("break", 1, "break outside a loop"),
    ("local function g() return ... end", 1, "cannot use '...' outside a vararg function"),
    ("local s = 'abc\nx'", 1, "unfinished string"),
    ("return 1\nx = 2", 2, "'<eof>' expected"),
    ("x = 3x", 1, "malformed number"),
    ("local x <foo> = 1", 1, "unknown attribute"),
    ("s = [[never closed", 1, "unfinished long string"),
    ("t = {1, 2", 1, "'}' expected"),
])
def test_errors(src, line, fragment):
    r = check(src)
    assert r["ok"] is False and r["line"] == line and fragment in r["error"]


def test_facts():
    pr = parse("local u = root.unitType\nu[1].speed = 2\nfunction onStart() end\nM.f_x = function() end\n"
               "addMod({ onStart = onStart, onTick = function() end })")
    assert ("onStart", "onStart", 5) in pr.addmod_handlers
    assert ("onTick", "<function>", 5) in pr.addmod_handlers
    assert pr.aliases["u"] == ["root", "unitType"]
    assert "f_x" in pr.defined_fields and "onStart" in pr.defined
    assert any(r.kind == "assign" and r.chain == ["u", "[]", "speed"] for r in pr.refs)


def test_bom_and_lines():
    assert parse("\ufeffprint(1)").refs[0].chain == ["print"]
    toks = tokenize("a\n--[[x\ny]]\nb")
    assert [t.line for t in toks if t.type == "name"] == [1, 4]
    with pytest.raises(LuaSyntaxError):
        parse("a = 'x")
