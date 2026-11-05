"""greg.compounding on hand-ordered ledgers: each condition of a credited reuse, and the price it reports.

The integration test (tests/integration/test_greg_retained_capability_compounding.py) runs real missions. These
cases fix the event order exactly, so each condition is shown to matter on its own.
"""
from __future__ import annotations

import pytest

from events.spine import EventSpine
from greg import compounding, sop
from greg.journal import Journal
from provenance.ledger import EvidenceLedger

CID, FN = "built.text.count.abc", "text.count"
OK = {c: True for c in sop.REQUIRED_CHECKS}


def spec(mid, check="c1"):
    return {"mission_id": mid, "success_checks": [{"check_id": check, "description": "d",
            "sensor": {"function": FN, "params": {"path": "/x"}, "target": "fs:x"},
            "predicate": {"op": "equals", "field": "n", "value": 1}}], "strategies": []}


class Ledger:
    def __init__(self, tmp_path):
        self.j = Journal(EventSpine(EvidenceLedger("sha256:" + "4" * 64, path=str(tmp_path / "l.jsonl"))),
                         actor="spiffe://uniimente.internal/test/compounding")
        self.n = 0

    def rec(self, kind, data):
        self.n += 1
        return self.j.record(kind, data, key=[kind, self.n])

    def register(self, mid, check="c1"):
        self.rec("mission.registered", {"mission_id": mid, "spec": spec(mid, check)})

    def form(self, mid, did="d1", cid=CID, owner=None, builds=2, costs=(0.25, 0.5)):
        self.rec("deficit.opened", {"deficit_id": did, "mission_id": owner or mid, "function": FN,
                                    "at": "2026-11-05T00:00:00Z"})
        for i in range(builds):
            self.rec("genesis.built", {"deficit_id": did, "attempt": i + 1, "cost_usd": costs[i]})
            self.rec("genesis.verified", {"deficit_id": did, "passed": i == builds - 1,
                                          "capability_id": cid if i == builds - 1 else f"{cid}.rejected"})
        self.rec("deficit.resolved", {"deficit_id": did, "capability_id": cid, "mission_id": mid,
                                      "at": "2026-11-05T00:01:30Z"})

    def use(self, mid, cid=CID, kind="mission.observed", receipt="sha256:r", status="DONE", passed=True,
            failure_class=None):
        data = {"mission_id": mid, "capability": cid, "receipt": receipt}
        if kind == "mission.action":
            data["status"] = status
        else:
            data["passed"] = passed
            if failure_class:
                data["failure_class"] = failure_class
        self.rec(kind, data)

    def appraise(self, mid, verdict="VERIFIED"):
        self.rec("mission.appraised", {"mission_id": mid, "verdict": verdict, "checks": OK})


def a_then_b(tmp_path, **form):
    led = Ledger(tmp_path)
    led.register("m:a")
    led.form("m:a", **form)
    led.use("m:a", cid=form.get("cid", CID))
    led.appraise("m:a")
    led.register("m:b", check="c2")
    led.use("m:b", cid=form.get("cid", CID))
    led.appraise("m:b")
    return led


def test_a_reuse_is_priced_from_what_the_forming_mission_paid(tmp_path):
    [reuse] = compounding.retained_reuse(a_then_b(tmp_path).j)["reuses"]
    assert reuse["avoided"] == {"builder_calls": 2, "build_cost_usd": 0.75, "build_cost_known": True,
                                "verifications": 2, "founder_attach": False, "blocked_seconds": 90.0}
    assert reuse["relation"] == "different procedure"


def test_an_unknown_build_cost_is_reported_as_unknown_not_zero(tmp_path):
    led = Ledger(tmp_path)
    led.register("m:a")
    led.form("m:a", costs=(None, 0.5))
    led.appraise("m:a")
    led.register("m:b", check="c2")
    led.use("m:b")
    led.appraise("m:b")
    [reuse] = compounding.retained_reuse(led.j)["reuses"]
    assert reuse["avoided"]["build_cost_known"] is False and reuse["avoided"]["build_cost_usd"] == 0.5


@pytest.mark.parametrize("who", ["m:a", "m:b"])
def test_a_rejected_appraisal_of_either_mission_cancels_the_credit(tmp_path, who):
    led = a_then_b(tmp_path)
    led.appraise(who, verdict="REJECTED")                      # the latest appraisal wins
    measured = compounding.retained_reuse(led.j)
    assert measured["reuses"] == []
    if who == "m:b":
        assert measured["refused"][0]["why_not"] == ["not appraised VERIFIED (appraisal rejected it)"]
    else:
        assert measured["formed"] == []


def test_a_built_in_capability_is_never_formed(tmp_path):
    led = a_then_b(tmp_path, cid="fs.read")
    assert compounding.retained_reuse(led.j) == {**compounding.retained_reuse(led.j), "formed": [], "reuses": []}


