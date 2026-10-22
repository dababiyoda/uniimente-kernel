"""Goal Gravity on the GREG body: one canonical persistent operating path (ADR-GOAL-GRAVITY-002).

    founder-signed GOAL --Body.apply (Ed25519, nonce, TTL)--> egregore GoalRegistry on the body ledger
    Body.tick --> tick() before the mission engine; no goal record means no work and no record:
        admission   founder_facts: each retained GOAL / GOAL_CONTROL re-judged at its own ledger position (key
                    valid there, this body, unused nonce, accepted inside its signed validity, and the command
                    path's own check_goal / check_control on the mission book and facts as they stood there);
                    anything else is preserved and quarantined (narrowing only)
        guard       every signed closure (revoke, supersede), stop or change, narrowing preference and priority
                    floor is restored if an unsigned record widened it
        sense       Gate receipts of each check's own sensor read (check predicate recomputed), separate-process
                    appraisals, greg.path, non-quarantined intake (untrusted, judged by what its content names):
                    only new or changed evidence
        reopen      a completed goal whose plan node an attributed observation shows regressed is dormant again
        loop        egregore GoalGravityLoop.turn in body mode: no gate, no executor, no grant
                      awake goal  -> MissionEngine.observe_now for its signed missions (timing only; a mission
                                     awaiting an APPROVAL then prepares in cone while the decision stays open)
                      decision    -> MissionEngine.request_decision (the engine's own APPROVAL, exact scope)
                      information -> greg.goal.notice
        settle      a signature-verified DECISION reject becomes a goal route refusal (both lineages)
    MissionEngine -> AuthorityOffice -> ConsequenceGate stays the only execution path.

The binding opens no ledger, constructs no Gate, issues no grant, holds no executor and writes no
founder ask of its own. Completion of a goal is observation-tier (attributed ledger observations,
recomputed from Gate receipts), never a claim of external verification.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import re
from types import SimpleNamespace
from typing import Any
import weakref

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from egregore.attention import AttentionItem
from egregore.contracts import ContractError, SignalEnvelope, digest, require_text
from egregore.goals import CONSEQUENCE_CLASSES, PREFERENCE_KINDS, PRIORITIES, GoalRegistry, GoalSpec, InterventionSpec, \
    PlanNode, WakeCondition
from egregore.gps import metric_error
from egregore.gravity import GoalGravityLoop
from egregore.relevance import GoalRelevanceRouter, score_signal
from egregore.resources import ResourceGovernor
from events.spine import EventError
from greg import asks, dataplane, path as devpath
from greg.authority import PRINCIPAL, AuthorityOffice
from greg.capabilities import BUILTINS, CapabilityError, CapabilityManifest
from greg.founder import CLOCK_SKEW, MAX_TTL, instant, key_id, signed_before_delegation, signing_bytes, spent_nonce
from greg.journal import SOURCE, iso
from greg.missions import TERMINAL, MissionBook, MissionError, evaluate_predicate, first_choice, measured, \
    pursued_checks, signed_answer, strategy_scope
from provenance.ledger import sha256_json

SCHEMA = "greg-goal-gravity-binding/1"
GOAL_FIELDS = frozenset({"goal", "missions", "max_consequence_class"})
DERIVED_GOAL_FIELDS = ("goal_id", "authority", "execution_authority")
CONTROL_FIELDS = frozenset({"goal_id", "kind", "value", "reason"})
CONTROL_KINDS = PREFERENCE_KINDS + ("revoke",)
# A device key may only narrow a goal (stop_pushing only with value true). Resuming, changing the goal,
# revoking it and authorizing a GOAL need the founder key.
DEVICE_GOAL_CONTROLS = ("stop_pushing", "lower_priority", "never_use_tactic", "do_not_monitor", "ask_before",
                        "forget_route", "revoke_capability")
VERIFIED_KINDS = ("MISSION", "DECISION", "GOAL", "GOAL_CONTROL")
KEY_KINDS = ("ROTATE_FOUNDER_KEY", "DEVICE_ENROLL", "DEVICE_REVOKE")
STOP_KINDS = ("stop_pushing", "change_goal")
# Signed narrowing controls and the goal-state preference list each one appends to.
NARROWING = {"never_use_tactic": "never_use_tactic", "do_not_monitor": "do_not_monitor", "ask_before": "ask_before",
             "forget_route": "forgotten_routes", "revoke_capability": "revoked_capabilities"}
NARROWING_KIND = {v: k for k, v in NARROWING.items()}
ANSWER = {"approve": "accept", "reject": "refuse"}
CLOSED = ("paused", "revoked", "superseded", "completed")
ADMISSION_ACTOR = "greg goal-gravity admission check"
PULL_MIN_INTERVAL = timedelta(seconds=60)   # a goal pulls one mission's observation at most once a minute
PATH_EVENTS = ("greg.mission.achieved", "greg.mission.appraised", "greg.deficit.resolved")
# What an approve of a goal's ask means (the mission engine's own APPROVAL semantics, unchanged by the binding).
APPROVE_MEANS = ("standing approval of this exact scope for the mission's lifetime: the mission runs it whenever "
                 "its own loop selects it again (for example after the check regresses), with no new ask, until the "
                 "mission closes or its signed horizon passes; to end it sooner, exclude the strategy with a signed "
                 "critique or pause or abandon the mission. It is not a one-time execution")
# A paid scope includes the mission's spend state (AuthorityOffice.scope_digest, #157): one paid approval funds one run.
APPROVE_MEANS_PAID = ("approval of one paid run at the spend this ask shows: the mission runs it once, when its own loop "
                      "selects it, and asks you again before any later run (for example after the check regresses). If "
                      "the mission spends before you answer, this ask is withdrawn and asked again at the new spend. "
                      "To end it before it runs, exclude the strategy with a signed critique, or pause or abandon the "
                      "mission; a reject after an approve is refused")


def approve_means(cost_usd, budget_usd) -> str:
    """What an approve of a move costing ``cost_usd`` in a mission with budget ``budget_usd`` means: standing for an
    unpaid scope, one run for a paid one (the engine binds a paid scope to the spend state whenever there is a budget)."""
    return APPROVE_MEANS_PAID if float(cost_usd or 0.0) > 0 and budget_usd is not None else APPROVE_MEANS


def _approve_means_of(r: dict) -> str:
    """``approve_means`` for one recorded APPROVAL, from the cost and budget the ask itself shows."""
    evidence = r.get("evidence") if isinstance(r.get("evidence"), dict) else {}
    budget = evidence.get("budget") if isinstance(evidence.get("budget"), dict) else {}
    return approve_means((r.get("authority_requested") or {}).get("cost_usd", 0.0), budget.get("budget_usd"))


def asks_for_move(r: dict, scope: dict) -> bool:
    """Whether a recorded request is the engine's APPROVAL ask for this exact goal move (``scope`` from
    ``strategy_scope``). It compares the spend-free move digest, so the link survives the mission's spending. A paid
    request recorded before the move digest existed is matched at the spend state its own ask shows
    (``evidence.budget``), an unpaid one by its scope digest. A compensation APPROVAL naming the same strategy is a
    different move (other capability, params or target)."""
    if r.get("kind") != "APPROVAL" or r.get("mission_id") != scope["mission_id"]:
        return False
    if "move_digest" in r:
        return r["move_digest"] == scope["move_digest"]
    if r.get("scope_digest") == scope["scope_digest"]:
        return True
    evidence = r.get("evidence") if isinstance(r.get("evidence"), dict) else {}
    budget = evidence.get("budget") if isinstance(evidence.get("budget"), dict) else {}
    if float(scope.get("cost_usd") or 0.0) <= 0 or "spent_usd" not in budget or "strategy" not in scope:
        return False
    return r.get("scope_digest") == AuthorityOffice.scope_digest(
        mission_id=scope["mission_id"], capability_id=scope["capability"],
        params=scope["strategy"].get("params", {}), target=scope["target"],
        consequence_class=scope["consequence_class"], cost_usd=scope["cost_usd"],
        # the Gate binds booked spend plus reservations of unknown outcomes (#173 ``committed_usd``)
        spent_usd=round(float(budget["spent_usd"]) + float(budget.get("reserved_usd", 0.0)), 9),
        budget_usd=budget.get("budget_usd"))


# A goal plan node may require a function rather than one implementation: ``"<function>@function"`` is
# present when any registered implementation of the function is usable, and a woken goal missing it asks
# Genesis to form it (``_form_requested``).
FUNCTION_VERSION = "function"


class _Genomes:
    """egregore.gps capability view over GREG's one CapabilityRegistry (present = registered + usable)."""

    def __init__(self, registry):
        self.registry = registry

    def get(self, name, version):
        if version == FUNCTION_VERSION:
            return next((m for m in self.registry.by_function(name) if self.registry.usable(m.capability_id)[0]),
                        None)
        m = self.registry.manifests.get(name)
        return m if m is not None and m.version == version and self.registry.usable(name)[0] else None


# -- founder facts, re-derived from retained signed envelopes at their ledger positions --------------------

def _verify_envelope(payload: dict, founders: dict, devices: dict, body_id: str,
                     at: datetime | None = None) -> str | None:
    """Principal of a retained command.accepted whose envelope verifies under a key valid at its position.

    A device delegation must cover the kind and be unexpired when the command was accepted (``at``, the
    body clock the command path judged it at) or, for a record that names no acceptance time, when signed."""
    env = payload.get("envelope")
    if not isinstance(env, dict) or env.get("kind") != payload.get("kind") or sha256_json(env) != payload.get("digest"):
        return None
    if env.get("body_id") != body_id:
        return None
    kid = env.get("founder_key_id")
    try:
        if kid in founders:
            public, principal = founders[kid], "founder"
        elif kid in devices:
            grant = devices[kid]
            when = at or instant(env["issued_at"])
            if env["kind"] not in grant["kinds"] or not when < instant(grant["expires_at"]):
                return None
            if signed_before_delegation(grant, instant(env["issued_at"])):   # an old token never reactivates
                return None
            public, principal = grant["public_key"], "device:" + grant["label"]
        else:
            return None
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public)).verify(bytes.fromhex(env["signature"]),
                                                                        signing_bytes(env))
    except (InvalidSignature, ValueError, KeyError, TypeError):
        return None
    return principal


def _fresh(env: dict, accepted_at: datetime | None) -> str | None:
    """The command path's lifetime check (FounderVerifier.verify), judged at the acceptance time; None = ok."""
    try:
        issued, expires = instant(env["issued_at"]), instant(env["expires_at"])
    except (KeyError, TypeError, ValueError):
        return "unreadable issued_at / expires_at"
    if expires - issued > MAX_TTL or expires <= issued:
        return "command lifetime invalid"
    if accepted_at is not None and not issued - CLOCK_SKEW <= accepted_at < expires:
        return "accepted outside its signed validity (expired or issued in the future)"
    return None


def _when(value: Any) -> datetime | None:
    try:
        return instant(value) if isinstance(value, str) else None
    except ValueError:
        return None


def _manifests_builtin() -> dict:
    return {manifest.capability_id: manifest for manifest, _ in BUILTINS.values()}


