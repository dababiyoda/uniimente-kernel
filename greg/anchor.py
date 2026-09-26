"""External time anchoring of GREG's ledger (RFC 3161).

The ledger's hash chain proves internal consistency, but whoever holds the ledger
-- including the body itself -- can rewrite history and re-chain it. An independent
Time-Stamp Authority signs the ledger head at a moment in time.

Two verifiers, with different trust:

* ``verify`` reads anchors and TSA roots from the ledger it checks. It catches a
  rewriter who leaves the anchor records alone, and nothing stronger: a complete
  ledger rewriter can delete anchors, roll back, or substitute roots and anchors.
* ``verify_witness`` uses only a witness bundle exported earlier (``export_witness``)
  and kept outside GREG's rewrite domain, plus TSA roots supplied by the verifier.
  It detects rewrite, deletion, rollback, root/anchor substitution and wholesale
  reconstruction *within the witnessed prefix*. Records after the latest witnessed
  head are not covered, and nothing protects a witness the attacker can also edit.

Authority: anchoring is off until Alfonso signs ``ANCHOR_CONFIGURE`` naming the
TSA and pinning its root certificate(s). Only a SHA-256 digest of the ledger
head leaves the machine. A TSA failure is recorded and never blocks a mission.
Verification uses rfc3161-client (the verifier sigstore-python uses); GREG
implements no timestamp cryptography of its own.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
import urllib.request
from urllib.parse import urlparse

from cryptography import x509
from rfc3161_client import (HashAlgorithm, TimestampRequestBuilder, VerifierBuilder, VerificationError,
                            decode_timestamp_response)

DEFAULT_INTERVAL_MINUTES = 60
MIN_INTERVAL_MINUTES = 5
TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 64 * 1024


class AnchorError(ValueError):
    """Refused anchor configuration or unusable TSA response."""


def _roots(pem: str) -> list[x509.Certificate]:
    try:
        roots = x509.load_pem_x509_certificates(pem.encode())
    except ValueError as exc:
        raise AnchorError(f"tsa_roots_pem is not PEM certificates: {exc}") from None
    if not roots:
        raise AnchorError("tsa_roots_pem must contain at least one certificate")
    return roots


def validate_config(body: dict) -> dict:
    """Validate a signed ANCHOR_CONFIGURE body. ``tsa_url: null`` disables anchoring."""
    allowed = {"tsa_url", "tsa_roots_pem", "interval_minutes"}
    if not isinstance(body, dict) or set(body) - allowed or "tsa_url" not in body:
        raise AnchorError(f"ANCHOR_CONFIGURE takes {sorted(allowed)} with tsa_url required")
    if body["tsa_url"] is None:
        return {"enabled": False}
    url = urlparse(body["tsa_url"])
    loopback = url.hostname in ("127.0.0.1", "localhost", "::1")
    if url.scheme != "https" and not (url.scheme == "http" and loopback):
        raise AnchorError("tsa_url must be https (plain http only on loopback)")
    pem = body.get("tsa_roots_pem")
    if not isinstance(pem, str):
        raise AnchorError("tsa_roots_pem is required: pin the TSA root certificate(s)")
    _roots(pem)
    interval = body.get("interval_minutes", DEFAULT_INTERVAL_MINUTES)
    if not isinstance(interval, int) or interval < MIN_INTERVAL_MINUTES:
        raise AnchorError(f"interval_minutes must be an integer >= {MIN_INTERVAL_MINUTES}")
    return {"enabled": True, "tsa_url": body["tsa_url"], "tsa_roots_pem": pem,
            "roots_sha256": hashlib.sha256(pem.encode()).hexdigest(), "interval_minutes": interval}


def configure(journal, body: dict, digest: str) -> dict:
    config = validate_config(body)
    journal.record("proof.anchor_configured", {**config, "command_digest": digest}, key=digest)
    return {k: v for k, v in config.items() if k != "tsa_roots_pem"}


def current_config(journal) -> dict | None:
    configured = journal.replay("proof.anchor_configured")
    if not configured or not configured[-1].payload["enabled"]:
        return None
    return configured[-1].payload


def _post(url: str, request: bytes) -> bytes:
    req = urllib.request.Request(url, data=request, method="POST",
                                 headers={"Content-Type": "application/timestamp-query"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise AnchorError("TSA response too large")
    return body


def _message(head: str) -> bytes:
    """The bytes the TSA timestamps: the raw SHA-256 of the ledger head (``sha256:<hex>``)."""
    algorithm, _, digest = head.partition(":")
    if algorithm != "sha256" or len(digest) != 64:
        raise AnchorError(f"unexpected ledger head format {head[:20]!r}")
    return bytes.fromhex(digest)


def _unanchored_records(journal, last_head: str | None) -> bool:
    """True when the ledger holds anything other than anchor bookkeeping past ``last_head``."""
    records = journal.ledger.records
    start = 0
    if last_head is not None:
        found = next((i for i, r in enumerate(records) if r.hash == last_head), None)
        if found is None:
            return True  # anchored head vanished: re-anchor now, verify() reports the rewrite
        start = found + 1
    for record in records[start:]:
        kind = record.payload.get("type", "") if record.record_type == "event" else record.record_type
        if not kind.startswith("greg.proof.anchor"):
            return True
    return False


def due(journal, now: datetime) -> bool:
    config = current_config(journal)
    if config is None:
        return False
    attempts = journal.replay("proof.anchored") + journal.replay("proof.anchor_failed")
    if attempts:
        last = max(datetime.fromisoformat(e.payload["at"].replace("Z", "+00:00")) for e in attempts)
        if now - last < timedelta(minutes=config["interval_minutes"]):
            return False
    anchored = journal.replay("proof.anchored")
    return _unanchored_records(journal, anchored[-1].payload["head"] if anchored else None)


def anchor_once(journal, now: datetime, *, transport=None) -> dict:
    """Timestamp the current ledger head. Records success or failure; never raises."""
    from greg.journal import iso
    config = current_config(journal)
    if config is None:
        return {"anchored": False, "reason": "anchoring not configured"}
    head, count = journal.ledger.head, len(journal.ledger.records)
    try:
        request = (TimestampRequestBuilder().data(_message(head)).hash_algorithm(HashAlgorithm.SHA256).nonce(nonce=True)
                   .cert_request(cert_request=True).build())
        response = decode_timestamp_response((transport or _post)(config["tsa_url"], request.as_bytes()))
        verifier = VerifierBuilder.from_request(request)
        for root in _roots(config["tsa_roots_pem"]):
            verifier = verifier.add_root_certificate(root)
        verifier.build().verify_message(response, _message(head))
    except Exception as exc:  # a TSA outage is a recorded blocker, never a crash loop
        failure = {"head": head, "tsa_url": config["tsa_url"], "error": f"{type(exc).__name__}: {exc}"[:300],
                   "at": iso(now)}
        journal.record("proof.anchor_failed", failure, key=[head, config["tsa_url"], iso(now)])
        return {"anchored": False, **failure}
    info = response.tst_info
    anchor = {"head": head, "record_count": count, "tsa_url": config["tsa_url"],
              "roots_sha256": config["roots_sha256"], "gen_time": iso(info.gen_time),
              "serial_number": str(info.serial_number), "nonce": str(info.nonce),
              "token_b64": base64.b64encode(response.as_bytes()).decode(), "at": iso(now)}
    journal.record("proof.anchored", anchor, key=[head, config["tsa_url"]])
    return {"anchored": True, **{k: v for k, v in anchor.items() if k != "token_b64"}}


def verify(journal) -> dict:
    """Re-verify every anchor against its pinned roots and the current ledger.

    VERIFIED: the TSA signature is valid and the anchored head is still in the chain.
    REWRITTEN: the anchored head is no longer in this ledger -- anchored history changed.
    INVALID: the token does not verify against the roots pinned when it was made.
    """
    configs = {e.payload.get("roots_sha256"): e.payload for e in journal.replay("proof.anchor_configured")
               if e.payload.get("enabled")}
    chain_ok, chain = journal.ledger.verify_chain()
    present = {r.hash for r in journal.ledger.records}
    results = []
    for event in journal.replay("proof.anchored"):
        a = event.payload
        row = {"head": a["head"], "gen_time": a["gen_time"], "tsa_url": a["tsa_url"],
               "record_count": a["record_count"]}
        try:
            response = decode_timestamp_response(base64.b64decode(a["token_b64"]))
            config = configs.get(a["roots_sha256"])
            if config is None:
                raise AnchorError("pinned roots for this anchor are not in the ledger")
            builder = VerifierBuilder(nonce=int(a["nonce"]), roots=_roots(config["tsa_roots_pem"]))
            builder.build().verify_message(response, _message(a["head"]))
            row["status"] = "VERIFIED" if a["head"] in present else "REWRITTEN"
        except (VerificationError, AnchorError, ValueError) as exc:
            row["status"], row["error"] = "INVALID", str(exc)[:300]
        results.append(row)
    verified = [r for r in results if r["status"] == "VERIFIED"]
    return {"scope": "ledger-internal only: anchors and roots are read from the ledger being checked, "
                     "so a complete ledger rewriter can defeat this check; use verify_witness",
            "chain_intact": chain_ok, "chain": chain, "anchors": len(results),
            "verified": len(verified), "rewritten": [r for r in results if r["status"] == "REWRITTEN"],
            "invalid": [r for r in results if r["status"] == "INVALID"],
            "latest": verified[-1] if verified else None,
            "unanchored_tail": _unanchored_records(journal, verified[-1]["head"] if verified else None),
            "configured": current_config(journal) is not None}


WITNESS_FORMAT = "greg-anchor-witness/1"


def _token_covers(entry: dict, roots: list) -> None:
    """Raise unless ``entry``'s token is a valid TSA signature over its head under ``roots``."""
    response = decode_timestamp_response(base64.b64decode(entry["token_b64"]))
    VerifierBuilder(nonce=int(entry["nonce"]), roots=roots).build().verify_message(response, _message(entry["head"]))


