"""Reproducible whole-machine trace (directive 2026-10-21 section 8; INTENT-20261001-FULL-MACHINE-COMPLETION).

One consequence-inert CI-planning mission on natural repository data runs through the canonical body, signed
inbox, Gate, Competency Compiler, Capability Genesis, separate-process appraiser and settlement, with two real
SIGKILLs of the body process; a second mission of the same class is routed differently because of retained
evidence; the organ edge runs on the registered contracts and adapters only. The founder key is a per-test key.
"""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(any(importlib.util.find_spec(m) is None
                                    for m in ("scipy", "networkx", "ortools", "z3", "yaml")),
                                reason="cognition solvers or open-source engines absent")
sys.path.insert(0, str(ROOT / "scripts"))
import greg_whole_machine_trace as T  # noqa: E402

SCIPY = "acquired.cognition.mechanism:linear_assignment.scipy"


@pytest.fixture(scope="module")
def trace(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("whole-machine")
    out = T.run(tmp / "evidence", tmp / "state")
    assert (tmp / "evidence" / "trace.json").exists()
    return out


def step(trace, n):
    return next(s for s in trace["steps"] if s["demonstration"] == n)


def test_every_demonstration_is_shown_and_the_trace_chain_verifies(trace):
    assert [s["status"] for s in trace["steps"]] == ["DEMONSTRATED"] * 9, \
        [(s["name"], s["status"]) for s in trace["steps"]]
    assert T.verify_trace(trace) == (True, "chain intact")
    assert trace["ledger"]["chain_verified"] is True
    assert trace["labels"]["VEPMC"] == 0 and trace["labels"]["revenue"] is None
    tampered = json.loads(json.dumps(trace))
    tampered["steps"][2]["status"] = "DEMONSTRATED (edited)"
    assert T.verify_trace(tampered)[0] is False


def test_method_selection_and_answers_agree_with_independent_checks(trace):
    sel = step(trace, 2)["evidence"]["compile_receipt"]
    assert sel["method_selected"] == "cognition.optimization" and sel["state"] == "ANSWERED"
    assert {r["method"] for r in sel["methods_rejected"]} >= {"cognition.milp_optimize"}
    assert sel["authority_created"] is False
    answers = trace["answers"]
    assert answers["m1_critical_path"]["makespan"] == answers["m1_critical_path"]["independent"]["makespan"]
    assert answers["m1_assignment"]["total"] == answers["m1_assignment"]["independent"]["total"]


def test_genesis_resolves_the_deficit_and_the_original_mission_closes_after_the_founder_attach(trace):
    ev = step(trace, 3)["evidence"]
    assert ev["first_compile"]["state"] == "CAPABILITY_DEFICIT"
    assert [v["capability_id"] for v in ev["genesis_verified"]] == [SCIPY]
    assert ev["genesis_verified"][0]["failures"] == [] and ev["genesis_verified"][0]["isolation"]
    assert ev["attach"][0]["by"] == "founder command"
    assert ev["ledger_order_strictly_increasing"] is True
    assert ev["answer"]["method_selected"] == SCIPY


def test_sigkill_recovery_settles_exactly_once_with_no_duplicate_effect(trace):
    ev = step(trace, 5)["evidence"]
    assert ev["kill_1"]["after_restart_before_attach"]["genesis.verified"] == 1
    assert ev["kill_1"]["after_restart_before_attach"]["decision.requested"] == 1
    final = ev["final"]
    assert final["cognition.settled"] == 2 and final["mission.appraised"] == 1
    assert final["genesis.verified"] == 1 and final["decision.requested"] == 1
    assert final["body.booted"] == 3 and final["body.recovered"] == 2
    if ev["kill_2"]["hit"]:
        assert ev["kill_2"]["at_kill"]["cognition.settled"] == 0


def test_governance_and_retained_evidence_change_the_second_decision(trace):
    gate = step(trace, 4)["evidence"]
    assert gate["receipts_without_grant_and_witness"] == [] and gate["external_targets"] == []
    assert gate["grant_ceilings"] == ["read_only"] and gate["forged_attach_refused"]
    ev = step(trace, 7)["evidence"]
    assert ev["before_mission_1_first_compile"]["state"] == "CAPABILITY_DEFICIT"
    assert ev["control_fresh_body_first_compile"]["state"] == "CAPABILITY_DEFICIT"
    assert ev["after_mission_2_first_compile"]["state"] == "ANSWERED"
    assert ev["after_mission_2_first_compile"]["method_selected"] == SCIPY
    assert ev["mission_2_counts"]["deficit.opened"] == 0 and ev["mission_2_counts"]["decision.requested"] == 0
    assert ev["mission_2_appraisal"][-1]["verdict"] == "VERIFIED"


def test_organ_edge_and_dissent_are_preserved(trace):
    organs = step(trace, 8)["evidence"]
    assert "CONTRACT+ADAPTER ONLY" in organs["reality"]
    assert organs["packet_adapter"]["unresolved"] and organs["packet_adapter"]["information_lost"]
    assert all(v.startswith("refused") for v in organs["transport"]["hostile_controls"].values())
    assert organs["assessment_adapter"]["execution_authority"] is False
    dissent = step(trace, 9)["evidence"]
    assert dissent["critical_path_compiler_dissent"]
    assert dissent["abstention"]["compile"]["state"] == "HUMAN_JUDGMENT_REQUIRED"
    assert dissent["abstention"]["counts"]["mission.achieved"] == 0
