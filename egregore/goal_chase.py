"""Founder-facing Infinite Goal Chase composition over canonical Kernel owners.

Sandbox v0 only. No scheduler, identity authority, grant issuer, executor plug-in,
or persistent store is implemented here. Goal state is a projection of EventSpine;
work cursors belong to DurableWorkflow; consequences belong to ConsequenceGate.
Use the locked session in goal_chase_sandbox to exercise this trusted-process slice.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid5
import hashlib
import json

from jsonschema import Draft202012Validator, FormatChecker

from egregore.contracts import canonical_copy, digest, ContractError, IntegrityConflict
from egregore.goal_chase_evaluator import evaluate_result
from events.spine import Event, WorkflowStep, WorkflowKilled, durable_workflow, resume_workflow
from memory.causal import CausalMemory
from policy.engine import Proposal, Verdict, evaluate
from provenance.ledger import sha256_json, GENESIS_PREV

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "spiffe://uniimente.internal/egregore/goal-chase-sandbox"
FOUNDER = "spiffe://uniimente.internal/human/alfonso-sandbox"
PRINCIPAL = "alfonso_lopez"
NAMESPACE = UUID("4ea41f57-8d23-4618-a21b-60f9670e403c")
STOPPED = {"ACHIEVED", "FAILED", "SUPERSEDED", "PROHIBITED", "ABANDONED_BY_FOUNDER", "DEFERRED"}
SCHEMA = json.loads((ROOT / "contracts/goal-chase.schema.json").read_text())


def stamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ContractError("clock must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def instant(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ContractError("timestamp requires timezone")
    return result


def validate(kind: str, value: dict) -> dict:
    value = canonical_copy(value)
    Draft202012Validator({**SCHEMA, "oneOf": [{"$ref": "#/$defs/" + kind}]},
                         format_checker=FormatChecker()).validate(value)
    return value


class CommunicationRouter:
    """Deterministic in-memory channel. Durable messages live only on the spine.

    Real adapters need a separate reviewed Gate integration. A transport name or
    external-effects flag cannot turn this class into a live provider.
    """
    def __init__(self, channel="in_memory", *, external_effects=False):
        if channel != "in_memory" or external_effects is not False:
            raise ContractError("external channels/effects are disabled in v0")
        self.available = True
        self.messages = {}

    def deliver(self, message: dict) -> str:
        message = validate("message", message)
        if not self.available:
            raise ConnectionError("sandbox communication adapter unavailable")
        self.messages.setdefault(message["message_id"], canonical_copy(message))
        return digest({"channel": "in_memory", "message_id": message["message_id"]})


class GoalChase:
    def __init__(self, *, spine, gate, registry, actor, verify_founder, clock,
                 router=None, sandbox=False):
        if sandbox is not True or gate.ledger is not spine.ledger:
            raise ContractError("requires explicit sandbox and one canonical ledger")
        if router is not None and type(router) is not CommunicationRouter:
            raise ContractError("only the deterministic simulated channel is admitted")
        self.spine, self.gate, self.registry = spine, gate, registry
        self.actor, self.verify_founder, self.clock = actor, verify_founder, clock
        self.router = router or CommunicationRouter()
        self.memory = CausalMemory(spine.ledger)
        self._refresh()

    @property
    def now(self):
        return self.clock()

    def _profile(self):
        seal = json.loads((ROOT / "tests/fixtures/goal_chase_v0_seal.json").read_text())
        for path, expected in seal.items():
            if hashlib.sha256((ROOT / path).read_bytes()).hexdigest() != expected:
                raise IntegrityConflict("frozen evaluator/spec changed: " + path)
        genomes = {}
        for name in ("research.compare", "prototype.simulate"):
            genome = self.registry.get(name, "1.0.0")
            genomes[name] = asdict(genome) if genome else None
        return digest({"seal": seal, "schema": SCHEMA, "genomes": genomes})

    def _refresh(self):
        ledger = self.spine.ledger
        ok, why = ledger.verify_chain()
        genesis = ledger.records[0]
        expected = {"kind": "genesis", "constitution_hash": self.gate.compiled.constitution_hash}
        if (not ok or genesis.payload != expected or genesis.hash != sha256_json(
                {"seq": 0, "payload": expected, "prev_hash": GENESIS_PREV})):
            raise IntegrityConflict("canonical history failed verification: " + why)
        self.events = self.spine.replay("goal.")
        self.by_id, self.tails, self.goals = {}, {}, {}
        self.requests, self.decisions, self.deliveries, self.ticks = {}, {}, {}, {}
        self.last_fingerprints = {}
        for event in self.events:
            if event.event_id in self.by_id:
                raise IntegrityConflict("duplicate event in canonical goal history")
            p = event.payload
            gid, data = p["goal_id"], p["data"]
            if (p.get("reality_status") != "SIMULATED" or event.source != SOURCE
                    or event.legal_principal != PRINCIPAL
                    or event.policy_version != self.gate.policy_version
                    or event.causal_parent != self.tails.get(gid)):
                raise IntegrityConflict("goal history source/policy/causal lineage mismatch")
            expected_id = str(uuid5(NAMESPACE, event.type + ":" + gid + ":" + p["event_key"]))
            if event.event_id != expected_id:
                raise IntegrityConflict("goal event identity mismatch")
            self.by_id[event.event_id] = event
            self.tails[gid] = event.event_id
            if event.type == "goal.registered":
                env = data["input"]
                self._authenticate(env, "GOAL", at=instant(event.occurred_at))
                goal = validate("goal", env["body"])
                if gid in self.goals or goal["goal_id"] != gid:
                    raise IntegrityConflict("goal was registered twice or misbound")
                self.goals[gid] = {"spec": goal, "input": env, "profile": data["profile"],
                                   "status": goal["lifecycle_state"], "observations": {},
                                   "reconciled": {}, "started": {}, "recorded": {},
                                   "denied_actions": [], "conflicted": False,
                                   "deficits": [], "bottleneck": None}
            elif event.type == "goal.observed":
                obs = validate("observation", data)
                self.goals[gid]["observations"][obs["key"]] = obs
            elif event.type == "goal.action_selected":
                self.goals[gid]["bottleneck"] = data
                self.goals[gid]["status"] = "ACTIVE"
            elif event.type == "goal.approval_requested":
                validate("message", data)
                self.requests[data["message_id"]] = data
                self.goals[gid]["status"] = "AWAITING_FOUNDER"
            elif event.type == "goal.decision_received":
                env = data["input"]
                self._authenticate(env, "DECISION", at=instant(event.occurred_at))
                body = validate("decision", env["body"])
                request = self.requests.get(body["request_id"])
                if not request or body["scope"] != request["authority_requested"]:
                    raise IntegrityConflict("replayed decision has no exact request")
                self.decisions[body["request_id"]] = env
                if body["answer"] == "REJECT":
                    self.goals[gid]["denied_actions"].append(body["scope"]["action"]["action_id"])
                    self.goals[gid]["status"] = "BLOCKED"
            elif event.type == "goal.lifecycle_changed":
                env = data["input"]
                self._authenticate(env, "LIFECYCLE", at=instant(event.occurred_at))
                self.goals[gid]["status"] = env["body"]["state"]
            elif event.type == "goal.intent_conflict":
                self.goals[gid]["conflicted"] = True
                self.goals[gid]["status"] = "BLOCKED"
            elif event.type == "goal.capability_deficit":
                self.goals[gid]["deficits"].append(data)
                self.goals[gid]["status"] = "BLOCKED"
            elif event.type == "goal.waiting":
                self.goals[gid]["status"] = data["status"]
            elif event.type == "goal.action_started":
                self.goals[gid]["started"][data["action_id"]] = data
            elif event.type == "goal.action_recorded":
                self.goals[gid]["recorded"][data["action_id"]] = data
            elif event.type == "goal.reconciled":
                self.goals[gid]["reconciled"][data["action_id"]] = data
                self.goals[gid]["status"] = data["goal_state"]
            elif event.type == "goal.message_delivered":
                self.deliveries[data["message_id"]] = data
            elif event.type == "goal.heartbeat":
                self.ticks[data["trigger_id"]] = data
                self.last_fingerprints.update(data["fingerprints"])

    def _emit(self, kind, key, gid, data):
        event_id = str(uuid5(NAMESPACE, "goal." + kind + ":" + gid + ":" + key))
        data = canonical_copy(data)
        old = self.by_id.get(event_id)
        if old:
            if old.payload["data"] != data or old.payload["goal_id"] != gid:
                raise IntegrityConflict("stable event key reused for changed content")
            return old
        event = Event(type="goal." + kind, source=SOURCE, actor=self.actor,
                      legal_principal=PRINCIPAL, event_id=event_id,
                      occurred_at=stamp(self.now), causal_parent=self.tails.get(gid),
                      policy_version=self.gate.policy_version,
                      payload={"goal_id": gid, "event_key": key,
                               "reality_status": "SIMULATED", "data": data})
        self.spine.emit(event)
        self._refresh()
        return event

    def _authenticate(self, envelope, kind, *, at=None):
        env = validate("envelope", envelope)
        if env["kind"] != kind or self.verify_founder(canonical_copy(env)) is not True:
            raise ContractError("forged or wrong-kind synthetic founder interaction")
        at = at or self.now
        if not instant(env["issued_at"]) <= at < instant(env["expires_at"]):
            raise ContractError("founder interaction is expired or future-dated")
        return env

    def _rejected(self, gid, value, exc):
        # Keep hostile input as inert data. Never execute text or log a signing key.
        try:
            clean = canonical_copy(value)
        except ContractError:
            clean = {"unrepresentable_input": type(value).__name__}
        self._emit("input_rejected", digest(clean), gid,
                   {"input": clean, "reason": str(exc), "instruction_status": "data_only"})

    def register(self, envelope):
        self._refresh()
        gid = envelope.get("body", {}).get("goal_id", "sandbox:rejected")
        try:
            env = self._authenticate(envelope, "GOAL")
            goal = validate("goal", env["body"])
            if gid in ("sandbox:portfolio", "sandbox:rejected"):
                raise ContractError("goal ID is reserved for control/event projection")
            if gid in self.goals:
                if self.goals[gid]["input"] == env:
                    return gid
                self._emit("intent_conflict", digest(env), gid, {"conflicting_input": env})
                raise IntegrityConflict("conflicting founder intent; supersede explicitly")
            ids = [a["action_id"] for a in goal["actions"]]
            if len(ids) != len(set(ids)) or gid in goal["dependencies"]:
                raise ContractError("duplicate action IDs or cyclic self dependency")
            if sum(a["cost_cents"] for a in goal["actions"]) > goal["budget_boundary"]["ceiling_cents"]:
                raise ContractError("action budget exceeds signed goal boundary")
            self._emit("registered", gid, gid, {"input": env, "profile": self._profile()})
            return gid
        except Exception as exc:
            self._rejected(gid, envelope, exc)
            raise

    def observe(self, value):
        self._refresh()
        gid = value.get("goal_id", "sandbox:rejected")
        try:
            obs = validate("observation", value)
            goal = self.goals[gid]
            if goal["status"] in STOPPED - {"DEFERRED"}:
                raise ContractError("goal is terminal")
            if obs["kind"] != "SIMULATION":
                raise ContractError("v0 accepts simulation observations only; model output is not evidence")
            if instant(obs["observed_at"]) > self.now:
                raise ContractError("future observation")
            ids = [r["source_id"] for r in obs["payload"]["records"]]
            if len(ids) != len(set(ids)):
                raise ContractError("duplicate observation source IDs")
            self._emit("observed", obs["observation_id"], gid, obs)
        except Exception as exc:
            self._rejected(gid, value, exc)
            raise

    def lifecycle(self, envelope):
        self._refresh()
        gid = envelope.get("body", {}).get("goal_id", "sandbox:rejected")
        try:
            env = self._authenticate(envelope, "LIFECYCLE")
            body = validate("lifecycle", env["body"])
            goal = self.goals[gid]
            if goal["status"] in STOPPED - {"DEFERRED"}:
                raise ContractError("terminal goal cannot be reactivated")
            if goal["conflicted"] and body["state"] == "ACTIVE":
                raise ContractError("conflicted goal requires explicit supersession")
            self._emit("lifecycle_changed", digest(env), gid, {"input": env})
        except Exception as exc:
            self._rejected(gid, envelope, exc)
            raise

    def _next(self, goal):
        return next((a for a in goal["spec"]["actions"]
                     if a["action_id"] not in goal["reconciled"]), None)

    def _fresh(self, goal, obs):
        return bool(obs and timedelta(0) <= self.now - instant(obs["observed_at"])
                    < timedelta(seconds=goal["spec"]["evidence_requirements"]["max_age_seconds"]))

    def _scope(self, gid, action, observation):
        goal = self.goals[gid]
        deadline = min(instant(goal["input"]["expires_at"]),
                       instant(observation["observed_at"]) + timedelta(
                           seconds=goal["spec"]["evidence_requirements"]["max_age_seconds"]))
        return {"goal_id": gid, "goal_digest": digest(goal["spec"]), "action": action,
                "observation_digest": digest(observation),
                "policy_digest": self.gate.compiled.constitution_hash,
                "qualification_digest": self._profile(), "worker_role": "sandbox:goal-chase",
                "max_uses": 1, "deadline": stamp(deadline)}

    def _request_id(self, scope):
        return digest({"kind": "founder-approval", "scope": scope})

    def _valid_decision(self, request_id, scope):
        env = self.decisions.get(request_id)
        if not env:
            return False
        try:
            self._authenticate(env, "DECISION")
            return (env["body"]["answer"] == "APPROVE" and env["body"]["scope"] == scope
                    and self.now < instant(scope["deadline"]))
        except ContractError:
            return False

    def decide(self, envelope):
        self._refresh()
        gid = envelope.get("body", {}).get("goal_id", "sandbox:rejected")
        try:
            env = self._authenticate(envelope, "DECISION")
            body = validate("decision", env["body"])
            request_id = body["request_id"]
            if request_id in self.decisions:
                if self.decisions[request_id] == env:
                    return request_id
                raise ContractError("request already decided; approval cannot overwrite rejection")
            goal = self.goals[gid]
            if goal["status"] in STOPPED or goal["conflicted"]:
                raise ContractError("goal stopped or founder intent conflicted")
            action = self._next(goal)
            obs = goal["observations"].get(action["observation_key"]) if action else None
            if not action or not self._fresh(goal, obs):
                raise ContractError("no current action or fresh observation")
            scope = self._scope(gid, action, obs)
            request = self.requests.get(request_id)
            if (not request or request_id != self._request_id(scope)
                    or body["scope"] != scope or body["goal_id"] != scope["goal_id"]):
                raise ContractError("approval request, goal, scope, budget or evidence mismatch")
            if body["conditions"] or body["requested_modification"] is not None:
                raise ContractError("conditional/modified approvals require a new explicit goal; not inferred")
            if self.now >= instant(request["expires_at"]):
                raise ContractError("approval request expired")
            # Reuse the canonical DecisionRecord shape inside the one durable event.
            decision = {"decision_id": str(uuid5(NAMESPACE, digest(env))),
                        "decided_at": env["issued_at"], "decider": FOUNDER,
                        "legal_principal": PRINCIPAL, "objective": gid,
                        "question": request["requested_founder_action"],
                        "options_considered": ["APPROVE", "REJECT"], "chosen": body["answer"],
                        "rationale": body["reason"], "evidence_refs": request["evidence_refs"],
                        "policy_version": self.gate.policy_version,
                        "reversibility": action["reversibility"], "authority_chain": [FOUNDER],
                        "expected_outcome": action["expected_outcome"],
                        "ledger_prev_hash": self.spine.ledger.head}
            Draft202012Validator(json.loads((ROOT / "contracts/decision.schema.json").read_text()),
                                 format_checker=FormatChecker()).validate(decision)
            self._emit("decision_received", request_id, gid, {"input": env, "decision": decision})
            return request_id
        except Exception as exc:
            self._rejected(gid, envelope, exc)
            raise

    def _wait(self, gid, action, status, reason, refs):
        data = {"action_id": action["action_id"], "status": status,
                "reason": reason, "evidence_refs": refs}
        self._emit("waiting", digest(data), gid, data)
        raise WorkflowKilled(reason)

    def _ask(self, gid, action, scope, reasons):
        request_id = self._request_id(scope)
        if request_id in self.requests:
            return request_id
        completed = list(self.goals[gid]["reconciled"])
        message = {"message_id": request_id, "goal_id": gid, "kind": "APPROVAL_REQUEST",
                   "urgency": "normal", "why_now": "RESERVED_AUTHORITY_REQUIRED: " + "; ".join(reasons),
                   "situation": self.goals[gid]["spec"]["statement"],
                   "what_has_already_been_done": completed, "current_bottleneck": action["bottleneck"],
                   "recommendation": action["rationale"], "alternatives": action["alternatives"],
                   "evidence_refs": [scope["observation_digest"], scope["goal_digest"]],
                   "uncertainty": "Synthetic fixture only; external outcome and real cost are unmeasured",
                   "requested_founder_action": "Approve or reject this exact sandbox action",
                   "authority_requested": scope, "budget_requested_cents": action["cost_cents"],
                   "deadline": scope["deadline"],
                   "consequence_of_approval": "One bounded simulated action; no real spending or contact",
                   "consequence_of_rejection": "Action stays denied; preserve goal for explicit revision",
                   "consequence_of_no_response": "Wait; no reserved action executes",
                   "reversibility": action["reversibility"],
                   "next_step_if_approved": action["expected_outcome"],
                   "next_step_if_rejected": "Retain rejection; do not ask again for the same action",
                   "dedupe_key": request_id, "created_at": stamp(self.now),
                   "expires_at": scope["deadline"], "reality_status": "SIMULATED"}
        validate("message", message)
        self._emit("approval_requested", request_id, gid, message)
        return request_id

    def _perform(self, gid, action):
        self._refresh()
        goal = self.goals[gid]
        aid = action["action_id"]
        if aid in goal["reconciled"]:
            return {aid: goal["reconciled"][aid]["receipt_hash"]}
        if goal["status"] in STOPPED or goal["conflicted"] or aid in goal["denied_actions"]:
            raise WorkflowKilled("goal/action is stopped, conflicted or denied")
        # Complete proof beats a stale workflow cursor after a checkpoint crash.
        if aid in goal["started"]:
            return self._reconcile(gid, action)
        if self.now >= instant(goal["input"]["expires_at"]):
            self._wait(gid, action, "BLOCKED", "signed goal expired", [])
        obs = goal["observations"].get(action["observation_key"])
        if not self._fresh(goal, obs):
            self._wait(gid, action, "NEEDS_EVIDENCE", "missing/stale observation", [digest(obs)] if obs else [])
        if not any(r["usable"] for r in obs["payload"]["records"]):
            self._wait(gid, action, "WAITING", "no useful source available", [digest(obs)])
        if self._profile() != goal["profile"]:
            self._wait(gid, action, "BLOCKED", "qualification/configuration changed; new reviewed goal required", [])
        selection = {"action_id": aid, "bottleneck": action["bottleneck"],
                     "discrepancy": goal["spec"]["observable_success_state"] + " remains unmet",
                     "rationale": action["rationale"], "alternatives": action["alternatives"],
                     "evidence_refs": [digest(obs), digest(goal["spec"])]}
        self._emit("action_selected", digest(selection), gid, selection)
        available, reason = self.registry.may_instantiate(
            action["capability"], action["version"], requested_class=action["consequence_class"],
            requested_budget_usd=action["cost_cents"] / 100)
        from egregore.goal_chase_sandbox import sandbox_function_available, run_sandbox_function
        available = available and sandbox_function_available(action["capability"])
        if not available:
            deficit = {"goal_id": gid, "action_id": aid, "required_function": action["capability"],
                       "reason": reason, "state": "NEEDED", "candidate_maturity": "DISCOVERED",
                       "route": "developmental/research proposal boundary",
                       "search_order": ["FIND", "RECOMPOSE", "SPECIALIZE", "MUTATE", "INVENT"],
                       "execution_authority": "none", "evidence_refs": [digest(obs)]}
            self._emit("capability_deficit", digest(deficit), gid, deficit)
            raise WorkflowKilled("capability deficit; no founder decision needed")
        if action["action_class"] in goal["spec"]["prohibited_actions"]:
            self._wait(gid, action, "BLOCKED", "action prohibited by signed goal", [digest(goal["spec"])])
        scope = self._scope(gid, action, obs)
        proposal = Proposal(actor=self.actor, legal_principal=PRINCIPAL,
                            action_class=action["action_class"], objective=gid,
                            payload={"scope": scope, "simulation": True}, target=action["target"],
                            consequence_class=action["consequence_class"], evidence_confidence=1.0,
                            evidence_refs=[digest(obs)], estimated_cost_usd=action["cost_cents"] / 100,
                            requested_capability=action["capability"],
                            expected_outcome=action["expected_outcome"],
                            proposal_id=str(uuid5(NAMESPACE, digest(scope))))
        identity_ok, _ = self.gate.passports.verify(self.actor)
        policy = evaluate(self.gate.compiled, proposal, identity_ok=identity_ok, grant=None)
        resolution = {"action_id": aid, "scope": scope, "capability_resolved": True,
                      "verdict": policy.verdict.value, "reasons": policy.reasons,
                      "authority_refs": goal["spec"]["authority_refs"], "law_applied": policy.law_applied}
        self._emit("authority_resolved", digest(resolution), gid, resolution)
        if policy.verdict == Verdict.DENY:
            self._wait(gid, action, "BLOCKED", "; ".join(policy.reasons), [digest(scope)])
        rid = self._request_id(scope)
        if policy.verdict == Verdict.REQUIRE_HUMAN:
            # One founder cannot satisfy a dual-control requirement.
            required = self.gate.compiled.reserved_matters.get(action["action_class"], ["alfonso"])
            if required != ["alfonso"]:
                self._wait(gid, action, "BLOCKED", "additional authority required", [digest(scope)])
            self._ask(gid, action, scope, policy.reasons)
            if not self._valid_decision(rid, scope):
                raise WorkflowKilled("pending exact founder decision")
        self._emit("action_started", gid + ":" + aid, gid,
                   {"action_id": aid, "proposal_id": proposal.proposal_id,
                    "scope": scope, "observation": obs,
                    "decision_ref": rid if policy.verdict == Verdict.REQUIRE_HUMAN else None})

        def execute(bound):
            # Recheck the exact decision and goal at dispatch, without promoting
            # model recommendations or capability descriptors into authority.
            if bound.payload["scope"] != scope or self.now >= instant(scope["deadline"]):
                raise ContractError("scope expired/changed at dispatch")
            if policy.verdict == Verdict.REQUIRE_HUMAN and not self._valid_decision(rid, scope):
                raise ContractError("decision invalid at dispatch")
            result = run_sandbox_function(action["capability"], canonical_copy(obs), canonical_copy(action))
            # Validate before the Gate can record a positive outcome. The raw
            # candidate result and dissent remain evidence even when rejected.
            result = canonical_copy(result)
            try:
                passed, reasons = evaluate_result(action["capability"], obs, action, result)
            except (KeyError, TypeError, AttributeError, ValueError) as exc:
                passed, reasons = False, ["malformed candidate result: " + type(exc).__name__]
            if type(result.get("external_effects")) is not int or result.get("result_class") != "positive":
                passed = False
                reasons.append("invalid result/effect type")
            self._emit("candidate_evaluated", gid + ":" + aid, gid,
                       {"action_id": aid, "passed": passed, "reasons": reasons,
                        "result": result, "evaluator": "frozen deterministic v0"})
            if not passed:
                raise ContractError("candidate failed independent sandbox evaluation")
            return result

        record = self.gate.run(proposal, executor=execute,
                               approver=lambda p, reasons: (self._valid_decision(rid, scope), rid))
        self._emit("action_recorded", gid + ":" + aid, gid,
                   {"action_id": aid, "record": asdict(record)})
        return self._reconcile(gid, action)

    def _reconcile(self, gid, action):
        goal, ledger = self.goals[gid], self.spine.ledger
        aid = action["action_id"]
        started = goal["started"][aid]
        rejected = [e for e in self.events if e.type == "goal.candidate_evaluated"
                    and e.payload["goal_id"] == gid and e.payload["data"]["action_id"] == aid
                    and e.payload["data"]["passed"] is False]
        if rejected:
            self._wait(gid, action, "FAILED", "candidate failed independent sandbox evaluation",
                       [digest(rejected[-1].payload)])
        # Recover through the canonical Gate's event/receipt/outcome join. No
        # second task result is invented if the workflow checkpoint is missing.
        action_ids = {r.payload["action_id"] for r in ledger.by_type("event")
                      if r.payload.get("type") == "action.proposed"
                      and r.payload.get("proposal_id") == started["proposal_id"]}
        receipts = [r for r in ledger.by_type("receipt") if r.payload.get("action_id") in action_ids]
        outcomes = [r for r in ledger.by_type("outcome") if r.payload.get("action_ref") in action_ids]
        if len(action_ids) != 1 or len(receipts) != 1 or len(outcomes) != 1:
            self._wait(gid, action, "BLOCKED", "RECONCILIATION_REQUIRED: incomplete or ambiguous Gate proof", [])
        receipt, outcome = receipts[0], outcomes[0]
        result = receipt.payload["result"]
        passed, reasons = evaluate_result(action["capability"], started["observation"], action, result)
        if not passed:
            self._wait(gid, action, "FAILED", "independent sandbox evaluation failed: " + "; ".join(reasons),
                       [receipt.hash, outcome.hash])
        if outcome.payload["external_observation"] != action["expected_outcome"]:
            self._wait(gid, action, "FAILED", "Gate outcome mismatch", [outcome.hash])
        remaining = [a for a in goal["spec"]["actions"]
                     if a["action_id"] not in {*goal["reconciled"], aid}]
        data = {"action_id": aid, "receipt_hash": receipt.hash, "outcome_hash": outcome.hash,
                "goal_state": "ACTIVE" if remaining else "ACHIEVED", "reality_status": "SIMULATED",
                "verification": "frozen deterministic evaluator", "artifact": result["artifact"],
                "next_action": remaining[0]["action_id"] if remaining else None,
                "learning": "Retain synthetic result and rejected sources; no external success inferred"}
        self._emit("reconciled", gid + ":" + aid, gid, data)
        return {aid: receipt.hash}

    def _fingerprint(self, gid):
        goal = self.goals[gid]
        return digest({"status": goal["status"], "observations": goal["observations"],
                       "fresh": {k: self._fresh(goal, v) for k, v in goal["observations"].items()},
                       "expired": self.now >= instant(goal["input"]["expires_at"]),
                       "reconciled": goal["reconciled"], "profile": self._profile(),
                       "decisions": {k: v for k, v in self.decisions.items() if v["body"]["goal_id"] == gid},
                       "decision_valid": {k: self._valid_decision(k, v["body"]["scope"])
                                          for k, v in self.decisions.items() if v["body"]["goal_id"] == gid},
                       "dependencies": {d: self.goals.get(d, {}).get("status") for d in goal["spec"]["dependencies"]}})

    def pending_messages(self):
        result = []
        for rid, message in self.requests.items():
            goal = self.goals[message["goal_id"]]
            action = self._next(goal)
            obs = goal["observations"].get(action["observation_key"]) if action else None
            if (rid not in self.decisions and action and goal["status"] not in STOPPED
                    and not goal["conflicted"] and action["action_id"] not in goal["denied_actions"]
                    and self._fresh(goal, obs)
                    and self._request_id(self._scope(message["goal_id"], action, obs)) == rid):
                result.append(canonical_copy(message))
        return result

    def tick(self, trigger_id):
        if not isinstance(trigger_id, str) or not trigger_id:
            raise ContractError("heartbeat needs a stable trigger ID")
        self._refresh()
        if trigger_id in self.ticks:
            return canonical_copy(self.ticks[trigger_id])
        # A fixed sequential workflow is the baseline within one goal. Across
        # goals, spend this trigger on useful, evidence-ready work first; retain
        # blocked goals and their reactivation reasons rather than blindly walk
        # a flat backlog in priority order.
        candidates = []
        for gid, goal in self.goals.items():
            action = self._next(goal)
            if goal["status"] in STOPPED or not action:
                continue
            obs = goal["observations"].get(action["observation_key"])
            blockers = [d for d in goal["spec"]["dependencies"]
                        if self.goals.get(d, {}).get("status") != "ACHIEVED"]
            ready = self._fresh(goal, obs) and not blockers and not goal["conflicted"]
            ready = ready and action["action_id"] not in goal["denied_actions"]
            candidates.append({"goal_id": gid, "action_id": action["action_id"],
                               "evidence_ready": bool(ready), "dependency_blockers": blockers,
                               "priority": goal["spec"]["priority"], "cost_cents": action["cost_cents"],
                               "downstream_goals": sum(gid in g["spec"]["dependencies"] for g in self.goals.values()),
                               "evidence_refs": [digest(obs)] if obs else [],
                               "reactivation_trigger": goal["spec"]["review_trigger"]})
        candidates.sort(key=lambda c: (not c["evidence_ready"], -c["priority"],
                                       -c["downstream_goals"], c["cost_cents"], c["goal_id"]))
        active = [c["goal_id"] for c in candidates]
        selection = {"selected": active[0] if active else None, "alternatives": candidates,
                     "rationale": "Fresh evidence and satisfied dependencies, then founder priority, downstream leverage, lower cost; stable ID breaks ties"}
        self._emit("portfolio_selected", digest(selection), "sandbox:portfolio", selection)
        before = len(self.requests)
        suppressed = 0
        for gid in active:
            goal = self.goals[gid]
            if self.last_fingerprints.get(gid) == self._fingerprint(gid):
                suppressed += int(goal["status"] == "AWAITING_FOUNDER")
                continue
            if goal["conflicted"] or any(self.goals.get(d, {}).get("status") != "ACHIEVED"
                                         for d in goal["spec"]["dependencies"]):
                continue
            steps = [WorkflowStep(a["action_id"], lambda state, a=a: self._perform(gid, a), max_retries=0)
                     for a in goal["spec"]["actions"]]
            wid = "goal-chase:" + gid
            checkpoints = [r for r in self.spine.ledger.by_type("workflow")
                           if r.payload.get("workflow_id") == wid]
            if checkpoints and checkpoints[-1].payload["status"] in ("completed", "failed", "compensated"):
                continue
            workflow = (resume_workflow(self.spine, wid, steps) if checkpoints else
                        durable_workflow(self.spine, wid, steps, actor=self.actor, legal_principal=PRINCIPAL))
            try:
                workflow.execute()
            except WorkflowKilled:
                pass
        for message in self.pending_messages():
            rid, gid = message["message_id"], message["goal_id"]
            if rid in self.deliveries:
                continue
            try:
                receipt_id = self.router.deliver(message)
                self._emit("message_delivered", rid, gid, {"message_id": rid, "receipt_id": receipt_id,
                                                            "channel": "in_memory", "reality_status": "SIMULATED"})
            except ConnectionError:
                self._emit("delivery_unavailable", rid, gid, {"message_id": rid, "retry_on": "next legitimate trigger"})
        result = {"trigger_id": trigger_id, "active_goals": len(active),
                  "primary_bottleneck": self.goals[active[0]]["bottleneck"] if active else None,
                  "new_requests": len(self.requests) - before, "duplicate_suppressed": suppressed,
                  "fingerprints": {gid: self._fingerprint(gid) for gid in self.goals},
                  "next_trigger": "await observation, founder decision, expiry or caller heartbeat",
                  "reality_status": "SIMULATED"}
        self._emit("heartbeat", trigger_id, "sandbox:portfolio", result)
        return canonical_copy(result)

    def snapshot(self):
        self._refresh()
        return canonical_copy({gid: {"state": g["status"], "bottleneck": g["bottleneck"],
                                    "statement": g["spec"]["statement"],
                                    "current_state": list(g["reconciled"]),
                                    "reality_status": "SIMULATED",
                                    "founder_intent_lineage": g["spec"]["founder_intent_lineage"],
                                    "reconciled": g["reconciled"], "deficits": g["deficits"],
                                    "denied_actions": g["denied_actions"], "profile": g["profile"],
                                    "next_action": self._next(g)} for gid, g in self.goals.items()})

    def metrics(self):
        self._refresh()
        completed = sum(g["status"] == "ACHIEVED" for g in self.goals.values())
        minutes = [e["body"]["intervention_minutes"] for e in self.decisions.values()]
        known_minutes = bool(minutes) and all(v is not None for v in minutes)
        starts = sum(len(g["started"]) for g in self.goals.values())
        reconciled = sum(len(g["reconciled"]) for g in self.goals.values())
        waiting = [max(0, (instant(env["issued_at"]) - instant(self.requests[rid]["created_at"])).total_seconds())
                   for rid, env in self.decisions.items()]
        resumed = []
        for event in self.events:
            if event.type == "goal.action_started":
                rid = event.payload["data"]["decision_ref"]
                if rid:
                    resumed.append(max(0, (instant(event.occurred_at) - instant(self.decisions[rid]["issued_at"])).total_seconds()))
        auto = sum(s["decision_ref"] is None for g in self.goals.values() for s in g["started"].values())
        return {"reality_status": "SIMULATED", "founder_interruptions": len(self.deliveries),
                "decision_requests": len(self.requests),
                "duplicate_suppressed": sum(t["duplicate_suppressed"] for t in self.ticks.values()),
                "sandbox_intervention_minutes": sum(minutes) if known_minutes else None,
                "sandbox_verified_outcomes": completed,
                "sandbox_intervention_minutes_per_verified_outcome": sum(minutes) / completed if known_minutes and completed else None,
                "founder_intervention_minutes_per_verified_outcome": None,
                "real_verified_outcomes": 0, "unauthorized_external_effects": 0,
                "time_waiting_on_founder_seconds": sum(waiting),
                "time_to_resume_after_decision_seconds": resumed,
                "work_started_under_standing_authority_fraction": auto / starts if starts else None,
                "avoidable_escalations": None,
                "unreconciled_actions": starts - reconciled,
                "persistent_closure_requires": "all acceptance gates plus separate fresh-process proof"}
