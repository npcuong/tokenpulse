"""
Google Gemini usage provider.

Supports two modes:
  1. quota_api — uses Google Cloud API to check quota consumption
                 (requires a service account or gcloud credentials)
  2. manual    — user enters current usage manually in config or via menu

Google AI Studio free tier does not expose a usage REST endpoint.
For paid Vertex AI users, quota monitoring is via Cloud Monitoring API.

Dashboard: https://aistudio.google.com/  (free tier)
           https://console.cloud.google.com/apis/api/generativelanguage.googleapis.com
"""

from typing import Optional

import requests

from .base import BaseProvider, UsageData


class GeminiProvider(BaseProvider):
    DISPLAY_NAME = "Gemini"
    DASHBOARD = "https://aistudio.google.com/"

    @property
    def dashboard_url(self) -> str:
        project = self.config.get("gcp_project")
        if project:
            return (
                f"https://console.cloud.google.com/apis/api/"
                f"generativelanguage.googleapis.com/quotas?project={project}"
            )
        return self.DASHBOARD

    def fetch_usage(self) -> UsageData:
        mode = self.config.get("mode", "manual")

        if mode == "quota_api":
            result = self._fetch_quota_api()
            if result:
                return result

        # Manual / config-based fallback
        used = self.config.get("used_tokens", 0)
        limit = self.limit or self.config.get("limit_tokens", 0)

        return UsageData(
            provider="gemini",
            display_name=self.DISPLAY_NAME,
            used=used,
            limit=limit,
            source="manual",
        )

    # ── private ──────────────────────────────────────────────────────────────

    def _fetch_quota_api(self) -> Optional[UsageData]:
        """
        Uses Google Cloud Monitoring API to fetch Gemini quota usage.
        Requires GOOGLE_APPLICATION_CREDENTIALS or api_key in config.
        """
        project = self.config.get("gcp_project")
        api_key = self.api_key

        if not project or not api_key:
            return None

        try:
            # Cloud Monitoring timeseries for Gemini quota
            url = (
                f"https://monitoring.googleapis.com/v3/projects/{project}"
                f"/timeSeries"
            )
            resp = requests.get(
                url,
                params={
                    "filter": (
                        'metric.type="serviceruntime.googleapis.com/quota/rate/net_usage"'
                        ' AND resource.labels.service="generativelanguage.googleapis.com"'
                    ),
                    "interval.startTime": _month_start_rfc3339(),
                    "interval.endTime": _now_rfc3339(),
                },
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            if resp.status_code == 200:
                series = resp.json().get("timeSeries", [])
                if series:
                    points = series[0].get("points", [])
                    if points:
                        used = int(points[0].get("value", {}).get("int64Value", 0))
                        return UsageData(
                            provider="gemini",
                            display_name=self.DISPLAY_NAME,
                            used=used,
                            limit=self.limit,
                            source="api",
                        )
        except Exception:
            pass

        return None


def _now_rfc3339() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _month_start_rfc3339() -> str:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