@dataclass
class FounderFacts:
    """What founder-signed commands bound to this body establish, each judged at its own ledger position.

    ``signed`` holds commands whose envelope verifies under the key valid at that position, addressed to
    this body, with a nonce no earlier verified accepted command (or verified-then-rejected GOAL /
    GOAL_CONTROL) spent (``greg.founder.spent_nonce``), accepted inside its signed validity. GOAL and GOAL_CONTROL commands must also pass the command
    path's own validators (``check_goal`` / ``check_control``) against the mission book, the capability
    manifests and these facts as they stood at that position. Everything else is retained data only:
    goal-registry state records never feed these facts, so an unsigned record can neither admit, re-open,
    un-mute, re-prioritize nor resume a goal."""
    body_id: str
    signed: dict = field(default_factory=dict)          # digest -> verified, fresh command (+ principal)
    signed_at: dict = field(default_factory=dict)       # digest -> event id of the command.accepted it verified at
    admitted: dict = field(default_factory=dict)        # goal_id -> the GOAL digest that admitted it
    specs: dict = field(default_factory=dict)           # goal_id -> GoalSpec of an admitted goal
    refused: dict = field(default_factory=dict)         # digest -> why a signed GOAL / GOAL_CONTROL does not count
    refused_at: dict = field(default_factory=dict)      # digest -> latest body time the body refused that command
    clock_floor: Any = None                             # latest body-clock time an earlier non-acceptance record states
    restored_at: Any = None                             # latest restore from a backup at this position (#186)
    closed: dict = field(default_factory=dict)          # goal_id -> {status, by, issued_at[, superseded_by]}
    closed_intents: dict = field(default_factory=dict)  # goal intent digest -> issued_at of the signed closure
    stop: dict = field(default_factory=dict)            # goal_id -> last signed stop / resume / change
    narrowing: dict = field(default_factory=dict)       # goal_id -> {state preference key: [values]}
    floor: dict = field(default_factory=dict)           # goal_id -> lowest priority signed (never above the spec's)
    controlled_at: dict = field(default_factory=dict)   # goal_id -> issued_at (instant) of its latest counted control
    authorizations: dict = field(default_factory=dict)  # goal_id -> first egregore.goal_authorized payload
    book: Any = None                                    # MissionBook folded to the end of the ledger (answers
                                                        # counted at their signed DECISION's acceptance)
    manifests: dict = field(default_factory=dict)       # capability id -> manifest, at the end of the ledger
    devices: dict = field(default_factory=dict)         # device key id -> delegation in force at the end of the
                                                        # ledger; a re-delegation carries signed_not_before (its
                                                        # accepted_at), as greg.body.device_delegations does
    revoked_devices: set = field(default_factory=set)   # device key ids a signed DEVICE_REVOKE revoked, or a
                                                        # revocation record removed while delegated

    def open_goals(self) -> dict:
        return {g: self.specs[g] for g in self.admitted if g not in self.closed}

    def stopped(self, goal_id: str) -> dict | None:
        """The signed stop in force for an admitted goal (stop_pushing true or change_goal), else None."""
        s = self.stop.get(goal_id)
        if goal_id not in self.admitted or s is None:
            return None
        return s if s["kind"] == "change_goal" or s["value"] is True else None


class _NoEvents:
    def replay(self, kind_prefix: str = "") -> list:
        return []


def founder_facts(ledger, *, body_id: str | None = None) -> FounderFacts:
    """One pass over the body ledger in order: keys, nonces, mission book, manifests and founder goal facts.

    The first trust-on-first-use enrollment is the root (and names the body); later founder keys, device
    delegations and revocations count only as founder-signed accepted commands that verify at their own
    position. A record written by any other route (an in-process ``command.accepted``, ``device.enrolled``
    or goal-registry record) authenticates nothing."""
    ok, why = ledger.verify_chain()
    if not ok:
        raise EventError(why)
    founders: dict[str, str] = {}
    seen_nonces: set[str] = set()
    book = MissionBook(_NoEvents(), verify_answers=True)
    manifests = _manifests_builtin()
    builtin = set(manifests)
    facts = FounderFacts(body_id=body_id or "", book=book, manifests=manifests)
    devices = facts.devices
    book._signed, book._signed_at = facts.signed, facts.signed_at   # grown in this pass, as each command verifies
    rooted = False
    for rec in ledger.records:
        if rec.record_type == GoalRegistry.AUTHORIZED_RECORD:
            goal = rec.payload.get("goal") if isinstance(rec.payload, dict) else None
            if isinstance(goal, dict) and isinstance(goal.get("goal_id"), str):
                facts.authorizations.setdefault(goal["goal_id"], rec.payload)
            continue
        if rec.record_type != "event" or "event_id" not in rec.payload:
            continue
        kind, p = rec.payload.get("type", ""), rec.payload.get("payload") or {}
        if not kind.startswith("greg."):
            continue
        if kind != "greg.command.accepted":     # the latest body-clock time an earlier record states
            for field_ in ("at", "created_at", "accepted_at"):
                stated = _when(p.get(field_)) if isinstance(p, dict) else None
                if stated is not None and (facts.clock_floor is None or stated > facts.clock_floor):
                    facts.clock_floor = stated
        if kind == "greg.body.restored":
            # A body restored from a backup (greg/recovery.py) refuses every command issued before the restore
            # (Body._after_restore): judged here the same way, from this position on. Unreadable: refuse them all,
            # as the body's own check fails on it.
            facts.restored_at = _when(p.get("restored_at")) or datetime.max.replace(tzinfo=timezone.utc)
        elif kind == "greg.device.revoked":
            # The body's own rule (greg.body.device_delegations): any revocation record removes the device. It only
            # ever narrows who may sign; a restore voids every delegation this way (#186). Delegated again, the key
            # carries signed_not_before, as the body's rule gives it.
            if devices.pop(p.get("device_key_id"), None) is not None:
                facts.revoked_devices.add(p.get("device_key_id"))
        if kind == "greg.founder.enrolled":
            if not rooted:                     # only the first enrollment is the root; later ones are data
                founders[p["key_id"]] = p["public_key"]
                rooted = True
                if body_id is None:
                    facts.body_id = str(p.get("body_id") or "")   # no body named: nothing verifies (fail closed)
            continue
        if kind == "greg.command.rejected":
            nonce = spent_nonce(kind, p)          # the body's rule exactly (it refused the command there)
            if nonce is not None:
                seen_nonces.add(nonce)
            refused_at = _when(p.get("at"))
            if isinstance(p.get("digest"), str) and refused_at is not None:
                facts.refused_at[p["digest"]] = max(refused_at, facts.refused_at.get(p["digest"], refused_at))
            book.fold("command.rejected", p, event_id=rec.payload["event_id"])
            continue
        if kind == "greg.capability.registered":
            try:
                manifest = CapabilityManifest.from_dict(p["manifest"])
                if manifest.capability_id not in builtin:
                    manifests[manifest.capability_id] = manifest
            except (KeyError, TypeError, ValueError):
                pass
        if kind != "greg.command.accepted":
            book.fold(kind[len("greg."):], p, event_id=rec.payload["event_id"])
            continue
        # Only a record that verified at its position, carrying its own envelope's nonce, spends that nonce
        # here (``spent_nonce``, the body's per-record rule); an unverified record spends nothing, so it can
        # never hide a later signed command the body applied (it can only make the body refuse one).
        digest_ = p.get("digest")
        known = isinstance(digest_, str) and digest_ in facts.signed
        if _accepted(facts, p, founders, devices, seen_nonces) is not None:
            seen_nonces.add(spent_nonce(kind, p))
        if not known and isinstance(digest_, str) and digest_ in facts.signed:
            facts.signed_at[digest_] = rec.payload["event_id"]
        book.fold("command.accepted", p, event_id=rec.payload["event_id"])   # a signed DECISION's answer counts here
    book.finish()
    return facts


# verified_decisions memo: ledger -> (records seen, hash of the last one, verified DECISIONs, their acceptance events)
_VERIFIED: "weakref.WeakKeyDictionary" = weakref.WeakKeyDictionary()
# The only records a DECISION's verification reads: the key root, key changes, nonces and acceptance times.
FOUNDER_RECORDS = ("greg.command.accepted", "greg.command.rejected", "greg.founder.enrolled")


def _founder_record(rec) -> bool:
    return rec.record_type == "event" and isinstance(rec.payload, dict) and rec.payload.get("type") in FOUNDER_RECORDS


def _decisions(ledger) -> tuple[dict, dict]:
    """(verified DECISIONs, digest -> the command.accepted event each verified at), from one ``founder_facts`` pass.

    Memoized per ledger and keyed on its last founder record (command.accepted, command.rejected, founder.enrolled):
    while no such record lands, the prefix that decides every DECISION is unchanged (the remembered tail hash chains
    it), so the pass reruns only when a command does. Finding that out reads only the records appended since."""
    records = ledger.records
    cached = _VERIFIED.get(ledger)
    if cached is not None:
        seen, tail, decisions, positions = cached
        if 0 < seen <= len(records) and records[seen - 1].hash == tail \
                and not any(_founder_record(r) for r in records[seen:]):
            _VERIFIED[ledger] = (len(records), records[-1].hash, decisions, positions)
            return decisions, positions
    seen, tail = len(records), records[-1].hash        # before the pass: a record landing during it is re-read next
    facts = founder_facts(ledger)
    decisions = {d: c for d, c in facts.signed.items() if c["kind"] == "DECISION"}
    positions = {d: facts.signed_at[d] for d in decisions}
    _VERIFIED[ledger] = (seen, tail, decisions, positions)
    return decisions, positions


def verified_decisions(ledger) -> dict[str, dict]:
    """digest -> founder-signed DECISION that ``founder_facts`` counts as signed at its own ledger position.

    The one verifier every reader that decides on a founder answer shares: the mission fold (``MissionBook``, with
    ``signed_answer``) and, through the book, the human-judgment return path, the founder surfaces and the sandbox
    diagnostic; the goal lineage reads the same ``founder_facts`` pass. Read-only: the dict is the memo's."""
    return _decisions(ledger)[0]


def decision_positions(ledger) -> dict[str, str]:
    """digest -> event id of the ``command.accepted`` record each verified DECISION counts at: where its answer
    takes effect."""
    return _decisions(ledger)[1]


def _accepted(facts: FounderFacts, p: dict, founders: dict, devices: dict, seen_nonces: set) -> str | None:
    """Judge one retained ``command.accepted`` at its ledger position.

    Returns the principal when its envelope verifies there under a key valid at that position and the record
    carries that envelope's nonce (the record then spends it), else None. Every kind's envelope is checked
    for that; only VERIFIED_KINDS and KEY_KINDS go on to become founder facts."""
    ckind, digest_ = p.get("kind"), p.get("digest")
    env = p.get("envelope")
    if not isinstance(env, dict):
        return None
    accepted_at = _when(p.get("accepted_at"))
    auth = None
    if ckind == "GOAL" and accepted_at is None:    # older records: the goal record carries the body clock
        try:
            auth = facts.authorizations.get(_spec(env.get("body"), digest_).goal_id)
        except (ContractError, MissionError, KeyError, TypeError, ValueError):
            auth = None
        accepted_at = _when((auth or {}).get("authorized_at"))
    principal = _verify_envelope(p, founders, devices, facts.body_id, accepted_at)
    if principal is None:
        return None
    issued = _when(env.get("issued_at"))
    if facts.restored_at is not None and (issued is None or issued < facts.restored_at):
        # Body.apply refuses it (Body._after_restore) and records no acceptance: this record is not one it wrote
        if ckind in VERIFIED_KINDS or ckind in KEY_KINDS:
            facts.refused[digest_] = ("issued before this body was restored from a backup: the body refuses it, so "
                                      "this record spends no nonce and counts for nothing")
        return None
    if not isinstance(p.get("nonce"), str) or p.get("nonce") != env.get("nonce"):
        if ckind in VERIFIED_KINDS or ckind in KEY_KINDS:
            facts.refused[digest_] = ("its record's nonce is not its signed envelope's: not a record Body.apply "
                                      "wrote; it spends no nonce and counts for nothing")
        return None
    if ckind not in VERIFIED_KINDS and ckind not in KEY_KINDS:
        return principal
    if env["nonce"] in seen_nonces:
        facts.refused[digest_] = "replayed nonce: an earlier accepted or verified-then-rejected command used it"
        return principal
    _founder_fact(facts, p, env, ckind, digest_, principal, accepted_at, founders, devices)
    return principal


