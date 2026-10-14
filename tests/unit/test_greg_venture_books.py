"""Node N7: a capability proven in one venture makes a second venture cheaper, and the second venture's
verified revenue funds every obligation and reserve Alfonso signed before any surplus is reinvestable.

Revenue counts only from business cases that closed N3. It runs through the Kernel's own waterfall
(capital/treasury.py over capital/allocation-policy.yaml); GREG moves and allocates no money. The
transplant is a ratified procedure taught by one venture's cases and run as closed cases in another.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from greg import path as devpath, sop, venture_books
from greg.body import Body
from greg.founder import COMMAND_KINDS, DEVICE_KINDS
from greg.missions import validate_mission
from greg.templates import business_case
from tests.greg_fixtures import Clock, drop, make_body, signed, workspace

ROOT = Path(__file__).resolve().parents[2]
TIERS = venture_books.load_waterfall()
TAXES, PAYROLL, RESERVES = TIERS[0], TIERS[1], TIERS[3]
HEADER = "date,description,amount,currency\n"


@pytest.mark.parametrize("body, message", [
    ({"venture": "x", "currency": "USD", "requirements": {TAXES: "1"}}, "short lowercase"),
    ({"venture": "audits", "currency": "usd", "requirements": {TAXES: "1"}}, "three-letter"),
    ({"venture": "audits", "currency": "USD", "requirements": {"bonuses": "1"}}, "unknown waterfall tiers"),
    ({"venture": "audits", "currency": "USD", "requirements": {TAXES: "-5"}}, "zero or more"),
    ({"venture": "audits", "currency": "USD", "requirements": {TAXES: "1.005"}}, "to the cent"),
    ({"venture": "audits", "currency": "USD", "requirements": {}}, "map waterfall tiers"),
    ({"venture": "audits", "currency": "USD", "requirements": {TAXES: "1"}, "spend": True}, "exactly venture"),
])
def test_treasury_requirements_are_read_exactly_as_signed_or_refused(body, message):
    with pytest.raises(venture_books.BooksError, match=message):
        venture_books.validate_requirements(body)


def test_only_the_founder_key_signs_treasury_requirements():
    assert "TREASURY_REQUIREMENTS" in COMMAND_KINDS and "TREASURY_REQUIREMENTS" not in DEVICE_KINDS


def books_for(tmp_path, monkeypatch, revenue: dict, requirements: dict | None):
    home, *_ = make_body(tmp_path)
    monkeypatch.setattr(venture_books, "_closed_cases", lambda journal: {
        f"m:case-{i}": ("audits", "USD", Decimal(v)) for i, v in enumerate(revenue)})
    with Body(home) as body:
        if requirements is not None:
            body.journal.record("treasury.requirements", venture_books.validate_requirements(
                {"venture": "audits", "currency": "USD", "requirements": requirements}), key="t")
        [row] = venture_books.books(body.journal)
    return row


def test_surplus_exists_only_after_every_obligation_and_reserve_is_funded(tmp_path, monkeypatch):
    row = books_for(tmp_path, monkeypatch, ["300.00", "300.00"],
                    {TAXES: "100", RESERVES: "50", TIERS[-1]: "999"})          # a tier below reinvestment
    assert row["verified_revenue"] == "600.00" and row["surplus_for_reinvestment"] == "450.00"
    assert row["protected_shortfall"] == {} and row["requirements_below_reinvestment"] == [TIERS[-1]]


def test_an_underfunded_obligation_leaves_nothing_to_reinvest(tmp_path, monkeypatch):
    row = books_for(tmp_path, monkeypatch, ["250.00"], {TAXES: "100", PAYROLL: "200", RESERVES: "50"})
    assert row["surplus_for_reinvestment"] == "0.00"
    assert row["protected_shortfall"] == {PAYROLL: "50.00", RESERVES: "50.00"}
    assert "not fully funded" in row["why"]


def test_without_signed_requirements_there_is_no_surplus_figure(tmp_path, monkeypatch):
    row = books_for(tmp_path, monkeypatch, ["250.00"], None)
    assert row["surplus_for_reinvestment"] is None and "no signed TREASURY_REQUIREMENTS" in row["why"]


def case(home, n: int, venture: str, **kw) -> dict:
    return validate_mission(business_case(
        case=f"{venture} case {n:02d}", buyer=f"Buyer {venture} {n}", offer=f"{venture} service {n}",
        price=str(200 + 50 * n), currency="USD", acceptance=f"done within {n + 2} business days",
        workspace_root=Path(home).resolve() / "workspace", venture=venture, **kw))


def test_a_business_procedure_asks_only_for_what_a_person_chose_and_moves_between_ventures(tmp_path):
    specs = [case(tmp_path, n, "leases", approve_writes=True) for n in range(3)]
    workflow = sop.generalize(specs)
    assert set(workflow["slots"]) == {"reference", "buyer", "offer", "price", "acceptance"}
    record = {"procedure_id": "sop-0123456789abcdef", "command_digest": "sha256:r",
              "workflow": {**workflow, "horizon_days": 45.0, "venture": "leases"}, "pre_approved_steps": []}
    taught = {k: v["examples"][1] for k, v in workflow["slots"].items()}
    assert sop._strip(sop.instantiate(record, taught, mission_id=specs[1]["mission_id"])) == sop._strip(specs[1])
    moved = sop.instantiate(record, {**taught, "reference": "CASE-AUDIT-01"}, venture="audits")
    assert moved["venture"] == "audits" and moved["success_checks"][2]["sensor"]["params"]["reference"] == "CASE-AUDIT-01"
    assert sop.instantiates(record, moved) == {**taught, "reference": "CASE-AUDIT-01"}


# -- the body: N7 closes only with a cheaper transplant and funded obligations ---------------

def tick(body, clock, ticks=3):
    clock.advance(4000)
    for _ in range(ticks):
        body.tick()
        clock.advance(1)


def requests(body, mid, kind):
    return [e.payload for e in body.journal.replay("decision.requested")
            if e.payload["mission_id"] == mid and e.payload["kind"] == kind]


def run_case(home, key, body_id, clock, body, spec) -> str:
    """Sign one case and do every person's step; approve GREG's writes when its cone asks."""
    mid = spec["mission_id"]
    ref = spec["success_checks"][2]["sensor"]["params"]["reference"]
    amount = spec["success_checks"][2]["sensor"]["params"]["amount"]
    folder = workspace(home, mid)
    drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))

    def step():
        tick(body, clock)
        for ask in requests(body, mid, "APPROVAL"):
            if not any(e.payload["request_id"] == ask["request_id"] for e in body.journal.replay("decision.answered")):
                drop(home, signed(key, body_id, "DECISION", {"request_id": ask["request_id"], "answer": "approve"},
                                  now=clock.now))
                tick(body, clock)
    step()
    for name, text in (("acceptance.txt", f"accepted {ref}"), ("statement.csv", HEADER + f"2026-10-02,Pay {ref},{amount},USD\n"),
                       ("delivery.txt", f"delivered {ref}"), ("outcome.txt", f"confirmed {ref}")):
        (folder / name).write_text(text + "\n")
        step()
    step()
    [achieved] = [e for e in body.journal.replay("mission.achieved") if e.payload["mission_id"] == mid]
    drop(home, signed(key, body_id, "CRITIQUE", {"target_event_id": achieved.event_id, "verdict": "accept",
                                                 "evidence_type": "founder_judgment", "text": "real buyer, paid"},
                      now=clock.now))
    tick(body, clock, 1)
    return mid


def test_a_procedure_from_one_venture_makes_a_second_cheaper_and_its_revenue_funds_reserves_first(
        tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    try:
        drop(home, signed(key, body_id, "BODY_DESIGNATE", {"purpose": "first_founder_body"}, now=clock.now))
        tick(body, clock, 1)
        taught = [run_case(home, key, body_id, clock, body, case(home, n, "leases", approve_writes=True))
                  for n in range(3)]
        assert all(len(requests(body, mid, "APPROVAL")) == 2 for mid in taught)
        assert len(devpath.business_loop_closed(body.journal)["cases"]) == 3
        [proposal] = [e.payload for e in body.journal.replay("sop.proposed")]
        assert set(proposal["workflow"]["slots"]) == {"reference", "buyer", "offer", "price", "acceptance"}
        assert proposal["workflow"]["venture"] == "leases"
        drop(home, signed(key, body_id, "SOP_RATIFY", {"procedure_id": proposal["procedure_id"],
                                                       "pre_approve": ["draft-offer", "record-settlement"]},
                          now=clock.now))
        tick(body, clock, 1)
        record = sop.ratified(body.journal)[proposal["procedure_id"]]["record"]

        moved = []
        for n in (1, 2):
            spec = sop.instantiate(record, {"reference": f"CASE-AUDIT-{n:02d}", "buyer": f"Audit client {n}",
                                            "offer": f"an audit memo {n}", "price": "300.00",
                                            "acceptance": "memo within 5 business days"},
                                   venture="audits", now=datetime.now(timezone.utc))  # signed at wall time
            moved.append(run_case(home, key, body_id, clock, body, spec))
        assert all(requests(body, mid, "APPROVAL") == [] for mid in moved)
        [transfer] = venture_books.transfers(body.journal)
        assert (transfer["from_venture"], transfer["to_venture"], transfer["runs"]) == ("leases", "audits", 2)
        assert transfer["per_outcome"]["interventions"] == {"taught_in_leases": 6.0, "run_in_audits": 4.0}
        assert transfer["faster_or_cheaper"] is True and "interventions" in transfer["lower"]

        before = devpath.venture_compounding(body.journal)
        assert before["met"] is False and "no surplus" in before["missing"][0]
        drop(home, signed(key, body_id, "TREASURY_REQUIREMENTS", {"venture": "audits", "currency": "USD",
                                                                  "requirements": {TAXES: "120", RESERVES: "80"}},
                          now=clock.now))
        tick(body, clock, 1)
        after = devpath.venture_compounding(body.journal)
        assert after["met"] is True, after
        [audits] = [b for b in after["books"] if b["venture"] == "audits"]
        assert audits["verified_revenue"] == "600.00" and audits["surplus_for_reinvestment"] == "400.00"
        [leases] = [b for b in after["books"] if b["venture"] == "leases"]
        assert leases["surplus_for_reinvestment"] is None            # no obligations signed there: no figure
        assert not [r for r in body.journal.ledger.by_type("event") if r.payload.get("type", "").startswith("treasury.")]
        assert body.journal.ledger.verify_chain()[0] is True     # one full verification of the whole chain
    finally:
        body.close()


def test_n7_refuses_a_transplant_with_too_few_runs_or_no_saving(tmp_path, monkeypatch):
    entry = {"procedure_id": "sop-x", "state": "RATIFIED",
             "baseline": {"missions": [{"mission_id": f"a{i}", "interventions": 4, "model_cost_usd": 0.0,
                                        "hours_to_close": 1.0} for i in range(3)]},
             "sop_runs": {"missions": [{"mission_id": "b0", "interventions": 4, "model_cost_usd": 0.0,
                                        "hours_to_close": 1.0}], "quality_failures": []}}
    specs = {**{f"a{i}": {"venture": "leases"} for i in range(3)}, "b0": {"venture": "audits"}}
    monkeypatch.setattr(sop, "trend", lambda journal: {"procedures": [entry]})
    monkeypatch.setattr(venture_books, "_closed_cases", lambda journal: {"b0": ("audits", "USD", Decimal(1))})

    class J:
        def replay(self, kind):
            return [type("E", (), {"payload": {"mission_id": m, "spec": s}}) for m, s in specs.items()]
    [row] = venture_books.transfers(J())
    assert row["faster_or_cheaper"] is False
    assert row["why_not"] == ["1 of 2 closed runs in audits", "no measure fell"]


def test_the_cli_reads_the_books_and_refuses_an_unknown_tier(tmp_path):
    home, *_ = make_body(tmp_path)

    def cli(*args):
        return subprocess.run([sys.executable, "-m", "greg", "--home", str(home), "treasury", *args],
                              capture_output=True, text=True, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT)},
                              timeout=60)
    out = cli("books")
    assert out.returncode == 0 and json.loads(out.stdout) == {"books": [], "transfers": []}
    bad = cli("set", "--venture", "audits", "--tier", "bonuses=5", "--key", str(tmp_path / "founder.pem"),
              "--no-passphrase")
    assert bad.returncode != 0 and "unknown waterfall tiers" in (bad.stderr + bad.stdout)
    node = next(n for n in devpath.load()["nodes"] if n["id"] == "N7")
    assert node["predicate"] == "venture_compounding" and node["predicate"] in devpath.PREDICATES


def transfer_rows(monkeypatch, *, runs, closed=("b0", "b1"), failures=(), venture="audits"):
    entry = {"procedure_id": "sop-x", "state": "RATIFIED",
             "baseline": {"missions": [{"mission_id": f"a{i}", "interventions": 6, "model_cost_usd": 0.0,
                                        "hours_to_close": 1.0} for i in range(3)]},
             "sop_runs": {"missions": runs, "quality_failures": list(failures)}}
    specs = {**{f"a{i}": {"venture": "leases"} for i in range(3)},
             **{r["mission_id"]: {"venture": venture} for r in runs}}
    monkeypatch.setattr(sop, "trend", lambda journal: {"procedures": [entry]})
    monkeypatch.setattr(venture_books, "_closed_cases", lambda journal: {
        m: ("audits", "USD", Decimal(1)) for m in closed})

    class J:
        def replay(self, kind):
            return [type("E", (), {"payload": {"mission_id": m, "spec": s}}) for m, s in specs.items()]
    return venture_books.transfers(J())


def run_row(mid, interventions=4, cost=0.0):
    return {"mission_id": mid, "interventions": interventions, "model_cost_usd": cost, "hours_to_close": 1.0}


def test_a_transplant_counts_only_closed_runs_held_quality_and_no_rising_spend(monkeypatch):
    assert transfer_rows(monkeypatch, runs=[run_row("b0"), run_row("b1")])[0]["faster_or_cheaper"] is True
    assert transfer_rows(monkeypatch, runs=[run_row("b0"), run_row("b1")], venture="leases") == []  # same venture
    [unclosed] = transfer_rows(monkeypatch, runs=[run_row("b0"), run_row("b1")], closed=("b0",))
    assert unclosed["runs"] == 1 and unclosed["faster_or_cheaper"] is False      # an unpaid run is no transplant
    [poor] = transfer_rows(monkeypatch, runs=[run_row("b0"), run_row("b1")], failures=[{"mission_id": "b2"}])
    assert poor["faster_or_cheaper"] is False and "quality not held" in poor["why_not"]
    [dearer] = transfer_rows(monkeypatch, runs=[run_row("b0", cost=0.5), run_row("b1", cost=0.5)])
    assert dearer["faster_or_cheaper"] is False and "model_cost_usd rose" in dearer["why_not"]


def test_n7_needs_surplus_in_the_venture_the_capability_moved_into(monkeypatch):
    proven = {"procedure_id": "sop-x", "from_venture": "leases", "to_venture": "audits", "faster_or_cheaper": True}
    monkeypatch.setattr(venture_books, "transfers", lambda journal: [proven])
    elsewhere = [{"venture": "leases", "currency": "USD", "surplus_for_reinvestment": "900.00"},
                 {"venture": "audits", "currency": "USD", "surplus_for_reinvestment": "0.00"}]
    monkeypatch.setattr(venture_books, "books", lambda journal: elsewhere)
    result = devpath.venture_compounding(None)
    assert result["met"] is False and "no surplus" in result["missing"][0]
    monkeypatch.setattr(venture_books, "books", lambda journal: [
        {"venture": "audits", "currency": "USD", "surplus_for_reinvestment": "0.01"}])
    assert devpath.venture_compounding(None)["met"] is True
