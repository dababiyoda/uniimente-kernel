"""Legacy outcomes remain negative while default eligibility is tested separately."""
from copy import deepcopy
import json

from greg.cognition import benchmark
from greg.cognition.catalog import initial_state
from greg.cognition.contracts import digest


CASES = [
    {"id": "active", "request": {"problem_id": "compat:active", "operation": "calculate", "data": {"expression": "1+1"}},
     "expected": {"method": "cognition.exact", "state": "NONE", "output": {"exact": "2"}}},
    {"id": "unattached", "request": {"problem_id": "compat:unattached", "operation": "beta_update", "data": {"alpha": 1, "beta": 1, "successes": 3, "failures": 1}},
     "expected": {"method": "cognition.probabilistic", "state": "NONE", "output": {"alpha": 4}}},
    {"id": "unknown", "request": {"problem_id": "compat:unknown", "operation": "unknown_geometry", "data": {}},
     "expected": {"method": "none", "state": "CAPABILITY_DEFICIT"}},
]


def suite(tmp_path, cases=CASES):
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({"baseline_required_for_superiority": ["always_llm"], "cases": cases}))
    return path


def test_original_labels_and_failures_survive_separate_default_gate_checks(tmp_path):
    path = suite(tmp_path)
    original = path.read_bytes()
    report = benchmark.compatibility(suite=path)
    assert report["correct"] == 1 and report["compatibility_correct"] == 3
    assert report["total"] == 3 and report["superiority_status"] == "UNMEASURED"
    assert [row["original_expected"] for row in report["cases"]] == [case["expected"] for case in CASES]
    assert path.read_bytes() == original
    assert initial_state("cognition.probabilistic") == "VERIFIED"
    assert report["cases"][1]["receipt"]["output"] is None
    assert all(row["receipt"]["authority_created"] is False for row in report["cases"])


def test_unauthorized_default_attachment_cannot_green_the_legacy_ci(monkeypatch, tmp_path):
    path = suite(tmp_path, [CASES[1]])
    original_registry = benchmark.registry_view
    def wrongly_attached():
        registry = original_registry()
        registry.set_state("cognition.probabilistic", "ATTACHED")
        return registry
    monkeypatch.setattr(benchmark, "registry_view", wrongly_attached)
    report = benchmark.compatibility(suite=path)
    assert report["correct"] == 1  # Legacy golden success cannot buy eligibility.
    assert report["compatibility_correct"] == 0
    assert report["cases"][0]["default_gate_contract"]["kind"] == "DEFAULT_UNATTACHED"


def test_active_wrong_answer_does_not_become_a_compatibility_success(monkeypatch, tmp_path):
    path = suite(tmp_path, [CASES[0]])
    original_reason = benchmark.reason
    def forged(*args, **kwargs):
        receipt = deepcopy(original_reason(*args, **kwargs))
        receipt["output"]["exact"] = "9"
        receipt.pop("receipt_id")
        receipt["receipt_id"] = digest(receipt)
        return receipt
    monkeypatch.setattr(benchmark, "reason", forged)
    report = benchmark.compatibility(suite=path)
    assert report["correct"] == report["compatibility_correct"] == 0


def test_optional_symbolic_dependency_unavailability_is_explicit(monkeypatch, tmp_path):
    import importlib.metadata
    original = importlib.metadata.version
    def missing(name):
        if name == "sympy":
            raise importlib.metadata.PackageNotFoundError(name)
        return original(name)
    monkeypatch.setattr(importlib.metadata, "version", missing)
    path = suite(tmp_path, [{"id": "symbolic", "request": {"problem_id": "compat:symbolic", "operation": "polynomial", "data": {"polynomial": [-4, 0, 1]}},
                             "expected": {"method": "cognition.exact", "state": "NONE", "output": {"real_roots": ["-2", "2"]}}}])
    report = benchmark.compatibility(suite=path)
    assert report["correct"] == 0 and report["compatibility_correct"] == 1
    assert report["cases"][0]["default_gate_contract"]["kind"] == "OPTIONAL_DEPENDENCY_UNAVAILABLE"
    assert report["cases"][0]["receipt"]["output"] is None
