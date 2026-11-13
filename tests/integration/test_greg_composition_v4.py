"""P6 v4: the natural F7 family's integrity (real SNDlib backbones -> graph_then_allocate).

Development networks only (abilene, di-yuan, india35, nobel-germany, polska); no held-out network is
generated here. Genome families start registered-and-withheld (VERIFIED); the one canonical-path test attaches
them in an in-memory registry view exactly as the frozen evaluation does. Nothing here changes a body or creates
authority.
"""
import gzip
import hashlib
import json

import pytest

pytest.importorskip("networkx")

from cortex.evaluation.composition_lift import run_v4 as R  # noqa: E402
from cortex.evaluation.composition_lift.vpl_metrics import validate_preregistration  # noqa: E402
from greg.cognition.composition import route  # noqa: E402
from greg.cognition.genomes.flow import expansion_truth, expansion_value  # noqa: E402


def dev_item(network="abilene", pair=2):
    dev, _ = R.partition()
    assert network in dev
    return R.f7(network, pair)


def test_the_preregistration_is_complete_and_names_the_committed_data():
    doc = json.loads(R.PREREG.read_text())
    assert validate_preregistration(doc) == []
    assert doc["latency_rule"] == {**doc["latency_rule"], "kind": "multiplier", "value": R.LATENCY_MULTIPLIER}
    assert doc["data_provenance"]["sha256"] == hashlib.sha256(R.DATA.read_bytes()).hexdigest()
    assert "research" in doc["data_provenance"]["licence"]


def test_the_partition_is_fixed_by_name_and_disjoint():
    dev, held = R.partition()
    names = sorted(json.loads(gzip.open(R.DATA).read())["networks"])
    assert dev == ["abilene", "di-yuan", "india35", "nobel-germany", "polska"]
    assert sorted(dev + held) == names and not set(dev) & set(held) and len(held) == 20


def test_items_are_deterministic_and_respect_the_declared_layer():
    item = dev_item()
    assert item == dev_item()
    net = item["payload"]["capacity_network"]
    assert route(item["payload"]) == "graph_then_allocate"
    assert 1 <= len(net["edges"]) <= R.MAX_ARCS                    # the optimisation family's 64-variable ceiling
    assert net["max_increment"] == R.MAX_INCREMENT
    assert all(c >= 0 for _, _, c in net["edges"])
    assert item["truth"]["optimum"] == expansion_truth(net)
    assert item["truth"]["without_lease"] == expansion_value(net, {})[0] <= item["truth"]["optimum"]


@pytest.mark.parametrize("load,free", [(0.0, 10), (7.9, 2), (8.0, 2), (8.5, 11), (100.0, 30), (99.9, 30), (40.0, 10)])
def test_free_capacity_is_the_module_headroom_at_80_percent(load, free):
    assert R.free_capacity(load) == free


def test_the_admissible_path_rule_shrinks_k_before_declaring_an_item_out_of_scope():
    net = json.loads(gzip.open(R.DATA).read())["networks"]["india35"]
    s, t, _ = net["top_demands"][0]
    arcs, k = R.corridor(net, s, t)
    assert 2 <= k <= 4 and len(arcs) <= R.MAX_ARCS
    def disjoint(paths, hops):
        links = []
        for j in range(paths):
            nodes = ["hub", *[f"p{j}h{i}" for i in range(hops - 1)], "far"]
            links += [[a, b, 1.0 + j / 100, 0.0, 0.0] for a, b in zip(nodes, nodes[1:])]
        return {"links": links}
    assert R.corridor(disjoint(6, 8), "hub", "far")[1] == 4      # 4 paths x 8 hops = 32 arcs: fits at K = 4
    assert R.corridor(disjoint(6, 10), "hub", "far")[1] == 3     # 40 arcs at K = 4, 30 at K = 3
    assert R.corridor(disjoint(6, 20), "hub", "far") is None      # 40 arcs even at K = 2: out of scope


def test_scoring_detects_over_budget_false_claims_and_optimality():
    item = dev_item()
    net = item["payload"]["capacity_network"]
    exact = R.parametric_min_cost_flow(net)
    assert R.f7_score(item, exact) == ("optimal", item["truth"]["optimum"])
    assert R.f7_score(item, {**exact, "flow_value": exact["flow_value"] + 1})[0] == "wrong"
    blown = {k: R.MAX_INCREMENT for k in exact["increments"]}
    assert R.f7_score(item, {"increments": blown})[0] == "wrong"
    assert R.f7_score(item, None) == ("no_decision", None)
    assert R.f7_score(item, {"increments": {k: 0 for k in exact["increments"]}})[0] in ("optimal", "suboptimal")


@pytest.mark.parametrize("network", ["abilene", "di-yuan", "india35", "nobel-germany", "polska"])
def test_the_practitioner_arms_stay_within_budget_on_development_networks(network):
    for pair in range(3):
        item = R.f7(network, pair)
        if item is None:
            continue
        net = item["payload"]["capacity_network"]
        assert R.f7_score(item, R.parametric_min_cost_flow(net))[0] == "optimal"
        assert R.f7_score(item, R.shortest_path_upgrade(net))[0] in ("optimal", "suboptimal")


def test_the_composition_answers_a_development_item_optimally_through_verified_stages():
    item = dev_item()
    answer, seconds, r = R.chain(item, "graph_then_allocate")
    assert r["state"] == "ANSWERED" and r["authority_created"] is False
    assert [s["stage"] for s in r["stages"]] == ["compile", "optimize", "cross_check"]
    assert R.f7_score(item, answer) == ("optimal", item["truth"]["optimum"])
    compiled, _, receipt = R.compiled(item)
    assert receipt["state"] == "ANSWERED" and R.f7_score(item, compiled)[0] == "optimal"
    assert receipt["method_or_composition_selected"] == "composition:graph_then_allocate"


def test_the_suite_build_refuses_without_a_complete_preregistration(monkeypatch, tmp_path):
    bad = tmp_path / "prereg.json"
    bad.write_text(json.dumps({"family_id": "F7"}))
    monkeypatch.setattr(R, "PREREG", bad)
    monkeypatch.setattr(R, "SUITE", tmp_path / "suite.json")
    monkeypatch.setattr("sys.argv", ["run_v4.py", "--build"])
    with pytest.raises(SystemExit, match="pre-registration is incomplete"):
        R.main()
    assert not (tmp_path / "suite.json").exists()
