"""Evidence-linked institutional routes for the existing cognition runtime.

Graph weights are explicit input estimates, not inferred social facts or calibrated
probabilities. Strongest-path propagation avoids counting overlapping chains twice.
The result is an ordinary CandidateProposal; only the existing Gate can act on it.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Sequence

from jsonschema import ValidationError

from adapters.contract_validation import validator

from .contracts import CandidateProposal, ContractError, SignalEnvelope, canonical_copy, digest

PROPOSER_NAME = "institutional_leverage"
_LIMITS = {"nodes": 128, "links": 512, "interventions": 64}


def _validate(kind: str, value: Any) -> dict:
    clean = canonical_copy(value)
    try:
        base = validator("institutional-leverage")
        base.evolve(schema={"$ref": f"#/$defs/{kind}", "$defs": base.schema["$defs"]}).validate(clean)
    except ValidationError as exc:
        location = ".".join(str(part) for part in exc.absolute_path)
        raise ContractError(f"institutional leverage {kind}.{location}: {exc.message}") from exc
    return clean


def _timestamp(value: str) -> datetime:
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError("timezone required")
        return result
    except (AttributeError, TypeError, ValueError) as exc:
        raise ContractError("institutional map observed_at must be a timezone-aware timestamp") from exc


def _collect(signals: Sequence[SignalEnvelope], request: dict) -> tuple[dict, dict, list]:
    tables: dict[str, dict[str, dict]] = {kind: {} for kind in _LIMITS}
    origins: dict[tuple[str, str], set[str]] = {}
    ignored = []
    as_of = _timestamp(request["as_of"])
    for signal in sorted(signals, key=lambda item: item.signal_id):
        if "institutional_map" not in signal.payload:
            continue
        age = (as_of - _timestamp(signal.observed_at)).total_seconds()
        if age < 0 or age > request["max_evidence_age_seconds"]:
            ignored.append({"signal_id": signal.signal_id, "reason": "future_or_stale"})
            continue
        model = _validate("map", signal.payload["institutional_map"])
        for kind, records in model.items():
            for record in records:
                refs = set(record["evidence_refs"])
                for claim in record.get("narrative", {}).get("claims", ()):
                    refs.update(claim["evidence_refs"])
                if not refs.issubset(signal.evidence_refs):
                    raise ContractError(f"{kind}/{record['id']} cites evidence outside its source signal")
                existing = tables[kind].get(record["id"])
                if existing is not None and existing != record:
                    raise ContractError(f"conflicting institutional map record: {kind}/{record['id']}")
                tables[kind][record["id"]] = record
                origins.setdefault((kind, record["id"]), set()).add(signal.signal_id)
                if len(tables[kind]) > _LIMITS[kind]:
                    raise ContractError(f"institutional map exceeds total {kind} limit")
    nodes = tables["nodes"]
    if request["outcome_node"] not in nodes:
        raise ContractError("outcome node has no fresh institutional evidence")
    for edge in tables["links"].values():
        if edge["source"] not in nodes or edge["target"] not in nodes:
            raise ContractError(f"dangling institutional link: {edge['id']}")
    for intervention in tables["interventions"].values():
        if intervention["node"] not in nodes:
            raise ContractError(f"unknown intervention node: {intervention['node']}")
    return tables, origins, ignored


def _paths_to(target: str, links: Mapping[str, dict], max_hops: int) -> dict:
    # Bounded Bellman relaxation: O(hops * edges), no exponential path enumeration.
    # Ties prefer fewer hops, then stable edge IDs. Products cannot amplify cycles.
    best = {target: (1.0, ())}
    for _ in range(max_hops):
        next_best = dict(best)
        for edge in sorted(links.values(), key=lambda item: item["id"]):
            if edge["target"] not in best:
                continue
            weight, tail = best[edge["target"]]
            weight *= edge["strength"] * edge["confidence"]
            if weight <= 0:
                continue
            route = (edge["id"],) + tail
            previous = next_best.get(edge["source"])
            if previous is None or (-weight, len(route), route) < (-previous[0], len(previous[1]), previous[1]):
                next_best[edge["source"]] = (weight, route)
        if next_best == best:
            break
        best = next_best
    return best


def propose_institutional_leverage(
    signals: tuple[SignalEnvelope, ...], context: dict[str, Any],
) -> tuple[CandidateProposal, ...]:
    """Compile context['institutional_leverage'] and signal maps into next actions.

    Nodes carry measured gap estimates. Links run from controlling node to affected
    node. Interventions carry concrete capability requests, costs and (for frame or
    doctrine routes) evidence-linked audience/message artifacts. No model is called.
    """
    if PROPOSER_NAME not in context:
        return ()
    request = _validate("request", context[PROPOSER_NAME])
    tables, origins, ignored = _collect(signals, request)
    nodes, links = tables["nodes"], tables["links"]
    horizon = request.get("max_hops", 6)
    to_outcome = _paths_to(request["outcome_node"], links, horizon)
    bottlenecks = sorted(
        ({"node": node_id, "gap": nodes[node_id]["gap"],
          "outcome_weight": weight, "severity": nodes[node_id]["gap"] * weight,
          "outcome_path": list(path)}
         for node_id, (weight, path) in to_outcome.items() if nodes[node_id]["gap"] > 0),
        key=lambda item: (-item["severity"], item["node"]),
    )
    if not bottlenecks:
        raise ContractError("no evidenced bottleneck reaches the requested outcome")
    bottleneck = bottlenecks[0]
    remaining_hops = horizon - len(bottleneck["outcome_path"])
    to_bottleneck = _paths_to(bottleneck["node"], links, remaining_hops)
    routes = []
    for item in sorted(tables["interventions"].values(), key=lambda value: value["id"]):
        row = {"intervention_id": item["id"], "controlling_node": item["node"],
               "mechanism": item["mechanism"], "score": 0.0, "reason": "eligible"}
        if item["cost_usd"] > request["budget_usd"]:
            row["reason"] = "over_budget"
        elif item["node"] not in to_bottleneck:
            row["reason"] = "no_evidenced_path_to_bottleneck_within_horizon"
        else:
            weight, path = to_bottleneck[item["node"]]
            full_path = (*path, *bottleneck["outcome_path"])
            visited = [item["node"], *(links[edge_id]["target"] for edge_id in full_path)]
            if len(visited) != len(set(visited)):
                row["reason"] = "cyclic_route"
                routes.append(row)
                continue
            confidence = item["confidence"]
            for edge_id in full_path:
                confidence *= links[edge_id]["confidence"]
            benefit = item["effect"] * item["confidence"] * weight * bottleneck["severity"]
            burden = 1 + item["cost_usd"] / max(1.0, request["budget_usd"]) + item["effort_hours"] + item["delay_days"]
            row.update(path=list(full_path), confidence=confidence, expected_benefit=benefit,
                       harm=item["harm"], burden=burden, score=(benefit - item["harm"]) / burden)
            if row["score"] <= 0:
                row["reason"] = "no_positive_net_effect"
        routes.append(row)
    ranked = sorted((row for row in routes if row["reason"] == "eligible"),
                    key=lambda row: (-row["score"], row["intervention_id"]))
    if not ranked:
        reasons = ", ".join(f"{row['intervention_id']}:{row['reason']}" for row in routes)
        raise ContractError(f"no viable institutional route; retain current state; {reasons}")
    # Bind the whole considered map, including competing bottlenecks and routes.
    evidence = sorted({ref for records in tables.values() for record in records.values()
                       for ref in record["evidence_refs"]} |
                      {ref for item in tables["interventions"].values()
                       for claim in item.get("narrative", {}).get("claims", ()) for ref in claim["evidence_refs"]})
    source_ids = sorted({signal_id for ids in origins.values() for signal_id in ids})
    model_hash = digest({kind: sorted(records.values(), key=lambda value: value["id"])
                         for kind, records in tables.items()})
    candidates = []
    for rank, row in enumerate(ranked[:request.get("max_candidates", 3)], start=1):
        item = tables["interventions"][row["intervention_id"]]
        trace = {
            "model_hash": model_hash, "request": request, "rank": rank,
            "bottleneck": bottleneck, "bottlenecks_considered": bottlenecks,
            "route": row, "alternatives": routes,
            "baseline": {"intervention_id": "do_nothing", "score": 0.0},
            "scoring": "(effect * confidence * path_weight * bottleneck_severity - harm) / (1 + cost/budget_scale + effort_hours + delay_days)",
            "estimate_status": "input_estimates_not_verified_outcomes",
            "success_measure": item["success_measure"], "rollback": item["rollback"],
            "counterargument": item["counterargument"], "ignored_signals": ignored,
        }
        if "narrative" in item:
            trace["narrative"] = item["narrative"]
        action = item["action"]
        candidates.append(CandidateProposal.build(
            proposed_by=PROPOSER_NAME, objective=request["objective"],
            action_class=action["action_class"], requested_capability=action["requested_capability"],
            target=action["target"], consequence_class=action["consequence_class"],
            payload={**action["payload"], PROPOSER_NAME: trace},
            evidence_refs=evidence, confidence=row["confidence"],
            estimated_cost_usd=item["cost_usd"], expected_outcome=item["expected_outcome"],
            source_signal_ids=source_ids,
        ))
    return tuple(candidates)
