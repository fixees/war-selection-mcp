import subprocess
import sys
import time

import pytest

from ws_mcp import logparse, logwatch, modtools, server

# Formats as they appear in player logs (2023 and 2025 bug reports); ids, hashes and text invented.
DRAFT_LOG = (
    "Log cleared in thread 1 at Asia/Yekaterinburg timezone Sun Oct 18 10:53:01 2026\n"
    "2026-10-18 05:53:02 Engine Version: 264\n"
    "2026-10-18 05:53:12 Using gameplay modifications: draft/EEEEEEEEEE5_2\n"
    "2026-10-18 05:54:00 Error: Lua program /modsStorage/draft/EEEEEEEEEE5_2-abcdefabcdef0123.lua run failed:\n"
    "\tError occured at:\n"
    "\tLine:3 function:[onStart]\n"
    "[string \"function onStart(var)...\"]:3: attempt to index a nil value (global 'zones')\n"
    "\n"
    "2026-10-18 05:54:05 Lua compilation error for: /modsStorage/draft/EEEEEEEEEE5_2-abcdefabcdef0123.lua\n"
    "\t[string \"function onStart(var)...\"]:4: 'end' expected (to close 'function' at line 1) near <eof>\n"
    "\n"
    "2026-10-18 05:54:06 Using obsolete parameter 'unitType.x'\n"
)
DRAFT_CODE = "function onStart(var)\n  local a = 1\n  zones.f_addCircle(1, 2, 3)\nend\naddMod({ onStart = onStart })\n"


@pytest.fixture()
def draftgame(devgame):
    d = devgame.mods_dir / "draft"
    d.mkdir()
    (d / "EEEEEEEEEE5_2-abcdefabcdef0123.lua").write_text(DRAFT_CODE)
    return devgame


def test_parse_real_formats():
    evs = logparse.parse_lines(DRAFT_LOG.splitlines(), warnings=True)
    kinds = [e["kind"] for e in evs]
    assert kinds == ["lua_error", "compile_error", "warning"]
    run = evs[0]
    assert run["mod_file"] == {"id": "EEEEEEEEEE5", "version": 2, "file": "EEEEEEEEEE5_2-abcdefabcdef0123.lua",
                               "source": "draft"}
    assert run["frames"] == [{"line": 3, "function": "onStart"}]
    assert run["chunk_line"] == 3 and "nil value" in run["message"]
    assert run["active_gameplay"] == ["draft/EEEEEEEEEE5_2"]
    assert evs[1]["chunk_line"] == 4 and "'end' expected" in evs[1]["message"]


def test_resolve_to_draft_with_excerpt(draftgame):
    ev = logparse.parse_lines(DRAFT_LOG.splitlines())[0]
    hit = modtools.resolve_source(draftgame, ev)[0]
    assert hit["source"] == "draft" and hit["line"] == 3
    assert "zones.f_addCircle" in hit["code"]
    assert ">" in hit["excerpt"] and "local a = 1" in hit["excerpt"]


def test_log_errors_maps_draft(draftgame):
    (draftgame.game_dir / "gen" / "log.txt").write_text(DRAFT_LOG)
    r = modtools.log_errors(draftgame)
    srcs = [c for g in r["groups"] for c in g["candidates"]]
    assert any(c.get("source") == "draft" for c in srcs)


def _log(cfg):
    return cfg.game_dir / "gen" / "log.txt"


def test_tail_cursor_append(devgame):
    p = _log(devgame)
    r = logwatch.tail(devgame, None, initial_lines=2)
    assert len(r["lines"]) == 2 and r["found"]
    c = r["next_cursor"]
    assert logwatch.tail(devgame, c)["lines"] == []
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("2026-10-18 06:00:00 one\n2026-10-18 06:00:01 partial")
    r = logwatch.tail(devgame, c)
    assert r["lines"] == ["2026-10-18 06:00:00 one"] and not r["rotated"]
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(" line\n")
    r2 = logwatch.tail(devgame, r["next_cursor"])
    assert r2["lines"] == ["2026-10-18 06:00:01 partial line"]


