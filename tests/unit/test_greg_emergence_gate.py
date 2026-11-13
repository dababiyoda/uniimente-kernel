"""Directive section 20 (S20.A2): a recombination states what it does that no source does alone and beats its
baseline, or is refused as integration.

Every reduction's stated `baseline` runs (greedy staffing, greedy matching, trial-and-error crashing, greedy
selection, dropping the costliest cost from the uncapped best). On the frozen cases, the construction's oracle cases
and the traps built to each baseline's stated weakness, a construction qualifies only when it states its claim, every
answer is certified exact, and the baseline misses the exact answer on at least one case.

Two different refusals follow. A construction that answers a case wrong (including where its baseline is right, or
uncertified) already fails its oracle: Genesis records "failed qualification". One that answers every case right but
shows nothing emergent (no stated claim, no runnable or a broken baseline, or a baseline that reaches the exact answer
everywhere) is recorded "failed the emergence gate, refused as integration: <why>", on every later tick too. Either
way nothing is registered. The gate's own identity (claim, baseline, oracle, traps) is kept with the qualification, so
a restore re-gates a construction qualified under a different gate.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from greg import recombine

DECISIVE = {"assignment.staffing": "trap:first-come-takes-the-flexible-worker", "assignment.matching": "perfect",
            "project.crash": "trap:shared-predecessor", "selection.closure": "shared-prerequisite",
            "selection.budgeted": "trap:costliest-cost-pays-most"}


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
        assert gate["spec_digest"] == recombine.emergence_digest(reduction) and len(gate["spec_digest"]) == 64


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
    budgeted = recombine.REDUCTIONS["selection.budgeted"]
    [trap] = recombine.trap_cases(budgeted)
    p = budgeted.normalize(trap["input"])
    assert trap["expected"] == {"profit": 14}                                # Anchor with its Plant fits the cap
    assert recombine.baseline_budgeted(p) == {"profit": 1}                  # dropping Plant drops Anchor


def test_the_budgeted_baseline_is_not_a_straw_man():
    """Dropping costs keeps no cost that nothing needs, and never ends below the empty plan, so it reaches the exact
    answer where a cheaper combination is not what the cap needs (the shared platform one unit short)."""
    budgeted = recombine.REDUCTIONS["selection.budgeted"]
    short = next(c for c in budgeted.oracle(0) if c["name"] == "shared-platform-short")
    assert recombine.baseline_budgeted(budgeted.normalize(short["input"])) == short["expected"]
    orphan = {"items": [{"id": "Kiosk", "value": 3}, {"id": "Store", "value": 11}, {"id": "Lease", "value": -4},
                        {"id": "Fitout", "value": -3}], "requires": [["Store", "Lease"], ["Store", "Fitout"]],
              "budget": 5}                  # dropping Lease drops Store; Fitout, needed by nothing kept, goes too
    assert recombine.baseline_budgeted(budgeted.normalize(orphan)) == {"profit": 3} == \
        {"profit": recombine.budgeted_brute_force(budgeted.normalize(orphan))}
    stranded = {"items": [{"id": "A", "value": 3}, {"id": "B", "value": 6}, {"id": "C", "value": 11},
                          {"id": "X", "value": -7}, {"id": "Y", "value": -4}, {"id": "Z", "value": -5}],
                "requires": [["A", "Y"], ["A", "Z"], ["B", "X"], ["C", "X"], ["C", "Y"], ["C", "Z"]], "budget": 11}
    assert recombine.baseline_budgeted(budgeted.normalize(stranded)) == {"profit": 0}   # A alone would be -6
    for seed in range(40):
        for case in frozen(budgeted, seed):
            assert recombine.baseline_budgeted(budgeted.normalize(case["input"]))["profit"] >= 0


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


def test_a_construction_that_does_not_state_its_claim_is_integration():
    closure = recombine.REDUCTIONS["selection.closure"]
    mute = replace(closure, emergence=replace(closure.emergence, claim="  "))
    cases = frozen(mute)
    gate = recombine.emergence(mute, cases, certified(cases))
    assert gate["verdict"] == "INTEGRATION" and gate["why"].startswith("the construction does not state what it does")


def test_the_gate_identity_covers_claim_baseline_oracle_and_traps():
    staffing = recombine.REDUCTIONS["assignment.staffing"]
    spec, digest = staffing.emergence, recombine.emergence_digest(staffing)
    for changed in (replace(spec, claim=spec.claim + "."), replace(spec, baseline=recombine.expect_staffing),
                    replace(spec, agrees=recombine.agrees_profit), replace(spec, expect=recombine.baseline_staffing),
                    replace(spec, traps=())):
        assert recombine.emergence_digest(replace(staffing, emergence=changed)) != digest
    assert recombine.emergence_digest(replace(staffing, emergence=None)) is None
    cases = frozen(staffing)
    qualification = {"failures": [], "emergence": recombine.emergence(staffing, cases, certified(cases))}
    assert recombine.gate_current(qualification, staffing)
    assert not recombine.gate_current(qualification, replace(staffing, emergence=replace(spec, traps=())))
    assert not recombine.gate_current({"failures": []}, staffing)          # qualified before the gate existed
    assert not recombine.gate_current({**qualification, "emergence": {**qualification["emergence"],
                                                                     "verdict": "INTEGRATION"}}, staffing)


def test_only_a_construction_right_on_every_case_is_recorded_as_refused_by_the_gate():
    gate = {"verdict": "INTEGRATION", "why": "nothing is shown to emerge"}
    assert recombine.integration_refusal({"failures": [], "emergence": gate}) == \
        "failed the emergence gate, refused as integration: nothing is shown to emerge"
    assert recombine.integration_refusal({"failures": ["no-pairs"], "emergence": gate}) is None
    assert recombine.integration_refusal({"failures": [], "emergence": {"verdict": "EMERGENT"}}) is None
    assert recombine.integration_refusal(None) is None


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
        ticks(body, clock, 3)                       # later ticks reuse the record and must not relabel it
        reasons = [result for route, result in routes(body) if route == "constructed" and not
                   result.startswith("chain ")]
        why = "refused as integration: the baseline reaches the exact answer on every frozen case: nothing is " \
              "shown to emerge"
        assert reasons[0] == "failed the emergence gate, " + why and len(reasons) > 1
        assert set(reasons[1:]) == {"failed the emergence gate earlier on this deficit (recorded; not re-run), " + why}
        assert not [c for c in body.registry.manifests if c.startswith("composed.")]


def test_a_restore_re_gates_a_construction_qualified_under_a_different_gate(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", constructed_question(function="assignment.staffing",
                                                                    params=STAFFING, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
        [cid] = [c for c in body.registry.manifests if c.startswith("composed.assignment.staffing.")]
        state = body.registry.state[cid]
    with Body(home, clock=clock) as body:          # the same gate: trusted again as it was
        body.boot()
        assert body.registry.state[cid] == state != "QUARANTINED"
    staffing = recombine.REDUCTIONS["assignment.staffing"]
    monkeypatch.setitem(recombine.REDUCTIONS, "assignment.staffing",
                        replace(staffing, emergence=replace(staffing.emergence, traps=())))
    with Body(home, clock=clock) as body:          # a different gate: the same id, quarantined until re-gated
        body.boot()
        assert body.registry.state[cid] == "QUARANTINED"
        [why] = [e.payload["why"] for e in body.journal.replay("capability.state")
                 if e.payload["capability_id"] == cid and e.payload["state"] == "QUARANTINED"]
        assert why.startswith("qualified without the emergence gate its reduction states now")
