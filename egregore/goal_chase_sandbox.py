"""Explicit simulation host and deterministic fixtures for Infinite Goal Chase.

No production authentication is claimed. The host, not candidate functions,
holds a synthetic founder key and composes existing Kernel authorities. The key
must be supplied by the test/demo caller and is never persisted in the ledger.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import fcntl
import hashlib
import hmac

from capabilities.genome import GenomeRegistry, CapabilityGenome, AuthorityEnvelope
from compiler.ucl_compiler import compile_constitution
from egregore.contracts import canonical_copy, canonical_json, digest, ContractError
from egregore.goal_chase import GoalChase, ROOT, stamp
from events.spine import EventSpine
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger


class SyntheticFounder:
    """Test-only authentication. This identity is never the real Alfonso."""
    def __init__(self, key: bytes):
        if not isinstance(key, bytes) or len(key) < 32:
            raise ContractError("synthetic founder key must contain at least 32 bytes")
        self._key = key

    def sign(self, kind, body, *, now, expires_at=None, source="sandbox:test-interaction"):
        env = {"kind": kind, "founder_identity": "sandbox:alfonso", "reality_status": "SIMULATED",
               "source_interaction": source, "issued_at": stamp(now),
               "expires_at": stamp(expires_at or now + timedelta(hours=1)), "body": canonical_copy(body)}
        env["signature"] = hmac.new(self._key, canonical_json(env).encode(), hashlib.sha256).hexdigest()
        return env

    def verify(self, env):
        unsigned = {k: v for k, v in env.items() if k != "signature"}
        expected = hmac.new(self._key, canonical_json(unsigned).encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, env.get("signature", ""))


def sandbox_function_available(name):
    return name in ("research.compare", "prototype.simulate")


def run_sandbox_function(name, observation, action):
    """Pure deterministic functions; input snapshots are the entire interface.

    No candidate callable, import path, tool invocation or network destination is
    accepted from a model, goal, observation or founder message.
    """
    if not action["target"].startswith("sandbox:"):
        raise ContractError("real targets are disabled")
    if name == "research.compare":
        records = observation["payload"]["records"]
        usable = sorted((r for r in records if r["usable"]), key=lambda r: (r["cost_cents"], r["source_id"]))
        artifact = {"source_ids": [r["source_id"] for r in usable],
                    "lowest_cost_cents": usable[0]["cost_cents"],
                    "rejected_source_ids": [r["source_id"] for r in records if not r["usable"]]}
    elif name == "prototype.simulate":
        artifact = {"cap_cents": action["cost_cents"], "target": action["target"], "simulated_count": 1}
    else:
        raise ContractError("capability has no qualified built-in implementation")
    return {"observed_outcome": action["expected_outcome"], "artifact": artifact,
            "result_class": "positive", "validation_status": "self_reported",
            "simulation": True, "external_effects": 0,
            "input_digest": digest(observation), "scope_digest": digest(action)}


def registry():
    result = GenomeRegistry()
    for name, consequence in (("research.compare", "internal_write"), ("prototype.simulate", "financial")):
        result.register(CapabilityGenome(
            name=name, version="1.0.0", description="Trusted deterministic sandbox function",
            interface={"inputs": {"observation": "SIMULATION", "action": "bounded snapshot"},
                       "outputs": {"artifact": "SIMULATED"}}, contracts=["evidence", "outcome"],
            authority=AuthorityEnvelope(consequence, 1000000, requires_human=consequence == "financial"),
            acceptance_tests=["egregore/goal_chase_evaluator.py"],
            failure_modes=["missing source", "wrong result", "unqualified candidate"],
            recovery_path="retain negative evidence; stop/reconcile before any retry"))
    return result


@contextmanager
def open_sandbox(path, *, founder, clock=None, router=None, genomes=None):
    """Own the local single-writer lock for the whole session, then release it.

    The lock contains no institutional state. Every durable fact is in the one
    EvidenceLedger. A fresh process remints a synthetic workload identity through
    the existing PassportRegistry; decisions bind its fixed sandbox role and the
    exact goal/action, not an expired previous process credential.
    """
    path = Path(path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(path.suffix + ".lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ContractError("another writer owns this sandbox ledger") from exc
        compiled = compile_constitution(str(ROOT))
        if path.exists() and path.stat().st_size == 0:
            raise ContractError("empty existing ledger is not a new institutional history")
        ledger = EvidenceLedger(compiled.constitution_hash, str(path))
        passports = PassportRegistry()
        actor = passports.issue(kind="workflow", creator="sandbox:founder-host",
                                owner_organ="uniimente-kernel", legal_principal="alfonso_lopez",
                                declared_capabilities=["research.compare", "prototype.simulate"],
                                budget_ceiling_usd=1000000, consequence_class="financial")
        gate = ConsequenceGate(compiled=compiled, passports=passports, ledger=ledger,
                               signer=WitnessSigner(env="development"))
        chase = GoalChase(spine=EventSpine(ledger), gate=gate, registry=genomes or registry(),
                          actor=actor.passport_id, verify_founder=founder.verify,
                          clock=clock or (lambda: datetime.now(timezone.utc)),
                          router=router, sandbox=True)
        try:
            yield chase
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def action(aid="sandbox:research", *, capability="research.compare", reserved=False):
    return {"action_id": aid, "capability": capability, "version": "1.0.0",
            "bottleneck": "Bounded prototype decision" if reserved else "Source qualification",
            "rationale": "Use the smallest reversible fixture experiment after comparing source records",
            "alternatives": ["Defer with retained evidence", "Use a smaller simulated experiment"],
            "observation_key": "sources", "action_class": "spending_above_predefined_thresholds" if reserved else "research.compare",
            "consequence_class": "financial" if reserved else "internal_write", "cost_cents": 43000 if reserved else 0,
            "target": "sandbox:prototype" if reserved else "sandbox:brief",
            "expected_outcome": "SIMULATED: prototype completed" if reserved else "SIMULATED: research compared",
            "reversibility": "reversible"}


def goal(gid="sandbox:GOAL-001", *, now, actions=None, state="ACTIVE", priority=100):
    return {"goal_id": gid, "founder_intent_lineage": ["sandbox:founder-intent", "IGC-SANDBOX-V0"],
            "statement": "Produce a source-qualified brief and exercise one bounded prototype decision",
            "observable_success_state": "Research and authorized sandbox prototype reconciled",
            "current_state": "No verified sandbox steps yet", "reality_status": "SIMULATED",
            "priority": priority, "portfolio_role": "primary" if priority == 100 else "supporting",
            "lifecycle_state": state, "dependencies": [], "assumptions": ["Fixture sources remain fresh"],
            "known_facts": [], "unknowns": ["Real-world efficacy"],
            "constraints": ["Deterministic sandbox only"], "prohibited_actions": ["expansion_of_uniimentes_own_sovereignty"],
            "legal_or_policy_boundaries": ["Existing Kernel law", "No external effects"],
            "budget_boundary": {"ceiling_cents": 43000, "standing_cents": 0},
            "authority_refs": ["sandbox:founder-goal", "authority/authority-matrix.yaml"],
            "evidence_requirements": {"kind": "SIMULATION", "max_age_seconds": 3600},
            "success_metrics": ["VERIFIED_PERSISTENT_GOAL_CHASE_CLOSURES"],
            "failure_conditions": ["Unverified output"], "kill_conditions": ["Any external effect"],
            "review_trigger": "Fresh evidence or founder decision", "active_bottleneck": None,
            "next_decision": None, "next_action": None, "owner": "alfonso",
            "created_at": stamp(now), "updated_at": stamp(now),
            "actions": actions if actions is not None else [action(), action("sandbox:prototype", capability="prototype.simulate", reserved=True)]}


def observation(gid="sandbox:GOAL-001", *, now, oid="sandbox:OBS-001", usable=True):
    return {"observation_id": oid, "goal_id": gid, "key": "sources", "kind": "SIMULATION",
            "observed_at": stamp(now), "source": "sandbox:fixtures",
            "payload": {"records": [
                {"source_id": "sandbox:source-A", "cost_cents": 43000, "usable": usable},
                {"source_id": "sandbox:source-B", "cost_cents": 52000, "usable": usable},
                {"source_id": "sandbox:stale-source", "cost_cents": 9000, "usable": False}]}}


def decision(message, *, answer="APPROVE", minutes=2.0):
    return {"request_id": message["message_id"], "goal_id": message["goal_id"],
            "scope": canonical_copy(message["authority_requested"]), "answer": answer,
            "reason": "Synthetic founder exercises this exact bounded decision",
            "conditions": [], "requested_modification": None, "intervention_minutes": minutes}