def verify_witness(journal, bundle: dict, roots_pem: str) -> dict:
    """Check a presented ledger against witness state retained OUTSIDE GREG.

    Trust comes only from ``bundle`` (exported earlier and kept elsewhere) and ``roots_pem``
    (supplied by the verifier). The ledger's own proof.anchored / proof.anchor_configured
    records are not consulted: a ledger rewriter controls those.

    Per witnessed head:
      VERIFIED       the TSA token is valid under the verifier's roots and the presented
                     ledger holds exactly that head at the witnessed position;
      DIVERGED       the ledger holds a different record there (rewrite, deletion, substitution,
                     reconstruction);
      ROLLED_BACK    the ledger is shorter than the witnessed position;
      INVALID_TOKEN  the witness entry itself does not verify under the verifier's roots.
    """
    if bundle.get("format") != WITNESS_FORMAT:
        raise AnchorError(f"not a {WITNESS_FORMAT} bundle")
    roots = _roots(roots_pem)
    records = journal.ledger.records
    chain_ok, chain = journal.ledger.verify_chain()
    rows = []
    for w in bundle["witnesses"]:
        row = {"head": w["head"], "record_count": w["record_count"], "gen_time": w["gen_time"]}
        try:
            _token_covers(w, roots)
        except (VerificationError, AnchorError, ValueError) as exc:
            row["status"], row["error"] = "INVALID_TOKEN", str(exc)[:300]
            rows.append(row)
            continue
        n = w["record_count"]
        if not isinstance(n, int) or n < 1:
            row["status"], row["error"] = "INVALID_TOKEN", "witness position must be a positive integer"
        elif n > len(records):
            row["status"] = "ROLLED_BACK"
        elif records[n - 1].hash != w["head"]:
            row["status"], row["presented"] = "DIVERGED", records[n - 1].hash
        else:
            row["status"] = "VERIFIED"
        rows.append(row)
    ok = [r for r in rows if r["status"] == "VERIFIED"]
    if not rows:
        verdict = "NO_WITNESS"
    elif chain_ok and len(ok) == len(rows):
        verdict = "VERIFIED"
    else:
        verdict = "FAILED"
    covered = max((r["record_count"] for r in ok), default=0)
    return {"verdict": verdict, "chain_intact": chain_ok, "chain": chain, "witnesses": rows,
            "witnessed_records": covered, "unwitnessed_tail_records": len(records) - covered,
            "scope": "witnessed prefix only; records after the latest witnessed head are not covered"}


