"""A revoked device key: the trail of what it no longer authorizes, and the retrospective integrity review.

Founder policy, 2026-11-11 (docs/intent/sources/REVOKED-DEVICE-AUTHORITY-2026-11-11-source.md): revoking a device
invalidates at once its unused authority to authorize future execution; what was legitimately completed stays in
the evidence ledger; a suspected key compromise opens a separate retrospective integrity review; the historical
validity of a signature is not its continuing authority to approve a new effect.

The rule itself is the mission fold's (greg/missions.py ``MissionBook._revoked``): from the ledger position of a
``device.revoked`` record, an answer that key signed authorizes nothing it had not already been used for. This
module owns no authority and decides nothing. It writes what the fold already derived, so the founder's surfaces
and a later reader find it on the ledger, and it builds the review:

- ``settle`` records one ``decision.withdrawn`` for each answer a revocation voided (the request, the device, the
  revocation, the answer and the command that carried it). The original answer, its command and every receipt stay
  as recorded. It is derived from the fold, so a body that died after the revocation and before its trail finishes
  it on the next turn, and writing it twice is impossible (one fact identity per request and revocation).
- A founder DEVICE_REVOKE that says ``suspected_compromise: true`` also opens a review: one
  ``device.integrity_review`` record listing every accepted command that key signed and every effect that rested on
  one, read from the ledger as it stood at the revocation, and one founder ask (DEVICE_INTEGRITY_REVIEW) on the
  surfaces that already show pending decisions. The review rewrites nothing and revokes nothing further; the answer
  to its ask is only recorded, and only the founder key gives it (greg.asks FOUNDER_KEY_ANSWERS).

Limits: a command the body refused is not attributed to a key (the ledger keeps its digest and reason, not its
signer). What a mission did after the key resumed it or the body ran under that mission's own founder-signed
mandate; the review lists the resume, not everything after it. A ledger shows what a key signed, never who held it.
"""
from __future__ import annotations

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from greg import asks
from greg.founder import signing_bytes
from greg.journal import Journal
from greg.missions import MissionBook, MissionError
from provenance.ledger import sha256_json

SUSPECTED = "suspected_compromise"
REVIEW_ASK = "DEVICE_INTEGRITY_REVIEW"
REVIEW_RECORD = "device.integrity_review"
ASK_SHOWN = 20          # rows of each list the ask itself carries; the review record on the ledger holds them all
UNKNOWN = (
    "commands signed with this key that the body refused: a refused file is kept under inbox/rejected and the "
    "ledger holds its digest and reason (command.rejected), not its signer",
    "what a mission did after this key resumed it, or the body: it ran under the mission's own founder-signed "
    "mandate and is not listed as resting on the device",
    "who held the key: each signature listed verifies against the delegated key, which is all a ledger can show",
)


def revoke_fields(body: dict) -> tuple[str | None, bool]:
    """(device key id, suspected compromise) of a DEVICE_REVOKE body, or MissionError.

    A plain revocation is exactly ``{"device_key_id": ...}``, as before. ``suspected_compromise`` is optional and,
    when given, is exactly ``true``: there is no way to sign "not suspected" that a reader could mistake for a
    clearance."""
    if not isinstance(body, dict) or set(body) - {"device_key_id", SUSPECTED} or "device_key_id" not in body:
        raise MissionError("revocation needs exactly one currently delegated device_key_id")
    if not isinstance(body["device_key_id"], str):
        raise MissionError("revocation needs exactly one currently delegated device_key_id")
    if SUSPECTED in body and body[SUSPECTED] is not True:
        raise MissionError("suspected_compromise, when given, is exactly true")
    return body["device_key_id"], SUSPECTED in body


def review_id(revoked) -> str:
    """The request id of the one review a suspected-compromise revocation opens."""
    return "review-" + sha256_json({"device": revoked.payload.get("device_key_id"),
                                    "revocation": revoked.event_id})[7:31]


