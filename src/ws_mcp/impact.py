"""Cross-reference a game version diff with cached mods and drafts."""

from __future__ import annotations

import re
from typing import Any

from . import core, snapshots
from .config import Config

UNIT_RE = re.compile(r"unitType\s*\[\s*(\d+)\s*\]")
BUILD_RE = re.compile(r"\bbuild\s*\[\s*(\d+)\s*\]")
RESEARCH_RE = re.compile(r"researches(?:\s*\.\s*list)?\s*\[\s*(\d+)\s*\]")
UPGRADE_RE = re.compile(r"upgrades\s*\[\s*(\d+)\s*\]")
F_RE = re.compile(r"\b(f_[A-Za-z0-9_]+)\b")


def _segments(path: str) -> list[str]:
    return [s for s in re.split(r"[.\[\]]+", path) if s and s not in ("n", "visual", "root") and not s.isdigit()]


def mod_impact(cfg: Config, a: str | None = None, b: str | None = None, limit: int = 200,
               include_drafts: bool = True) -> dict[str, Any]:
    d = snapshots.diff_versions(cfg, a, b, limit=1_000_000, write_full=False)
    if d.get("diff", True) is None:
        return {"snapshots": d["snapshots"], "impact": None, "message": d["message"]}
    g, api = d["gameplay"], d["api"]
    units = {str(u["id"]): f"unit type {u['id']} removed ({u['unit']})" for u in g["units"]["removed"]}
    units |= {str(u["id"]): f"unit type {u['id']} renamed {u['old']} -> {u['new']}" for u in g["units"]["renamed"]}
    builds = {str(x["build_id"]): f"build rule {x['build_id']} {x['op']} ({x['unit']})" for x in g["build_rules"]}
    for x in g["build_rules"]:
        if x.get("unit_id") is not None and str(x["unit_id"]) not in units:
            units[str(x["unit_id"])] = f"build rule of unit type {x['unit_id']} {x['op']} ({x['unit']})"
    researches = {str(x["id"]): f"research {x['id']} {x['op']}" for x in g["researches"]}
    upgrades = {str(x["id"]): f"upgrade {x['id']} {x['op']}" for x in g["upgrades"]}
    funcs: dict[str, str] = {}
    fields: list[tuple[re.Pattern, str]] = []
    for r in api["removed_paths"]:
        segs = _segments(r["path"])
        if not segs:
            continue
        if segs[-1].startswith("f_"):
            funcs.setdefault(segs[-1], f"API removed: {r['path']}")
        elif len(segs) >= 2:
            pat = r"(?<![A-Za-z0-9_])" + r"(?:\s*\[[^\]]*\]\s*)*[._]".join(map(re.escape, segs[-2:])) + r"(?![A-Za-z0-9_])"
            fields.append((re.compile(pat), f"API removed: {r['path']}"))
    for c in api["changed_paths"]:
        segs = _segments(c["path"])
        if segs and segs[-1].startswith("f_"):
            old, new = c["old"].get("signature"), c["new"].get("signature")
            funcs.setdefault(segs[-1], f"API changed: {c['path']} {old} -> {new}")
    hits: list[dict[str, Any]] = []
    per_reason: dict[str, int] = {}
    files = core.latest_sources(cfg, include_drafts=include_drafts)
    cap = max(1, min(int(limit), 5000))
    for f in files:
        for i, line in enumerate(core._read_text(f["path"]).splitlines(), 1):
            if line.lstrip().startswith("--"):
                continue
            reasons = []
            for rx, table in ((UNIT_RE, units), (BUILD_RE, builds), (RESEARCH_RE, researches), (UPGRADE_RE, upgrades)):
                if table:
                    reasons += [table[m] for m in rx.findall(line) if m in table]
            if funcs:
                reasons += [funcs[n] for n in F_RE.findall(line) if n in funcs]
            for rx, why in fields:
                if rx.search(line):
                    reasons.append(why)
            for why in dict.fromkeys(reasons):
                per_reason[why] = per_reason.get(why, 0) + 1
                if len(hits) < cap:
                    hits.append({"mod": f"mod-{f['id']}", "source": f["source"], "version": f["version"],
                                 "file": f["file"], "line": i, "code": line.strip()[:200], "reason": why})
    mods = sorted({h["mod"] + (" (draft)" if h["source"] == "draft" else "") for h in hits})
    return {"a": d["a"], "b": d["b"], "engine": d["engine"], "files_scanned": len(files),
            "checked": {"unit_ids": len(units), "build_ids": len(builds), "research_ids": len(researches),
                        "upgrade_ids": len(upgrades), "api_functions": len(funcs), "api_fields": len(fields)},
            "mods_affected": mods, "hits_total": sum(per_reason.values()), "hits": hits,
            "by_reason": dict(sorted(per_reason.items(), key=lambda x: -x[1])[:cap]),
            "note": ("Static text match on latest cached versions and drafts. Unit type ids are matched as "
                     "unitType[<id>] with ids from legacyIds.json units; build rules as build[<index>]; "
                     "researches as researches[.list][<index>]; upgrades as upgrades[<index>].")}
