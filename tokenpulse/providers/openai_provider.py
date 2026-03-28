"""
OpenAI / ChatGPT usage provider.

Uses OpenAI's billing dashboard API:
  GET /v1/dashboard/billing/subscription  → hard_limit_usd
  GET /v1/dashboard/billing/usage         → total_usage (cents)

These endpoints require an API key with billing read access.
If they return 404 (deprecated for some plan types), falls back to manual mode.

Set mode: "manual" and used_usd / limit_usd in config for manual tracking.
Dashboard: https://platform.openai.com/account/usage
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

import requests

from .base import BaseProvider, UsageData


class OpenAIProvider(BaseProvider):
    DISPLAY_NAME = "ChatGPT"
    DASHBOARD = "https://platform.openai.com/account/usage"
    _BASE = "https://api.openai.com/v1"

    @property
    def dashboard_url(self) -> str:
        return self.DASHBOARD

    def fetch_usage(self) -> UsageData:
        mode = self.config.get("mode", "api")

        if mode == "api" and self.api_key:
            result = self._fetch_from_api()
            if result:
                return result

        # Manual fallback
        used_usd = self.config.get("used_usd", 0.0)
        limit_usd = self.cost_limit or self.config.get("limit_usd", 0.0)
        return UsageData(
            provider="openai",
            display_name=self.DISPLAY_NAME,
            used=0,
            limit=0,
            cost_used=used_usd,
            cost_limit=limit_usd,
            source="manual",
        )

    # ── private ──────────────────────────────────────────────────────────────

    def _fetch_from_api(self) -> Optional[UsageData]:
        headers = {"Authorization": f"Bearer {self.api_key}"}

        # Get subscription limit
        limit_usd = 0.0
        try:
            sub_resp = requests.get(
                f"{self._BASE}/dashboard/billing/subscription",
                headers=headers,
                timeout=8,
            )
            if sub_resp.status_code == 200:
                limit_usd = sub_resp.json().get("hard_limit_usd", 0.0)
            elif sub_resp.status_code in (401, 403):
                return UsageData(
                    provider="openai",
                    display_name=self.DISPLAY_NAME,
                    error="Invalid API key or insufficient permissions",
                )
        except Exception:
            return None

        # Get usage for current billing cycle (current month)
        now = datetime.now(timezone.utc)
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now + timedelta(days=1)

        try:
            usage_resp = requests.get(
                f"{self._BASE}/dashboard/billing/usage",
                headers=headers,
                params={
                    "start_date": start.strftime("%Y-%m-%d"),
                    "end_date": end.strftime("%Y-%m-%d"),
                },
                timeout=8,
            )
            if usage_resp.status_code == 200:
                # total_usage is in cents
                total_cents = usage_resp.json().get("total_usage", 0)
                cost_used = total_cents / 100.0
                return UsageData(
                    provider="openai",
                    display_name=self.DISPLAY_NAME,
                    used=0,
                    limit=0,
                    cost_used=cost_used,
                    cost_limit=limit_usd or self.cost_limit,
                    source="api",
                )
        except Exception:
            pass

        return None