class _AsOf:
    """The journal through one event, inclusive: a book folded over it is the book as that event left it."""

    def __init__(self, journal: Journal, through: int):
        self.ledger, self._journal, self._through = journal.ledger, journal, through
        self._pos = journal.positions("")

    def replay(self, kind_prefix: str = "") -> list:
        return [e for e in self._journal.replay(kind_prefix) if self._pos.get(e.event_id, 1 << 60) <= self._through]


def _verifies(envelope, public_hex) -> bool:
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_hex)).verify(
            bytes.fromhex(envelope["signature"]), signing_bytes(envelope))
    except (InvalidSignature, ValueError, KeyError, TypeError):
        return False
    return True


def _standing(book: MissionBook, rid, answer: dict | None, digest: str, revoked_event: str) -> str:
    """Where one DECISION of the revoked key stands as the revocation left the book."""
    if answer is None or answer.get("command_digest") != digest:
        return "NOT_COUNTED: the mission fold does not count this answer"
    void = book.voided.get(rid)
    if void is not None:
        return ("VOIDED_BY_THIS_REVOCATION: what ran under it stays as recorded; it authorizes nothing more, and "
                "the decision is asked again if it is needed again"
                if void["voided_by"].get("revocation_event") == revoked_event else
                "VOIDED_BY_AN_EARLIER_REVOCATION of this key")
    kind, given = (book.requests.get(rid) or {}).get("kind"), answer.get("answer")
    if kind == "APPROVAL" and given == "approve":
        if rid in book.withdrawn:
            return "WITHDRAWN_EARLIER: " + str(book.withdrawn[rid].get("why"))[:200]
        return ("USED: its one paid run happened" if rid in book.consumed else
                "STANDING: the fold did not attribute this approval to the revoked key; review it first")
    if kind == "RECONCILIATION":
        return "USED: the reconciliation it gave is recorded"
    if given == "reject":
        return "REJECTION_STANDS: a rejection authorizes nothing"
    return "RECORD_ONLY: this answer authorizes no action"


def _action_row(event, basis: str, rested_on: dict) -> dict:
    p = event.payload
    return {"effect": basis, "event_id": event.event_id, "mission_id": p.get("mission_id"),
            "action_id": p.get("action_id"), "attempt": p.get("attempt"), "status": p.get("status"),
            "capability": p.get("capability"), "scope_digest": p.get("scope_digest"), "receipt": p.get("receipt"),
            "cost_usd": p.get("cost_usd"), "at": p.get("at"), "rested_on": rested_on}