def _founder_fact(facts: FounderFacts, p: dict, env: dict, ckind: str, digest_: str, principal: str,
                  accepted_at: datetime | None, founders: dict, devices: dict) -> None:
    """One verified, fresh-nonce command at its position: a key change, or a founder fact (MISSION, DECISION,
    GOAL, GOAL_CONTROL) judged with the command path's own validators."""
    stale = _fresh(env, accepted_at)
    if stale is None and accepted_at is None and ckind in ("GOAL", "GOAL_CONTROL"):
        stale = "no acceptance time on the ledger"
    if stale is None and accepted_at is None and ckind in ("MISSION", "DECISION") and facts.clock_floor is not None:
        # no acceptance time recorded (bodies before accepted_at): it happened no earlier than the latest time an
        # earlier record states, so a floor already past the signed expiry proves it was accepted after it
        try:
            if facts.clock_floor >= instant(env["expires_at"]):
                stale = "no acceptance time, and an earlier record is already later than its signed expiry"
        except (KeyError, TypeError, ValueError):
            stale = "unreadable expires_at"
    refused = facts.refused_at.get(digest_)
    if stale is None and refused is not None and (accepted_at is None or accepted_at < refused):
        # the body already refused this very command at ``refused`` (by its own clock); an acceptance claiming an
        # earlier time is a backdated record, never a later re-send the body applied
        stale = "accepted at a time before the body's own refusal of this command"
    if stale is not None:
        facts.refused[digest_] = stale
        return
    body = env["body"]
    try:
        if ckind == "ROTATE_FOUNDER_KEY" and principal == "founder":
            new = key_id(body["new_public_key"])
            # as Body._dispatch refuses it: rotated in, a device key's unexpired old tokens would verify as founder's
            if new in devices or new in facts.revoked_devices:
                facts.refused[digest_] = "rotation to a key that is or was a delegated device key"
                return
            founders.pop(env["founder_key_id"], None)
            founders[new] = body["new_public_key"]
        elif ckind == "DEVICE_ENROLL" and principal == "founder":
            kid = key_id(body["public_key"])
            grant = {"public_key": body["public_key"], "label": str(body["label"]), "kinds": tuple(body["kinds"]),
                     "expires_at": body["expires_at"]}
            if kid in facts.revoked_devices:   # re-delegated: nothing signed before its acceptance verifies
                grant["signed_not_before"] = p.get("accepted_at")
            devices[kid] = grant
        elif ckind == "DEVICE_REVOKE" and principal == "founder":
            facts.revoked_devices.add(body.get("device_key_id"))
            devices.pop(body.get("device_key_id"), None)
    except (KeyError, TypeError, ValueError):
        return
    if ckind not in VERIFIED_KINDS:
        return
    facts.signed[digest_] = {**p, "principal": principal}
    try:
        if ckind == "GOAL":
            _admit(facts, body, digest_, principal, env, accepted_at)
        elif ckind == "GOAL_CONTROL":
            gid, ck, value = check_control(facts, body, signer=principal, issued_at=env["issued_at"])
            _apply_control(facts, gid, ck, value, digest_, principal, env["issued_at"])
    except (ContractError, MissionError, KeyError, TypeError, ValueError) as exc:
        facts.refused[digest_] = f"{type(exc).__name__}: {exc}"[:300]


def _admit(facts: FounderFacts, body: Any, digest_: str, principal: str, env: dict, accepted_at: datetime) -> None:
    """A retained GOAL counts only as the command path would have applied it at this position."""
    spec = check_goal(facts, body, digest_, signer=principal, book=facts.book, manifests=facts.manifests,
                      at=accepted_at, issued_at=env["issued_at"])
    auth = facts.authorizations.get(spec.goal_id)
    if auth is None or auth.get("goal") != spec.to_dict():
        raise MissionError("no goal record for exactly this GOAL precedes its acceptance")
    authorized_at = _when(auth.get("authorized_at"))
    if authorized_at is None or _fresh(env, authorized_at) is not None or authorized_at > accepted_at:
        raise MissionError("its goal record is dated outside the GOAL's signed validity or after its acceptance")
    gid = spec.goal_id
    facts.admitted[gid], facts.specs[gid] = digest_, spec
    facts.floor[gid] = spec.priority
    facts.narrowing[gid] = {}
    if spec.supersedes:
        facts.closed[spec.supersedes] = {"status": "superseded", "by": digest_, "superseded_by": gid,
                                         "issued_at": env["issued_at"], "principal": principal}
        _close_intent(facts, spec.supersedes, env["issued_at"])


def _close_intent(facts: FounderFacts, goal_id: str, issued_at: str) -> None:
    intent = _intent(facts.specs[goal_id])
    at = instant(issued_at)
    facts.closed_intents[intent] = max(at, facts.closed_intents.get(intent, at))


def _apply_control(facts: FounderFacts, gid: str, ck: str, value: Any, digest_: str, principal: str,
                   issued_at: str) -> None:
    at = instant(issued_at)
    facts.controlled_at[gid] = max(at, facts.controlled_at.get(gid, at))
    if ck == "revoke":
        facts.closed[gid] = {"status": "revoked", "by": digest_, "issued_at": issued_at, "principal": principal}
        _close_intent(facts, gid, issued_at)
    elif ck in STOP_KINDS:
        facts.stop[gid] = {"kind": ck, "value": value, "by": digest_, "principal": principal, "issued_at": issued_at}
    elif ck == "lower_priority":
        facts.floor[gid] = max(facts.floor[gid], int(value))
    elif ck in NARROWING:
        values = facts.narrowing[gid].setdefault(NARROWING[ck], [])
        text = require_text(ck, value)
        if text not in values:
            values.append(text)


def signed_commands(journal, *kinds: str, body_id: str | None = None) -> dict[str, dict]:
    """digest -> accepted command (plus ``principal``) whose retained envelope still verifies.

    Keys are re-derived in ledger order, never from ``issued_at``: the first trust-on-first-use
    enrollment is the root; later founder keys, device delegations and revocations count only when
    they arrive as founder-signed ROTATE_FOUNDER_KEY / DEVICE_ENROLL / DEVICE_REVOKE commands that
    themselves verify at their position. A record written by any other route (an in-process
    ``command.accepted`` or ``device.enrolled``) authenticates nothing.

    Every envelope must be addressed to this body: ``body_id`` defaults to the one the root enrollment
    names, so the tick and every founder view (projection, status, morning report, evidence, closure)
    agree that a command the same key signed for another body authenticates nothing here. A replayed
    nonce, or an acceptance outside the envelope's signed validity, authenticates nothing either."""
    return {d: c for d, c in founder_facts(journal.ledger, body_id=body_id).signed.items() if c["kind"] in kinds}


def _spec(payload: Any, digest_: str) -> GoalSpec:
    """The GoalSpec a signed GOAL body authorizes; the authority block comes from the signature only."""
    if not isinstance(payload, dict) or set(payload) != GOAL_FIELDS:
        raise MissionError(f"a GOAL takes exactly {sorted(GOAL_FIELDS)}")
    goal, missions = payload["goal"], payload["missions"]
    if not isinstance(goal, dict) or set(goal) & set(DERIVED_GOAL_FIELDS):
        raise MissionError("a GOAL's goal must not carry goal_id, authority or execution_authority: the body "
                           "derives them from your signature")
    if not isinstance(missions, list) or not all(isinstance(m, str) and m for m in missions) \
            or len(set(missions)) != len(missions):
        raise MissionError("a GOAL's missions must be a list of distinct mission ids")
    return GoalSpec.from_dict({**goal, "authority": {
        "authorized_by": "founder (signed GOAL command)", "authorization_ref": digest_,
        "legal_principal": PRINCIPAL, "max_consequence_class": payload["max_consequence_class"],
        "missions": sorted(missions), "standing_capabilities": []}})


def admitted(signed: dict, registry: GoalRegistry) -> dict[str, str]:
    """goal_id -> GOAL command digest, for registry goals a founder-signed GOAL in ``signed`` admits at its
    ledger position (signature, body, nonce, validity and the command path's GOAL validator)."""
    facts = founder_facts(registry.ledger)
    goals = set(registry.goals())
    return {gid: d for gid, d in facts.admitted.items() if d in signed and gid in goals}


# -- the command path's validators (Body.apply and the tick's re-derivation use these same functions) -----

def _move_scope(book: MissionBook, manifests: dict, spec: GoalSpec, move: InterventionSpec, *,
                now: datetime) -> dict:
    """The exact mission scope a goal move restates, or MissionError."""
    ref = move.payload
    if not isinstance(ref, dict) or not {"mission_id", "action_id"} <= set(ref):
        raise MissionError(f"goal move {move.intervention_id} must name {{mission_id, action_id}} of a bound "
                           "mission's strategy: GREG asks only for what a signed mission can execute")
    if ref["mission_id"] not in spec.authority.get("missions", []):
        raise MissionError(f"goal move {move.intervention_id} names a mission the goal does not bind")
    scope = strategy_scope(book.missions.get(ref["mission_id"]), manifests, ref["action_id"], now=now)
    if (scope["capability"], scope["target"], scope["consequence_class"], scope["cost_usd"]) != \
            (move.requested_capability, move.target, move.consequence_class, float(move.estimated_cost_usd)):
        raise MissionError(f"goal move {move.intervention_id} must restate its strategy's capability, target, "
                           "consequence class and cost exactly")
    return scope


def _linked(engine, spec: GoalSpec, move: InterventionSpec, *, now: datetime) -> dict:
    """The exact mission scope a goal move restates, on the live engine (asks and mirrored refusals)."""
    return _move_scope(engine.book, engine.registry.manifests, spec, move, now=now)


def check_goal(facts: FounderFacts, payload: Any, digest_: str, *, signer: str, book: MissionBook, manifests: dict,
               at: datetime, issued_at: str) -> GoalSpec:
    """The GOAL validator. Raises MissionError (the command is rejected and retained as data)."""
    if signer != "founder":
        raise MissionError("only the founder key may authorize a goal")
    spec = _spec(payload, digest_)
    cones = []
    for mid in spec.authority["missions"]:
        m = book.missions.get(mid)
        if m is None or m.status in TERMINAL:
            raise MissionError(f"goal binds unknown or closed mission {mid}")
        signed_mission(facts, mid, book=book)
        cones.append(CONSEQUENCE_CLASSES.index(m.cone.max_consequence_class))
    if CONSEQUENCE_CLASSES.index(spec.authority["max_consequence_class"]) > max(cones, default=0):
        raise MissionError("a goal cannot declare more authority than its missions' signed light cones")
    for move in _moves(spec):
        scope = _move_scope(book, manifests, spec, move, now=at)
        if not scope["outside_cone"]:
            raise MissionError(f"{move.intervention_id} is inside its mission's light cone: the mission pursues it "
                               "when the goal wakes; declare only moves that need your decision")
        m = book.missions[scope["mission_id"]]
        if scope["action_id"] in m.excluded:   # the mission never selects (so never asks for) an excluded strategy
            raise MissionError(f"{move.intervention_id} names {scope['action_id']}, which you excluded by a signed "
                               f"critique ({m.excluded[scope['action_id']][:120]}); a goal may not ask for it")
        if scope["scope_digest"] in m.rejected_scopes:
            raise MissionError(f"{move.intervention_id}: you already rejected this exact scope")
        pursued = pursued_checks(m.spec)
        if not set(scope["strategy"].get("advances", [])) & pursued:
            raise MissionError(f"{move.intervention_id} names {scope['action_id']}, which advances none of the checks "
                               f"mission {m.mission_id}'s loop pursues ({', '.join(sorted(pursued))}): the mission "
                               "would never run it, so your approve could change nothing")
    intent = _intent(spec)
    open_goals = facts.open_goals()
    for gid, other in open_goals.items():
        if gid != spec.goal_id and _intent(other) == intent:
            raise MissionError(f"an identical goal is already authorized as {gid[:23]}; supersede it to change it")
    closed_at = facts.closed_intents.get(intent)
    if closed_at is not None and not instant(issued_at) > closed_at:
        raise MissionError("you revoked or superseded a goal with this intent after this GOAL was signed; sign a "
                           "new GOAL to authorize it again")
    if spec.supersedes and spec.supersedes not in open_goals:
        raise MissionError("a goal may supersede only an admitted, open goal")
    controlled = facts.controlled_at.get(spec.supersedes) if spec.supersedes else None
    if controlled is not None and controlled > instant(issued_at):
        # A replacement signed before your latest control of the goal it replaces would silently undo that
        # control (a stop, a mute, a lower priority): the newest signed instruction about the lineage wins.
        raise MissionError("a later-signed control on the goal it replaces is in force; sign a new GOAL")
    return spec


