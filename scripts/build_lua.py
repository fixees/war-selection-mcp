"""Regenerate lua/wsdump.lua and lua/wsdump-oneline.lua from the template and the bundled index."""

from __future__ import annotations

from pathlib import Path

from ws_mcp import core, dumpscript

OUT = Path(__file__).resolve().parent.parent / "lua"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    full = dumpscript.render(dump_id=dumpscript.SHIPPED_ID, index_entries=core.load_api_index())
    one = dumpscript.render(dump_id=dumpscript.SHIPPED_ID, compact=True, seeds=False)
    for name, res in (("wsdump.lua", full), ("wsdump-oneline.lua", one)):
        (OUT / name).write_text(res["script"] + "\n", encoding="utf-8", newline="\n")
        print(OUT / name, res["bytes"], "bytes")


if __name__ == "__main__":
    main()
