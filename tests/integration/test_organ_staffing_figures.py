"""The Mind's staffing figures change WealthMachine's assessment, on the real organ path.

Step 9 of the fifteen-step mission carries GREG's certified staffing answer to WealthMachine as packet evidence. Until
WealthMachineIntelligence #45 WealthMachine only counted that evidence: two packets with the same number of evidence
items, one reporting every unit staffed and one a shortage, came back with the same reasons and the same first
validation step (WMI 7a45d223; fail-before evidence in docs/evidence/organ-staffing-figures-2026-10-28/).

Here the Kernel's own certified answers (``certify_staffing`` over a ``certify_max_flow`` certificate, the chain the
constructed ``assignment.staffing`` capability runs) for a fully staffed problem (8 of 8) and a short one (4 of 8)
travel the real organ exchange: DALEOBANKS refines the seed in its own interpreter and signs the packet, WealthMachine
verifies it, assesses and signs, the Kernel verifies both under per-organ keys, and a second WealthMachine process
reproduces the assessment. Asserted:

- the two packets carry the same number of evidence items and differ only in the report (and the ids derived from it),
  and the engine's scores are identical, so neither evidence count nor an unrelated score explains the difference;
- the shortage changes the assessment's reasons, its evidence requests (``validation_plan``) and its validation
  priority (``recommended_next_action``), and caps the verdict below ``go``;
- every reading is labelled an unverified report whose arithmetic agrees, never a verification of demand, capacity,
  optimality or the world, and ``requires_human_approval`` stays true with no authority created;
- truncated, internally inconsistent, contradictory, replayed and self-promoting reports keep explicit uncertainty.

Gated as test_greg_organs.py's live exchange: the four UNIIMENTE_* variables name the organ checkouts (skipped with the
reason, failed under UNIIMENTE_REQUIRE_ORGANS=1, which CI job 8 sets). Reality: LABORATORY on the host that runs it;
synthetic staffing problems, nothing sent, published, spent or decided.
"""
from __future__ import annotations

import json

import pytest

nx = pytest.importorskip("networkx")

from greg import organs  # noqa: E402
from greg.cognition import network  # noqa: E402
from greg.recombine import certify_staffing, decode_staffing, encode_staffing, normalize_staffing  # noqa: E402
from tests.unit.test_greg_organs import SEED, ctx, journal, live_organs, organ_roots  # noqa: E402,F401

# The fifteen-step mission's seed template (tests/integration/test_one_mission_fifteen_steps.py), so the report reaches
# DALEOBANKS in exactly the producer format the whole-machine mission uses.
LABEL = "Evidence from GREG's certified staffing plan"
SEED_TEMPLATE = SEED + f" {LABEL} for the docks and the line: {{value}}"

FULL = {"workers": [{"id": "Ana", "capacity": 4, "skills": ["forklift"]},
                    {"id": "Ben", "capacity": 4, "skills": ["packing"]}],
        "orders": [{"id": "Dock", "demand": 4, "skill": "forklift"},
                   {"id": "Line", "demand": 4, "skill": "packing"}]}
SHORT = {"workers": [{"id": "Ana", "capacity": 2, "skills": ["forklift"]},
                     {"id": "Ben", "capacity": 2, "skills": ["packing"]}],
         "orders": [{"id": "Dock", "demand": 4, "skill": "forklift"},
                    {"id": "Line", "demand": 4, "skill": "packing"}]}


def certified(problem: dict) -> dict:
    """GREG's certified staffing answer: the networkx max-flow runner's claim, certified by the Kernel's own code."""
    p = normalize_staffing(problem)
    req = network.normalize_max_flow(encode_staffing(p))
    g = nx.DiGraph()
    g.add_nodes_from(req["nodes"])
    for u, v, c in req["arcs"]:
        g.add_edge(u, v, capacity=c)
    value, flow = nx.maximum_flow(g, req["source"], req["sink"], capacity="capacity")
    claim = {"value": value, "flows": [[u, v, f] for u, row in flow.items() for v, f in row.items() if f]}
    return certify_staffing(p, decode_staffing(p, network.certify_max_flow(req, claim)))


def seed_for(*answers) -> str:
    """The seed a mission binds: one report sentence per answer, rendered as the mission's bind renders JSON."""
    seed = SEED + "".join(f" {LABEL} for the docks and the line: {json.dumps(a)}" for a in answers)
    assert len(seed) <= organs.MAX_SEED, len(seed)
    return seed


def run(tmp_path, journal, params, seed, mission_id):  # noqa: F811
    """One real exchange; the packet and the assessment as the Kernel retained them (verified, untrusted content)."""
    out = organs.exchange({**params, "seed": seed},
                          ctx(tmp_path, journal, roots=organ_roots(params), mission_id=mission_id))
    retained = {e.payload["content_sha256"]: e.payload for e in journal.replay("external.ingested")}
    body = {}
    for o in journal.replay("organ.observed"):
        if o.payload["mission_id"] == mission_id:
            item = retained[o.payload["content_sha256"]]
            assert not item["truncated"], f"{o.payload['organ']}'s message was cut at retention"
            body[o.payload["organ"]] = json.loads(item["content"])
    return out, body["daleobanks"], body["wealthmachine"]


def staffing_reasons(assessment: dict) -> list[str]:
    return [r for r in assessment["reasons"] if "staffing" in r.lower()]


