"""LOCAL-REAL: an unchanged Body.run samples this host's /proc, asks about a sustained bottleneck, takes a signed
answer (a generated test key, not the founder's), and asks again once a full window measured after the answer still
shows it. Usage: python -B live_reask.py SCRATCH_DIR > live-body-reask.json"""
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from greg import asks, compute  # noqa: E402
from greg.body import Body  # noqa: E402
from tests.greg_fixtures import drop, make_body, signed  # noqa: E402

tmp = Path(tempfile.mkdtemp(prefix="wu05-live-", dir=sys.argv[1]))
home, key, body_id, _ = make_body(tmp)


def loop(ticks):
    Body(home).run(tick_seconds=0.05, max_ticks=ticks, telemetry_every=2)


def compute_asks():
    with Body(home) as body:
        return [e.payload for e in body.journal.replay("decision.requested") if e.payload["kind"] == "COMPUTE"]


def samples():
    with Body(home) as body:
        return [e.payload for e in body.journal.replay("compute.telemetry")]


out = {"host_load1_start": os.getloadavg()[0]}
loop(2 * compute.SUSTAINED_SAMPLES)
first = compute_asks()
out["after_first_window"] = {"samples": len(samples()), "asks": [
    (a["request_id"], a["evidence"]["bottleneck"]["resource"], a["evidence"]["epoch"]) for a in first]}
out["first_window_samples"] = [{k: s[k] for k in ("at", "load_ratio", "psi_cpu_some_avg60", "psi_memory_some_avg60",
                                                  "psi_io_some_avg60", "mem_available_ratio", "disk_free_ratio")}
                               for s in samples()]
if first:
    loop(2 * compute.SUSTAINED_SAMPLES)                     # still pending: no second ask
    out["while_pending"] = len(compute_asks())
    drop(home, signed(key, body_id, "DECISION", {"request_id": first[0]["request_id"], "answer": "reject"}))
    loop(2 * (compute.SUSTAINED_SAMPLES - 1))               # the answer is applied; 4 samples after it
    out["four_samples_after_answer"] = len(compute_asks())
    loop(2)                                                  # the fifth
    later = compute_asks()
    out["after_fifth_sample"] = [(a["request_id"], a["evidence"]["bottleneck"]["resource"], a["evidence"]["epoch"],
                                  a["evidence"]["earlier_asks"]) for a in later]
    with Body(home) as body:
        out["ask_state"] = compute.ask_state(body.journal, later[-1]["evidence"]["bottleneck"]["resource"])
        out["first_option"] = later[-1]["options"][0]["option"]
        out["screen"] = asks.screen(later[-1])
out["host_load1_end"] = os.getloadavg()[0]
print(json.dumps(out, indent=1))
