"""
Only this computer's own page may use the API (ported from Dijkstra UI's guard).

Binding to 127.0.0.1 keeps the network out, but not other websites open in your browser:
 - CSRF: any page can make your browser send a POST to 127.0.0.1. Browsers name the
   sending page in the "Origin" header, so writes must come from our own origin.
 - DNS rebinding: an attacker's domain can point itself at 127.0.0.1. Its requests still
   carry the attacker's name in the "Host" header, so only our host names pass.
"""

from __future__ import annotations

from fastapi.responses import JSONResponse

from . import config

SAFE_METHODS = ("GET", "HEAD")
SECURITY_HEADERS = [
    (b"content-security-policy",
     b"default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; "
     b"frame-ancestors 'none'"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"no-referrer"),
    (b"x-content-type-options", b"nosniff"),
]


def allowed(port: int) -> tuple[set[str], set[str]]:
    hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
    dev = {f"127.0.0.1:{config.VITE_PORT}", f"localhost:{config.VITE_PORT}"}
    origins = {f"http://{h}" for h in hosts | dev}
    return hosts, origins


class LocalOnly:
    """ASGI middleware: checks every request before any endpoint sees it."""

    def __init__(self, app, port: int = config.PORT):
        self.app = app
        self.hosts, self.origins = allowed(port)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]}
        problem = None
        if headers.get("host") not in self.hosts:
            problem = "unknown host"
        elif scope["method"] not in SAFE_METHODS and headers.get("origin") not in self.origins:
            problem = "request did not come from the wardrobe page"
        if problem:
            return await JSONResponse({"error": f"Forbidden: {problem}"}, 403)(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message.get("headers", [])) + SECURITY_HEADERS
            await send(message)

        await self.app(scope, receive, send_with_headers)