def signed_mission(facts: FounderFacts, mission_id: str, *, book: MissionBook | None = None):
    """The mission state of ``mission_id`` when its registration is a founder-signed MISSION verified on this
    body for exactly that spec (mission id included), else MissionError.

    ``MissionBook`` folds any ``greg.mission.registered`` record (mission-side P2), so every goal-side claim of
    "your signed mission" (admission, the light cones a goal is judged against, ``authorize --from-mission``)
    checks the registration against the retained, verified envelope first."""
    m = (book or facts.book).missions.get(mission_id)
    cmd = facts.signed.get(m.command_digest) if m is not None else None
    body = ((cmd or {}).get("envelope") or {}).get("body")
    if m is None or cmd is None or cmd.get("kind") != "MISSION" or cmd.get("principal") != "founder" \
            or not isinstance(body, dict) or body.get("mission_id") != mission_id or body != m.spec:
        raise MissionError(f"mission {mission_id} is not founder-signed on this body: its registration cites no "
                           "verified founder MISSION for exactly this mission and spec")
    return m


def signed_mission_spec(journal, mission_id: str) -> dict:
    """The founder-signed spec of one registered mission (``greg gravity authorize --from-mission``)."""
    return signed_mission(founder_facts(journal.ledger), mission_id).spec


def check_control(facts: FounderFacts, payload: Any, *, signer: str, issued_at: str) -> tuple[str, str, Any]:
    """The GOAL_CONTROL validator: (goal_id, kind, value), or MissionError."""
    if not isinstance(payload, dict) or set(payload) - CONTROL_FIELDS or not {"goal_id", "kind"} <= set(payload):
        raise MissionError("GOAL_CONTROL takes goal_id, kind and optionally value, reason")
    gid, ck, value = payload["goal_id"], payload["kind"], payload.get("value")
    if gid not in facts.admitted:
        raise MissionError("GOAL_CONTROL names an unknown or unadmitted goal")
    if ck not in CONTROL_KINDS:
        raise MissionError(f"GOAL_CONTROL kind must be one of {CONTROL_KINDS}")
    if ck == "stop_pushing" and not isinstance(value, bool):
        raise MissionError("stop_pushing takes true (stop) or false (resume)")
    if signer != "founder" and not (ck in DEVICE_GOAL_CONTROLS and (ck != "stop_pushing" or value is True)):
        raise MissionError(f"a device key may only narrow a goal ({', '.join(DEVICE_GOAL_CONTROLS)}; stop_pushing "
                           f"only true); {ck}{'=false' if ck == 'stop_pushing' else ''} needs the founder key")
    closed = facts.closed.get(gid)
    if closed is not None and ck != "revoke":
        raise MissionError(f"a {closed['status']} goal accepts no further controls; authorize a new goal instead")
    if ck == "lower_priority" and (isinstance(value, bool) or value not in PRIORITIES or value < facts.floor[gid]):
        raise MissionError("lower_priority may only lower (1 highest .. 5 lowest)")
    if ck in NARROWING or ck == "change_goal":
        require_text(ck, value)
    last = facts.stop.get(gid)
    if ck in STOP_KINDS and last is not None and instant(issued_at) < instant(last["issued_at"]):
        raise MissionError("a later-signed stop, resume or change of this goal is already applied; this one is stale")
    return gid, ck, value


def _moves(spec: GoalSpec):
    return [move for node in spec.plan for move in node.interventions]


def _intent(spec: GoalSpec) -> str:
    return digest({k: v for k, v in spec.to_dict().items() if k not in ("goal_id", "authority")})


# -- the hosted attention store: the one ask path, no egregore founder records -------------------------

class BodyAttentionStore:
    """FounderAttentionRouter storage on a GREG body.

    Decision items become the mission engine's own APPROVAL asks (greg.asks contract, exact scope,
    deterministic request id); information items become ``greg.goal.notice`` events. It writes no
    ``egregore.founder_ask`` / ``egregore.founder_answer`` record, and an unsigned answer is refused:
    founder answers on a body are signed DECISION commands, read back from the retained envelopes."""

    accepts_unsigned_answers = False

    def __init__(self, body):
        self.body = body
        self.registry: GoalRegistry | None = None
        self.signed: dict = {}
        self.noticed: set[str] = set()
        self._notices: set[tuple] = set()      # (item_id, kind, why): each notice is recorded once
        self._routed: dict[str, dict] = {}
        self.asked: list[str] = []
        self.at: datetime | None = None

    def begin(self, signed: dict, at: datetime | None = None) -> None:
        self.signed, self.at = signed, at
        notices = [e.payload for e in self.body.journal.replay("goal.notice")]
        self.noticed = {n["item_id"] for n in notices}
        self._notices = {(n["item_id"], n["kind"], n.get("why", "")) for n in notices}
        self.asked = []

    # A decision item maps to one move of an admitted goal, then to one exact mission scope.
    def _scope(self, item: dict) -> dict | None:
        try:
            spec = self.registry.get(item["goal_id"])
            move = next((m for m in _moves(spec) if m.route_hash == item.get("route_hash")), None)
            return None if move is None else _linked(self.body.engine, spec, move, now=self.body.clock())
        except (ContractError, MissionError, KeyError):
            return None

    def _requests(self, scope: dict) -> list[str]:
        book = self.body.engine.book
        return [rid for rid, r in book.requests.items() if asks_for_move(r, scope)]

    def _refusal(self, item: dict) -> str | None:
        """Why the decision's move cannot be asked for now (the engine's own ``ask_refusal``), or None."""
        try:
            spec = self.registry.get(item["goal_id"])
            move = next((m for m in _moves(spec) if m.route_hash == item.get("route_hash")), None)
            if move is None:
                return "MissionError: the decision names no declared move of this goal"
            ref = move.payload
            return self.body.engine.ask_refusal(ref["mission_id"], ref["action_id"], now=self.at or self.body.clock())
        except CONTAINED as exc:
            return f"{type(exc).__name__}: {exc}"

    def _open(self, item: dict) -> bool:
        if item["kind"] != "decision":
            return item["item_id"] in self._routed or item["item_id"] in self.noticed
        scope = self._scope(item)
        book = self.body.engine.book
        if scope is not None and any(rid not in book.answers and rid not in book.withdrawn
                                     for rid in self._requests(scope)):
            return True
        # An ask the engine refused stays settled while the same refusal holds: it is not re-routed every wake
        # (one notice, never a fault). When the reason changes (the founder resumed the mission), it is routed.
        why = self._refusal(item)
        return why is not None and (item["item_id"], "ask_not_recorded", why[:300]) in self._notices

    def open_items(self) -> list[dict]:
        return [dict(v) for v in self._routed.values() if self._open(v)]

    def get_open(self, item_id: str) -> dict | None:
        item = self._routed.get(item_id)
        return dict(item) if item is not None and self._open(item) else None

    def is_open(self, item: AttentionItem) -> bool:
        return self._open(item.to_dict())

    def answer_for(self, item: AttentionItem) -> dict | None:
        if item.kind != "decision":
            return None
        scope = self._scope(item.to_dict())
        if scope is None:
            return None
        book = self.body.engine.book
        for rid in self._requests(scope):
            answer = book.answers.get(rid)
            if not (answer and answer.get("answer") in ANSWER and signed_answer(self.signed, rid, answer)):
                continue
            if rid in book.withdrawn:
                # withdrawn after its answer: a restore from a backup voided the approval (#186); it is asked again
                continue
            # A paid approve funds one run at the spend it named (#157): once that run happened, or the mission
            # spent since, it no longer answers this move and the goal may ask again. A reject answers the move.
            if answer["answer"] == "approve" and (rid in book.consumed
                                                  or book.requests[rid].get("scope_digest") != scope["scope_digest"]):
                continue
            return {"decision": ANSWER[answer["answer"]], "request_id": rid,
                    "command_digest": answer["command_digest"]}
        return None

    def _notice(self, item: AttentionItem, *, kind: str, lane: str, why: str = "") -> None:
        data = {"goal_id": item.goal_id, "item_id": item.item_id, "kind": kind, "category": item.category,
                "urgency": item.urgency, "lane": lane, "title": item.title, "text": item.question,
                "evidence_refs": list(item.evidence_refs), "created_at": item.created_at,
                "founder_surface": "notice only: no ask, no decision requested", "execution_authority": "none"}
        if why:
            data["why"] = why[:300]
        ident = (item.item_id, kind, why[:300])
        if ident not in self._notices:      # once: a later turn's copy differs only in its time and lane
            self.body.journal.record("goal.notice", data, key=[item.item_id, kind, why[:300]])
            self._notices.add(ident)
        self.noticed.add(item.item_id)

    def record_ask(self, item: AttentionItem, payload: dict) -> None:
        self._routed[item.item_id] = item.to_dict()
        lane = payload.get("lane", "batched")
        if item.kind != "decision":
            self._notice(item, kind=item.kind, lane=lane)
            return
        why = self._refusal(item.to_dict())
        if why is None:
            # One goal's refused or faulting ask never faults the turn for the other goals: it becomes one notice.
            try:
                spec = self.registry.get(item.goal_id)
                move = next(m for m in _moves(spec) if m.route_hash == item.route_hash)
                ref = move.payload
                budget = self.body.engine.book.missions[ref["mission_id"]].cone.budget_usd
                rid = self.body.engine.request_decision(
                    ref["mission_id"], ref["action_id"], why=item.question, recommendation=item.recommendation,
                    now=datetime.fromisoformat(str(payload.get("routed_at", iso(self.body.clock()))).replace("Z", "+00:00")),
                    evidence={"goal_id": item.goal_id, "goal_item_id": item.item_id, "lane": lane,
                              "evidence_refs": list(item.evidence_refs),
                              "approve_means": approve_means(move.estimated_cost_usd, budget)},
                    quoted=tuple(asks.founder_text([spec.founder_intent, spec.desired_state, move.description,
                                                    move.intervention_id, move.expected_outcome,
                                                    [n.gate for n in spec.plan], [n.outcome for n in spec.plan]])))
                self.asked.append(rid)
                return
            except (asks.AskContractError, StopIteration, *CONTAINED) as exc:
                why = f"{type(exc).__name__}: {exc}"
        self._notice(item, kind="ask_not_recorded", lane=lane, why=why)

    def record_answer(self, item_id: str, payload: dict) -> None:
        raise ContractError("founder answers on a GREG body arrive only as signed DECISION commands")


# -- untrusted intake judged by what it is about, not only by the channel it arrived on ----------------------

MIN_TERM_CHARS = 3


def _norm(text: str) -> str:
    return dataplane._normal(str(text))     # casefolded words, punctuation collapsed (the intake clustering key)


def _mission_terms(spec: dict) -> set[str]:
    """Words that name a signed mission's world: its id, the id's last segment, and the base name of every sensor
    and strategy target (``fs:c.txt`` -> ``c txt``). Wildcards and terms under three characters never count."""
    names = [spec["mission_id"], re.split(r"[:/]", spec["mission_id"])[-1]]
    targets = [(c.get("sensor") or {}).get("target") for c in spec.get("success_checks", [])]
    targets += [s.get("target") for s in spec.get("strategies", [])]
    names += [re.split(r"[:/]", t)[-1] for t in targets if isinstance(t, str)]
    return {_norm(n) for n in names if "*" not in n and len(_norm(n).replace(" ", "")) >= MIN_TERM_CHARS}


def goal_subjects(spec: GoalSpec) -> set[str]:
    """What a goal is about: its signed missions, its relevant entities and the subjects it wakes on."""
    return (set(spec.authority.get("missions", [])) | set(spec.relevant_entities)
            | {c.match for c in spec.wake_conditions if c.kind == "subject"})


def intake_about(content: str, book: MissionBook, registry: GoalRegistry) -> tuple[list[str], list[str]]:
    """(subjects, matched terms): the missions and goal subjects an intake item's text names, as whole words."""
    text = f" {_norm(content)} "
    about, matched = set(), set()
    for mid, m in book.missions.items():
        hits = {t for t in _mission_terms(m.spec) if f" {t} " in text}
        if hits:
            about.add(mid)
            matched |= hits
    for gid in registry.goals():
        for subject in goal_subjects(registry.get(gid)):
            term = _norm(subject)
            if len(term.replace(" ", "")) >= MIN_TERM_CHARS and f" {term} " in text:
                about.add(subject)
                matched.add(term)
    return sorted(about), sorted(matched)