def export_witness(journal, roots_pem: str, existing: dict | None = None) -> dict:
    """Build or extend a witness bundle to be stored outside GREG's rewrite domain.

    Only anchors whose tokens verify under the verifier-supplied roots are admitted, so an
    anchor injected under a substituted TSA root never becomes witness state. An existing
    bundle is append-only: if the presented ledger contradicts it, export is refused.
    """
    roots = _roots(roots_pem)
    bundle = existing or {"format": WITNESS_FORMAT, "witnesses": []}
    if bundle["witnesses"]:
        report = verify_witness(journal, bundle, roots_pem)
        if report["verdict"] != "VERIFIED":
            raise AnchorError(f"presented ledger contradicts the retained witness: {report['verdict']}")
    known = {w["head"] for w in bundle["witnesses"]}
    admitted, rejected = [], []
    for event in journal.replay("proof.anchored"):
        a = event.payload
        if a["head"] in known:
            continue
        entry = {k: a[k] for k in ("head", "record_count", "gen_time", "tsa_url", "nonce", "token_b64")}
        try:
            _token_covers(entry, roots)
        except (VerificationError, AnchorError, ValueError) as exc:
            rejected.append({"head": a["head"], "error": str(exc)[:200]})
            continue
        admitted.append(entry)
    bundle = {**bundle, "witnesses": sorted(bundle["witnesses"] + admitted, key=lambda w: w["record_count"])}
    return {"bundle": bundle, "admitted": len(admitted), "rejected": rejected}


def summary(journal) -> dict:
    """Compact projection for status and the morning report."""
    report = verify(journal)
    failures = journal.replay("proof.anchor_failed")
    return {"configured": report["configured"], "anchors": report["anchors"], "verified": report["verified"],
            "rewritten": len(report["rewritten"]), "invalid": len(report["invalid"]),
            "latest_gen_time": report["latest"]["gen_time"] if report["latest"] else None,
            "latest_tsa": report["latest"]["tsa_url"] if report["latest"] else None,
            "last_failure": failures[-1].payload if failures else None}
