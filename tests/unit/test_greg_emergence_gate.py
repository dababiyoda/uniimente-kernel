"""Directive section 20 (S20.A2): a recombination states what it does that no source does alone and beats its
baseline, or is refused as integration.

Every reduction's stated `baseline` runs (greedy staffing, greedy matching, trial-and-error crashing, greedy
selection, dropping costs from the uncapped best). On the frozen cases, the construction's oracle cases and the
traps built to each baseline's stated weakness, a construction qualifies only when every answer is certified exact
and the baseline misses the exact answer on at least one case. A baseline that reaches it everywhere, a missing or
broken baseline, or a construction worse than its baseline leaves the construction refused as integration: Genesis
records why and registers nothing.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from greg import recombine

DECISIVE = {"assignment.staffing": "trap:first-come-takes-the-flexible-worker", "assignment.matching": "perfect",
            "project.crash": "trap:shared-predecessor", "selection.closure": "shared-prerequisite",
            "selection.budgeted": "shared-platform-short"}


def certified(cases):
    """Answers a correct construction gives: certified, and the exact value the oracle expects."""
    return [{"certified": True, **case["expected"]} for case in cases]


def frozen(reduction, seed=0):
    return reduction.oracle(seed) + recombine.trap_cases(reduction)


@pytest.mark.parametrize("function", sorted(DECISIVE))
def test_each_construction_beats_its_runnable_baseline_on_a_frozen_case_whatever_the_seed(function):
    reduction = recombine.REDUCTIONS[function]
    assert reduction.emergence is not None and reduction.emergence.claim
    for seed in range(5):
        cases = frozen(reduction, seed)
        gate = recombine.emergence(reduction, cases, certified(cases))
        assert gate["verdict"] == "EMERGENT", gate
        assert DECISIVE[function] in gate["beaten_on"]                 # a frozen case, not a lucky random one
        assert gate["construction_certified"] == gate["cases"] == len(cases)
        assert gate["baseline_matched"] + len(gate["beaten_on"]) == len(cases)
        assert gate["baseline"] == reduction.baseline and len(gate["baseline_digest"]) == 64


def test_the_traps_are_the_stated_weakness_proved_by_brute_force():
    staffing = recombine.REDUCTIONS["assignment.staffing"]
    [trap] = recombine.trap_cases(staffing)
    p = staffing.normalize(trap["input"])
    assert trap["expected"] == {"staffed": 2} and recombine.baseline_staffing(p) == {"staffed": 1}
    crash = recombine.REDUCTIONS["project.crash"]
    [trap] = recombine.trap_cases(crash)
    p = crash.normalize(trap["input"])
    assert trap["expected"] == {"feasible": True, "cost": 3}                 # shorten the shared Site once
    assert recombine.baseline_crash(p) == {"feasible": True, "cost": 4}      # shortens East, then West


@pytest.mark.parametrize("function", sorted(DECISIVE))
def test_no_baseline_ever_claims_more_than_the_exact_answer(function):
    """The baselines are honest alternatives: each answer is achievable, so a loss is a real shortfall."""
    reduction = recombine.REDUCTIONS[function]
    spec = reduction.emergence
    for seed in range(40):
        for case in frozen(reduction, seed):
            got, best = spec.baseline(reduction.normalize(case["input"])), case["expected"]
            if function == "project.crash":
                assert not got["feasible"] or (best["feasible"] and got["cost"] >= best["cost"]), (seed, case)
            else:
                key = next(iter(best))
                assert got[key] <= best[key], (seed, case["name"])


def test_a_baseline_that_reaches_the_exact_answer_everywhere_is_integration():
    staffing = recombine.REDUCTIONS["assignment.staffing"]
    exact = replace(staffing, emergence=replace(staffing.emergence, baseline=recombine.expect_staffing))
    cases = frozen(exact)
    gate = recombine.emergence(exact, cases, certified(cases))
    assert gate["verdict"] == "INTEGRATION" and gate["beaten_on"] == []
    assert gate["why"].startswith("the baseline reaches the exact answer on every frozen case")


def test_no_runnable_baseline_is_integration():
    bare = replace(recombine.REDUCTIONS["selection.closure"], emergence=None)
    cases = frozen(bare)
    gate = recombine.emergence(bare, cases, certified(cases))
    assert gate["verdict"] == "INTEGRATION" and gate["why"].startswith("no runnable baseline")


def test_a_baseline_that_cannot_run_is_integration_not_a_win():
    selection = recombine.REDUCTIONS["selection.closure"]

    def broken(p):
        raise KeyError("profit")
    gate = recombine.emergence(replace(selection, emergence=replace(selection.emergence, baseline=broken)),
                               frozen(selection), certified(frozen(selection)))
    assert gate["verdict"] == "INTEGRATION" and gate["why"].startswith("the baseline could not run on ")


def test_a_construction_worse_than_its_baseline_or_uncertified_is_integration():
    matching = recombine.REDUCTIONS["assignment.matching"]
    cases = frozen(matching)
    answers = certified(cases)
    i = next(k for k, c in enumerate(cases) if c["name"] == "no-pairs")      # greedy reaches size 0 there
    answers[i] = {**answers[i], "size": answers[i]["size"] + 1}
    gate = recombine.emergence(matching, cases, answers)
    assert gate["verdict"] == "INTEGRATION" and gate["baseline_better_on"] == ["no-pairs"]
    answers = certified(cases)
    answers[0] = {**answers[0], "certified": False}
    gate = recombine.emergence(matching, cases, answers)
    assert gate["verdict"] == "INTEGRATION" and gate["why"] == "the construction is not certified exact on every case"


# -- through Genesis, on a real body ------------------------------------------------------------

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg.body import Body  # noqa: E402
from greg.templates import constructed_question  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed  # noqa: E402
from tests.unit.test_greg_recombine import STAFFING, routes, ticks  # noqa: E402


def verified(body, function):
    return [e.payload for e in body.journal.replay("genesis.verified")
            if e.payload["capability_id"].startswith(f"composed.{function}.")]


def test_genesis_registers_a_construction_with_its_measured_emergence(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", constructed_question(function="assignment.staffing",
                                                                    params=STAFFING, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
        [record] = verified(body, "assignment.staffing")
        gate = record["report"]["emergence"]
        assert record["passed"] and gate["verdict"] == "EMERGENT"
        assert DECISIVE["assignment.staffing"] in gate["beaten_on"] and record["report"]["traps"] == 1
        [cid] = [c for c in body.registry.manifests if c.startswith("composed.assignment.staffing.")]
        assert body.registry.manifests[cid].provenance["qualification"]["emergence"]["verdict"] == "EMERGENT"


def test_genesis_refuses_a_construction_that_only_matches_its_baseline_and_registers_nothing(tmp_path, monkeypatch):
    staffing = recombine.REDUCTIONS["assignment.staffing"]
    monkeypatch.setitem(recombine.REDUCTIONS, "assignment.staffing",
                        replace(staffing, emergence=replace(staffing.emergence, baseline=recombine.expect_staffing)))
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", constructed_question(function="assignment.staffing",
                                                                    params=STAFFING, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert ticks(body, clock, 2)[-1]["state"] in ("BLOCKED", "WAITING")
        [record] = verified(body, "assignment.staffing")
        assert not record["passed"] and record["report"]["failures"] == []
        assert record["report"]["emergence"]["verdict"] == "INTEGRATION"
        reasons = [result for route, result in routes(body) if route == "constructed"]
        assert "refused as integration: the baseline reaches the exact answer on every frozen case: nothing is " \
               "shown to emerge" in reasons
        assert "failed qualification" not in reasons
        assert not [c for c in body.registry.manifests if c.startswith("composed.")]
