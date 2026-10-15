"""Directive 2026-10-07 sections 25-26: no frontier capability disappears because it cannot be completed now.

Section 31 item 16: "All speculative descendants remain preserved in the Backcast GPS horizon." Section 7 classifies
the developmental horizon in the founder's own words; every descendant it names keeps a backcast with that class,
quoted verbatim, and a BUILDABLE_NOW label must say why it describes the destination rather than the precursor.
"""
import collections
import json
from pathlib import Path
import re

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


WORDS = ("no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")
ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth")


def _natural_recipe_families() -> dict:
    """P6 family -> lifted?, for every family a frozen run's own limits call real data (not constructed)."""
    index = json.loads((ROOT / "docs/evidence/greg-mind-evidence-index.json").read_text())
    out = {}
    for row in index["recipes"].values():
        for verdict in [row, *row.get("history", [])]:
            limits = json.loads((ROOT / verdict["evidence"].partition("#")[0]).read_text())["limits"]
            named = [x for x in limits if verdict["family"] in re.findall(r"\bF\d+R?\b", x)]
            text = " ".join(named or [x for x in limits if not re.findall(r"\bF\d+R?\b", x)])
            if re.search(r"\breal\b", text) and "constructed" not in text:
                out[verdict["family"]] = verdict["status"] == "VPL_LIFT"
    return out


def test_mind_nodes_record_measured_reality_not_plans():
    cortex = path.load()["subordinate_workstreams"]["polyintelligence_cortex"]
    nodes = {n["id"]: n for n in cortex["nodes"]}
    assert nodes["P8"]["status"] == "active" and nodes["P8"]["exit_met"] is False
    for ref in nodes["P8"]["implementation_refs"] + nodes["P6"]["implementation_refs"]:
        assert (ROOT / ref).exists(), ref


def test_the_p6_node_counts_the_natural_families_the_evidence_index_records():
    natural = _natural_recipe_families()
    lifted = sorted(f for f, lift in natural.items() if lift)
    nodes = {n["id"]: n for n in path.load()["subordinate_workstreams"]["polyintelligence_cortex"]["nodes"]}
    exit_met = nodes["P6"]["exit_met"]
    count = f"{WORDS[len(lifted)]} of {WORDS[len(natural)]} natural families"
    assert natural and count in exit_met, (natural, exit_met)
    for family in natural:
        assert re.search(rf"\b{family}\b", exit_met), family


def test_the_p8_node_records_every_frozen_cycle():
    cycles = sorted(ROOT.glob("docs/evidence/greg-protected-evolution/*/cycle-*.json"))
    decisions = [json.loads(c.read_text())["decision"] for c in cycles]
    p8 = {n["id"]: n for n in path.load()["subordinate_workstreams"]["polyintelligence_cortex"]["nodes"]}["P8"]
    assert cycles and f"{WORDS[len(cycles)]} frozen cycles" in p8["reality"], p8["reality"]
    for number, decision in enumerate(decisions, 1):
        assert re.search(rf"cycle {number} \([^)]*\) {decision}", p8["reality"]), (number, decision)
    for ordinal in ORDINALS[:len(cycles)]:
        assert f"a {ordinal} cycle" not in p8["smallest_next_experiment"], "the next experiment is already done"
    if all(d == "REJECT" for d in decisions):
        assert p8["exit_met"] is False and "never kept an improvement" in p8["reality"]


def test_the_p8_next_experiment_states_how_far_the_latest_search_moved_p_restart():
    """Found by the 2026-10-15 independent review and its fix verifier: greg/path.json first said cycle 4's search did
    not move p_restart, then planned a cycle "whose closed space can reach the measured headroom", as if cycle 4's
    space could not. The record holds three configurations with p_restart above 0, the largest 0.339 of the 1.0 the
    space allows: the search did not reach the headroom, which says nothing about what the space can reach."""
    from greg.cognition.genomes.developmental import CR_CONFIG_SPACE
    record = json.loads(sorted(ROOT.glob("docs/evidence/greg-protected-evolution/*/cycle-cr-*.json"))[-1].read_text())
    tried = sorted(e["config"]["p_restart"] for e in record["search"]["lineage"] if e["config"]["p_restart"] > 0)
    upper = CR_CONFIG_SPACE["p_restart"][1][1]
    p8 = {n["id"]: n for n in path.load()["subordinate_workstreams"]["polyintelligence_cortex"]["nodes"]}["P8"]
    plan = p8["smallest_next_experiment"]
    assert f"the {WORDS[len(tried)]} searched configurations with p_restart above 0" in plan, plan
    assert f"at most {max(tried)} of the allowed {upper}" in plan, plan
    if max(tried) < upper:
        assert f"nothing above {max(tried)} was tried" in plan and "closed space can reach" not in plan, plan


