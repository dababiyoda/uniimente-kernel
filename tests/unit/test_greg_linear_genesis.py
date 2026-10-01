"""A linear plan in words, solved by an installed open-source engine and proved by GREG's duality certificate.

Second family on the open-source genesis route (founder correction 2026-10-01, #144). SciPy's
HiGHS and OR-Tools GLOP are untrusted: GREG checks primal feasibility, dual feasibility and a
zero duality gap itself. An engine's "infeasible" or "unbounded" carries no certificate through
these interfaces, so it is reported, never closed on.
"""
from __future__ import annotations

import random

import pytest

pytest.importorskip("scipy")
pytest.importorskip("ortools")

from greg import genesis as genesis_mod  # noqa: E402
from greg import mechanisms, planner  # noqa: E402
from greg.body import Body  # noqa: E402
from greg.capabilities import CapabilityError, CapabilityRegistry  # noqa: E402
from greg.cognition import linear  # noqa: E402
from greg.templates import plan_in_words, read_plan_words  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed  # noqa: E402

PLAN = ("Maximize 40 chairs + 30 tables. 2 chairs + 3 tables <= 120. 4 chairs + 2 tables at most 160. "
        "tables between 0 and 30.")


def candidate(distribution):
    return next(c for c in genesis_mod.CATALOG["lp.optimize"]["candidates"] if c.distribution == distribution)


def solve_with(distribution, params):
    c = candidate(distribution)
    card = mechanisms.card(c, "lp.optimize", mechanisms.installed(distribution))
    req = linear.normalize_lp(params)
    [claim] = mechanisms.run(c, linear.RUNNERS[c.runner], [req], location=card["location"], version=card["version"])
    return req, claim["result"]


def ticks(body, clock, n):
    out = []
    for _ in range(n):
        out.append(body.tick()["missions"][0])
        clock.advance(31)
    return out


@pytest.mark.parametrize("distribution", ["scipy", "ortools"])
def test_each_installed_lp_engine_qualifies_with_a_duality_certificate_at_the_size_limit(distribution):
    c = candidate(distribution)
    card = mechanisms.card(c, "lp.optimize", mechanisms.installed(distribution))
    passed, report = genesis_mod.qualify_package("lp.optimize", c, card, seed=20261001)
    assert passed, report["failures"]
    assert report["scale_probe"]["certified"] and report["scale_probe"]["variables"] == 500
    assert "exact fractions" in report["oracle"]


@pytest.mark.parametrize("distribution", ["scipy", "ortools"])
def test_both_engines_give_the_same_certified_plan_with_its_prices(distribution):
    req, claim = solve_with(distribution, read_plan_words(PLAN))
    answer = linear.certify_lp(req, claim)
    assert answer["objective"] == pytest.approx(1800)
    assert answer["values"] == pytest.approx({"chairs": 30, "tables": 20})
    assert answer["shadow_prices"] == pytest.approx({"2 chairs + 3 tables <= 120": 5,
                                                     "4 chairs + 2 tables at most 160": 7.5})


@pytest.mark.parametrize("distribution", ["scipy", "ortools"])
def test_a_price_is_the_change_in_the_stated_objective_per_unit_of_the_stated_limit(distribution):
    req, claim = solve_with(distribution, read_plan_words("Minimize 2 a + 3 b. a + b >= 5. a <= 3."))
    answer = linear.certify_lp(req, claim)
    assert answer["objective"] == pytest.approx(12)
    assert answer["shadow_prices"] == pytest.approx({"a + b >= 5": 3, "a <= 3": -1})   # demand costs; capacity saves