@dataclass(frozen=True)
class _Mention:
    """An intake item names this subject. Scoring input only: never integrated as a belief or evidence."""
    subject: str
    value: bool = True

    @property
    def key(self) -> str:
        return f"{self.subject}.intake_mention"


class BodyRelevanceRouter(GoalRelevanceRouter):
    """The GREG body's relevance router: untrusted intake counts for a goal by what its content is about.

    An intake item that names a goal's subject (a bound mission's id or targets, a relevant entity) matches the
    goal's subject conditions on any channel, and its channel (domain, tag) counts too. An item that names none
    of them is noise for that goal whatever channel it came on. Every other signal scores exactly as in egregore."""

    def score(self, spec: GoalSpec, signal: SignalEnvelope, observations):
        about = signal.payload.get("about")
        if not signal.payload.get("intake") or not isinstance(about, list):
            return super().score(spec, signal, observations)
        named = sorted(goal_subjects(spec) & set(about))
        if not named:
            bare = {k: v for k, v in signal.payload.items() if k not in ("domain", "tags")}
            return score_signal(spec, SimpleNamespace(payload=bare), observations)
        return score_signal(spec, signal, list(observations) + [_Mention(s) for s in named])


@dataclass
class _Binding:
    loop: GoalGravityLoop
    store: BodyAttentionStore
    cursor: int = 0
    pulls: dict = field(default_factory=dict)


def binding_for(body) -> _Binding:
    """The body's one hosted loop (body mode, hosted attention store), cached per open Body."""
    held = getattr(body, "_goal_gravity", None)
    if held is None or held.loop.ledger is not body.ledger:
        store = BodyAttentionStore(body)
        loop = GoalGravityLoop(ledger=body.ledger, compiled=body.compiled, passports=body.passports,
                               actor=body.identity.passport_id, legal_principal=PRINCIPAL,
                               genomes=_Genomes(body.registry), body_mode=True, attention_store=store)
        loop.router = BodyRelevanceRouter(loop.registry)   # same registry; content-aware scoring of intake only
        store.registry = loop.registry
        held = _Binding(loop=loop, store=store)
        body._goal_gravity = held
    return held


# -- founder commands (already signature-verified by Body.apply) ---------------------------------------

def command(body, kind: str, payload: dict, digest_: str, *, signer: str = "founder", envelope: dict | None = None,
            now: datetime | None = None) -> dict:
    """Apply one verified GOAL or GOAL_CONTROL. Raises MissionError (rejected, retained as data).

    The validators are the ones the tick re-runs at this command's ledger position (``founder_facts``), on
    the same facts: the mission book and manifests folded to here and the founder goal facts so far."""
    held = binding_for(body)
    reg, now = held.loop.registry, now or body.clock()
    reg.refresh()
    facts = founder_facts(body.journal.ledger, body_id=body.config["body_id"])
    issued_at = (envelope or {}).get("issued_at") or iso(now)
    if kind == "GOAL_CONTROL":
        gid, ck, value = check_control(facts, payload, signer=signer, issued_at=issued_at)
        actor = f"{signer} (signed GOAL_CONTROL {digest_[7:19]})"
        reason = str(payload.get("reason") or ck)[:300]
        if ck == "revoke":
            state = reg.revoke(gid, actor=actor, reason=reason, now=now)
        else:
            completed = reg.state(gid).status == "completed"
            if completed:     # observation-tier completion never makes a goal deaf to your controls
                reg.transition(gid, status="dormant", now=now, reason=f"reopened to record {ck} by {actor}")
            state = reg.record_preference(gid, kind=ck, value=value, actor=actor, reason=reason, now=now)
            if completed and state.status == "dormant":   # a stop or change keeps it paused; anything else
                state = reg.transition(gid, status="completed", now=now,   # leaves it completed, as observed
                                       reason=f"still completed (observation-tier) after recording {ck}")
        return {"goal_id": gid, "kind": ck, "status": state.status, "signer": signer, "authority_created": False}
    spec = check_goal(facts, payload, digest_, signer=signer, book=facts.book, manifests=facts.manifests, at=now,
                      issued_at=issued_at)
    prior = facts.authorizations.get(spec.goal_id)
    if prior is not None:        # only a crash-replay of this same GOAL may find its record already written
        at = _when(prior.get("authorized_at"))
        if at is None or not instant(issued_at) - CLOCK_SKEW <= at <= now:
            raise MissionError(f"a goal record for this GOAL already exists, dated {prior.get('authorized_at')}, "
                               "outside this envelope's signed validity: it was not written by this body applying "
                               "your GOAL; it stays preserved and quarantined. Sign a new GOAL")
    if spec.supersedes:
        gid = reg.supersede(spec.supersedes, spec, actor=f"founder (signed GOAL {digest_[7:19]})",
                            reason="founder-signed replacement", now=now)
    else:
        gid = reg.authorize(spec, now=now)   # authorized_at is the body clock, never the envelope's
    return {"goal_id": gid, "missions": spec.authority["missions"], "supersedes": spec.supersedes,
            "authority_created": False, "execution_authority": "none"}


# -- one turn on the body ------------------------------------------------------------------------------

def _guard(body, reg: GoalRegistry, facts: FounderFacts, at: datetime) -> list[str]:
    """Narrowing only. Unadmitted goals never pull; for an admitted goal every authority-relevant fact is
    re-derived from signed commands and restored when an unsigned record widened it: a signed revoke or
    supersede closes it, a signed stop or change keeps it stopped, every signed narrowing preference stays,
    and its priority is never above both the signed spec and the lowest priority the founder signed."""
    quarantined = []
    ok = facts.admitted
    for gid in reg.goals():
        if gid not in ok and reg.state(gid).status not in CLOSED:
            reg.record_preference(gid, kind="stop_pushing", value=True, actor=ADMISSION_ACTOR, now=at,
                                  reason="no retained founder-signed GOAL authorizes this goal; preserved, never woken")
            quarantined.append(gid)
    for gid in ok:                                     # lift only the binding's own quarantine, once admitted
        prefs = [r.payload for r in body.ledger.by_type(GoalRegistry.PREFERENCE_RECORD) if r.payload["goal_id"] == gid]
        if prefs and prefs[-1]["reason"].startswith(f"stop_pushing by {ADMISSION_ACTOR}") \
                and reg.state(gid).status == "paused" and facts.stopped(gid) is None:
            reg.record_preference(gid, kind="stop_pushing", value=False, actor=ADMISSION_ACTOR, now=at,
                                  reason="a retained founder-signed GOAL now authorizes this goal")
    for gid in ok:
        if gid in reg.goals():
            try:
                _restore(reg, facts, gid, at)
            except ContractError:            # a refused restoration never faults the turn; the goal stays narrow
                continue
    return quarantined


def _restore(reg: GoalRegistry, facts: FounderFacts, gid: str, at: datetime) -> None:
    state = reg.state(gid)
    closed = facts.closed.get(gid)
    if closed is not None:
        if state.status != closed["status"]:
            actor = f"restoring signed {closed['principal']} {closed['status']} {closed['by'][7:19]}"
            if closed["status"] == "revoked":
                reg.revoke(gid, actor=actor, reason="signed revoke", now=at)
            else:
                reg.supersede(gid, reg.get(closed["superseded_by"]), actor=actor, reason="signed supersede", now=at)
        return
    if state.status in ("revoked", "superseded"):
        return                       # closed by no signed command: narrowing, preserved, labelled in the views
    stop = facts.stopped(gid)
    missing = [(NARROWING_KIND[key], value) for key, values in facts.narrowing.get(gid, {}).items()
               for value in values if value not in state.preferences.get(key, [])]
    floor = facts.floor.get(gid)
    low = floor is not None and reg.effective_priority(gid) < floor
    if state.status == "completed":
        # Observation-tier completion is not a closure: a completed goal still carries every signed stop and
        # narrowing (a later regression reopens it, ``_reopen``), so one an unsigned record widened is restored
        # as the command path records a control on a completed goal (reopen to record, then completed again;
        # a signed stop leaves it paused, as the command path does).
        if stop is None and not missing and not low:
            return
        reg.transition(gid, status="dormant", now=at, reason="reopened to restore signed founder controls")
    if stop is not None and reg.state(gid).status not in CLOSED:
        reg.record_preference(gid, kind="stop_pushing", value=True, reason="signed stop", now=at,
                              actor=f"restoring signed {stop['principal']} control {stop['by'][7:19]}")
    for kind, value in missing:
        if reg.state(gid).status not in ("revoked", "superseded", "completed"):
            reg.record_preference(gid, kind=kind, value=value, reason="signed narrowing", now=at,
                                  actor="restoring a signed founder narrowing")
    if low and reg.effective_priority(gid) < floor:
        reg.record_preference(gid, kind="lower_priority", value=floor, reason="signed priority", now=at,
                              actor="restoring the signed priority ceiling")
    if state.status == "completed" and reg.state(gid).status == "dormant":
        reg.transition(gid, status="completed", now=at,     # a stop keeps it paused; otherwise still completed
                       reason="still completed (observation-tier) after restoring signed founder controls")


def _release_pulls(body, reg: GoalRegistry, facts: FounderFacts, at: datetime) -> list[str]:
    """A goal's pull lives only while a goal binding that mission is admitted, open and not stopped.

    Once the founder revokes, supersedes or stops every goal that binds a mission (or an unsigned record
    narrows it), a still-pending pull is released unserved through the engine (``release_pull``): the
    mission waiting on an APPROVAL goes back to only waiting, as a mission no goal is bound to does.
    Runs after the guard (signed facts restored) and before any turn, so it holds in the very tick the
    control is applied."""
    live: set[str] = set()
    goals = set(reg.goals())
    for gid in facts.admitted:
        if gid in facts.closed or facts.stopped(gid) is not None or gid not in goals \
                or reg.state(gid).status in CLOSED:
            continue
        live |= set(facts.specs[gid].authority.get("missions", []))
    released = []
    for mid, m in sorted(body.engine.book.missions.items()):
        if m.pull is not None and mid not in live and body.engine.release_pull(
                mid, at, why="no admitted, open, unstopped goal binds this mission any more"):
            released.append(mid)
    return released


def _settle(body, reg: GoalRegistry, facts: FounderFacts, at: datetime) -> list[str]:
    """A signature-verified reject of a goal move's exact scope is remembered by the goal too."""
    book, mirrored, signed = body.engine.book, [], facts.signed
    for gid in facts.admitted:
        if gid not in reg.goals() or reg.state(gid).status in ("revoked", "superseded", "completed"):
            continue
        spec = reg.get(gid)
        for move in _moves(spec):
            if reg.is_route_refused(gid, move.route_hash):
                continue
            try:
                scope = _linked(body.engine, spec, move, now=at)
            except (ContractError, MissionError):
                continue
            for rid, r in book.requests.items():
                answer = book.answers.get(rid)
                if asks_for_move(r, scope) and answer \
                        and answer.get("answer") == "reject" and signed_answer(signed, rid, answer):
                    who = signed[answer["command_digest"]]["principal"]
                    reg.record_refusal(gid, route_hash=move.route_hash, now=at,
                                       actor=f"{who} (signed DECISION {answer['command_digest'][7:19]})",
                                       reason=answer.get("reason") or "rejected")
                    mirrored.append(move.intervention_id)
                    break
    return mirrored


def _reopen(reg: GoalRegistry, facts: FounderFacts, signals: list, at: datetime) -> list[str]:
    """Completion is observation-tier, never terminal: an admitted, completed goal whose plan node an attributed
    observation in this turn shows regressed is dormant again, so the same turn may wake it (an infinite
    mission's checks keep being re-verified; a maintenance goal does not close for good)."""
    readings: dict[str, Any] = {}
    for sig in signals:
        if sig.trust_level == "attributed":
            for o in sig.payload.get("observations", []):
                readings[f"{o['subject']}.{o['attribute']}"] = o["value"]
    reopened = []
    for gid in facts.admitted:
        if gid in facts.closed or facts.stopped(gid) is not None or gid not in reg.goals() \
                or reg.state(gid).status != "completed":
            continue                  # a signed stop stays in force: a stopped goal is never reopened to wake
        for node in reg.get(gid).plan:
            gap = metric_error(node.sbm_direction, node.sbm_target, readings[node.sbm]) if node.sbm in readings else None
            if gap is not None and gap > 0:
                reg.transition(gid, status="dormant", now=at,
                               reason=f"reopened: {node.sbm} observed {readings[node.sbm]!r} (needs {node.sbm_direction} "
                                      f"{node.sbm_target!r}); completion is observation-tier")
                reopened.append(gid)
                break
    return reopened