def build_review(journal: Journal, revoked) -> dict:
    """Every accepted command the revoked key signed and every effect that rested on one, from the ledger as the
    revocation left it. A pure reading: the same revocation gives the same review whenever it is built."""
    pos = journal.positions("")
    cut = pos[revoked.event_id]
    asof = _AsOf(journal, cut)
    book = MissionBook(asof)
    kid = revoked.payload["device_key_id"]
    delegations = [e.payload for e in asof.replay("device.enrolled") if e.payload.get("device_key_id") == kid]
    public = delegations[-1].get("public_key") if delegations else None
    accepted = [e for e in asof.replay("command.accepted") if e.payload.get("founder_key_id") == kid
                and str(e.payload.get("signer") or "").startswith("device:")]
    withdrawn_at = {}
    for e in asof.replay("decision.withdrawn"):
        withdrawn_at.setdefault(e.payload.get("request_id"), pos[e.event_id])
    # The Gate's own grant records, by ledger position: a dispatch it granted on an approval that the mission had
    # not recorded yet when the key was revoked (the body stopped inside it) is an effect all the same.
    ledger = journal.ledger
    seq = {r.payload.get("event_id"): r.seq for r in ledger.by_type("event")}
    granted = [r for r in ledger.by_type("event") if r.payload.get("type") == "greg.authority.grant_issued"
               and r.payload.get("founder_approved_scope") and r.seq < seq[revoked.event_id]]
    actions = asof.replay("mission.action")
    compensated = asof.replay("mission.compensated")
    lifecycles = {e.payload.get("command_digest"): e for e in asof.replay("mission.lifecycle")}
    critiques = {e.payload.get("command_digest"): e.payload for e in asof.replay("critique.recorded")}
    excluded = asof.replay("mission.strategy_excluded")
    commands, effects = [], []
    for event in accepted:
        c = event.payload
        env = c.get("envelope") if isinstance(c.get("envelope"), dict) else {}
        signed = env.get("body") if isinstance(env.get("body"), dict) else {}
        digest, kind, at = c.get("digest"), c.get("kind"), pos[event.event_id]
        row = {"command_digest": digest, "kind": kind, "signer": c.get("signer"), "issued_at": c.get("issued_at"),
               "accepted_at": c.get("accepted_at"), "channel": c.get("channel"),
               "signature_verifies": bool(public) and sha256_json(env) == digest and _verifies(env, public)}
        basis = {"command_digest": digest, "kind": kind}
        if kind == "DECISION":
            rid = signed.get("request_id")
            request, answer = book.requests.get(rid) or {}, book.answers.get(rid)
            row.update(request_id=rid, answer=signed.get("answer"), request_kind=request.get("kind"),
                       mission_id=request.get("mission_id"), action_id=request.get("action_id"),
                       scope_digest=request.get("scope_digest"),
                       standing=_standing(book, rid, answer, digest, revoked.event_id))
            basis["request_id"] = rid
            counted = answer is not None and answer.get("command_digest") == digest
            if counted and request.get("kind") == "APPROVAL" and signed.get("answer") == "approve":
                end = min(withdrawn_at.get(rid, cut), cut)     # the approval stood from its acceptance to here
                recorded = set()                               # grants the mission's own records account for
                for e in actions:
                    p = e.payload
                    if (p.get("mission_id") == request.get("mission_id") and at < pos[e.event_id] <= end
                            and p.get("scope_digest") == request.get("scope_digest")
                            and p.get("route") not in ("founder_reconciliation", "standing_reconciliation")
                            and (p.get("receipt") or p.get("status") == "UNCERTAIN")):
                        effects.append(_action_row(e, "an action dispatched under its approval", basis))
                        receipt = ledger.find(p["receipt"]) if p.get("receipt") else None
                        recorded.add(receipt.payload.get("grant_id") if receipt is not None else p.get("grant_id"))
                for r in granted:
                    g = r.payload
                    if g.get("scope_digest") == request.get("scope_digest") and r.seq > seq[event.event_id] \
                            and g.get("grant_id") not in recorded:
                        effects.append({"effect": "a dispatch the Gate granted under its approval, not yet recorded "
                                                  "by the mission when the key was revoked",
                                        "mission_id": request.get("mission_id"), "action_id": request.get("action_id"),
                                        "scope_digest": g.get("scope_digest"), "grant_id": g.get("grant_id"),
                                        "proposal_id": g.get("proposal_id"), "rested_on": basis})
                for e in compensated:
                    p = e.payload
                    if (p.get("mission_id") == request.get("mission_id") and at < pos[e.event_id] <= end
                            and p.get("scope_digest") == request.get("scope_digest")):
                        effects.append({**_action_row(e, "a compensation dispatched under its approval", basis),
                                        "original_receipt": p.get("original_receipt")})
            elif counted and request.get("kind") == "RECONCILIATION":
                for e in actions:
                    p = e.payload
                    named = (p.get("reconciles") or {}).get("request_id")
                    if p.get("route") == "founder_reconciliation" and pos[e.event_id] > at and (
                            named == rid or (named is None and p.get("mission_id") == request.get("mission_id")
                                             and p.get("action_id") == request.get("action_id"))):
                        effects.append(_action_row(e, "an interrupted dispatch settled by its answer", basis))
            elif counted and request.get("kind") == "COMPENSATION":
                for e in compensated:
                    if e.payload.get("request_id") == rid:
                        effects.append(_action_row(e, "a compensation obligation closed by its answer", basis))
        elif kind == "LIFECYCLE":
            row.update(mission_id=signed.get("mission_id"), state=signed.get("state"))
            applied = lifecycles.get(digest)
            if applied is not None:
                effects.append({"effect": "a mission lifecycle it set", "event_id": applied.event_id,
                                "mission_id": applied.payload.get("mission_id"),
                                "state": applied.payload.get("state"), "rested_on": basis})
                if applied.payload.get("state") in ("ABANDONED", "SUPERSEDED"):
                    for e in compensated:
                        if e.payload.get("mission_id") == applied.payload.get("mission_id") \
                                and pos[e.event_id] > pos[applied.event_id] and e.payload.get("receipt"):
                            effects.append(_action_row(e, "a compensation run after it ended the mission", basis))
        elif kind == "CRITIQUE":
            critique = critiques.get(digest) or {}
            row.update(critique_id=critique.get("critique_id"), target_event_id=signed.get("target_event_id"),
                       verdict=signed.get("verdict"))
            for e in excluded:
                if critique.get("critique_id") and e.payload.get("critique_ref") == critique["critique_id"]:
                    effects.append({"effect": "a strategy excluded by its critique", "event_id": e.event_id,
                                    "mission_id": e.payload.get("mission_id"),
                                    "action_id": e.payload.get("action_id"), "rested_on": basis})
        elif kind == "GOAL_CONTROL":
            row.update(goal_id=signed.get("goal_id"), control=signed.get("kind"), value=signed.get("value"))
        elif kind in ("BODY_PAUSE", "BODY_RESUME", "BODY_STOP"):
            effects.append({"effect": {"BODY_PAUSE": "the body paused by it", "BODY_RESUME": "the body resumed by it",
                                       "BODY_STOP": "the body stopped by it"}[kind], "rested_on": basis})
        commands.append(row)
    voided = sorted(rid for rid, v in book.voided.items() if v["voided_by"].get("revocation_event") == revoked.event_id)
    missions = sorted({str(x.get("mission_id")) for x in commands + effects if x.get("mission_id")})
    return {
        "review_id": review_id(revoked), "status": "OPEN_FOR_FOUNDER_REVIEW",
        "device": {"device_key_id": kid, "label": delegations[-1].get("label") if delegations else None,
                   "delegations": [{k: d.get(k) for k in ("command_digest", "kinds", "expires_at", "at")}
                                   for d in delegations]},
        "revocation": {"event_id": revoked.event_id, "command_digest": revoked.payload.get("command_digest"),
                       "at": revoked.payload.get("at"), SUSPECTED: True},
        "commands": commands, "effects": effects, "voided_by_this_revocation": voided, "missions": missions,
        "receipts": sorted({x["receipt"] for x in effects if x.get("receipt")}),
        "scopes": sorted({x["scope_digest"] for x in commands + effects if x.get("scope_digest")}),
        "read_through": {"event_id": revoked.event_id, "what": "the ledger as this revocation left it"},
        "unknown": list(UNKNOWN),
        "history_rewritten": False, "revokes_further": False, "authority_created": False,
        "at": revoked.payload.get("at")}


