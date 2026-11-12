"""The operational slice, case 2: a subcontractor's progress-payment draw (SYNTHETIC: no real party, payer or
payment), processed by the case-1 mechanism with a new rulebook and documents only.

The rulebook (tests/fixtures/request_case/progress_draw/rulebook.json, written by make_rulebook.py from the withheld
SPEC.md) and the twelve withheld case folders and LABELS.json beside it were written by someone who never saw the
implementation. Each withheld case is read by ``case.assess`` in place and graded by tests/unit/request_case_2_grading.py
(the translation fixed before the first case was assessed). Where the reading agrees with the label, the label is
asserted; where it does not, the test pins what the mechanism reads and says why (RESULT-case-2.md). The clean case
runs end to end through the ``request-case`` template on a real Body and MissionEngine with a test key (not the
founder's).
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

import pytest

from greg.body import Body, drop_intake
from greg.cases import load_rulebook
from greg.missions import validate_mission
from greg.templates import request_case
from tests.greg_fixtures import Clock, drop, make_body, signed
from tests.unit.request_case_2_grading import CASES, CHANNEL, COLUMNS, LABELS, REF, RULEBOOK, grade, read_case

AGREES = ["01-alder", "02-birch", "03-cedar", "04-dogwood", "05-elm", "06-fir", "07-ginkgo", "09-ironwood",
          "10-juniper", "11-larch", "12-maple"]
# Facts the rulebook's static needs ask for beyond the label: a rule lists its facts once, whatever the pay
# application bills, so L5 (billed at 0 percent) and CO-02 (not billed) are waited on, and so are the inspection's
# dispute lines that the R4 dispute items read.
OVER_ASKED = {
    "02-birch": ["inspection.dispute_line (not a SPEC fact)", "inspection.dispute_status (not a SPEC fact)",
                 "inspection.dispute_value (not a SPEC fact)", "inspection.line[CO-02].observed_percent_complete",
                 "inspection.line[L5].observed_percent_complete"],
    "10-juniper": ["sov.change_order[CO-02].amount", "sov.change_order[CO-02].approved",
                   "sov.line[L5].scheduled_value"],
}


@pytest.fixture(scope="module")
def graded(tmp_path_factory):
    root = tmp_path_factory.mktemp("case2")
    return {case: grade(case, read_case(case, root)) for case in sorted(p.name for p in CASES.iterdir())}


def test_the_case2_rulebook_is_data_the_mechanism_accepts_unchanged():
    book = load_rulebook(RULEBOOK.read_bytes())
    assert book["rulebook"] == "progress-draw-eligibility" and book["label"].startswith("SYNTHETIC")
    assert sorted(LABELS["cases"]) == sorted(p.name for p in CASES.iterdir()) and len(LABELS["cases"]) == 12


@pytest.mark.parametrize("case", AGREES)
def test_a_withheld_case_is_classified_and_routed_as_its_label_says(graded, case):
    g = graded[case]
    assert g["eligibility"] == g["expected_eligibility"] and g["route"] == g["expected_route"]
    assert sorted(g["deciding"]) == g["expected_deciding"]
    assert g["rule_outcomes"] == g["expected_rule_outcomes"]
    assert g["payment_gated"] == g["expected_payment"]
    assert g["missing_absent"] == [] and g["missing_extra"] == OVER_ASKED.get(case, [])
    assert not g["unknown_reported_decided"] and not g["decided_reported_unknown"]


def test_no_unknown_is_read_as_a_pass_or_a_failure_on_any_withheld_case(graded):
    assert all(not g["unknown_reported_decided"] for g in graded.values())


def test_the_duplicate_is_declined_naming_r9_since_the_mechanism_has_no_duplicate_state(graded):
    """08-hazel: the label is duplicate / refer_to_existing_draw with R1-R8 not evaluated. case.assess has four
    routing states (eligible, ineligible, undetermined, disputed) and evaluates every rule, so the resubmission is
    declined with R9 the one rule not met. No settlement path opens either way."""
    g = graded["08-hazel"]
    assert g["expected_eligibility"] == "duplicate" and g["expected_route"] == "refer_to_existing_draw"
    assert (g["eligibility"], g["route"], g["deciding"]) == ("ineligible", "decline_naming_failed_rules", ["R9"])
    assert g["rule_outcomes"] == {**{f"R{i}": "pass" for i in range(1, 9)}, "R9": "fail"}
    assert g["payment_gated"] == "not-applicable"


def test_the_statement_is_read_whatever_the_eligibility_and_matches_the_label_only_where_a_settlement_exists(graded):
    """case.assess reconciles the statement for every case; the SPEC gives a payment status only to an eligible
    draw. With no statement on file the ten other cases read 'no statement', where the label says not-applicable."""
    strict = {c: g["payment_strict"] for c, g in graded.items()}
    assert strict == {**{c: "unknown-no-statement" for c in strict}, "01-alder": "paid",
                      "11-larch": "unknown-ambiguous"}


# -- the clean case end to end, through the request-case template on a body -------------------------------------------

class Draw:
    """One body, one founder key (a test key, not Alfonso's), one withheld case copied inside the body's read root."""

    def __init__(self, tmp_path, case="01-alder"):
        self.home, self.key, self.body_id, self.data = make_body(tmp_path)
        self.folder = self.data / f"draw-{case}"
        shutil.copytree(CASES / case, self.folder)
        self.statement = self.folder / "statement.csv"
        self.held = self.statement.read_bytes() if self.statement.exists() else None
        if self.held is not None:
            self.statement.unlink()             # the statement is exported after the payment, as in case 1
        self.rulebook = self.data / "rulebooks" / "progress-draw.json"
        self.rulebook.parent.mkdir(parents=True)
        shutil.copyfile(RULEBOOK, self.rulebook)
        self.clock = Clock()
        self.body = Body(self.home, clock=self.clock).open()
        self.body.boot()
        self.send("BODY_DESIGNATE", {"purpose": "first_founder_body"})
        self.tick(1, 0)
        self.spec = validate_mission(request_case(reference=REF, request=f"pay application, {case}",
                                                  rulebook=self.rulebook, folder=self.folder, columns=COLUMNS))
        self.mid = self.spec["mission_id"]

    def send(self, kind, body):
        drop(self.home, signed(self.key, self.body_id, kind, body, now=self.clock.now))

    def tick(self, ticks=3, advance=4000):
        self.clock.advance(advance)
        for _ in range(ticks):
            self.body.tick()
            self.clock.advance(1)

    def events(self, kind):
        return [e.payload for e in self.body.journal.replay(kind) if e.payload.get("mission_id") == self.mid]

    def asks(self, kind=None):
        return [a for a in self.events("decision.requested") if kind is None or a["kind"] == kind]

    def human(self):
        return [a["evidence"]["function"] for a in self.asks("HUMAN_WORK")]

    def packets(self):
        root = self.body.deliver_root / "cases"
        return sorted(root.glob("*/packet.json"), key=lambda p: p.stat().st_mtime_ns) if root.is_dir() else []

    def latest(self):
        import json
        return json.loads(self.packets()[-1].read_text())["assessment"]

    def to_first_packet(self):
        drop_intake(self.home, source="mail://subcontractor.example/synthetic", channel=CHANNEL,
                    content=f"Pay application for draw 4 under {REF} is saved to the case folder. "
                            "SYNTHETIC — not a real party.")
        self.send("MISSION", self.spec)
        self.tick()
        [approval] = self.asks("APPROVAL")
        assert approval["action_id"] == "deliver-packet" and not self.packets()
        self.send("DECISION", {"request_id": approval["request_id"], "answer": "approve"})
        self.tick()

    def accept(self):
        (self.folder / "payer_acceptance.txt").write_text(
            f"SYNTHETIC — not a real party\ncontract_reference: {REF}\ndraw_number: 4\ndecision: accepted\n")

    def close(self):
        self.body.close()


def test_the_clean_draw_runs_through_the_request_case_template_to_a_reconciled_payment(tmp_path):
    d = Draw(tmp_path)
    try:
        assert d.spec["provenance"]["inputs"]["rulebook_sha256"] == hashlib.sha256(RULEBOOK.read_bytes()).hexdigest()
        d.to_first_packet()
        first = d.latest()
        assert first["route"]["state"] == "eligible"
        assert first["route"]["route"] == "prepare_settlement_and_await_payment" and first["unresolved"] == []
        assert first["request_recorded"] is True and first["payment"]["state"] == "unknown"
        assert d.human() == ["human.obtain_acceptance"]          # stopped at a person's act

        d.accept()
        d.tick()
        assert d.human() == ["human.obtain_acceptance", "human.pay"]
        assert d.latest()["accepted"] is True

        d.statement.write_bytes(d.held)                          # the payer's bank export, written after paying
        d.tick(5)
        [achieved] = d.events("mission.achieved")
        final = d.latest()
        assert final["payment_observed"] is True and final["projection"]["unknown"] == []
        [row] = final["projection"]["actual"]
        assert (row["amount"], row["currency"], row["row"]) == ("35100.00", "USD", 5)     # ACH-55187 only
        done = {e["action_id"] for e in d.events("mission.action") if e["status"] == "DONE"}
        assert done == {"deliver-packet"}                        # GREG's only act: packets
        [appraisal] = d.events("mission.appraised")
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        assert appraisal["checks"]["world_reobserved"] is True
        assert appraisal["checks"]["deliveries_bound_to_evidence"] is True
    finally:
        d.close()