def _sense(body, loop: GoalGravityLoop, cursor: int) -> tuple[list[SignalEnvelope], int]:
    """New, changed, Gate-derived evidence only. An executor's own claim never becomes an observation."""
    world, book = loop.world, body.engine.book
    seen = {e.signal_id for e in world.experiences()}
    records = body.ledger.records[cursor:]
    end = len(body.ledger.records)
    out: list[SignalEnvelope] = []

    def emit(event_id, at, record_hash, observations=(), trust="attributed", **payload):
        sig = SignalEnvelope.build(source=SOURCE, source_event_id=event_id, observed_at=at,
                                   payload={"observations": list(observations), **payload},
                                   evidence_refs=(record_hash,), trust_level=trust)
        if sig.signal_id not in seen:
            seen.add(sig.signal_id)
            out.append(sig)

    def changed(subject, attribute, value, trust):
        b = world.belief(subject, attribute)
        return b is None or b.value != value or b.trust_level != trust

    latest: dict[tuple, tuple] = {}            # one reading per (subject, attribute): the latest in ledger order
    path_changed = cursor == 0
    gate: dict = {}                            # grant_issued and witness records, read once if needed
    for rec in records:
        if rec.record_type != "event":
            continue
        t, p = rec.payload.get("type"), rec.payload.get("payload", {})
        if t in PATH_EVENTS:
            path_changed = True
        if t == "greg.mission.observed" and p.get("receipt") and measured(p):
            # A read that did not measure the world (refused, stopped by the host, abstained) says nothing about
            # the check: recomputing the predicate over its output would read the fault as the world.
            m = book.missions.get(p["mission_id"])
            check = next((c for c in (m.spec["success_checks"] if m else []) if c["check_id"] == p["check_id"]), None)
            receipt = None if check is None else _sensor_receipt(body.ledger, gate, m, check, p["receipt"])
            if receipt is None:               # missing, or not this check's own sensor read: never evidence
                continue
            value, _ = evaluate_predicate(check["predicate"], receipt.payload.get("result", {}).get("output"))
            trust = "attributed" if value == p["passed"] else "untrusted"
            latest[(p["mission_id"], p["check_id"])] = (rec.payload["event_id"], p["at"], rec.hash, value, trust)
        elif t == "greg.mission.appraised" and p.get("verdict") in ("VERIFIED", "REFUTED"):
            latest[(p["mission_id"], "appraised_verified")] = (rec.payload["event_id"], rec.ts_utc, rec.hash,
                                                               p["verdict"] == "VERIFIED", "attributed")
        elif t in ("greg.capability.registered", "greg.capability.state"):
            # Capability formation as perception: a capability that became usable (formed, recovered, attached)
            # or stopped being usable changes what a mission blocked on its function can do. Recorded by Genesis
            # or the founder's own command on the ledger; it creates no authority and pulls only timing.
            cid = (p.get("manifest") or {}).get("capability_id") or p.get("capability_id")
            manifest = body.registry.manifests.get(cid)
            if manifest is not None and p.get("state") in CAPABILITY_USABLE:
                for mid, waiting in _blocked_on(body, book, manifest.function) \
                        + _goal_formations(body, manifest.function):
                    latest[(mid, f"capability:{waiting}")] = (rec.payload["event_id"], p.get("at") or rec.ts_utc,
                                                              rec.hash, p["state"], "attributed")
        elif t == "greg.external.ingested" and not p.get("quarantined"):
            about, terms = intake_about(p.get("content", ""), book, loop.registry)
            emit(rec.payload["event_id"], p["at"], rec.hash, trust="untrusted", tags=[p["channel"]],
                 domain=p["channel"], intake=True, about=about, matched_terms=terms)
    for (subject, attribute), (event_id, at, record_hash, value, trust) in latest.items():
        if changed(subject, attribute, value, trust):
            emit(event_id, at, record_hash, [{"subject": subject, "attribute": attribute, "value": value,
                                              "confidence": 1.0}], trust)
    if records and path_changed:
        where = devpath.position(body.journal)   # one developmental backcast, read by both lineages
        for node in where["achieved"] + ([where["active"]["id"]] if where["active"] else []):
            met = node in where["achieved"]
            if changed("greg.path", node, met, "attributed"):
                emit(f"greg.path:{node}:{met}:{end}", iso(body.clock()), body.ledger.head,
                     [{"subject": "greg.path", "attribute": node, "value": met, "confidence": 1.0}])
    return out, end


# Each transition is its own change: formed or recovered (VERIFIED: attachable), attached (usable now),
# quarantined or detached (no longer usable). The value is the state, so every one of them can wake a goal.
CAPABILITY_USABLE = ("VERIFIED", "ATTACHED", "QUARANTINED", "DETACHED")


def _blocked_on(body, book: MissionBook, function: str) -> list[tuple[str, str]]:
    """(mission, the function it waits on) for open missions blocked on ``function`` directly, or on a
    construction whose engine provides ``function``."""
    genesis = getattr(body, "genesis", None)
    out = []
    for mid, m in sorted(book.missions.items()):
        waiting = (m.blocker or {}).get("function")
        if not waiting or m.status in TERMINAL:
            continue
        engine = genesis.construction_engine(waiting) if genesis is not None else None
        if function in (waiting, engine):
            out.append((mid, waiting))
    return out


def _goal_formations(body, function: str) -> list[tuple[str, str]]:
    """(mission, function) for open deficits a goal asked Genesis to form, on ``function`` directly or on a
    construction whose engine provides it: their mission is not blocked, but the goal waits on them."""
    genesis = getattr(body, "genesis", None)
    if genesis is None:
        return []
    resolved = {e.payload["deficit_id"] for e in body.journal.replay("deficit.resolved")}
    out = set()
    for e in body.journal.replay("deficit.opened"):
        p = e.payload
        if p.get("requested_by_goal") and p["deficit_id"] not in resolved \
                and function in (p["function"], genesis.construction_engine(p["function"])):
            out.add((p["mission_id"], p["function"]))
    return sorted(out)


def _form_requested(body, reg: GoalRegistry, facts: FounderFacts, woken, at: datetime) -> list[dict]:
    """A woken goal whose active plan node requires ``<function>@function`` that no usable implementation
    serves asks Genesis to form it, under the first open, unpaused mission the goal binds.

    Formation only (``Genesis.form_for_goal``): the result is VERIFIED and waits for your signed attach;
    no auto_attach, no builder, no spend, no scope. A function a person performs (``asks.human_work``),
    one Genesis cannot form without a builder, a revoked capability and a stopped goal are left alone."""
    genesis = getattr(body, "genesis", None)
    if genesis is None:
        return []
    book = body.engine.book
    out = []
    for gid in woken:
        if gid not in facts.admitted or facts.stopped(gid) is not None:
            continue
        state = reg.state(gid)
        revoked = set(state.preferences.get("revoked_capabilities", []))
        for cap in state.missing_capabilities:
            function, _, version = cap.partition("@")
            if version != FUNCTION_VERSION or cap in revoked or not genesis.formable(function) \
                    or asks.human_work(function) is not None:
                continue
            mission = next((m for mid in sorted(reg.get(gid).authority.get("missions", []))
                            if (m := book.missions.get(mid)) is not None and m.status not in TERMINAL
                            and not m.paused), None)
            if mission is None:
                continue
            try:
                found = genesis.form_for_goal(goal_id=gid, mission=mission, function=function, now=at,
                                              purpose=f"goal {gid[:23]} plan node {state.active_node_id} requires "
                                                      f"{function}")
            except CapabilityError as exc:
                # A host outage while qualifying (a runner timeout, isolation unavailable) is no evidence about any
                # candidate: nothing was qualified, failed or built. It is recorded once per reason and the request
                # re-runs on the goal's next wake; it never stops this turn's missions (a mission's own formation
                # waits it out on an outage blocker, MissionEngine._form).
                if exc.failure_class != "transient":
                    raise
                why = str(exc)[:200]
                body.journal.record("goal_gravity.formation_outage", {
                    "goal_id": gid, "function": function, "mission_id": mission.mission_id, "why": why,
                    "reconsider": "re-runs when the goal next wakes; nothing was qualified, failed or built"},
                    key=[gid, function, mission.mission_id, why])
                out.append({"goal_id": gid, "function": function, "mission_id": mission.mission_id,
                            "serving": None, "outage": why})
                continue
            out.append({"goal_id": gid, "function": function, "mission_id": mission.mission_id,
                        "serving": found.capability_id if found is not None else None})
    return out


def _close_goal_formations(body, at: datetime) -> list[str]:
    """Resolve each open goal-requested deficit once an attached, usable implementation serves its function
    (attached by your signed command): the goal's plan then reads the function present."""
    genesis = getattr(body, "genesis", None)
    if genesis is None:
        return []
    resolved = {e.payload["deficit_id"] for e in body.journal.replay("deficit.resolved")}
    closed = []
    for e in body.journal.replay("deficit.opened"):
        p = e.payload
        if not p.get("requested_by_goal") or p["deficit_id"] in resolved:
            continue
        serving = genesis.find_attached(p["function"])
        if serving is None:
            continue
        body.journal.record("deficit.resolved", {"deficit_id": p["deficit_id"],
                                                 "capability_id": serving.capability_id,
                                                 "mission_id": p["mission_id"],
                                                 "resume": f"goal {p['requested_by_goal']}", "at": iso(at)},
                            key=[p["deficit_id"], "resolved"])
        resolved.add(p["deficit_id"])
        closed.append(p["deficit_id"])
    return closed


def _sensor_receipt(ledger, gate: dict, m, check: dict, receipt_hash: str):
    """The Gate receipt of this check's own sensor read for this mission, or None.

    An observation may cite only the receipt of the read its check names: a grant issued under this
    mission's signed command, witnessed on the sensor's capability and target, and (for static params)
    for exactly the scope AuthorityOffice derives for that read. Any other receipt, however genuine,
    measured something else."""
    receipt = ledger.find(receipt_hash)
    if receipt is None or receipt.record_type != "receipt":
        return None
    if not gate:
        gate["issued"] = {r.payload.get("grant_id"): r.payload for r in ledger.by_type("event")
                          if r.payload.get("type") == "greg.authority.grant_issued"}
        gate["witness"] = {r.payload.get("witness_id"): r.payload for r in ledger.by_type("witness")}
    grant = gate["issued"].get(receipt.payload.get("grant_id"))
    witness = gate["witness"].get(receipt.payload.get("witness_id"))
    sensor = check.get("sensor") or {}
    if grant is None or witness is None or grant.get("authority_ref") != m.command_digest \
            or witness.get("grant_id") != grant.get("grant_id") or witness.get("target") != sensor.get("target"):
        return None
    capability = sensor.get("capability")          # absent: a function sensor resolved to an attached capability
    if capability is not None:
        if witness.get("capability") != capability:
            return None
        params = sensor.get("params", {})
        if "$from_action" not in json.dumps(params) and grant.get("scope_digest") != AuthorityOffice.scope_digest(
                mission_id=m.mission_id, capability_id=capability, params=params, target=sensor["target"],
                consequence_class="read_only", cost_usd=0.0):
            return None
    return receipt


def _activate(body, held: _Binding, turn, at: datetime) -> list[str]:
    """An awake goal makes its signed missions observe now. Timing only, rate-limited, and a paused or
    terminal mission is the founder's: it is never resumed or touched here."""
    pulled = []
    for gid in turn.woken:
        for mid in held.loop.registry.get(gid).authority.get("missions", []):
            last = held.pulls.get(mid)
            if last is not None and at - last < PULL_MIN_INTERVAL:
                continue
            if body.engine.observe_now(mid, at, cause=f"goal {gid[7:23]} woke in turn {turn.turn_id[7:23]}"):
                held.pulls[mid] = at
                pulled.append(mid)
    return pulled