def review_ask(review: dict, review_event: str) -> dict:
    """The founder ask for one review, built only from its record (so it is the same whenever it is asked)."""
    device, counts = review["device"], {k: len(review[k]) for k in ("commands", "effects", "voided_by_this_revocation",
                                                                    "missions", "receipts")}
    label = f"{device.get('label') or 'unlabelled'} ({device['device_key_id']})"
    return {
        "request_id": review["review_id"], "kind": REVIEW_ASK, "mission_id": None, "action_id": None,
        "scope_digest": sha256_json({"device": device["device_key_id"], "revocation": review["revocation"]["event_id"]}),
        "why_now": (f"you revoked the device key {label} as a suspected compromise: {counts['commands']} accepted "
                    f"command(s) it signed and {counts['effects']} effect(s) that rested on them are listed for "
                    "your review"),
        "recommendation": "inspect each listed command and receipt; undo or accept each effect yourself, and answer "
                          "again where the revocation voided an approval",
        "alternatives": ["approve: record that you reviewed the list and the recorded history stands",
                         "reject: record that something listed should not stand (GREG undoes nothing by itself)",
                         "leave it open: nothing changes (costs nothing)"],
        "evidence": {"review_event": review_event, "device": {k: device.get(k) for k in ("device_key_id", "label")},
                     "revoked_at": review["revocation"]["at"], "counts": counts,
                     "commands": [{k: c.get(k) for k in ("kind", "command_digest", "accepted_at", "request_id",
                                                         "mission_id", "standing")} for c in review["commands"][:ASK_SHOWN]],
                     "effects": [{k: x.get(k) for k in ("effect", "mission_id", "action_id", "status", "receipt")}
                                 for x in review["effects"][:ASK_SHOWN]],
                     "voided_by_this_revocation": review["voided_by_this_revocation"][:ASK_SHOWN],
                     "truncated": any(len(review[k]) > ASK_SHOWN for k in ("commands", "effects",
                                                                           "voided_by_this_revocation")),
                     "whole_list": "greg device reviews (the device.integrity_review record on the ledger)",
                     "unknown": review["unknown"]},
        "authority_requested": {"command": None, "spend": "none", "execution": "none: a review changes nothing"},
        "consequence_of_no_response": "nothing changes: each listed effect keeps its receipt, what the revocation "
                                      "voided stays void, and this review stays open",
        "created_at": review["at"], "reality_status": "RECORDED_LOCAL_MESSAGE"}


