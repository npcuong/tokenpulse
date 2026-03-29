"""
HTTP server that receives usage data from the TokenPulse browser extension.
Runs on http://127.0.0.1:7777

Endpoints:
  POST /api/usage   — receive usage update from extension
  GET  /api/status  — health check (extension polls this to show connected status)
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Callable

from .storage import Storage

VERSION = "0.1.0"


class ExtensionReceiver:
    """Lightweight HTTP server that accepts usage data from the browser extension."""

    def __init__(self, storage: Storage, on_update: Callable, port: int = 7777):
        self._storage = storage
        self._on_update = on_update
        self._port = port
        self._server: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        handler = self._make_handler()
        self._server = HTTPServer(("127.0.0.1", self._port), handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
            name="extension-receiver",
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _make_handler(self):
        receiver = self

        class _Handler(BaseHTTPRequestHandler):
            def _send_cors_headers(self):
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                self.send_header(
                    "Access-Control-Allow-Headers", "Content-Type, Authorization"
                )

            def _send_json(self, status: int, body: dict):
                payload = json.dumps(body).encode()
                self.send_response(status)
                self._send_cors_headers()
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_OPTIONS(self):
                self.send_response(204)
                self._send_cors_headers()
                self.end_headers()

            def do_GET(self):
                if self.path == "/api/status":
                    self._send_json(200, {"status": "ok", "version": VERSION})
                else:
                    self._send_json(404, {"error": "Not found"})

            def do_POST(self):
                if self.path != "/api/usage":
                    self._send_json(404, {"error": "Not found"})
                    return

                length = int(self.headers.get("Content-Length", 0))
                try:
                    body = json.loads(self.rfile.read(length))
                except Exception:
                    self._send_json(400, {"error": "Invalid JSON"})
                    return

                provider = body.get("provider")
                if provider not in ("claude", "openai", "gemini"):
                    self._send_json(400, {"error": "Unknown provider"})
                    return

                # Token-based data (Claude, Gemini)
                used = body.get("used")
                if isinstance(used, int) and used >= 0:
                    receiver._storage.set_manual_usage(provider, used)

                # Cost-based data (OpenAI)
                cost_used = body.get("cost_used")
                if isinstance(cost_used, (int, float)):
                    receiver._storage.set(f"{provider}_cost_used", float(cost_used))

                cost_limit = body.get("cost_limit")
                if isinstance(cost_limit, (int, float)):
                    receiver._storage.set(f"{provider}_cost_limit", float(cost_limit))

                limit = body.get("limit")
                if isinstance(limit, int) and limit > 0:
                    receiver._storage.set(f"{provider}_limit_tokens", limit)

                # Trigger a UI refresh
                try:
                    receiver._on_update()
                except Exception:
                    pass

                self._send_json(200, {"status": "ok"})

            def log_message(self, *_):
                pass  # Suppress access logs

        return _Handler
