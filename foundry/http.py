"""Dependency-free HTTP boundary for signed Foundry underwriting intake.

Run locally with ``python -m foundry.http``. This endpoint accepts and records a
proposal-only opportunity. It does not compile an architecture, create a grant,
or execute an external effect.
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Iterable

from provenance.ledger import EvidenceLedger

from .contracts import FoundryError
from .engine import AdvantageFoundry
from .transport import (
    H_IDEMPOTENCY,
    H_IDENTITY,
    H_NONCE,
    H_SCHEMA,
    H_SIGNATURE,
    H_TIMESTAMP,
    H_TRACE,
    ReplayGuard,
    TransportSecurityError,
    build_signed_headers,
    ingest_signed_underwriting,
)

MAX_BODY_BYTES = 1_000_000
DEFAULT_PATH = "/foundry/underwriting/intake"


class FoundryWSGIApp:
    def __init__(
        self,
        *,
        key: bytes | str,
        ledger: EvidenceLedger,
        foundry: AdvantageFoundry | None = None,
        replay_guard: ReplayGuard | None = None,
    ) -> None:
        if not key:
            raise RuntimeError("inter-organ signing key is required")
        self.key = key
        self.ledger = ledger
        self.foundry = foundry or AdvantageFoundry(ledger)
        self.replay_guard = replay_guard or ReplayGuard()

    def __call__(self, environ: dict[str, Any], start_response: Callable) -> Iterable[bytes]:
        if environ.get("PATH_INFO") != DEFAULT_PATH:
            return self._respond(start_response, "404 Not Found", {"error": "not_found"})
        if environ.get("REQUEST_METHOD") != "POST":
            return self._respond(
                start_response,
                "405 Method Not Allowed",
                {"error": "method_not_allowed"},
                extra_headers=[("Allow", "POST")],
            )
        try:
            content_length = int(environ.get("CONTENT_LENGTH") or "0")
        except ValueError:
            return self._respond(
                start_response,
                "400 Bad Request",
                {"error": "invalid_content_length"},
            )
        if content_length <= 0:
            return self._respond(
                start_response,
                "400 Bad Request",
                {"error": "empty_body"},
            )
        if content_length > MAX_BODY_BYTES:
            return self._respond(
                start_response,
                "413 Payload Too Large",
                {"error": "body_too_large"},
            )

        body = environ["wsgi.input"].read(content_length)
        headers = self._headers_from_environ(environ)
        try:
            ingested = ingest_signed_underwriting(
                headers,
                body,
                key=self.key,
                replay_guard=self.replay_guard,
                ledger=self.ledger,
            )
            self.foundry.intake(ingested.opportunity)
        except TransportSecurityError as exc:
            return self._respond(
                start_response,
                "401 Unauthorized",
                {"error": "transport_rejected", "detail": str(exc)},
            )
        except FoundryError as exc:
            return self._respond(
                start_response,
                "422 Unprocessable Entity",
                {"error": "foundry_intake_rejected", "detail": str(exc)},
            )

        payload = {
            "status": "accepted_for_foundry_analysis",
            "opportunity_id": ingested.opportunity.opportunity_id,
            "opportunity_digest": ingested.opportunity.digest,
            "duplicate": ingested.transport.duplicate,
            "requires_human_approval": True,
            "execution_authority": "none",
        }
        return self._signed_response(
            start_response,
            "202 Accepted",
            payload,
            idempotency_key=ingested.transport.idempotency_key,
            trace_id=ingested.transport.trace_id,
            schema_version=ingested.transport.schema_version,
        )

    @staticmethod
    def _headers_from_environ(environ: dict[str, Any]) -> dict[str, str]:
        result = {}
        for header in (
            H_IDENTITY, H_TIMESTAMP, H_NONCE, H_IDEMPOTENCY,
            H_SCHEMA, H_SIGNATURE, H_TRACE,
        ):
            key = "HTTP_" + header.upper().replace("-", "_")
            value = environ.get(key)
            if value is not None:
                result[header] = str(value)
        return result

    def _signed_response(
        self,
        start_response: Callable,
        status: str,
        payload: dict[str, Any],
        *,
        idempotency_key: str,
        trace_id: str,
        schema_version: str,
    ) -> Iterable[bytes]:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        signed = build_signed_headers(
            body,
            key=self.key,
            identity="uniimente-kernel",
            schema_version=schema_version,
            idempotency_key=idempotency_key,
            trace_id=trace_id,
        )
        headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
        headers.extend(signed.items())
        start_response(status, headers)
        return [body]

    @staticmethod
    def _respond(
        start_response: Callable,
        status: str,
        payload: dict[str, Any],
        *,
        extra_headers: list[tuple[str, str]] | None = None,
    ) -> Iterable[bytes]:
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body)))]
        headers.extend(extra_headers or [])
        start_response(status, headers)
        return [body]


def create_app_from_env() -> FoundryWSGIApp:
    key = os.getenv("UNIIMENTE_INTERORGAN_SIGNING_KEY") or os.getenv("WEALTHMACHINE_SIGNING_KEY")
    if not key:
        raise RuntimeError(
            "UNIIMENTE_INTERORGAN_SIGNING_KEY is required "
            "(WEALTHMACHINE_SIGNING_KEY is accepted during migration)"
        )
    constitution_hash = os.getenv("UNIIMENTE_CONSTITUTION_HASH", "")
    if not constitution_hash.startswith("sha256:"):
        raise RuntimeError("UNIIMENTE_CONSTITUTION_HASH must be a canonical sha256 reference")
    ledger_path = os.getenv("UNIIMENTE_LEDGER_PATH") or None
    ledger = EvidenceLedger(constitution_hash, path=ledger_path)
    return FoundryWSGIApp(key=key, ledger=ledger)


def main() -> None:
    from wsgiref.simple_server import make_server

    host = os.getenv("UNIIMENTE_FOUNDRY_HOST", "127.0.0.1")
    port = int(os.getenv("UNIIMENTE_FOUNDRY_PORT", "8765"))
    app = create_app_from_env()
    with make_server(host, port, app) as server:
        print(f"UNIIMENTE Foundry intake listening on http://{host}:{port}{DEFAULT_PATH}")
        server.serve_forever()


if __name__ == "__main__":
    main()


__all__ = ["DEFAULT_PATH", "FoundryWSGIApp", "MAX_BODY_BYTES", "create_app_from_env"]
