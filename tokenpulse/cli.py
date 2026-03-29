"""
TokenPulse interactive setup wizard.

Run with:  tokenpulse-setup
"""

import os
import sys
from pathlib import Path

import yaml

CONFIG_PATH = Path.home() / ".config" / "tokenpulse" / "config.yaml"

EXTENSION_URL = "https://github.com/YOUR_USERNAME/tokenpulse/tree/main/extension"

ANTHROPIC_BASE_URL = "http://127.0.0.1:7778"
GEMINI_BASE_URL = "http://127.0.0.1:7779"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _ask(prompt: str, default: str = "") -> str:
    """Read a line from stdin. Returns default if user presses Enter."""
    try:
        hint = f" [{default}]" if default else ""
        value = input(f"{prompt}{hint}: ").strip()
        return value if value else default
    except (EOFError, KeyboardInterrupt):
        raise


def _ask_int(prompt: str, default: int) -> int:
    while True:
        raw = _ask(prompt, str(default))
        try:
            return int(raw)
        except ValueError:
            print("  Please enter a whole number.")


def _ask_float(prompt: str, default: float) -> float:
    while True:
        raw = _ask(prompt, str(default))
        try:
            return float(raw)
        except ValueError:
            print("  Please enter a number (e.g. 20.0).")


def _choose(prompt: str, options: list[str], allow_multi: bool = False):
    """
    Present a numbered menu. If allow_multi=True, user can enter "1 2 3".
    Returns a list of 0-based indices.
    """
    for i, opt in enumerate(options, 1):
        print(f"  [{i}] {opt}")
    while True:
        raw = _ask(prompt)
        parts = raw.split()
        chosen = []
        valid = True
        for part in parts:
            try:
                idx = int(part) - 1
                if 0 <= idx < len(options):
                    chosen.append(idx)
                else:
                    valid = False
            except ValueError:
                valid = False
        if valid and chosen:
            if not allow_multi:
                return chosen[:1]
            return chosen
        print(f"  Enter a number between 1 and {len(options)}.")


def _detect_shell_rc() -> Path | None:
    shell = os.environ.get("SHELL", "")
    if "zsh" in shell:
        return Path.home() / ".zshrc"
    if "bash" in shell:
        return Path.home() / ".bashrc"
    return None


def _append_env_export(rc_path: Path, var: str, value: str) -> None:
    block = f"\n# TokenPulse proxy\nexport {var}={value}\n"
    with open(rc_path, "a") as f:
        f.write(block)


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def _load_existing_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            return yaml.safe_load(CONFIG_PATH.read_text()) or {}
        except Exception:
            pass
    return {}


def _save_config(cfg: dict) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(yaml.dump(cfg, default_flow_style=False, allow_unicode=True))


# ── Provider wizards ──────────────────────────────────────────────────────────


def _setup_claude() -> dict:
    print()
    print("  Claude (Anthropic)")
    print("  [1] proxy mode (recommended for API users)")
    print("      -> Start local proxy, set ANTHROPIC_BASE_URL automatically")
    print("  [2] extension mode (recommended for web users)")
    print("      -> Install browser extension, no API key needed")
    print("  [3] manual mode")
    print("      -> Enter token count yourself")

    [mode_idx] = _choose("  Choose mode", ["proxy", "extension", "manual"])
    mode = ["proxy", "extension", "manual"][mode_idx]

    api_key = _ask("  API key (optional, for proxy mode)", "")
    limit = _ask_int("  Monthly token limit", 1_000_000)

    cfg: dict = {
        "enabled": True,
        "mode": mode,
        "limit_tokens": limit,
    }
    if api_key:
        cfg["api_key"] = api_key

    return cfg, mode


def _setup_openai() -> dict:
    print()
    print("  ChatGPT (OpenAI)")
    print("  [1] api mode (recommended) <- auto-fetches billing data")
    print("  [2] manual mode")

    [mode_idx] = _choose("  Choose mode", ["api", "manual"])
    mode = ["api", "manual"][mode_idx]

    api_key = _ask("  API key (sk-...)", "")
    budget = _ask_float("  Monthly budget (USD)", 20.0)

    cfg: dict = {
        "enabled": True,
        "mode": mode,
        "limit_usd": budget,
    }
    if api_key:
        cfg["api_key"] = api_key

    return cfg, mode


def _setup_gemini() -> dict:
    print()
    print("  Gemini (Google AI)")
    print("  [1] proxy mode (recommended for API users)")
    print("  [2] extension mode")
    print("  [3] manual mode")

    [mode_idx] = _choose("  Choose mode", ["proxy", "extension", "manual"])
    mode = ["proxy", "extension", "manual"][mode_idx]

    api_key = _ask("  API key (AIzaSy..., optional)", "")
    limit = _ask_int("  Monthly token limit", 1_000_000)

    cfg: dict = {
        "enabled": True,
        "mode": mode,
        "limit_tokens": limit,
    }
    if api_key:
        cfg["api_key"] = api_key

    return cfg, mode


