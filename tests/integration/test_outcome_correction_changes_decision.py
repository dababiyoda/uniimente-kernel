"""An authorized correction of a disputed world outcome changes a later decision; without the repair it does not.

Pre-registered in docs/evidence/outcome-correction-2026-10-28/DECLARATION.md (committed and pushed at 3886d727
before this file existed). Arms and the frozen scoring rule are taken from it verbatim. Six of the eight
predictions are asserted as declared. Two were missed as worded and are asserted as recorded instead, with the miss
disclosed in the evidence README: prediction 5's method total (5 of 11, not 4 of 10; the ten reported claims are 4 of
10) and prediction 8's attach count (three attaches, not two). Laboratory tier: a temporary body, a per-test founder key, declared world values. Real
constructions, compile receipts, signed missions, signed REALIZATION commands and appraisals on the canonical path.
"""
from __future__ import annotations

import hashlib
import json

import pytest

pytest.importorskip("networkx")
pytest.importorskip("scipy")

from greg import gravity  # noqa: E402
from greg.cognition import compiler, settlement  # noqa: E402
from greg.cognition.genomes.flow import maxflow_instance  # noqa: E402
from tests.unit.test_greg_construction_realization import PROMISED, Run, construction_id  # noqa: E402
from tests.unit.test_greg_recombine import PORTFOLIO  # noqa: E402

TRUE_PROFIT = [0] * 6 + [PROMISED] * 4               # declared world: answers 0-5 fail their promise, 6-9 keep it
TRUE_RATE = {"cognition.flow_maxflow": 1.0}          # declared; the construction's rate is computed from TRUE_PROFIT


def score(method, cid):
    """The frozen rule: the declared true success rate of the selected method."""
    if method == cid:
        return sum(p >= PROMISED - settlement.realization_tolerance(PROMISED) for p in TRUE_PROFIT) / len(TRUE_PROFIT)
    return TRUE_RATE[method]


def portfolio_counts(journal, portfolios):
    """(count, correct) over the ten portfolio claims the scenario reports on. The method's total also holds the
    mid-mission's own answer (prediction 6), which the declaration's prediction 5 did not count."""
    receipts = {r.hash for r in portfolios}
    rows = [o for o in settlement.measured_outcomes(journal) if o["receipt"] in receipts
            or (o.get("world") or {}).get("realization_events")
            and any(e.payload["receipt"] in receipts for e in objective_facts(journal)
                    if e.event_id in o["world"]["realization_events"])]
    return len(rows), sum(o["correct"] for o in rows)


def objective_facts(journal):
    return [e for e in journal.replay("cognition.realization") if e.payload.get("kind") == "objective"]