def test_the_cortex_summary_and_the_older_p5_node_state_the_latest_frozen_totals():
    """Found by the 2026-10-15 independent review: the polyintelligence workstream's ``current`` summary still
    counted three P8 cycles after cycle 4 was frozen, and the older P5 node still gave admission v1's 20 admitted of
    31 after v3. Both state the latest frozen totals, read here from the cycle records and the evidence index."""
    data = path.load()
    current = data["subordinate_workstreams"]["polyintelligence_cortex"]["current"]
    cycles = sorted(ROOT.glob("docs/evidence/greg-protected-evolution/*/cycle-*.json"))
    decisions = {json.loads(c.read_text())["decision"] for c in cycles}
    assert cycles and f"P8 cycles 1-{len(cycles)}" in current, current
    if len(decisions) == 1:
        assert f"P8 cycles 1-{len(cycles)}: {next(iter(decisions))}" in current, current
    genomes = json.loads((ROOT / "docs/evidence/greg-mind-evidence-index.json").read_text())["genomes"]
    counts = collections.Counter(g["status"] for g in genomes.values())
    admitted = counts["DEFAULT_FOR_GEOMETRY"] + counts["NICHE_CAPABILITY"]
    assert f"{admitted} admitted of {len(genomes)}" in current, current
    [ws] = [w for w in data["workstreams"] if w["id"] == "cognition_cortex"]
    p5 = {n["id"]: n for n in ws["nodes"]}["P5"]
    assert f"all {len(genomes)} executable genomes" in p5["status"]
    # the latest totals only: the node keeps admission v1's counts before them as lineage, so a count v1 shares
    # (3 COMPOSITION_ONLY) would otherwise be found in v1's text however the latest clause states it
    latest_clause = p5["status"].split(f"all {len(genomes)} executable genomes", 1)[1]
    assert f"({admitted} admitted)" in latest_clause, latest_clause
    stated = {status: int(n) for n, status in re.findall(r"\b(\d+) ([A-Z][A-Z_]+)\b", latest_clause)}
    assert stated and all(stated.get(s, 0) == counts[s] for s in set(stated) | set(counts)), (stated, counts)
    latest = sorted(ROOT.glob("docs/evidence/greg-genome-admission/*/results.json"))[-1]
    assert str(latest.relative_to(ROOT)) in p5["evidence_refs"], p5["evidence_refs"]


# The frozen runs each Mind node is measured by (a P8 cycle record is not an index source).
FROZEN_RUNS = {"P4": "docs/evidence/greg-learned-routing/", "P6": "docs/evidence/greg-composition-lift/",
               "P8": "docs/evidence/greg-protected-evolution/"}


def test_the_older_cognition_cortex_nodes_point_at_the_measured_nodes_and_their_frozen_evidence():
    """The cognition_cortex P0-P13 backcast is lineage (developmental inheritance: reroute, never delete). Where the
    polyintelligence_cortex node of the same id records measured reality, the older node may not remain a bare
    placeholder: it names that node as its current record, cites every frozen run measuring it, and states the
    frozen outcome (the natural-family count, every P8 cycle decision, the P4 verdict)."""
    data = path.load()
    [ws] = [w for w in data["workstreams"] if w["id"] == "cognition_cortex"]
    older = {n["id"]: n for n in ws["nodes"]}
    current = {n["id"]: n for n in data["subordinate_workstreams"]["polyintelligence_cortex"]["nodes"]}
    measured = sorted(k for k, n in current.items() if n.get("reality"))
    assert set(FROZEN_RUNS) <= set(measured)
    sources = [s["path"] for s in json.loads((ROOT / "docs/evidence/greg-mind-evidence-index.json").read_text())
               ["sources"]]
    cycles = sorted(ROOT.glob("docs/evidence/greg-protected-evolution/*/cycle-*.json"))
    for key in measured:
        node, live = older[key], current[key]
        assert node.get("current_record") == {"workstream": "polyintelligence_cortex", "node": key}, key
        cited = set(re.findall(r"docs/evidence/[\w./-]+\.(?:md|json)",
                               json.dumps([live.get("implementation_refs", []), live.get("evidence", "")])))
        if key in FROZEN_RUNS:
            cited |= {s for s in sources if s.startswith(FROZEN_RUNS[key])}
            assert node["status"].split(";")[0].strip() != "HORIZON", key
        if key == "P8":
            cited |= {str(c.relative_to(ROOT)) for c in cycles}
        refs = node.get("evidence_refs") or []
        assert cited <= set(refs), (key, sorted(cited - set(refs)))
        assert all((ROOT / ref).exists() for ref in refs), key
    natural = _natural_recipe_families()
    p6 = older["P6"]["status"]
    assert f"{WORDS[sum(natural.values())]} of {WORDS[len(natural)]} natural families" in p6, p6
    assert all(re.search(rf"\b{family}\b", p6) for family in natural), p6
    p8 = older["P8"]["status"]
    decisions = [json.loads(c.read_text())["decision"] for c in cycles]
    assert f"{WORDS[len(cycles)]} frozen cycles" in p8, p8
    for number, decision in enumerate(decisions, 1):
        assert re.search(rf"cycle {number} \([^)]*\) {decision}", p8), (number, decision)
    verdict = json.loads((ROOT / "docs/evidence/greg-mind-evidence-index.json").read_text())["routing"][
        "conditional_competence"]["verdict"]
    assert verdict in older["P4"]["status"] and (verdict != "REGRESSION" or "DEMOTED" in older["P4"]["status"])


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
