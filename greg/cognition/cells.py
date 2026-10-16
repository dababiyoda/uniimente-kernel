"""Bounded competency cells are projections of the existing body, never another OS."""
from .contracts import digest
from .settlement import measured_outcomes


def cells(journal, registry):
    grouped = {}
    for outcome in measured_outcomes(journal):
        key = (outcome["method"], outcome["method_version"], outcome["geometry_key"])
        grouped.setdefault(key, []).append(outcome)
    result = []
    for (method, version, geometry), observations in sorted(grouped.items()):
        manifest = registry.manifests.get(method)
        if manifest is None or not manifest.cognitive_profile:
            continue
        active, reason = registry.usable(method)
        successes = sum(o["correct"] for o in observations)
        failed = len(observations) - successes
        result.append({
            "cell_id": digest({"method": method, "version": version, "geometry": geometry}),
            "problem_geometry": geometry,
            "observations": [o["observation_event"] for o in observations[-32:]],
            "local_state": {"observed": len(observations), "correct": successes, "failed": failed},
            "target_state": "satisfy the founder's mission predicate within the supplied problem model",
            "allowed_transitions": ["sense", "bounded_compute", "abstain", "report_deficit", "settle_appraised_outcome"],
            "reasoner": {"capability_id": method, "version": version},
            "memory_scope": "last 32 observation refs projected from the canonical journal; no second store",
            "resource_budget": {"money_usd": 0, "latency_seconds": 30, "memory_bytes": 2 * 1024**3},
            "confidence": {"local_predicate_rate": successes / len(observations), "world_confidence": None},
            "abstention_conditions": manifest.cognitive_profile["abstention_conditions"],
            "cognitive_light_cone": "intersection of the existing signed mission light cone and capability manifest",
            "authority_ceiling": "read_only",
            "health_state": "DETACHED" if not active else "DEGRADED" if failed else "AVAILABLE",
            "failure_signatures": (["local predicate failed"] if failed else []) + ([reason] if not active else []),
            "escalation_boundary": "existing mission deficit, authority request or founder review; never self-enlarge",
            "feedback_rule": "replay appraised outcomes to update local predicate counts and routing rank",
            "authority_created": False,
            "limits": "bounded computation cell; not autonomous persistent goal pursuit, general homeostasis or external calibration",
        })
    return result