# ── Shell env setup ────────────────────────────────────────────────────────────


def _offer_shell_export(provider: str, var: str, value: str) -> None:
    rc_path = _detect_shell_rc()
    if rc_path is None:
        print(f"\n  Add this to your shell profile manually:")
        print(f"    export {var}={value}")
        return

    print(f"\n  To enable proxy mode for {provider}, add this to {rc_path.name}:")
    print(f"    export {var}={value}")
    answer = _ask("  Add it now? (y/n)", "y").lower()
    if answer == "y":
        _append_env_export(rc_path, var, value)
        print(f"  Added to {rc_path}. Run 'source {rc_path}' or restart your terminal.")


# ── Main wizard ───────────────────────────────────────────────────────────────


PROVIDER_CHOICES = [
    "Claude (Anthropic)",
    "ChatGPT (OpenAI)",
    "Gemini (Google AI)",
]

PROVIDER_KEYS = ["claude", "openai", "gemini"]


def main():
    print()
    print("=" * 60)
    print("  TokenPulse Setup Wizard")
    print("  Track your AI token & cost usage from the macOS menu bar")
    print("=" * 60)

    # ── 1. Which providers? ────────────────────────────────────────────────────
    print()
    print("Which providers do you want to enable?")
    print("(Enter one or more numbers separated by spaces, e.g. '1 3')")
    selected_indices = _choose(
        "  Providers", PROVIDER_CHOICES, allow_multi=True
    )
    selected_keys = [PROVIDER_KEYS[i] for i in selected_indices]

    if not selected_keys:
        print("\nNo providers selected. Exiting.")
        sys.exit(0)

    # ── 2. Configure each provider ─────────────────────────────────────────────
    provider_configs: dict[str, dict] = {}
    proxy_vars: list[tuple[str, str, str]] = []   # (provider, VAR, value)
    extension_providers: list[str] = []

    try:
        for key in selected_keys:
            if key == "claude":
                cfg, mode = _setup_claude()
            elif key == "openai":
                cfg, mode = _setup_openai()
            else:
                cfg, mode = _setup_gemini()

            provider_configs[key] = cfg

            if mode == "proxy":
                if key == "claude":
                    proxy_vars.append(("Claude", "ANTHROPIC_BASE_URL", ANTHROPIC_BASE_URL))
                elif key == "gemini":
                    proxy_vars.append(("Gemini", "GENERATIVEAI_API_ENDPOINT", GEMINI_BASE_URL))
            elif mode == "extension":
                extension_providers.append(key)

    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(0)

    # ── 3. Write config ────────────────────────────────────────────────────────
    existing = _load_existing_config()
    existing.setdefault("providers", {})
    for key, cfg in provider_configs.items():
        existing["providers"][key] = _deep_merge(
            existing["providers"].get(key, {}), cfg
        )

    _save_config(existing)
    print(f"\n  Config written to {CONFIG_PATH}")

    # ── 4. Shell env vars for proxy mode ───────────────────────────────────────
    try:
        for provider, var, value in proxy_vars:
            _offer_shell_export(provider, var, value)
    except KeyboardInterrupt:
        print("\n\nSkipping shell export.")

    # ── 5. Extension install instructions ─────────────────────────────────────
    if extension_providers:
        names = ", ".join(p.capitalize() for p in extension_providers)
        print()
        print(f"  Browser Extension Setup ({names})")
        print(f"  --------------------------------------------------")
        print(f"  1. Download the extension from:")
        print(f"     {EXTENSION_URL}")
        print(f"  2. Open Chrome/Edge -> Extensions -> Enable Developer Mode")
        print(f"  3. Click 'Load unpacked' and select the 'extension' folder")
        print(f"  4. The extension will connect to TokenPulse automatically on port 7777")

    # ── 6. Summary ─────────────────────────────────────────────────────────────
    print()
    print("=" * 60)
    print("  Setup complete!")
    print()
    print("  Enabled providers:")
    for key in selected_keys:
        mode = provider_configs[key].get("mode", "?")
        print(f"    - {key.capitalize()}: {mode} mode")
    print()
    print("  Next steps:")
    print("    1. Launch TokenPulse:  tokenpulse")
    if proxy_vars:
        print("    2. Restart your terminal (or source your shell profile)")
        print("       so the proxy env vars take effect")
    if extension_providers:
        print("    3. Install the browser extension (instructions above)")
    print()
    print("=" * 60)
    print()
