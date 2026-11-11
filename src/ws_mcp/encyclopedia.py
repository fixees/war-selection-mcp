"""In-game encyclopedia catalog (Cache/Content/interfaces/WarSelection/encyclopedia).

Verified on disk 2026-10-30 (engine 277): catalog.json holds countries, eras, rosters,
entity keys (kind, icon, nameKey) and researches (name/text keys). It does **not** store
stats or prices — those stay in Cache/Projects/WarSelection/gameplay.json (unit_lookup).
Localization is `localization/<lang>.loc` (`<*key>value` records).
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import Config
from .core import ToolError

LOC_KEY_RE = re.compile(r"<\*([^<>]+)>")
SAFE_LANG_RE = re.compile(r"^[a-z]{2}$")


def encyclopedia_dir(cfg: Config) -> Path:
    return cfg.game_dir / "Cache" / "Content" / "interfaces" / "WarSelection" / "encyclopedia"


def _mtime(p: Path) -> str | None:
    try:
        return datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except OSError:
        return None


def parse_loc(text: str) -> dict[str, str]:
    """Parse `<*key>value` records. The next `<*` starts a new key."""
    out: dict[str, str] = {}
    matches = list(LOC_KEY_RE.finditer(text))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        out[m.group(1)] = text[m.end():end].rstrip("\r\n")
    return out


def load_loc(folder: Path, lang: str = "en") -> dict[str, str]:
    if not SAFE_LANG_RE.match(lang):
        raise ToolError("lang must be a two-letter code, e.g. en or ru")
    p = folder / "localization" / f"{lang}.loc"
    if not p.is_file():
        return {}
    return parse_loc(p.read_text(encoding="utf-8-sig", errors="replace"))


def load_catalog(cfg: Config) -> dict[str, Any] | None:
    d = encyclopedia_dir(cfg)
    p = d / "catalog.json"
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as e:
        raise ToolError(f"Cannot read encyclopedia catalog: {e}") from e
    if not isinstance(data, dict):
        raise ToolError("encyclopedia catalog.json is not a JSON object")
    return data


def _entity_places(catalog: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    places: dict[str, list[dict[str, Any]]] = {}
    for roster in catalog.get("rosters") or []:
        if not isinstance(roster, dict):
            continue
        country = roster.get("countryKey")
        era = roster.get("eraId")
        def add(key: str | None) -> None:
            if not key:
                return
            rec = {"country": country, "era_id": era}
            lst = places.setdefault(key, [])
            if rec not in lst:
                lst.append(rec)
        for b in roster.get("buildings") or []:
            if not isinstance(b, dict):
                continue
            add(b.get("entityKey"))
            for prod in b.get("products") or []:
                if isinstance(prod, dict):
                    add(prod.get("entityKey"))
            for up in b.get("upgrades") or []:
                if isinstance(up, dict):
                    add(up.get("entityKey"))
            for form in b.get("forms") or []:
                if isinstance(form, dict):
                    add(form.get("entityKey"))
    return places


def encyclopedia_info(cfg: Config) -> dict[str, Any]:
    d = encyclopedia_dir(cfg)
    cat_p = d / "catalog.json"
    if not cat_p.is_file():
        return {
            "present": False,
            "path": str(d),
            "note": ("No encyclopedia catalog. Expected Cache/Content/interfaces/"
                     "WarSelection/encyclopedia/catalog.json (present on engine 277, 2026-10-30)."),
        }
    data = load_catalog(cfg) or {}
    loc_dir = d / "localization"
    langs = sorted(p.stem for p in loc_dir.glob("*.loc")) if loc_dir.is_dir() else []
    ents = data.get("entities") if isinstance(data.get("entities"), dict) else {}
    kinds: dict[str, int] = {}
    for e in ents.values():
        if isinstance(e, dict):
            k = str(e.get("kind") or "?")
            kinds[k] = kinds.get(k, 0) + 1
    return {
        "present": True,
        "path": str(d),
        "catalog": str(cat_p),
        "catalog_version": data.get("catalogVersion"),
        "mtime": _mtime(cat_p),
        "entities": len(ents),
        "kinds": kinds,
        "researches": len(data.get("researches") or {}),
        "countries": [c.get("key") for c in (data.get("countries") or []) if isinstance(c, dict)],
        "eras": data.get("eras") or [],
        "rosters": len(data.get("rosters") or []),
        "languages": langs,
        "note": ("Catalog is the authored structure (names, icons, country/era rosters). "
                 "It does not contain stats or prices; use unit_lookup / gameplay.json for those. "
                 "The in-game encyclopedia UI (announced for a later menu update) reads this catalog "
                 "plus live gameplay data."),
    }


def encyclopedia_lookup(cfg: Config, query: str, lang: str = "en", kind: str | None = None,
                        limit: int = 20) -> dict[str, Any]:
    """Search encyclopedia entities, researches and countries by key or localized name."""
    q = str(query).strip()
    if not q:
        raise ToolError("Empty query.")
    limit = max(1, min(int(limit), 200))
    data = load_catalog(cfg)
    if data is None:
        return {"found": False, "query": q, "matches": [],
                "note": "Encyclopedia catalog not found under the game folder."}
    loc = load_loc(encyclopedia_dir(cfg), lang)
    ql = q.lower()
    places = _entity_places(data)
    matches: list[dict[str, Any]] = []

    def name_of(key: str | None) -> str | None:
        if not key:
            return None
        return loc.get(key)

    def hit(hay: str | None) -> bool:
        return bool(hay) and ql in hay.lower()

    kind_f = kind.strip().lower() if kind else None

    for key, e in (data.get("entities") or {}).items():
        if not isinstance(e, dict):
            continue
        ekind = e.get("kind")
        if kind_f and str(ekind).lower() != kind_f:
            continue
        nm = name_of(e.get("nameKey"))
        if hit(key) or hit(nm) or hit(e.get("nameKey")):
            matches.append({
                "type": "entity",
                "key": key,
                "kind": ekind,
                "name": nm,
                "name_key": e.get("nameKey"),
                "icon": e.get("iconAsset"),
                "places": places.get(key, []),
            })

    if not kind_f or kind_f in ("research", "researches"):
        researches = data.get("researches") or {}
        if isinstance(researches, dict):
            for rid, r in researches.items():
                if not isinstance(r, dict):
                    continue
                nm = name_of(r.get("nameKey"))
                text = name_of(r.get("textKey"))
                if hit(str(rid)) or hit(nm) or hit(text) or hit(r.get("nameKey")):
                    matches.append({
                        "type": "research",
                        "id": r.get("id", rid),
                        "name": nm,
                        "text": text,
                        "name_key": r.get("nameKey"),
                        "icon": r.get("iconAsset"),
                    })

    if not kind_f or kind_f in ("country", "countries"):
        for c in data.get("countries") or []:
            if not isinstance(c, dict):
                continue
            nm = name_of(c.get("nameKey"))
            if hit(c.get("key") or "") or hit(nm):
                matches.append({
                    "type": "country",
                    "key": c.get("key"),
                    "name": nm,
                    "eras": c.get("eras") or [],
                    "name_key": c.get("nameKey"),
                })

    return {
        "found": True,
        "query": q,
        "lang": lang,
        "total": len(matches),
        "matches": matches[:limit],
        "truncated": len(matches) > limit,
        "note": "Names come from localization/*.loc. Stats and prices are not in the catalog.",
    }


def entity_meta(cfg: Config, path: str, lang: str = "en") -> dict[str, Any] | None:
    """Encyclopedia fields for a unit/building asset path, or None if catalog/path missing."""
    data = load_catalog(cfg)
    if data is None:
        return None
    ents = data.get("entities") or {}
    e = ents.get(path)
    if not isinstance(e, dict):
        return None
    loc = load_loc(encyclopedia_dir(cfg), lang)
    return {
        "name": loc.get(e["nameKey"]) if e.get("nameKey") else None,
        "kind": e.get("kind"),
        "name_key": e.get("nameKey"),
        "icon": e.get("iconAsset"),
        "places": _entity_places(data).get(path, []),
    }


def paths_matching_name(cfg: Config, query: str, lang: str = "en") -> list[str]:
    """Entity keys whose localized name or key contains query (case-insensitive)."""
    q = query.strip().lower()
    if not q:
        return []
    data = load_catalog(cfg)
    if data is None:
        return []
    loc = load_loc(encyclopedia_dir(cfg), lang)
    out = []
    for key, e in (data.get("entities") or {}).items():
        if not isinstance(e, dict):
            continue
        nm = loc.get(e["nameKey"]) if e.get("nameKey") else None
        if q in key.lower() or (nm and q in nm.lower()):
            out.append(key)
    return out
