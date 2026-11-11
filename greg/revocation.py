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
from greg.authority import AuthorityOffice
from greg.founder import signing_bytes
from greg.journal import Journal
from greg.missions import (GATE_SCOPE_ASKS, RECONCILIATION_ASKS, TERMINAL, MissionBook, MissionError,
                           compensation_attempt)
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
    "what ran after the point this review reads the ledger to: a compensation of a mission this key ended that was "
    "still to run is listed as such, not as run (greg status, security.device_revocations, shows what ran since)",
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


def unreviewed_revocation(journal: Journal, kid: str) -> str | None:
    """The event id of the revocation that ended ``kid``'s latest delegation, when the key stands revoked and no
    review of that revocation was opened yet; else None. A suspicion often arises after the key was revoked: the
    founder then signs DEVICE_REVOKE for it again with ``suspected_compromise`` (greg/body.py), which revokes
    nothing more and opens the review once."""
    ended, reviewed = None, False
    for e in journal.replay("device."):
        if e.payload.get("device_key_id") != kid:
            continue
        if e.type == "greg.device.enrolled":
            ended, reviewed = None, False
        elif e.type == "greg.device.revoked":
            ended = ended or e.event_id
            reviewed = reviewed or e.payload.get(SUSPECTED) is True
    return ended if ended is not None and not reviewed else None


def _revocations(revoked) -> set:
    """The revocation a review is about: this record, and the earlier one it marks as suspected (if it does)."""
    return {revoked.event_id, revoked.payload.get("marks_revocation")} - {None}


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


def _standing(book: MissionBook, rid, answer: dict | None, digest: str, revocations: set) -> str:
    """Where one DECISION of the revoked key stands as the revocation left the book."""
    if answer is None or answer.get("command_digest") != digest:
        return "NOT_COUNTED: the mission fold does not count this answer"
    void = book.voided.get(rid)
    if void is not None:
        return ("VOIDED_BY_THIS_REVOCATION: what ran under it stays as recorded; it authorizes nothing more, and "
                "the decision is asked again if it is needed again"
                if void["voided_by"].get("revocation_event") in revocations else
                "VOIDED_BY_AN_EARLIER_REVOCATION of this key")
    kind, given = (book.requests.get(rid) or {}).get("kind"), answer.get("answer")
    if kind in GATE_SCOPE_ASKS and given == "approve":
        if rid in book.withdrawn:
            return "WITHDRAWN_EARLIER: " + str(book.withdrawn[rid].get("why"))[:200]
        return ("USED: its one paid run happened" if rid in book.consumed else
                "STANDING: the fold did not attribute this approval to the revoked key; review it first")
    if kind in RECONCILIATION_ASKS:
        return "USED: the reconciliation it gave is recorded"
    if given == "reject":
        return "REJECTION_STANDS: a rejection authorizes nothing"
    return "RECORD_ONLY: this answer authorizes no action"


STILL_TO_RUN = ("a signed compensation still to run for a mission it ended: it is dispatched after this point under "
                "the mission's own founder-signed mandate, and the revocation holds nothing back")