def test_a_resolution_claimed_by_another_mission_than_the_deficit_named_forms_nothing(tmp_path):
    led = a_then_b(tmp_path, owner="m:someone-else")
    measured = compounding.retained_reuse(led.j)
    assert measured["formed"] == [] and measured["reuses"] == []


def test_a_use_before_the_capability_was_formed_is_not_a_reuse(tmp_path):
    led = Ledger(tmp_path)
    led.register("m:b", check="c2")
    led.register("m:a")
    led.use("m:b")                                             # before A's resolution, and only then
    led.form("m:a")
    led.appraise("m:a")
    led.appraise("m:b")
    measured = compounding.retained_reuse(led.j)
    assert measured["reuses"] == [] and measured["refused"] == []


@pytest.mark.parametrize("use", [{"receipt": None}, {"kind": "mission.action", "status": "FAILED"}])
def test_an_unreceipted_or_failed_use_is_not_a_use(tmp_path, use):
    led = Ledger(tmp_path)
    led.register("m:a")
    led.form("m:a")
    led.appraise("m:a")
    led.register("m:b", check="c2")
    led.use("m:b", **use)
    led.appraise("m:b")
    measured = compounding.retained_reuse(led.j)
    assert measured["reuses"] == [] and measured["refused"] == []


def test_a_done_action_counts_like_an_observation(tmp_path):
    led = Ledger(tmp_path)
    led.register("m:a")
    led.form("m:a")
    led.appraise("m:a")
    led.register("m:b", check="c2")
    led.use("m:b", kind="mission.action")
    led.appraise("m:b")
    assert [r["reused_in"] for r in compounding.retained_reuse(led.j)["reuses"]] == ["m:b"]


def test_detach_between_formation_and_use_refuses_the_credit(tmp_path):
    led = Ledger(tmp_path)
    led.register("m:a")
    led.form("m:a")
    led.appraise("m:a")
    led.register("m:b", check="c2")
    led.rec("capability.state", {"capability_id": CID, "state": "DETACHED"})
    led.use("m:b")
    led.appraise("m:b")
    [refused] = compounding.retained_reuse(led.j)["refused"]
    assert refused["why_not"] == ["the capability was quarantined or detached before this use"]


def test_the_tiered_result_never_meets_on_a_ledger_with_no_founder_tier(tmp_path):
    result = compounding.capability_compounding(a_then_b(tmp_path).j)
    assert result["structurally_met"] is True and result["met"] is False and result["value"] == 0
    assert result["not_founder_tier"]


def test_a_use_after_a_later_re_formation_is_credited_to_that_formation_only(tmp_path):
    led = Ledger(tmp_path)
    led.register("m:a")
    led.form("m:a", did="d1")
    led.appraise("m:a")
    led.register("m:c", check="c3")
    led.form("m:c", did="d2", builds=1, costs=(0.1,))           # formed again, by C
    led.appraise("m:c")
    led.register("m:b", check="c2")
    led.use("m:b")
    led.appraise("m:b")
    reuses = compounding.retained_reuse(led.j)["reuses"]
    assert [(r["formed_in"], r["reused_in"], r["avoided"]["builder_calls"]) for r in reuses] == [("m:c", "m:b", 1)]


def test_a_mission_that_opened_its_own_deficit_for_the_function_paid_for_it_and_is_not_credited(tmp_path):
    led = Ledger(tmp_path)
    led.register("m:a")
    led.form("m:a")
    led.appraise("m:a")
    led.register("m:b", check="c2")
    led.rec("deficit.opened", {"deficit_id": "d-b", "mission_id": "m:b", "function": FN, "at": "2026-11-05T00:05:00Z"})
    led.use("m:b")
    led.appraise("m:b")
    measured = compounding.retained_reuse(led.j)
    assert measured["reuses"] == []
    assert measured["refused"][0]["why_not"] == [f"opened its own deficit for {FN}"]


# -- review of 2026-11-05: each reproduced finding, now refused or priced correctly ------------------------------

def reattach(led, mid, did, cid=CID):
    """Genesis rung verified_detached: an already-verified capability is attached to close a deficit; nothing built."""
    led.rec("deficit.opened", {"deficit_id": did, "mission_id": mid, "function": FN, "at": "2026-11-05T00:00:00Z"})
    led.rec("deficit.resolved", {"deficit_id": did, "capability_id": cid, "mission_id": mid,
                                 "at": "2026-11-05T00:00:01Z"})


def test_r1_a_re_attach_develops_nothing_and_is_not_a_formation(tmp_path):
    led = Ledger(tmp_path)
    led.register("m:a")
    reattach(led, "m:a", "d1")
    led.appraise("m:a")
    led.register("m:b", check="c2")
    led.use("m:b")
    led.appraise("m:b")
    measured = compounding.retained_reuse(led.j)
    assert measured["formed"] == [] and measured["reuses"] == []


