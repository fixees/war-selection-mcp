"""Incremental parser for Lua errors and warnings in gen/log.txt.

Formats (verified in game logs, see docs/log-watch.md):

    2025-02-21 17:35:30 Lua program scripts/.../_work.lua run (Error) failed:
    \tError occured at:
    \tLine:805 function:[showWorkButton]
    [string "local interfaceName = getParameter("interface..."]:805: attempt to ... (global 'workObject')

    2023-09-19 14:02:47 Error: Lua program /modsStorage/draft/Cl0LWNP6m05_1-0436ea81441a4e3a.lua run failed:
    \tError occured at:
    \tLine:-1 function:[f_create]
    No match address "create"

    2023-09-19 14:02:48 Lua compilation error for: /modsStorage/draft/j5necqbufzh_1-75ba3418b6b7a1cc.lua
    \t[string "local unitType1ExtData = fromJson（root.sess..."]:1: unexpected symbol near '<\\239>'

Continuation lines carry no timestamp; a block ends at an empty line or at the next timestamped line.
"""

from __future__ import annotations

import re
from typing import Any, Callable

LOG_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s?(.*)$")
USING_RE = re.compile(r"Using (gameplay|visual) modifications:\s*(.*)$")
ACTIVE_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])((?:draft/)?)([A-Za-z0-9]{11})_(\d+)\b")
LUA_FAIL_RE = re.compile(r"^(?:Error:\s*)?Lua program (?P<script>\S+) run (?:\((?P<status>[^)]*)\) )?failed:?")
COMPILE_RE = re.compile(r"^Lua compilation error for:\s*(?P<script>\S+)")
FRAME_RE = re.compile(r"^\s*Line:\s*(-?\d+)\s+function:\[([^\]]*)\]")
CHUNK_RE = re.compile(r'\[string "(?P<preview>.*?)(?:\.\.\.)?"\]:(?P<line>-?\d+):\s*(?P<msg>.*)')
ERROR_AT_RE = re.compile(r"^\s*Error occur+ed at:?")
MOD_PATH_RE = re.compile(r"/?modsStorage/(?P<draft>draft/)?(?P<file>(?P<id>[A-Za-z0-9]{11})_(?P<ver>\d+)-[0-9a-fA-F]{16}\.lua)")
WARNING_RES = [
    (re.compile(r"^Using obsolete parameter .*"), "warning"),
    (re.compile(r"^Obsolete interface address: .*"), "warning"),
    (re.compile(r"^Value is read only.*"), "warning"),
    (re.compile(r"^Global exception: .*"), "engine_error"),
    (re.compile(r"^Code panic at.*"), "engine_error"),
]


def mod_ref_from_script(script: str | None) -> dict[str, Any] | None:
    """'/modsStorage/draft/<id>_<ver>-<hash>.lua' -> {id, version, file, source}."""
    if not script:
        return None
    m = MOD_PATH_RE.search(script)
    if not m:
        return None
    return {"id": m["id"], "version": int(m["ver"]), "file": m["file"], "source": "draft" if m["draft"] else "cache"}


class LogErrorParser:
    """Feed log lines one by one; completed events are passed to `emit`."""

    def __init__(self, emit: Callable[[dict[str, Any]], None], warnings: bool = True):
        self.emit = emit
        self.warnings = warnings
        self.active: dict[str, list[str]] = {"gameplay": [], "visual": []}
        self.cur: dict[str, Any] | None = None
        self.line_no = 0

    def _new(self, kind: str, ts: str | None, script: str | None, status: str | None) -> dict[str, Any]:
        return {"kind": kind, "line_no": self.line_no, "time": ts, "script": script, "status": status,
                "frames": [], "message": None, "chunk_preview": None, "chunk_line": None,
                "mod_file": mod_ref_from_script(script),
                "active_gameplay": list(self.active["gameplay"]), "active_visual": list(self.active["visual"])}

    def _close(self) -> None:
        if self.cur is not None:
            self.emit(self.cur)
            self.cur = None

    def flush(self) -> None:
        """Emit a pending block (end of input or idle timeout)."""
        self._close()

    @property
    def pending(self) -> bool:
        return self.cur is not None

    def feed(self, raw: str) -> None:
        self.line_no += 1
        raw = raw.rstrip("\r\n")
        m_ts = LOG_TS_RE.match(raw)
        ts, body = (m_ts.group(1), m_ts.group(2)) if m_ts else (None, raw)
        cur = self.cur
        if cur is not None and m_ts is None:
            if ERROR_AT_RE.match(raw):
                return
            fm = FRAME_RE.match(raw)
            if fm:
                cur["frames"].append({"line": int(fm.group(1)), "function": fm.group(2)})
                return
            if not raw.strip():
                if cur["message"] is not None:
                    self._close()
                return
            if cur["message"] is None:
                cm = CHUNK_RE.search(raw)
                if cm:
                    cur.update(chunk_preview=cm.group("preview"), chunk_line=int(cm.group("line")),
                               message=cm.group("msg").strip())
                else:
                    cur["message"] = raw.strip()
                return
            cur["message"] += "\n" + raw.strip()
            return
        if cur is not None:
            self._close()
        mu = USING_RE.search(body)
        if mu:
            self.active[mu.group(1)] = [f"{d}{a}_{b}" for d, a, b in ACTIVE_TOKEN_RE.findall(mu.group(2))]
            return
        mf = LUA_FAIL_RE.search(body)
        if mf:
            self.cur = self._new("lua_error", ts, mf.group("script"), mf.group("status"))
            return
        mc = COMPILE_RE.search(body)
        if mc:
            self.cur = self._new("compile_error", ts, mc.group("script"), None)
            return
        cm = CHUNK_RE.search(body)
        if cm:
            e = self._new("lua_error", ts, None, None)
            e.update(message=cm.group("msg").strip(), chunk_preview=cm.group("preview"), chunk_line=int(cm.group("line")))
            self.emit(e)
            return
        if self.warnings and m_ts:
            for rx, kind in WARNING_RES:
                if rx.match(body):
                    e = self._new(kind, ts, None, None)
                    e["message"] = body.strip()
                    self.emit(e)
                    return


def parse_lines(lines: list[str], warnings: bool = False) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    p = LogErrorParser(out.append, warnings=warnings)
    for l in lines:
        p.feed(l)
    p.flush()
    return out