def test_an_authorized_correction_changes_the_later_selection_and_the_ablation_does_not(tmp_path, monkeypatch):
    index = json.loads(compiler.EVIDENCE_INDEX.read_text())
    index["genomes"]["flow_maxflow"]["status"] = "EXPERIMENTAL"           # the declared fixture of the scenario
    (tmp_path / "index.json").write_text(json.dumps(index))
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    fixture_digest = hashlib.sha256((tmp_path / "index.json").read_bytes()).hexdigest()
    network = maxflow_instance(3)[0]
    both = {**PORTFOLIO, **network}
    with Run(tmp_path) as run:
        journal = run.body.journal
        run.command("CAPABILITY_ATTACH", {"capability_id": "cognition.flow_maxflow"})
        for i in range(10):
            run.ask(f"net-{i}", network, allow=False)
        portfolios = [run.ask(f"pf-{i}", PORTFOLIO) for i in range(10)]
        cid = construction_id(run.body)
        states_before = len(journal.replay("capability.state"))
        # prediction 8 declared "the two founder attaches"; the setup records three attaches: one founder command and
        # two signed read-only auto_attach (review of #210, record item). Asserted as recorded, not as declared.
        setup = [(e.payload.get("capability_id"), e.payload.get("state"), e.payload.get("by"))
                 for e in journal.replay("capability.state")]
        attached = [row for row in setup if row[1] == "ATTACHED"]
        assert [row[2] for row in attached] == (["founder command"]
                                                + ["founder-signed mission auto_attach (read_only)"] * 2)
        assert attached[0][0] == "cognition.flow_maxflow" and cid in {row[0] for row in attached}

        receipts = {}

        def decide(arm=None):
            receipt = compiler.run({"problem_id": "later", "compile": {"geometry": {"geometry": "optimization"},
                                                                       "data": both, "execute": False}},
                                   registry=run.body.registry, journal=journal)
            receipts[arm] = receipt
            return receipt["method_or_composition_selected"]

        # step 1: adversarial reports, all claiming the promise was kept
        for record in portfolios:
            run.realize(record, PROMISED, source="founder_reported")
        arm_a = decide()
        assert compiler._settled_counts(journal)[cid] == (10, 10)

        # step 2: independent observations of the declared truth
        for record, truth in zip(portfolios, TRUE_PROFIT):
            run.realize(record, truth, source="external_record")
        arm_b = decide()
        assert compiler._settled_counts(journal)[cid] == (4, 4)             # prediction 4: disputes score nothing
        trust = gravity._measured_trust(journal)
        assert trust["conflicting_construction_claims"] == 6 and trust["disputes_to_investigate"] == 6   # pred. 7
        mid = run.ask("mid-mission", both)                                  # a signed decision on contested evidence
        assert mid.payload["result"]["output"]["method_or_composition_selected"] == cid

        disputes = [row for row in settlement.awaiting_realization(journal) if row["kind"] == "objective_conflict"]
        assert len(disputes) == 6 and all(row["resolvable_now"] and row["priority"] == "investigate"
                                          for row in disputes)
        # prediction 4: unsupported corrections are refused or resolve nothing
        first = disputes[0]["prepared_resolution"]["body"]
        founder_fact = next(r["event"] for r in disputes[0]["reports"] if r["declared_source"] == "founder_reported")
        with pytest.raises(ValueError, match="accepts only a report declared as an independent source"):
            run.command("REALIZATION", {**first, "accept": founder_fact, "note": "I am sure"})
        with pytest.raises(ValueError, match="basis"):
            run.command("REALIZATION", {**first, "note": " "})
        unsigned_before = compiler._settled_counts(journal)[cid]
        settlement.record_resolution(journal, receipt=first["receipt"], resolves=first["resolves"],
                                     accept=first["accept"], note="written around the founder",
                                     command_digest="sha256:" + "0" * 64)
        assert compiler._settled_counts(journal)[cid] == unsigned_before == (5, 5)   # + the mid-mission's answer
        assert portfolio_counts(journal, portfolios) == (4, 4)

        # step 3: the founder signs each resolution the body prepared
        settled_before = len(journal.replay("cognition.settled"))
        for row in disputes:
            body = {**row["prepared_resolution"]["body"], "note": "time-clock export, external record"}
            run.command("REALIZATION", body)
        arm_c = decide("C")
        # the selection in arm C is the compiler's existing settled-outcome rule (Holm-adjusted one-sided Fisher),
        # not the frozen evaluation rule: score() below is the frozen rule, applied to what was selected (second
        # review of #219, R2)
        preference = receipts["C"].get("settled_preference") or {}
        assert preference.get("against") == cid and preference.get("preferred") == "cognition.flow_maxflow"
        assert receipts["C"]["selection_level"] == "preferred_by_settled_outcomes"
        monkeypatch.setattr(settlement, "_resolutions", lambda journal, signed=None: [])
        arm_b_after = decide()                                              # the same history, repair disabled
        assert compiler._settled_counts(journal)[cid] == (5, 5)
        monkeypatch.undo()
        monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")

        # predictions 1 and 2, under the frozen rule
        assert (arm_a, arm_b, arm_b_after) == (cid, cid, cid)
        assert arm_c == "cognition.flow_maxflow"
        assert score(arm_c, cid) > score(arm_b, cid) == score(arm_a, cid) == 0.4
        later = run.ask("later-mission", both)
        assert later.payload["result"]["output"]["method_or_composition_selected"] == "cognition.flow_maxflow"

        # prediction 3: every fact kept
        assert len(objective_facts(journal)) == 20
        # prediction 5: corrected competence, recomputed once
        assert portfolio_counts(journal, portfolios) == (10, 4)
        assert compiler._settled_counts(journal)[cid] == (11, 5)            # + the mid-mission's own answer
        settlement.reconcile(journal)
        once = len(journal.replay("cognition.settled"))
        settlement.reconcile(journal)
        assert len(journal.replay("cognition.settled")) == once
        adjudicated = [e for e in journal.replay("cognition.settled")[settled_before:]
                       if (e.payload.get("world") or {}).get("state") == "adjudicated"]
        assert len(adjudicated) == 6 and len({e.payload["outcome_id"] for e in adjudicated}) == 6
        assert all(e.payload["supersedes"] for e in adjudicated)
        # prediction 6: the decision made on contested evidence is listed for recheck
        recheck = settlement.decisions_to_recheck(journal)
        assert [r["receipt"] for r in recheck] == [mid.hash] and recheck[0]["affected_methods"] == [cid]
        # prediction 7: nothing left to investigate
        trust = gravity._measured_trust(journal)
        assert trust["disputes_to_investigate"] == 0 and trust["conflicting_construction_claims"] == 0
        assert trust["decisions_to_recheck"] == 1
        # prediction 8: safeguards
        assert len(journal.replay("capability.state")) == states_before
        assert [(e.payload.get("capability_id"), e.payload.get("state"), e.payload.get("by"))
                for e in journal.replay("capability.state")] == setup             # no capability state changed
        assert not any((e.payload or {}).get("authority_created") is True for e in journal.replay(""))
        compiles = [r.payload["result"]["output"] for r in run.body.ledger.by_type("receipt")
                    if isinstance(r.payload["result"].get("output"), dict)
                    and r.payload["result"]["output"].get("schema") == compiler.SCHEMA]
        assert all(c["authority_created"] is False and not (c.get("cost") or {}).get("money_usd") for c in compiles)
        assert hashlib.sha256((tmp_path / "index.json").read_bytes()).hexdigest() == fixture_digest
