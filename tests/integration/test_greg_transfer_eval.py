"""The transfer test's harness and its frozen verdict rules (scripts/greg_transfer_eval.py).

The pre-registered run itself is recorded in docs/evidence/greg-transfer/2026-10-28/; here:
- the verdict rules decide exactly as declared, on synthetic rows (no bodies): a worse or wrong experienced arm is
  NEGATIVE_TRANSFER, a wrong control is INVALID, a transfer on the unrelated tier makes the experiment INVALID;
- the contamination check finds a hidden instance equal to one Genesis qualified on, and an empty check is invalid;
- the committed results re-derive: their verdicts are summarise() of their own raw rows, and every hidden instance
  is the declared generator's output, so neither can have been edited by hand;
- one live cross-family pair on real bodies shows the harness measures what it claims (a few seconds per body).
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import greg_transfer_eval as T  # noqa: E402

EVIDENCE = ROOT / "docs" / "evidence" / "greg-transfer" / "2026-10-28"


def phase(work, *, correct_state="ACHIEVED", seeds=(), authority=False, self_attached=0):
    return {"work": work, "attach_asks": 0, "qualifications": 0, "seconds": 1.0, "state": correct_state,
            "appraisal": "VERIFIED", "qualification_seeds": list(seeds), "authority_created": authority,
            "self_attached": self_attached}


def row(tier, i, e_work, c_work, *, e_ok=True, c_ok=True, problem=None, seeds=()):
    return {"tier": tier, "i": i, "problem": problem or T.instances("greg-transfer-unit", {tier: i + 1})[tier][i],
            "experienced": {"construction": phase(6, seeds=seeds), "task": phase(e_work)},
            "control": {"task": phase(c_work, seeds=seeds)}, "experienced_correct": e_ok, "control_correct": c_ok}


SEEDS = [("reduction:staffing-via-maxflow", 12345)]


def raw(rows):
    return {"tasks": rows}


def verdicts(rows):
    return {t: v["verdict"] for t, v in T.summarise(raw(rows))["tiers"].items()}


def test_the_rules_decide_as_declared():
    ok = [row("same_family", i, 0, 6, seeds=SEEDS) for i in range(10)] + \
         [row("unrelated", i, 6, 6, seeds=SEEDS) for i in range(10)]
    s = T.summarise(raw(ok))
    assert verdicts(ok) == {"same_family": "TRANSFER", "unrelated": "NO_TRANSFER"} and s["experiment"] == "VALID"
    worse = copy.deepcopy(ok)
    worse[3]["experienced"]["task"]["work"] = 7
    assert verdicts(worse)["same_family"] == "NEGATIVE_TRANSFER"
    wrong = copy.deepcopy(ok)
    wrong[0]["experienced_correct"] = False
    assert verdicts(wrong)["same_family"] == "NEGATIVE_TRANSFER"
    broken = copy.deepcopy(ok)
    broken[1]["control_correct"] = False
    assert verdicts(broken)["same_family"] == "INVALID"
    mixed = copy.deepcopy(ok)
    for r in mixed[:2]:
        r["experienced"]["task"]["work"] = 6
    assert verdicts(mixed)["same_family"] == "MIXED"           # 8 of 10 better is short of ceil(0.9 * 10) = 9
    leak = copy.deepcopy(ok)
    leak[12]["experienced"]["task"]["work"] = 3                 # a transfer on the negative control
    assert T.summarise(raw(leak))["experiment"] == "INVALID"


def test_an_authority_breach_invalidates_the_experiment():
    rows = [row("unrelated", 0, 6, 6, seeds=SEEDS)]
    rows[0]["experienced"]["task"]["self_attached"] = 1
    assert T.summarise(raw(rows))["experiment"] == "INVALID"


def test_the_contamination_check_finds_a_qualified_instance_and_refuses_to_be_empty():
    from greg.recombine import REDUCTIONS
    reduction = next(r for r in REDUCTIONS.values() if r.reduction_id == "staffing-via-maxflow")
    leaked = reduction.oracle(12345)[-1]["input"]               # an instance Genesis qualified on
    rows = [row("same_family", 0, 0, 6, problem=leaked, seeds=SEEDS), row("unrelated", 0, 6, 6, seeds=SEEDS)]
    s = T.summarise(raw(rows))
    assert s["contaminated"] == ["same_family[0]"] and s["experiment"] == "INVALID"
    unseeded = [row("same_family", 0, 0, 6), row("unrelated", 0, 6, 6)]
    s = T.summarise(raw(unseeded))
    assert s["qualification_instances_checked"] == 0 and s["experiment"] == "INVALID"


def test_hidden_instances_are_valid_problems_of_their_family():
    from greg import recombine as r
    hidden = T.instances("greg-transfer-unit", {"same_family": 5, "cross_family": 5, "unrelated": 5})
    for problem in hidden["same_family"]:
        r.normalize_staffing(problem)
    for problem in hidden["cross_family"]:
        r.normalize_matching(problem)
    for problem in hidden["unrelated"]:
        r.normalize_crash(problem)
    assert hidden["replay"] == [T.CONSTRUCTION]


def test_the_construction_problem_is_the_fifteen_step_missions():
    from tests.integration.test_greg_mind_constructs_capability import STAFFING
    assert T.CONSTRUCTION == STAFFING


@pytest.mark.skipif(not (EVIDENCE / "results.json").exists(), reason="the pre-registered run is not recorded yet")
def test_the_recorded_run_re_derives_from_its_own_rows():
    result = json.loads((EVIDENCE / "results.json").read_text())
    # the run's own harness: a changed script needs a new declaration and namespace, not this record
    script = (ROOT / "scripts" / "greg_transfer_eval.py").read_bytes()
    assert result["raw"]["script_sha256"] == hashlib.sha256(script).hexdigest(), "the recorded run's harness changed"
    assert T.summarise(result["raw"]) == result["summary"], "a verdict was edited after the run"
    assert result["raw"]["namespace"] == T.NAMESPACE and result["raw"]["n"] == T.N
    hidden = T.instances()
    want_construction = T.expected("replay", T.CONSTRUCTION)
    for r in result["raw"]["tasks"]:
        assert r["problem"] == hidden[r["tier"]][r["i"]], "a hidden instance is not the declared generator's"
        assert r["expected"] == T.expected(r["tier"], r["problem"])
        # the correctness flags the verdicts rest on, recomputed from the recorded answers
        for side in ("experienced", "control"):
            task = r[side]["task"]
            assert r[f"{side}_correct"] == (task["state"] == "ACHIEVED" and T.judge(r["tier"], task["answer"],
                                                                                    r["expected"])), (side, r["i"])
        built = r["experienced"]["construction"]
        assert r["construction_correct"] == (built["state"] == "ACHIEVED"
                                             and T.judge("replay", built["answer"], want_construction))


def test_one_live_cross_family_pair_measures_reuse(tmp_path):
    problem = T.instances("greg-transfer-ci", {"cross_family": 1})["cross_family"][0]
    want = T.expected("cross_family", problem)
    e = T.arm("cross_family", 0, problem, True, tmp_path, "ci")
    c = T.arm("cross_family", 0, problem, False, tmp_path, "ci")
    assert T.judge("replay", e["construction"]["answer"], T.expected("replay", T.CONSTRUCTION))
    for a in (e["task"], c["task"]):
        assert a["state"] == "ACHIEVED" and T.judge("cross_family", a["answer"], want)
        assert a["appraisal"] == "VERIFIED" and not a["authority_created"] and a["self_attached"] == 0
    # the experienced body acquires no engine: its only deficit is the new function, its only ask that attach
    assert e["task"]["deficits"] == ["assignment.matching"] and e["task"]["attach_asks"] == 1
    assert c["task"]["deficits"] == ["assignment.matching", "graph.max_flow"] and c["task"]["attach_asks"] == 2
    assert e["task"]["work"] < c["task"]["work"]
