"""The IntelligenceGenome library projects onto GREG's one catalog, worker, verifier and receipt."""
import json

import pytest

from greg.cognition import catalog
from greg.cognition.genomes import admission, library
from greg.cognition.genomes.contract import ADMISSION, GenomeError, IntelligenceGenome


def test_every_genome_validates_and_projects_onto_the_existing_catalog():
    items = library.executables()
    assert {"flow_maxflow", "forecast_quantile", "decision_preposterior"} <= set(items)
    for family, item in items.items():
        g = item.genome
        assert catalog.FAMILIES[family] == (g.layer, (g.operation,), (g.epistemic_class,), "genome_certificate",
                                            g.dependency)
        assert g.authority_ceiling == g.consequence_limit == "read_only"
        assert catalog.initial_state(f"cognition.{family}") == "VERIFIED"      # registered, never auto-attached


def test_a_genome_cannot_declare_effect_authority_or_skip_its_baseline():
    g = library.genome("flow_maxflow")
    with pytest.raises(GenomeError):
        IntelligenceGenome(**{**g.to_dict(), "authority_ceiling": "financial"}).validate()
    with pytest.raises(GenomeError):
        IntelligenceGenome(**{**g.to_dict(), "baseline": ""}).validate()


def test_a_genome_runs_on_the_canonical_path_with_an_independent_verifier():
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    data, truth = library.executables()["flow_maxflow"].instance(3)
    withheld = reason({"problem_id": "g", "operation": "max_flow", "data": data}, registry=registry)
    assert withheld["abstention_state"] == "CAPABILITY_DEFICIT"            # withheld until attached
    registry.set_state("cognition.flow_maxflow", "ATTACHED")
    r = reason({"problem_id": "g", "operation": "max_flow", "data": data}, registry=registry)
    assert r["abstention_state"] == "NONE" and r["output"]["value"] == truth["value"]
    assert r["proof_type"] == "genome_certificate" and r["proof_artifact"]["evidence_type"] == "optimality_certificate"
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and r["authority_created"] is False


def test_the_independent_check_refutes_a_forged_flow():
    data, _ = library.executables()["flow_maxflow"].instance(3)
    out = library.run("flow_maxflow", data, {"latency_limit": 5, "compute_limit": 1000})
    assert all(library.check("flow_maxflow", data, out["output"], out["proof"]).values())
    forged = json.loads(json.dumps(out["output"]))
    forged["value"] += 1
    assert not all(library.check("flow_maxflow", data, forged, out["proof"]).values())
    tampered = {**out["proof"], "inputs_digest": "sha256:0"}
    assert not library.check("flow_maxflow", data, out["output"], tampered)["inputs_bound"]


class _Item:
    def __init__(self, standalone=True):
        self.tolerance = 1e-9
        self.subregion = None
        self.genome = type("G", (), {"standalone_decision": standalone})()


def _rows(c, b, k, *, cat=lambda q: "correct", secs=(1.0, 1.0, 1.0)):
    return [{"arms": {"candidate": {"quality": x, "category": cat(x), "seconds": secs[0]},
                      "baseline": {"quality": y, "category": cat(y), "seconds": secs[1]},
                      "competitor": {"quality": z, "category": cat(z), "seconds": secs[2]}}}
            for x, y, z in zip(c, b, k)]


def test_admission_rule_outcomes():
    ten = [1.0] * 10
    assert admission.decide(_Item(False), _rows(ten, ten, ten))[0] == "COMPOSITION_ONLY"
    assert admission.decide(_Item(), _rows([0.0] * 10, ten, ten))[0] == "REJECTED"
    assert admission.decide(_Item(), _rows(ten, ten, ten))[0] == "EXPERIMENTAL"
    assert admission.decide(_Item(), _rows(ten, [0.0] * 10, [2.0] * 10))[0] == "SUPERSEDED"
    assert admission.decide(_Item(), _rows([2.0] + [1.0] * 9, [0.0] * 10, [1.5] + [2.0] * 9))[0] == "NICHE_CAPABILITY"
    assert admission.decide(_Item(), _rows(ten, [0.0] * 10, ten))[0] == "DEFAULT_FOR_GEOMETRY"
    assert admission.decide(_Item(), _rows(ten, [0.0] * 10, ten, secs=(3.0, 1.0, 1.0)))[0] == "SUPERSEDED"
    assert set(ADMISSION) >= {"DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY", "REJECTED", "FRONTIER_HORIZON"}


def test_a_refuted_candidate_answer_is_scored_as_a_false_answer_below_abstention():
    item = library.executables()["flow_maxflow"]
    forged = type(item)(**{**item.__dict__, "verify": lambda d, o, c: {"forged": False}})
    rows = admission.evaluate(forged, [0])
    arm = rows[0]["arms"]["candidate"]
    data, truth = item.instance(0)
    assert arm["category"] == "wrong" and arm["refuted"] is True
    assert arm["quality"] < item.score(data, truth, None)["quality"]


def test_held_out_admission_refuses_changed_code(tmp_path, monkeypatch):
    monkeypatch.setattr(admission, "EVIDENCE", tmp_path)
    admission.main(["--freeze", "r1", "--only", "flow_maxflow"])
    frozen = json.loads((tmp_path / "r1" / "freeze.json").read_text())
    frozen["inputs"]["code"]["greg/cognition/genomes/flow.py"] = "sha256:changed"
    (tmp_path / "r1" / "freeze.json").write_text(json.dumps(frozen))
    with pytest.raises(SystemExit, match="FROZEN_INPUT_CHANGED"):
        admission.main(["--run", "r1"])
