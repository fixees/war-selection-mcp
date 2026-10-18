import json
import shutil
import subprocess
from pathlib import Path

import pytest

from ws_mcp import apidump, core, dumpscript, modtools
from ws_mcp.lua_syntax import parse

FIX = Path(__file__).parent / "fixtures"
MOCK_LOG = FIX / "dump_mock.log"
LUA = shutil.which("lua5.4") or shutil.which("lua")


def _put_log(cfg, text: str) -> Path:
    gen = cfg.game_dir / "gen"
    gen.mkdir(exist_ok=True)
    p = gen / "log.txt"
    p.write_text(text, encoding="utf-8", newline="")
    return p


def _rec(did, *fields):
    return "WSDUMP\t" + did + "\t" + "\t".join(fields)


# ---------------------------------------------------------------- script

def test_script_renders_and_parses():
    r = dumpscript.render(dump_id="abc123", index_entries=core.load_api_index())
    assert r["dump_id"] == "abc123" and r["seed_names"] > 100
    parse(r["script"])
    assert 'id = "abc123"' in r["script"] and "math.random" not in r["script"] and "atan2" not in r["script"]
    assert "WSDUMP_RUN = wsdump" in r["script"] and r["script"].rstrip().endswith("wsdump()")


def test_script_compact_is_one_line():
    r = dumpscript.render(compact=True, seeds=False)
    assert "\n" not in r["script"] and "--" not in r["script"]
    parse(r["script"])
    assert r["bytes"] < 8000


def test_script_options_validated(game):
    with pytest.raises(core.ToolError):
        core.api_dump_script(game, root="os.execute('x')")
    with pytest.raises(core.ToolError):
        core.api_dump_script(game, space="lobby")
    r = core.api_dump_script(game, root="root.unitType[0]", depth=3)
    assert "depth = 3" in r["script"] and 'root = "root.unitType[0]"' in r["script"]
    assert r["how_to_run"] and r["next"].startswith("import_api_dump")


def test_seeds_by_space():
    entries = [{"kind": "function", "path": "root.scene[n].units.f_create", "name": "f_create"},
               {"kind": "field", "path": "visual.root.session.visual.commands", "name": "commands"},
               {"kind": "note", "path": "", "name": "x"}]
    g = dumpscript.seeds_from_index(entries, "gameplay")
    assert g == {"root.scene[].units": ["f_create"]}
    v = dumpscript.seeds_from_index(entries, "visual")
    assert v == {"root.session.visual": ["commands"]}
    assert dumpscript.seeds_from_index(entries, "gameplay", "root.unitType[0]") == {}


@pytest.mark.skipif(not LUA, reason="lua interpreter not installed")
@pytest.mark.parametrize("tostring", [False, True])
def test_script_runs_against_mock_engine(tostring, game):
    import importlib.util
    spec = importlib.util.spec_from_file_location("mk", Path(__file__).parent.parent / "scripts" / "make_dump_fixture.py")
    mk = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mk)
    for compact in (False, True):
        r = dumpscript.render(dump_id="m1", compact=compact, seeds=not compact, index_entries=core.load_api_index())
        out = mk.run_mock(r["script"], tostring=tostring)
        d = apidump.parse_dumps(out)[0]
        assert d["complete"] and d["status"] == "ok" and d["malformed"] == 0
        assert dict(d["raw"]["root"])["f_newThing"] == "(a,b=1)"  # native listing always captured
        if not tostring and compact:
            # no pairs(), no tostring listing, no seeds: only the root and its native listing
            assert set(d["nodes"]) == {"root"}
            continue
        assert d["nodes"]["root.version"] == ("num", "264")
        if not tostring:
            assert d["nodes"]["root.auraTypes"] == ("nil", "")  # seeded name missing in the engine
            continue
        assert d["nodes"]["root.text"] == ("str", "a\tb\nc")
        assert d["nodes"]["root.broken.f_explode"][0] == "err"
        assert d["nodes"]["root.loop.self"] == ("link", "root.loop")
        assert any(w.startswith("cycle guard") for w in d["warnings"])
        assert d["nodes"]["root.unitType[].attack.range"][0] == "num"


