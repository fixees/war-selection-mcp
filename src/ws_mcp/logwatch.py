"""Cursor-based tail of gen/log.txt and a background watcher for Lua errors.

The game clears gen/log.txt on start (first line 'Log cleared in thread ...'); the previous session
is kept as gen/log_prev.txt. A cursor is '<file id>:<byte offset>' where the file id is a hash of the
first line, so a recreated log is detected even when it has grown past the old offset.
"""

from __future__ import annotations

import hashlib
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable

from .config import Config
from .core import ToolError
from .logparse import LogErrorParser

HEAD_BYTES = 256
MAX_CHUNK = 2_000_000


class CursorError(ToolError):
    pass


def _file_id(path: Path) -> str | None:
    try:
        with open(path, "rb") as fh:
            head = fh.read(HEAD_BYTES)
    except OSError:
        return None
    if not head:
        return "empty"
    first = head.split(b"\n", 1)[0]
    return hashlib.sha1(first).hexdigest()[:12]


def make_cursor(fid: str | None, offset: int) -> str:
    return f"{fid or 'none'}:{offset}"


def parse_cursor(cursor: str) -> tuple[str, int]:
    try:
        fid, off = cursor.rsplit(":", 1)
        return fid, int(off)
    except (ValueError, AttributeError):
        raise CursorError(f"Bad cursor {cursor!r}; pass the next_cursor from a previous call or omit it.") from None


def _read_from(path: Path, offset: int, limit: int = MAX_CHUNK) -> tuple[list[str], int, bool]:
    """Complete lines from offset; returns (lines, new_offset, more_available)."""
    with open(path, "rb") as fh:
        fh.seek(offset)
        data = fh.read(limit + 1)
    more = len(data) > limit
    data = data[:limit]
    cut = data.rfind(b"\n")
    if cut < 0:
        return [], offset, more
    chunk = data[:cut + 1]
    text = chunk.decode("utf-8", "replace")
    if offset == 0 and text.startswith("\ufeff"):
        text = text[1:]
    return text.splitlines(), offset + len(chunk), more


def _log_paths(cfg: Config) -> tuple[Path | None, Path | None]:
    cur = next((p for p in cfg.log_candidates("log.txt") if p.is_file()), None)
    if cur is None:
        cands = cfg.log_candidates("log.txt")
        cur_guess = next((p for p in cands if p.parent.is_dir()), None)
    else:
        cur_guess = cur
    prev = cur_guess.with_name("log_prev.txt") if cur_guess else None
    return cur, (prev if prev and prev.is_file() else None)


def tail(cfg: Config, cursor: str | None = None, max_lines: int = 500, initial_lines: int = 50) -> dict[str, Any]:
    """New log lines since `cursor`. Without a cursor: the last `initial_lines` lines and a cursor at the end."""
    max_lines = max(1, min(int(max_lines), 20_000))
    cur, prev = _log_paths(cfg)
    if cur is None:
        return {"found": False, "lines": [], "next_cursor": cursor or make_cursor(None, 0),
                "message": "gen/log.txt not found (game not started yet?). Set WS_LOG_PATH if it is elsewhere."}
    fid = _file_id(cur)
    size = cur.stat().st_size
    out: dict[str, Any] = {"found": True, "path": str(cur), "rotated": False, "lines": []}
    if cursor is None:
        start = max(0, size - 200_000)
        lines, end, _ = _read_from(cur, start, size - start)
        if start > 0 and lines:
            lines = lines[1:]
        out["lines"] = lines[-max(0, int(initial_lines)):] if initial_lines else []
        out["next_cursor"] = make_cursor(fid, end)
        out["more"] = False
        return out
    cfid, off = parse_cursor(cursor)
    lines: list[str] = []
    if cfid != fid or off > size:
        out["rotated"] = True
        # the old file became log_prev.txt: deliver its remainder first
        if prev is not None and _file_id(prev) == cfid and off <= prev.stat().st_size:
            rest, _, _ = _read_from(prev, off, MAX_CHUNK)
            lines += rest
            out["from_prev"] = len(rest)
        off = 0
    new, end, more = _read_from(cur, off, MAX_CHUNK)
    budget = max(0, max_lines - len(lines))
    if len(new) > budget:
        new = new[:budget]
        end = _offset_after(cur, off, budget)
        more = True
    lines += new
    out["lines"] = lines
    out["next_cursor"] = make_cursor(fid, end)
    out["more"] = more
    return out