def test_a_worse_plan_an_infeasible_plan_and_forged_prices_are_refuted():
    req, claim = solve_with("scipy", read_plan_words(PLAN))
    with pytest.raises(linear.CertificateError, match="differ"):
        linear.certify_lp(req, {**claim, "x": [40.0, 0.0]})                      # feasible, worse: gap remains
    with pytest.raises(linear.CertificateError, match="violated"):
        linear.certify_lp(req, {**claim, "x": [60.0, 0.0]})                      # breaks a limit
    with pytest.raises(linear.CertificateError, match="wrong sign"):
        linear.certify_lp(req, {**claim, "y_ub": [-y for y in claim["y_ub"]]})
    with pytest.raises(linear.CertificateError, match="reproduce"):
        linear.certify_lp(req, {**claim, "y_ub": [claim["y_ub"][0], 0.0]})
    with pytest.raises(linear.CertificateError):
        linear.certify_lp(req, {**claim, "x": [30.0]})
    stated = linear.certify_lp(req, {"status": "unbounded"})
    assert stated["certified"] is False and "cannot prove" in stated["why"]


@pytest.mark.parametrize("seed", range(15))
def test_greg_oracle_and_an_engine_agree_on_random_bounded_programs(seed):
    case = linear.oracle_lp(seed)[-1]
    req, claim = solve_with("scipy", case["input"])
    answer = linear.certify_lp(req, claim)
    if answer.get("follow_up"):                                  # "no plan exists" must be proved, not relayed
        c = candidate("scipy")
        card = mechanisms.card(c, "lp.optimize", mechanisms.installed("scipy"))
        [extra] = mechanisms.run(c, linear.RUNNERS[c.runner], [answer["follow_up"]], location=card["location"],
                                 version=card["version"])
        answer = linear.follow_up_lp(req, answer, extra["result"])
    assert linear.judge_lp(answer, case["expected"])


@pytest.mark.parametrize("params, message", [
    ({"variables": [], "objective": {"sense": "max", "coefficients": {}}}, "variables required"),
    ({"variables": [{"name": "x"}], "objective": {"sense": "best", "coefficients": {"x": 1}}}, "sense"),
    ({"variables": [{"name": "x"}], "objective": {"sense": "max", "coefficients": {"y": 1}}}, "unknown variable"),
    ({"variables": [{"name": "x", "lower": 2, "upper": 1}], "objective": {"sense": "max", "coefficients": {}}},
     "lower bound above"),
    ({"variables": [{"name": "x"}], "objective": {"sense": "max", "coefficients": {"x": 1e12}}}, "1e9"),
])
def test_programs_outside_competence_are_refused_before_any_engine_runs(params, message):
    with pytest.raises(CapabilityError, match=message):
        linear.normalize_lp(params)


def test_words_become_a_read_only_plan_mission_and_unread_words_stop_it():
    ctx = planner.PlannerContext(read_roots=(), capabilities=CapabilityRegistry().inventory(), repositories={})
    proposal = planner.template_route(PLAN, ctx)
    assert proposal["status"] == "PROPOSED" and proposal["origin"] == "template:plan-in-words"
    assert proposal["spec"]["success_checks"][0]["sensor"]["function"] == "lp.optimize"
    assert any("nonnegative" in n for n in proposal["notes"])
    unread = planner.template_route("Maximize joy. Be kind. joy <= 3.", ctx)
    assert unread["status"] == "NEEDS_INPUT" and "Be kind" in unread["questions"][0]


def test_a_plan_mission_closes_on_a_certified_optimum_from_a_formed_capability(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", plan_in_words(text=PLAN, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
        routes = [(e.payload["route"], e.payload["result"]) for e in body.journal.replay("genesis.route")]
        assert ("installed_package", "acquired") in routes
        assert any(k == "existing_project" and "integer" in r for k, r in routes)
        [answer] = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                    if isinstance(r.payload["result"].get("output"), dict)
                    and r.payload["result"]["output"].get("certified")][-1:]
        assert answer["objective"] == pytest.approx(1800) and answer["authority_created"] is False
        assert body.journal.replay("mission.appraised")[-1].payload["verdict"] == "VERIFIED"


def test_an_impossible_plan_closes_only_on_a_proof_that_names_the_conflicting_limits(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", plan_in_words(text="Maximize x. x >= 5. x <= 3.", auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 4)]
        [answer] = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                    if isinstance(r.payload["result"].get("output"), dict)
                    and r.payload["result"]["output"].get("certified")][-1:]
        assert answer["status"] == "infeasible" and answer["least_total_violation"] == pytest.approx(2)
        assert answer["conflicting"] == ["x <= 3", "x >= 5"] and "follow_up" not in answer


