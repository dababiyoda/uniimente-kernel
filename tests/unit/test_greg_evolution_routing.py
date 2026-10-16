"""PR #155 routing-genome alternative (evolution_routing): a candidate may change only data in a closed schema, and it cannot edit the evaluator that judges it."""
import random

import pytest

from greg.cognition.evolution_routing import BASELINE, MutationRefused, ProtectedEvaluator, evolve, mutate, sha256, validate


@pytest.mark.parametrize("key", ["approval_threshold", "budget_usd", "shutdown_delay", "grant_scope",
                                 "evaluator_path", "founder_override", "threshold_accept"])
def test_authority_bearing_keys_are_refused_as_unauthorized_mutation(key):
    with pytest.raises(MutationRefused, match="unauthorized mutation attempt"):
        validate({**BASELINE, key: 1})


@pytest.mark.parametrize("candidate,message", [
    ({**BASELINE, "margin": 0.9}, "outside"), ({**BASELINE, "min_evidence": True}, "outside"),
    ({**BASELINE, "features": ["kind", "kind"]}, "duplicate-free"),
    ({**BASELINE, "features": ["kind", "owner"]}, "duplicate-free"), ({**BASELINE, "colour": 1}, "unknown key"),
    ("not an object", "JSON object"),
])
def test_values_outside_the_schema_are_refused(candidate, message):
    with pytest.raises(MutationRefused, match=message):
        validate(candidate)


def test_mutation_stays_inside_the_schema():
    rng, genome = random.Random(1), dict(BASELINE)
    for _ in range(200):
        genome, _ = mutate(genome, rng)
        assert validate(genome) == genome


def _evaluator(tmp_path, body="print(json.dumps({'partition': sys.argv[1], 'correct': len(g['features']), "
                              "'wrong': 0, 'no_decision': 0, 'n': 6, 'per_item': []}))"):
    path = tmp_path / "evaluator.py"
    path.write_text("import json, sys\ng = json.loads(sys.stdin.read())\n" + body + "\n")
    return path


def test_evaluator_edited_after_pinning_stops_the_run(tmp_path):
    path = _evaluator(tmp_path)
    evaluate = ProtectedEvaluator(path, sha256(path), cwd=tmp_path)
    assert evaluate(BASELINE, "dev")["correct"] == len(BASELINE["features"])
    path.write_text(path.read_text() + "# a candidate edited its judge\n")
    with pytest.raises(RuntimeError, match="EVALUATOR_CHANGED"):
        evaluate(BASELINE, "dev")


def test_evaluator_may_not_return_fields_outside_its_contract(tmp_path):
    path = _evaluator(tmp_path, "print(json.dumps({'correct': 1, 'wrong': 0, 'promote': True}))")
    with pytest.raises(RuntimeError, match="outside its contract"):
        ProtectedEvaluator(path, sha256(path), cwd=tmp_path)(BASELINE, "dev")


def test_selection_is_elitist_and_keeps_lineage(tmp_path):
    evaluate = ProtectedEvaluator(_evaluator(tmp_path), sha256(tmp_path / "evaluator.py"), cwd=tmp_path)
    result = evolve(evaluate, generations=2, population=3, seed=5)
    assert result["baseline"]["id"] == "g0-baseline" and len(result["lineage"]) == 1 + 2 * 3
    assert result["champion"]["dev"]["correct"] >= result["baseline"]["dev"]["correct"]
    assert all(entry["parent"] in {x["id"] for x in result["lineage"]} for entry in result["lineage"][1:])
