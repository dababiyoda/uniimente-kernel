"""One founder-signed, bounded, revocable grant over a reviewed set of read-only methods.

Founder directive 2026-11-22 (item 2): "Find where GREG has a qualified read-only method that would help but keeps
stopping for attachment. Build and test a way for me to authorize a reviewed set of methods in one signed, bounded,
revocable grant, using existing controls wherever possible. Make the grant specific about which tools, data,
resources, and time window it covers. Inside that scope, GREG should select and combine tools without asking again
each time. Spending, sending, publishing, deployment, sensitive access, and permission changes still require their
own applicable authority."

The stop it removes. A fresh body holds 103 read-only cognition families VERIFIED and withheld (catalog
``initial_state``); each one a mission reaches blocks the mission on a CAPABILITY_ATTACH ask, and after the founder
attaches it the next family the mission reaches blocks it again. One founder interruption per method.

What it is. Not a new authority plane and not a new enforcement point. A ``CAPABILITY_GRANT`` (founder key only; a
device cannot sign it) records one ``capability.grant`` fact and then writes the ordinary ``capability.state``
ATTACHED record for each covered capability, marked ``by: grant``. Everything that already decides whether a
capability may run reads those records: the Kernel's ``AuthorityOffice.attach_refusal`` (only ATTACHED executes), the
registry projections (``Body._apply_capability_states``, ``cortex.registry_view``) and the Competency Compiler's
eligibility. Every act still crosses the mission's signed light cone, policy and the Consequence Gate.

Scope, all of it checked before anything is attached (one ineligible capability refuses the whole grant):

* **tools**: exact capability ids, each bound to the digest of the manifest the founder reviewed. A manifest that
  later differs is no longer covered.
* **consequence**: ``read_only`` only, with no network, no filesystem, no credentials and a zero spending ceiling.
  Spending, sending, publishing, deployment, sensitive access and permission changes are therefore outside any grant;
  they keep their own authority (the mission's light cone, exact-scope DECISIONs, the Gate).
* **data**: the data classes the grant names; a capability declaring any other class is refused.
* **resources**: ``max_uses``, the number of Gate receipts whose cognitive answer was served by a granted method.
* **time**: ``not_before`` .. ``expires_at``, at most ``MAX_WINDOW``.

It ends by itself. ``sweep`` runs at the start of every body turn, paused or not, and when a grant command is
applied: an expired, exhausted or revoked grant detaches every capability whose latest state record is that grant's
own attach (a capability the founder attached on its own, or Genesis quarantined since, is left as it is). A grant
attaches each capability at most once: a founder detach or a quarantine during the window is never undone by it. A
``CAPABILITY_GRANT_REVOKE`` ends it at once. Records are keyed facts, so a restart re-derives the same state and
never writes them twice. A grant never attaches a capability that is QUARANTINED or merely DISCOVERED.

Limits: ``max_uses`` counts receipts at turn boundaries, so a turn that begins under the ceiling may finish the
actions it selected; sensitivity and premises re-runs inside one compiled answer are one use. The window is read from
the body's clock. A grant authorizes nothing a revoked device key signed: it is founder-key only.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from greg.journal import iso
from greg.missions import MissionError
from greg.founder import instant

GRANT_KIND, REVOKE_KIND = "CAPABILITY_GRANT", "CAPABILITY_GRANT_REVOKE"
BODY_KEYS = {"grant_id", "capabilities", "data_classes", "not_before", "expires_at", "max_uses", "purpose"}
MAX_WINDOW = timedelta(days=30)
MAX_CAPABILITIES = 200
MAX_USES = 100_000
ATTACHABLE_STATES = ("VERIFIED", "DETACHED", "ATTACHED")
BY = "grant"


def eligibility(manifest, state, data_classes) -> str | None:
    """Why this capability may not be covered by a method grant, or None."""
    cid = manifest.capability_id
    if state not in ATTACHABLE_STATES:
        return f"{cid} is {state}; a grant covers only verified capabilities"
    if manifest.consequence_class != "read_only":
        return f"{cid} is {manifest.consequence_class}; a grant covers read-only methods only"
    if manifest.network != "none":
        return f"{cid} uses the network ({manifest.network}); sending needs its own authority"
    if manifest.filesystem != "none":
        return f"{cid} touches the filesystem ({manifest.filesystem}); a grant covers no file access"
    if manifest.credentials:
        return f"{cid} needs credentials; sensitive access needs its own authority"
    if float(manifest.budget_ceiling_usd or 0) != 0.0:
        return f"{cid} may spend up to ${manifest.budget_ceiling_usd}; spending needs its own authority"
    extra = sorted(set(manifest.data_classes) - set(data_classes))
    if extra:
        return f"{cid} declares data classes {extra} the grant does not name"
    ok, why = manifest.available()
    if not ok:
        return f"{cid} is not available on this body: {why}"
    return None


def _parse(body) -> dict:
    if not isinstance(body, dict) or set(body) != BODY_KEYS:
        raise MissionError(f"a capability grant takes exactly {sorted(BODY_KEYS)}")
    gid, caps, classes = body["grant_id"], body["capabilities"], body["data_classes"]
    if not isinstance(gid, str) or not 1 <= len(gid) <= 64:
        raise MissionError("grant_id names the grant in 1 to 64 characters")
    if not isinstance(caps, dict) or not 1 <= len(caps) <= MAX_CAPABILITIES or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in caps.items()):
        raise MissionError("capabilities maps each capability id to the manifest digest the founder reviewed")
    if not isinstance(classes, list) or not all(isinstance(c, str) for c in classes):
        raise MissionError("data_classes lists the data classes the grant covers (may be empty)")
    uses = body["max_uses"]
    if isinstance(uses, bool) or not isinstance(uses, int) or not 1 <= uses <= MAX_USES:
        raise MissionError(f"max_uses is a whole number from 1 to {MAX_USES}")
    start, end = instant(body["not_before"]), instant(body["expires_at"])
    if not end > start or end - start > MAX_WINDOW:
        raise MissionError(f"the window runs forward and lasts at most {MAX_WINDOW.days} days")
    if not isinstance(body["purpose"], str) or not body["purpose"].strip():
        raise MissionError("purpose states what the grant is for")
    return {"grant_id": gid, "capabilities": dict(caps), "data_classes": sorted(set(classes)),
            "not_before": iso(start), "expires_at": iso(end), "max_uses": uses, "purpose": body["purpose"].strip()}


def grants(journal) -> dict:
    """grant id -> its record and whether a revocation ended it."""
    out = {e.payload["grant_id"]: {**e.payload, "revoked": None} for e in journal.replay("capability.grant")
           if e.type == "greg.capability.grant"}
    for e in journal.replay("capability.grant_revoked"):
        if e.payload["grant_id"] in out:
            out[e.payload["grant_id"]]["revoked"] = e.payload
    return out


def apply_grant(body, payload, digest, now: datetime) -> dict:
    record = _parse(payload)
    if record["grant_id"] in grants(body.journal):
        raise MissionError(f"grant {record['grant_id']} already exists; grants are never re-issued under one id")
    refusals = []
    for cid, reviewed in record["capabilities"].items():
        manifest = body.registry.manifests.get(cid)
        if manifest is None:
            refusals.append(f"{cid} is not registered on this body")
            continue
        if manifest.digest() != reviewed:
            refusals.append(f"{cid}'s manifest is not the one reviewed (digest {manifest.digest()[:19]}...)")
            continue
        why = eligibility(manifest, body.registry.state[cid], record["data_classes"])
        if why:
            refusals.append(why)
    if refusals:
        raise MissionError("capability grant refused, nothing attached: " + "; ".join(refusals))
    record.update({"command_digest": digest, "applied_at": iso(now),
                   "receipts_before": len(body.ledger.by_type("receipt")), "authority_created": False,
                   "excludes": "spending, sending, publishing, deployment, sensitive access, permission changes"})
    body.journal.record("capability.grant", record, key=record["grant_id"])
    return {"grant_id": record["grant_id"], **sweep(body, now)}


def apply_revoke(body, payload, digest, now: datetime) -> dict:
    if not isinstance(payload, dict) or set(payload) != {"grant_id", "reason"} or not isinstance(
            payload["reason"], str) or not payload["reason"].strip():
        raise MissionError("a grant revocation takes grant_id and a stated reason")
    known = grants(body.journal)
    if payload["grant_id"] not in known:
        raise MissionError(f"no grant {payload['grant_id']!r} on this body")
    if known[payload["grant_id"]]["revoked"] is None:
        body.journal.record("capability.grant_revoked", {"grant_id": payload["grant_id"],
                                                         "reason": payload["reason"].strip(),
                                                         "command_digest": digest, "at": iso(now)},
                            key=payload["grant_id"])
    return {"grant_id": payload["grant_id"], **sweep(body, now)}


def uses(body, record) -> int:
    """Gate receipts since the grant whose cognitive answer a granted method served."""
    covered, count = set(record["capabilities"]), 0
    for rec in body.ledger.by_type("receipt")[record["receipts_before"]:]:
        output = ((rec.payload.get("result") or {}).get("output")) if isinstance(rec.payload, dict) else None
        if isinstance(output, dict) and covered & {output.get("method"), output.get("method_or_composition_selected")}:
            count += 1
    return count


def status(body, record, now: datetime) -> str:
    if record["revoked"] is not None:
        return "REVOKED"
    if now >= instant(record["expires_at"]):
        return "EXPIRED"
    if uses(body, record) >= record["max_uses"]:
        return "EXHAUSTED"
    if now < instant(record["not_before"]):
        return "NOT_YET"
    return "ACTIVE"


def _states(journal) -> tuple[dict, set]:
    """The latest state record per capability, and every (capability, grant) a grant has ever attached."""
    latest, touched = {}, set()
    for e in journal.replay("capability.state"):
        latest[e.payload["capability_id"]] = e.payload
        if e.payload.get("by") == BY:
            touched.add((e.payload["capability_id"], e.payload.get("grant_id")))
    return latest, touched


def sweep(body, now: datetime) -> dict:
    """Attach what an active grant covers; detach what an ended grant attached. Idempotent across restarts."""
    attached, detached = [], []
    latest, touched = _states(body.journal)
    for gid, record in grants(body.journal).items():
        state = status(body, record, now)
        for cid, reviewed in sorted(record["capabilities"].items()):
            manifest, last = body.registry.manifests.get(cid), latest.get(cid, {})
            ours = last.get("by") == BY and last.get("grant_id") == gid and last.get("state") == "ATTACHED"
            if state == "ACTIVE" and not ours:
                # A grant attaches each capability at most once. Whatever follows its attach is final for this grant:
                # a founder CAPABILITY_DETACH, a Genesis quarantine, or the grant's own end. Re-attaching would undo a
                # founder act (or a quarantine) with a grant that predates it.
                if (manifest is None or manifest.digest() != reviewed or body.registry.state.get(cid) == "ATTACHED"
                        or (cid, gid) in touched):
                    continue
                if eligibility(manifest, body.registry.state[cid], record["data_classes"]) is None:
                    body.registry.set_state(cid, "ATTACHED")
                    body.journal.record("capability.state", {"capability_id": cid, "state": "ATTACHED", "by": BY,
                                                             "grant_id": gid, "command_digest": record["command_digest"]},
                                        key=[cid, "ATTACHED", BY, gid])
                    attached.append(cid)
            elif state != "ACTIVE" and ours:
                body.registry.set_state(cid, "DETACHED")
                body.journal.record("capability.state", {"capability_id": cid, "state": "DETACHED", "by": BY,
                                                         "grant_id": gid, "why": f"grant {state.lower()}",
                                                         "at": iso(now)}, key=[cid, "DETACHED", BY, gid])
                detached.append(cid)
    return {"attached": attached, "detached": detached}


def report(body, now: datetime) -> list[dict]:
    """What each grant covers and its state now: for the founder's surfaces."""
    return [{"grant_id": gid, "state": status(body, r, now), "capabilities": sorted(r["capabilities"]),
             "data_classes": r["data_classes"], "window": [r["not_before"], r["expires_at"]],
             "uses": uses(body, r), "max_uses": r["max_uses"], "purpose": r["purpose"]}
            for gid, r in grants(body.journal).items()]
