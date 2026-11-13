"""An in-process HTTPS world for egress tests: no socket, no network, real urllib.

``FakeWeb`` replaces only ``HTTPSHandler.https_open``, the last step that would open a
connection. Everything above it is urllib's own machinery, including the default
``HTTPRedirectHandler`` (which follows 3xx and copies request headers) and any
handler a caller installs instead. Each request that would have left the machine is
recorded with its method and headers, so a test can assert what a host received.
"""
from __future__ import annotations

import email.message
import io
import json
import urllib.parse
import urllib.request
import urllib.response


class FakeWeb:
    def __init__(self, routes: dict[str, tuple]):
        """routes: url -> (status, location or None, body bytes or JSON-able object)."""
        self.routes = routes
        self.seen: list[dict] = []

    def hosts(self) -> list[str]:
        return [urllib.parse.urlsplit(r["url"]).hostname for r in self.seen]

    def received(self, host: str) -> list[dict]:
        return [r for r in self.seen if urllib.parse.urlsplit(r["url"]).hostname == host]

    def _open(self, handler, request):
        headers = {name.lower(): value for name, value in request.header_items()}
        self.seen.append({"url": request.full_url, "method": request.get_method(), "headers": headers})
        status, location, body = self.routes.get(request.full_url, (404, None, b"not found"))
        if not isinstance(body, bytes):
            body = json.dumps(body).encode()
        message = email.message.Message()
        message["Content-Type"] = "application/json"
        if location:
            message["Location"] = location
        response = urllib.response.addinfourl(io.BytesIO(body), message, request.full_url, status)
        response.msg = "fake"
        return response

    def install(self, monkeypatch):
        web = self
        monkeypatch.setattr(urllib.request.HTTPSHandler, "https_open",
                            lambda handler, request: web._open(handler, request))
        return self
