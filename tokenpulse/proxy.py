"""
TokenPulse local proxy server.

Runs a lightweight HTTP reverse proxy on localhost. SDK/app points to
http://127.0.0.1:<port> instead of the real API host. The proxy forwards
every request transparently and extracts token counts from responses.

Usage in user's code:
  # Anthropic
  client = anthropic.Anthropic(base_url="http://127.0.0.1:7778")

  # Gemini (google-generativeai SDK)
  genai.configure(transport="rest", client_options={"api_endpoint": "http://127.0.0.1:7779"})
"""

import json
import ssl
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen


# ── Token extractors per provider ─────────────────────────────────────────────

def _extract_anthropic(data: dict) -> int:
    usage = data.get("usage", {})
    return usage.get("input_tokens", 0) + usage.get("output_tokens", 0)


def _extract_gemini(data: dict) -> int:
    meta = data.get("usageMetadata", {})
    return meta.get("totalTokenCount", 0)


EXTRACTORS: dict[str, Callable[[dict], int]] = {
    "claude": _extract_anthropic,
    "gemini": _extract_gemini,
}

# ── Proxy server ───────────────────────────────────────────────────────────────

_SKIP_HEADERS = frozenset(
    {"host", "content-length", "connection", "transfer-encoding", "keep-alive"}
)


class TokenCountingProxy:
    """
    One proxy instance per provider (Anthropic or Gemini).
    Runs on a background daemon thread.
    """

    def __init__(
        self,
        provider: str,
        target_host: str,
        port: int,
        on_tokens: Callable[[str, int], None],
    ):
        self.provider = provider
        self.target_host = target_host
        self.port = port
        self._on_tokens = on_tokens
        self._extract = EXTRACTORS[provider]
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        handler = self._make_handler()
        self._server = HTTPServer(("127.0.0.1", self.port), handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True, name=f"proxy-{self.provider}"
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    # ── Internal ──────────────────────────────────────────────────────────────

    def _make_handler(self):
        proxy = self

        class _Handler(BaseHTTPRequestHandler):
            def _forward(self, method: str, body: bytes | None = None):
                target_url = f"https://{proxy.target_host}{self.path}"
                headers = {
                    k: v
                    for k, v in self.headers.items()
                    if k.lower() not in _SKIP_HEADERS
                }
                req = Request(target_url, data=body, headers=headers, method=method)
                ctx = ssl.create_default_context()
                try:
                    with urlopen(req, context=ctx) as resp:
                        status = resp.status
                        resp_headers = list(resp.headers.items())
                        resp_body = resp.read()
                except HTTPError as exc:
                    status = exc.code
                    resp_headers = list(exc.headers.items())
                    resp_body = exc.read()

                # Count tokens from successful responses
                if status == 200 and resp_body:
                    try:
                        tokens = proxy._extract(json.loads(resp_body))
                        if tokens > 0:
                            proxy._on_tokens(proxy.provider, tokens)
                    except Exception:
                        pass

                self.send_response(status)
                for k, v in resp_headers:
                    if k.lower() not in _SKIP_HEADERS:
                        self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp_body)

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                self._forward("POST", self.rfile.read(length))

            def do_GET(self):
                self._forward("GET")

            def log_message(self, *_):
                pass  # Suppress access logs

        return _Handler


# ── Proxy manager ──────────────────────────────────────────────────────────────

class ProxyManager:
    """Manages all running proxy instances."""

    TARGET_HOSTS = {
        "claude": "api.anthropic.com",
        "gemini": "generativelanguage.googleapis.com",
    }

    def __init__(self, config: dict, on_tokens: Callable[[str, int], None]):
        self._proxies: dict[str, TokenCountingProxy] = {}
        self._on_tokens = on_tokens
        self._config = config

    def start_for_provider(self, provider: str) -> int | None:
        """Start proxy for a provider. Returns the port, or None if disabled."""
        cfg = self._config.get("providers", {}).get(provider, {})
        if cfg.get("mode") != "proxy":
            return None
        port = cfg.get("proxy_port", _default_port(provider))
        if provider in self._proxies:
            return port  # already running

        proxy = TokenCountingProxy(
            provider=provider,
            target_host=self.TARGET_HOSTS[provider],
            port=port,
            on_tokens=self._on_tokens,
        )
        proxy.start()
        self._proxies[provider] = proxy
        return port

    def start_all(self) -> dict[str, int]:
        """Start proxies for all proxy-mode providers. Returns {provider: port}."""
        result = {}
        for provider in ("claude", "gemini"):
            port = self.start_for_provider(provider)
            if port:
                result[provider] = port
        return result

    def stop_all(self) -> None:
        for proxy in self._proxies.values():
            proxy.stop()
        self._proxies.clear()

    def base_url(self, provider: str) -> str | None:
        p = self._proxies.get(provider)
        return p.base_url if p else None


def _default_port(provider: str) -> int:
    return {"claude": 7778, "gemini": 7779}.get(provider, 7780)