def test_r1b_a_re_attach_does_not_take_the_use_from_the_mission_that_built_it(tmp_path):
    led = Ledger(tmp_path)
    led.register("m:x", check="c0")
    led.form("m:x", did="dx")
    led.appraise("m:x")
    led.register("m:a")
    reattach(led, "m:a", "da")
    led.appraise("m:a")
    led.register("m:b", check="c2")
    led.use("m:b")
    led.appraise("m:b")
    reuses = compounding.retained_reuse(led.j)["reuses"]
    assert sorted((r["formed_in"], r["reused_in"]) for r in reuses) == [("m:x", "m:b")]


@pytest.mark.parametrize("bad", [{"passed": False}, {"failure_class": "transient"}])
def test_r3_a_failed_or_transient_reading_is_not_a_use(tmp_path, bad):
    led = Ledger(tmp_path)
    led.register("m:a")
    led.form("m:a")
    led.appraise("m:a")
    led.register("m:b", check="c2")
    led.use("m:b", **bad)
    led.appraise("m:b")
    measured = compounding.retained_reuse(led.j)
    assert measured["reuses"] == [] and measured["refused"] == []


def test_r2_a_use_after_the_verdict_could_not_serve_it(tmp_path):
    led = Ledger(tmp_path)
    led.register("m:a")
    led.form("m:a")
    led.appraise("m:a")
    led.register("m:b", check="c2")
    led.appraise("m:b")
    led.use("m:b")
    [refused] = compounding.retained_reuse(led.j)["refused"]
    assert refused["why_not"] == ["used the capability only after its verdict"]


def test_a_forming_mission_verified_before_it_had_the_capability_is_not_a_formation(tmp_path):
    led = Ledger(tmp_path)
    led.register("m:a")
    led.appraise("m:a")
    led.form("m:a")
    led.register("m:b", check="c2")
    led.use("m:b")
    led.appraise("m:b")
    assert compounding.retained_reuse(led.j)["formed"] == []


def test_r6_a_use_before_a_later_quarantine_still_counts(tmp_path):
    led = Ledger(tmp_path)
    led.register("m:a")
    led.form("m:a")
    led.appraise("m:a")
    led.register("m:b", check="c2")
    led.use("m:b")
    led.rec("capability.state", {"capability_id": CID, "state": "QUARANTINED"})
    led.use("m:b")
    led.appraise("m:b")
    assert [r["reused_in"] for r in compounding.retained_reuse(led.j)["reuses"]] == ["m:b"]


@pytest.mark.parametrize("missing", ["m:a", "m:b"])
def test_r4_r5_an_unregistered_mission_is_never_credited(tmp_path, missing):
    led = Ledger(tmp_path)
    if missing != "m:a":
        led.register("m:a")
    led.form("m:a")
    led.appraise("m:a")
    if missing != "m:b":
        led.register("m:b", check="c2")
    led.use("m:b")
    led.appraise("m:b")
    measured = compounding.retained_reuse(led.j)
    assert measured["reuses"] == []
    assert "a mission of the pair has no registration on this ledger" in measured["refused"][0]["why_not"]


def test_a_boolean_cost_is_unknown_not_one_dollar(tmp_path):
    led = Ledger(tmp_path)
    led.register("m:a")
    led.form("m:a", costs=(True, 0.5))
    led.appraise("m:a")
    led.register("m:b", check="c2")
    led.use("m:b")
    led.appraise("m:b")
    [reuse] = compounding.retained_reuse(led.j)["reuses"]
    assert reuse["avoided"]["build_cost_usd"] == 0.5 and reuse["avoided"]["build_cost_known"] is False


def test_the_measure_stays_linear_enough_for_every_morning_report(tmp_path):
    import time
    led = Ledger(tmp_path)
    for i in range(150):                                  # 150 formations, 150 reuses: ~2,000 events
        cid = f"{CID}.{i}"
        led.register(f"m:a{i}", check=f"a{i}")
        led.form(f"m:a{i}", did=f"d{i}", cid=cid)
        led.appraise(f"m:a{i}")
        led.register(f"m:b{i}", check=f"b{i}")
        led.use(f"m:b{i}", cid=cid)
        led.appraise(f"m:b{i}")
    start = time.perf_counter()
    measured = compounding.retained_reuse(led.j)
    assert len(measured["reuses"]) == 150
    assert time.perf_counter() - start < 10


@pytest.mark.parametrize("verification", [{"passed": False, "capability_id": CID},
                                          {"passed": True, "capability_id": "built.text.count.other"}])
