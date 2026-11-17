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
    # every second-engine certificate on these correct answers succeeded: CERTIFIED, not merely "not REFUTED", which
    # NOT_RUN and UNKNOWN also satisfy (review 2026-11-17, finding 6)
    assert correlated["certificate_outcomes"].get("CERTIFIED", 0) > 0
    assert set(correlated["certificate_outcomes"]) == {"CERTIFIED"}
    assert set(report["not_applicable"]) == {"memory_depth", "persistence", "prediction_horizon", "adaptability",
                                             "cooperation", "higher_scale_coherence"}
    assert all(reason for reason in report["not_applicable"].values())
    assert report["authority_created"] is False and report["environment"]["python"]


def test_the_report_keeps_the_actual_status_when_the_second_engine_is_missing(monkeypatch, tmp_path):
    # The verifier worker (a separate process) runs under an interpreter that genuinely has no Z3; the solver keeps
    # its own. The report counts what happened, NOT_RUN, and never rewrites it as CERTIFIED (review 2026-11-17: the
    # positive finding preserved).
    import subprocess
    import sys
    import venv
    from greg.cognition import cortex
    venv.EnvBuilder(with_pip=False, system_site_packages=False).create(tmp_path / "bare")
    bare = str(tmp_path / "bare" / "bin" / "python")
    assert subprocess.run([bare, "-I", "-c", "import z3"], capture_output=True).returncode != 0
    real = cortex.independent_verify

    def verify_without_z3(*args, **kwargs):
        with monkeypatch.context() as m:
            m.setattr(sys, "executable", bare)
            return real(*args, **kwargs)
    monkeypatch.setattr(cortex, "independent_verify", verify_without_z3)
    outcomes = C.characterize(["optimization"], quick=True)["families"]["optimization"][
        "correlated_failure_evidence"]["certificate_outcomes"]
    assert outcomes.get("NOT_RUN", 0) > 0 and "CERTIFIED" not in outcomes


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
