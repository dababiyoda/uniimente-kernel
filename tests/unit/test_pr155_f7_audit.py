"""The independent F7 audit is falsifiable: development items only (the held-out run is frozen evidence)."""
import json

import pytest

from cortex.evaluation.pr155_f7_audit import audit as A

DEV = "docs/evidence/greg-composition-lift/2026-10-14-v4/development-v4.json"


@pytest.fixture(scope="module")
def item():
    row = json.loads((A.ROOT / DEV).read_text())["rows"][0]                     # F7-abilene-0, a development item
    network, pair = row["item_id"].split("-", 1)[1].rsplit("-", 1)
    assert network in [n for i, n in enumerate(sorted(A.networks())) if i % 5 == 0]
    return row, A.instance(A.networks()[network], int(pair))


def test_the_independent_optimum_and_rescoring_reproduce_a_development_item(item):
    row, inst = item
    best = A.optimum(inst)
    assert best["optimal"] and best["integral"] and best["value"] == row["truth"]["optimum"]
    assert best["plan_value"] == best["value"] and best["plan_spent"] <= inst["budget"]
    for arm, rec in row["arms"].items():
        assert A.rescore(inst, rec.get("answer"), best["value"]) == (rec["result"], rec["throughput"]), arm


def test_forged_plans_are_caught(item):
    row, inst = item
    truth = row["truth"]["optimum"]
    plan = dict(row["arms"]["parametric_min_cost_flow"]["answer"])
    assert A.rescore(inst, {**plan, "flow_value": truth + 1}, truth)[0] == "wrong"           # false flow claim
    over = {k: A.MAX_INCREMENT for k in plan["increments"]}
    assert A.rescore(inst, {"increments": over}, truth)[0] == "wrong"                         # over budget
    assert A.rescore(inst, {"increments": {"X->Y": 1}}, truth)[0] == "wrong"                   # unknown arc
    assert A.rescore(inst, None, truth)[0] == "no_decision"


def test_a_changed_frozen_input_refuses_the_run(tmp_path, monkeypatch):
    frozen = json.loads(A.FREEZE.read_text())
    frozen["inputs"][A.RESULTS] = "sha256:" + "0" * 64
    fake = tmp_path / "freeze.json"
    fake.write_text(json.dumps(frozen))
    monkeypatch.setattr(A, "FREEZE", fake)
    with pytest.raises(A.AuditError, match="FROZEN_INPUT_CHANGED"):
        A.check_freeze()


def test_the_recorded_audit_is_never_overwritten():
    assert A.OUT.exists()
    with pytest.raises(A.AuditError, match="never overwritten"):
        A.main()
