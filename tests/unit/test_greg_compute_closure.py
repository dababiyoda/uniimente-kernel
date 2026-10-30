"""Compute closure (directive sections 48, 58, 60, 71): memory and IO pressure, a working re-ask, the heaviest
measured workload, a deterministic benchmark and a before/after verdict.

Real bodies and real ledgers throughout. Timing fixtures emit events at fixed ledger times so the
quantities are exact; real benchmark timings are reported by the evidence README, never asserted here.
"""
import ast
import json
import os
from pathlib import Path
import sys
import tempfile
import time

import pytest

from events.spine import Event, EventSpine
from greg import asks, compute
from greg.body import Body
from greg.journal import PRINCIPAL, SOURCE, Journal, fact_id
from provenance.ledger import EvidenceLedger
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy

ROOT = Path(__file__).resolve().parents[2]
N = compute.SUSTAINED_SAMPLES


def telemetry(journal, at, **fields):
    base = {"at": at, "cores": 4, "load1": 0.8, "load_ratio": 0.2, "disk_free_ratio": 0.5, "memory_bytes": 1,
            "disk_total": 1, "disk_free": 1, "machine": "x86_64", "system": "Linux"}
    compute.record_telemetry(journal, Path("."), telemetry={**base, **fields})


def window(journal, prefix, **fields):
    for i in range(N):
        telemetry(journal, f"{prefix}:{i:02d}Z", **fields)


CPU = {"load1": 5.0, "load_ratio": 1.25}


def compute_asks(journal):
    return [e.payload for e in journal.replay("decision.requested") if e.payload["kind"] == "COMPUTE"]


def answer(home, key, body_id, request_id, verdict="reject"):
    """Alfonso's signed DECISION, applied by the body exactly as in production."""
    drop(home, signed(key, body_id, "DECISION", {"request_id": request_id, "answer": verdict}))
    with Body(home, clock=Clock()) as body:
        body.tick()
        assert any(e.payload["request_id"] == request_id for e in body.journal.replay("decision.answered"))


# --- the re-ask defect -----------------------------------------------------------------------------------------

def test_after_a_signed_answer_a_still_sustained_cpu_bottleneck_is_asked_again(tmp_path):
    """The defect: request_id hashed the resource alone, so after one answered cpu ask GREG could never ask again."""
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        window(body.journal, "2026-10-30T00:00", **CPU)
        first = compute.recommend(body.journal)
    answer(home, key, body_id, first["request_id"])
    with Body(home) as body:
        window(body.journal, "2026-10-30T02:00", **CPU)
        again = compute.recommend(body.journal)
    assert again is not None and again["request_id"] != first["request_id"]


