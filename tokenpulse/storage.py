"""Local JSON storage for manual usage overrides."""

import json
from pathlib import Path
from typing import Any

_STORE_PATH = Path.home() / ".config" / "tokenpulse" / "usage.json"


class Storage:
    def __init__(self, path: Path = _STORE_PATH):
        self.path = path
        self._data: dict = self._load()

    def _load(self) -> dict:
        try:
            if self.path.exists():
                return json.loads(self.path.read_text())
        except Exception:
            pass
        return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2))

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._save()

    def get_manual_usage(self, provider: str) -> int:
        return int(self._data.get(f"{provider}_used", 0))

    def set_manual_usage(self, provider: str, tokens: int) -> None:
        self.set(f"{provider}_used", tokens)