# ---------------------------------------------------------------- parser

def test_parse_fixture():
    d = apidump.parse_dumps(MOCK_LOG.read_text(encoding="utf-8"))
    assert len(d) == 1
    d = d[0]
    assert d["id"] == "a1b2c3d4" and d["complete"] and d["engine_version"] == "264"
    assert d["game_version"].startswith("264.4021")
    assert d["space"] == "gameplay" and d["root"] == "root"
    assert d["nodes"]["root.auraTypes"] == ("nil", "")
    assert "root.scene[]" in d["expanded"]
    assert ("f_random", "(limit)") in d["raw"]["root"]


def test_parse_malformed_and_foreign_lines():
    text = "\n".join([
        "2026-10-18 05:53:01 Engine Version: 264",
        _rec("x1", "B", "1", "gameplay", "root", "version=264"),
        _rec("x1", "N", "root.a", "num", "1"),
        _rec("x1", "N", "root.b"),                       # too few fields
        _rec("x1", "N", "root.c", "weird", "1"),         # unknown type
        _rec("x1", "N", "os.exit", "func", ""),          # path outside root
        _rec("x1", "Q", "junk"),                         # unknown record
        "WSDUMP\tbad id!\tN\troot.z\tnum\t1",            # bad id: ignored
        "2026-10-18 05:53:02 some engine line",
        "WSDUMP",                                        # bare prefix
        _rec("x1", "N", "root.d", "str", "x\\ty"),
        _rec("x1", "E", "2", "ok", "0"),
    ])
    d = apidump.parse_dumps(text)[0]
    assert set(d["nodes"]) == {"root.a", "root.d"}
    assert d["nodes"]["root.d"] == ("str", "x\ty")
    assert d["malformed"] == 4 and d["complete"]


def test_parse_truncated_raw_block_and_interleaved_dumps():
    text = "\n".join([
        _rec("a", "B", "1", "gameplay", "root", ""),
        _rec("b", "B", "1", "visual", "root", ""),
        _rec("a", "X", "root", "obj", "0"),
        _rec("a", "R", "root"),
        "2026-10-18 05:53:01 f_one: (x)",
        "f_two: ()",
        "garbage line without colon",
        _rec("a", "N", "root.k", "num", "1"),            # raw not closed: closed implicitly
        "late: 5",                                       # not part of any raw block
        _rec("b", "N", "root.interface", "obj", ""),
        _rec("b", "E", "1", "ok", "0"),
    ])
    a, b = apidump.parse_dumps(text)
    assert not a["complete"] and b["complete"]
    assert a["raw"]["root"] == [("f_one", "(x)"), ("f_two", "()")]
    assert a["raw_closed"] == [] and "root.k" in a["nodes"]


# ---------------------------------------------------------------- import

def test_import_from_game_log(game):
    _put_log(game, MOCK_LOG.read_text(encoding="utf-8"))
    before = sorted(p.name for p in game.game_dir.rglob("*"))
    r = core.import_api_dump(game, limit=500)
    assert sorted(p.name for p in game.game_dir.rglob("*")) == before  # nothing written to the game folder
    assert Path(r["stored"]).parent == game.data_dir
    assert r["engine_version"] == "264" and r["complete"] and r["dump_id"] == "a1b2c3d4"
    diff = r["diff_vs_bundled"]
    assert "root.f_newThing" in diff["added_paths"]
    removed = {x["path"] for x in diff["removed_paths"]}
    assert {"root.auraTypes", "root.f_fingerprint"} <= removed
    assert "root.f_random" not in removed and "root.version" not in removed
    assert {"path": "root.synced", "field": "type", "bundled": "bool", "live": "str"} in diff["changed_paths"]
    assert "root.unitType[0].attack" in r["unexplored"]
    assert "root" not in diff["added_paths"]
    doc = json.loads(Path(r["stored"]).read_text(encoding="utf-8"))
    fn = next(e for e in doc["entries"] if e["path"] == "root.f_newThing")
    assert fn["signature"] == "f_newThing(a,b=1)" and fn["kind"] == "function"
    assert next(e for e in doc["entries"] if e["path"] == "root.scripts.onStart")["kind"] == "event"
    assert Path(r["diff_file"]).is_file()