def _offset_after(path: Path, offset: int, n_lines: int) -> int:
    with open(path, "rb") as fh:
        fh.seek(offset)
        for _ in range(n_lines):
            if not fh.readline():
                break
        return fh.tell()


class Watcher:
    """Background thread: follows the log with `tail`, parses errors, keeps the last `maxlen` events."""

    def __init__(self, cfg: Config, enrich: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
                 interval: float = 0.5, maxlen: int = 1000, warnings: bool = True, idle_flush: float = 1.5):
        self.cfg = cfg
        self.enrich = enrich
        self.interval = interval
        self.idle_flush = idle_flush
        self.events: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self.seq = 0
        self.lock = threading.Lock()
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.cursor: str | None = None
        self.parser = LogErrorParser(self._emit, warnings=warnings)
        self.rotations = 0
        self.lines_read = 0
        self.errors: list[str] = []
        self.started_at: str | None = None
        self._last_feed = time.monotonic()

    def _emit(self, ev: dict[str, Any]) -> None:
        if self.enrich:
            try:
                ev = self.enrich(ev)
            except Exception as e:  # mapping must never kill the watcher
                ev["mapping_error"] = str(e)
        with self.lock:
            self.seq += 1
            ev["seq"] = self.seq
            self.events.append(ev)

    def step(self) -> int:
        """One poll; returns number of lines read. Also used directly by tests and the CLI."""
        r = tail(self.cfg, self.cursor, max_lines=20_000, initial_lines=0)
        if not r["found"]:
            return 0
        if r.get("rotated"):
            self.rotations += 1
            self.parser.flush()
            if not r.get("from_prev"):
                self.parser.active = {"gameplay": [], "visual": []}
        for line in r["lines"]:
            self.parser.feed(line)
        n = len(r["lines"])
        self.lines_read += n
        self.cursor = r["next_cursor"]
        now = time.monotonic()
        if n:
            self._last_feed = now
        elif self.parser.pending and now - self._last_feed >= self.idle_flush:
            self.parser.flush()
        return n

    def start(self, from_start: bool = False) -> None:
        if self.thread and self.thread.is_alive():
            return
        if from_start:
            cur, _ = _log_paths(self.cfg)
            self.cursor = make_cursor(_file_id(cur), 0) if cur else None
        else:
            self.cursor = tail(self.cfg, None, initial_lines=0)["next_cursor"]
        self.started_at = time.strftime("%Y-%m-%d %H:%M:%S")
        self.stop_event.clear()
        self.thread = threading.Thread(target=self._run, name="ws-log-watch", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        while not self.stop_event.is_set():
            try:
                while self.step() >= 20_000:
                    pass
            except Exception as e:
                self.errors = (self.errors + [f"{time.strftime('%H:%M:%S')} {e}"])[-10:]
            self.stop_event.wait(self.interval)

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=5)
        self.parser.flush()

    @property
    def running(self) -> bool:
        return bool(self.thread and self.thread.is_alive())

    def poll(self, since_seq: int = 0, limit: int = 100) -> dict[str, Any]:
        with self.lock:
            evs = [e for e in self.events if e["seq"] > since_seq]
            first_kept = self.events[0]["seq"] if self.events else self.seq + 1
        lost = max(0, first_kept - since_seq - 1) if since_seq and since_seq < first_kept - 1 else 0
        limit = max(1, min(int(limit), 1000))
        out = evs[:limit]
        return {"running": self.running, "events": out,
                "next_seq": out[-1]["seq"] if out else since_seq,
                "more": len(evs) > limit, "dropped_before": lost, "rotations": self.rotations,
                "lines_read": self.lines_read, "started_at": self.started_at, "watcher_errors": self.errors}
