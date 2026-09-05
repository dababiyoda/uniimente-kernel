"""Frozen, deterministic v0 sandbox evaluator; no candidate/runtime imports.

This qualifies a synthetic result, never external reality or authority. Candidate
functions receive only their declared observation and bounded action. They never
receive this callable, its expectations, decision keys, a ledger, or a Gate.
This is interface separation for trusted in-process functions, not OS isolation.
"""
from __future__ import annotations

from egregore.contracts import digest


def evaluate_result(capability: str, observation: dict, action: dict,
                    result: dict) -> tuple[bool, list[str]]:
    errors = []
    if result.get("simulation") is not True or result.get("external_effects") != 0:
        errors.append("result is not an effect-free simulation")
    if result.get("validation_status") != "self_reported":
        errors.append("candidate may not declare its own verification")
    if result.get("observed_outcome") != action["expected_outcome"]:
        errors.append("expected outcome was not observed")
    if result.get("input_digest") != digest(observation):
        errors.append("input lineage mismatch")
    if result.get("scope_digest") != digest(action):
        errors.append("scope lineage mismatch")
    artifact = result.get("artifact", {})
    if capability == "research.compare":
        records = observation["payload"]["records"]
        usable = [r for r in records if r["usable"]]
        source_ids = artifact.get("source_ids", [])
        if not usable or set(source_ids) != {r["source_id"] for r in usable}:
            errors.append("brief omitted or invented a usable source")
        if len(source_ids) != len(set(source_ids)):
            errors.append("brief duplicated sources")
        price = artifact.get("lowest_cost_cents")
        if not any(r["cost_cents"] == price for r in usable):
            errors.append("selected price lacks a source")
        if any(r["cost_cents"] < price for r in usable) if isinstance(price, int) else True:
            errors.append("selected price is not minimal")
        if set(artifact.get("rejected_source_ids", [])) != {
                r["source_id"] for r in records if not r["usable"]}:
            errors.append("negative source evidence was hidden")
    elif capability == "prototype.simulate":
        if artifact != {"cap_cents": action["cost_cents"],
                        "target": action["target"], "simulated_count": 1}:
            errors.append("simulation exceeded or changed its bounded action")
    else:
        errors.append("no frozen qualification for this capability")
    return not errors, errors