def test_search_and_lint_prefer_live_index(game):
    assert core.search_api("f_fingerprint", cfg=game)["results"]  # bundled before import
    core.import_api_dump(game, file=str(MOCK_LOG))
    res = core.search_api("f_newThing", cfg=game)
    assert res["index"]["active"] == "live + bundled fallback" and res["index"]["engine_version"] == "264"
    assert res["results"][0]["source"].startswith("live dump")
    assert not [e for e in core.search_api("f_fingerprint", cfg=game)["results"] if e.get("path") == "root.f_fingerprint"]
    # bundled entries outside the dumped levels stay available, notes are kept
    assert core.search_api("f_recreateModifiedUnitTypes", kind="note", cfg=game)["results"]
    code = ("function onStart()\n  root.f_fingerprint()\n  root.f_newThing(1)\n  root.f_random(5)\nend\n"
            "addMod({ onStart = onStart })\n")
    r = modtools.lint_mod(game, code=code, kind="gameplay")
    rules = {(i["rule"], i["line"]) for i in r["issues"]}
    assert ("absent-in-engine", 2) in rules
    assert not any(i["line"] == 3 for i in r["issues"])
    assert not any(i["line"] == 4 for i in r["issues"])
    assert "live dump" in r["api_index"]
    st = core.api_index_status(game)
    assert st["live_present"] and st["engine_version"] == "264" and "stale" not in st


def test_lint_without_live_index_has_no_absent_rule(game):
    r = modtools.lint_mod(game, code="root.f_fingerprint()\n", kind="gameplay")
    assert not any(i["rule"] == "absent-in-engine" for i in r["issues"])
    assert "bundled" in r["api_index"]
    assert "stale" in core.api_index_status(game)


def test_truncated_dump_requires_allow_partial(game):
    lines = MOCK_LOG.read_text(encoding="utf-8").splitlines()
    cut = [l for l in lines if "\tE\t" not in l][:60]
    p = _put_log(game, "\n".join(cut))
    with pytest.raises(core.ToolError, match="no END record"):
        core.import_api_dump(game)
    r = core.import_api_dump(game, file=str(p), allow_partial=True)
    assert not r["complete"] and any("no END" in w for w in r["warnings"])


def test_no_dump_in_log(game):
    _put_log(game, "2026-10-18 05:53:01 Engine Version: 264\n")
    with pytest.raises(core.ToolError, match="No WSDUMP records"):
        core.import_api_dump(game)


def test_cycles_become_links_not_unexplored(game):
    text = "\n".join([
        "2026-10-18 05:53:01 Engine Version: 264",
        _rec("c1", "B", "1", "gameplay", "root", ""),
        _rec("c1", "N", "root", "obj", ""),
        _rec("c1", "X", "root", "obj", "0"),
        _rec("c1", "N", "root.loop", "obj", ""),
        _rec("c1", "X", "root.loop", "obj", "0"),
        _rec("c1", "N", "root.loop.self", "link", "root.loop"),
        _rec("c1", "N", "root.loop.again", "obj", ""),
        _rec("c1", "W", "cycle guard: root.loop.again"),
        _rec("c1", "N", "root.unitType", "nil", ""),
        _rec("c1", "E", "4", "ok", "0"),
    ])
    p = _put_log(game, text)
    r = core.import_api_dump(game, file=str(p))
    assert r["cycle_guards"] == 1 and r["warnings"] == []
    assert "root.loop.self" not in r["unexplored"] and "root.loop.again" in r["unexplored"]
    doc = json.loads(Path(r["stored"]).read_text(encoding="utf-8"))
    link = next(e for e in doc["entries"] if e["path"] == "root.loop.self")
    assert link["link"] is True


