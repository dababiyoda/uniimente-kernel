"""The first real ``world.observe.*`` capabilities: read a construction's realized outcome from a founder-placed record.

Settlement (``_observers``) prepares a dispute's verification task only for an attached read-only observer of the
disputed quantity. Until now no body had one. These read ``greg-outcome-records.csv`` in a read root and return what
one row states for one answer, bound to the file's digest. They start VERIFIED: the founder attaches one. Values are
synthetic test inputs.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from greg import outcome_records
from greg.capabilities import BUILTINS, CapabilityError
from greg.cognition import settlement
from greg.cognition.catalog import initial_state

R = "sha256:" + "a" * 64


def ctx(*roots):
    return SimpleNamespace(read_roots=tuple(Path(r) for r in roots))


def write(root, text):
    (Path(root) / outcome_records.RECORDS_NAME).write_text(text)


def test_one_observer_per_objective_settlement_promises_and_none_attached_until_the_founder_does():
    assert set(outcome_records.OBSERVABLE_OBJECTIVES) == {o for o, _ in settlement.OBJECTIVES.values()}
    for objective in outcome_records.OBSERVABLE_OBJECTIVES:
        manifest, _ = BUILTINS[f"records.observe.{objective}"]
        assert manifest.function == f"world.observe.{objective}" and manifest.consequence_class == "read_only"
        assert manifest.network == "none" and manifest.budget_ceiling_usd == 0
        assert initial_state(manifest.capability_id) == "VERIFIED"


def test_reads_the_one_value_the_record_states_bound_to_its_digest(tmp_path):
    write(tmp_path, f"receipt,objective,realized,reference\n{R},profit,\"1,250.5\",GL-2026-10\n{R},cost,9,x\n")
    out = outcome_records.observe({"receipt": R, "objective": "profit"}, ctx(tmp_path))
    assert out["realized"] == 1250.5 and out["line"] == 2 and out["reference"] == "GL-2026-10"
    import hashlib
    assert out["sha256"] == hashlib.sha256((tmp_path / outcome_records.RECORDS_NAME).read_bytes()).hexdigest()


@pytest.mark.parametrize("text,why", [
    (None, "no greg-outcome-records.csv"),
    ("receipt,objective,realized\n", "no row for this answer"),
    (f"receipt,objective,realized\n{R},cost,3\n", "no row for this answer"),
    (f"receipt,objective,realized\n{R},profit,nan\n", "no finite realized value"),
    (f"receipt,objective,realized\n{R},profit,lots\n", "no finite realized value"),
    (f"receipt,objective\n{R},profit\n", "lacks the columns"),
    (f"receipt,objective,realized\n{R},profit,1\n{R},profit,2\n", "disagree"),
])
def test_no_value_is_read_where_the_record_does_not_state_exactly_one(tmp_path, text, why):
    if text is not None:
        write(tmp_path, text)
    out = outcome_records.observe({"receipt": R, "objective": "profit"}, ctx(tmp_path))
    assert "realized" not in out and why in out["why"]


def test_a_link_in_place_of_the_record_is_not_followed_and_bad_params_are_refused(tmp_path):
    target = tmp_path / "elsewhere.csv"
    target.write_text(f"receipt,objective,realized\n{R},profit,2\n")
    (tmp_path / outcome_records.RECORDS_NAME).symlink_to(target)
    assert "realized" not in outcome_records.observe({"receipt": R, "objective": "profit"}, ctx(tmp_path))
    with pytest.raises(CapabilityError):
        outcome_records.observe({"receipt": R, "objective": "revenue"}, ctx(tmp_path))


def test_on_a_body_an_attached_record_reader_decides_a_dispute_through_the_founders_signatures(tmp_path, monkeypatch):
    """No test double: the real built-in, attached by the founder's signed command, reads the record the founder
    placed; the drafted mission runs only once signed; the reading resolves nothing until the founder signs the
    report and the prepared resolution; competence then settles once."""
    pytest.importorskip("networkx")
    pytest.importorskip("scipy")
    from tests.greg_fixtures import drop, signed
    from tests.unit.test_greg_construction_realization import PROMISED, Run
    from tests.unit.test_greg_dispute_evidence_acquisition import REAL_SIGNED_REALIZATIONS
    from tests.unit.test_greg_recombine import PORTFOLIO
    monkeypatch.setattr(settlement, "_signed_realizations", REAL_SIGNED_REALIZATIONS)

    def conflict(journal):
        return next(r for r in settlement.awaiting_realization(journal) if r.get("kind") == "objective_conflict")

    with Run(tmp_path) as run:
        journal = run.body.journal
        record = run.ask("pf-records", PORTFOLIO)
        run.realize(record, PROMISED - 2, source="founder_reported")
        run.realize(record, PROMISED, source="founder_reported")
        row = conflict(journal)
        assert row["evidence_request"]["acquirable_by_body"] == []          # registered, but not attached

        run.command("CAPABILITY_ATTACH", {"capability_id": "records.observe.profit"})
        row = conflict(journal)
        assert row["evidence_request"]["acquirable_by_body"] == ["records.observe.profit"]
        spec = row["prepared_verification"]["mission"]
        root = Path(run.body.config["read_roots"][0])
        write(root, f"receipt,objective,realized,reference\n{row['reports'][-1]['receipt']},profit,{PROMISED},"
                    "GL-2026-10 period close\n")

        drop(run.home, signed(run.key, run.body_id, "MISSION", spec))
        for _ in range(8):
            run.body.tick()
            run.clock.advance(31)
            if run.body.engine.book.missions[spec["mission_id"]].status == "ACHIEVED":
                break
        assert run.body.engine.book.missions[spec["mission_id"]].status == "ACHIEVED"
        [reading] = [r for r in run.body.ledger.by_type("receipt")
                     if ((r.payload.get("result") or {}).get("output") or {}).get("reference", "").startswith("GL-")]
        output = reading.payload["result"]["output"]
        assert output["realized"] == PROMISED and len(output["sha256"]) == 64
        assert run.outcome(record) is None                                  # the reading alone decides nothing

        run.command("REALIZATION", {"receipt": record.hash, "realized": output["realized"],
                                    "source": "external_record",
                                    "note": f"{output['record']} line {output['line']} sha256 {output['sha256']}, "
                                            f"read by receipt {reading.hash}"})
        run.command("REALIZATION", {**conflict(journal)["prepared_resolution"]["body"],
                                    "note": f"outcome record {output['reference']}"})
        assert run.outcome(record)["world"]["state"] == "adjudicated" and run.outcome(record)["correct"] is True
        settlement.reconcile(journal)
        once = [e for e in journal.replay("cognition.settled") if e.payload.get("receipt") == record.hash]
        settlement.reconcile(journal)
        run.body.tick()
        assert [e for e in journal.replay("cognition.settled") if e.payload.get("receipt") == record.hash] == once
