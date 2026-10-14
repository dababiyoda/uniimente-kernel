"""GREG's one outbound HTTP opener: a redirect is a new request, re-checked or refused.

urllib's default ``HTTPRedirectHandler`` follows 301/302/303/307/308 to any scheme
and host, and copies every request header (``Authorization`` included) onto the
redirected request. A 3xx from an allowlisted host could therefore move a
capability's egress, and its credential, anywhere. Here:

* urllib never follows a redirect (``NoRedirect``); the 3xx surfaces;
* each ``Location`` is resolved against the current URL and checked exactly as the
  first request was: https only, no userinfo, a well-formed port, and a host that is
  a member of the capability's egress allowlist (exact names, no subdomain widening);
* at most ``MAX_HOPS`` redirects are followed and the next one is refused;
* credential headers are dropped when a hop changes host and are never restored, so a
  credential is only ever sent to the host it was issued for;
* a request with a body (POST) is never re-sent or converted to GET on a redirect.

A refusal raises ``EgressRefused``; callers map it to their own definite refusal
(``CapabilityError`` for capabilities), so a refused hop is never an unknown outcome.

Mechanism lineage: egregore/local_model.py ``_NoRedirect`` and
foundry/research_sources.py ``NoRedirect`` (surface, never follow; those loopback
clients keep refusing every redirect); PR #26 (WP-03) kernel/adapters/http_research.py
``_fetch_bounded``, ``urllib_fetcher`` and ``validate_research_url`` (per-hop
re-validation, three hops), re-expressed with exact allowlist membership in place of
WP-03's subdomain-matching ``host_allowed``.
"""
from __future__ import annotations

import urllib.error
import urllib.parse
import urllib.request

MAX_HOPS = 3
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
CREDENTIAL_HEADERS = frozenset({"authorization", "proxy-authorization", "cookie"})


class EgressRefused(ValueError):
    """A request, or one of its redirect hops, is outside the permitted egress."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never auto-follow: the 3xx surfaces as an ``HTTPError`` for the caller to judge."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def opener() -> urllib.request.OpenerDirector:
    """urllib's default chain (environment proxies, verified TLS) with redirects surfaced."""
    return urllib.request.build_opener(NoRedirect())


def send(request: urllib.request.Request, timeout: float):
    """One request, one response; a 3xx raises ``HTTPError`` instead of being followed."""
    return opener().open(request, timeout=timeout)


def check(url: str, allowlist) -> str:
    """Refuse anything but https to a host in ``allowlist``; return the host."""
    if not isinstance(url, str) or not url or any(ch.isspace() or ord(ch) < 32 for ch in url):
        raise EgressRefused("url is empty or contains whitespace or control characters")
    try:
        parts = urllib.parse.urlsplit(url)
        parts.port                              # a malformed or out-of-range port raises here
    except ValueError as exc:
        raise EgressRefused(f"url is malformed: {exc}") from None
    if parts.scheme != "https":
        raise EgressRefused(f"scheme {parts.scheme!r} refused: https only")
    if "@" in parts.netloc:
        raise EgressRefused("url userinfo refused")
    host = parts.hostname
    if not host or host not in tuple(allowlist):
        raise EgressRefused(f"egress to {host!r} not in allowlist")
    return host


def open_checked(request: urllib.request.Request, *, allowlist, timeout: float,
                 max_hops: int = MAX_HOPS):
    """Open ``request`` and follow at most ``max_hops`` re-checked redirects.

    Returns the final non-redirect response (its ``geturl()`` is the URL actually read).
    4xx/5xx raise ``urllib.error.HTTPError`` exactly as ``urlopen`` does; a refused
    request or hop raises ``EgressRefused`` before anything is sent to it.
    """
    host = check(request.full_url, allowlist)
    for hop in range(max_hops + 1):
        try:
            return send(request, timeout)
        except urllib.error.HTTPError as exc:
            if exc.code not in REDIRECT_STATUSES:
                raise
            status, location = exc.code, (exc.headers.get("Location") if exc.headers else None)
            exc.close()
        if request.data is not None or request.get_method() not in ("GET", "HEAD"):
            raise EgressRefused(f"redirect (HTTP {status}) of a {request.get_method()} request refused")
        if hop == max_hops:
            raise EgressRefused(f"redirect chain exceeds {max_hops} hops")
        if not location:
            raise EgressRefused(f"redirect (HTTP {status}) without a Location target")
        target = urllib.parse.urljoin(request.full_url, location)
        next_host = check(target, allowlist)
        headers = {name: value for name, value in request.header_items()
                   if next_host == host or name.lower() not in CREDENTIAL_HEADERS}
        request = urllib.request.Request(target, headers=headers, method=request.get_method())
        host = next_host
    raise AssertionError("unreachable")
