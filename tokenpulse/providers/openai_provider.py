"""
OpenAI / ChatGPT usage provider.

Mode: api (auto) — fetches billing usage from OpenAI's dashboard API.
  Endpoints used:
    GET /v1/dashboard/billing/subscription → hard_limit_usd
    GET /v1/dashboard/billing/usage        → total_usage (cents, current month)

  Works with any standard OpenAI API key (sk-...).
  Dashboard: https://platform.openai.com/account/usage

Mode: manual — set used_usd + limit_usd in config.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

from .base import BaseProvider, UsageData

_BASE = "https://api.openai.com/v1"


class OpenAIProvider(BaseProvider):
    DISPLAY_NAME = "ChatGPT"
    DASHBOARD = "https://platform.openai.com/account/usage"

    def __init__(self, config: dict, storage=None):
        super().__init__(config, storage=storage)
        self._storage = storage

    @property
    def dashboard_url(self) -> str:
        return self.DASHBOARD

    def fetch_usage(self) -> UsageData:
        if self.api_key and self.config.get("mode", "api") == "api":
            result = self._fetch_billing()
            if result:
                return result

        # Extension-provided cost fallback
        ext_cost = (
            self._storage.get("openai_cost_used")
            if self._storage is not None
            else None
        )
        if ext_cost is not None:
            ext_limit = (
                self._storage.get("openai_cost_limit") or self.cost_limit
            ) if self._storage is not None else self.cost_limit
            return UsageData(
                provider="openai",
                display_name=self.DISPLAY_NAME,
                cost_used=float(ext_cost),
                cost_limit=float(ext_limit),
                source="extension",
            )

        # Manual fallback
        return UsageData(
            provider="openai",
            display_name=self.DISPLAY_NAME,
            cost_used=self.config.get("used_usd", 0.0),
            cost_limit=self.cost_limit,
            source="manual",
        )

    # ── private ──────────────────────────────────────────────────────────────

    def _fetch_billing(self) -> Optional[UsageData]:
        headers = {"Authorization": f"Bearer {self.api_key}"}

        # ── 1. Get hard limit ────────────────────────────────────────────────
        limit_usd = self.cost_limit
        try:
            sub = requests.get(
                f"{_BASE}/dashboard/billing/subscription",
                headers=headers,
                timeout=8,
            )
            if sub.status_code == 200:
                limit_usd = float(sub.json().get("hard_limit_usd", 0) or 0)
            elif sub.status_code in (401, 403):
                return UsageData(
                    provider="openai",
                    display_name=self.DISPLAY_NAME,
                    error="Invalid API key or no billing access",
                )
        except Exception:
            return None

        # ── 2. Get usage for current billing month ────────────────────────────
        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now + timedelta(days=1)

        try:
            usage = requests.get(
                f"{_BASE}/dashboard/billing/usage",
                headers=headers,
                params={
                    "start_date": start.strftime("%Y-%m-%d"),
                    "end_date": end.strftime("%Y-%m-%d"),
                },
                timeout=8,
            )
            if usage.status_code == 200:
                cents = usage.json().get("total_usage", 0) or 0
                return UsageData(
                    provider="openai",
                    display_name=self.DISPLAY_NAME,
                    cost_used=cents / 100.0,
                    cost_limit=limit_usd or self.cost_limit,
                    source="api",
                )
        except Exception:
            pass

        return None
