"""Directive 2026-10-07 sections 25-26: no frontier capability disappears because it cannot be completed now."""
import json
from pathlib import Path

import pytest

from greg import path

ROOT = Path(__file__).resolve().parents[2]
NAMED = {"generalized_morphogenetic_repair", "automatic_invention_of_intelligence_families",
         "substrate_adaptive_cognition", "reliable_multi_body_agency", "advanced_robotic_embodiment",
         "persistent_spatial_ecology", "large_scale_human_machine_coordination", "jarvis_environmental_awareness",
         "self_financed_research_infrastructure"}


def test_every_named_frontier_keeps_a_complete_backcast_with_real_precursors():
    data = path.load()
    items = {b["id"]: b for b in data["frontier_backcasts"]}
    assert NAMED <= set(items)
    for item in items.values():
        assert all(item[f] for f in path.BACKCAST_FIELDS)
        assert item["buildability_status"] in path.BUILDABILITY
        for ref in item["current_precursor"]:
            assert (ROOT / ref).exists(), (item["id"], ref)


@pytest.mark.parametrize("change,needle", [
    (lambda b: b.pop("risk"), "missing"),
    (lambda b: b.__setitem__("buildability_status", "DONE"), "unknown buildability"),
    (lambda b: b.__setitem__("horizon", "nowhere"), "unknown node or horizon"),
])
def test_the_validator_refuses_a_thinned_or_relabelled_frontier(change, needle):
    data = json.loads((ROOT / "greg/path.json").read_text())
    change(data["frontier_backcasts"][0])
    with pytest.raises(path.PathError, match=needle):
        path.validate(data)


def test_mind_nodes_record_measured_reality_not_plans():
    cortex = path.load()["subordinate_workstreams"]["polyintelligence_cortex"]
    nodes = {n["id"]: n for n in cortex["nodes"]}
    assert nodes["P8"]["status"] == "active" and nodes["P8"]["exit_met"] is False
    for ref in nodes["P8"]["implementation_refs"] + nodes["P6"]["implementation_refs"]:
        assert (ROOT / ref).exists(), ref
