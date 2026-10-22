"""Who does which job, in words, solved by an installed open-source engine and proved by GREG.

Third family on the open-source genesis route (#144). SciPy's linear_sum_assignment and OR-Tools'
SimpleLinearSumAssignment are untrusted: GREG checks that no exchange of jobs improves the total
(no negative cycle in the residual graph) and proves "no full assignment exists" by Hall's
condition, naming the people whose allowed jobs are too few.
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
from greg.cognition import assignment  # noqa: E402
from greg.templates import assignment_in_words, read_assignment_words  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed  # noqa: E402

WORDS = ("Ana on Painting: 4. Ana on Wiring: 7. Ben on Painting: 3. Ben on Wiring: 5 hours. Ben on Tiling: 6. "
         "Cara on Wiring: 2. Cara on Tiling: 8. Cheapest assignment.")
SHORT = ("Ana on Painting: 4. Ben on Painting: 3. Ben on Wiring: 5. Ben on Tiling: 2. Cara on Painting: 1. "
         "Cheapest assignment.")


def candidate(distribution):
    return next(c for c in genesis_mod.CATALOG["assignment.optimize"]["candidates"] if c.distribution == distribution)


def solve_with(distribution, params):
    c = candidate(distribution)
    card = mechanisms.card(c, "assignment.optimize", mechanisms.installed(distribution))
    req = assignment.normalize_assignment(params)
    [claim] = mechanisms.run(c, assignment.RUNNERS[c.runner], [req], location=card["location"],
                             version=card["version"])
    return req, claim["result"]


def ticks(body, clock, n):
    out = []
    for _ in range(n):
        out.append(body.tick()["missions"][0])
        clock.advance(31)
    return out


def certified_answers(body):
    return [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
            if isinstance(r.payload["result"].get("output"), dict) and r.payload["result"]["output"].get("certified")]


@pytest.mark.parametrize("distribution", ["scipy", "ortools"])
def test_each_installed_engine_qualifies_on_greg_oracle_and_at_the_size_limit(distribution):
    c = candidate(distribution)
    card = mechanisms.card(c, "assignment.optimize", mechanisms.installed(distribution))
    passed, report = genesis_mod.qualify_package("assignment.optimize", c, card, seed=20261013)
    assert passed, report["failures"]
    assert report["scale_probe"]["certified"] and report["scale_probe"]["rows"] == assignment.MAX_SIDE
    assert report["scale_probe"]["agrees_with_local"] and "brute force" in report["oracle"]


@pytest.mark.parametrize("distribution", ["scipy", "ortools"])
def test_both_engines_give_the_same_certified_assignment(distribution):
    req, claim = solve_with(distribution, read_assignment_words(WORDS))
    answer = assignment.certify_assignment(req, claim)
    assert answer["total"] == 12
    assert answer["assignment"] == [["Ana", "Painting", 4], ["Ben", "Tiling", 6], ["Cara", "Wiring", 2]]
    prices = answer["certificate"]["dual_prices"]
    assert set(prices["rows"]) == {"Ana", "Ben", "Cara"}


@pytest.mark.parametrize("distribution", ["scipy", "ortools"])
def test_no_full_assignment_is_proved_by_naming_who_is_short_of_jobs(distribution):
    req, claim = solve_with(distribution, read_assignment_words(SHORT))
    assert claim["status"] == "infeasible"
    answer = assignment.certify_assignment(req, claim)
    assert answer["status"] == "infeasible"
    assert answer["rows_in_conflict"] == ["Ana", "Cara"] and answer["columns_they_allow"] == ["Painting"]


def test_a_worse_assignment_a_forbidden_pair_a_shared_job_and_a_false_no_assignment_are_refuted():
    req = assignment.normalize_assignment(read_assignment_words(WORDS))
    best = [[0, 0], [1, 2], [2, 1]]
    assert assignment.certify_assignment(req, {"status": "optimal", "pairs": best})["total"] == 12
    for pairs, why in [([[0, 1], [1, 0], [2, 2]], "cheaper exchange"),     # valid but 18
                       ([[0, 2], [1, 0], [2, 1]], "not an allowed pair"),  # Ana cannot tile
                       ([[0, 0], [1, 0], [2, 1]], "used twice"),
                       ([[0, 0], [2, 1]], "one \\[row, column\\] pair per row")]:
        with pytest.raises(assignment.CertificateError, match=why):
            assignment.certify_assignment(req, {"status": "optimal", "pairs": pairs})
    with pytest.raises(assignment.CertificateError, match="but one does"):
        assignment.certify_assignment(req, {"status": "infeasible"})


def test_a_free_job_that_is_cheaper_is_an_improving_exchange():
    req = assignment.normalize_assignment({"costs": [[5, 1, 9], [1, 9, 9]]})
    with pytest.raises(assignment.CertificateError, match="cheaper exchange"):
        assignment.certify_assignment(req, {"status": "optimal", "pairs": [[0, 0], [1, 1]]})   # 14; best is 2
    # Only a move to the free job improves this one; no exchange between assigned rows exists.
    lone = assignment.normalize_assignment({"costs": [[5, 1]]})
    with pytest.raises(assignment.CertificateError, match="cheaper exchange"):
        assignment.certify_assignment(lone, {"status": "optimal", "pairs": [[0, 0]]})
    assert assignment.certify_assignment(lone, {"status": "optimal", "pairs": [[0, 1]]})["free_columns"] == ["column1"]


@pytest.mark.parametrize("seed", range(4))
def test_greg_oracle_and_an_engine_agree_on_random_problems(seed):
    rng = random.Random(seed)
    for _ in range(6):
        n = rng.randint(1, 6)
        m = rng.randint(n, 7)
        params = {"costs": [[None if rng.random() < 0.25 else rng.randint(-5, 20) for _ in range(m)]
                            for _ in range(n)], "maximize": rng.random() < 0.3}
        req, claim = solve_with("scipy", params)
        answer = assignment.certify_assignment(req, claim)
        assert assignment.judge_assignment(answer, assignment.brute_force(req))


@pytest.mark.parametrize("params, message", [
    ({"costs": [[1, 2], [3, 4], [5, 6]]}, "every row needs its own column"),
    ({"costs": [[1, 2], [3]]}, "same number of columns"),
    ({"costs": [[0.1234567]]}, "six decimal places"),
    ({"costs": [[2e9]]}, "exceeds 1e9"),
    ({"costs": [[float("nan")]]}, "not finite"),
    ({"costs": [[True]]}, "not a number"),
    ({"costs": [[1] * 121]}, "more than 120 columns"),
    ({"costs": [[1, 2]], "rows": ["a", "b"]}, "row names"),
])
def test_problems_outside_competence_are_refused_before_any_engine_runs(params, message):
    with pytest.raises(CapabilityError, match=message):
        assignment.normalize_assignment(params)


def test_words_become_a_read_only_assignment_mission_and_unread_words_stop_it():
    ctx = planner.PlannerContext(read_roots=(), capabilities=CapabilityRegistry().inventory(), repositories={})
    proposal = planner.template_route(WORDS, ctx)
    assert proposal["status"] == "PROPOSED" and proposal["origin"] == "template:assignment-in-words"
    assert proposal["spec"]["light_cone"]["max_consequence_class"] == "read_only"
    assert any("not allowed" in n for n in proposal["notes"])
    unread = planner.template_route("Ana on Painting: 4. Be nice. Cheapest assignment.", ctx)
    assert unread["status"] == "NEEDS_INPUT" and "Be nice" in unread["questions"][0]
    with pytest.raises(ValueError, match="also said to be impossible"):
        read_assignment_words("Ana on Painting: 4. Ana cannot do Painting. Cheapest assignment.")
    assert read_assignment_words("Ana on X: 9. Ana on Y: 2. Most valuable assignment.")["maximize"] is True


def test_an_assignment_mission_closes_on_a_certified_answer_from_a_formed_capability(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", assignment_in_words(text=WORDS, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
        routes = [(e.payload["route"], e.payload["result"]) for e in body.journal.replay("genesis.route")]
        assert ("installed_package", "acquired") in routes
        answer = certified_answers(body)[-1]
        assert answer["total"] == 12 and answer["authority_created"] is False and answer["license"]
        assert body.journal.replay("mission.appraised")[-1].payload["verdict"] == "VERIFIED"


def test_an_impossible_assignment_closes_only_on_a_proof_that_names_who_is_short(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", assignment_in_words(text=SHORT, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert "ACHIEVED" in [s["state"] for s in ticks(body, clock, 3)]
        answer = certified_answers(body)[-1]
        assert answer["status"] == "infeasible" and answer["rows_in_conflict"] == ["Ana", "Cara"]


def test_an_engine_that_falsely_says_no_assignment_exists_is_refuted_quarantined_and_replaced(tmp_path, monkeypatch):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", assignment_in_words(text=WORDS, auto_attach=True)))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        ticks(body, clock, 1)                                       # honest qualification; read-only auto-attach
        assert body.registry.state["acquired.assignment.optimize.scipy"] == "ATTACHED"
        lie = assignment.RUNNERS["scipy.assignment"].replace(
            "def solve(req):\n", 'def solve(req):\n    return {"status": "infeasible"}\n', 1)
        monkeypatch.setitem(assignment.RUNNERS, "scipy.assignment", lie)
        states = [s["state"] for s in ticks(body, clock, 8)]
        assert "ACHIEVED" in states, states
        [quarantined] = [e.payload for e in body.journal.replay("capability.state")
                         if e.payload["state"] == "QUARANTINED"]
        assert quarantined["capability_id"] == "acquired.assignment.optimize.scipy"
        answers = certified_answers(body)
        assert answers and all(a["status"] == "optimal" for a in answers)
        assert answers[-1]["engine"].startswith("ortools ") and answers[-1]["total"] == 12