def test_a_bottleneck_that_outlives_an_answer_is_asked_again_once_and_never_while_pending(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        window(body.journal, "2026-10-30T00:00", **CPU)
        first = compute.recommend(body.journal)
        assert first is not None and first["evidence"]["epoch"] == 0
        window(body.journal, "2026-10-30T01:00", **CPU)
        assert compute.recommend(body.journal) is None          # the first ask is pending: no second one
    answer(home, key, body_id, first["request_id"])
    with Body(home) as body:
        for i in range(N - 1):                                   # samples from before the answer do not count
            telemetry(body.journal, f"2026-10-30T02:{i:02d}Z", **CPU)
            assert compute.recommend(body.journal) is None
        telemetry(body.journal, f"2026-10-30T02:{N - 1:02d}Z", **CPU)
        second = compute.recommend(body.journal)                 # a full window measured after the answer
        assert second is not None and second["request_id"] != first["request_id"]
        assert second["evidence"]["epoch"] == 1 and second["evidence"]["earlier_asks"] == [first["request_id"]]
        assert "asked again" in second["why_now"]
        asks.validate(second)
        assert asks.screen(second) == [] and "wording_withheld" not in second
        window(body.journal, "2026-10-30T03:00", **CPU)
        assert compute.recommend(body.journal) is None           # the re-ask is pending in its turn
        assert [a["request_id"] for a in compute_asks(body.journal)] == [first["request_id"], second["request_id"]]


def test_the_first_ask_keeps_its_identity_so_existing_ledgers_are_not_asked_twice(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        window(body.journal, "2026-10-30T00:00", **CPU)
        first = compute.recommend(body.journal)
    legacy = "req-compute-" + compute.sha256_json({"resource": "cpu"})[7:23]
    assert first["request_id"] == legacy


def test_a_withdrawn_ask_also_closes_its_epoch(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        window(body.journal, "2026-10-30T00:00", **CPU)
        first = compute.recommend(body.journal)
        # what a restore from a backup records for an ask the old body raised (greg/recovery.py)
        body.journal.record("decision.withdrawn", {"request_id": first["request_id"], "mission_id": None,
                                                   "why": "restored from a backup", "at": "2026-10-30T00:30:00Z"},
                            key=[first["request_id"], "withdrawn"])
        assert compute.recommend(body.journal) is None           # the samples so far predate the withdrawal
        window(body.journal, "2026-10-30T01:00", **CPU)
        second = compute.recommend(body.journal)
    assert second is not None and second["evidence"]["epoch"] == 1


def test_an_answer_row_no_signed_decision_stands_behind_does_not_close_the_ask(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        window(body.journal, "2026-10-30T00:00", **CPU)
        first = compute.recommend(body.journal)
        body.journal.record("decision.answered", {"request_id": first["request_id"], "mission_id": None,
                                                  "answer": "reject", "reason": "", "command_digest": "sha256:forged"})
        window(body.journal, "2026-10-30T01:00", **CPU)
        assert compute.recommend(body.journal) is None
        state = compute.ask_state(body.journal, "cpu")
    assert state["pending"] == [first["request_id"]] and state["epoch"] == 0


def test_a_pending_compute_ask_for_the_resource_blocks_a_new_one_whatever_its_identity(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        window(body.journal, "2026-10-30T00:00", **CPU)
        found = compute.bottleneck(body.journal)
        asks.record(body.journal, asks.resource_request(                 # an ask under another identity scheme
            request_id="req-compute-recorded-elsewhere", kind="COMPUTE", resource="compute", why_now=found["measure"],
            recommendation="optimize first", evidence={"bottleneck": found},
            options=[{"option": "optimize", "cost": "none", "expected_effect": "less load"},
                     {"option": "a node", "cost": "hardware price", "expected_effect": "more capacity"}],
            expected_effect="less queueing", uncertainty="unpriced", authority_requested={"spend": "none requested"},
            consequence_of_no_response="nothing is bought", created_at="2026-10-30T00:05:00Z"))
        assert compute.ask_state(body.journal, "cpu")["pending"] == ["req-compute-recorded-elsewhere"]
        assert compute.recommend(body.journal) is None


def test_an_ask_row_under_another_identity_is_not_an_ask_and_does_not_advance_the_epoch(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        window(body.journal, "2026-10-30T00:00", **CPU)
        found = compute.bottleneck(body.journal)
        # not keyed on its request id, so no founder surface shows it (asks.open_requests) and nobody can answer it
        body.journal.record("decision.requested", {"request_id": "req-compute-copy", "kind": "COMPUTE",
                                                   "mission_id": None, "evidence": {"bottleneck": found}},
                            key=["copy", "elsewhere"])
        state = compute.ask_state(body.journal, "cpu")
        first = compute.recommend(body.journal)
    assert state["epoch"] == 0 and state["closed"] == [] and state["pending"] == []
    assert first["request_id"] == "req-compute-" + compute.sha256_json({"resource": "cpu"})[7:23]


def test_one_open_ask_per_resource_not_one_for_all_compute(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        window(body.journal, "2026-10-30T00:00", **CPU)
        cpu = compute.recommend(body.journal)
        window(body.journal, "2026-10-30T01:00", **CPU, psi_memory_some_avg60=40.0)
        memory = compute.recommend(body.journal)
    assert cpu["evidence"]["bottleneck"]["resource"] == "cpu"
    assert memory["evidence"]["bottleneck"]["resource"] == "memory" and memory["request_id"] != cpu["request_id"]


# --- memory and IO pressure ------------------------------------------------------------------------------------

def test_sustained_memory_pressure_with_low_load_is_a_memory_bottleneck(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        window(body.journal, "2026-10-30T00:00", psi_memory_some_avg60=35.0)     # load/cores 0.2: no cpu rule
        found = compute.bottleneck(body.journal)
        assert found is not None and found["resource"] == "memory" and found["also_sustained"] == []
        assert str(compute.MEMORY_PSI_THRESHOLD) in found["measure"]
        message = compute.recommend(body.journal)
    asks.validate(message)
    assert message["evidence"]["samples"][0]["psi_memory_some_avg60"] == 35.0


def test_memavailable_below_the_floor_is_memory_pressure_without_psi():
    floor = compute.MEM_AVAILABLE_FLOOR
    low = [{"at": str(i), "load_ratio": 0.1, "disk_free_ratio": 0.5, "mem_available_ratio": floor / 2,
            "psi_memory_some_avg60": None} for i in range(N)]
    assert compute.assess(low)["resource"] == "memory"
    assert compute.assess([{**s, "mem_available_ratio": floor} for s in low]) is None     # at the floor is not below


def test_sustained_io_pressure_is_an_io_bottleneck():
    samples = [{"at": str(i), "load_ratio": 0.3, "disk_free_ratio": 0.5,
                "psi_io_some_avg60": compute.IO_PSI_THRESHOLD} for i in range(N)]
    assert compute.assess(samples)["resource"] == "io"


def test_precedence_is_memory_then_io_then_cpu_then_disk_and_the_rest_are_reported():
    every = {"load_ratio": 2.0, "disk_free_ratio": 0.01, "psi_memory_some_avg60": 50.0, "psi_io_some_avg60": 50.0}
    order = []
    for drop_rule in (None, "psi_memory_some_avg60", "psi_io_some_avg60", "load_ratio"):
        fields = {k: v for k, v in every.items() if k != drop_rule}
        found = compute.assess([{"at": str(i), **fields} for i in range(N)])
        order.append(found["resource"])
        every = fields
    assert order == ["memory", "io", "cpu", "disk"] == list(compute.PRECEDENCE)
    everything = {"load_ratio": 2.0, "disk_free_ratio": 0.01, "psi_memory_some_avg60": 50.0,
                  "psi_io_some_avg60": 50.0}
    assert compute.assess([{"at": str(i), **everything} for i in range(N)])["also_sustained"] == ["io", "cpu", "disk"]


@pytest.mark.parametrize("hole", [None, "missing"])
def test_a_sample_missing_a_field_never_counts_as_pressure(hole):
    pressed = [{"at": str(i), "load_ratio": 0.1, "disk_free_ratio": 0.5, "psi_memory_some_avg60": 90.0,
                "psi_io_some_avg60": 90.0, "mem_available_ratio": 0.01} for i in range(N)]
    gap = {"at": "gap", "load_ratio": 0.1, "disk_free_ratio": 0.5}
    if hole is None:
        gap.update(psi_memory_some_avg60=None, psi_io_some_avg60=None, mem_available_ratio=None)
    assert compute.assess(pressed)["resource"] == "memory"
    assert compute.assess(pressed[:-1] + [gap]) is None
    legacy = [{"at": str(i), "cores": 8, "load_ratio": 0.2, "disk_free_ratio": 0.5} for i in range(N)]
    assert compute.assess(legacy) is None                                          # pre-PSI telemetry: no new rule


@pytest.mark.skipif(not Path("/proc/pressure/memory").exists(), reason="this kernel exposes no PSI")
def test_sample_reads_real_pressure_and_memavailable_on_this_host(tmp_path):
    data = compute.sample(tmp_path)
    for resource in ("cpu", "memory", "io"):
        readable = os.access(compute.PROC / "pressure" / resource, os.R_OK)    # PSI is absent on some kernels
        for window_ in ("avg10", "avg60"):
            value = data[f"psi_{resource}_some_{window_}"]
            assert (isinstance(value, float) and 0.0 <= value <= 100.0) if readable else value is None
    assert 0 < data["mem_available_bytes"] <= data["mem_total_bytes"]
    assert 0 < data["mem_available_ratio"] <= 1
    for kept in ("at", "machine", "system", "cores", "load1", "load_ratio", "memory_bytes", "disk_total",
                 "disk_free", "disk_free_ratio"):
        assert kept in data
    json.dumps(data, allow_nan=False)                                              # what the ledger will retain


def test_unreadable_or_malformed_pressure_is_none_never_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(compute, "PROC", tmp_path / "no-proc")
    data = compute.sample(tmp_path)
    fields = [k for k in data if k.startswith("psi_") or k.startswith("mem_")]
    assert len(fields) == 9 and all(data[k] is None for k in fields)
    proc = tmp_path / "proc"
    (proc / "pressure").mkdir(parents=True)
    (proc / "pressure" / "cpu").write_text("some avg10=abc avg60=nan avg300=0.00 total=1\n")
    (proc / "pressure" / "memory").write_text("full avg10=5.00 avg60=5.00 avg300=0.00 total=1\n")
    (proc / "pressure" / "io").write_text("some avg10=0.00 avg60=7.50 avg300=0.00 total=1\n")
    (proc / "meminfo").write_text("MemTotal:       4000000 kB\nMemFree:        100 kB\n")
    monkeypatch.setattr(compute, "PROC", proc)
    data = compute.sample(tmp_path)
    assert data["psi_cpu_some_avg10"] is None and data["psi_cpu_some_avg60"] is None
    assert data["psi_memory_some_avg10"] is None and data["psi_memory_some_avg60"] is None   # only a "full" line
    assert data["psi_io_some_avg10"] == 0.0 and data["psi_io_some_avg60"] == 7.5           # a real zero stays zero
    assert data["mem_total_bytes"] == 4000000 * 1024 and data["mem_available_bytes"] is None
    assert data["mem_available_ratio"] is None
    (proc / "pressure" / "cpu").write_text("some avg10=-1.00 avg60=-0.50 avg300=0.00 total=-5\n")
    assert compute._pressure("cpu") == (None, None) and compute._stall_totals()["cpu"] is None   # not a reading


# --- quantify: step timing and the heaviest measured workload ----------------------------------------------------

def emit(journal, kind, payload, at, key):
    journal.spine.emit(Event(type="greg." + kind, source=SOURCE, actor="spiffe://uniimente.internal/greg/test",
                             legal_principal=PRINCIPAL, event_id=fact_id(kind, key), payload=payload,
                             occurred_at=at))


def step(journal, mission_id, action_id, capability, start, end, **extra):
    emit(journal, "mission.dispatching", {"mission_id": mission_id, "action_id": action_id, "attempt": 0,
                                          "capability": capability}, start, [mission_id, action_id, "d"])
    emit(journal, "mission.action", {"mission_id": mission_id, "action_id": action_id, "attempt": 0,
                                     "status": "DONE", "capability": capability, **extra}, end,
         [mission_id, action_id, "a"])


def timed_journal():
    """Before the window, fs.write takes 2 s three times. In a 2400 s window it takes 6 s twice and a cognition solve
    with no history takes 30 s; a step recovered after a restart (its gap is downtime) is not timing."""
    journal = Journal(EventSpine(EvidenceLedger("compute-closure-fixture")), actor="spiffe://uniimente.internal/t")
    for i in range(3):
        step(journal, "m:a", f"w{i}", "fs.write", f"2026-10-29T10:00:{i}0Z", f"2026-10-29T10:00:{i}2Z")
    for i in range(N):
        emit(journal, "compute.telemetry", {"at": f"t{i}", "cores": 4, "load_ratio": 1.5, "disk_free_ratio": 0.5},
             f"2026-10-30T00:{i * 10:02d}:00Z", f"t{i}")
        if i == 1:
            step(journal, "m:a", "w3", "fs.write", "2026-10-30T00:11:00Z", "2026-10-30T00:11:06Z")
            step(journal, "m:b", "solve", "cognition.solve", "2026-10-30T00:12:00Z", "2026-10-30T00:12:30Z")
        if i == 2:
            step(journal, "m:a", "w4", "fs.write", "2026-10-30T00:21:00Z", "2026-10-30T00:21:06Z")
            step(journal, "m:c", "late", "fs.write", "2026-10-30T00:22:00Z", "2026-10-30T03:22:00Z",
                 routing={"chosen": "late", "recovered": True})
    step(journal, "m:a", "after", "fs.write", "2026-10-30T01:00:00Z", "2026-10-30T01:59:00Z")  # after the window
    return journal


def test_quantify_names_the_heaviest_measured_workload_and_labels_the_delay_an_estimate():
    journal = timed_journal()
    found = compute.quantify(journal, journal.replay("compute.telemetry"))
    work, delay = found["workload"], found["delay"]
    assert work["recorded"] is True and work["steps_in_window"] == 3
    assert work["heaviest"] == {"capability": "cognition.solve", "steps": 1, "seconds": 30.0, "share": 0.7143}
    assert [r["capability"] for r in work["by_capability"]] == ["cognition.solve", "fs.write"]
    assert delay["latency_inflation"] == {"fs.write": 3.0}
    assert delay["excess_step_seconds"] == 8.0 and delay["window_seconds"] == 2400.0
    assert delay["mission_hours_delayed_per_week"] == 0.56               # 8 s per 2400 s, scaled to 604800 s
    assert delay["basis"].startswith("estimate (method: ") and "measured" not in delay["basis"]
    assert delay["unbaselined_capabilities"] == ["cognition.solve"]


def test_the_ask_names_the_heaviest_workload_only_when_the_journal_timed_steps(tmp_path):
    journal = timed_journal()
    named = compute.recommend(journal)
    asks.validate(named)
    assert "cognition.solve" in named["options"][0]["option"] and "71%" in named["options"][0]["option"]
    assert named["options"][0]["cost"].startswith("none")
    assert named["evidence"]["delay"]["basis"].startswith("estimate (method: ")
    assert "unpriced: no ROI claim" in named["uncertainty"]
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        window(body.journal, "2026-10-30T00:00", **CPU)
        untimed = compute.recommend(body.journal)
    assert "records no mission step timing" in untimed["options"][0]["option"]
    assert untimed["evidence"]["workload"]["heaviest"] is None
    assert untimed["evidence"]["delay"]["mission_hours_delayed_per_week"] is None
    assert untimed["evidence"]["delay"]["basis"].startswith("estimate (method: ")


def test_steps_outside_the_bottleneck_window_point_outside_greg():
    journal = Journal(EventSpine(EvidenceLedger("compute-closure-fixture")), actor="spiffe://uniimente.internal/t")
    step(journal, "m:a", "w0", "fs.write", "2026-10-29T10:00:00Z", "2026-10-29T10:00:02Z")
    for i in range(N):
        emit(journal, "compute.telemetry", {"at": f"t{i}", "cores": 4, "load_ratio": 1.5, "disk_free_ratio": 0.5},
             f"2026-10-30T00:{i * 10:02d}:00Z", f"t{i}")
    message = compute.recommend(journal)
    assert "no GREG mission step ran in the bottleneck window" in message["options"][0]["option"]


def fixture_journal():
    return Journal(EventSpine(EvidenceLedger("compute-closure-fixture")), actor="spiffe://uniimente.internal/t")


def test_a_step_that_waited_for_the_founder_or_for_a_restart_is_not_timed():
    """Review finding WU05-F1: a re-dispatch reuses its deduplicated first intent, so the founder's approval wait and
    the body's downtime were booked as capability time and could name the wrong heaviest workload."""
    journal = fixture_journal()
    # APPROVAL: the intent, the ask and the block, the founder's answer an hour later, then the same intent runs
    intent = {"mission_id": "m:a", "action_id": "pay", "attempt": 0, "capability": "fs.write"}
    emit(journal, "mission.dispatching", intent, "2026-10-30T10:00:00Z", ["m:a", "pay", 0, "s"])
    emit(journal, "decision.requested", {"request_id": "req-a", "mission_id": "m:a", "kind": "APPROVAL"},
         "2026-10-30T10:00:01Z", "req-a")
    emit(journal, "mission.blocked", {"mission_id": "m:a", "blocker": {"request_id": "req-a"}},
         "2026-10-30T10:00:01Z", ["m:a", "blocked"])
    emit(journal, "decision.answered", {"request_id": "req-a", "mission_id": "m:a", "answer": "approve"},
         "2026-10-30T11:00:00Z", ["req-a", "answered"])
    emit(journal, "mission.action", {**intent, "status": "DONE"}, "2026-10-30T11:00:02Z", ["m:a", "pay", "a"])
    # RESTART: the intent, then the body stops before the Gate claims the dispatch and boots ten minutes later
    intent = {"mission_id": "m:b", "action_id": "w", "attempt": 0, "capability": "fs.write"}
    emit(journal, "mission.dispatching", intent, "2026-10-30T12:00:00Z", ["m:b", "w", 0, "s"])
    emit(journal, "body.booted", {"boot_id": "boot-2"}, "2026-10-30T12:10:00Z", "boot-2")
    emit(journal, "mission.action", {**intent, "status": "DONE"}, "2026-10-30T12:10:02Z", ["m:b", "w", "a"])
    # a later intent for the same slot (its scope changed) that ran straight through: timed from that intent
    intent = {"mission_id": "m:c", "action_id": "w", "attempt": 0, "capability": "fs.write"}
    emit(journal, "mission.dispatching", intent, "2026-10-30T13:00:00Z", ["m:c", "w", 0, "s1"])
    emit(journal, "mission.observed", {"mission_id": "m:c", "check_id": "n"}, "2026-10-30T13:30:00Z", ["m:c", "o"])
    emit(journal, "mission.dispatching", intent, "2026-10-30T13:30:01Z", ["m:c", "w", 0, "s2"])
    emit(journal, "mission.action", {**intent, "status": "DONE"}, "2026-10-30T13:30:04Z", ["m:c", "w", "a"])
    # a capability's own record inside its dispatch is not an interruption
    intent = {"mission_id": "m:d", "action_id": "f", "attempt": 0, "capability": "foundry.repair"}
    emit(journal, "mission.dispatching", intent, "2026-10-30T14:00:00Z", ["m:d", "f", 0, "s"])
    emit(journal, "foundry.committing", {"mission_id": "m:d"}, "2026-10-30T14:00:01Z", ["m:d", "commit"])
    emit(journal, "mission.action", {**intent, "status": "DONE"}, "2026-10-30T14:00:02Z", ["m:d", "f", "a"])
    assert [(s["mission_id"], s["seconds"]) for s in compute.step_times(journal)] == [("m:c", 3.0), ("m:d", 2.0)]



@pytest.mark.parametrize("between", ["mission.observed", "decision.answered", "body.booted", "command.accepted",
                                     "compute.telemetry"])
def test_any_loop_record_between_an_intent_and_its_outcome_voids_the_timing(between):
    """The body is single-threaded: only its loop writes these, never a dispatch in progress (compute.LOOP_RECORDS)."""
    journal = fixture_journal()
    intent = {"mission_id": "m:a", "action_id": "w", "attempt": 0, "capability": "fs.write"}
    emit(journal, "mission.dispatching", intent, "2026-10-30T10:00:00Z", ["m:a", "w", 0, "s"])
    emit(journal, between, {"mission_id": "m:a"}, "2026-10-30T10:30:00Z", ["between", between])
    emit(journal, "mission.action", {**intent, "status": "DONE"}, "2026-10-30T10:30:02Z", ["m:a", "w", "a"])
    assert compute.step_times(journal) == []

def test_reconciliations_outcomes_without_an_intent_and_a_stepped_clock_are_not_timing():
    journal = fixture_journal()
    # an UNCERTAIN dispatch, then the founder's reconciliation of that same dispatch twenty minutes later
    intent = {"mission_id": "m:r", "action_id": "c", "attempt": 0, "capability": "worker.commission"}
    emit(journal, "mission.dispatching", intent, "2026-10-30T00:11:00Z", ["m:r", "c", 0, "s"])
    emit(journal, "mission.action", {**intent, "status": "UNCERTAIN"}, "2026-10-30T00:11:05Z", ["m:r", "c", "u"])
    emit(journal, "mission.action", {**intent, "status": "DONE", "route": "founder_reconciliation"},
         "2026-10-30T00:31:00Z", ["m:r", "c", "reconciled"])
    # refused before any intent was written
    emit(journal, "mission.action", {"mission_id": "m:n", "action_id": "x", "attempt": 0, "status": "REFUSED",
                                     "capability": "fs.write"}, "2026-10-30T00:40:00Z", ["m:n", "x", "a"])
    # the clock stepped back between the intent and the outcome
    intent = {"mission_id": "m:s", "action_id": "w", "attempt": 0, "capability": "fs.write"}
    emit(journal, "mission.dispatching", intent, "2026-10-30T00:50:00Z", ["m:s", "w", 0, "s"])
    emit(journal, "mission.action", {**intent, "status": "DONE"}, "2026-10-30T00:49:00Z", ["m:s", "w", "a"])
    assert [s["seconds"] for s in compute.step_times(journal)] == [5.0]


def journal_with_window(steps):
    journal = fixture_journal()
    for i in range(N):
        emit(journal, "compute.telemetry", {"at": f"t{i}", "cores": 4, "load_ratio": 1.5, "disk_free_ratio": 0.5},
             f"2026-10-30T00:{i * 10:02d}:00Z", f"t{i}")
        if i == 1:
            steps(journal)
    return journal


def test_a_step_without_a_capability_or_a_window_of_zero_second_steps_never_breaks_the_ask():
    """Review finding WU05-F4: a capability-less outcome beside a named one, or a 0 s total, raised in recommend()."""
    def unnamed(journal):
        step(journal, "m:a", "x", "fs.write", "2026-10-30T00:11:00Z", "2026-10-30T00:11:06Z")
        emit(journal, "mission.dispatching", {"mission_id": "m:a", "action_id": "y", "attempt": 0,
                                              "capability": "fs.write"}, "2026-10-30T00:12:00Z", ["m:a", "y", "d"])
        emit(journal, "mission.action", {"mission_id": "m:a", "action_id": "y", "attempt": 0, "status": "REFUSED",
                                         "reasons": ["pipeline input unavailable"]},     # no capability: its input
             "2026-10-30T00:12:06Z", ["m:a", "y", "a"])
    message = compute.recommend(journal_with_window(unnamed))
    asks.validate(message)
    assert [r["capability"] for r in message["evidence"]["workload"]["by_capability"]] == ["fs.write"]
    zero = compute.recommend(journal_with_window(
        lambda j: step(j, "m:a", "x", "fs.write", "2026-10-30T00:11:00Z", "2026-10-30T00:11:00Z")))
    asks.validate(zero)
    assert zero["evidence"]["workload"]["heaviest"] is None
    assert "no measurable time" in zero["options"][0]["option"]


WAIT = 1.0      # seconds the founder or the body takes; hours in life


def paid_write(home, key, body_id, mid):
    ws = workspace(home, mid)
    drop(home, signed(key, body_id, "MISSION", mission(
        mid, checks=[note_check("filed", ws / "f.txt", "filed")], capabilities=["fs.read"], budget=1.0,
        strategies=[write_strategy("file", "f.txt", "filed", ["filed"], cost_usd=0.5, rationale="file now")])))


def plain_write(home, key, body_id, mid):
    ws = workspace(home, mid)
    drop(home, signed(key, body_id, "MISSION", mission(
        mid, checks=[note_check("done", ws / "f.txt", "done")], capabilities=["fs.read", "fs.write"],
        strategies=[write_strategy("w", "f.txt", "done", ["done"])])))


def test_on_a_real_body_the_founders_approval_wait_is_not_booked_as_step_time(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    paid_write(home, key, body_id, "m:urgent-taxes")
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(4):
            body.tick()
            clock.advance(1)
        rid = next(e.payload["request_id"] for e in body.journal.replay("decision.requested")
                   if e.payload["kind"] == "APPROVAL")
    time.sleep(WAIT)
    drop(home, signed(key, body_id, "DECISION", {"request_id": rid, "answer": "approve"}))
    with Body(home, clock=clock) as body:
        for _ in range(6):
            body.tick()
            clock.advance(1)
        assert len(body.journal.replay("mission.dispatching")) == 1        # the approved run reused the intent
        assert [e.payload["status"] for e in body.journal.replay("mission.action")] == ["DONE"]
        assert compute.step_times(body.journal) == []


class Killed(BaseException):
    pass


def test_on_a_real_body_downtime_before_the_gate_claimed_a_dispatch_is_not_step_time(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    plain_write(home, key, body_id, "m:write-once")
    clock = Clock()
    with pytest.raises(Killed):
        with Body(home, clock=clock) as body:
            act = body.engine.office.act

            def die(*args, **kwargs):           # the process dies inside the dispatch, before the Gate claims it
                if kwargs.get("manifest") is not None and kwargs["manifest"].capability_id == "fs.write":
                    raise Killed()
                return act(*args, **kwargs)
            body.engine.office.act = die
            for _ in range(8):
                body.tick()
                clock.advance(1)
    time.sleep(WAIT)
    with Body(home, clock=clock) as body:
        for _ in range(12):
            body.tick()
            clock.advance(40)
        actions = [e.payload for e in body.journal.replay("mission.action")]
        assert [a["status"] for a in actions] == ["DONE"] and not actions[0]["routing"].get("recovered")
        assert compute.step_times(body.journal) == []


def test_on_a_real_body_a_dispatch_that_ran_straight_through_is_timed(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    plain_write(home, key, body_id, "m:write-once")
    clock = Clock()
    with Body(home, clock=clock) as body:
        for _ in range(6):
            body.tick()
            clock.advance(1)
        steps = compute.step_times(body.journal)
    assert [(s["mission_id"], s["capability"]) for s in steps] == [("m:write-once", "fs.write")]
    assert 0 <= steps[0]["seconds"] < WAIT


# --- benchmark and verification -----------------------------------------------------------------------------------

SMALL = {"sha256_rounds": 2000, "ledger_records": 3}


def test_the_benchmark_is_deterministic_scratch_only_and_reports_median_iqr_and_host(tmp_path, monkeypatch):
    home, *_ = make_body(tmp_path)
    ledger = home / "ledger.jsonl"
    # A private temporary directory: any other benchmark on this host shares the default one (review finding F3).
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    held = ledger.read_bytes() if ledger.exists() else None
    one = compute.benchmark(3, workload=SMALL)
    two = compute.benchmark(3, workload=SMALL)
    assert (ledger.read_bytes() if ledger.exists() else None) == held          # never the body's ledger
    assert list(scratch.iterdir()) == []                                       # scratch removed
    for result in (one, two):
        assert result["runs"] == 3 and len(result["samples_seconds"]) == 3 and result["deterministic"] is True
        assert result["median_seconds"] > 0 and result["iqr_seconds"] >= 0
        assert set(result["component_medians"]) == {"sha256_chain", "ledger_append_verify", "process_spawn"}
        assert result["host"]["cores"] >= 1 and result["host"]["python"]
        assert set(result["host"]["conditions_at_end"]) == set(result["host"]["conditions"])
        assert result["network"] == "none"
        per_run = result["contention"]["per_run"]                              # measured during every replicate
        assert len(per_run) == 3 and all(set(c) == set(compute.CONTENTION_MEASURES) for c in per_run)
        assert all(0.0 <= c["cpu_wait_share"] <= 1.0 for c in per_run)
        assert result["contention"]["medians"]["cpu_wait_share"] is not None
    assert one["workload_digest"] == two["workload_digest"] and one["output_digest"] == two["output_digest"]
    assert compute.benchmark(1, workload={**SMALL, "seed": "other"})["workload_digest"] != one["workload_digest"]


QUIET = {"cpu_wait_share": 0.02, "psi_cpu_share": 0.10, "psi_io_share": 0.01, "psi_memory_share": 0.0}


def bench(samples, digest="w1", contention=QUIET, host=None):
    """A benchmark result as ``benchmark`` writes it; by default both runs met the same measured contention."""
    run = {"samples_seconds": samples, "workload_digest": digest, "host": host or {"machine": "x86_64", "cores": 4}}
    if contention is not None:
        run["contention"] = {"medians": dict(contention)}
    return run


BEFORE = [1.00, 1.02, 0.98, 1.01, 0.99, 1.03, 0.97]


def test_a_clearly_faster_after_is_verified():
    result = compute.verify_improvement(bench(BEFORE), bench([0.80, 0.82, 0.79, 0.81, 0.78, 0.83, 0.80]))
    assert result["verdict"] == "VERIFIED"
    assert result["p_value"] <= result["alpha"] == compute.ALPHA and result["method"].startswith("exact")
    assert result["relative_effect"] > result["noise_floor"] > 0


@pytest.mark.parametrize("after", [
    [0.99, 1.01, 1.00, 0.98, 1.02, 0.97, 1.03],          # the same distribution
    [1.20, 1.22, 1.19, 1.21, 1.18, 1.23, 1.20],          # slower: one-sided, never "improved"
    [0.96, 1.04, 0.95, 1.05, 0.97, 1.03, 0.99],          # overlapping
    [0.80, 1.30, 0.82, 1.25, 0.85, 1.20, 0.90],          # a 10% lower median, but no consistent shift (p 0.36)
])
def test_overlapping_or_slower_samples_are_not_improved(after):
    assert compute.verify_improvement(bench(BEFORE), bench(after))["verdict"] == "NOT_IMPROVED"


def test_a_shift_inside_the_before_noise_is_not_improved_even_when_significant():
    noisy = [1.00, 1.01, 1.02, 1.30, 1.31, 1.32, 1.00]    # a contended before run: IQR / median = 0.29
    shifted = [0.95, 0.96, 0.97, 0.95, 0.96, 0.97, 0.96]   # every value below every before value, but 6% faster
    result = compute.verify_improvement(bench(noisy), bench(shifted))
    assert result["p_value"] <= compute.ALPHA and result["relative_effect"] < result["noise_floor"]
    assert result["verdict"] == "NOT_IMPROVED"


def test_too_few_samples_or_different_workloads_are_inconclusive():
    few = compute.verify_improvement(bench(BEFORE[:4]), bench([0.5, 0.5, 0.5, 0.5]))
    assert few["verdict"] == "INCONCLUSIVE" and str(compute.MIN_REPLICATES) in few["reason"]
    other = compute.verify_improvement(bench(BEFORE), bench([0.5] * 7, digest="w2"))
    assert other["verdict"] == "INCONCLUSIVE" and "different workloads" in other["reason"]
    with pytest.raises(ValueError):
        compute.verify_improvement(bench(BEFORE), bench([0.5, float("nan"), 0.5, 0.5, 0.5]))


def test_large_samples_use_a_seeded_permutation_test_that_repeats_exactly():
    before = [1.0 + (i % 7) / 100 for i in range(30)]
    after = [0.9 + (i % 7) / 100 for i in range(30)]
    one = compute.verify_improvement(bench(before), bench(after))
    two = compute.verify_improvement(bench(before), bench(after))
    assert one["method"].startswith("seeded permutation") and one == two and one["verdict"] == "VERIFIED"


def test_tied_samples_take_midranks_so_the_exact_p_value_is_right():
    # 126 of the 252 arrangements put three or more of the five 1.0s on the after side
    p_value, method = compute._rank_sum_p([1.0, 1.0, 2.0, 2.0, 2.0], [1.0, 1.0, 1.0, 2.0, 2.0])
    assert method.startswith("exact") and p_value == 0.5


BUSY = {"cpu_wait_share": 0.45, "psi_cpu_share": 0.80, "psi_io_share": 0.20, "psi_memory_share": 0.0}
FASTER = [0.80, 0.82, 0.79, 0.81, 0.78, 0.83, 0.80]


def test_the_same_code_on_a_quieter_host_is_never_verified():
    """Review findings WU05-F2 and F1-verify: only ambient load changed between the runs, and verify said VERIFIED."""
    result = compute.verify_improvement(bench(BEFORE, contention=BUSY), bench(FASTER, contention=QUIET))
    assert result["verdict"] == "INCONCLUSIVE" and "quieter" in result["reason"]
    assert result["p_value"] <= compute.ALPHA and result["relative_effect"] > result["noise_floor"]  # it was faster
    assert result["contention"]["before"] == BUSY and result["contention"]["after"] == QUIET
    assert result["contention"]["shift"]["cpu_wait_share"] == -0.43
    assert "the code and the host together" in result["scope"]
    io_eased = {**QUIET, "psi_io_share": 0.01 + compute.CONTENTION_TOLERANCE + 0.01}      # one measure is enough
    assert compute.verify_improvement(bench(BEFORE, contention=io_eased), bench(FASTER))["verdict"] == "INCONCLUSIVE"
    within = {**QUIET, "cpu_wait_share": 0.02 + compute.CONTENTION_TOLERANCE - 0.01}       # inside the tolerance
    assert compute.verify_improvement(bench(BEFORE, contention=within), bench(FASTER))["verdict"] == "VERIFIED"


def test_no_change_on_a_busier_host_is_inconclusive_and_a_speed_up_despite_it_is_verified():
    masked = compute.verify_improvement(bench(BEFORE), bench(BEFORE, contention=BUSY))
    assert masked["verdict"] == "INCONCLUSIVE" and "busier" in masked["reason"]
    assert compute.verify_improvement(bench(BEFORE), bench(FASTER, contention=BUSY))["verdict"] == "VERIFIED"


def test_a_verdict_needs_contention_measured_during_both_runs():
    for before, after in ((bench(BEFORE, contention=None), bench(FASTER)), (bench(BEFORE), FASTER),
                          (bench(BEFORE, contention=dict.fromkeys(QUIET)), bench(FASTER))):
        result = compute.verify_improvement(before, after)
        assert result["verdict"] == "INCONCLUSIVE" and "no contention was measured" in result["reason"]


def test_verify_reports_whether_both_runs_used_the_same_host():
    one = {"machine": "x86_64", "cores": 4, "conditions": {"load1": 1.0}}
    later = {**one, "conditions": {"load1": 3.0}, "conditions_at_end": {"load1": 2.0}}
    assert compute.verify_improvement(bench(BEFORE, host=one), bench(BEFORE, host=later))["same_host"] is True
    assert compute.verify_improvement(bench(BEFORE, host=one), bench(BEFORE, host={**one, "cores": 8}))[
        "same_host"] is False


def test_a_scratch_ledger_that_fails_verification_stops_the_benchmark_and_varying_output_is_flagged(tmp_path,
                                                                                                     monkeypatch):
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    real = EvidenceLedger.verify_chain

    def tampered(self, *args, **kwargs):        # only the benchmark's own final check sees a broken chain
        caller = sys._getframe(1).f_globals.get("__name__")
        return (False, "tampered") if caller == "greg.compute" else real(self, *args, **kwargs)
    with monkeypatch.context() as patched:
        patched.setattr(EvidenceLedger, "verify_chain", tampered)
        with pytest.raises(RuntimeError, match="failed verification"):
            compute.benchmark(1, workload=SMALL)
    outputs = iter(["a", "b"])
    monkeypatch.setattr(compute, "_sha256_chain", lambda seed, rounds: next(outputs))
    assert compute.benchmark(2, workload=SMALL)["deterministic"] is False


# --- the CLI: read-only status, files only ---------------------------------------------------------------------

def test_cli_compute_reads_the_body_and_writes_only_the_files_it_names(tmp_path, capsys):
    from greg import cli
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        window(body.journal, "2026-10-30T00:00", **CPU)
        compute.recommend(body.journal)
    ledger = home / "ledger.jsonl"
    held = ledger.read_bytes()
    assert cli.main(["--home", str(home), "compute", "status"]) == 0
    shown = json.loads(capsys.readouterr().out)
    assert shown["bottleneck"]["resource"] == "cpu" and shown["asks"]["cpu"]["pending"]
    assert "psi_memory_some_avg60" in shown["sample"]
    assert cli.main(["--home", str(home), "compute", "benchmark", "--runs", "1", "--out", str(home / "b.json")]) == 2
    assert "outside the body" in capsys.readouterr().err and not (home / "b.json").exists()
    out = tmp_path / "bench.json"
    assert cli.main(["--home", str(home), "compute", "benchmark", "--runs", "2", "--out", str(out)]) == 0
    assert json.loads(out.read_text())["runs"] == 2
    capsys.readouterr()
    (tmp_path / "a.json").write_text(json.dumps(bench(BEFORE)))
    (tmp_path / "b.json").write_text(json.dumps(bench([0.8] * 7)))
    assert cli.main(["--home", str(home), "compute", "verify", "--before", str(tmp_path / "a.json"),
                     "--after", str(tmp_path / "b.json")]) == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == "VERIFIED"
    assert ledger.read_bytes() == held                                     # the CLI never wrote the body's ledger


def test_cli_benchmark_guard_expands_the_home_and_never_overwrites_a_file_it_did_not_write(tmp_path, monkeypatch,
                                                                                          capsys):
    """Review finding WU05-F3: a home given as '~/body' slipped past the guard and --out replaced the ledger."""
    from greg import cli
    home, *_ = make_body(tmp_path)                                         # tmp_path/body
    monkeypatch.setenv("HOME", str(tmp_path))
    ledger = home / "ledger.jsonl"
    held = ledger.read_bytes()
    assert cli.main(["--home", "~/body", "compute", "status"]) == 0        # '~/body' is the real body
    capsys.readouterr()
    for out in ("~/body/ledger.jsonl", "~/body/results.json", str(home / "inbox" / ".." / "x.json")):
        assert cli.main(["--home", "~/body", "compute", "benchmark", "--runs", "1", "--out", out]) == 2
        assert "outside the body" in capsys.readouterr().err
    assert ledger.read_bytes() == held and not (home / "results.json").exists()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    foreign = elsewhere / "ledger.jsonl"
    foreign.write_text("another body's ledger\n")
    assert cli.main(["--home", str(home), "compute", "benchmark", "--runs", "1", "--out", str(foreign)]) == 2
    assert "not a benchmark result" in capsys.readouterr().err and foreign.read_text() == "another body's ledger\n"
    assert cli.main(["--home", str(home), "compute", "benchmark", "--runs", "0",
                     "--out", str(elsewhere / "b.json")]) == 2
    assert "--runs must be at least 1" in capsys.readouterr().err
    mine = elsewhere / "bench.json"
    for _ in range(2):                                                     # its own earlier result is replaced
        assert cli.main(["--home", str(home), "compute", "benchmark", "--runs", "1", "--out", str(mine)]) == 0
    assert json.loads(mine.read_text())["kind"] == "compute.benchmark"


def test_compute_stays_stdlib_and_never_provisions():
    tree = ast.parse((ROOT / "greg/compute.py").read_text())
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not imported & {"scipy", "numpy", "socket", "urllib", "http", "requests", "ssl"}
    source = (ROOT / "greg/compute.py").read_text()
    for forbidden in ("ConsequenceGate", "GrantIssuer", "urlopen", "requests."):
        assert forbidden not in source
