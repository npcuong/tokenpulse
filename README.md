# 🔮 TokenPulse

> **Track your AI token usage — right from the macOS menu bar.**

TokenPulse sits in your menu bar and shows how much of your monthly quota you've burned across **Claude**, **ChatGPT**, and **Gemini** — with a notification when you hit 80%.

![menu bar preview](docs/preview.png)

```
🔮 C:45%  G:72%  ✦:30%          ← normal
⚠️ C:45%  G:87%  ✦:30%          ← ChatGPT is over 80%
```

---

## Features

- **Menu bar display** — usage % for each AI, color-coded by severity
- **Progress bars** in the dropdown for a quick visual read
- **Notifications** at configurable threshold (default 80%)
- **Auto-refresh** every 5 minutes (configurable)
- **3 providers** out of the box: Claude, ChatGPT, Gemini
- **Flexible modes**: API-based fetching where possible, manual entry as fallback
- **Edit Usage** menu — update numbers without touching config
- **Dashboard shortcuts** — one click opens the right billing page
- **Auto-start** via launchd (optional)

---

## Installation

### Requirements

- macOS 12+
- Python 3.11+

### Quick install

```bash
git clone https://github.com/YOUR_USERNAME/tokenpulse.git
cd tokenpulse
bash setup.sh
```

Then edit your config:

```bash
open ~/.config/tokenpulse/config.yaml
```

Start the app:

```bash
tokenpulse
```

### Auto-start on login

```bash
bash scripts/autostart.sh
```

---

## Configuration

Config lives at `~/.config/tokenpulse/config.yaml`. Created automatically from `config.example.yaml` on first run.

```yaml
refresh_interval: 300      # seconds between auto-refresh (default: 5 min)
warning_threshold: 80      # percent at which to send notification

providers:

  claude:
    enabled: true
    mode: manual            # "manual" | "api"
    api_key: "sk-ant-..."  # optional, for api mode
    limit_tokens: 1000000
    used_tokens: 0          # update from console.anthropic.com/settings/usage

  openai:
    enabled: true
    mode: api               # fetches billing automatically with your API key
    api_key: "sk-..."
    limit_usd: 20.00        # your monthly spending limit

  gemini:
    enabled: true
    mode: manual
    limit_tokens: 1000000
    used_tokens: 0          # update from aistudio.google.com
```

---

## Provider details

| Provider | Auto-fetch? | How | Dashboard |
|----------|-------------|-----|-----------|
| **Claude** | Experimental | Anthropic usage API (if available) | [console.anthropic.com](https://console.anthropic.com/settings/usage) |
| **ChatGPT** | ✅ Yes | OpenAI billing dashboard API | [platform.openai.com](https://platform.openai.com/account/usage) |
| **Gemini** | Via GCP only | Cloud Monitoring API (Vertex AI) | [aistudio.google.com](https://aistudio.google.com) |

For providers without auto-fetch, use **Edit Usage** in the menu bar to update your current count after checking your dashboard.

---

## Menu reference

| Item | Description |
|------|-------------|
| `🟢/🟡/🔴 Provider [████░░] 45%` | Usage bar + percent |
| `↻ Refresh Now` | Fetch latest data immediately |
| `Open Dashboard > Provider` | Opens billing page in browser |
| `Edit Usage > Provider` | Manually set current token count |
| `Quit` | Exit TokenPulse |

---

## Notification logic

- A notification fires once per billing cycle when a provider crosses the threshold.
- If usage drops below the threshold (new cycle), the alert resets automatically.

---

## Contributing

PRs welcome! Adding a new provider is easy — see [`tokenpulse/providers/base.py`](tokenpulse/providers/base.py) for the interface.

```python
class MyProvider(BaseProvider):
    def fetch_usage(self) -> UsageData: ...
    @property
    def dashboard_url(self) -> str: ...
```

---

## License

MIT — see [LICENSE](LICENSE).

---

*Built with [rumps](https://github.com/jaredks/rumps) — the best way to make macOS menu bar apps in Python.*
