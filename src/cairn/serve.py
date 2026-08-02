"""serve — a loopback-only review server for the console (RT-10b, D49).

**Why a listener at all.** The console is static HTML, and a static page cannot run BM25.
The tempting alternative — reimplement retrieval in JavaScript so the page is
self-contained — would put a **second oracle** in the system: two retrieval
implementations that can silently drift, in a project whose central claim is that the
same corpus and query give the same result (I6). One mechanism, not two. So the page
calls the *actual* tools, and that requires a transport.

The MCP hardening brief is explicit that a local server's *absence* of a listener is the
win, and one should not be added without cause. The cause here is determinism. The cost is
paid down deliberately:

  · **Loopback only, enforced.** Binding anything but a loopback address is refused
    outright rather than warned about — a review server reachable from the network is a
    different product with a different threat model.
  · **Origin validated.** A browser will happily let `http://evil.example` POST to
    `127.0.0.1`; DNS rebinding makes that reachable even from a hostile page. Requests
    carrying a foreign `Origin` are rejected (the MCP Inspector RCE class).
  · **Read-shaped surface only.** The handlers come from the same registry the MCP server
    uses, so schema validation, path containment (D35) and bounded inputs (D41) apply
    unchanged. No new tool exists here that does not exist there.
  · **No file serving outside the console directory**, canonicalized — the same
    containment reasoning as `DocumentStore.doc_dir`.

This is a **development and review** server. It has no authentication because it has no
remote surface; if that ever changes, it needs the brief's P1 items first, and the change
should be a decision with its own row.
"""

from __future__ import annotations

import http.server
import ipaddress
import json
import socketserver
from pathlib import Path
from urllib.parse import urlparse

from .tools import Tool

MAX_BODY = 64 * 1024          # a query is small; a large body is a mistake or an attack


class NotLoopback(RuntimeError):
    """Refused to bind a non-loopback address (D49)."""


def require_loopback(host: str) -> None:
    """Refuse anything the outside world could reach. Raises rather than warns."""
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if host in ("localhost", "localhost.localdomain"):
            return
        raise NotLoopback(
            f"refusing to bind {host!r}: this is a loopback-only review server. "
            f"Serving it on a reachable interface is a different product with a "
            f"different threat model, and needs auth, TLS and a decision row first."
        ) from None
    if not ip.is_loopback:
        raise NotLoopback(f"refusing to bind {host!r}: not a loopback address")


def origin_allowed(origin: str | None, port: int) -> bool:
    """Same-origin or no Origin at all.

    A browser lets any page POST to 127.0.0.1, and DNS rebinding lets a hostile site
    reach it by name. `Origin` is the only signal that distinguishes our own console from
    someone else's page, so an unrecognised one is refused.
    """
    if origin is None:                       # non-browser client (curl, tests)
        return True
    try:
        u = urlparse(origin)
    except ValueError:
        return False
    if u.scheme not in ("http", "https"):
        return False
    if u.hostname not in ("127.0.0.1", "::1", "localhost"):
        return False
    return u.port in (port, None)


def make_handler(tools: dict[str, Tool], root: Path, port: int):
    root = Path(root).resolve()

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)

        def log_message(self, fmt, *args):        # quiet by default; the audit log is the record
            pass

        def _json(self, code: int, body: dict) -> None:
            blob = json.dumps(body).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(blob)))
            # No CORS header on purpose: the console is served from this same origin, so
            # it needs none, and adding one would hand the surface to any page that asks.
            self.end_headers()
            self.wfile.write(blob)

        def do_POST(self) -> None:               # noqa: N802 — stdlib naming
            if not origin_allowed(self.headers.get("Origin"), port):
                self._json(403, {"error": "cross-origin request refused (DNS-rebinding "
                                          "protection); this server answers its own "
                                          "console only"})
                return
            if not self.path.startswith("/tool/"):
                self._json(404, {"error": "unknown endpoint"})
                return
            name = self.path[len("/tool/"):]
            tool = tools.get(name)
            if tool is None:
                self._json(404, {"error": f"no such tool: {name}",
                                 "available": sorted(tools)})
                return
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                self._json(400, {"error": "bad Content-Length"})
                return
            if length > MAX_BODY:
                self._json(413, {"error": f"body over {MAX_BODY} bytes"})
                return
            try:
                args = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError as e:
                self._json(400, {"error": f"invalid JSON: {e}"})
                return
            try:
                # The same handler the MCP server exposes — so schema validation, path
                # containment and bounded inputs all apply, and the audit log gets the
                # same record. There is no second code path to keep in step.
                self._json(200, tool.handler(args))
            except Exception as e:               # noqa: BLE001 — surfaced, never swallowed
                self._json(400, {"error": f"{type(e).__name__}: {e}"})

    return Handler


def serve(tools: dict[str, Tool], root: Path, *, host: str = "127.0.0.1",
          port: int = 8765) -> socketserver.TCPServer:
    """Start the review server. Caller owns `serve_forever` / shutdown."""
    require_loopback(host)
    socketserver.TCPServer.allow_reuse_address = True
    return socketserver.TCPServer((host, port), make_handler(tools, root, port))