def owed_compensations(m, actions: list, compensated: list) -> list[dict]:
    """Executed strategies of mission ``m`` whose signed compensation has no record yet among ``compensated``: what
    an ended mission still dispatches (MissionEngine._compensate). A strategy with no compensation signed runs
    nothing (it is a founder ask or an open obligation) and is not listed."""
    if m is None:
        return []
    done = {}
    for e in actions:
        if e.payload.get("mission_id") == m.mission_id and e.payload.get("status") == "DONE":
            done[e.payload["action_id"]] = e.payload.get("receipt")
    closed = {e.payload.get("action_id") for e in compensated if e.payload.get("mission_id") == m.mission_id}
    return [{"action_id": s["action_id"], "compensate": s.get("compensate"), "receipt": done[s["action_id"]]}
            for s in m.spec.get("strategies", ())
            if s.get("compensate") and s["action_id"] in done and s["action_id"] not in closed]


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
    # Where each approval stopped standing: the first record that withdrew its request (a failed standing run, a
    # restore, a revocation's trail), or the revocation that voided it, which precedes its trail record. For a
    # suspicion signed after a plain revocation that is the earlier revocation, not this marking record.
    stopped: dict = {}
    for e in asof.replay("decision.withdrawn"):
        stopped.setdefault(e.payload.get("request_id"), []).append(e.event_id)
    for rid, void in book.voided.items():
        stopped.setdefault(rid, []).append(void["voided_by"].get("revocation_event"))
    # The Gate's own grant records, by ledger position: a dispatch it granted on an approval that the mission had
    # not recorded yet when the key was revoked (the body stopped inside it) is an effect all the same.
    ledger = journal.ledger
    seq = {r.payload.get("event_id"): r.seq for r in ledger.by_type("event")}
    granted = [r for r in ledger.by_type("event") if r.payload.get("type") == "greg.authority.grant_issued"
               and r.payload.get("founder_approved_scope")]
    actions = asof.replay("mission.action")
    observed = asof.replay("mission.observed")
    compensated = asof.replay("mission.compensated")

    def grant_of(p: dict):
        """The Gate grant one mission record accounts for: its receipt's, the one an unknown outcome names, or for
        a compensation with neither (its dispatch was interrupted) the one the Gate claimed for its proposal."""
        receipt = ledger.find(p["receipt"]) if p.get("receipt") else None
        if receipt is not None or p.get("grant_id") or "original_receipt" not in p:
            return receipt.payload.get("grant_id") if receipt is not None else p.get("grant_id")
        claims = ledger.select("grant_dispatch", proposal_id=AuthorityOffice.proposal_id(
            p.get("scope_digest"), compensation_attempt(p.get("action_id"), p.get("original_receipt"))))
        return claims[-1].payload.get("grant_id") if claims else None
    recorded = {grant_of(e.payload) for e in actions + observed + compensated} - {None}
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
                       standing=_standing(book, rid, answer, digest, _revocations(revoked)))
            basis["request_id"] = rid
            counted = answer is not None and answer.get("command_digest") == digest
            if counted and request.get("kind") in GATE_SCOPE_ASKS and signed.get("answer") == "approve":
                # The approval stood from its acceptance to ``end``. What rested on it: each grant the Gate issued
                # for its exact scope in that span (``under``), and each mission record written in that span or
                # accounting for one of those grants (a dispatch granted under it and recorded only afterwards).
                # A grant issued once it no longer stood rested on another decision (the founder's answer to the
                # ask that followed) and is not this key's.
                ends = [x for x in stopped.get(rid, []) if x in pos] + [revoked.event_id]
                end, end_seq = min(pos[x] for x in ends), min(seq[x] for x in ends)
                under = [r for r in granted if r.payload.get("scope_digest") == request.get("scope_digest")
                         and seq[event.event_id] < r.seq < end_seq]
                grants = {r.payload.get("grant_id") for r in under}

                def rested(e) -> bool:
                    return (e.payload.get("mission_id") == request.get("mission_id")
                            and (at < pos[e.event_id] <= end or grant_of(e.payload) in grants))
                for e in observed if grants else ():
                    # an observation outside the cone (SENSOR_SCOPE): its record names no scope, its receipt's grant does
                    p = e.payload
                    if p.get("mission_id") == request.get("mission_id") and grant_of(p) in grants:
                        effects.append({"effect": "an observation read under its approval", "event_id": e.event_id,
                                        "mission_id": p.get("mission_id"), "check_id": p.get("check_id"),
                                        "capability": p.get("capability"), "receipt": p.get("receipt"),
                                        "scope_digest": request.get("scope_digest"), "grant_id": grant_of(p),
                                        "at": p.get("at"), "rested_on": basis})
                for e in actions:
                    p = e.payload
                    if (rested(e) and p.get("scope_digest") == request.get("scope_digest")
                            and p.get("route") not in ("founder_reconciliation", "standing_reconciliation")
                            and (p.get("receipt") or p.get("status") == "UNCERTAIN")):
                        effects.append(_action_row(e, "an action dispatched under its approval", basis))
                for r in under:
                    g = r.payload
                    if g.get("grant_id") not in recorded:
                        effects.append({"effect": "a dispatch the Gate granted under its approval, not yet recorded "
                                                  "by the mission at the point this review reads the ledger to",
                                        "mission_id": request.get("mission_id"), "action_id": request.get("action_id"),
                                        "scope_digest": g.get("scope_digest"), "grant_id": g.get("grant_id"),
                                        "proposal_id": g.get("proposal_id"), "rested_on": basis})
                for e in compensated:
                    p = e.payload
                    if rested(e) and p.get("scope_digest") == request.get("scope_digest"):
                        effects.append({**_action_row(e, "a compensation dispatched under its approval", basis),
                                        "original_receipt": p.get("original_receipt")})
            elif counted and request.get("kind") in RECONCILIATION_ASKS:
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
                    mid = applied.payload.get("mission_id")
                    for e in compensated:
                        if e.payload.get("mission_id") == mid \
                                and pos[e.event_id] > pos[applied.event_id] and e.payload.get("receipt"):
                            effects.append(_action_row(e, "a compensation run after it ended the mission", basis))
                    # Ending a mission starts the compensations signed with its executed strategies, one Gate
                    # dispatch per turn. Those not yet recorded here run after this point: the revocation holds
                    # nothing back (ADR-20261111, open question 1), so the review says they were still to run.
                    for action in owed_compensations(book.missions.get(mid), actions, compensated):
                        effects.append({"effect": STILL_TO_RUN, "mission_id": mid, "action_id": action["action_id"],
                                        "capability": (action["compensate"] or {}).get("capability"),
                                        "original_receipt": action["receipt"], "rested_on": basis})
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
    voided = sorted(rid for rid, v in book.voided.items()
                    if v["voided_by"].get("revocation_event") in _revocations(revoked))
    missions = sorted({str(x.get("mission_id")) for x in commands + effects if x.get("mission_id")})
    return {
        "review_id": review_id(revoked), "status": "OPEN_FOR_FOUNDER_REVIEW",
        "device": {"device_key_id": kid, "label": delegations[-1].get("label") if delegations else None,
                   "delegations": [{k: d.get(k) for k in ("command_digest", "kinds", "expires_at", "at")}
                                   for d in delegations]},
        "revocation": {"event_id": revoked.event_id, "command_digest": revoked.payload.get("command_digest"),
                       "at": revoked.payload.get("at"), SUSPECTED: True,
                       **({"marks_revocation": revoked.payload["marks_revocation"]}
                          if revoked.payload.get("marks_revocation") else {})},
        "commands": commands, "effects": effects, "voided_by_this_revocation": voided, "missions": missions,
        "receipts": sorted({x["receipt"] for x in effects if x.get("receipt")}),
        "scopes": sorted({x["scope_digest"] for x in commands + effects if x.get("scope_digest")}),
        "read_through": {"event_id": revoked.event_id, "what": "the ledger as this revocation left it"},
        "unknown": list(UNKNOWN),
        "history_rewritten": False, "revokes_further": False, "authority_created": False,
        "at": revoked.payload.get("at")}


