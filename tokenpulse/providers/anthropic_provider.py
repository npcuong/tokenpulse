"""
Anthropic / Claude usage provider.

Anthropic does not expose a public billing/quota REST endpoint at this time.
TokenPulse supports two modes:
  1. manual  — user sets `used_tokens` in config.yaml (or via Edit Usage menu)
  2. api_key — tracks every API call's usage field and accumulates locally
               (only counts calls made while TokenPulse is running)

Set mode: "manual" in your config to enter current usage yourself after
checking https://console.anthropic.com/settings/usage
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

from .base import BaseProvider, UsageData

_CACHE_FILE = Path.home() / ".config" / "tokenpulse" / "cache_claude.json"


class AnthropicProvider(BaseProvider):
    DISPLAY_NAME = "Claude"
    DASHBOARD = "https://console.anthropic.com/settings/usage"

    @property
    def dashboard_url(self) -> str:
        return self.DASHBOARD

    def fetch_usage(self) -> UsageData:
        mode = self.config.get("mode", "manual")

        # ── 1. Try official usage API (may become available in future) ──────
        if mode == "api" and self.api_key:
            result = self._try_api()
            if result:
                return result

        # ── 2. Manual mode: read from cache file (updated by user or app) ───
        cached = self._load_cache()
        used = cached.get("used_tokens", self.config.get("used_tokens", 0))
        month = cached.get("month", "")

        # Reset counter if we've moved to a new month
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        if month and month != current_month:
            used = 0
            self._save_cache(used)

        return UsageData(
            provider="claude",
            display_name=self.DISPLAY_NAME,
            used=used,
            limit=self.limit,
            source="manual" if mode == "manual" else "cache",
        )

    def record_api_usage(self, tokens: int) -> None:
        """Call this after each API request to accumulate token counts."""
        cached = self._load_cache()
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        if cached.get("month") != current_month:
            cached = {"used_tokens": 0, "month": current_month}
        cached["used_tokens"] = cached.get("used_tokens", 0) + tokens
        self._save_cache(cached["used_tokens"])

    def set_manual_usage(self, tokens: int) -> None:
        self._save_cache(tokens)

    # ── private ──────────────────────────────────────────────────────────────

    def _try_api(self) -> UsageData | None:
        """
        Attempt to hit Anthropic's usage endpoint if it exists.
        Returns None if unavailable so we fall through to manual.
        """
        try:
            resp = requests.get(
                "https://api.anthropic.com/v1/usage",
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
                timeout=8,
            )
            if resp.status_code == 200:
                data = resp.json()
                used = data.get("input_tokens", 0) + data.get("output_tokens", 0)
                return UsageData(
                    provider="claude",
                    display_name=self.DISPLAY_NAME,
                    used=used,
                    limit=self.limit,
                    source="api",
                )
        except Exception:
            pass
        return None

    def _load_cache(self) -> dict:
        try:
            if _CACHE_FILE.exists():
                return json.loads(_CACHE_FILE.read_text())
        except Exception:
            pass
        return {}

    def _save_cache(self, tokens: int) -> None:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        _CACHE_FILE.write_text(
            json.dumps({"used_tokens": tokens, "month": current_month})
        )
