"""Settled construction outcomes reach a later compile decision; a relaxed construction may not win it.

Since be58b2b5 a construction's verified answer settles (``test_greg_construction_settlement.py``). Settled
competence then enters the Competency Compiler's evidence ranking (``_rank``, Laplace competence, pooled over a
method's geometries as ``_settled_counts`` states). On 9e12b9a6 the first decision that construction outcomes
changed on the mission path was wrong: two uncapped portfolio answers by ``selection.closure`` ranked it ahead of
``selection.budgeted`` for a capped request, and "Spend at most 5" was ANSWERED with a plan spending 9 (profit 6),
certified by the closure's own certificate, achieved and settled as correct. With construction settlement ablated
the same sequence chose ``selection.budgeted`` (profit 4, spend 2). The closure was eligible at all because
``constructed_candidates`` did not apply the relaxation rule that catalogued methods meet (``_reject_relaxations``).

Rule kept here: a construction whose inputs are a strict subset of another fitting reduction's answers a
relaxation and is rejected, attached or not. Settled outcomes still reorder the ranking; they can no longer route a
capped question to a construction that ignores the cap. No threshold, authority or signature changes. The founder
key is a per-test Ed25519 key.
"""
from __future__ import annotations

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg.body import Body  # noqa: E402
from greg.cognition import compiler, settlement  # noqa: E402

from greg.templates import compiled_question  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed  # noqa: E402
from tests.unit.test_greg_budgeted_selection import FLIP  # noqa: E402
from tests.unit.test_greg_recombine import PORTFOLIO  # noqa: E402

COSTS = {i["id"]: -i["value"] for i in FLIP["items"] if i["value"] < 0}


class Run:
    def __init__(self, tmp_path):
        self.home, self.key, self.body_id, _ = make_body(tmp_path)
        self.clock = Clock()
        self.body = Body(self.home, clock=self.clock)

    def __enter__(self):
        self.body.__enter__()
        self.body.boot()
        return self

    def __exit__(self, *exc):
        self.body.__exit__(*exc)

    def ask(self, pid, data, n=8):
        spec = compiled_question(problem_id=pid, data=data, allow_construction=True, objective="which offers to take")
        drop(self.home, signed(self.key, self.body_id, "MISSION", spec))
        for _ in range(n):
            self.body.tick()
            self.clock.advance(31)
        assert self.body.engine.book.missions[spec["mission_id"]].status == "ACHIEVED"
        [answered] = [o for o in self.compiles(pid) if o["state"] == "ANSWERED"]
        return answered

    def compiles(self, pid):
        return [r.payload["result"]["output"] for r in self.body.ledger.by_type("receipt")
                if isinstance(r.payload["result"].get("output"), dict)
                and r.payload["result"]["output"].get("schema") == compiler.SCHEMA
                and r.payload["result"]["output"].get("problem_id") == pid]

    def construction(self, function):
        return next(e.payload["manifest"]["capability_id"] for e in self.body.journal.replay("capability.registered")
                    if (e.payload.get("origin") or {}).get("kind") == "composed"
                    and e.payload["manifest"]["capability_id"].startswith(f"composed.{function}."))


def within_cap(receipt):
    answer = receipt["result"]
    spend = sum(COSTS.get(i, 0) for i in answer["chosen"])
    return spend <= FLIP["budget"], spend, answer["profit"]


def test_settled_construction_outcomes_reorder_the_ranking_and_the_relaxation_cannot_win_the_capped_question(
        tmp_path, monkeypatch):
    with Run(tmp_path) as run:
        first = run.ask("capped-0", FLIP)                      # forms selection.budgeted; no closure yet
        budgeted = run.construction("selection.budgeted")
        assert first["method_or_composition_selected"] == budgeted
        run.ask("uncapped-1", PORTFOLIO)                       # forms selection.closure, which answers both
        run.ask("uncapped-2", PORTFOLIO)
        closure = run.construction("selection.closure")
        settled = compiler._settled_counts(run.body.journal)
        assert settled[closure] == (2, 2) and settled[budgeted] == (1, 1)

        # The settled outcomes change the evidence ranking between the two attached constructions ...
        rows = {r["method"]: r for r in compiler.constructed_candidates(
            FLIP, compiler.CompetencyGeometry(geometry="optimization"), run.body.registry)}
        competence = compiler._settled_competence(run.body.journal, "optimization")
        assert competence[closure] > competence[budgeted]
        order = sorted(rows.values(), key=lambda r: compiler._rank(r, [], competence))
        assert order[0]["method"] == closure
        # ... and only because construction outcomes settle: ablated as before be58b2b5, the tie stands.
        with monkeypatch.context() as m:
            m.setattr(settlement, "_constructed", lambda value, constructed: None)
            ablated = compiler._settled_competence(run.body.journal, "optimization")
            assert closure not in ablated and budgeted not in ablated
            assert sorted(rows.values(), key=lambda r: compiler._rank(r, [], ablated))[0]["method"] == budgeted

        # The closure ignores the cap, so it is rejected and the capped question keeps its correct answer.
        later = run.ask("capped-2", FLIP)
        ok, spend, profit = within_cap(later)
        assert ok and (spend, profit) == (2, 4), \
            f"{later['method_or_composition_selected']} answered the capped question spending {spend}"
        assert later["method_or_composition_selected"] == budgeted
        assert any(r["method"] == closure and "relaxation" in r["why"] for r in later["methods_rejected"])
        assert rows[closure]["rejected"].startswith("answers a relaxation: ignores declared inputs ['budget']")
        assert rows[budgeted]["rejected"] is None
        assert compiler._settled_counts(run.body.journal)[closure] == (2, 2)   # it answered no capped question


def test_a_capped_question_after_an_uncapped_one_constructs_the_capped_capability_instead_of_the_relaxed_answer(
        tmp_path):
    with Run(tmp_path) as run:
        run.ask("uncapped-1", PORTFOLIO)
        closure = run.construction("selection.closure")
        receipt = run.ask("capped-1", FLIP, n=10)
        # On 9e12b9a6 the attached closure answered here: profit 6, spending Kit and Plant (9 > 5), ACHIEVED.
        ok, spend, profit = within_cap(receipt)
        assert ok and (spend, profit) == (2, 4), \
            f"{receipt['method_or_composition_selected']} answered the capped question spending {spend}"
        assert receipt["method_or_composition_selected"] == run.construction("selection.budgeted") != closure
        deficits = [o["capability_deficit"] for o in run.compiles("capped-1") if o["state"] == "CAPABILITY_DEFICIT"]
        assert deficits and all(d["function"] == "selection.budgeted"
                                and "selection.closure" not in d.get("constructible", {}).get("alternatives", [])
                                for d in deficits)
        assert compiler._settled_counts(run.body.journal)[closure] == (1, 1)    # the relaxed answer never settled