def unbuilt_review(revoked, exc: Exception) -> dict:
    """The review record when the reading itself failed: it says so and lists nothing. A review is a reading, and the
    body must keep turning without it (the void of the key's unused authority is the fold's and does not wait for
    it); the founder is still asked, and reads the key's commands on the ledger (``command.accepted`` rows)."""
    kid = revoked.payload.get("device_key_id")
    return {"review_id": review_id(revoked), "status": "COULD_NOT_BE_BUILT",
            "error": f"{type(exc).__name__}: {exc}"[:400],
            "device": {"device_key_id": kid, "label": None, "delegations": []},
            "revocation": {"event_id": revoked.event_id, "command_digest": revoked.payload.get("command_digest"),
                           "at": revoked.payload.get("at"), SUSPECTED: True},
            "commands": [], "effects": [], "voided_by_this_revocation": [], "missions": [], "receipts": [],
            "scopes": [], "read_through": {"event_id": revoked.event_id, "what": "nothing: the reading failed"},
            "unknown": ["everything this key signed: the list could not be built (see error); read the ledger's "
                        "command.accepted rows whose founder_key_id is this key", *UNKNOWN],
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
                    "your review" if review["status"] != "COULD_NOT_BE_BUILT" else
                    f"you revoked the device key {label} as a suspected compromise, and the list of what it signed "
                    f"could not be built ({review.get('error')}): nothing is listed, so read the ledger yourself"),
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
            try:
                review = build_review(journal, revoked)
            except Exception as exc:     # a failed reading is recorded as one; it never stops the body's turn
                review = unbuilt_review(revoked, exc)
            record = journal.record(REVIEW_RECORD, review, key=[rid])
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


def resumed_and_running(journal: Journal, book: MissionBook) -> dict[str, dict]:
    """Per device key: what it resumed that is still running. A mission counts when its latest lifecycle record is
    an ACTIVE that key signed over a pause and the mission has not ended; the body counts when its
    latest pause or resume record is that key's BODY_RESUME. A reading for the founder's status only: a resume is
    not a Gate approval, and revoking the key pauses nothing (ADR-20261111, open question 3)."""
    signer = {e.payload.get("digest"): e.payload.get("founder_key_id") for e in journal.replay("command.accepted")
              if str(e.payload.get("signer") or "").startswith("device:")
              and e.payload.get("kind") in ("LIFECYCLE", "BODY_RESUME")}
    out: dict[str, dict] = {}
    latest, paused = {}, set()
    for e in journal.replay("mission.lifecycle"):
        mid, state = e.payload.get("mission_id"), e.payload.get("state")
        latest[mid] = e.payload.get("command_digest") if state == "ACTIVE" and mid in paused else None
        paused = paused | {mid} if state == "PAUSED" else paused - {mid}
    for mid, digest in sorted(latest.items(), key=lambda kv: str(kv[0])):
        m = book.missions.get(mid)
        if digest in signer and m is not None and m.status not in TERMINAL:
            out.setdefault(signer[digest], {"missions": [], "body": False})["missions"].append(mid)
    state = [e for e in journal.replay("body.") if e.type in ("greg.body.paused", "greg.body.resumed")]
    if state and state[-1].type == "greg.body.resumed" and state[-1].payload.get("command_digest") in signer:
        out.setdefault(signer[state[-1].payload["command_digest"]], {"missions": [], "body": False})["body"] = True
    return out