def settle(journal: Journal, book: MissionBook) -> dict:
    """Finish the trail of every device revocation on the ledger; returns what this call wrote.

    Called by the body when it records a revocation and again at the start of each turn, so a body that died
    between a revocation and its trail completes it. Idempotent: every record has one identity."""
    book.rebuild()
    voided, reviews = [], []
    for rid, void in sorted(book.voided.items()):
        if book.withdrawn.get(rid) != void:
            continue                    # another withdrawal of this request is already the record (a restore's)
        key = [rid, "withdrawn", "device-revoked", void["voided_by"].get("revocation_event")]
        if journal.retained("decision.withdrawn", key) is None:
            journal.record("decision.withdrawn", void, key=key)
            voided.append(rid)
    for revoked in journal.replay("device.revoked"):
        if revoked.payload.get(SUSPECTED) is not True:
            continue
        rid = review_id(revoked)
        record = journal.retained(REVIEW_RECORD, [rid])
        if record is None:
            record = journal.record(REVIEW_RECORD, build_review(journal, revoked), key=[rid])
        if journal.retained("decision.requested", rid) is None:
            review = record.payload
            asks.record(journal, review_ask(review, record.event_id), quoted=asks.founder_text(
                [review["missions"], review["device"].get("label"),
                 [[x.get("action_id"), x.get("effect")] for x in review["effects"]],
                 [[c.get("standing"), c.get("request_id")] for c in review["commands"]]]))
            reviews.append(rid)
    if voided or reviews:
        book.rebuild()
    return {"voided": voided, "reviews": reviews}


def summary(journal: Journal, book: MissionBook) -> list[dict]:
    """Each device revocation on the ledger for the founder's status: what it voided and whether a review is open."""
    answered = {rid: a.get("answer") for rid, a in book.answers.items()}
    out = []
    for revoked in journal.replay("device.revoked"):
        p = revoked.payload
        voided = sorted(rid for rid, v in book.voided.items()
                        if v["voided_by"].get("revocation_event") == revoked.event_id)
        row = {"device_key_id": p.get("device_key_id"), "at": p.get("at"),
               "by": p.get("by") or "founder DEVICE_REVOKE", "voided_requests": voided}
        if p.get(SUSPECTED) is True:
            rid = review_id(revoked)
            row["integrity_review"] = {"request_id": rid, "recorded": journal.retained(REVIEW_RECORD, [rid]) is not None,
                                       "state": f"ANSWERED: {answered[rid]}" if rid in answered else "OPEN"}
        out.append(row)
    return out
