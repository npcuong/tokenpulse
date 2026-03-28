from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UsageData:
    provider: str
    display_name: str
    used: int = 0          # tokens used this period
    limit: int = 0         # token limit this period
    cost_used: float = 0.0 # USD spent (optional)
    cost_limit: float = 0.0
    error: Optional[str] = None
    source: str = "api"    # "api" | "manual" | "cache"

    @property
    def percent(self) -> float:
        if self.limit <= 0:
            # cost-based fallback
            if self.cost_limit > 0:
                return min(self.cost_used / self.cost_limit * 100, 100.0)
            return 0.0
        return min(self.used / self.limit * 100, 100.0)

    @property
    def is_warning(self) -> bool:
        return self.percent >= 80.0

    @property
    def is_critical(self) -> bool:
        return self.percent >= 95.0

    @property
    def status_emoji(self) -> str:
        if self.error:
            return "❓"
        if self.is_critical:
            return "🔴"
        if self.is_warning:
            return "🟡"
        return "🟢"


class BaseProvider(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.api_key: str = config.get("api_key", "")
        self.limit: int = config.get("limit_tokens", 0)
        self.cost_limit: float = config.get("limit_usd", 0.0)

    @abstractmethod
    def fetch_usage(self) -> UsageData:
        """Fetch current usage from the provider API or local store."""

    @property
    @abstractmethod
    def dashboard_url(self) -> str:
        """URL to open when user wants to see full dashboard."""