def test_tail_max_lines(devgame):
    c = logwatch.tail(devgame, None)["next_cursor"]
    with open(_log(devgame), "a", encoding="utf-8") as fh:
        fh.writelines(f"2026-10-18 06:00:00 n{i}\r\n" for i in range(10))
    r = logwatch.tail(devgame, c, max_lines=4)
    assert r["lines"] == [f"2026-10-18 06:00:00 n{i}" for i in range(4)] and r["more"]
    r = logwatch.tail(devgame, r["next_cursor"], max_lines=100)
    assert r["lines"][0] == "2026-10-18 06:00:00 n4" and len(r["lines"]) == 6


def test_tail_rotation_with_prev(devgame):
    p = _log(devgame)
    c = logwatch.tail(devgame, None)["next_cursor"]
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("2026-10-18 06:00:00 last of old session\n")
    p.replace(p.with_name("log_prev.txt"))
    p.write_text("Log cleared in thread 7 at X\n2026-10-18 07:00:00 new session\n")
    r = logwatch.tail(devgame, c)
    assert r["rotated"] and r["from_prev"] == 1
    assert r["lines"] == ["2026-10-18 06:00:00 last of old session", "Log cleared in thread 7 at X",
                          "2026-10-18 07:00:00 new session"]


def test_tail_truncated_same_header(devgame):
    p = _log(devgame)
    c = logwatch.tail(devgame, None)["next_cursor"]
    p.write_text("Log cleared in thread 1\nshort\n")  # same first line, smaller file
    r = logwatch.tail(devgame, c)
    assert r["rotated"] and r["lines"] == ["Log cleared in thread 1", "short"]


def test_tail_bad_cursor_and_missing(devgame, tmp_path, monkeypatch):
    with pytest.raises(logwatch.CursorError):
        logwatch.tail(devgame, "garbage")
    assert server.log_tail("garbage").get("error")
    _log(devgame).unlink()
    assert logwatch.tail(devgame, None)["found"] is False


def test_watcher_steps(draftgame):
    p = _log(draftgame)
    w = logwatch.Watcher(draftgame, enrich=server._enrich, idle_flush=0)
    w.cursor = logwatch.tail(draftgame, None, initial_lines=0)["next_cursor"]
    p.write_text(DRAFT_LOG)  # game restarted: log recreated
    w.step()
    w.step()  # idle -> flush pending block
    r = w.poll(0)
    kinds = [e["kind"] for e in r["events"]]
    assert kinds == ["lua_error", "compile_error", "warning"]
    assert w.rotations == 1
    src = r["events"][0]["source"][0]
    assert src["source"] == "draft" and src["line"] == 3 and "excerpt" in src
    assert w.poll(r["next_seq"])["events"] == []
    assert "draft/EEEEEEEEEE5_2-abcdefabcdef0123.lua:3" in server.format_event(r["events"][0])


def test_watch_tools_thread(draftgame):
    st = server.watch_log_start()
    try:
        assert st["running"]
        assert server.watch_log_start()["already_running"]
        with open(_log(draftgame), "a", encoding="utf-8") as fh:
            fh.write(DRAFT_LOG.split("\n", 1)[1])
        deadline = time.time() + 10
        evs = []
        while time.time() < deadline and len(evs) < 3:
            evs += server.watch_log_poll(evs[-1]["seq"] if evs else 0)["events"]
            time.sleep(0.2)
        assert [e["kind"] for e in evs][:2] == ["lua_error", "compile_error"]
    finally:
        assert server.watch_log_stop()["running"] is False


def test_cli_watch_log(draftgame, monkeypatch):
    (draftgame.game_dir / "gen" / "log.txt").write_text(DRAFT_LOG)
    import os
    proc = subprocess.Popen([sys.executable, "-m", "ws_mcp", "--watch-log", "--from-start"], env=dict(os.environ),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        out, err = proc.communicate(timeout=4)
    except subprocess.TimeoutExpired:
        proc.terminate()
        out, err = proc.communicate(timeout=10)
    assert "lua_error mod-EEEEEEEEEE5 draft/EEEEEEEEEE5_2-abcdefabcdef0123.lua:3" in out
    assert "zones.f_addCircle" in out
    assert "watching" in err
