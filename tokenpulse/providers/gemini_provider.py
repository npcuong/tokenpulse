"""
Google Gemini usage provider.

Modes:
  proxy  — run a local HTTP proxy; point your SDK to http://127.0.0.1:7779
           and every API call is counted automatically.
  manual — enter used_tokens yourself (from aistudio.google.com)

Google AI Studio (AIzaSy... API keys) does NOT expose accumulated usage via REST.
The Cloud Monitoring API for Vertex AI requires OAuth2 service accounts, not API keys.
The proxy mode is the recommended approach for auto-counting.

Proxy setup (one-time):
  # google-generativeai SDK
  import google.generativeai as genai
  from google.api_core.client_options import ClientOptions
  genai.configure(
      api_key="YOUR_KEY",
      client_options=ClientOptions(api_endpoint="127.0.0.1:7779"),
      transport="rest",
  )

  # Or set env var for HTTP client override
  export GOOGLE_AI_BASE_URL=http://127.0.0.1:7779

Time frame:
  - AI Studio free tier: daily quota (tokens/min, requests/day)
  - Paid / Vertex AI:    monthly quota
  Set reset_period: "daily" or "monthly" in config (default: daily).

Dashboard: https://aistudio.google.com/
"""

from .base import BaseProvider, UsageData

DASHBOARD = "https://aistudio.google.com/"


class GeminiProvider(BaseProvider):
    DISPLAY_NAME = "Gemini"

    def __init__(self, config: dict, storage=None):
        super().__init__(config)
        self._storage = storage

    @property
    def dashboard_url(self) -> str:
        return DASHBOARD

    def fetch_usage(self) -> UsageData:
        used = self._storage.get_monthly_usage("gemini") if self._storage else 0
        return UsageData(
            provider="gemini",
            display_name=self.DISPLAY_NAME,
            used=used,
            limit=self.limit,
            source="proxy" if self.config.get("mode") == "proxy" else "manual",
        )

    def set_manual_usage(self, tokens: int) -> None:
        if self._storage:
            self._storage.set_manual_usage("gemini", tokens)
