"""Infinite Goal Chase for the GREG body: persistent missions as feedback control.

A mission is a founder-signed target state plus the scope in which GREG may
pursue it. Each tick is one turn of a goal-directed feedback loop:

    observe (read-only sensors, through the Gate)
      -> discrepancy = failing checks of the current setpoint
      -> none failing: bounded mission closes; infinite mission advances to the
         next setpoint on its ladder, or holds and keeps re-verifying so drift is
         noticed and corrected (the practical meaning of "self-healing")
      -> otherwise choose the highest-leverage strategy that advances a failing
         check (most discrepancy closed per cost; structured routes before
         visual ones; founder critique exclusions respected)
      -> missing function  -> CapabilityDeficit -> Capability Genesis -> resume
      -> outside scope / constitution requires a human -> ONE decision request,
         then wait economically with the blocker remembered
      -> uncertain outcome -> reconcile; never blind retry of a consequential act

Mission truth is a projection of ``greg.*`` events on the canonical spine, so a
killed process, a new process or a replacement machine reconstructs the same
state. Process completion never closes a mission: only re-observed evidence does.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from greg.authority import AuthorityOffice
from greg.capabilities import InvocationContext, ROUTES
from greg import routing
from greg.journal import Journal, iso
from greg.lightcone import LightCone
from provenance.ledger import sha256_json

ROOT = Path(__file__).resolve().parents[1]
MISSION_SCHEMA = json.loads((ROOT / "contracts/greg-mission.schema.json").read_text())
TERMINAL = {"ACHIEVED", "ABANDONED", "SUPERSEDED"}
LIFECYCLE_STATES = {"ACTIVE", "PAUSED", "ABANDONED", "SUPERSEDED"}
DECISION_ANSWERS = {"approve", "reject", "reconcile_executed", "reconcile_not_executed"}


class MissionError(ValueError):
    """Malformed or conflicting mission input. Retained as data, never executed."""


def validate_mission(spec: dict) -> dict:
    errors = sorted(Draft202012Validator(MISSION_SCHEMA, format_checker=FormatChecker()).iter_errors(spec),
                    key=lambda e: list(e.path))
    if errors:
        raise MissionError(f"mission contract: {errors[0].message} at {list(errors[0].path)}")
    cone = LightCone.from_dict(spec["light_cone"])
    checks = {c["check_id"] for c in spec["success_checks"]}
    if len(checks) != len(spec["success_checks"]):
        raise MissionError("duplicate check ids")
    actions = [s["action_id"] for s in spec["strategies"]]
    if len(actions) != len(set(actions)):
        raise MissionError("duplicate strategy ids")
    for strategy in spec["strategies"]:
        unknown = set(strategy["advances"]) - checks
        if unknown:
            raise MissionError(f"strategy {strategy['action_id']} advances unknown checks {sorted(unknown)}")
        if ("capability" in strategy) == ("function" in strategy):
            raise MissionError("each strategy names exactly one of capability or function")
    ladder = spec["closure"].get("ladder", [])
    for rung in ladder:
        if set(rung) - checks:
            raise MissionError("ladder rung names unknown checks")
    if spec["closure"]["kind"] == "bounded" and ladder:
        raise MissionError("bounded missions close on their checks; ladders are for infinite missions")
    functions = [c["function"] for c in spec.get("capability_specs", [])]
    if len(functions) != len(set(functions)):
        raise MissionError("duplicate capability_specs functions")
    if sum(c["build_budget_usd"] for c in spec.get("capability_specs", [])) > cone.budget_usd + 1e-9:
        raise MissionError("capability build budgets exceed the mission budget")
    del cone
    return spec


def _field(output, path: str):
    value = output
    for part in path.split(".") if path else []:
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            raise KeyError(path)
    if isinstance(value, dict) and value.get("truncated"):
        value = value["prefix"]
    return value


def evaluate_predicate(predicate: dict, output) -> tuple[bool, str]:
    op = predicate["op"]
    try:
        value = _field(output, predicate.get("field", ""))
    except KeyError:
        return (op == "absent"), f"field {predicate.get('field')!r} absent"
    expected = predicate.get("value")
    if op == "exists":
        return True, "present"
    if op == "absent":
        return False, "present"
    if op == "equals":
        return value == expected, f"{value!r} == {expected!r}"
    if op == "contains":
        return (expected in value) if isinstance(value, (str, list)) else False, f"contains {expected!r}"
    if op == "not_contains":
        return (expected not in value) if isinstance(value, (str, list)) else False, f"not contains {expected!r}"
    if op in ("gte", "lte"):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return False, "not numeric"
        return (value >= expected if op == "gte" else value <= expected), f"{value} {op} {expected}"
    if op == "count_gte":
        return (len(value) >= expected) if isinstance(value, (list, str)) else False, f"len {op} {expected}"
    raise MissionError(f"unknown predicate op {op!r}")


@dataclass
class MissionState:
    spec: dict
    command_digest: str
    cone: LightCone
    status: str = "ACTIVE"
    paused: bool = False
    rung: int = 0
    blocker: dict | None = None
    failed: dict = field(default_factory=dict)          # action_id -> reason
    excluded: dict = field(default_factory=dict)        # action_id -> founder critique reason
    attempts: dict = field(default_factory=dict)        # action_id -> next attempt number
    spent_usd: float = 0.0
    approved_scopes: set = field(default_factory=set)
    rejected_scopes: set = field(default_factory=set)
    observations: dict = field(default_factory=dict)    # check_id -> latest observation data
    next_observe_at: str | None = None
    actions_done: int = 0
    setpoints_reached: int = 0
    pending_effect: dict = field(default_factory=dict)  # action_id -> checks it should change

    @property
    def mission_id(self):
        return self.spec["mission_id"]

    def current_checks(self) -> list[dict]:
        ladder = self.spec["closure"].get("ladder") or []
        if self.spec["closure"]["kind"] == "infinite" and ladder:
            wanted = set().union(*ladder[: self.rung + 1])
        else:
            wanted = {c["check_id"] for c in self.spec["success_checks"]}
        return [c for c in self.spec["success_checks"] if c["check_id"] in wanted]


class MissionBook:
    """Projection of mission truth from retained greg.* events."""

    def __init__(self, journal: Journal):
        self.journal = journal
        self.missions: dict[str, MissionState] = {}
        self.requests: dict[str, dict] = {}
        self.answers: dict[str, dict] = {}
        self.rebuild()

    def rebuild(self):
        self.missions, self.requests, self.answers, self.withdrawn = {}, {}, {}, {}
        for event in self.journal.replay():
            kind, data = event.type[len("greg."):], event.payload
            mid = data.get("mission_id")
            m = self.missions.get(mid)
            if kind == "mission.registered":
                self.missions[mid] = MissionState(spec=data["spec"], command_digest=data["command_digest"],
                                                  cone=LightCone.from_dict(data["spec"]["light_cone"]))
            elif m is None:
                if kind == "decision.requested":
                    self.requests[data["request_id"]] = data
                elif kind == "decision.answered":
                    self.answers[data["request_id"]] = data
                elif kind == "decision.withdrawn":
                    self.withdrawn[data["request_id"]] = data
                continue
            elif kind == "mission.lifecycle":
                m.paused = data["state"] == "PAUSED"
                if data["state"] in ("ABANDONED", "SUPERSEDED"):
                    m.status = data["state"]
            elif kind == "mission.observed":
                m.observations[data["check_id"]] = data
                if data["passed"]:  # drift later -> previously ineffective strategies may be tried again
                    for aid in [a for a, r in m.failed.items() if r.startswith(f"executed but {data['check_id']} ")]:
                        m.failed.pop(aid)
                for aid, checks in list(m.pending_effect.items()):
                    if data["check_id"] not in checks:
                        continue
                    if data["passed"]:
                        checks.discard(data["check_id"])
                    else:
                        # Surprise: executed, yet the world did not change. Replan
                        # instead of repeating; eligible again after a later pass.
                        m.failed[aid] = f"executed but {data['check_id']} still failing: {data['detail']}"[:300]
                    if not checks:
                        m.pending_effect.pop(aid, None)
            elif kind == "mission.action":
                aid = data["action_id"]
                m.attempts[aid] = data["attempt"] + 1
                if data["status"] == "DONE":
                    m.actions_done += 1
                    m.spent_usd += data.get("cost_usd", 0.0)
                    m.failed.pop(aid, None)
                    strategy = next((s for s in m.spec["strategies"] if s["action_id"] == aid), None)
                    if strategy:
                        m.pending_effect[aid] = set(strategy["advances"])
                elif data["status"] in ("REFUSED", "UNAVAILABLE"):
                    m.failed[aid] = "; ".join(data["reasons"])[:300]
            elif kind == "mission.blocked":
                m.blocker = data["blocker"]
            elif kind == "mission.unblocked":
                m.blocker = None
            elif kind == "mission.setpoint":
                m.setpoints_reached += 1
                m.rung = data["next_rung"]
            elif kind == "mission.achieved":
                m.status = "ACHIEVED"
            elif kind == "mission.schedule":
                m.next_observe_at = data["next_observe_at"]
            elif kind == "mission.strategy_excluded":
                m.excluded[data["action_id"]] = data["reason"]
            elif kind == "decision.requested":
                self.requests[data["request_id"]] = data
            elif kind == "decision.withdrawn":
                self.withdrawn[data["request_id"]] = data
            elif kind == "decision.answered":
                self.answers[data["request_id"]] = data
                request = self.requests.get(data["request_id"])
                if request and data["answer"] == "approve":
                    m.approved_scopes.add(request["scope_digest"])
                elif request and data["answer"] == "reject":
                    m.rejected_scopes.add(request["scope_digest"])
                    if request.get("action_id"):
                        m.failed[request["action_id"]] = "founder rejected: " + data.get("reason", "")[:200]

    def open_requests(self) -> list[dict]:
        return [r for rid, r in self.requests.items() if rid not in self.answers and rid not in self.withdrawn]


class MissionEngine:
    """One tick = one bounded turn of every active mission's feedback loop."""

    def __init__(self, *, journal: Journal, office: AuthorityOffice, registry, secrets, workspace_root: Path,
                 read_roots: tuple, genesis=None, max_actions_per_tick: int = 1, deliver_root: Path | None = None):
        self.journal, self.office, self.registry, self.secrets = journal, office, registry, secrets
        self.workspace_root, self.read_roots = Path(workspace_root), tuple(Path(p) for p in read_roots)
        self.deliver_root = Path(deliver_root) if deliver_root else None
        self.genesis, self.max_actions_per_tick = genesis, max_actions_per_tick
        self.book = MissionBook(journal)

    # -- founder inputs (already signature-verified by the body) ---------------
    def register(self, spec: dict, command_digest: str) -> str:
        spec = validate_mission(spec)
        mid = spec["mission_id"]
        existing = self.book.missions.get(mid)
        if existing:
            if existing.command_digest == command_digest or existing.spec == spec:
                return mid
            raise MissionError("mission id already bound to different founder intent; supersede explicitly")
        self.journal.record("mission.registered", {"mission_id": mid, "spec": spec,
                                                   "command_digest": command_digest}, key=mid)
        self.book.rebuild()
        return mid

    def lifecycle(self, body: dict, command_digest: str):
        mid, state = body.get("mission_id"), body.get("state")
        if mid not in self.book.missions or state not in LIFECYCLE_STATES:
            raise MissionError("unknown mission or lifecycle state")
        if self.book.missions[mid].status in TERMINAL:
            raise MissionError("terminal mission cannot change lifecycle")
        self.journal.record("mission.lifecycle", {"mission_id": mid, "state": state,
                                                  "reason": body.get("reason", ""),
                                                  "command_digest": command_digest}, key=command_digest)
        self.book.rebuild()

    def answer(self, body: dict, command_digest: str):
        rid, answer = body.get("request_id"), body.get("answer")
        request = self.book.requests.get(rid)
        if request is None or answer not in DECISION_ANSWERS:
            raise MissionError("unknown decision request or answer")
        if rid in self.book.withdrawn:
            raise MissionError("request withdrawn: " + self.book.withdrawn[rid]["why"])
        if rid in self.book.answers:
            if self.book.answers[rid]["answer"] == answer:
                return  # duplicate approval: no duplicate action
            raise MissionError("decision already answered differently")
        if request["kind"] == "RECONCILIATION" and not answer.startswith("reconcile_"):
            raise MissionError("reconciliation requests take reconcile_* answers")
        if request["kind"] != "RECONCILIATION" and answer.startswith("reconcile_"):
            raise MissionError("reconcile answers apply only to reconciliation requests")
        self.journal.record("decision.answered", {"request_id": rid, "mission_id": request["mission_id"],
                                                  "answer": answer, "reason": str(body.get("reason", ""))[:500],
                                                  "command_digest": command_digest}, key=rid)
        self.book.rebuild()

    def exclude_strategy(self, mission_id: str, action_id: str, reason: str, critique_ref: str):
        self.journal.record("mission.strategy_excluded", {"mission_id": mission_id, "action_id": action_id,
                                                          "reason": reason[:300], "critique_ref": critique_ref},
                            key=[mission_id, action_id, critique_ref])
        self.book.rebuild()

    # -- the loop ---------------------------------------------------------------
    def tick(self, now: datetime, *, should_stop=None) -> list[dict]:
        """One turn per mission. ``should_stop`` is consulted before every mission step:
        a stop that arrives mid-tick admits no further dispatch (from #112)."""
        self.book.rebuild()
        summary = []
        order = sorted(self.book.missions.values(), key=lambda m: (-m.spec.get("priority", 0), m.mission_id))
        for m in order:
            if should_stop is not None and should_stop():
                summary.append({"mission_id": m.mission_id, "state": "NOT_STEPPED", "why": "stop requested"})
                continue
            summary.append({"mission_id": m.mission_id, **self._step(m, now)})
        return summary

    def _context(self, m: MissionState, manifest) -> InvocationContext:
        return InvocationContext(workspace=self.workspace_root / m.mission_id.replace(":", "_"),
                                 read_roots=self.read_roots, secrets=self.secrets, manifest=manifest,
                                 deliver_root=self.deliver_root)

    def _request(self, m: MissionState, *, kind: str, scope_digest: str, action_id: str | None, why: str,
                 recommendation: str, alternatives: list, requested: dict, now: datetime) -> str:
        epoch = 0
        while True:
            rid = "req-" + sha256_json({"mission": m.mission_id, "kind": kind, "scope": scope_digest,
                                        **({"epoch": epoch} if epoch else {})})[7:31]
            if rid not in self.book.withdrawn:
                break
            epoch += 1  # the same discrepancy returned after healing: a new escalation
        if rid in self.book.requests:
            return rid  # one escalation per exact scope; waiting creates no spam
        self.journal.record("decision.requested", {
            "request_id": rid, "mission_id": m.mission_id, "kind": kind, "action_id": action_id,
            "scope_digest": scope_digest, "why_now": why, "recommendation": recommendation,
            "alternatives": alternatives, "authority_requested": requested,
            "consequence_of_no_response": "the mission waits; no action is taken",
            "created_at": iso(now), "reality_status": "RECORDED_LOCAL_MESSAGE"}, key=rid)
        return rid

    def _block(self, m: MissionState, blocker: dict):
        if m.blocker != blocker:
            self.journal.record("mission.blocked", {"mission_id": m.mission_id, "blocker": blocker},
                                key=[m.mission_id, blocker])
            m.blocker = blocker

    def _unblock(self, m: MissionState, why: str):
        self.journal.record("mission.unblocked", {"mission_id": m.mission_id, "resolved": m.blocker, "why": why},
                            key=[m.mission_id, "unblock", m.blocker])
        m.blocker = None

    def _blocker_resolved(self, m: MissionState) -> tuple[bool, str]:
        b = m.blocker
        if b["type"] in ("decision", "reconciliation"):
            answer = self.book.answers.get(b["request_id"])
            return (answer is not None, f"founder answered {answer['answer']}" if answer else "awaiting founder")
        if b["type"] == "capability":
            ok, why = self.registry.usable(b["capability_id"]) if b.get("capability_id") else (False, "none")
            if not ok and self.genesis is not None and b.get("function"):
                cap = self.genesis.find_attached(b["function"])
                return (cap is not None, "capability now attached" if cap else why)
            return ok, why
        if b["type"] == "no_strategy":
            return True, "re-evaluate strategies at cadence"
        return False, "unknown blocker"

    def _schedule(self, m: MissionState, now: datetime, seconds: int):
        at = iso(now + timedelta(seconds=seconds))
        self.journal.record("mission.schedule", {"mission_id": m.mission_id, "next_observe_at": at},
                            key=[m.mission_id, "schedule", at])
        m.next_observe_at = at

    def _step(self, m: MissionState, now: datetime) -> dict:
        if m.status in TERMINAL:
            return {"state": m.status}
        if m.paused:
            return {"state": "PAUSED"}
        if datetime.fromisoformat(m.cone.horizon.replace("Z", "+00:00")) <= now:
            self._block(m, {"type": "decision", "request_id": self._request(
                m, kind="SCOPE_RENEWAL", scope_digest=sha256_json({"horizon": m.cone.horizon}), action_id=None,
                why="the mission mandate horizon expired", recommendation="renew with a new signed MISSION",
                alternatives=["abandon", "renew with narrower scope"], requested={"horizon": "extend"}, now=now),
                "why": "mandate expired", "reconsider": "founder renews or abandons"})
            return {"state": "BLOCKED", "blocker": m.blocker}
        if m.blocker and m.blocker.get("failing_checks") and not self._blocker_resolved(m)[0]:
            return self._watch_while_blocked(m, now)
        if m.blocker:
            resolved, why = self._blocker_resolved(m)
            if not resolved:
                return {"state": "WAITING", "blocker": m.blocker, "why": why}
            if m.blocker["type"] == "reconciliation":
                answer = self.book.answers[m.blocker["request_id"]]["answer"]
                aid = m.blocker["action_id"]
                self.journal.record("mission.action", {
                    "mission_id": m.mission_id, "action_id": aid, "attempt": m.attempts.get(aid, 1) - 1,
                    "status": "DONE" if answer == "reconcile_executed" else "RECONCILED_NOT_EXECUTED",
                    "reasons": ["founder reconciliation: " + answer], "cost_usd": 0.0},
                    key=[m.mission_id, aid, "reconciled", m.blocker["request_id"]])
            self._unblock(m, why)
            self.book.rebuild()
            m = self.book.missions[m.mission_id]
        if m.next_observe_at and now < datetime.fromisoformat(m.next_observe_at.replace("Z", "+00:00")):
            return {"state": "WAITING", "until": m.next_observe_at}

        failing, evidence = self._observe(m, now)
        if failing is None:
            return {"state": "BLOCKED", "blocker": m.blocker}
        # Fresh observations may reveal a surprise; decide on the updated truth.
        self.book.rebuild()
        m = self.book.missions[m.mission_id]
        self._record_routing_outcomes(m)
        if not failing:
            return self._setpoint_reached(m, now, evidence)
        errors = set(self.sensor_errors)
        if errors and errors == failing:
            # The world was not measured; that is not a failed goal. Back off and
            # re-observe; escalate once after repeated measurement failure.
            streak = 0
            for obs in reversed([e.payload for e in self.journal.replay("mission.observed")
                                 if e.payload["mission_id"] == m.mission_id]):
                if obs["check_id"] in errors and obs["detail"].startswith("sensor "):
                    streak += 1
                else:
                    break
            if streak >= 3:
                rid = self._request(m, kind="SENSOR_FAILURE", scope_digest=sha256_json(sorted(errors)), action_id=None,
                                    why="the mission cannot measure its success checks",
                                    recommendation="repair or replace the sensor capability, or revise the check",
                                    alternatives=["attach another capability for this function", "abandon"],
                                    requested={"checks": sorted(errors)}, now=now)
                self._block(m, {"type": "decision", "request_id": rid, "why": "repeated sensor failure",
                                "reconsider": "founder repairs sensing"})
                return {"state": "BLOCKED", "blocker": m.blocker}
            self._schedule(m, now, 30 * streak or 30)
            return {"state": "SENSOR_RETRY", "checks": sorted(errors)}
        return self._pursue(m, now, failing, evidence)

    def _observe(self, m: MissionState, now: datetime):
        failing, evidence = set(), []
        sensor_errors = self.sensor_errors = set()
        for check in m.current_checks():
            sensor = check["sensor"]
            manifest, adapter, missing = self._resolve(sensor)
            if manifest is None:
                self._deficit(m, sensor, now, purpose=f"sensor for {check['check_id']}")
                return None, None
            if manifest.consequence_class != "read_only":
                self._block(m, {"type": "no_strategy", "why": f"sensor {manifest.capability_id} is not read-only"})
                return None, None
            attempt = m.attempts.get("sense:" + check["check_id"], 0)
            outcome = self.office.act(
                mission_id=m.mission_id, cone=m.cone, command_digest=m.command_digest, manifest=manifest,
                adapter=adapter, ctx=self._context(m, manifest), params=sensor.get("params", {}),
                target=sensor["target"], cost_usd=0.0, expected_outcome="observation captured",
                evidence_refs=[], attempt=f"{attempt}@{iso(now)}", spent_usd=m.spent_usd,
                approved_scopes=m.approved_scopes)
            if outcome.status != "DONE":
                if outcome.status in ("OUTSIDE_SCOPE", "NEEDS_DECISION"):
                    rid = self._request(m, kind="SENSOR_SCOPE", scope_digest=outcome.scope_digest, action_id=None,
                                        why=f"sensor for {check['check_id']} is outside the mission scope",
                                        recommendation="approve this exact read-only observation or narrow the check",
                                        alternatives=["reject and revise the success check"],
                                        requested={"capability": manifest.capability_id, "target": sensor["target"]},
                                        now=now)
                    self._block(m, {"type": "decision", "request_id": rid, "why": "; ".join(outcome.reasons)})
                    return None, None
                passed, detail = False, "sensor " + outcome.status + ": " + "; ".join(outcome.reasons)[:200]
                sensor_errors.add(check["check_id"])
            else:
                passed, detail = evaluate_predicate(check["predicate"], outcome.output)
            data = {"mission_id": m.mission_id, "check_id": check["check_id"], "passed": passed,
                    "detail": detail[:300], "receipt": outcome.receipt_hash, "rung": m.rung, "at": iso(now)}
            self.journal.record("mission.observed", data, key=[m.mission_id, check["check_id"], outcome.proposal_id])
            if outcome.receipt_hash:
                evidence.append(outcome.receipt_hash)
            if not passed:
                failing.add(check["check_id"])
        return failing, evidence

    def _record_routing_outcomes(self, m: MissionState):
        """Close the routing loop: an executed strategy that did not change the world
        lowers its capability's reliability for every future mission."""
        for aid, reason in m.failed.items():
            if not reason.startswith("executed but "):
                continue
            done = [e.payload for e in self.journal.replay("mission.action")
                    if e.payload["mission_id"] == m.mission_id and e.payload["action_id"] == aid
                    and e.payload["status"] == "DONE"]
            if done:
                last = done[-1]
                self.journal.record("routing.outcome", {"mission_id": m.mission_id, "action_id": aid,
                                                        "capability": last["capability"], "verdict": "ineffective",
                                                        "receipt": last["receipt"], "reason": reason[:300]},
                                    key=[m.mission_id, aid, last["receipt"]])

    def _watch_while_blocked(self, m: MissionState, now: datetime) -> dict:
        """No strategy is not blindness: keep re-observing at cadence. If the world heals
        without GREG acting, the escalation is withdrawn as moot (a body event, never a
        founder answer) and the mission resumes; otherwise it keeps waiting, silently."""
        if m.next_observe_at and now < datetime.fromisoformat(m.next_observe_at.replace("Z", "+00:00")):
            return {"state": "WAITING", "blocker": m.blocker, "until": m.next_observe_at}
        failing, evidence = self._observe(m, now)
        if failing is None:
            return {"state": "BLOCKED", "blocker": m.blocker}
        if failing:
            self._schedule(m, now, m.spec["closure"].get("cadence_seconds", 3600))
            return {"state": "WAITING", "blocker": m.blocker, "still_failing": sorted(failing)}
        rid = m.blocker["request_id"]
        why = "world re-observed: every failing check now passes without any GREG action"
        self.journal.record("decision.withdrawn", {"request_id": rid, "mission_id": m.mission_id, "why": why,
                                                   "evidence": evidence, "at": iso(now)}, key=[rid, "withdrawn"])
        self._unblock(m, why)
        self.book.rebuild()
        return self._setpoint_reached(self.book.missions[m.mission_id], now, evidence)

    def _setpoint_reached(self, m: MissionState, now: datetime, evidence: list) -> dict:
        closure = m.spec["closure"]
        if closure["kind"] == "bounded":
            self.journal.record("mission.achieved", {
                "mission_id": m.mission_id, "evidence": evidence, "actions_done": m.actions_done,
                "closure_rule": "every success check re-observed passing through the Gate",
                "founder_authenticated_mission": True, "at": iso(now)}, key=[m.mission_id, "achieved"])
            return {"state": "ACHIEVED", "evidence": evidence}
        ladder = closure.get("ladder") or []
        if m.rung + 1 < len(ladder):
            self.journal.record("mission.setpoint", {"mission_id": m.mission_id, "reached_rung": m.rung,
                                                     "next_rung": m.rung + 1, "evidence": evidence, "at": iso(now)},
                                key=[m.mission_id, "rung", m.rung])
            return {"state": "ADVANCED", "rung": m.rung + 1}
        # Homeostasis: the infinite mission holds its highest setpoint and keeps
        # re-verifying it; a later failing check is pursued again.
        self._schedule(m, now, closure.get("cadence_seconds", 3600))
        return {"state": "HOLDING", "evidence": evidence}

    def _resolve(self, spec: dict):
        cid = spec.get("capability")
        if cid is None and self.genesis is not None:
            found = self.genesis.find_attached(spec["function"])
            cid = found.capability_id if found else None
        if cid is None:
            return None, None, spec.get("function")
        ok, _ = self.registry.usable(cid)
        if not ok and cid in self.registry.manifests and self.registry.state[cid] == "ATTACHED":
            return self.registry.manifests[cid], self.registry.adapters[cid], None  # unavailable is reported by act
        if not ok:
            return None, None, cid
        return self.registry.manifests[cid], self.registry.adapters[cid], None

    def _deficit(self, m: MissionState, spec: dict, now: datetime, *, purpose: str):
        function = spec.get("function") or self.registry.manifests.get(spec.get("capability"), None)
        function = function.function if hasattr(function, "function") else (function or spec.get("capability"))
        if self.genesis is not None:
            capability = self.genesis.resolve(mission=m, function=function, purpose=purpose, now=now)
            if capability is not None:
                return capability
        rid = self._request(m, kind="CAPABILITY_ATTACH", scope_digest=sha256_json({"function": function}),
                            action_id=None, why=f"missing capability for {purpose}",
                            recommendation="attach a verified capability for this function, or revise the mission",
                            alternatives=["provide an API key/connector", "revise the strategy", "abandon"],
                            requested={"function": function}, now=now)
        self._block(m, {"type": "capability", "function": function, "capability_id": spec.get("capability"),
                        "request_id": rid, "why": f"no attached capability for {function}",
                        "reconsider": "a verified capability for this function is attached"})
        return None

    def _pursue(self, m: MissionState, now: datetime, failing: set, evidence: list) -> dict:
        candidates = []
        records = routing.track_record(self.journal)
        value = float(m.spec.get("value_per_check_usd", 1.0))
        for index, s in enumerate(m.spec["strategies"]):
            gain = len(set(s["advances"]) & failing)
            if not gain or s["action_id"] in m.failed or s["action_id"] in m.excluded:
                continue
            manifest = self.registry.manifests.get(s.get("capability"))
            if manifest is None and s.get("function") and self.genesis is not None:
                manifest = self.genesis.find_attached(s["function"])
            route = ROUTES.index(manifest.route) if manifest else len(ROUTES)
            estimate = routing.reliability(records.get(manifest.capability_id) if manifest else None)
            expected = routing.score(gain=gain, reliability_estimate=estimate,
                                     cost_usd=float(s.get("cost_usd", 0.0)), value_per_check_usd=value)
            candidates.append((-expected, route, index, s, estimate))
        if not candidates:
            key = sha256_json({"failing": sorted(failing), "failed": sorted(m.failed), "excluded": sorted(m.excluded)})
            rid = self._request(m, kind="NO_STRATEGY", scope_digest=key, action_id=None,
                                why="every strategy for the failing checks is exhausted, refused or excluded",
                                recommendation="add or revise strategies, widen scope, or abandon the mission",
                                alternatives=[f"{a}: {r}" for a, r in sorted({**m.failed, **m.excluded}.items())][:10],
                                requested={"failing_checks": sorted(failing)}, now=now)
            self._block(m, {"type": "decision", "request_id": rid, "why": "no admissible strategy",
                            "failing_checks": sorted(failing), "reconsider": "founder revises mission"})
            return {"state": "BLOCKED", "blocker": m.blocker}
        candidates.sort(key=lambda c: c[:3])
        s = candidates[0][3]
        routing_decision = {"chosen": s["action_id"], "expected_value": round(-candidates[0][0], 4),
                            "reliability": round(candidates[0][4], 4),
                            "alternatives": [{"action_id": c[3]["action_id"], "expected_value": round(-c[0], 4),
                                              "reliability": round(c[4], 4)} for c in candidates[1:6]]}
        manifest, adapter, _ = self._resolve(s)
        if manifest is None:
            if self._deficit(m, s, now, purpose=f"strategy {s['action_id']}") is None:
                return {"state": "BLOCKED", "blocker": m.blocker}
            manifest, adapter, _ = self._resolve(s)
            if manifest is None:
                return {"state": "BLOCKED", "blocker": m.blocker}
        aid = s["action_id"]
        attempt = m.attempts.get(aid, 0)
        outcome = self.office.act(
            mission_id=m.mission_id, cone=m.cone, command_digest=m.command_digest, manifest=manifest,
            adapter=adapter, ctx=self._context(m, manifest), params=s.get("params", {}), target=s["target"],
            cost_usd=float(s.get("cost_usd", 0.0)), expected_outcome=s.get("expected_outcome", "strategy executed"),
            evidence_refs=evidence, attempt=attempt, spent_usd=m.spent_usd, approved_scopes=m.approved_scopes,
            evidence_confidence=float(s.get("evidence_confidence", 1.0)))
        record = {"mission_id": m.mission_id, "action_id": aid, "attempt": attempt, "status": outcome.status,
                  "reasons": [str(r)[:300] for r in outcome.reasons], "receipt": outcome.receipt_hash,
                  "capability": manifest.capability_id, "route": manifest.route,
                  "cost_usd": outcome.cost_usd if outcome.status == "DONE" else 0.0,
                  "scope_digest": outcome.scope_digest, "routing": routing_decision, "at": iso(now)}
        if outcome.status in ("OUTSIDE_SCOPE", "NEEDS_DECISION"):
            if outcome.scope_digest in m.rejected_scopes:
                record["status"] = "REFUSED"
                record["reasons"].append("founder already rejected this exact scope")
                self.journal.record("mission.action", record, key=[m.mission_id, aid, attempt, "rejected"])
                return {"state": "REPLANNING", "action": aid}
            rid = self._request(m, kind="APPROVAL", scope_digest=outcome.scope_digest, action_id=aid,
                                why="; ".join(outcome.reasons)[:400],
                                recommendation=f"approve {aid} ({manifest.capability_id} on {s['target']}) "
                                               f"at ${s.get('cost_usd', 0.0)}: {s.get('rationale', '')}"[:400],
                                alternatives=[x["action_id"] for x in m.spec["strategies"] if x["action_id"] != aid][:5]
                                + ["reject: the mission will try alternatives or ask again"],
                                requested={"capability": manifest.capability_id, "target": s["target"],
                                           "consequence_class": manifest.consequence_class,
                                           "cost_usd": s.get("cost_usd", 0.0)}, now=now)
            self._block(m, {"type": "decision", "request_id": rid, "action_id": aid, "why": record["reasons"][:3],
                            "reconsider": "founder approves or rejects this exact scope"})
            return {"state": "WAITING", "blocker": m.blocker}
        self.journal.record("mission.action", record, key=[m.mission_id, aid, attempt])
        if outcome.status == "UNCERTAIN":
            if manifest.retry_safe:
                return {"state": "RETRYING", "action": aid, "why": "read-only idempotent capability"}
            rid = self._request(m, kind="RECONCILIATION", scope_digest=outcome.scope_digest, action_id=aid,
                                why="an action may or may not have executed before an interruption",
                                recommendation="inspect the retained evidence, then state whether it executed",
                                alternatives=["reconcile_executed", "reconcile_not_executed"],
                                requested={"action_id": aid}, now=now)
            self._block(m, {"type": "reconciliation", "request_id": rid, "action_id": aid,
                            "why": "uncertain completion; no blind retry",
                            "reconsider": "founder reconciliation decision"})
            return {"state": "BLOCKED", "blocker": m.blocker}
        # DONE: re-observe next tick to verify the effect in the world; REFUSED/
        # UNAVAILABLE: the failure is retained and an alternative is tried next.
        return {"state": "ACTED" if outcome.status == "DONE" else "REPLANNING", "action": aid,
                "status": outcome.status}