def _record_quarantine(body, reg: GoalRegistry) -> None:
    for q in reg.quarantined:
        body.journal.record("goal.record_quarantined", q, key=[q["record_hash"]])


# A fault inside the binding (a refused contract, an integrity conflict, a defect) is contained: it is
# recorded once per distinct reason and the missions keep running. Ledger write faults (WriterConflict,
# ReconciliationRequired: RuntimeError) are not contained; the body's own recovery handles them.
CONTAINED = (ValueError, LookupError, TypeError, AttributeError)


def tick(body, now: datetime) -> dict | None:
    """One Goal Gravity turn on the body. No goal record: no work, no record. A fault never stops missions."""
    if not body.ledger.by_type(GoalRegistry.AUTHORIZED_RECORD):
        return None
    try:
        return _tick(body, now)
    except CONTAINED as exc:
        why = f"{type(exc).__name__}: {exc}"[:300]
        if not any(e.payload.get("why") == why for e in body.journal.replay("goal_gravity.fault")):
            body.journal.record("goal_gravity.fault", {"why": why, "first_at": iso(now),
                                                       "missions": "unaffected: they keep their own loop"},
                                key=[why])
        # Fail closed: a turn that could not re-derive which goals are open serves no goal pull. Every pending
        # pull is released, so a waiting mission only waits (as a goal-less one does) until a sound turn pulls.
        try:
            body.engine.book.rebuild()
            released = [mid for mid, m in sorted(body.engine.book.missions.items()) if m.pull is not None
                        and body.engine.release_pull(mid, now, why="goal gravity faulted this turn: " + why)]
        except CONTAINED:            # the mission book itself is unreadable: the engine's own tick reports it
            released = []
        return {"state": "FAULT", "why": why, **({"pulls_released": released} if released else {})}


def _tick(body, now: datetime) -> dict:
    held = binding_for(body)
    loop, reg = held.loop, held.loop.registry
    reg.refresh()                                      # goal records any other writer appended
    _record_quarantine(body, reg)
    last = [r.payload["turn"]["at"] for r in body.ledger.by_type(GoalGravityLoop.TURN_RECORD)][-1:]
    at = max([now] + [datetime.fromisoformat(a.replace("Z", "+00:00")) for a in last])   # never backdated
    body.engine.book.rebuild()
    facts = founder_facts(body.ledger, body_id=body.config["body_id"])
    held.store.begin(facts.signed, at)
    quarantined = _guard(body, reg, facts, at)
    released = _release_pulls(body, reg, facts, at)
    extra = {"pulls_released": released} if released else {}
    refusals = _settle(body, reg, facts, at)
    signals, end = _sense(body, loop, held.cursor)
    closed = _close_goal_formations(body, at)    # after sensing: the attach that closes one still wakes its goal
    if closed:
        extra["formations_closed"] = closed
    reopened = _reopen(reg, facts, signals, at)
    if not (signals or reg.due_for_review(at) or reg.by_status("awake")):
        held.cursor = end
        return {"state": "DORMANT", "quarantined": quarantined, "refusals_mirrored": refusals, **extra}
    turn = loop.turn(trigger_id=f"greg:{iso(at)}:{body.ledger.head[7:23]}", now=at, signals=signals,
                     resources=ResourceGovernor(max_model_calls=1, max_estimated_cost_usd=0.01),
                     evidence_confidence=1.0)   # an upper bound only: body mode derives it from world evidence
    held.cursor = end                              # advanced only after the turn succeeded
    pulled = _activate(body, held, turn, at)
    formed = _form_requested(body, reg, facts, turn.woken, at)
    extra.update({"formation_requested": formed} if formed else {})
    return {"state": turn.status, "turn_id": turn.turn_id, "woken": list(turn.woken), "missions_pulled": pulled,
            "asked": list(held.store.asked), "wake_refused": [w["goal_id"] for w in turn.wake_refused],
            "quarantined": quarantined, "refusals_mirrored": refusals, "reopened": reopened, **extra}


# -- read-only projections (CLI, status, morning report, console, closures) ---------------------------

def _mission_rows(book: MissionBook, mids) -> list[dict]:
    rows = []
    for mid in mids:
        m = book.missions.get(mid)
        rows.append({"mission_id": mid, "status": m.status if m else "UNKNOWN", "paused": bool(m and m.paused),
                     "rung": m.rung if m else None, "next_observe_at": m.next_observe_at if m else None,
                     "blocker": (m.blocker or {}).get("why") if m else None})
    return rows


def _move_scopes(book: MissionBook, manifests: dict, spec: GoalSpec) -> list[dict]:
    """Each declared move's exact strategy scope: the one link from a goal to the engine's APPROVAL asks
    (``asks_for_move``), as the attention store and ``_settle`` match. An APPROVAL of another scope that names the
    same strategy (the compensation of its executed effect) is the mission's decision, not the goal's move."""
    scopes = []
    for move in _moves(spec):
        ref = move.payload if isinstance(move.payload, dict) else {}
        try:
            scope = strategy_scope(book.missions.get(ref.get("mission_id")), manifests, ref.get("action_id"),
                                   now=datetime.now(timezone.utc))      # the time reads only the cone, not the scope
        except MissionError:
            continue
        scopes.append(scope)
    return scopes


def _goal_request(r: dict, gid: str, scopes: list) -> bool:
    evidence = r.get("evidence") if isinstance(r.get("evidence"), dict) else {}
    return evidence.get("goal_id") == gid or any(asks_for_move(r, scope) for scope in scopes)


def _goal_requests(book: MissionBook, manifests: dict, gid: str, spec: GoalSpec) -> list[str]:
    scopes = _move_scopes(book, manifests, spec)
    return [r["request_id"] for r in book.open_requests() if _goal_request(r, gid, scopes)]


def _stop_label(facts: FounderFacts, gid: str, status: str) -> str | None:
    """Who stopped a paused goal, as the founder surfaces say it. Only a signed GOAL_CONTROL is "you"."""
    if status != "paused":
        return None
    if gid not in facts.admitted:
        return "quarantined by admission (no founder-signed GOAL admits it here)"
    stop = facts.stopped(gid)
    if stop is None:
        return "stopped by an unsigned record, not by you"
    if stop["kind"] == "change_goal":
        return "paused by you for a change"
    return "stopped by you" if stop["principal"] == "founder" else \
        f"stopped by your device ({stop['principal'].split(':', 1)[-1]})"


def _undone(book: MissionBook, spec: GoalSpec) -> list[str]:
    """Plan nodes whose observed effect GREG's own compensation undid after the bound mission ended. An ended
    mission never observes again, so no regression observation can reopen the goal for them."""
    nodes = {node.sbm: node.node_id for node in spec.plan}
    out = []
    for mid in spec.authority.get("missions", []):
        m = book.missions.get(mid)
        if m is None or m.status not in TERMINAL:
            continue
        advances = {s["action_id"]: s.get("advances", []) for s in m.spec["strategies"]}
        for c in book.journal.replay("mission.compensated"):
            p = c.payload
            hit = [nodes[f"{mid}.{check}"] for check in advances.get(p.get("action_id"), [])
                   if f"{mid}.{check}" in nodes]
            if p.get("mission_id") == mid and p.get("status") == "DONE" and hit:
                out.append(f"GREG compensated {p['action_id']} of {mid} after it ended {m.status} (receipt "
                           f"{str(p.get('receipt'))[:19]}), undoing the effect behind {', '.join(hit)}")
    return out


def _completion_label(book: MissionBook, spec: GoalSpec, status: str) -> str | None:
    """What "completed" means on the founder surfaces: observation-tier, and never the end of a maintenance goal."""
    if status != "completed":
        return None
    undone = _undone(book, spec)
    if undone:
        return ("no longer holds: " + "; ".join(undone) + ". The mission has ended, so nothing re-verifies it and "
                "no observation can reopen this goal")
    standing = [mid for mid in spec.authority.get("missions", []) if (m := book.missions.get(mid)) is not None
                and m.status not in TERMINAL and m.spec["closure"]["kind"] == "infinite"]
    if standing:
        return (f"holding: every plan node is observed satisfied; {', '.join(standing)} keeps re-verifying, and a "
                "regressed check reopens this goal")
    return "completed at observation tier; a regressed plan-node observation reopens it"


def projection(journal, *, closure: bool = True) -> dict:
    """Every goal on this body, read-only (safe while the body runs). Labels say what is and is not claimed."""
    reg = GoalRegistry(ledger=journal.ledger, quarantine_unhydratable=True)
    facts = founder_facts(journal.ledger)
    signed, ok = facts.signed, facts.admitted
    book = MissionBook(journal)
    goals, unadmitted = [], []
    for gid in reg.goals():
        spec, state = reg.get(gid), reg.state(gid)
        stop = facts.stopped(gid) if state.status == "paused" else None
        row = {"goal_id": gid, "founder_intent": spec.founder_intent, "desired_state": spec.desired_state,
               "priority": reg.effective_priority(gid), "status": state.status,
               "stopped_by_founder": stop is not None, "stop_label": _stop_label(facts, gid, state.status),
               "completion_label": _completion_label(book, spec, state.status),
               "stop_command": stop["by"] if stop else None,
               "active_node": state.active_node_id, "active_gate": state.active_gate, "sbm": state.sbm,
               "blockers": list(state.blockers), "last_woken_at": state.last_woken_at, "wake_reason": state.wake_reason,
               "missions": _mission_rows(book, spec.authority.get("missions", [])),
               "moves": [m.intervention_id for m in _moves(spec)],
               "refused_routes": len(state.preferences.get("refused_routes", [])),
               "open_requests": _goal_requests(book, facts.manifests, gid, spec), "supersedes": spec.supersedes}
        if gid in ok:
            goals.append({**row, "admitted": True, "authorization_command": ok[gid]})
        else:
            ref = spec.authority.get("authorization_ref")
            why = (f"its signed GOAL does not admit it here: {facts.refused[ref]}" if ref in facts.refused
                   else "no retained founder-signed GOAL authorizes it")
            unadmitted.append({**row, "admitted": False, "why": why + "; preserved, never woken"})
    turns = journal.ledger.by_type(GoalGravityLoop.TURN_RECORD)
    out = {
        "schema": SCHEMA, "goals": goals, "unadmitted": unadmitted, "quarantined_records": list(reg.quarantined),
        "turns": {"count": len(turns), "last": ({k: turns[-1].payload["turn"][k] for k in ("at", "status", "woken")}
                                                if turns else None)},
        "notices": [e.payload for e in journal.replay("goal.notice")][-10:],
        "faults": [e.payload for e in journal.replay("goal_gravity.fault")][-5:],
        "execution_authority": "none", "executes": False,
        "how_it_acts": "an awake goal pulls its signed missions' next observation forward (a mission waiting on "
                       "your decision then re-observes and repairs its other checks inside its cone); the missions "
                       "do all execution through the AuthorityOffice and the Consequence Gate",
        "approve_means": {"free": APPROVE_MEANS, "paid": APPROVE_MEANS_PAID},
        "completion_tier": "observation: attributed ledger observations recomputed from Gate receipts and "
                           "separate-process appraisals; not external verification",
    }
    if closure:
        out["closure"] = ledger_closure(journal, signed=signed)
    return out


def status_summary(journal) -> dict:
    """The compact Goal Gravity view for ``body.status()['gravity']`` (the phone's /api/status)."""
    label = ("persistent Goal Gravity goals (founder-signed GOAL commands); missions are listed under "
             "'missions' (and 'goals' for older clients)")
    if not journal.ledger.by_type(GoalRegistry.AUTHORIZED_RECORD):
        return {"label": label, "goals": [], "unadmitted": 0, "execution_authority": "none"}
    view = projection(journal, closure=False)
    return {"label": label, "execution_authority": "none", "completion_tier": view["completion_tier"],
            "goals": [{k: g[k] for k in ("goal_id", "desired_state", "status", "stopped_by_founder", "stop_label",
                                         "completion_label", "active_gate", "open_requests")}
                      | {"missions": [m["mission_id"] for m in g["missions"]]} for g in view["goals"]],
            "unadmitted": len(view["unadmitted"]), "faults": len(view["faults"])}


