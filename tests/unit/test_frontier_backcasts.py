"""Directive 2026-10-07 sections 25-26: no frontier capability disappears because it cannot be completed now.

Section 31 item 16: "All speculative descendants remain preserved in the Backcast GPS horizon." Section 7 classifies
the developmental horizon in the founder's own words; every descendant it names keeps a backcast with that class,
quoted verbatim, and a BUILDABLE_NOW label must say why it describes the destination rather than the precursor.
"""
import json
from pathlib import Path

import pytest

from greg import path
from greg.cognition.catalog import FAMILIES

ROOT = Path(__file__).resolve().parents[2]
NAMED = {"generalized_morphogenetic_repair", "automatic_invention_of_intelligence_families",
         "substrate_adaptive_cognition", "reliable_multi_body_agency", "advanced_robotic_embodiment",
         "persistent_spatial_ecology", "large_scale_human_machine_coordination", "jarvis_environmental_awareness",
         "self_financed_research_infrastructure"}
DIRECTIVE = ROOT / "docs/intent/sources/POLYINTELLIGENCE-MIND-CONTINUATION-DIRECTIVE-2026-10-07-source.md"
# Section 7's horizon headers in the founder's words -> the section 25 buildability vocabulary.
HEADERS = {"Present-day buildable:": "BUILDABLE_NOW", "Experimental:": "EXPERIMENTAL_NOW",
           "Frontier:": "FRONTIER_RESEARCH", "Science-fiction descendant:": "SCIENCE_FICTION_DESCENDANT"}
# Every section 7 descendant beyond present-day buildable -> the backcast that preserves it.
DESCENDANTS = {
    "* robust unscripted organ formation;": "robust_unscripted_organ_formation",
    "* generalized repair across many functional domains;": "generalized_morphogenetic_repair",
    "* cross-substrate developmental compilation.": "cross_substrate_developmental_compilation",
    "* reliable open-ended generation of entirely new cognitive organizations.":
        "open_ended_cognitive_organization_generation",
    "* extremely general substrate-independent developmental intelligence with the reliability, generality, "
    "embodiment flexibility, and autonomy implied by the strongest Levin-inspired vision.":
        "substrate_independent_developmental_intelligence",
}


def _section_7() -> tuple[list[str], dict]:
    """The verbatim lines of directive section 7, and each horizon bullet's class from the header above it."""
    lines = DIRECTIVE.read_text(encoding="utf-8").splitlines()
    body = lines[lines.index("7. LAYER 4: DEVELOPMENTAL / MORPHOGENETIC INTELLIGENCE"):
                 lines.index("8. LAYER 5: META-INTELLIGENCE / INSTITUTIONAL COLLECTIVE COGNITION")]
    classes, current = {}, None
    for line in body:
        if line in HEADERS:
            current = HEADERS[line]
        elif line.startswith("* ") and current:
            classes[line] = current
        elif line.strip():
            current = None
    return body, classes


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


def test_every_section_7_descendant_stays_on_the_horizon_with_the_founders_class():
    body, classes = _section_7()
    beyond_now = {line for line, cls in classes.items() if cls != "BUILDABLE_NOW"}
    assert beyond_now == set(DESCENDANTS), "a section 7 descendant has no backcast (or the source changed)"
    items = {b["id"]: b for b in path.load()["frontier_backcasts"]}
    for line, record_id in DESCENDANTS.items():
        item = items[record_id]
        assert item["buildability_status"] == classes[line], (record_id, classes[line])
        quote = item.get("source_quote")
        if quote is not None:                       # quoted records quote the source verbatim, header included
            assert line in quote and all(q in body for q in quote), record_id
            assert any(HEADERS.get(q) == classes[line] for q in quote), record_id
    descendant = items["substrate_independent_developmental_intelligence"]
    assert descendant["node"] == "N2" and "Do not falsely claim it exists." in descendant["source_quote"]


def test_a_buildable_now_label_states_why_it_describes_the_destination():
    for item in path.load()["frontier_backcasts"]:
        if item["buildability_status"] == "BUILDABLE_NOW":
            review = item.get("buildability_review") or {}
            assert review.get("finding") and review.get("source_check") and "label_changed" in review, item["id"]
        for ref in item.get("precursor_mechanisms", []):
            assert ref.startswith("cognition.") and ref.removeprefix("cognition.") in FAMILIES, (item["id"], ref)
