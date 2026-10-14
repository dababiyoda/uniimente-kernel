"""Goal Gravity on the GREG body: one canonical persistent operating path (ADR-GOAL-GRAVITY-002).

    founder-signed GOAL --Body.apply (Ed25519, nonce, TTL)--> egregore GoalRegistry on the body ledger
    Body.tick --> tick() before the mission engine; no goal record means no work and no record:
        admission   retained GOAL envelope re-verified under the key valid at its ledger position and
                    rebuilt byte for byte; anything else is preserved and quarantined (narrowing only)
        guard       a signed founder stop/change/revoke is restored if an unsigned record undid it
        sense       Gate receipts (check predicate recomputed), separate-process appraisals, greg.path,
                    non-quarantined intake (untrusted): only new or changed evidence
        loop        egregore GoalGravityLoop.turn in body mode: no gate, no executor, no grant
                      awake goal  -> MissionEngine.observe_now for its signed missions (timing only)
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
from datetime import datetime, timedelta
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from egregore.attention import AttentionItem
from egregore.contracts import ContractError, SignalEnvelope, digest, require_text
from egregore.goals import CONSEQUENCE_CLASSES, PREFERENCE_KINDS, PRIORITIES, GoalRegistry, GoalSpec, InterventionSpec, \
    PlanNode, WakeCondition
from egregore.gravity import GoalGravityLoop
from egregore.resources import ResourceGovernor
from events.spine import EventError
from greg import asks, path as devpath
from greg.authority import PRINCIPAL
from greg.capabilities import BUILTINS, CapabilityManifest
from greg.founder import CLOCK_SKEW, MAX_TTL, instant, key_id, signing_bytes
from greg.journal import SOURCE, iso
from greg.missions import TERMINAL, MissionBook, MissionError, evaluate_predicate, strategy_scope
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


class _Genomes:
    """egregore.gps capability view over GREG's one CapabilityRegistry (present = registered + usable)."""

    def __init__(self, registry):
        self.registry = registry

    def get(self, name, version):
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
    this body, with a nonce no earlier accepted (or verified-then-rejected GOAL / GOAL_CONTROL) command
    used, accepted inside its signed validity. GOAL and GOAL_CONTROL commands must also pass the command
    path's own validators (``check_goal`` / ``check_control``) against the mission book, the capability
    manifests and these facts as they stood at that position. Everything else is retained data only:
    goal-registry state records never feed these facts, so an unsigned record can neither admit, re-open,
    un-mute, re-prioritize nor resume a goal."""
    body_id: str
    signed: dict = field(default_factory=dict)          # digest -> verified, fresh command (+ principal)
    admitted: dict = field(default_factory=dict)        # goal_id -> the GOAL digest that admitted it
    specs: dict = field(default_factory=dict)           # goal_id -> GoalSpec of an admitted goal
    refused: dict = field(default_factory=dict)         # digest -> why a signed GOAL / GOAL_CONTROL does not count
    closed: dict = field(default_factory=dict)          # goal_id -> {status, by, issued_at[, superseded_by]}
    closed_intents: dict = field(default_factory=dict)  # goal intent digest -> issued_at of the signed closure
    stop: dict = field(default_factory=dict)            # goal_id -> last signed stop / resume / change
    narrowing: dict = field(default_factory=dict)       # goal_id -> {state preference key: [values]}
    floor: dict = field(default_factory=dict)           # goal_id -> lowest priority signed (never above the spec's)
    authorizations: dict = field(default_factory=dict)  # goal_id -> first egregore.goal_authorized payload
    book: Any = None                                    # MissionBook folded to the end of the ledger
    manifests: dict = field(default_factory=dict)       # capability id -> manifest, at the end of the ledger

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
    devices: dict[str, dict] = {}
    seen_nonces: set[str] = set()
    book = MissionBook(_NoEvents())
    manifests = _manifests_builtin()
    builtin = set(manifests)
    facts = FounderFacts(body_id=body_id or "", book=book, manifests=manifests)
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
        if kind == "greg.founder.enrolled":
            if not rooted:                     # only the first enrollment is the root; later ones are data
                founders[p["key_id"]] = p["public_key"]
                rooted = True
                if body_id is None:
                    facts.body_id = str(p.get("body_id") or "")   # no body named: nothing verifies (fail closed)
            continue
        if kind == "greg.command.rejected":
            consumed = p.get("consumed")
            if isinstance(consumed, dict) and isinstance(consumed.get("nonce"), str):
                seen_nonces.add(consumed["nonce"])
            continue
        if kind == "greg.capability.registered":
            try:
                manifest = CapabilityManifest.from_dict(p["manifest"])
                if manifest.capability_id not in builtin:
                    manifests[manifest.capability_id] = manifest
            except (KeyError, TypeError, ValueError):
                pass
        if kind != "greg.command.accepted":
            book.fold(kind[len("greg."):], p)
            continue
        nonce = p.get("nonce")
        try:
            _accepted(facts, p, founders, devices, seen_nonces)
        finally:
            if isinstance(nonce, str):
                seen_nonces.add(nonce)
            env = p.get("envelope")
            if isinstance(env, dict) and isinstance(env.get("nonce"), str):
                seen_nonces.add(env["nonce"])
    return facts


def _accepted(facts: FounderFacts, p: dict, founders: dict, devices: dict, seen_nonces: set) -> None:
    ckind, digest_ = p.get("kind"), p.get("digest")
    if ckind not in VERIFIED_KINDS and ckind not in KEY_KINDS:
        return
    env = p.get("envelope")
    if not isinstance(env, dict):
        return
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
        return
    if env.get("nonce") in seen_nonces or p.get("nonce") != env.get("nonce"):
        facts.refused[digest_] = "replayed nonce: an earlier accepted or verified-then-rejected command used it"
        return
    stale = _fresh(env, accepted_at)
    if stale is None and accepted_at is None and ckind in ("GOAL", "GOAL_CONTROL"):
        stale = "no acceptance time on the ledger"
    if stale is not None:
        facts.refused[digest_] = stale
        return
    body = env["body"]
    try:
        if ckind == "ROTATE_FOUNDER_KEY" and principal == "founder":
            founders.pop(env["founder_key_id"], None)
            founders[key_id(body["new_public_key"])] = body["new_public_key"]
        elif ckind == "DEVICE_ENROLL" and principal == "founder":
            devices[key_id(body["public_key"])] = {"public_key": body["public_key"], "label": str(body["label"]),
                                                   "kinds": tuple(body["kinds"]), "expires_at": body["expires_at"]}
        elif ckind == "DEVICE_REVOKE" and principal == "founder":
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


def signed_answer(signed: dict, request_id: str, answer: Any) -> dict | None:
    """The signature-verified DECISION behind one recorded ``decision.answered``, or None.

    It counts only when the cited digest is a verified DECISION (not a MISSION, GOAL or GOAL_CONTROL),
    for exactly this request, with exactly the recorded answer. Every goal-side reader uses this one
    predicate: the mirrored refusal, the attention store, the evidence view and the ledger closure."""
    if not isinstance(answer, dict):
        return None
    cmd = signed.get(answer.get("command_digest"))
    body = ((cmd or {}).get("envelope") or {}).get("body")
    if cmd is None or cmd.get("kind") != "DECISION" or not isinstance(body, dict):
        return None
    if body.get("request_id") != request_id or body.get("answer") != answer.get("answer"):
        return None
    return cmd


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
    return spec


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
        self._routed: dict[str, dict] = {}
        self.asked: list[str] = []

    def begin(self, signed: dict) -> None:
        self.signed = signed
        self.noticed = {e.payload["item_id"] for e in self.body.journal.replay("goal.notice")}
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
        return [rid for rid, r in book.requests.items()
                if r.get("kind") == "APPROVAL" and r.get("mission_id") == scope["mission_id"]
                and r.get("scope_digest") == scope["scope_digest"]]

    def _open(self, item: dict) -> bool:
        if item["kind"] != "decision":
            return item["item_id"] in self._routed or item["item_id"] in self.noticed
        scope = self._scope(item)
        if scope is None:
            return item["item_id"] in self._routed
        book = self.body.engine.book
        return any(rid not in book.answers and rid not in book.withdrawn for rid in self._requests(scope))

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
            if answer and answer.get("answer") in ANSWER and signed_answer(self.signed, rid, answer):
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
        self.body.journal.record("goal.notice", data, key=[item.item_id, kind, why[:300]])
        self.noticed.add(item.item_id)

    def record_ask(self, item: AttentionItem, payload: dict) -> None:
        self._routed[item.item_id] = item.to_dict()
        lane = payload.get("lane", "batched")
        if item.kind != "decision":
            self._notice(item, kind=item.kind, lane=lane)
            return
        spec = self.registry.get(item.goal_id)
        move = next((m for m in _moves(spec) if m.route_hash == item.route_hash), None)
        try:
            if move is None:
                raise MissionError("the decision names no declared move of this goal")
            ref = move.payload
            rid = self.body.engine.request_decision(
                ref["mission_id"], ref["action_id"], why=item.question, recommendation=item.recommendation,
                now=datetime.fromisoformat(str(payload.get("routed_at", iso(self.body.clock()))).replace("Z", "+00:00")),
                evidence={"goal_id": item.goal_id, "goal_item_id": item.item_id, "lane": lane,
                          "evidence_refs": list(item.evidence_refs)},
                quoted=tuple(asks.founder_text([spec.founder_intent, spec.desired_state, move.description,
                                                move.intervention_id, move.expected_outcome,
                                                [n.gate for n in spec.plan], [n.outcome for n in spec.plan]])))
            self.asked.append(rid)
        except (MissionError, asks.AskContractError) as exc:
            self._notice(item, kind="ask_not_recorded", lane=lane, why=f"{type(exc).__name__}: {exc}")

    def record_answer(self, item_id: str, payload: dict) -> None:
        raise ContractError("founder answers on a GREG body arrive only as signed DECISION commands")


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
            state = reg.record_preference(gid, kind=ck, value=value, actor=actor, reason=reason, now=now)
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
    """Narrowing only: unadmitted goals never pull; a signed stop/change/revoke is never undone unsigned."""
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
    if closed is not None and closed["status"] == "revoked" and state.status != "revoked":
        reg.revoke(gid, actor=f"restoring signed {closed['principal']} control {closed['by'][7:19]}",
                   reason="signed revoke", now=at)
        return
    stop = facts.stopped(gid)
    if stop is not None and state.status not in CLOSED:
        reg.record_preference(gid, kind="stop_pushing", value=True, reason="signed stop", now=at,
                              actor=f"restoring signed {stop['principal']} control {stop['by'][7:19]}")


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
                if r.get("kind") == "APPROVAL" and r.get("mission_id") == scope["mission_id"] \
                        and r.get("scope_digest") == scope["scope_digest"] and answer \
                        and answer.get("answer") == "reject" and signed_answer(signed, rid, answer):
                    who = signed[answer["command_digest"]]["principal"]
                    reg.record_refusal(gid, route_hash=move.route_hash, now=at,
                                       actor=f"{who} (signed DECISION {answer['command_digest'][7:19]})",
                                       reason=answer.get("reason") or "rejected")
                    mirrored.append(move.intervention_id)
                    break
    return mirrored


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
    for rec in records:
        if rec.record_type != "event":
            continue
        t, p = rec.payload.get("type"), rec.payload.get("payload", {})
        if t in PATH_EVENTS:
            path_changed = True
        if t == "greg.mission.observed" and p.get("receipt"):
            m = book.missions.get(p["mission_id"])
            receipt = body.ledger.find(p["receipt"])
            check = next((c for c in (m.spec["success_checks"] if m else []) if c["check_id"] == p["check_id"]), None)
            if receipt is None or receipt.record_type != "receipt" or check is None:
                continue
            value, _ = evaluate_predicate(check["predicate"], receipt.payload.get("result", {}).get("output"))
            trust = "attributed" if value == p["passed"] else "untrusted"
            latest[(p["mission_id"], p["check_id"])] = (rec.payload["event_id"], p["at"], rec.hash, value, trust)
        elif t == "greg.mission.appraised" and p.get("verdict") in ("VERIFIED", "REFUTED"):
            latest[(p["mission_id"], "appraised_verified")] = (rec.payload["event_id"], rec.ts_utc, rec.hash,
                                                               p["verdict"] == "VERIFIED", "attributed")
        elif t == "greg.external.ingested" and not p.get("quarantined"):
            emit(rec.payload["event_id"], p["at"], rec.hash, trust="untrusted", tags=[p["channel"]],
                 domain=p["channel"])
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
        return {"state": "FAULT", "why": why}


def _tick(body, now: datetime) -> dict:
    held = binding_for(body)
    loop, reg = held.loop, held.loop.registry
    reg.refresh()                                      # goal records any other writer appended
    _record_quarantine(body, reg)
    last = [r.payload["turn"]["at"] for r in body.ledger.by_type(GoalGravityLoop.TURN_RECORD)][-1:]
    at = max([now] + [datetime.fromisoformat(a.replace("Z", "+00:00")) for a in last])   # never backdated
    body.engine.book.rebuild()
    facts = founder_facts(body.ledger, body_id=body.config["body_id"])
    held.store.begin(facts.signed)
    quarantined = _guard(body, reg, facts, at)
    refusals = _settle(body, reg, facts, at)
    signals, end = _sense(body, loop, held.cursor)
    if not (signals or reg.due_for_review(at) or reg.by_status("awake")):
        held.cursor = end
        return {"state": "DORMANT", "quarantined": quarantined, "refusals_mirrored": refusals}
    turn = loop.turn(trigger_id=f"greg:{iso(at)}:{body.ledger.head[7:23]}", now=at, signals=signals,
                     resources=ResourceGovernor(max_model_calls=1, max_estimated_cost_usd=0.01),
                     evidence_confidence=1.0)   # an upper bound only: body mode derives it from world evidence
    held.cursor = end                              # advanced only after the turn succeeded
    pulled = _activate(body, held, turn, at)
    return {"state": turn.status, "turn_id": turn.turn_id, "woken": list(turn.woken), "missions_pulled": pulled,
            "asked": list(held.store.asked), "wake_refused": [w["goal_id"] for w in turn.wake_refused],
            "quarantined": quarantined, "refusals_mirrored": refusals}


# -- read-only projections (CLI, status, morning report, console, closures) ---------------------------

def _mission_rows(book: MissionBook, mids) -> list[dict]:
    rows = []
    for mid in mids:
        m = book.missions.get(mid)
        rows.append({"mission_id": mid, "status": m.status if m else "UNKNOWN", "paused": bool(m and m.paused),
                     "rung": m.rung if m else None, "next_observe_at": m.next_observe_at if m else None,
                     "blocker": (m.blocker or {}).get("why") if m else None})
    return rows


def _goal_requests(book: MissionBook, gid: str, spec: GoalSpec) -> list[str]:
    links = {(m.payload.get("mission_id"), m.payload.get("action_id")) for m in _moves(spec)}
    return [r["request_id"] for r in book.open_requests()
            if (r.get("evidence") or {}).get("goal_id") == gid
            or (r.get("kind") == "APPROVAL" and (r.get("mission_id"), r.get("action_id")) in links)]


def projection(journal, *, closure: bool = True) -> dict:
    """Every goal on this body, read-only (safe while the body runs). Labels say what is and is not claimed."""
    reg = GoalRegistry(ledger=journal.ledger, quarantine_unhydratable=True)
    facts = founder_facts(journal.ledger)
    signed, ok = facts.signed, facts.admitted
    book = MissionBook(journal)
    goals, unadmitted = [], []
    for gid in reg.goals():
        spec, state = reg.get(gid), reg.state(gid)
        row = {"goal_id": gid, "founder_intent": spec.founder_intent, "desired_state": spec.desired_state,
               "priority": reg.effective_priority(gid), "status": state.status,
               "stopped_by_founder": bool(state.preferences.get("stop_pushing")) and gid in ok,
               "active_node": state.active_node_id, "active_gate": state.active_gate, "sbm": state.sbm,
               "blockers": list(state.blockers), "last_woken_at": state.last_woken_at, "wake_reason": state.wake_reason,
               "missions": _mission_rows(book, spec.authority.get("missions", [])),
               "moves": [m.intervention_id for m in _moves(spec)],
               "refused_routes": len(state.preferences.get("refused_routes", [])),
               "open_requests": _goal_requests(book, gid, spec), "supersedes": spec.supersedes}
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
        "how_it_acts": "an awake goal pulls its signed missions' next observation forward; the missions do all "
                       "execution through the AuthorityOffice and the Consequence Gate",
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
            "goals": [{k: g[k] for k in ("goal_id", "desired_state", "status", "stopped_by_founder", "active_gate",
                                         "open_requests")} | {"missions": [m["mission_id"] for m in g["missions"]]}
                      for g in view["goals"]],
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
    links = {(m.payload.get("mission_id"), m.payload.get("action_id")) for m in _moves(spec)}
    requests = [rid for rid, r in book.requests.items()
                if (r.get("evidence") or {}).get("goal_id") == gid
                or (r.get("kind") == "APPROVAL" and (r.get("mission_id"), r.get("action_id")) in links)]
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
        "asks": [{"request_id": rid, "answer": (book.answers.get(rid) or {}).get("answer"),
                  "answer_command": (book.answers.get(rid) or {}).get("command_digest"),
                  "answer_signature_verified": signed_answer(signed, rid, book.answers.get(rid)) is not None}
                 for rid in requests],
        "mission_receipts": sorted({e.payload["receipt"] for e in journal.replay("mission.")
                                    if e.type in ("greg.mission.action", "greg.mission.observed")
                                    and e.payload.get("mission_id") in mids and e.payload.get("receipt")}),
        "notices": [journal.event_hash(e.event_id) for e in journal.replay("goal.notice")
                    if e.payload.get("goal_id") == gid],
        "tier": "ledger records on this body's one hash chain; observation tier, not external verification",
    }


def ledger_closure(journal, *, signed: dict | None = None) -> dict:
    """Detective closure over the body ledger.

    Every Gate dispatch traces to a ``greg.authority.grant_issued`` whose authority_ref is a founder MISSION
    command digest that still verifies for this body; no ``egregore.founder_answer`` exists at all (the
    hosted store writes none: founder answers on a body are signed DECISION commands); and every
    ``greg.decision.answered`` carries a signature-verified DECISION for exactly that request and answer
    (the mission fold still trusts the record itself, ADR-GOAL-GRAVITY-002 P2: this closure detects it)."""
    ledger = journal.ledger
    signed = signed if signed is not None else signed_commands(journal, *VERIFIED_KINDS)
    missions = {d for d, c in signed.items() if c["kind"] == "MISSION" and c["principal"] == "founder"}
    issued = {r.payload.get("grant_id"): r.payload for r in ledger.by_type("event")
              if r.payload.get("type") == "greg.authority.grant_issued"}
    problems = []
    dispatches = ledger.by_type("grant_dispatch")
    for r in dispatches:
        grant = issued.get(r.payload.get("grant_id"))
        if grant is None:
            problems.append({"record": r.hash, "problem": "grant_dispatch without greg.authority.grant_issued"})
        elif grant.get("authority_ref") not in missions:
            problems.append({"record": r.hash, "problem": "grant authority_ref is not a verified founder MISSION digest"})
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


# -- founder operation without code: a GOAL derived from a signed mission ----------------------------

def _band(priority: int) -> int:
    """Mission priority (higher first, default 50) -> goal priority band 1 (highest) .. 5."""
    return max(1, min(5, 5 - int(priority) // 20))


def goal_from_mission(spec: dict, manifests: dict) -> dict:
    """A GOAL body derived deterministically from a founder-signed mission spec.

    Plan nodes are the mission's checks (ladder order first), each with the check as its bottleneck
    metric; the wake condition is the mission id; the ceiling is the mission's light-cone ceiling; the
    only declared moves are the mission's static strategies whose exact scope lies outside its cone
    (these are what the goal may ask about ahead of time). ``manifests`` maps capability id -> manifest
    (consequence class); strategies on capabilities absent there are left out and listed."""
    mid, cone = spec["mission_id"], spec["light_cone"]
    from greg.lightcone import LightCone
    light = LightCone.from_dict(cone)
    ladder = [c for rung in (spec["closure"].get("ladder") or []) for c in rung]
    order = list(dict.fromkeys(ladder + [c["check_id"] for c in spec["success_checks"]]))
    checks = {c["check_id"]: c for c in spec["success_checks"]}
    moves, skipped = {}, []
    for s in spec["strategies"]:
        manifest = manifests.get(s.get("capability"))
        if "capability" not in s or s.get("bind") or "$from_action" in json.dumps(s.get("params", {})):
            continue
        if manifest is None:
            skipped.append(s["action_id"])
            continue
        cost = float(s.get("cost_usd", 0.0))
        outside = light.admits(capability=s["capability"], target=s["target"], cost_usd=cost,
                               consequence_class=manifest.consequence_class,
                               at=instant(cone["horizon"]) - timedelta(seconds=1))
        if not outside:
            continue
        move = InterventionSpec.build(
            intervention_id=s["action_id"], description=s.get("rationale") or f"{s['capability']} on {s['target']}",
            action_class="greg." + s["capability"], requested_capability=s["capability"],
            consequence_class=manifest.consequence_class, target=s["target"],
            expected_outcome=s.get("expected_outcome") or f"advances {', '.join(s['advances'])}",
            payload={"mission_id": mid, "action_id": s["action_id"]}, estimated_cost_usd=cost)
        node = next((c for c in order if c in s["advances"]), order[0])
        moves.setdefault(node, []).append(move)
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
            "note": "derived deterministically from your signed mission; signing it as a GOAL authorizes no new "
                    "action: the mission's light cone and Gate still decide every execution"}
