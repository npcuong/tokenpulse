"""TokenPulse — macOS menu bar app for AI token usage tracking."""

import subprocess
import threading
from typing import Dict

import rumps

from .config import Config
from .providers import get_providers
from .providers.base import UsageData
from .storage import Storage

# Provider icons (menu bar title)
ICONS = {"claude": "C", "openai": "G", "gemini": "✦"}
PROVIDER_LABELS = {"claude": "Claude", "openai": "ChatGPT", "gemini": "Gemini"}


class TokenPulseApp(rumps.App):
    def __init__(self):
        super().__init__("TokenPulse", title="🔮 ...", quit_button=None)

        self.config = Config()
        self.storage = Storage()
        self.providers = get_providers(self.config)

        # Track which providers already triggered 80% notification
        self._alerted: set = set()
        self._usage: Dict[str, UsageData] = {}

        self._build_menu()

        # Initial fetch (non-blocking)
        threading.Thread(target=self._refresh, daemon=True).start()

        # Periodic refresh timer
        self._timer = rumps.Timer(
            lambda _: threading.Thread(target=self._refresh, daemon=True).start(),
            self.config.refresh_interval,
        )
        self._timer.start()

    # ── Menu construction ─────────────────────────────────────────────────────

    def _build_menu(self):
        self.menu.clear()

        # Placeholder items for each provider (updated in _update_menu_items)
        for key in PROVIDER_LABELS:
            if key in self.providers:
                self.menu.add(rumps.MenuItem(PROVIDER_LABELS[key], callback=None))

        self.menu.add(None)  # separator

        refresh_item = rumps.MenuItem("↻  Refresh Now", callback=self.on_refresh)
        self.menu.add(refresh_item)

        self.menu.add(None)

        # Per-provider dashboard links
        dashboards = rumps.MenuItem("Open Dashboard")
        for key, provider in self.providers.items():
            item = rumps.MenuItem(
                PROVIDER_LABELS[key],
                callback=lambda _, url=provider.dashboard_url: self._open_url(url),
            )
            dashboards.add(item)
        self.menu.add(dashboards)

        # Manual usage editing (for manual-mode providers)
        edit_menu = rumps.MenuItem("Edit Usage")
        for key in self.providers:
            label = PROVIDER_LABELS[key]
            item = rumps.MenuItem(
                label,
                callback=lambda _, k=key: self.on_edit_usage(k),
            )
            edit_menu.add(item)
        self.menu.add(edit_menu)

        self.menu.add(None)
        self.menu.add(rumps.MenuItem("About TokenPulse", callback=self.on_about))
        self.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application))

    # ── Refresh logic ─────────────────────────────────────────────────────────

    def _refresh(self):
        new_usage: Dict[str, UsageData] = {}
        for key, provider in self.providers.items():
            try:
                new_usage[key] = provider.fetch_usage()
            except Exception as e:
                from .providers.base import UsageData

                new_usage[key] = UsageData(
                    provider=key,
                    display_name=PROVIDER_LABELS[key],
                    error=str(e),
                )

        self._usage = new_usage
        self._update_title()
        self._update_menu_items()
        self._check_notifications()

    def _update_title(self):
        if not self._usage:
            self.title = "🔮 —"
            return

        parts = []
        has_warning = False

        for key in ["claude", "openai", "gemini"]:
            if key not in self._usage:
                continue
            data = self._usage[key]
            icon = ICONS[key]
            if data.error:
                parts.append(f"{icon}:?")
                continue
            pct = data.percent
            if pct >= 80:
                has_warning = True
            parts.append(f"{icon}:{pct:.0f}%")

        prefix = "⚠️ " if has_warning else "🔮 "
        self.title = prefix + "  ".join(parts)

    def _update_menu_items(self):
        threshold = self.config.warning_threshold
        for key, data in self._usage.items():
            label = PROVIDER_LABELS[key]
            if label not in self.menu:
                continue

            if data.error:
                self.menu[label].title = f"{data.status_emoji} {label}: Error — {data.error}"
                continue

            pct = data.percent
            bar = _make_bar(pct)
            detail = _format_detail(data)
            self.menu[label].title = (
                f"{data.status_emoji} {label}  {bar}  {pct:.1f}%  {detail}"
            )

    def _check_notifications(self):
        threshold = self.config.warning_threshold
        for key, data in self._usage.items():
            if data.error:
                continue
            if data.percent >= threshold and key not in self._alerted:
                self._alerted.add(key)
                rumps.notification(
                    title="TokenPulse ⚠️",
                    subtitle=f"{data.display_name} usage at {data.percent:.1f}%",
                    message=(
                        f"You've used {data.percent:.1f}% of your monthly limit. "
                        f"Check your dashboard."
                    ),
                    sound=True,
                )
            elif data.percent < threshold and key in self._alerted:
                # Reset alert if usage drops (e.g. new billing cycle)
                self._alerted.discard(key)

    # ── Callbacks ─────────────────────────────────────────────────────────────

    @rumps.clicked("↻  Refresh Now")
    def on_refresh(self, _):
        self.title = "🔮 ..."
        threading.Thread(target=self._refresh, daemon=True).start()

    def on_edit_usage(self, provider_key: str):
        label = PROVIDER_LABELS[provider_key]
        current = self._usage.get(provider_key)
        current_val = current.used if current and not current.error else 0

        window = rumps.Window(
            message=f"Enter current token usage for {label}:",
            title=f"Edit {label} Usage",
            default_text=str(current_val),
            ok="Save",
            cancel="Cancel",
            dimensions=(300, 20),
        )
        resp = window.run()
        if resp.clicked and resp.text.strip().isdigit():
            tokens = int(resp.text.strip())
            self.storage.set_manual_usage(provider_key, tokens)
            # Patch live config for next refresh
            self.providers[provider_key].config["used_tokens"] = tokens
            threading.Thread(target=self._refresh, daemon=True).start()

    def on_about(self, _):
        rumps.alert(
            title="TokenPulse",
            message=(
                "🔮 TokenPulse — AI token usage tracker\n\n"
                "Track Claude, ChatGPT & Gemini usage\n"
                "right from your macOS menu bar.\n\n"
                "github.com/YOUR_USERNAME/tokenpulse"
            ),
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _open_url(url: str):
        subprocess.Popen(["open", url])


# ── Utility functions ─────────────────────────────────────────────────────────


def _make_bar(pct: float, width: int = 10) -> str:
    filled = round(pct / 100 * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def _format_detail(data: UsageData) -> str:
    if data.limit > 0:
        used_k = data.used / 1000
        limit_k = data.limit / 1000
        return f"({used_k:.0f}k / {limit_k:.0f}k tokens)"
    if data.cost_limit > 0:
        return f"(${data.cost_used:.2f} / ${data.cost_limit:.2f})"
    return ""


def run():
    TokenPulseApp().run()
