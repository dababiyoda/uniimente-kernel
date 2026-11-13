"""Node N3's machinery: one business case closes in commercial order and GREG takes no external action.

problem -> buyer -> offer -> payment -> delivery -> customer outcome (business/commercial_loop.py),
run as a founder-signed GREG mission on the body. GREG drafts the offer and writes the settlement
record; people send, collect, deliver and confirm, each through one HUMAN_WORK ask; payment counts
only when one statement posting matches the signed amount, currency and case reference to the cent.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from greg import path as devpath
from greg.body import Body
from greg.business_loop import parse_amount, reconcile
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext
from greg.missions import validate_mission
from greg.templates import business_case
from greg.metrics import NOT_FOUNDER_TIER
from tests.greg_fixtures import TEST_PASSPHRASE, Clock, attest_founder_tier, drop, make_body, signed, workspace

REF = "CASE-LEASE-REVIEW-01"
HEADER = "date,description,amount,currency\n"


def case_spec(home: Path, **overrides) -> dict:
    fields = {"case": "lease review 01", "buyer": "Acme Property LLC", "offer": "a reviewed lease summary",
              "price": "250", "currency": "USD", "acceptance": "summary delivered within 5 business days",
              "workspace_root": Path(home).resolve() / "workspace", **overrides}
    return validate_mission(business_case(**fields))


def ctx(root: Path) -> InvocationContext:
    return InvocationContext(workspace=root / "ws", read_roots=(root,), secrets=None,
                             manifest=BUILTINS["business.reconcile"][0])


def statement(tmp_path, text: str) -> dict:
    path = tmp_path / "statement.csv"
    path.write_text(HEADER + text)
    return {"path": str(path), "amount": "250.00", "currency": "USD", "reference": REF}


@pytest.mark.parametrize("rows, matched, detail", [
    (f"2026-10-02,Payment {REF},250.00,USD\n", True, "one posting"),
    (f"2026-10-02,Payment {REF},\"$250\",usd\n", True, "one posting"),
    (f"2026-10-02,Payment {REF},249.99,USD\n", False, "differ in amount or currency"),
    (f"2026-10-02,Payment {REF},250.00,EUR\n", False, "differ in amount or currency"),
    ("2026-10-02,Payment without reference,250.00,USD\n", False, "no posting carries"),
    (f"2026-10-02,Payment {REF},250.00,USD\n2026-10-03,Again {REF},250.00,USD\n", False, "ambiguous: 2"),
])
def test_payment_counts_only_for_exactly_one_posting_to_the_cent(tmp_path, rows, matched, detail):
    out = reconcile(statement(tmp_path, rows), ctx(tmp_path))
    assert out["matched"] is matched and detail in out["detail"]


def test_reconciliation_reads_signed_columns_and_minor_units_and_refuses_what_it_cannot_judge(tmp_path):
    path = tmp_path / "stripe.csv"
    path.write_text(f"Created,Memo,Amount (cents),Cur\n2026-10-02,{REF},25000,usd\n")
    params = {"path": str(path), "amount": "250", "currency": "usd", "reference": REF, "minor_units": True,
              "columns": {"amount": "Amount (cents)", "currency": "Cur", "reference": "Memo"}}
    assert reconcile(params, ctx(tmp_path))["matched"] is True
    unsigned = reconcile({**params, "columns": None}, ctx(tmp_path))
    assert unsigned["matched"] is False and "lacks the signed columns" in unsigned["detail"]
    assert reconcile({**params, "path": str(tmp_path / "none.csv")}, ctx(tmp_path))["exists"] is False
    with pytest.raises(CapabilityError, match="at least 6"):
        reconcile({**params, "reference": "C-1"}, ctx(tmp_path))
    with pytest.raises(CapabilityError, match="positive"):
        reconcile({**params, "amount": "0"}, ctx(tmp_path))
    assert parse_amount("(12.00)") == -12 and parse_amount("1,234.50") == parse_amount("1234.5")
    assert parse_amount("NaN") is None and parse_amount("twelve") is None


@pytest.mark.parametrize("override, message", [
    ({"currency": "dollars"}, "three-letter"), ({"price": "12.345"}, "two decimal"), ({"price": "-5"}, "positive"),
    ({"buyer": " "}, "buyer must be stated"), ({"acceptance": ""}, "acceptance must be stated"),
    ({"statement": "../x.csv"}, "plain file name"), ({"case": "!"}, "at least 3"),
])
def test_a_case_cannot_be_signed_without_buyer_price_and_acceptance_terms(tmp_path, override, message):
    with pytest.raises(ValueError, match=message):
        case_spec(tmp_path, **override)


def human_asks(body, mid):
    return [e.payload for e in body.journal.replay("decision.requested")
            if e.payload["mission_id"] == mid and e.payload["kind"] == "HUMAN_WORK"]


def run(body, clock, ticks=3, advance=4000):
    clock.advance(advance)
    for _ in range(ticks):
        body.tick()
        clock.advance(1)


@pytest.mark.parametrize("founder_tier", [False, True], ids=["test-key", "founder-tier-attested"])
def test_a_case_closes_in_commercial_order_with_people_doing_every_outward_act(tmp_path, monkeypatch, founder_tier):
    passphrase = TEST_PASSPHRASE if founder_tier else None
    home, key, body_id, _ = make_body(tmp_path, passphrase=passphrase)
    clock = Clock()
    body = Body(home, clock=clock).open()
    body.boot()
    try:
        drop(home, signed(key, body_id, "BODY_DESIGNATE", {"purpose": "first_founder_body"}, now=clock.now))
        if founder_tier:                                      # as `greg founder attest` does, before the case is signed
            attest_founder_tier(home, tmp_path / "founder.pem", passphrase, monkeypatch)
        run(body, clock, 1, 0)
        spec = case_spec(home)
        mid = spec["mission_id"]
        folder = workspace(home, mid)
        drop(home, signed(key, body_id, "MISSION", spec, now=clock.now))
        run(body, clock, 3, 0)
        assert REF in (folder / "offer.md").read_text() and "Acme Property LLC" in (folder / "offer.md").read_text()
        [send] = human_asks(body, mid)
        assert send["evidence"]["function"] == "human.send_offer" and send["resource"] == "human_worker"

        (folder / "acceptance.txt").write_text(f"Acme accepts {REF}: summary within 5 business days\n")
        run(body, clock)
        assert [a["evidence"]["function"] for a in human_asks(body, mid)][-1] == "human.collect_payment"

        (folder / "statement.csv").write_text(HEADER + f"2026-10-02,Payment {REF},240.00,USD\n")
        run(body, clock)                                         # a short payment never counts
        assert len(human_asks(body, mid)) == 2 and not (folder / "settlement.md").exists()
        (folder / "statement.csv").write_text(HEADER + f"2026-10-02,Payment {REF},240.00,USD\n"
                                              f"2026-10-03,Balance {REF},250.00,USD\n")
        run(body, clock)
        assert [a["evidence"]["function"] for a in human_asks(body, mid)][-1] == "human.deliver"

        (folder / "delivery.txt").write_text(f"Summary for {REF} sent to Acme on 2026-10-04\n")
        run(body, clock)
        assert [a["evidence"]["function"] for a in human_asks(body, mid)][-1] == "human.confirm_outcome"
        assert not (folder / "settlement.md").exists()           # nothing settled before the buyer confirms

        (folder / "outcome.txt").write_text(f"Acme confirms {REF} met the terms\n")
        run(body, clock, 5)
        assert REF in (folder / "settlement.md").read_text()
        [achieved] = [e for e in body.journal.replay("mission.achieved") if e.payload["mission_id"] == mid]
        [appraisal] = [e.payload for e in body.journal.replay("mission.appraised") if e.payload["mission_id"] == mid]
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        assert appraisal["checks"]["preconditions_honored"] is True
        done = {e.payload["action_id"] for e in body.journal.replay("mission.action")
                if e.payload["mission_id"] == mid and e.payload["status"] == "DONE"}
        assert done == {"draft-offer", "record-settlement"}       # GREG only wrote inside its workspace
        withdrawn = {e.payload["request_id"] for e in body.journal.replay("decision.withdrawn")}
        assert {a["request_id"] for a in human_asks(body, mid)} <= withdrawn and len(human_asks(body, mid)) == 4

        before = devpath.business_loop_closed(body.journal)
        assert before["met"] is False and before["incomplete"][0]["missing"] == ["founder_accepted"]
        drop(home, signed(key, body_id, "CRITIQUE", {"target_event_id": achieved.event_id, "verdict": "accept",
                                                     "evidence_type": "founder_judgment",
                                                     "text": "accepted after reading the settlement"}, now=clock.now))
        run(body, clock, 1, 0)
        after = devpath.business_loop_closed(body.journal)
        assert after["structurally_met"] is True and after["cases"] == [{"mission_id": mid, "human_steps": 4}]
        if founder_tier:
            assert after["met"] is True and after["evidence_level"] == "FOUNDER_TIER" and after["value"] == 1
            return
        # Reason (#137 verifier): a closure signed with a test key never moves the founder's path (N1 kill condition).
        assert after["met"] is False and after["evidence_level"] == "STRUCTURAL_CANDIDATE" and after["value"] == 0
        assert after["not_founder_tier"] == {mid: NOT_FOUNDER_TIER} and "founder tier" in after["blocker"]
        # Deliberately the documented residual: this UNPROTECTED fixture key self-attests through the API (the CLI
        # would refuse it; greg/metrics.py CUSTODY_CLAIM). Only the timing rule is under test here.
        drop(home, signed(key, body_id, "FOUNDER_TIER", {"key_custody": "passphrase"}, now=clock.now))
        run(body, clock, 1, 0)                                 # an attestation after the fact does not reach back
        late = devpath.business_loop_closed(body.journal)
        assert late["met"] is False and "only after this mission was registered" in late["not_founder_tier"][mid]
    finally:
        body.close()


@pytest.mark.parametrize("paid", [True, False])
def test_n3_refuses_a_case_where_greg_acted_outward_or_a_person_never_did(tmp_path, paid):
    home, key, body_id, _ = make_body(tmp_path)
    spec = case_spec(home)
    mid = spec["mission_id"]
    with Body(home) as body:                      # a crafted history: what a faulty engine would leave behind
        j = body.journal
        j.record("mission.registered", {"mission_id": mid, "spec": spec, "command_digest": "x"}, key=mid)
        j.record("mission.action", {"mission_id": mid, "action_id": "send", "attempt": 0, "status": "DONE",
                                    "reasons": [], "receipt": None, "capability": "http.post",
                                    "route": "api", "cost_usd": 0.0, "scope_digest": "s", "at": "t"}, key=[mid, 1])
        j.record("mission.observed", {"mission_id": mid, "check_id": "paid", "passed": paid, "detail": "x",
                                      "receipt": "r", "rung": 0, "at": "t"}, key=[mid, 2])
        j.record("mission.achieved", {"mission_id": mid, "evidence": []}, key=[mid, "achieved"])
        result = devpath.business_loop_closed(j)
    assert result["met"] is False
    missing = result["incomplete"][0]["missing"]
    assert "greg_external_action:http.post" in missing and "no_person_did_the_outward_work" in missing
    assert ("payment_reconciled" in missing) is (not paid)


def test_n3_now_has_a_ledger_predicate():
    node = next(n for n in devpath.load()["nodes"] if n["id"] == "N3")
    assert node["predicate"] == "business_loop_closed" and node["predicate"] in devpath.PREDICATES


def test_the_cli_drafts_a_case_and_refuses_one_without_terms(tmp_path):
    import json, os, subprocess, sys
    root = Path(__file__).resolve().parents[2]
    home, *_ = make_body(tmp_path)

    def cli(*args):
        return subprocess.run([sys.executable, "-m", "greg", "--home", str(home), "mission", "new", "business-case",
                               *args, "--print-only"], capture_output=True, text=True, cwd=root,
                              env={**os.environ, "PYTHONPATH": str(root)}, timeout=60)
    out = cli("--case", "lease review 01", "--buyer", "Acme Property LLC", "--offer", "a reviewed lease summary",
              "--price", "250", "--acceptance", "summary within 5 business days")
    assert out.returncode == 0, out.stderr
    spec = json.loads(out.stdout)
    spec = spec.get("spec", spec)
    assert spec["mission_id"] == "m:case-lease-review-01" and spec["success_checks"][2]["sensor"]["params"]["amount"] == "250.00"
    refused = cli("--case", "x1y", "--buyer", "Acme", "--offer", "o", "--price", "250")
    assert refused.returncode != 0 and "--acceptance" in (refused.stderr + refused.stdout)


def test_n3_refuses_a_case_whose_human_work_was_never_observed(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    spec = case_spec(home)
    mid = spec["mission_id"]
    with Body(home) as body:                      # a person was asked, but their evidence never appeared
        j = body.journal
        j.record("mission.registered", {"mission_id": mid, "spec": spec, "command_digest": "x"}, key=mid)
        j.record("decision.requested", {"request_id": "req-open", "mission_id": mid, "kind": "HUMAN_WORK"},
                 key="req-open")
        j.record("mission.achieved", {"mission_id": mid, "evidence": []}, key=[mid, "achieved"])
        missing = devpath.business_loop_closed(j)["incomplete"][0]["missing"]
    assert "human_work_not_observed" in missing and "no_person_did_the_outward_work" not in missing
