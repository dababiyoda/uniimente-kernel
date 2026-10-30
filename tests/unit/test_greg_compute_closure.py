"""Compute closure (directive sections 48, 58, 60, 71): memory and IO pressure, a working re-ask, the heaviest
measured workload, a deterministic benchmark and a before/after verdict.

Real bodies and real ledgers throughout. Timing fixtures emit events at fixed ledger times so the
quantities are exact; real benchmark timings are reported by the evidence README, never asserted here.
"""
import ast
import json
from pathlib import Path
import tempfile

import pytest

from events.spine import Event, EventSpine
from greg import asks, compute
from greg.body import Body
from greg.journal import PRINCIPAL, SOURCE, Journal, fact_id
from provenance.ledger import EvidenceLedger
from tests.greg_fixtures import Clock, drop, make_body, signed

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
        for window_ in ("avg10", "avg60"):
            value = data[f"psi_{resource}_some_{window_}"]
            assert isinstance(value, float) and 0.0 <= value <= 100.0
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


# --- benchmark and verification -----------------------------------------------------------------------------------

SMALL = {"sha256_rounds": 2000, "ledger_records": 3}


def test_the_benchmark_is_deterministic_scratch_only_and_reports_median_iqr_and_host(tmp_path):
    home, *_ = make_body(tmp_path)
    ledger = home / "ledger.jsonl"
    before = sorted(Path(tempfile.gettempdir()).glob("greg-benchmark-*"))
    held = ledger.read_bytes() if ledger.exists() else None
    one = compute.benchmark(3, workload=SMALL)
    two = compute.benchmark(3, workload=SMALL)
    assert (ledger.read_bytes() if ledger.exists() else None) == held          # never the body's ledger
    assert sorted(Path(tempfile.gettempdir()).glob("greg-benchmark-*")) == before   # scratch removed
    for result in (one, two):
        assert result["runs"] == 3 and len(result["samples_seconds"]) == 3 and result["deterministic"] is True
        assert result["median_seconds"] > 0 and result["iqr_seconds"] >= 0
        assert set(result["component_medians"]) == {"sha256_chain", "ledger_append_verify", "process_spawn"}
        assert result["host"]["cores"] >= 1 and result["host"]["python"]
        assert result["network"] == "none"
    assert one["workload_digest"] == two["workload_digest"] and one["output_digest"] == two["output_digest"]
    assert compute.benchmark(1, workload={**SMALL, "seed": "other"})["workload_digest"] != one["workload_digest"]


def bench(samples, digest="w1"):
    return {"samples_seconds": samples, "workload_digest": digest, "host": {"machine": "x86_64", "cores": 4}}


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


def test_compute_stays_stdlib_and_never_provisions():
    tree = ast.parse((ROOT / "greg/compute.py").read_text())
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    imported |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not imported & {"scipy", "numpy", "socket", "urllib", "http", "requests", "ssl"}
    source = (ROOT / "greg/compute.py").read_text()
    for forbidden in ("ConsequenceGate", "GrantIssuer", "urlopen", "requests."):
        assert forbidden not in source
