"""Regenerate tests/fixtures/dump_mock.log (needs lua5.4 or lua on PATH)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from ws_mcp import core, dumpscript

HERE = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
HEADER = [
    "Log cleared in thread 29220 at Asia/Yekaterinburg timezone Sun Oct 18 10:53:01 2026",
    "",
    "2026-10-18 05:53:01 Engine run: pid=1",
    "2026-10-18 05:53:01 Engine Version: 264",
    "2026-10-18 05:53:10 Game Version: 264.4021.e337461122577e69_29234.12142",
    "2026-10-18 05:53:12 Using gameplay modifications: JnHcuvqS6ga_11",
]


def run_mock(script: str, tostring: bool = False) -> str:
    lua = shutil.which("lua5.4") or shutil.which("lua")
    if not lua:
        raise SystemExit("lua5.4 not found")
    with tempfile.NamedTemporaryFile("w", suffix=".lua", delete=False, encoding="utf-8") as fh:
        fh.write(script)
    pre = "MOCK_TOSTRING=true " if tostring else ""
    code = f'{pre}dofile([[{HERE / "mock_engine.lua"}]]) dofile([[{fh.name}]])'
    return subprocess.run([lua, "-e", code], capture_output=True, text=True, check=True).stdout


def main() -> None:
    script = dumpscript.render(dump_id="a1b2c3d4", index_entries=core.load_api_index())["script"]
    lines = HEADER + run_mock(script).splitlines() + ["2026-10-18 06:31:00 Session closed with reason 0"]
    (HERE / "dump_mock.log").write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8"))
    print(HERE / "dump_mock.log", len(lines))


if __name__ == "__main__":
    main()
