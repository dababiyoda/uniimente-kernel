"""The competency characterization harness measures, and notices a weakened verifier (directive section 5)."""
import pytest

from greg.cognition import characterize as C


@pytest.fixture(scope="module")
def report():
    return C.characterize(["exact", "optimization"], quick=True)


def test_measured_dimensions_and_declared_not_applicable_ones(report):
    for name in ("exact", "optimization"):
        family = report["families"][name]
        assert family["available"] is True
        assert family["error_correction"]["n"] > 0
        assert family["error_correction"]["refuted"] == family["error_correction"]["n"]
        assert family["generalization"]["invariant"] == family["generalization"]["n"] > 0
        assert family["problem_space"]["largest_correct_size"] is not None
        assert family["responsiveness"]["p50_seconds"] > 0
    correlated = report["families"]["optimization"]["correlated_failure_evidence"]
    assert correlated["certificates"] == ["z3: different engine from the solver (Z3 against CP-SAT)"]
    assert sum(correlated["certificate_outcomes"].values()) > 0 and "REFUTED" not in correlated["certificate_outcomes"]
    assert set(report["not_applicable"]) == {"memory_depth", "persistence", "prediction_horizon", "adaptability",
                                             "cooperation", "higher_scale_coherence"}
    assert all(reason for reason in report["not_applicable"].values())
    assert report["authority_created"] is False and report["environment"]["python"]


def test_a_verifier_that_accepts_everything_shows_up_as_zero_error_correction(monkeypatch):
    monkeypatch.setattr(C, "verify", lambda *a, **k: {"verdict": "STRUCTURALLY_VERIFIED"})
    weakened = C.characterize(["optimization"], quick=True)["families"]["optimization"]["error_correction"]
    assert weakened["n"] > 0 and weakened["refuted"] == 0 and weakened["rate_wilson95"][0] == 0.0


def test_an_unattached_family_is_reported_unavailable_not_scored():
    graph = C.characterize(["graph"], quick=True)["families"]["graph"]
    if graph["available"]:
        pytest.skip("graph is attached in this environment")
    assert graph["problem_space"]["largest_correct_size"] is None and graph["error_correction"]["n"] == 0


def test_wilson_intervals():
    assert C.wilson(0, 0) is None
    assert C.wilson(4, 4)[0] == pytest.approx(4 / (4 + 1.959963984540054 ** 2), abs=1e-4)
    low, high = C.wilson(5, 10)
    assert low < 0.5 < high