def morning_section(journal) -> dict:
    """What Goal Gravity did overnight, for the morning report: goals, wakes, asks, notices, faults."""
    if not journal.ledger.by_type(GoalRegistry.AUTHORIZED_RECORD):
        return {"goals": [], "note": "no founder-signed GOAL on this body", "execution_authority": "none"}
    view = projection(journal)
    return {"goals": [{k: g[k] for k in ("goal_id", "desired_state", "status", "active_gate", "last_woken_at",
                                         "open_requests")} for g in view["goals"]],
            "unadmitted": [g["goal_id"] for g in view["unadmitted"]], "turns": view["turns"],
            "notices": view["notices"], "faults": view["faults"], "closure": view["closure"],
            "completion_tier": view["completion_tier"], "execution_authority": "none"}


def evidence(journal, goal_id: str) -> dict:
    """Ledger hashes behind one goal: authorization, the signed command, state records, turns, experiences,
    asks and answers, and the bound missions' Gate receipts. Read-only."""
    from egregore.experience import WorldModel
    reg = GoalRegistry(ledger=journal.ledger, quarantine_unhydratable=True)
    matches = [g for g in reg.goals() if g == goal_id or g.startswith(goal_id)]
    if len(matches) != 1:
        raise MissionError(f"no single goal matches {goal_id!r}")
    gid = matches[0]
    spec = reg.get(gid)
    facts = founder_facts(journal.ledger)
    signed, ok = facts.signed, facts.admitted
    ledger = journal.ledger
    command_events = [e for e in journal.replay("command.accepted") if e.payload.get("digest") == ok.get(gid)]
    mids = set(spec.authority.get("missions", []))
    book = MissionBook(journal)
    scopes = _move_scopes(book, facts.manifests, spec)
    requests = [rid for rid, r in book.requests.items() if _goal_request(r, gid, scopes)]
    return {
        "goal_id": gid, "admitted": gid in ok,
        "authorization_record": reg.authorization_hash(gid),
        "signed_goal_command": ({"digest": ok[gid], "event_hash": journal.event_hash(command_events[-1].event_id)}
                                if command_events else None),
        "goal_records": [r.hash for r in ledger.records
                         if r.record_type in (GoalRegistry.TRANSITION_RECORD, GoalRegistry.PREFERENCE_RECORD)
                         and r.payload.get("goal_id") == gid],
        "turns": [r.hash for r in ledger.by_type(GoalGravityLoop.TURN_RECORD)
                  if any(p["goal_id"] == gid for p in r.payload["turn"]["processed"])],
        "experiences": WorldModel(ledger=ledger).evidence_for_goal(gid)[0],
        # an answer row the mission book does not count is shown too, labelled: answer_counted is False
        "asks": [{"request_id": rid, "answer": (_answer_row(book, rid) or {}).get("answer"),
                  "answer_command": (_answer_row(book, rid) or {}).get("command_digest"),
                  "answer_signature_verified": signed_answer(signed, rid, _answer_row(book, rid)) is not None,
                  "answer_counted": rid in book.answers,
                  "approve_means": _approve_means_of(book.requests[rid])}
                 for rid in requests],
        "mission_receipts": sorted({e.payload["receipt"] for e in journal.replay("mission.")
                                    if e.type in ("greg.mission.action", "greg.mission.observed")
                                    and e.payload.get("mission_id") in mids and e.payload.get("receipt")}),
        "notices": [journal.event_hash(e.event_id) for e in journal.replay("goal.notice")
                    if e.payload.get("goal_id") == gid],
        "tier": "ledger records on this body's one hash chain; observation tier, not external verification",
    }


def _answer_row(book: MissionBook, rid: str) -> dict | None:
    """The answer the mission book counts for a request, else the row it keeps unverified (never applied)."""
    return book.answers.get(rid) or (book.unverified.get(rid) or {}).get("row")


def ledger_closure(journal, *, signed: dict | None = None) -> dict:
    """Detective closure over the body ledger.

    Every Gate dispatch traces to a ``greg.authority.grant_issued`` whose authority_ref is a founder MISSION
    command digest that still verifies for this body; no ``egregore.founder_answer`` exists at all (the
    hosted store writes none: founder answers on a body are signed DECISION commands); and every
    ``greg.decision.answered`` carries a signature-verified DECISION for exactly that request and answer.
    The mission fold no longer trusts such a row (it counts only the record re-derived from a signed DECISION
    at its acceptance, ADR-GOAL-GRAVITY-002 P2), so a row reported here moved nothing; the closure still names it,
    because the ledger holds an answer no signed DECISION stands behind."""
    ledger = journal.ledger
    signed = signed if signed is not None else signed_commands(journal, *VERIFIED_KINDS)
    missions = {d: c["envelope"]["body"] for d, c in signed.items()
                if c["kind"] == "MISSION" and c["principal"] == "founder"}
    issued = {r.payload.get("grant_id"): r.payload for r in ledger.by_type("event")
              if r.payload.get("type") == "greg.authority.grant_issued"}
    # grant -> the missions whose recorded actions / observations cite its receipt (the proposal's mission)
    receipt_grant = {r.hash: r.payload.get("grant_id") for r in ledger.by_type("receipt")}
    acted_for: dict[str, set] = {}
    for e in journal.replay("mission."):
        if e.type in ("greg.mission.action", "greg.mission.observed") and e.payload.get("receipt") in receipt_grant:
            acted_for.setdefault(receipt_grant[e.payload["receipt"]], set()).add(e.payload.get("mission_id"))
    problems = []
    dispatches = ledger.by_type("grant_dispatch")
    for r in dispatches:
        grant = issued.get(r.payload.get("grant_id"))
        body = missions.get((grant or {}).get("authority_ref"))
        if grant is None:
            problems.append({"record": r.hash, "problem": "grant_dispatch without greg.authority.grant_issued"})
        elif body is None:
            problems.append({"record": r.hash, "problem": "grant authority_ref is not a verified founder MISSION digest"})
        elif grant.get("cone") != _signed_cone(body):
            problems.append({"record": r.hash, "problem": "grant cone is not the light cone of the founder MISSION it "
                                                          "cites: authority borrowed from another mission's signature"})
        elif acted_for.get(grant.get("grant_id"), set()) - {body.get("mission_id")}:
            problems.append({"record": r.hash, "problem": "grant was used for a mission other than the one its founder "
                                                          "MISSION signs"})
    answers = ledger.by_type("egregore.founder_answer")
    for r in answers:   # a digest alone binds nothing to the item it answers: none may exist on a body
        problems.append({"record": r.hash, "problem": "egregore.founder_answer without a signature-verified DECISION "
                                                      "for its item: a GREG body's hosted attention store writes none"})
    unsigned = 0
    for e in journal.replay("decision.answered"):
        if signed_answer(signed, e.payload.get("request_id"), e.payload) is None:
            unsigned += 1
            problems.append({"record": journal.event_hash(e.event_id),
                             "problem": "decision.answered without a signature-verified DECISION for that request "
                                        "and answer"})
    return {"ok": not problems, "problems": problems, "grant_dispatches": len(dispatches),
            "founder_answers": len(answers), "founder_asks": len(ledger.by_type("egregore.founder_ask")),
            "unsigned_answers": unsigned}


def _signed_cone(body: dict) -> dict | None:
    try:
        from greg.lightcone import LightCone
        return LightCone.from_dict(body["light_cone"]).to_dict()
    except (KeyError, TypeError, ValueError):
        return None


# -- founder operation without code: a GOAL derived from a signed mission ----------------------------

def _band(priority: int) -> int:
    """Mission priority (higher first, default 50) -> goal priority band 1 (highest) .. 5."""
    return max(1, min(5, 5 - int(priority) // 20))


def goal_from_mission(spec: dict, manifests: dict) -> dict:
    """A GOAL body derived deterministically from a founder-signed mission spec.

    Plan nodes are the mission's checks (ladder order first), each with the check as its bottleneck
    metric; the wake condition is the mission id; the ceiling is the mission's light-cone ceiling; the
    only declared moves are the mission's static strategies whose exact scope lies outside its cone
    (these are what the goal may ask about ahead of time), one per check: the strategy the mission's own
    selection ranks first for it. ``manifests`` maps capability id -> manifest (consequence class);
    strategies on capabilities absent there, or advancing no check the mission's loop pursues, are left out
    and listed; alternatives the mission would not run first are listed under ``alternatives_not_declared``.

    The wake condition is the mission id: intake that names the mission or its targets wakes the goal on any
    channel (``BodyRelevanceRouter``), and so does any changed observation of its checks."""
    mid, cone = spec["mission_id"], spec["light_cone"]
    from greg.lightcone import LightCone
    light = LightCone.from_dict(cone)
    ladder = [c for rung in (spec["closure"].get("ladder") or []) for c in rung]
    order = list(dict.fromkeys(ladder + [c["check_id"] for c in spec["success_checks"]]))
    checks = {c["check_id"]: c for c in spec["success_checks"]}
    pursued = pursued_checks(spec)
    # One move per check: only the strategy the mission's own selection ranks first for a check (no track
    # record yet; the ask path re-ranks live and refuses any other) may be declared, so one decision is one ask.
    first = {cid: first_choice(spec, {cid}, manifest_for=lambda s: manifests.get(s.get("capability")), records={})
             for cid in sorted(pursued)}
    moves, skipped, alternatives = {}, [], []
    for s in spec["strategies"]:
        manifest = manifests.get(s.get("capability"))
        if "capability" not in s or s.get("bind") or "$from_action" in json.dumps(s.get("params", {})):
            continue
        if manifest is None or not set(s["advances"]) & pursued:   # unregistered, or never run by the mission
            skipped.append(s["action_id"])
            continue
        cost = float(s.get("cost_usd", 0.0))
        outside = light.admits(capability=s["capability"], target=s["target"], cost_usd=cost,
                               consequence_class=manifest.consequence_class,
                               at=instant(cone["horizon"]) - timedelta(seconds=1))
        if not outside:
            continue
        mine = [c for c in order if first.get(c) == s["action_id"]]
        if not mine:                      # an alternative: the mission runs (or asks for) another one first
            alternatives.append(s["action_id"])
            continue
        move = InterventionSpec.build(
            intervention_id=s["action_id"], description=s.get("rationale") or f"{s['capability']} on {s['target']}",
            action_class="greg." + s["capability"], requested_capability=s["capability"],
            consequence_class=manifest.consequence_class, target=s["target"],
            expected_outcome=s.get("expected_outcome") or f"advances {', '.join(s['advances'])}",
            payload={"mission_id": mid, "action_id": s["action_id"]}, estimated_cost_usd=cost)
        moves.setdefault(mine[0], []).append(move)
    plan = [PlanNode.build(node_id=cid, outcome=checks[cid]["description"], gate=f"mission {mid} check {cid}",
                           sbm=f"{mid}.{cid}", sbm_direction="eq", sbm_target=True,
                           interventions=tuple(moves.get(cid, ()))) for cid in order]
    goal = GoalSpec.build(
        founder_intent=spec["founder_expression"], desired_state=spec["intended_effect"],
        priority=_band(spec.get("priority", 50)),
        authority={"authorized_by": "template", "authorization_ref": "template", "legal_principal": PRINCIPAL,
                   "max_consequence_class": cone["max_consequence_class"]},
        time_horizon=f"until {cone['horizon']}", plan=plan, relevant_entities=[mid],
        wake_conditions=(WakeCondition.build(kind="subject", match=mid),),
        review_cadence_seconds=int(spec["closure"].get("cadence_seconds", 86400)))
    body = {k: v for k, v in goal.to_dict().items() if k not in DERIVED_GOAL_FIELDS}
    return {"goal_command": {"goal": body, "missions": [mid], "max_consequence_class": cone["max_consequence_class"]},
            "strategies_left_out": skipped,
            **({"alternatives_not_declared": alternatives} if alternatives else {}),
            "note": "derived deterministically from your signed mission; signing it as a GOAL authorizes no new "
                    "action: the mission's light cone and Gate still decide every execution"}
