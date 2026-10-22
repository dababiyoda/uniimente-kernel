"""The advantage compiler generates lawful candidates at evidenced bottlenecks and invents no magnitudes."""
from dataclasses import replace

import pytest

from greg.cognition import advantage as A
from greg.cognition.contracts import CognitionError

REF = ["evidence:interview-2026-10-01"]
MAP = {
    "nodes": [
        {"id": "outcome", "kind": "outcome", "label": "paid repair jobs", "gap": 0.0, "evidence_refs": REF},
        {"id": "trust", "kind": "process", "label": "contractor verification", "gap": 0.8, "evidence_refs": REF},
        {"id": "permit", "kind": "rule", "label": "municipal permit rule", "gap": 0.5, "evidence_refs": REF},
        {"id": "island", "kind": "process", "label": "unconnected step", "gap": 0.9, "evidence_refs": REF},
    ],
    "links": [
        {"id": "l1", "source": "trust", "target": "outcome", "mechanism": "direct", "strength": 0.9,
         "confidence": 0.8, "evidence_refs": REF},
        {"id": "l2", "source": "permit", "target": "trust", "mechanism": "rule", "strength": 0.6,
         "confidence": 0.7, "evidence_refs": REF},
    ],
    "interventions": [],
}
REQUEST = {"objective": "more verified paid repair jobs", "outcome_node": "outcome"}


def test_candidates_come_only_from_evidenced_bottlenecks_on_a_path_to_the_outcome():
    out = A.compile_map(MAP, REQUEST)
    nodes = {c["node"] for c in out["candidates"]}
    assert nodes == {"trust", "permit"}                 # the unconnected high-gap node is not a bottleneck
    assert out["candidates"][0]["node"] == "trust"      # severity 0.8 * (0.9 * 0.8) beats 0.5 * (0.6 * 0.7 * 0.72)
    assert all(c["lawful"] and c["estimate_status"].startswith("UNESTIMATED") for c in out["candidates"])
    assert out["authority_created"] is False and out["refused_operators"] == []


def test_financial_means_require_a_founder_grant_and_commodity_gaps_backcast_to_acquisition():
    out = A.compile_map(MAP, REQUEST)
    settle = next(c for c in out["candidates"] if c["operator"] == "settlement_on_proof")
    assert settle["consequence_class"] == "financial" and "founder grant" in settle["authority_required"]
    # cognition.evidence is built but has no native benchmark yet, so the operator is EXPERIMENTAL_NOW;
    # the absent escrow is commodity: it backcasts to acquisition, not research.
    assert settle["buildability"] == "EXPERIMENTAL_NOW"
    assert any(s["capability"] == "cognition.evidence" and "native benchmark" in s["step"] for s in settle["backcast"])
    assert any(s["capability"] == "payments.escrow" and "Capability Genesis" in s["step"] for s in settle["backcast"])


@pytest.mark.parametrize("means", ["coercion", "covert_surveillance", "deception_campaign", "made_up_means"])
def test_operators_with_unlawful_or_unknown_means_are_refused(means):
    rogue = replace(A.OPERATORS[0], id="rogue", means=("build_software", means))
    out = A.compile_map(MAP, REQUEST, operators=(rogue,))
    assert out["candidates"] == [] and out["refused_operators"][0]["operator"] == "rogue"


def test_library_operators_are_all_lawful():
    assert all(A.lawful(op) == [] for op in A.OPERATORS)


def test_estimates_are_required_before_ranking_and_feed_the_existing_ranker():
    out = A.compile_map(MAP, REQUEST)
    first = out["candidates"][0]
    assert A.to_interventions(out["candidates"], {}) == []
    with pytest.raises(CognitionError, match="estimates need"):
        A.to_interventions(out["candidates"], {first["id"]: {"effect": 0.5}})
    estimate = {"effect": 0.5, "confidence": 0.6, "harm": 0.05, "cost_usd": 100, "effort_hours": 4, "delay_days": 2,
                "evidence_refs": REF, "action": {"action_class": "build", "requested_capability": "fs.write",
                                                  "target": "workspace:receipts", "consequence_class": "internal_write",
                                                  "payload": {}}}
    rows = A.to_interventions(out["candidates"], {first["id"]: estimate})
    assert rows[0]["id"] == first["id"] and rows[0]["effect"] == 0.5


def test_frontier_capabilities_raise_buildability_and_science_fiction_stays_on_the_horizon():
    assert A.buildability((("x.absent", "frontier"),), {})[0] == "FRONTIER_RESEARCH"
    assert A.buildability((("x.absent", "experimental"),), {})[0] == "EXPERIMENTAL_NOW"
    watch = next(A.backcast(d) for d in A.DESTINATIONS if d.expression.startswith("Watch over"))
    assert watch["literal"] == "SCIENCE_FICTION_DESCENDANT"
    assert watch["compiled_effect_buildability"] == "BUILDABLE_NOW"
    assert watch["kept_on_horizon"] == ["perception.ubiquitous"]


def test_cli_exposes_genomes_advantage_and_destinations(tmp_path, capsys):
    import json
    from greg import cli
    home = tmp_path / "home"
    assert cli.main(["--home", str(home), "cognition", "genomes"]) == 0
    assert json.loads(capsys.readouterr().out)["problems"] == []
    (tmp_path / "map.json").write_text(json.dumps(MAP))
    assert cli.main(["--home", str(home), "cognition", "advantage", "--map", str(tmp_path / "map.json"),
                     "--outcome", "outcome", "--objective", REQUEST["objective"]]) == 0
    assert json.loads(capsys.readouterr().out)["candidates"]
    assert cli.main(["--home", str(home), "cognition", "destinations"]) == 0
    assert len(json.loads(capsys.readouterr().out)) == len(A.DESTINATIONS)