def test_merge_subtrees_and_engine_change(game):
    def dump(did, root, engine, nodes):
        return "\n".join([f"2026-10-18 05:53:01 Engine Version: {engine}",
                          _rec(did, "B", "1", "gameplay", root, ""),
                          *[_rec(did, "N", *n) for n in nodes],
                          _rec(did, "E", str(len(nodes)), "ok", "0")])
    a = _put_log(game, dump("d1", "root", "264", [("root.f_one", "func", ""), ("root.unitType", "arr", "3")]))
    core.import_api_dump(game, file=str(a))
    b = game.game_dir / "gen" / "b.txt"
    b.write_text(dump("d2", "root.unitType[0]", "264", [("root.unitType[]", "obj", ""), ("root.unitType[].cost", "num", "3")]))
    core.import_api_dump(game, file=str(b))
    paths = {e["path"] for e in json.loads(apidump.live_path(game).read_text())["entries"]}
    assert {"root.f_one", "root.unitType", "root.unitType[n].cost"} <= paths
    c = game.game_dir / "gen" / "c.txt"
    c.write_text(dump("d3", "root", "265", [("root.f_two", "func", "")]))
    r = core.import_api_dump(game, file=str(c))
    assert "engine changed 264 -> 265" in r["previous_index"]
    paths = {e["path"] for e in json.loads(apidump.live_path(game).read_text())["entries"]}
    assert paths == {"root.f_two"}
    assert (game.data_dir / apidump.PREV_FILE).is_file()


def test_dry_run_writes_nothing(game):
    r = core.import_api_dump(game, file=str(MOCK_LOG), dry_run=True)
    assert r["stored"] is None and not game.data_dir.exists()


def test_refuses_data_dir_inside_game_folder(game, monkeypatch):
    monkeypatch.setenv("WS_MCP_DATA_DIR", str(game.game_dir / "gen" / "idx"))
    from ws_mcp.config import Config
    cfg = Config.from_env()
    with pytest.raises(core.ToolError, match="inside the game folder"):
        core.import_api_dump(cfg, file=str(MOCK_LOG))
    assert not (game.game_dir / "gen" / "idx").exists()


def test_space_detection_overrides_header(game):
    text = "\n".join([_rec("v1", "B", "1", "gameplay", "root", ""),
                      _rec("v1", "N", "root.interface", "obj", ""),
                      _rec("v1", "N", "root.session", "obj", ""),
                      _rec("v1", "E", "2", "ok", "0")])
    p = _put_log(game, text)
    r = core.import_api_dump(game, file=str(p))
    assert r["space"] == "visual" and any("looks like 'visual'" in w for w in r["warnings"])
    doc = json.loads(Path(r["stored"]).read_text(encoding="utf-8"))
    assert {e["path"] for e in doc["entries"]} == {"visual.root.interface", "visual.root.session"}


def test_rerun_with_same_id_keeps_runs_apart(game):
    run1 = [_rec("s1", "B", "1", "gameplay", "root", ""), _rec("s1", "N", "root.old", "num", "1"),
            _rec("s1", "E", "1", "ok", "0")]
    run2 = [_rec("s1", "B", "1", "gameplay", "root", ""), _rec("s1", "N", "root.new", "num", "1")]
    d = apidump.parse_dumps("\n".join(run1 + run2))
    assert len(d) == 2 and d[0]["complete"] and not d[1]["complete"]
    assert set(d[0]["nodes"]) == {"root.old"} and set(d[1]["nodes"]) == {"root.new"}
    p = _put_log(game, "\n".join(run1 + run2))
    r = core.import_api_dump(game, file=str(p), dump_id="s1")
    assert r["complete"] and r["nodes"] == 1


def test_shipped_lua_files_are_current():
    root = Path(__file__).parent.parent / "lua"
    full = dumpscript.render(dump_id=dumpscript.SHIPPED_ID, index_entries=core.load_api_index())["script"]
    one = dumpscript.render(dump_id=dumpscript.SHIPPED_ID, compact=True, seeds=False)["script"]
    assert (root / "wsdump.lua").read_text(encoding="utf-8") == full + "\n", "run: python scripts/build_lua.py"
    assert (root / "wsdump-oneline.lua").read_text(encoding="utf-8") == one + "\n"
