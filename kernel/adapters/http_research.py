"""HttpResearchAdapter — the first REAL bounded external consequence (WP-03).

Re-expresses the DALEOBANKS ``services/websearch.py`` trust model (read-only
bounded web research) as a kernel adapter, minus its known security flaw F1:
DALEOBANKS matched trust with ``domain.endswith(trusted)``, so the allowlist
entry ``"gov"`` matched ``notgov.example`` and ``evilgov`` — a suffix bypass.
This adapter matches hosts LABEL-EXACT (``host == d or host.endswith("." + d)``,
case-insensitive), so a label boundary is always required.

Constitutional reasoning:

- Hard Rule 1 (witness): inherited from ``BoundedAdapter`` — ``execute``
  re-verifies the CommitWitness (presence, type, signature against the
  authority key, expiry, one-use) before any network call happens. No witness,
  no socket. The adapter fetches exactly ``witness.exact_target`` — the target
  the founder-approved fingerprint binds — never a caller-supplied URL.
- Hard Rule 4 (fail closed on ANY ambiguity): non-https schemes, userinfo,
  whitespace, malformed URLs, non-allowlisted hosts (including ANY redirect
  hop), redirect chains longer than 3, timeouts, DNS failures, non-2xx
  statuses, and bodies over 256 KiB all raise ``ExecutionRefusal``. The body
  is NEVER returned to the caller or written to the spine — only its hash.
- Hard Rule 5 (determinism): the only wall-clock value produced is
  ``fetched_at`` inside the receipt's signed ``external_id`` fetch-facts
  (metadata; never part of fingerprints or decision traces).

Reconciliation semantics (ADR, per SPEC-WP03 section 3.3 — WP-01 contract
shapes are NOT changed): the gate's RECONCILE stage compares
``sha256(canonical_json(witness.expected_outcome))`` against
``provider_response_hash``. ``expected_outcome`` is a ``str``, so its canonical
form is a JSON-quoted string; a raw-body sha256 could therefore never
reconcile for a non-JSON body (e.g. HTML). Like ``EchoAdapter``, this adapter
returns the OUTCOME-ATTESTATION hash
``sha256_hex(canonical_json(witness.expected_outcome))`` — but only after the
live fetch has been cryptographically checked against the approved
expectation: when ``expected_outcome`` parses as a JSON object carrying any of
``status_code`` / ``final_url`` / ``body_sha256``, every present key must
match the observed response or the execution is refused. The raw body hash is
carried in the receipt's signed ``external_id`` fetch-facts (the only free
result field in the WP-01 receipt shape) as ``body_sha256``.

Redirect discipline: the real transport NEVER auto-follows redirects. Every
hop's target is returned to the adapter, re-validated against the same
allowlist (label-exact, https-only), and only then fetched — at most 3 hops.

Trailing-dot rule (documented per SPEC): exactly ONE trailing dot is stripped
from the host before matching, so ``https://example.com./`` matches the
``example.com`` entry. ``example.com..`` keeps a trailing dot after one strip
and is refused. The URL actually fetched is the original witness target; only
the matching uses the normalized host.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Sequence

from ..contracts.execution import CommitWitness
from ..crypto.hashing import canonical_json, sha256_hex
from ..gate import errors
from .base import BoundedAdapter

ADAPTER_ID = "http-research"
RESEARCH_ACTION_TYPE = "research_fetch"

# The DALEOBANKS trusted set, PLUS example.com (IANA-operated, content-stable)
# as the canonical proof target. Production research targets still require
# per-target approval: the fingerprint binds the exact URL.
DEFAULT_ALLOWLIST: tuple[str, ...] = (
    "gov",
    "edu",
    "bbc.co.uk",
    "nytimes.com",
    "theguardian.com",
    "reuters.com",
    "apnews.com",
    "bloomberg.com",
    "example.com",
)

USER_AGENT = (
    "uniimente-kernel/http-research "
    "(+https://github.com/dababiyoda/uniimente-kernel)"
)
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_BYTES = 256 * 1024  # 256 KiB hard cap on response bodies
DEFAULT_MAX_REDIRECTS = 3

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_EXPECTATION_KEYS = ("status_code", "final_url", "body_sha256")


@dataclass(frozen=True)
class FetchResult:
    """One bounded HTTP response hop, as returned by the injected transport."""

    status_code: int
    body: bytes
    final_url: str  # for 3xx: the Location target; otherwise the URL fetched


# Injected transport signature: (url, timeout_seconds, max_bytes) -> FetchResult.
Fetcher = Callable[[str, float, int], FetchResult]


def allowlist_version(allowlist: Sequence[str]) -> str:
    """Content hash of the allowlist tuple (binds receipts to the egress policy)."""
    return sha256_hex(canonical_json(list(allowlist)).encode("utf-8"))


def host_allowed(host: str, allowlist: Sequence[str]) -> bool:
    """LABEL-EXACT host matching: ``host == d or host.endswith("." + d)``.

    Case-insensitive (hosts are lowercased before matching). This is the fix
    for DALEOBANKS finding F1: ``notgov.example`` does NOT match ``gov``, and
    ``evil-example.com`` does NOT match ``example.com``.
    """
    for entry in allowlist:
        if host == entry or host.endswith("." + entry):
            return True
    return False


def _normalize_host(raw_host: str) -> str:
    """Lowercase and strip exactly ONE trailing dot; refuse on ambiguity."""
    host = raw_host.lower()
    if host.endswith("."):
        host = host[:-1]
    if not host:
        raise errors.ExecutionRefusal("url host is empty", stage="EXECUTE")
    return host


def validate_research_url(url: str, allowlist: Sequence[str]) -> str:
    """Fail-closed validation of a research target; returns the normalized host.

    Refuses: non-str/empty input, any whitespace, non-https schemes, userinfo
    (``@``), malformed ports, empty hosts, and hosts outside the allowlist.
    """
    stage = "EXECUTE"
    if not isinstance(url, str) or not url:
        raise errors.ExecutionRefusal("research target must be a non-empty url", stage=stage)
    if any(ch.isspace() for ch in url):
        raise errors.ExecutionRefusal("url contains whitespace", stage=stage)
    try:
        parts = urllib.parse.urlsplit(url)
        # Touch port: urlsplit raises ValueError on malformed/out-of-range ports.
        _ = parts.port
    except ValueError as exc:
        raise errors.ExecutionRefusal(f"url is malformed: {exc}", stage=stage) from exc
    if parts.scheme != "https":
        raise errors.ExecutionRefusal(
            f"scheme {parts.scheme!r} refused: research_fetch is https-only", stage=stage
        )
    if "@" in parts.netloc:
        raise errors.ExecutionRefusal("url userinfo (@) refused", stage=stage)
    raw_host = parts.hostname or ""
    if any(ch.isspace() for ch in raw_host):
        raise errors.ExecutionRefusal("url host contains whitespace", stage=stage)
    host = _normalize_host(raw_host)
    if not host_allowed(host, allowlist):
        raise errors.ExecutionRefusal(
            f"host {host!r} is not in the egress allowlist (label-exact match)",
            stage=stage,
        )
    return host


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never auto-follow: the adapter re-checks every hop against the allowlist."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D102
        return None


def urllib_fetcher(url: str, timeout: float, max_bytes: int) -> FetchResult:
    """The real transport: stdlib urllib, GET only, fixed User-Agent, no body.

    Performs ONE request (redirects are surfaced, not followed). Reads at most
    ``max_bytes + 1`` bytes so the adapter can refuse oversize bodies instead
    of silently truncating them. TLS certificate verification is the urllib
    default (never disabled).
    """
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(request, timeout=timeout) as response:
            status = int(response.status)
            if status in _REDIRECT_STATUSES:
                location = response.headers.get("Location", "") or ""
                return FetchResult(status_code=status, body=b"", final_url=location)
            body = response.read(max_bytes + 1)
            return FetchResult(status_code=status, body=body, final_url=response.geturl())
    except urllib.error.HTTPError as exc:
        # HTTPError is also the no-redirect 3xx surface; 4xx/5xx arrive here too.
        status = int(exc.code)
        if status in _REDIRECT_STATUSES:
            location = exc.headers.get("Location", "") or ""
            return FetchResult(status_code=status, body=b"", final_url=location)
        body = exc.read(max_bytes + 1)
        return FetchResult(status_code=status, body=body, final_url=url)


class HttpResearchAdapter(BoundedAdapter):
    """Bounded read-only HTTPS research adapter (one action family).

    Handles exactly ``research_fetch``-shaped witnesses: the CommitWitness
    carries no action_type field (WP-01 shape), so family membership is
    enforced by target shape — the exact target must be an allowlisted https
    URL. A witness minted for any other action family (e.g. a subprocess or
    filesystem target) is refused at target validation.
    """

    def __init__(
        self,
        *,
        adapter_id: str = ADAPTER_ID,
        allowlist: Sequence[str] = DEFAULT_ALLOWLIST,
        fetcher: Fetcher | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_bytes: int = DEFAULT_MAX_BYTES,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        **kwargs,
    ):
        super().__init__(adapter_id=adapter_id, **kwargs)
        normalized = tuple(self._normalize_allowlist_entry(d) for d in allowlist)
        if not normalized:
            raise ValueError("egress allowlist must be non-empty (fail closed)")
        self._allowlist: tuple[str, ...] = normalized
        self._allowlist_version = allowlist_version(normalized)
        self._fetcher: Fetcher = fetcher or urllib_fetcher
        self._timeout = float(timeout)
        self._max_bytes = int(max_bytes)
        self._max_redirects = int(max_redirects)
        if self._max_bytes <= 0 or self._timeout <= 0 or self._max_redirects < 0:
            raise ValueError("bounds must be positive (fail closed)")
        self.calls = 0
        self.executed_witness_ids: list[str] = []

    @staticmethod
    def _normalize_allowlist_entry(entry: str) -> str:
        host = entry.strip().lower()
        if host.endswith("."):
            host = host[:-1]
        if not host or any(ch.isspace() for ch in host) or "@" in host:
            raise ValueError(f"invalid allowlist entry {entry!r} (fail closed)")
        return host

    @property
    def allowlist(self) -> tuple[str, ...]:
        return self._allowlist

    @property
    def allowlist_version(self) -> str:
        return self._allowlist_version

    # ------------------------------------------------------------ transport

    def _call_fetcher(self, url: str) -> FetchResult:
        """Invoke the injected transport; ANY transport error fails closed."""
        try:
            result = self._fetcher(url, self._timeout, self._max_bytes)
        except errors.GateRefusal:
            raise
        except Exception as exc:
            raise errors.ExecutionRefusal(
                f"transport failed for {url!r}: {exc!r}", stage="EXECUTE"
            ) from exc
        if not isinstance(result, FetchResult):
            raise errors.ExecutionRefusal(
                "fetcher returned no FetchResult; ambiguity fails closed", stage="EXECUTE"
            )
        return result

    def _fetch_bounded(self, url: str) -> FetchResult:
        """Fetch ``url``, following at most ``max_redirects`` re-checked hops."""
        for hop in range(self._max_redirects + 1):
            result = self._call_fetcher(url)
            if result.status_code not in _REDIRECT_STATUSES:
                break
            if hop == self._max_redirects:
                raise errors.ExecutionRefusal(
                    f"redirect chain exceeds {self._max_redirects} hops", stage="EXECUTE"
                )
            if not result.final_url:
                raise errors.ExecutionRefusal(
                    "redirect response without a Location target", stage="EXECUTE"
                )
            next_url = urllib.parse.urljoin(url, result.final_url)
            # EVERY redirect target must pass the same allowlist check.
            validate_research_url(next_url, self._allowlist)
            url = next_url
        if not 200 <= result.status_code < 300:
            raise errors.ExecutionRefusal(
                f"non-2xx status {result.status_code}", stage="EXECUTE"
            )
        if len(result.body) > self._max_bytes:
            raise errors.ExecutionRefusal(
                f"response body exceeds {self._max_bytes}-byte cap; "
                "refused instead of silently truncating",
                stage="EXECUTE",
            )
        return result

    # ------------------------------------------------- expectation binding

    @staticmethod
    def _verify_expectation(
        expected_outcome: str, result: FetchResult, body_sha256: str
    ) -> None:
        """Refuse if the live response contradicts the approved expectation.

        When ``expected_outcome`` parses as a JSON object carrying any of
        ``status_code`` / ``final_url`` / ``body_sha256``, every present key
        must equal the observed value. Opaque descriptive outcomes skip this
        check (generic predicates — 2xx, cap, allowlist — already enforced).
        """
        try:
            doc = json.loads(expected_outcome)
        except (TypeError, ValueError):
            return
        if not isinstance(doc, dict) or not any(k in doc for k in _EXPECTATION_KEYS):
            return
        observed = {
            "status_code": result.status_code,
            "final_url": result.final_url,
            "body_sha256": body_sha256,
        }
        for key in _EXPECTATION_KEYS:
            if key in doc and doc[key] != observed[key]:
                raise errors.ExecutionRefusal(
                    f"live fetch contradicts the approved expected_outcome "
                    f"({key}: expected {doc[key]!r}, observed {observed[key]!r})",
                    stage="EXECUTE",
                )

    # ------------------------------------------------------------- perform

    def _perform(self, witness: CommitWitness) -> tuple[str, str | None]:
        """One bounded real HTTPS GET of ``witness.exact_target``.

        Returns (provider_response_hash, external_id). The body itself NEVER
        leaves the adapter: the hash chain sees only its sha256 and the signed
        fetch-facts. Any refusal raises before this returns — zero bytes are
        handed to the caller on failure.
        """
        # The adapter fetches exactly the witness-bound target (Hard Rule 2).
        validate_research_url(witness.exact_target, self._allowlist)
        result = self._fetch_bounded(witness.exact_target)
        body_sha256 = sha256_hex(result.body)
        self._verify_expectation(witness.expected_outcome, result, body_sha256)

        facts = {
            "status_code": result.status_code,
            "bytes_fetched": len(result.body),
            "final_url": result.final_url,
            "body_sha256": body_sha256,
            "allowlist_version": self._allowlist_version,
            # Wall clock is allowed in receipt metadata only — never in
            # fingerprints or decision traces (Hard Rule 5).
            "fetched_at": self._clock().isoformat(),
        }
        # Outcome-attestation hash (see module docstring ADR): identical to
        # EchoAdapter semantics and to what the gate's RECONCILE stage verifies.
        response_hash = sha256_hex(canonical_json(witness.expected_outcome).encode("utf-8"))
        self.calls += 1
        self.executed_witness_ids.append(witness.id)
        return response_hash, canonical_json(facts)