def ended_and_compensated(journal: Journal, book: MissionBook) -> dict[str, list[dict]]:
    """Per revocation record: each mission the revoked key had ended (ABANDONED or SUPERSEDED) whose compensations
    went on after that revocation: each ``mission.compensated`` record written since (with its status: DONE and
    REFUSED carry a Gate receipt, UNCERTAIN a dispatch of unknown outcome, the others ran nothing), and the signed
    compensations still to run.

    A reading for the founder's status only. Ending a mission is not a Gate approval: its compensations were signed
    by the founder with the mission and run under that mandate, so revoking the key that ended it holds none of
    them back (ADR-20261111, open question 1). A mission counts under the first revocation of the key after the
    command that ended it."""
    pos = journal.positions("")
    signer = {e.payload.get("digest"): e.payload.get("founder_key_id") for e in journal.replay("command.accepted")
              if str(e.payload.get("signer") or "").startswith("device:") and e.payload.get("kind") == "LIFECYCLE"}
    ended = [e for e in journal.replay("mission.lifecycle") if e.payload.get("state") in ("ABANDONED", "SUPERSEDED")
             and e.payload.get("command_digest") in signer]
    if not ended:
        return {}
    actions, compensated = journal.replay("mission.action"), journal.replay("mission.compensated")
    out: dict[str, list[dict]] = {}
    counted = set()
    for revoked in journal.replay("device.revoked"):
        for e in ended:
            mid = e.payload.get("mission_id")
            if signer[e.payload["command_digest"]] != revoked.payload.get("device_key_id") \
                    or pos[e.event_id] > pos[revoked.event_id] or e.event_id in counted:
                continue
            counted.add(e.event_id)
            since = [{"action_id": c.payload.get("action_id"), "status": c.payload.get("status"),
                      "receipt": c.payload.get("receipt")} for c in compensated
                     if c.payload.get("mission_id") == mid and pos[c.event_id] > pos[revoked.event_id]]
            owed = [a["action_id"] for a in owed_compensations(book.missions.get(mid), actions, compensated)]
            if since or owed:
                out.setdefault(revoked.event_id, []).append({
                    "mission_id": mid, "state": e.payload.get("state"),
                    "compensated_since_the_revocation": since, "still_to_run": owed})
    return out


def summary(journal: Journal, book: MissionBook) -> list[dict]:
    """Each device revocation on the ledger for the founder's status: what it voided, what the key resumed that is
    still running, what it ended that was compensated since or still is to be, and whether a review is open."""
    answered = {rid: a.get("answer") for rid, a in book.answers.items()}
    revocations = journal.replay("device.revoked")
    running = resumed_and_running(journal, book) if revocations else {}
    compensating = ended_and_compensated(journal, book) if revocations else {}
    out = []
    for revoked in revocations:
        p = revoked.payload
        voided = sorted(rid for rid, v in book.voided.items()
                        if v["voided_by"].get("revocation_event") == revoked.event_id)
        row = {"device_key_id": p.get("device_key_id"), "at": p.get("at"),
               "by": p.get("by") or "founder DEVICE_REVOKE", "voided_requests": voided}
        if p.get("marks_revocation"):       # a suspicion signed after the key was revoked: it revoked nothing itself
            row["marks_revocation"] = p["marks_revocation"]
        if p.get("device_key_id") in running:     # nothing is paused for it: the founder decides (pause it, or not)
            row["resumed_and_still_running"] = running[p["device_key_id"]]
        if revoked.event_id in compensating:      # nothing is held for it either: the founder decides
            row["ended_and_compensated"] = compensating[revoked.event_id]
        if p.get(SUSPECTED) is True:
            rid = review_id(revoked)
            row["integrity_review"] = {"request_id": rid, "recorded": journal.retained(REVIEW_RECORD, [rid]) is not None,
                                       "state": f"ANSWERED: {answered[rid]}" if rid in answered else "OPEN"}
        out.append(row)
    return out
