"""TokenPulse — macOS menu bar app for AI token usage tracking."""

import subprocess
import threading
from typing import Dict

import rumps

from .config import Config
from .providers import get_providers
from .providers.base import UsageData
from .proxy import ProxyManager
from .storage import Storage

ICONS = {"claude": "C", "openai": "G", "gemini": "✦"}
PROVIDER_LABELS = {"claude": "Claude", "openai": "ChatGPT", "gemini": "Gemini"}


class TokenPulseApp(rumps.App):
    def __init__(self):
        super().__init__("TokenPulse", title="🔮 ...", quit_button=None)

        self.config = Config()
        self.storage = Storage()
        self.providers = get_providers(self.config._data, storage=self.storage)

        self._alerted: set = set()
        self._usage: Dict[str, UsageData] = {}
        self._proxy_urls: dict[str, str] = {}

        # Start proxy servers for providers in proxy mode
        self._proxy_manager = ProxyManager(
            config=self.config._data,
            on_tokens=self.storage.increment_usage,
        )
        active_proxies = self._proxy_manager.start_all()
        for provider, port in active_proxies.items():
            self._proxy_urls[provider] = f"http://127.0.0.1:{port}"

        self._build_menu()
        threading.Thread(target=self._refresh, daemon=True).start()

        self._timer = rumps.Timer(
            lambda _: threading.Thread(target=self._refresh, daemon=True).start(),
            self.config.refresh_interval,
        )
        self._timer.start()

    # ── Menu ─────────────────────────────────────────────────────────────────

    def _build_menu(self):
        self.menu.clear()

        for key in PROVIDER_LABELS:
            if key in self.providers:
                self.menu.add(rumps.MenuItem(PROVIDER_LABELS[key]))

        self.menu.add(None)
        self.menu.add(rumps.MenuItem("↻  Refresh Now", callback=self.on_refresh))
        self.menu.add(None)

        # Dashboard links
        dashboards = rumps.MenuItem("Open Dashboard")
        for key, provider in self.providers.items():
            dashboards.add(
                rumps.MenuItem(
                    PROVIDER_LABELS[key],
                    callback=lambda _, u=provider.dashboard_url: self._open(u),
                )
            )
        self.menu.add(dashboards)

        # Edit usage (manual mode providers)
        edit_menu = rumps.MenuItem("Edit Usage")
        for key in self.providers:
            edit_menu.add(
                rumps.MenuItem(
                    PROVIDER_LABELS[key],
                    callback=lambda _, k=key: self.on_edit_usage(k),
                )
            )
        self.menu.add(edit_menu)

        # Proxy setup info
        if self._proxy_urls:
            proxy_menu = rumps.MenuItem("Proxy Setup")
            for provider, url in self._proxy_urls.items():
                proxy_menu.add(
                    rumps.MenuItem(
                        f"{PROVIDER_LABELS[provider]}: {url}",
                        callback=lambda _, u=url: self._copy_to_clipboard(u),
                    )
                )
            self.menu.add(proxy_menu)

        self.menu.add(None)
        self.menu.add(rumps.MenuItem("About TokenPulse", callback=self.on_about))
        self.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application))

    # ── Refresh ───────────────────────────────────────────────────────────────

    def _refresh(self):
        new_usage: Dict[str, UsageData] = {}
        for key, provider in self.providers.items():
            try:
                new_usage[key] = provider.fetch_usage()
            except Exception as e:
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
            if data.error:
                parts.append(f"{ICONS[key]}:?")
                continue
            pct = data.percent
            if pct >= 80:
                has_warning = True
            parts.append(f"{ICONS[key]}:{pct:.0f}%")
        prefix = "⚠️ " if has_warning else "🔮 "
        self.title = prefix + "  ".join(parts)

    def _update_menu_items(self):
        for key, data in self._usage.items():
            label = PROVIDER_LABELS[key]
            if label not in self.menu:
                continue
            if data.error:
                self.menu[label].title = f"❓ {label}: {data.error}"
                continue
            pct = data.percent
            bar = _make_bar(pct)
            detail = _format_detail(data)
            mode_tag = f" [{data.source}]" if data.source in ("proxy", "api") else ""
            self.menu[label].title = (
                f"{data.status_emoji} {label}{mode_tag}  {bar}  {pct:.1f}%  {detail}"
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
                    subtitle=f"{data.display_name} at {data.percent:.1f}%",
                    message=f"You've used {data.percent:.1f}% of your limit. Check your dashboard.",
                    sound=True,
                )
            elif data.percent < threshold:
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
            message=f"Enter current token count for {label}:",
            title=f"Edit {label} Usage",
            default_text=str(current_val),
            ok="Save",
            cancel="Cancel",
            dimensions=(300, 20),
        )
        resp = window.run()
        if resp.clicked and resp.text.strip().isdigit():
            tokens = int(resp.text.strip())
            provider = self.providers.get(provider_key)
            if hasattr(provider, "set_manual_usage"):
                provider.set_manual_usage(tokens)
            threading.Thread(target=self._refresh, daemon=True).start()

    def on_about(self, _):
        proxy_info = ""
        if self._proxy_urls:
            lines = "\n".join(
                f"  {PROVIDER_LABELS[k]}: {u}" for k, u in self._proxy_urls.items()
            )
            proxy_info = f"\n\nProxy endpoints (auto-counting):\n{lines}"

        rumps.alert(
            title="TokenPulse",
            message=(
                "🔮 TokenPulse — AI token usage tracker\n\n"
                "Track Claude, ChatGPT & Gemini usage\n"
                "right from your macOS menu bar."
                f"{proxy_info}\n\n"
                "github.com/npcuong/tokenpulse"
            ),
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _open(url: str):
        subprocess.Popen(["open", url])

    @staticmethod
    def _copy_to_clipboard(text: str):
        subprocess.run(["pbcopy"], input=text.encode(), check=False)
        rumps.notification("TokenPulse", "Copied!", text, sound=False)


# ── Utility ───────────────────────────────────────────────────────────────────


def _make_bar(pct: float, width: int = 10) -> str:
    filled = round(pct / 100 * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def _format_detail(data: UsageData) -> str:
    if data.limit > 0:
        return f"({data.used / 1000:.0f}k / {data.limit / 1000:.0f}k tokens)"
    if data.cost_limit > 0:
        return f"(${data.cost_used:.2f} / ${data.cost_limit:.2f})"
    return f"({data.used / 1000:.0f}k tokens)"


def run():
    TokenPulseApp().run()
