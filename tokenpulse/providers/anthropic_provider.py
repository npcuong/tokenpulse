"""
Claude (Anthropic) usage provider.

Modes:
  proxy  — run a local HTTP proxy; point your SDK to http://127.0.0.1:7778
           and every API call is counted automatically.
  manual — enter used_tokens yourself (from console.anthropic.com/settings/usage)

Anthropic does not expose a public billing/usage REST endpoint.
The proxy mode is the only way to auto-count tokens with just an API key.

Proxy setup (one-time):
  export ANTHROPIC_BASE_URL=http://127.0.0.1:7778
  # or in Python:
  client = anthropic.Anthropic(base_url="http://127.0.0.1:7778")
"""

from .base import BaseProvider, UsageData

DASHBOARD = "https://console.anthropic.com/settings/usage"


class AnthropicProvider(BaseProvider):
    DISPLAY_NAME = "Claude"

    def __init__(self, config: dict, storage=None):
        super().__init__(config)
        self._storage = storage  # injected by app.py

    @property
    def dashboard_url(self) -> str:
        return DASHBOARD

    def fetch_usage(self) -> UsageData:
        used = self._storage.get_monthly_usage("claude") if self._storage else 0
        return UsageData(
            provider="claude",
            display_name=self.DISPLAY_NAME,
            used=used,
            limit=self.limit,
            source="proxy" if self.config.get("mode") == "proxy" else "manual",
        )

    def set_manual_usage(self, tokens: int) -> None:
        if self._storage:
            self._storage.set_manual_usage("claude", tokens)