def test_a_shortage_changes_reasons_evidence_requests_and_priority_with_nothing_else_changed(tmp_path, journal):
    params = live_organs()
    full, short = certified(FULL), certified(SHORT)
    assert (full["staffed"], full["total_demand"], full["shortage"]) == (8, 8, 0)
    assert (short["staffed"], short["total_demand"], short["shortage"]) == (4, 8, 4)

    out_f, packet_f, wmi_f = run(tmp_path / "f", journal, params, seed_for(full), "m:staffing-full")
    out_s, packet_s, wmi_s = run(tmp_path / "s", journal, params, seed_for(short), "m:staffing-short")

    for out, wmi in ((out_f, wmi_f), (out_s, wmi_s)):
        assert out["appraisal_verdict"] == "REPRODUCED" and out["transport_verified"] is True
        assert out["sender_identity_isolated"] is True
        assert out["authority_created"] is False and out["external_effects"] is None
        assert wmi["requires_human_approval"] is True and out["assessment"]["requires_human_approval"] is True

    # The real producer carried each certified answer whole, as one evidence item, in packets of equal size.
    for packet, answer in ((packet_f, full), (packet_s, short)):
        reports = [e for e in packet["evidence"] if e.startswith(LABEL)]
        assert len(reports) == 1 and json.loads(reports[0].split(": ", 1)[1]) == answer
    assert len(packet_f["evidence"]) == len(packet_s["evidence"]) == 2

    # Nothing but the report differs, and the engine scores the two packets identically.
    def without_report(packet):
        return {k: v for k, v in packet.items() if k not in ("id", "evidence", "created_at", "source_ref")}
    assert without_report(packet_f) == without_report(packet_s), "the packets differ beyond the report"
    for field in ("opportunity_score", "market_alignment", "risk_level", "legal_readiness", "expected_roi",
                  "pricing_hypothesis"):
        assert wmi_f[field] == wmi_s[field], field

    # The figures are read: different reasons, different evidence requests, a different first step.
    [reason_f], [reason_s] = staffing_reasons(wmi_f), staffing_reasons(wmi_s)
    assert "staffed=8, total_demand=8, shortage=0" in reason_f
    assert "staffed=4, total_demand=8, shortage=4" in reason_s and '"Dock": 2' in reason_s and '"Line": 2' in reason_s
    other_f = [r for r in wmi_f["reasons"] if r not in (reason_f,)]
    other_s = [r for r in wmi_s["reasons"] if r not in (reason_s,) and "shortfall" not in r]
    assert other_f == other_s, "a reason other than the staffing reading differs"
    assert wmi_f["validation_plan"][0] != wmi_s["validation_plan"][0]
    assert wmi_f["recommended_next_action"] == wmi_f["validation_plan"][0]
    assert wmi_s["recommended_next_action"] == wmi_s["validation_plan"][0]
    assert "8/8 units" in wmi_f["recommended_next_action"]
    assert "shortage of 4 units" in wmi_s["recommended_next_action"]
    assert wmi_f["validation_plan"][1:] == wmi_s["validation_plan"][1:], "evidence requests beyond staffing changed"
    # GREG sees the changed priority in the exchange's own receipt, not only in the retained organ body.
    assert out_s["assessment"]["recommended_next_action"] == wmi_s["recommended_next_action"]

    # A shortage can only lower the verdict; a complete report never raises one.
    assert wmi_s["go_no_go"] != "go"
    if wmi_f["go_no_go"] == "go":
        assert wmi_s["go_no_go"] == "needs_more_evidence"

    # Arithmetic agreement is never promoted to verification of demand, capacity, optimality or the world.
    for reason in (reason_f, reason_s):
        assert "unverified report" in reason and "not verified" in reason
    for wmi in (wmi_f, wmi_s):
        text = json.dumps(wmi).lower()
        assert "verified optimal" not in text and "certified plan verified" not in text


HOSTILE = {
    # the report cut short: what a size limit or a lossy relay leaves
    "truncated": lambda full, short: SEED + f" {LABEL} for the docks and the line: " + json.dumps(full)[:-25],
    # figures that do not add up: staffed 8 of 8 with a shortage of 1
    "inconsistent": lambda full, short: seed_for({**full, "shortage": 1}),
    # two reports for the same request that disagree
    "contradictory": lambda full, short: seed_for(full, short),
    # the same report delivered twice in one thought
    "replayed": lambda full, short: seed_for(full, full),
    # a report that promotes itself
    "self-promoting": lambda full, short: seed_for({**short, "verified": True, "independently_accepted": True}),
}


@pytest.mark.parametrize("case", sorted(HOSTILE))
def test_hostile_reports_keep_explicit_uncertainty(tmp_path, journal, case):
    params = live_organs()
    full, short = certified(FULL), certified(SHORT)
    out, packet, wmi = run(tmp_path, journal, params, HOSTILE[case](full, short), f"m:staffing-{case}")
    assert out["appraisal_verdict"] == "REPRODUCED" and out["authority_created"] is False
    assert wmi["requires_human_approval"] is True
    readings = staffing_reasons(wmi)
    assert readings and all("unverified" in r or "differ" in r or "shortfall" in r for r in readings), readings
    first = wmi["recommended_next_action"]
    if case == "replayed":
        # DALEOBANKS keeps one copy of a repeated statement: no second evidence item, no second reading.
        assert sum(e.startswith(LABEL) for e in packet["evidence"]) == 1
        assert len(packet["evidence"]) == 2 and "8/8 units" in first
        return
    assert wmi["go_no_go"] != "go", (case, wmi["go_no_go"], readings)
    if case == "truncated":
        assert any("malformed or incomplete" in r for r in readings) and first.startswith("Resolve staffing evidence")
    elif case == "inconsistent":
        assert any("does not equal total_demand" in r for r in readings) and first.startswith("Resolve staffing")
    elif case == "contradictory":
        assert any("staffing reports differ" in r for r in readings) and first.startswith("Reconcile differing staffing")
    elif case == "self-promoting":
        assert "shortage of 4 units" in first and all("unverified report" in r for r in readings[:1])