@pytest.mark.parametrize("distribution", ["scipy", "ortools"])
def test_no_plan_is_proved_with_the_least_violation_and_a_false_no_plan_is_refuted(distribution):
    req, claim = solve_with(distribution, read_plan_words("Minimize a + b. a + b = 3. a + b >= 5. a <= 4."))
    stated = linear.certify_lp(req, claim)
    assert stated["status"] == "infeasible" and stated["certified"] is False and stated["follow_up"]["elastic"]
    c = candidate(distribution)
    card = mechanisms.card(c, "lp.optimize", mechanisms.installed(distribution))
    [extra] = mechanisms.run(c, linear.RUNNERS[c.runner], [stated["follow_up"]], location=card["location"],
                             version=card["version"])
    proof = linear.follow_up_lp(req, stated, extra["result"])
    assert proof["certified"] and proof["least_total_violation"] == pytest.approx(2)
    assert set(proof["conflicting"]) == {"a + b = 3", "a + b >= 5"}
    feasible_req, feasible_claim = solve_with(distribution, read_plan_words(PLAN))
    lie = linear.certify_lp(feasible_req, {"status": "infeasible"})          # the engine claims no plan exists
    [extra] = mechanisms.run(c, linear.RUNNERS[c.runner], [lie["follow_up"]], location=card["location"],
                             version=card["version"])
    with pytest.raises(linear.CertificateError, match="a plan meets every limit"):
        linear.follow_up_lp(feasible_req, lie, extra["result"])


def test_greg_vertex_oracle_is_exact():
    rng = random.Random(3)
    for _ in range(20):
        lo = rng.randint(-3, 0)
        params = {"variables": [{"name": "a", "lower": lo, "upper": lo + 4}, {"name": "b", "lower": 0, "upper": 5}],
                  "objective": {"sense": "max", "coefficients": {"a": rng.randint(-3, 3), "b": rng.randint(-3, 3)}},
                  "constraints": [{"coefficients": {"a": 1, "b": 1}, "op": "<=", "rhs": rng.randint(-2, 8)}]}
        expected = linear.vertex_enumeration(linear.normalize_lp(params))
        best = None                                                   # brute force over a fine rational grid
        for i in range(0, 41):
            for j in range(0, 51):
                a, b = lo + i / 10, j / 10
                if a + b <= params["constraints"][0]["rhs"] + 1e-12:
                    v = params["objective"]["coefficients"]["a"] * a + params["objective"]["coefficients"]["b"] * b
                    best = v if best is None else max(best, v)
        if best is None:
            assert expected["status"] == "infeasible"
        else:
            assert float(expected["objective"]) == pytest.approx(best)


def test_an_engine_that_falsely_says_no_plan_exists_is_refuted_quarantined_and_replaced(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", plan_in_words(text=PLAN, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 1)                                       # honest qualification; read-only auto-attach
        assert body.registry.state["acquired.lp.optimize.scipy"] == "ATTACHED"
        lie = linear.RUNNERS["scipy.lp"].replace(
            "def solve(req):\n", 'def solve(req):\n    if not req.get("elastic"):\n        return {"status": "infeasible"}\n', 1)
        monkeypatch.setitem(linear.RUNNERS, "scipy.lp", lie)        # in service, the engine denies any plan exists
        states = [s["state"] for s in ticks(body, clock, 8)]
        assert "ACHIEVED" in states, states
        [quarantined] = [e.payload for e in body.journal.replay("capability.state")
                         if e.payload["state"] == "QUARANTINED"]
        assert quarantined["capability_id"] == "acquired.lp.optimize.scipy"
        assert "a plan meets every limit" in quarantined["why"]
        answers = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                   if isinstance(r.payload["result"].get("output"), dict)
                   and r.payload["result"]["output"].get("certified")]
        assert answers and all(a["status"] == "optimal" for a in answers)     # the false "no plan" was never accepted
        assert answers[-1]["engine"].startswith("ortools ") and answers[-1]["objective"] == pytest.approx(1800)
