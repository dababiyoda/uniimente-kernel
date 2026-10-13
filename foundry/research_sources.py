"""Bounded SearXNG search and content-addressed source records."""
from __future__ import annotations

import ipaddress
import json
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit

from provenance.ledger import sha256_json

MAX_JSON = 128 * 1024


def text(value, label, limit=4000, *, empty=False):
    if not isinstance(value, str) or (not empty and not value.strip()) or len(value) > limit:
        raise ValueError(f"{label} must be {'an optional' if empty else 'a nonempty'} string of at most {limit} characters")
    return value.strip()


def local_url(value):
    url = urlsplit(value)
    try:
        local = url.hostname == "localhost" or ipaddress.ip_address(url.hostname or "").is_loopback
    except ValueError:
        local = False
    if (not local or url.scheme not in ("http", "https") or url.username or url.password
            or url.query or url.fragment or url.path not in ("", "/")):
        raise ValueError("SearXNG requires a loopback root URL without credentials")
    # Access the port here so malformed authorities fail during planning.
    url.port
    return value.rstrip("/")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("search redirects are refused")


def source_record(title, excerpt, url="", *, kind="search_snippet"):
    title = text(title, "source title", 300)
    excerpt = text(excerpt, "source excerpt", 4000)
    if kind not in ("search_snippet", "local_document"):
        raise ValueError("unsupported source kind")
    url = text(url, "source URL", 2000, empty=True)
    if kind == "search_snippet":
        parsed = urlsplit(url)
        if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError("search source needs an HTTP URL without credentials")
    body = {"title": title, "excerpt": excerpt, "url": url, "kind": kind}
    return {**body, "source_id": sha256_json(body),
            "captured_at": datetime.now(timezone.utc).isoformat(),
            "evidence_tier": "observation", "verified_buyer_demand": False}


def normalize_results(results, limit):
    if not isinstance(results, list):
        raise ValueError("search results must be a list")
    records, seen = [], set()
    # Bound processing independently of the response and output limits.
    for item in results[:100]:
        if not isinstance(item, dict):
            raise ValueError("search result must be an object")
        if not item.get("content"):
            continue
        record = source_record(item.get("title", "")[:300], item["content"][:4000],
                               item.get("url", ""))
        if record["source_id"] not in seen:
            records.append(record)
            seen.add(record["source_id"])
        if len(records) >= limit:
            break
    return records


class SearxSearch:
    def __init__(self, base_url="http://127.0.0.1:8080", *, limit=5, timeout=20):
        self.base_url = local_url(base_url)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 20:
            raise ValueError("source limit must be between 1 and 20")
        if isinstance(timeout, bool) or not isinstance(timeout, (float, int)) or not 0 < timeout <= 60:
            raise ValueError("search timeout must be positive and at most 60")
        self.limit, self.timeout = limit, timeout
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def search(self, query):
        text(query, "query", 1000)
        request = urllib.request.Request(self.base_url + "/search?" + urlencode({
            "q": query, "format": "json", "safesearch": 1}), headers={"Accept": "application/json"})
        with self.opener.open(request, timeout=self.timeout) as response:
            raw = response.read(MAX_JSON + 1)
        if len(raw) > MAX_JSON:
            raise ValueError("search response exceeds 128 KiB")
        data = json.loads(raw)
        if not isinstance(data, dict) or "results" not in data:
            raise ValueError("invalid SearXNG response")
        warnings = data.get("unresponsive_engines", [])
        if not isinstance(warnings, list):
            raise ValueError("invalid search engine warnings")
        return {"sources": normalize_results(data["results"], self.limit),
                "search_warnings": warnings[:20], "search_mode": "searxng"}
