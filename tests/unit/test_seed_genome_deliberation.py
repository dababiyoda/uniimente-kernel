"""The 2026-10-13 convergence deliberation and ADR are consistent with each other
and with the evidence they cite."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DELIB = ROOT / "docs/collaboration/deliberation-polyintelligence-seed-genome-20261013.json"
ADR = ROOT / "docs/decisions/ADR-20261013-polyintelligence-seed-genome-convergence.md"


def test_deliberation_has_five_roles_two_passes_and_a_consistent_decision():
    d = json.loads(DELIB.read_text(encoding="utf-8"))
    roles = {r["role"].lower() for r in d["roles"]}
    assert {"founder-intent steward", "systems architect", "adversarial reviewer", "operator and maintainer",
            "evidence and welfare guardian"} <= roles
    # The roles recommend an experiment; merging it is the founder's decision, and chat text never records approval.
    assert d["decision"] == d["pass_2"]["recommendation"] == "NEEDS_FOUNDER_DECISION"
    assert {r["recommendation"] for r in d["roles"]} == {"EXPERIMENT"}
    assert d["authority_impact"]["approval_status"] != "approved"
    assert d["dissent"]["present"] is True and d["dissent"]["entries"]
    assert all(e["evidence_threshold"] and e["owner"] and e["review_trigger"] for e in d["dissent"]["entries"])
    assert d["authority_impact"]["changes_authority"] is False
    assert {"do_nothing_option", "alternatives", "kill_criteria", "rollback_plan", "migration_plan"} <= set(d)
    assert len(d["alternatives"]) >= 5 and all(a["revival_evidence"] for a in d["alternatives"])
    disadvantages = {x["id"] for x in d["pass_1"]["disadvantages"]}
    assert disadvantages == {x["disadvantage_id"] for x in d["pass_2"]["pass_1_disadvantage_dispositions"]}
    assert set(d["pass_1"]["comparisons"]) == {"baseline", "do_nothing", "simplest_viable_alternative",
                                               "strongest_competing_architecture", "reversible_experiment"}
    assert d["pass_2"]["final_design"] and d["pass_2"]["residual_risks"]
    for role in d["roles"]:
        assert role["evidence_refs"] and all((ROOT / ref).exists() for ref in role["evidence_refs"]), role["role"]


def test_adr_names_the_decision_and_evidence_references_exist():
    d = json.loads(DELIB.read_text(encoding="utf-8"))
    adr = ADR.read_text(encoding="utf-8")
    assert f"`{d['decision']}`" in adr and d["decision_id"] in adr
    for row in d["evidence"] + d["counterevidence"]:
        ref = row["reference"].split("#")[0]
        if "/" in ref and " " not in ref:
            assert (ROOT / ref).exists(), ref


def test_verdict_in_records_matches_the_frozen_results():
    held = json.loads((ROOT / "tests/evidence/cortex-seed-v0.1.6/heldout-results.json").read_text(encoding="utf-8"))
    d = json.loads(DELIB.read_text(encoding="utf-8"))
    verdict = held["exit"]["verdict"]
    assert any(verdict in row["finding"] for row in d["evidence"] + d["counterevidence"])
    assert verdict in ADR.read_text(encoding="utf-8")
    assert held["cortex_version"] == "0.1.6"
    assert held["arm_provenance"]["replayed_arms"] == ["always_llm", "llm_committee"]
