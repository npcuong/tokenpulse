"""Local JSON storage — monthly token accumulators + manual overrides."""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_STORE_PATH = Path.home() / ".config" / "tokenpulse" / "usage.json"


class Storage:
    def __init__(self, path: Path = _STORE_PATH):
        self.path = path
        self._lock = threading.Lock()
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

    # ── Generic ───────────────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._save()

    # ── Monthly accumulator ───────────────────────────────────────────────────

    def _current_month(self) -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def increment_usage(self, provider: str, tokens: int) -> int:
        """Add tokens to the current month's counter. Thread-safe. Returns new total."""
        month = self._current_month()
        month_key = f"{provider}_month"
        count_key = f"{provider}_used"

        with self._lock:
            if self._data.get(month_key) != month:
                # New billing period — reset
                self._data[month_key] = month
                self._data[count_key] = 0
            self._data[count_key] = self._data.get(count_key, 0) + tokens
            total = self._data[count_key]
            self._save()

        return total

    def get_monthly_usage(self, provider: str) -> int:
        """Return accumulated tokens for the current month (resets on new month)."""
        month = self._current_month()
        with self._lock:
            if self._data.get(f"{provider}_month") != month:
                return 0
            return int(self._data.get(f"{provider}_used", 0))

    # ── Manual override ───────────────────────────────────────────────────────

    def set_manual_usage(self, provider: str, tokens: int) -> None:
        month = self._current_month()
        with self._lock:
            self._data[f"{provider}_month"] = month
            self._data[f"{provider}_used"] = tokens
            self._save()

    def get_manual_usage(self, provider: str) -> int:
        return self.get_monthly_usage(provider)
