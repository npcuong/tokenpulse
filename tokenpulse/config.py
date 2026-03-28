"""Config loader for TokenPulse."""

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "tokenpulse" / "config.yaml"

DEFAULTS: dict = {
    "refresh_interval": 300,  # seconds
    "warning_threshold": 80,  # percent
    "providers": {
        "claude": {
            "enabled": False,
            "mode": "manual",
            "api_key": "",
            "limit_tokens": 1_000_000,
            "used_tokens": 0,
        },
        "openai": {
            "enabled": False,
            "mode": "api",
            "api_key": "",
            "limit_usd": 20.0,
            "used_usd": 0.0,
        },
        "gemini": {
            "enabled": False,
            "mode": "manual",
            "api_key": "",
            "limit_tokens": 1_000_000,
            "used_tokens": 0,
        },
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


class Config:
    def __init__(self, path: Path = DEFAULT_CONFIG_PATH):
        self.path = path
        self._data: dict = self._load()

    def _load(self) -> dict:
        if self.path.exists():
            try:
                user = yaml.safe_load(self.path.read_text()) or {}
                return _deep_merge(DEFAULTS, user)
            except Exception as e:
                print(f"[TokenPulse] Config error: {e} — using defaults.")
        return DEFAULTS.copy()

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def reload(self) -> None:
        self._data = self._load()

    @property
    def warning_threshold(self) -> float:
        return float(self._data.get("warning_threshold", 80))

    @property
    def refresh_interval(self) -> int:
        return int(self._data.get("refresh_interval", 300))

    @property
    def providers(self) -> dict:
        return self._data.get("providers", {})

    def create_example(self) -> None:
        """Write an example config to the config directory."""
        example = Path(__file__).parent.parent / "config.example.yaml"
        dest = self.path.parent / "config.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() and example.exists():
            dest.write_text(example.read_text())
            print(f"[TokenPulse] Created config at {dest}")
