from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, fields
from pathlib import Path


def default_home() -> Path:
    override = os.environ.get("SCRIPTS_FACTORY_HOME")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "win32":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return root / "scripts-factory"
    root = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state"))
    return root / "scripts-factory"


@dataclass(slots=True)
class Settings:
    home: Path
    database_path: Path
    bundles_dir: Path
    candidates_dir: Path
    provider: str = "fake"
    model: str | None = None
    max_concurrency: int = 3
    max_depth: int = 3
    max_nodes: int = 12
    session_timeout_seconds: int = 1800

    @classmethod
    def load(cls, config_path: Path | None = None) -> "Settings":
        home = default_home()
        path = config_path or Path(os.environ.get("SCRIPTS_FACTORY_CONFIG", home / "config.toml"))
        raw: dict = {}
        if path.is_file():
            raw = tomllib.loads(path.read_text(encoding="utf-8"))
        core = raw.get("core", {})
        paths = raw.get("paths", {})
        values = {
            "home": home,
            "database_path": Path(os.environ.get("SCRIPTS_FACTORY_DB", paths.get("database", home / "state.db"))),
            "bundles_dir": Path(os.environ.get("SCRIPTS_FACTORY_BUNDLES_DIR", paths.get("bundles", home / "bundles"))),
            "candidates_dir": Path(os.environ.get("SCRIPTS_FACTORY_CANDIDATES_DIR", paths.get("candidates", home / "candidates"))),
            "provider": os.environ.get("SCRIPTS_FACTORY_PROVIDER", core.get("provider", "fake")),
            "model": os.environ.get("SCRIPTS_FACTORY_MODEL", core.get("model")),
            "max_concurrency": int(os.environ.get("SCRIPTS_FACTORY_MAX_CONCURRENCY", core.get("max_concurrency", 3))),
            "max_depth": int(os.environ.get("SCRIPTS_FACTORY_MAX_DEPTH", core.get("max_depth", 3))),
            "max_nodes": int(os.environ.get("SCRIPTS_FACTORY_MAX_NODES", core.get("max_nodes", 12))),
            "session_timeout_seconds": int(os.environ.get("SCRIPTS_FACTORY_SESSION_TIMEOUT", core.get("session_timeout_seconds", 1800))),
        }
        settings = cls(**values)
        settings.validate()
        return settings

    def validate(self) -> None:
        for field_name in ("max_concurrency", "max_depth", "max_nodes", "session_timeout_seconds"):
            if getattr(self, field_name) < 1:
                raise ValueError(f"{field_name} must be positive")

    def ensure_directories(self) -> None:
        for path in (self.home, self.database_path.parent, self.bundles_dir, self.candidates_dir):
            path.mkdir(parents=True, exist_ok=True)

    def public_dict(self) -> dict[str, object]:
        return {field.name: str(getattr(self, field.name)) if isinstance(getattr(self, field.name), Path) else getattr(self, field.name) for field in fields(self)}
