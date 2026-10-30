"""A construction's answer can settle as wrong in the world, and such outcomes can change a later compile.

Before this, a construction's certified answer settled only through its own certificate
(``test_greg_construction_settlement.py``), so its settled outcome was always correct and no outcome could make a
later compile prefer another fit. A signed REALIZATION now binds the realized value of the objective the answer
promised (the profit of a chosen portfolio) to that answer's receipt. Rule kept: the realized objective is compared
with the promised one under the tolerance declared in code (``settlement.REALIZATION_RELATIVE_TOLERANCE``); worse by
more than it is wrong in the world, which is evidence about the method on this geometry, not a refuted certificate.
One fact per receipt; a repeat is idempotent and a different value is a conflict scored as neither. The world
verdict supersedes the certificate's for competence and both stay on the record.

The realized values here are synthetic test inputs, not real-world outcomes. The founder key is a per-test Ed25519
key. The end-to-end test fixes frozen evidence (``flow_maxflow`` read as EXPERIMENTAL) so the construction ranks
first on a request carrying both shapes' inputs: it tests the routing mechanism, not a natural competition.
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg.body import Body  # noqa: E402
from greg.cognition import compiler, settlement  # noqa: E402
from greg.cognition.genomes.flow import maxflow_instance  # noqa: E402
from greg.templates import compiled_question  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, signed  # noqa: E402
from tests.unit.test_greg_recombine import PORTFOLIO  # noqa: E402

PROMISED = 2                      # the best PORTFOLIO profit (Offer1, Offer2, Platform, Audit)


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

    def command(self, kind, body):
        return self.body.apply(signed(self.key, self.body_id, kind, body))

    def ask(self, pid, data, allow=True, n=8):
        """One signed compiled question; the ledger receipt that carries its ANSWERED compile receipt."""
        spec = compiled_question(problem_id=pid, data=data, allow_construction=allow, objective="which to take")
        drop(self.home, signed(self.key, self.body_id, "MISSION", spec))
        for _ in range(n):
            self.body.tick()
            self.clock.advance(31)
            if self.body.engine.book.missions[spec["mission_id"]].status == "ACHIEVED":
                break
        assert self.body.engine.book.missions[spec["mission_id"]].status == "ACHIEVED"
        [record] = [r for r in self.body.ledger.by_type("receipt")
                    if isinstance(r.payload["result"].get("output"), dict)
                    and r.payload["result"]["output"].get("schema") == compiler.SCHEMA
                    and r.payload["result"]["output"].get("problem_id") == pid
                    and r.payload["result"]["output"]["state"] == "ANSWERED"]
        return record

    def realize(self, record, value, source="external_record"):
        return self.command("REALIZATION", {"receipt": record.hash, "realized": value, "source": source})

    def outcome(self, record):
        return next((o for o in settlement.measured_outcomes(self.body.journal) if o["receipt"] == record.hash), None)


def construction_id(body):
    return next(e.payload["manifest"]["capability_id"] for e in body.journal.replay("capability.registered")
                if (e.payload.get("origin") or {}).get("kind") == "composed")


def test_a_realization_short_of_the_promise_settles_the_construction_wrong_and_one_within_tolerance_correct(tmp_path):
    with Run(tmp_path) as run:
        short, kept = run.ask("pf-short", PORTFOLIO), run.ask("pf-kept", PORTFOLIO)
        cid = construction_id(run.body)
        assert short.payload["result"]["output"]["result"]["profit"] == PROMISED
        assert compiler._settled_counts(run.body.journal)[cid] == (2, 2)        # certificates alone: always correct
        settlement.reconcile(run.body.journal)
        applied = run.realize(short, PROMISED - 1)                              # 1 below: beyond 0.05 x max(2, 1)
        assert applied["status"] == "APPLIED" and applied["result"]["met"] is False
        assert run.realize(kept, PROMISED - 0.05)["result"]["met"] is True      # within the declared tolerance
        wrong, right = run.outcome(short), run.outcome(kept)
        assert wrong["correct"] is False and wrong["certificate_correct"] is True
        assert wrong["world"] == {**wrong["world"], "objective": "profit", "sense": "max", "promised": PROMISED,
                                  "realized": PROMISED - 1, "met": False, "source": "external_record"}
        assert right["correct"] is True and right["world"]["met"] is True
        assert compiler._settled_counts(run.body.journal)[cid] == (2, 1)
        settlement.reconcile(run.body.journal)                                 # a revision, the first fact kept
        facts = [e.payload for e in run.body.journal.replay("cognition.settled") if e.payload["receipt"] == short.hash]
        assert [f["correct"] for f in facts] == [True, False] and facts[1]["supersedes"]
        settlement.reconcile(run.body.journal)                                 # replay-safe: nothing more
        assert len([e for e in run.body.journal.replay("cognition.settled")
                    if e.payload["receipt"] == short.hash]) == 2
        assert all(e.payload["authority_created"] is False for e in run.body.journal.replay("cognition.realization"))


def test_one_realization_per_receipt_a_repeat_is_idempotent_and_a_different_value_is_scored_as_neither(tmp_path):
    with Run(tmp_path) as run:
        first, second = run.ask("pf-a", PORTFOLIO), run.ask("pf-b", PORTFOLIO)
        cid = construction_id(run.body)
        run.realize(first, 0)
        run.realize(first, 0)                                                  # same value and source: idempotent
        assert len(list(run.body.journal.replay("cognition.realization"))) == 1
        run.realize(first, 0, source="founder_reported")                       # same value, another source: kept as
        assert len(list(run.body.journal.replay("cognition.realization"))) == 2    # corroboration (2026-10-28)
        assert run.outcome(first)["correct"] is False
        run.realize(second, PROMISED)
        assert compiler._settled_counts(run.body.journal)[cid] == (2, 1)
        conflict = run.realize(first, PROMISED)                                # a different value for one receipt
        assert conflict["status"] == "APPLIED"
        facts = [e.payload for e in run.body.journal.replay("cognition.realization") if e.payload["receipt"] == first.hash]
        assert len(facts) == 3 and facts[1]["corroborates"] and facts[2]["conflicts_with"]
        assert run.outcome(first) is None                                      # neither correct nor wrong
        assert compiler._settled_counts(run.body.journal)[cid] == (1, 1)
        run.realize(first, PROMISED)                                           # the conflict itself is idempotent
        assert len(list(run.body.journal.replay("cognition.realization"))) == 4


def test_a_realization_is_refused_on_an_unknown_or_unanswered_receipt_and_on_a_non_numeric_value(tmp_path):
    with Run(tmp_path) as run:
        record = run.ask("pf-1", PORTFOLIO)
        bound = settlement.record_realization(run.body.journal, receipt=record.hash, realized=PROMISED,
                                              source="sensor_observation")
        assert bound["kind"] == "objective" and bound["met"] is True and bound["authority_created"] is False
        deficit = next(r for r in run.body.ledger.by_type("receipt")
                       if isinstance(r.payload["result"].get("output"), dict)
                       and r.payload["result"]["output"].get("state") == "CAPABILITY_DEFICIT")
        for receipt in ("sha256:" + "0" * 64, deficit.hash):
            with pytest.raises(ValueError, match="unrefuted forecast receipt or a certified construction answer"):
                settlement.record_realization(run.body.journal, receipt=receipt, realized=1, source="external_record")
        other = run.ask("pf-2", PORTFOLIO)
        for value in ("2", True, float("nan"), float("inf"), [2], None):
            with pytest.raises(ValueError, match="one finite number"):
                settlement.record_realization(run.body.journal, receipt=other.hash, realized=value,
                                              source="external_record")
        with pytest.raises(ValueError, match="source is one of"):
            settlement.record_realization(run.body.journal, receipt=other.hash, realized=2, source="rumour")
        assert [e.payload["receipt"] for e in run.body.journal.replay("cognition.realization")] == [record.hash]


def test_world_failures_of_a_construction_make_a_later_compile_choose_the_other_fit_and_the_ablation_does_not(
        tmp_path, monkeypatch):
    index = json.loads(compiler.EVIDENCE_INDEX.read_text())
    index["genomes"]["flow_maxflow"]["status"] = "EXPERIMENTAL"               # fixture: the construction ranks first
    (tmp_path / "index.json").write_text(json.dumps(index))
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    network = maxflow_instance(3)[0]
    both = {**PORTFOLIO, **network}
    with Run(tmp_path) as run:
        run.command("CAPABILITY_ATTACH", {"capability_id": "cognition.flow_maxflow"})
        for i in range(10):                                                   # the other fit: 10 verified answers
            assert run.ask(f"net-{i}", network, allow=False).payload["result"]["output"][
                "method_or_composition_selected"] == "cognition.flow_maxflow"
        portfolios = [run.ask(f"pf-{i}", PORTFOLIO) for i in range(10)]
        cid = construction_id(run.body)
        assert {r.payload["result"]["output"]["method_or_composition_selected"] for r in portfolios} == {cid}
        for i, record in enumerate(portfolios):                               # six of ten fall short in the world
            run.realize(record, PROMISED - 2 if i < 6 else PROMISED)

        def decide():
            return compiler.run({"problem_id": "later", "compile": {"geometry": {"geometry": "optimization"},
                                                                    "data": both, "execute": False}},
                                registry=run.body.registry, journal=run.body.journal)

        assert compiler._settled_counts(run.body.journal) == {"cognition.flow_maxflow": (10, 10), cid: (10, 4)}
        assert compiler._settled_inhibition(10, 4) is None                     # the Fisher rule acts, not inhibition
        later = decide()
        assert later["method_or_composition_selected"] == "cognition.flow_maxflow"
        assert later["settled_preference"]["against"] == cid and later["settled_preference"]["preferred"] == \
            "cognition.flow_maxflow" and later["settled_preference"]["tests"][0]["p_holm"] < 0.05
        assert run.ask("later-mission", both).payload["result"]["output"]["method_or_composition_selected"] == \
            "cognition.flow_maxflow"                                           # and a signed mission follows it
        with monkeypatch.context() as ablation:                               # the realization path disabled
            ablation.setattr(settlement, "_world_realizations", lambda journal: {})
            assert compiler._settled_counts(run.body.journal)[cid] == (10, 10)
            ablated = decide()
            assert ablated["method_or_composition_selected"] == cid
            assert not ablated.get("settled_preference") or ablated["settled_preference"]["preferred"] is None
