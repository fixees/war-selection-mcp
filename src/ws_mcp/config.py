"""Paths and environment configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_GAME_DIR = r"C:\Program Files (x86)\Steam\steamapps\common\War Selection"


def _env_path(name: str) -> Path | None:
    value = os.environ.get(name, "").strip().strip('"')
    return Path(value) if value else None


@dataclass
class Config:
    game_dir: Path
    log_path_override: Path | None = None
    extra_log_dirs: list[Path] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "Config":
        game = _env_path("WS_GAME_DIR") or Path(DEFAULT_GAME_DIR)
        return cls(game_dir=game, log_path_override=_env_path("WS_LOG_PATH"))

    @property
    def mods_dir(self) -> Path:
        return self.game_dir / "modsStorage"

    @property
    def draft_dir(self) -> Path:
        return self.mods_dir / "draft"

    @property
    def data_dir(self) -> Path:
        """Per-user data folder for files this server writes (imported API index). Never the game folder."""
        override = _env_path("WS_MCP_DATA_DIR")
        if override:
            return override
        local = _env_path("LOCALAPPDATA")
        if local:
            return local / "war-selection-mcp"
        xdg = _env_path("XDG_DATA_HOME")
        return (xdg or Path.home() / ".local" / "share") / "war-selection-mcp"

    @property
    def project_dir(self) -> Path:
        return self.game_dir / "Cache" / "Projects" / "WarSelection"

    def log_candidates(self, filename: str = "log.txt") -> list[Path]:
        """Likely locations of gen/log.txt, in search order."""
        cands: list[Path] = []
        if self.log_path_override:
            p = self.log_path_override
            cands.append(p if p.suffix else p / filename)
        cands += [self.game_dir / "gen" / filename, self.game_dir / filename]
        local = _env_path("LOCALAPPDATA")
        if local:
            for sub in ("War Selection", "WarSelection", "Glyph Worlds/War Selection", "GlyphWorlds/WarSelection"):
                cands += [local / sub / "gen" / filename, local / sub / filename]
        profile = _env_path("USERPROFILE") or Path.home()
        for docs in (profile / "Documents", profile / "OneDrive" / "Documents"):
            for sub in ("War Selection", "WarSelection", "My Games/War Selection"):
                cands += [docs / sub / "gen" / filename, docs / sub / filename]
        for d in self.extra_log_dirs:
            cands.append(d / filename)
        seen: set[str] = set()
        out = []
        for c in cands:
            key = str(c).lower()
            if key not in seen:
                seen.add(key)
                out.append(c)
        return out
