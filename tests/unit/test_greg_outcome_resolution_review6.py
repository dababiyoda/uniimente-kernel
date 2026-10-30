"""Round 5 of the review of #221 (session_01Kucyfoabgsg6W8H8xj4qea, #221 comment 6515476874).

The six cases the round gives for the mutants no test saw (N29, N32, N43, N54, N58, N60), and the evaluation limit
of the decision walk (W4-1). Decision-value cases run on injected settled counts through the compiler's own rules;
the reconcile case on a real body with a per-test founder key. Values are synthetic test inputs.
"""
from __future__ import annotations

from functools import lru_cache

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg.cognition import compiler, settlement  # noqa: E402
from greg.cognition.contracts import digest  # noqa: E402
from tests.unit.test_greg_construction_realization import Run  # noqa: E402
from tests.unit.test_greg_outcome_resolution_review5 import _old_rule_body, weigh  # noqa: E402
from tests.unit.test_greg_pending_construction_realization import appraise  # noqa: E402


def inhibit():
    return lru_cache(maxsize=None)(compiler._settled_inhibition)


def preference_reasons(row):
    return [r for r in row["decision_impact"]["could_change"] if r.startswith("the settled-outcome preference")]


# --- N29: the method demoted at every reachable count is ranked last, not first -------------------------------------


def test_n29_a_method_demoted_at_every_reachable_count_is_never_walked_as_first():
    states = settlement._resolution_states(30, 3, 1)
    counts = {"X": (30, 3), "A": (20, 7), "B": (19, 2)}
    assert settlement._preference_changes("X", states, counts, {}, inhibit()) == ([], [])


# --- N32: no row is superseded twice ---------------------------------------------------------------------------------


def test_n32_no_settlement_is_superseded_twice_after_a_merge_then_a_withdrawal(tmp_path, monkeypatch):
    with Run(tmp_path) as run:
        journal = run.body.journal
        record, head, _ = _old_rule_body(run, monkeypatch, "pf-n32-r5")
        journal.record("cognition.settled", {**head.payload, "answer_version": digest(["engine-2"]),
                                             "supersedes": None}, key=["old-rule", "engine-2"])
        settlement.reconcile(journal)
        mission = next(e.payload["mission_id"] for e in journal.replay("mission.observed")
                       if e.payload["receipt"] == record.hash)
        appraise(journal, "UNAVAILABLE", mission_id=mission)
        settlement.reconcile(journal)
        settlement.reconcile(journal)
        closed = [e.payload["supersedes"] for e in journal.replay("cognition.settled") if e.payload.get("supersedes")]
        assert len(closed) == len(set(closed))


# --- N43: the reason names the fit ranked first once the method's own demotion moves another fit up -------------


def test_n43_the_reason_names_the_fit_ranked_first_when_the_methods_demotion_moves_it(monkeypatch):
    row = weigh(monkeypatch, {"X": (7, 1), "A": (19, 11), "B": (10, 7), "C": (26, 19)}, {"X": 4})["X"]
    assert any("with A or X ranked first among ['A', 'X']" in r for r in preference_reasons(row))


# --- N54: the joint state limit is the family's own ---------------------------------------------------------------


def test_n54_a_family_inside_the_state_limit_is_walked_while_all_the_others_exceed_it(monkeypatch):
    counts = {"construction.X": (34, 20), "construction.Z": (14, 12),
              "construction.ZP": (20, 15), "construction.ZQ": (20, 15)}
    disputes = {"construction.X": 1, "construction.Z": 4, "construction.ZP": 3, "construction.ZQ": 3}
    row = weigh(monkeypatch, counts, disputes)["construction.X"]
    assert any("with construction.Z at 13 of 15" in r for r in row["decision_impact"]["could_change"])


# --- N58: another disputed method's values are compared only within the method's demotion class -----------------


def test_n58_another_disputed_methods_values_of_the_other_demotion_class_are_not_a_laplace_tie(monkeypatch):
    rows = weigh(monkeypatch, {"X": (3, 0), "Y": (31, 4)}, {"X": 1, "Y": 4})
    assert rows["X"]["priority"] == "hold" and rows["Y"]["priority"] == "hold"


# --- N60: a demoted first is skipped, so a change is reported once -----------------------------------------------


def test_n60_a_demoted_first_fit_does_not_repeat_a_found_change(monkeypatch):
    row = weigh(monkeypatch, {"X": (11, 3), "Y": (23, 7)}, {"X": 4, "Y": 2})["X"]
    assert len([r for r in preference_reasons(row) if "among ['X', 'Y']" in r]) == 1


# --- W4-1: the walk stops at a deterministic evaluation limit ---------------------------------------------------


def test_w4_1_the_walk_stops_at_the_evaluation_limit_and_says_so(monkeypatch):
    """Three disputed methods with four disputes each beside five undemoted fits: nothing is pruned, and the walk
    needed several hundred thousand rule evaluations before the limit."""
    counts = {f"construction.D{i}": (20 + i, 11 + i) for i in range(3)}
    counts.update({f"fit.F{i}": (18 + 2 * i, 10 + i) for i in range(5)})
    calls = []
    real = compiler._settled_preference
    monkeypatch.setattr(compiler, "_settled_preference", lambda *a, **k: calls.append(1) or real(*a, **k))
    row = weigh(monkeypatch, counts, {f"construction.D{i}": 4 for i in range(3)})["construction.D0"]
    assert row["priority"] == "investigate"
    assert any("evaluation limit" in w for w in row["decision_impact"]["walk_limits"])
    assert len(calls) <= 3 * settlement.PREFERENCE_EVALUATION_LIMIT       # one walk per disputed method


def test_w4_1_a_walk_inside_the_evaluation_limit_names_no_limit(monkeypatch):
    row = weigh(monkeypatch, {"construction.X": (36, 24), "construction.Y": (31, 28)},
                {"construction.X": 4, "construction.Y": 2})["construction.X"]
    assert row["decision_impact"]["walk_limits"] == []