def test_a_formation_needs_a_passing_verification_of_the_capability_it_attached(tmp_path, verification):
    led = Ledger(tmp_path)
    led.register("m:a")
    led.rec("deficit.opened", {"deficit_id": "d1", "mission_id": "m:a", "function": FN, "at": "2026-11-05T00:00:00Z"})
    led.rec("genesis.built", {"deficit_id": "d1", "attempt": 1, "cost_usd": 0.2})
    led.rec("genesis.verified", {"deficit_id": "d1", **verification})
    led.rec("deficit.resolved", {"deficit_id": "d1", "capability_id": CID, "mission_id": "m:a",
                                 "at": "2026-11-05T00:00:30Z"})
    led.appraise("m:a")
    led.register("m:b", check="c2")
    led.use("m:b")
    led.appraise("m:b")
    assert compounding.retained_reuse(led.j)["formed"] == []


# -- formation by founder attach (the Mind's constructions): verified under A's deficit, then attached -------------

def founder_formed(led, mid, did="d1", cid=CID, attach_first=False, attach_id=None):
    led.rec("deficit.opened", {"deficit_id": did, "mission_id": mid, "function": FN, "at": "2026-11-05T00:00:00Z"})
    if attach_first:
        led.rec("capability.state", {"capability_id": attach_id or cid, "state": "ATTACHED", "by": "founder command"})
    led.rec("genesis.verified", {"deficit_id": did, "passed": True, "capability_id": cid})
    led.rec("deficit.awaiting_attach", {"deficit_id": did, "capability_id": cid})
    if not attach_first:
        led.rec("capability.state", {"capability_id": attach_id or cid, "state": "ATTACHED", "by": "founder command"})


def b_after(led):
    led.register("m:b", check="c2")
    led.use("m:b")
    led.appraise("m:b")


def test_a_capability_the_founder_attached_after_it_passed_under_a_deficit_is_a_formation(tmp_path):
    led = Ledger(tmp_path)
    led.register("m:a")
    founder_formed(led, "m:a")
    led.use("m:a")
    led.appraise("m:a")
    b_after(led)
    [reuse] = compounding.retained_reuse(led.j)["reuses"]
    assert reuse["formed_in"] == "m:a" and reuse["avoided"]["founder_attach"] is True
    assert reuse["avoided"]["verifications"] == 1 and reuse["avoided"]["blocked_seconds"] is not None


@pytest.mark.parametrize("variant", [{"attach_first": True}, {"attach_id": "built.text.count.other"}])
def test_an_attach_before_verification_or_of_another_capability_is_not_a_formation(tmp_path, variant):
    led = Ledger(tmp_path)
    led.register("m:a")
    founder_formed(led, "m:a", **variant)
    led.appraise("m:a")
    b_after(led)
    assert compounding.retained_reuse(led.j)["formed"] == []


def test_a_founder_attach_after_the_forming_missions_verdict_is_not_its_formation(tmp_path):
    led = Ledger(tmp_path)
    led.register("m:a")
    led.rec("deficit.opened", {"deficit_id": "d1", "mission_id": "m:a", "function": FN, "at": "2026-11-05T00:00:00Z"})
    led.rec("genesis.verified", {"deficit_id": "d1", "passed": True, "capability_id": CID})
    led.appraise("m:a")
    led.rec("capability.state", {"capability_id": CID, "state": "ATTACHED", "by": "founder command"})
    b_after(led)
    assert compounding.retained_reuse(led.j)["formed"] == []


def test_the_same_procedure_on_new_inputs_is_a_different_mission_and_says_so(tmp_path):
    led = Ledger(tmp_path)
    led.register("m:a")
    led.form("m:a")
    led.appraise("m:a")
    led.rec("mission.registered", {"mission_id": "m:b", "spec": dict(spec("m:b"), success_checks=[
        dict(spec("m:b")["success_checks"][0], sensor={"function": FN, "params": {"path": "/other"}, "target": "fs:x"})])})
    led.use("m:b")
    led.appraise("m:b")
    [reuse] = compounding.retained_reuse(led.j)["reuses"]
    assert reuse["relation"] == "same procedure, new inputs"


def test_a_founder_attach_of_a_candidate_that_failed_verification_is_not_a_formation(tmp_path):
    led = Ledger(tmp_path)
    led.register("m:a")
    led.rec("deficit.opened", {"deficit_id": "d1", "mission_id": "m:a", "function": FN, "at": "2026-11-05T00:00:00Z"})
    led.rec("genesis.verified", {"deficit_id": "d1", "passed": False, "capability_id": CID})
    led.rec("capability.state", {"capability_id": CID, "state": "ATTACHED", "by": "founder command"})
    led.appraise("m:a")
    b_after(led)
    assert compounding.retained_reuse(led.j)["formed"] == []
