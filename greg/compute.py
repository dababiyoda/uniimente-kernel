"""Body and compute manager: measure the body, recommend growth, never self-provision.

The first computer is Body 1, not the institution's identity. The institution is
the ledger, the founder key and the missions; a replacement machine restores
from them. Additional nodes join only by founder-signed NODE_ENROLL, each with
its own identity and a bounded light cone, never universal authority.

Growth is an instrument for founder goals. Telemetry may justify a
recommendation with alternatives and uncertainty; it may not buy, rent or
install anything, and it never argues from self-preservation.

What is measured, and how (directive sections 48, 58, 60, 71):

* ``sample`` reads load, disk and, on Linux, pressure stall information (PSI, ``/proc/pressure``) and
  MemAvailable. On a 4-8 GB Chromebook memory, not CPU, is the usual limit. A field that cannot be read is
  None, never 0, and a sample missing a field never counts as pressure.
* ``bottleneck`` names one sustained resource by a declared precedence; ``recommend`` turns it into ONE
  founder ask per resource at a time, and asks again only when a full window measured after the founder's
  answer still shows it.
* ``quantify`` reads mission step timing the ledger already records (the write-ahead intent to the recorded
  outcome, for steps that ran straight through: never the founder's approval wait or the body's downtime) and names
  the heaviest measured workload. Its delay figure is an estimate and says so.
* ``benchmark`` runs a fixed stdlib workload in a scratch directory and measures the contention each replicate met;
  ``verify_improvement`` decides with a one-sided permutation test whether a change measurably helped, and credits
  it only when that contention did not ease in its favour. Nothing here uses the network or prices.
"""
from __future__ import annotations

import bisect
from datetime import datetime
import hashlib
import itertools
import math
import os
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

from greg import asks
from greg.journal import Journal, fact_id, iso, utcnow
from greg.lightcone import LightCone
from provenance.ledger import sha256_json

LOAD_RATIO_THRESHOLD = 0.9
DISK_FREE_THRESHOLD = 0.10
SUSTAINED_SAMPLES = 5
# Declared thresholds, not learned ones. PSI "some avg60" is the share of the last minute (percent) in which at
# least one task stalled waiting on the resource; a body samples about every ten minutes, so avg60 is used.
MEMORY_PSI_THRESHOLD = 10.0
MEM_AVAILABLE_FLOOR = 0.10          # MemAvailable / MemTotal below this is memory pressure without PSI
IO_PSI_THRESHOLD = 20.0
# When several rules hold over the same samples, the first is the bottleneck and the rest are reported.
# Memory first: reclaim and swap show up as IO stalls and as load. IO before CPU: Linux counts tasks waiting
# on IO in the load average. Disk space last: a capacity, not a rate, and the order before this was cpu, disk.
PRECEDENCE = ("memory", "io", "cpu", "disk")
PROC = Path("/proc")
PSI_FIELDS = tuple(f"psi_{r}_some_{w}" for r in ("cpu", "memory", "io") for w in ("avg10", "avg60"))
MEMINFO_FIELDS = ("mem_total_bytes", "mem_available_bytes", "mem_available_ratio")
WEEK_SECONDS = 7 * 86400
DELAY_METHOD = ("estimate (method: for each capability, the median step time in the bottleneck window minus "
                "its median before the window, summed over the window's steps and scaled from the window's span "
                "to 7 days; all excess is attributed to the bottleneck, which the journal cannot establish)")


def memory_bytes() -> int | None:
    try:
        if sys.platform == "darwin":
            out = subprocess.run(["/usr/sbin/sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5)
            return int(out.stdout.strip())
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (OSError, ValueError):
        return None


def _finite(value) -> float | None:
    """A non-negative finite number from /proc text, else None (never 0 for "could not read")."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number >= 0 else None


def _psi_some(resource: str) -> dict:
    """The raw fields of the 'some' line of /proc/pressure/<resource>; empty where the kernel offers none."""
    try:
        text = (PROC / "pressure" / resource).read_text()
    except (OSError, UnicodeDecodeError):
        return {}
    for line in text.splitlines():
        head, _, rest = line.partition(" ")
        if head == "some":
            return dict(token.partition("=")[::2] for token in rest.split())
    return {}


def _pressure(resource: str) -> tuple[float | None, float | None]:
    """PSI 'some' avg10 and avg60 (percent) for cpu, memory or io; None where the kernel offers none."""
    fields = _psi_some(resource)
    return _finite(fields.get("avg10")), _finite(fields.get("avg60"))


def _stall_totals() -> dict:
    """PSI 'some' stall time (microseconds since boot) per resource, host-wide; None where unreadable."""
    return {resource: _finite(_psi_some(resource).get("total")) for resource in ("cpu", "memory", "io")}


def _meminfo() -> dict:
    found = {}
    try:
        lines = (PROC / "meminfo").read_text().splitlines()
    except (OSError, UnicodeDecodeError):
        lines = []
    for line in lines:
        name, _, rest = line.partition(":")
        parts = rest.split()
        if name in ("MemTotal", "MemAvailable") and len(parts) == 2 and parts[1] == "kB" and parts[0].isdigit():
            found[name] = int(parts[0]) * 1024
    total, available = found.get("MemTotal"), found.get("MemAvailable")
    return {"mem_total_bytes": total, "mem_available_bytes": available,
            "mem_available_ratio": round(available / total, 4) if total and available is not None else None}


def pressure() -> dict:
    """PSI for cpu, memory and io, and MemAvailable/MemTotal: the fields ``sample`` adds."""
    out = {}
    for resource in ("cpu", "memory", "io"):
        out[f"psi_{resource}_some_avg10"], out[f"psi_{resource}_some_avg60"] = _pressure(resource)
    return {**out, **_meminfo()}


def sample(home: Path) -> dict:
    cores = os.cpu_count() or 1
    load1 = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
    disk = shutil.disk_usage(home)
    return {"at": iso(utcnow()), "machine": platform.machine(), "system": platform.system(),
            "cores": cores, "load1": round(load1, 3), "load_ratio": round(load1 / cores, 3),
            "memory_bytes": memory_bytes(), "disk_total": disk.total, "disk_free": disk.free,
            "disk_free_ratio": round(disk.free / disk.total, 4) if disk.total else None, **pressure()}


def record_telemetry(journal: Journal, home: Path, *, telemetry: dict | None = None) -> dict:
    data = telemetry or sample(home)
    journal.record("compute.telemetry", data, key=data["at"])
    return data


def _num(s: dict, key: str) -> float | None:
    value = s.get(key)
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _at_least(s: dict, key: str, threshold: float) -> bool:
    value = _num(s, key)
    return value is not None and value >= threshold


def _below(s: dict, key: str, threshold: float) -> bool:
    value = _num(s, key)
    return value is not None and value < threshold


RULES = {
    "memory": (lambda s: _at_least(s, "psi_memory_some_avg60", MEMORY_PSI_THRESHOLD)
               or _below(s, "mem_available_ratio", MEM_AVAILABLE_FLOOR),
               f"memory pressure (PSI some avg60) >= {MEMORY_PSI_THRESHOLD}% or MemAvailable/MemTotal < "
               f"{MEM_AVAILABLE_FLOOR:.0%} for {SUSTAINED_SAMPLES} samples"),
    "io": (lambda s: _at_least(s, "psi_io_some_avg60", IO_PSI_THRESHOLD),
           f"IO pressure (PSI some avg60) >= {IO_PSI_THRESHOLD}% for {SUSTAINED_SAMPLES} samples"),
    "cpu": (lambda s: _at_least(s, "load_ratio", LOAD_RATIO_THRESHOLD),
            f"load/cores >= {LOAD_RATIO_THRESHOLD} for {SUSTAINED_SAMPLES} samples"),
    "disk": (lambda s: _below(s, "disk_free_ratio", DISK_FREE_THRESHOLD),
             f"free disk < {DISK_FREE_THRESHOLD:.0%} for {SUSTAINED_SAMPLES} samples"),
}


def assess(samples: list) -> dict | None:
    """The sustained bottleneck over the last SUSTAINED_SAMPLES samples, first by PRECEDENCE, or None."""
    window = samples[-SUSTAINED_SAMPLES:]
    if len(window) < SUSTAINED_SAMPLES:
        return None
    held = [r for r in PRECEDENCE if all(RULES[r][0](s) for s in window)]
    if not held:
        return None
    return {"resource": held[0], "evidence": [s["at"] for s in window], "measure": RULES[held[0]][1],
            "also_sustained": held[1:]}


def bottleneck(journal: Journal) -> dict | None:
    return assess([e.payload for e in journal.replay("compute.telemetry")])


def _bottleneck_resource(ask: dict) -> str | None:
    found = (ask.get("evidence") or {}).get("bottleneck") if isinstance(ask.get("evidence"), dict) else None
    return found.get("resource") if isinstance(found, dict) else None


def ask_state(journal: Journal, resource: str) -> dict:
    """Where the COMPUTE asks about one bottleneck resource stand, read the way every founder surface reads them.

    An ask is closed by a founder-signed answer the mission book counts (an answer row nothing signed stands behind
    leaves it open) or by a withdrawal. ``epoch`` is the number closed; ``closed_at`` the ledger position of the
    latest closing row. Asks are matched by the resource in their evidence, so asks recorded before epochs existed
    count too."""
    requested = [e for e in journal.replay("decision.requested")
                 if e.payload.get("kind") == "COMPUTE" and _bottleneck_resource(e.payload) == resource
                 and e.event_id == fact_id("decision.requested", e.payload.get("request_id"))]
    if not requested:
        return {"resource": resource, "epoch": 0, "pending": [], "closed": [], "closed_at": None}
    from greg.missions import MissionBook
    decisions = journal.replay("decision.")
    still_open = {r["request_id"] for r in asks.open_requests(decisions, counted=MissionBook(journal).answers)}
    ids = [e.payload["request_id"] for e in requested]
    closed = [rid for rid in ids if rid not in still_open]
    positions = journal.positions("")
    closing = [positions[e.event_id] for e in decisions
               if e.type in ("greg.decision.answered", "greg.decision.withdrawn")
               and e.payload.get("request_id") in closed and e.event_id in positions]
    return {"resource": resource, "epoch": len(closed), "pending": [rid for rid in ids if rid in still_open],
            "closed": closed, "closed_at": max(closing) if closing else None}


def _when(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


# Records only the body's loop writes, never a dispatch in progress (the body is single-threaded, and a dispatch
# writes its intent, its capability's own records and its outcome). One of these between a step's intent and its
# outcome means the step did not run straight through: it waited for the founder (an APPROVAL asked, blocked and
# answered), the body stopped and booted again, or the body moved on to other work before the same intent ran.
LOOP_RECORDS = ("mission.", "decision.", "body.", "command.", "compute.telemetry")


def step_times(journal: Journal) -> list[dict]:
    """Every timed mission step: the ledger record time of its latest write-ahead intent (``mission.dispatching``)
    to that of its first recorded outcome (``mission.action``). Wall clock, so it includes the Gate and the
    capability.

    Not timing: an outcome with no intent before it (refused before dispatch) or with no capability (its input
    failed, not a capability), an outcome recovered after a restart, a step with a loop record between its intent
    and its outcome (LOOP_RECORDS: the founder's approval wait or the body's downtime is not the capability's time;
    a later record of the same dispatch, a reconciliation, always has the first outcome between), and a negative
    span (the clock stepped)."""
    positions = journal.positions("")
    loop = sorted(positions[event_id] for kind in LOOP_RECORDS for event_id in journal.positions(kind)
                  if event_id in positions)
    intents = {}
    for e in journal.replay("mission.dispatching"):
        p = e.payload
        if positions.get(e.event_id) is not None:
            intents.setdefault((p.get("mission_id"), p.get("action_id"), p.get("attempt")), []).append(
                (positions[e.event_id], e.occurred_at))
    steps = []
    for e in journal.replay("mission.action"):
        p = e.payload
        end = positions.get(e.event_id)
        begun = [i for i in intents.get((p.get("mission_id"), p.get("action_id"), p.get("attempt")), ())
                 if end is not None and i[0] < end]
        if not begun or not isinstance(p.get("capability"), str) or (p.get("routing") or {}).get("recovered"):
            continue
        start, started_at = max(begun)
        if bisect.bisect_right(loop, start) < bisect.bisect_left(loop, end):
            continue
        seconds = (_when(e.occurred_at) - _when(started_at)).total_seconds()
        if seconds >= 0:
            steps.append({"mission_id": p.get("mission_id"), "capability": p["capability"],
                          "seconds": seconds, "position": end})
    return steps


def quantify(journal: Journal, window: list) -> dict:
    """Measured step time inside the bottleneck window (``window``: its telemetry events), the heaviest workload by
    share of that time, and an estimate, labelled as one, of the mission time the window's slowdown cost."""
    positions = journal.positions("")
    first, last = positions.get(window[0].event_id), positions.get(window[-1].event_id)
    steps = step_times(journal)
    inside = [s for s in steps if s["position"] is not None and first is not None and last is not None
              and first <= s["position"] <= last]
    before = [s for s in steps if s["position"] is not None and first is not None and s["position"] < first]
    span = (_when(window[-1].occurred_at) - _when(window[0].occurred_at)).total_seconds()
    work = {"recorded": bool(steps), "steps_in_window": len(inside), "heaviest": None, "by_capability": []}
    delay = {"basis": DELAY_METHOD, "excess_step_seconds": None, "window_seconds": round(span, 3),
             "mission_hours_delayed_per_week": None, "latency_inflation": {}, "unbaselined_capabilities": []}
    if not inside:
        work["note"] = ("no GREG mission step ran in the bottleneck window, so the load may come from outside "
                        "GREG's missions" if steps else
                        "the journal records no mission step timing yet, so no workload is named")
        return {"workload": work, "delay": delay}
    by_capability = {}
    for s in inside:
        by_capability.setdefault(s["capability"], []).append(s["seconds"])
    total = sum(sum(v) for v in by_capability.values())
    rows = sorted(({"capability": c, "steps": len(v), "seconds": round(sum(v), 3),
                    "share": round(sum(v) / total, 4) if total > 0 else None} for c, v in by_capability.items()),
                  key=lambda r: (-r["seconds"], str(r["capability"])))
    work["by_capability"] = rows
    if total > 0:
        work["heaviest"] = rows[0]
    else:                               # every timed step took 0 s on the record clock: no share to rank by
        work["note"] = "the window's timed mission steps took no measurable time, so no workload is named"
    baseline = {}
    for s in before:
        baseline.setdefault(s["capability"], []).append(s["seconds"])
    usual = {c: statistics.median(v) for c, v in baseline.items()}
    excess = sum(max(0.0, s["seconds"] - usual[s["capability"]]) for s in inside if s["capability"] in usual)
    delay.update(
        latency_inflation={c: round(statistics.median(v) / usual[c], 3) for c, v in sorted(by_capability.items())
                           if usual.get(c, 0) > 0},
        unbaselined_capabilities=sorted(c for c in by_capability if c not in usual),
        excess_step_seconds=round(excess, 3) if any(c in usual for c in by_capability) else None)
    if delay["excess_step_seconds"] is not None and span > 0:
        delay["mission_hours_delayed_per_week"] = round(excess * WEEK_SECONDS / span / 3600, 4)
    return {"workload": work, "delay": delay}


def _optimization_option(work: dict) -> str:
    heaviest = work.get("heaviest")
    if heaviest is not None:
        return (f"software/workload optimization (no spend): start with {heaviest['capability']}, "
                f"{heaviest['share']:.0%} of measured mission step time in the bottleneck window")
    return f"software/workload optimization (no spend); {work.get('note') or 'no workload is named'}"


def recommend(journal: Journal) -> dict | None:
    """Turn a sustained bottleneck into ONE founder decision request with alternatives.

    One ask per resource at a time: none while one is pending. After the founder answers (or an ask is withdrawn),
    GREG asks again only when SUSTAINED_SAMPLES samples recorded after that still show the bottleneck; the new ask
    carries the next epoch in its identity, so it is a new question, not a repeat of the answered one."""
    found = bottleneck(journal)
    if found is None:
        return None
    standing = ask_state(journal, found["resource"])
    if standing["pending"]:
        return None
    telemetry = journal.replay("compute.telemetry")
    window = telemetry[-SUSTAINED_SAMPLES:]
    if standing["closed_at"] is not None and journal.positions("")[window[0].event_id] <= standing["closed_at"]:
        return None
    epoch = standing["epoch"]
    # Epoch 0 keeps the identity asks had before epochs, so a body that already asked is not asked twice.
    request_id = "req-compute-" + sha256_json({"resource": found["resource"]} if epoch == 0 else
                                              {"resource": found["resource"], "epoch": epoch})[7:23]
    if any(e.payload["request_id"] == request_id for e in journal.replay("decision.requested")):
        return None
    samples = [e.payload for e in window]
    measured = quantify(journal, window)
    message = asks.resource_request(
        request_id=request_id, kind="COMPUTE", resource="compute", scope_digest=sha256_json(found),
        why_now=found["measure"] + (f"; asked again: {epoch} earlier ask(s) were answered or withdrawn, and the "
                                    f"bottleneck held for {SUSTAINED_SAMPLES} samples measured after the last" if epoch
                                    else ""),
        recommendation="optimize the heaviest measured workload first (named in the first option); if still "
                       "constrained, price cloud burst versus an additional enrolled node and decide on measured ROI",
        expected_effect="missions stop queueing behind a saturated " + found["resource"] + "; the improvement is "
                        "benchmarked on the same workload before any growth is kept (greg compute benchmark, then "
                        "greg compute verify)",
        options=[
            {"option": _optimization_option(measured["workload"]), "cost": "none in money; engineering time",
             "expected_effect": "lower load from the same missions; measured by the next telemetry window"},
            {"option": "temporary cloud compute (metered)", "cost": "metered provider price; data leaves this body",
             "expected_effect": "burst capacity for the heaviest missions while it runs"},
            {"option": "additional local node (capital purchase; human installation)",
             "cost": "hardware price and your installation time",
             "expected_effect": "durable capacity as a separately enrolled body with its own bounded identity"},
            {"option": "do nothing: missions wait", "cost": "none",
             "expected_effect": "missions continue at current capacity and finish later"}],
        evidence={"bottleneck": found, "epoch": epoch, "earlier_asks": standing["closed"],
                  "samples": [{k: s.get(k) for k in ("at", "cores", "load_ratio", "disk_free_ratio",
                                                     "mem_available_ratio", "psi_memory_some_avg60",
                                                     "psi_io_some_avg60", "psi_cpu_some_avg60")} for s in samples],
                  **measured},
        uncertainty="prices and workload growth are not yet measured; unpriced: no ROI claim; the delay figure in "
                    "the evidence is an estimate, not a measurement; the pressure thresholds are declared, not learned",
        authority_requested={"spend": "none requested; any purchase is a separate founder decision"},
        consequence_of_no_response="missions continue at current capacity; nothing is bought",
        created_at=iso(utcnow()),
        argued_from="measured telemetry and mission step timing; never the body's own continuation")
    return asks.record(journal, message)


def status(journal: Journal) -> dict:
    """Read-only: the retained telemetry's bottleneck, each resource's COMPUTE asks, and step timing."""
    telemetry = journal.replay("compute.telemetry")
    resources = sorted({r for r in (_bottleneck_resource(e.payload) for e in journal.replay("decision.requested")
                                    if e.payload.get("kind") == "COMPUTE") if r})
    return {"samples": len(telemetry), "bottleneck": assess([e.payload for e in telemetry]),
            "asks": {r: ask_state(journal, r) for r in resources},
            **(quantify(journal, telemetry[-SUSTAINED_SAMPLES:]) if telemetry else {})}


# --- benchmark and before/after verification --------------------------------------------------------------------

BENCHMARK_RUNS = 7
BENCHMARK_WORKLOAD = {"version": 1, "seed": "greg-compute-benchmark/1", "sha256_rounds": 200_000,
                      "ledger_records": 50, "spawn": "python -I -c pass"}
ALPHA = 0.05                 # one-sided: the after run is faster
MIN_REPLICATES = 5           # per side; 5 against 5 gives an exact p as small as 1/252
EXACT_LIMIT = 50_000         # arrangements enumerated exactly; beyond this a seeded permutation sample
PERMUTATIONS = 20_000
PERMUTATION_SEED = 20261030
# What competed with each replicate, as a share of its time. The chain's time off the CPU is always measured;
# the PSI shares are host-wide stall time and None on a kernel without PSI.
CONTENTION_MEASURES = ("cpu_wait_share", "psi_cpu_share", "psi_io_share", "psi_memory_share")
# A difference in a measure's median between two runs above this (a share of each replicate's time) is a
# different host, not the same host at two times. Declared, not learned.
CONTENTION_TOLERANCE = 0.05
VERDICT_SCOPE = ("the fixed workload's speed on this host at two times: the code and the host together. A change "
                 "is credited only when the contention measured during both runs did not move in its favour, so a "
                 "change that works by lowering the host's load (an optimized workload) shows in the next telemetry "
                 "window, not here")


def _conditions() -> dict:
    load1 = os.getloadavg()[0] if hasattr(os, "getloadavg") else None
    return {"load1": round(load1, 3) if load1 is not None else None, **pressure()}


def host_facts() -> dict:
    """What a benchmark ran on, and the load and pressure when it started. These are lagging averages read once,
    so they cannot tell a contended run from a quiet one; the per-replicate contention is what verify compares."""
    return {"machine": platform.machine(), "system": platform.system(), "release": platform.release(),
            "python": platform.python_version(), "implementation": platform.python_implementation(),
            "cores": os.cpu_count() or 1, "memory_bytes": memory_bytes(), "conditions": _conditions()}


def _contention(stalls_before: dict, stalls_after: dict, chain_cpu: float, chain_wall: float, wall: float) -> dict:
    """What competed with one replicate: the share of the sha256 chain's wall time this process spent off the CPU,
    and, per resource, the PSI 'some' stall time the host accumulated over the replicate as a share of it."""
    out = {"cpu_wait_share": round(min(1.0, max(0.0, 1 - chain_cpu / chain_wall)), 4) if chain_wall > 0 else None}
    for resource in ("cpu", "io", "memory"):
        a, b = stalls_before.get(resource), stalls_after.get(resource)
        out[f"psi_{resource}_share"] = (round(min(1.0, (b - a) / 1e6 / wall), 4)
                                        if a is not None and b is not None and b >= a and wall > 0 else None)
    return out


def _sha256_chain(seed: str, rounds: int) -> str:
    digest = seed.encode()
    for _ in range(rounds):
        digest = hashlib.sha256(digest).digest()
    return digest.hex()


def _scratch_ledger(seed: str, records: int) -> None:
    """Append ``records`` facts to a fresh ledger in a temporary directory and verify its chain. Never the body's:
    the directory is created here and removed before returning."""
    from events.spine import EventSpine
    from provenance.ledger import EvidenceLedger
    with tempfile.TemporaryDirectory(prefix="greg-benchmark-") as scratch:
        ledger = EvidenceLedger("greg-benchmark-scratch", str(Path(scratch) / "ledger.jsonl"))
        try:
            journal = Journal(EventSpine(ledger), actor="spiffe://uniimente.internal/greg/benchmark")
            for i in range(records):
                journal.record("benchmark.record", {"seed": seed, "i": i}, key=[seed, i])
            ok, detail = ledger.verify_chain()
        finally:
            ledger.close()
    if not ok:
        raise RuntimeError(f"scratch ledger failed verification: {detail}")


def _quartiles(values: list) -> tuple[float, float, float]:
    if len(values) < 2:
        return values[0], values[0], values[0]
    q1, q2, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return q1, q2, q3


def benchmark(runs: int = BENCHMARK_RUNS, *, workload: dict | None = None) -> dict:
    """Run the fixed workload ``runs`` times: a seeded sha256 chain, a scratch ledger append-and-verify, and one
    interpreter spawn. Returns per-run seconds, median, IQR and host facts. Writes nothing outside a temporary
    directory it removes; no network."""
    if runs < 1:
        raise ValueError("a benchmark needs at least one run")
    spec = {**BENCHMARK_WORKLOAD, **(workload or {})}
    host, started = host_facts(), iso(utcnow())
    parts = {"sha256_chain": [], "ledger_append_verify": [], "process_spawn": []}
    totals, outputs, contention = [], set(), []
    for _ in range(runs):
        stalls, c0, t0 = _stall_totals(), time.process_time(), time.perf_counter()
        outputs.add(_sha256_chain(spec["seed"], int(spec["sha256_rounds"])))
        c1, t1 = time.process_time(), time.perf_counter()
        _scratch_ledger(spec["seed"], int(spec["ledger_records"]))
        t2 = time.perf_counter()
        subprocess.run([sys.executable, "-I", "-c", "pass"], check=True, capture_output=True, timeout=60)
        t3 = time.perf_counter()
        contention.append(_contention(stalls, _stall_totals(), c1 - c0, t1 - t0, t3 - t0))
        for name, seconds in zip(parts, (t1 - t0, t2 - t1, t3 - t2)):
            parts[name].append(round(seconds, 6))
        totals.append(round(t3 - t0, 6))
    host["conditions_at_end"] = _conditions()
    q1, median, q3 = _quartiles(totals)
    medians = {}
    for measure in CONTENTION_MEASURES:
        values = [c[measure] for c in contention if c[measure] is not None]
        medians[measure] = round(statistics.median(values), 4) if len(values) == len(contention) else None
    return {"kind": "compute.benchmark", "workload": spec, "workload_digest": sha256_json(spec), "runs": runs,
            "samples_seconds": totals, "components_seconds": parts,
            "component_medians": {k: round(statistics.median(v), 6) for k, v in parts.items()},
            "median_seconds": round(median, 6), "iqr_seconds": round(q3 - q1, 6),
            "relative_iqr": round((q3 - q1) / median, 6) if median > 0 else None,
            "contention": {"per_run": contention, "medians": medians},
            "deterministic": len(outputs) == 1, "output_digest": sorted(outputs)[0], "host": host,
            "started_at": started, "finished_at": iso(utcnow()), "network": "none",
            "reality_status": "MEASURED_ON_THIS_HOST"}


def _seconds(run) -> list[float]:
    values = run.get("samples_seconds") if isinstance(run, dict) else run
    if not isinstance(values, (list, tuple)) or not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v > 0 for v in values):
        raise ValueError("benchmark samples must be a list of positive, finite seconds")
    return [float(v) for v in values]


def _rank_sum_p(before: list, after: list) -> tuple[float, str]:
    """One-sided permutation p-value that ``after`` is faster: the share of arrangements of the pooled ranks whose
    'after' rank sum is at most the observed one. Doubled midranks keep ties exact."""
    pooled = before + after
    order = sorted(range(len(pooled)), key=pooled.__getitem__)
    ranks = [0] * len(pooled)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and pooled[order[j + 1]] == pooled[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = i + j + 2
        i = j + 1
    m, observed = len(after), sum(ranks[len(before):])
    total = math.comb(len(pooled), m)
    if total <= EXACT_LIMIT:
        hits = sum(1 for chosen in itertools.combinations(ranks, m) if sum(chosen) <= observed)
        return hits / total, f"exact ({total} arrangements)"
    rng = random.Random(PERMUTATION_SEED)
    hits = sum(1 for _ in range(PERMUTATIONS) if sum(rng.sample(ranks, m)) <= observed)
    return (hits + 1) / (PERMUTATIONS + 1), f"seeded permutation (seed {PERMUTATION_SEED}, {PERMUTATIONS} draws)"


def _contention_medians(run) -> dict | None:
    found = run.get("contention", {}).get("medians") if isinstance(run, dict) and \
        isinstance(run.get("contention"), dict) else None
    if not isinstance(found, dict):
        return None
    return {m: found.get(m) if isinstance(found.get(m), (int, float)) and not isinstance(found.get(m), bool)
            and math.isfinite(found.get(m)) else None for m in CONTENTION_MEASURES}


def verify_improvement(before, after, *, alpha: float = ALPHA) -> dict:
    """Did ``after`` measurably beat ``before``? Each is a benchmark result (or a list of seconds).

    VERIFIED needs a one-sided permutation p-value at most ``alpha``, a relative improvement of the medians above
    the noise floor (the before run's IQR over its median), and contention measured during both runs that did not
    ease in the after run's favour. INCONCLUSIVE when a side has fewer than MIN_REPLICATES samples, the two ran
    different workloads, no contention was measured during both, the after run was faster on a measurably quieter
    host (its speed cannot be credited to the change), or it was not faster on a measurably busier one (the change
    may be masked); NOT_IMPROVED otherwise. A different host is reported, not refused: a new node is exactly what an
    after run may measure."""
    b, a = _seconds(before), _seconds(after)
    digests = [run.get("workload_digest") for run in (before, after) if isinstance(run, dict)]
    hosts = [run.get("host") for run in (before, after) if isinstance(run, dict)]
    measured = {"before": _contention_medians(before), "after": _contention_medians(after),
                "tolerance": CONTENTION_TOLERANCE}
    result = {"kind": "compute.improvement", "alpha": alpha, "n_before": len(b), "n_after": len(a),
              "scope": VERDICT_SCOPE, "contention": measured,
              "same_host": ({k: v for k, v in (hosts[0] or {}).items() if not k.startswith("conditions")}
                            == {k: v for k, v in (hosts[1] or {}).items() if not k.startswith("conditions")})
              if len(hosts) == 2 else None}
    if len(digests) == 2 and digests[0] != digests[1]:
        return {**result, "verdict": "INCONCLUSIVE", "reason": "the two benchmarks ran different workloads"}
    if min(len(b), len(a)) < MIN_REPLICATES:
        return {**result, "verdict": "INCONCLUSIVE",
                "reason": f"fewer than {MIN_REPLICATES} replicates on a side"}
    q1, median_before, q3 = _quartiles(b)
    median_after = statistics.median(a)
    noise_floor = (q3 - q1) / median_before
    effect = (median_before - median_after) / median_before
    p_value, method = _rank_sum_p(b, a)
    stats = {"p_value": round(p_value, 6), "method": method, "median_before": round(median_before, 6),
             "median_after": round(median_after, 6), "relative_effect": round(effect, 6),
             "noise_floor": round(noise_floor, 6)}
    cb, ca = measured["before"], measured["after"]
    shifts = {m: round(ca[m] - cb[m], 4) for m in CONTENTION_MEASURES
              if cb is not None and ca is not None and cb[m] is not None and ca[m] is not None}
    measured["shift"] = shifts
    if not shifts:
        return {**result, **stats, "verdict": "INCONCLUSIVE",
                "reason": "no contention was measured during both runs, so a faster after run cannot be told apart "
                          "from a quieter host"}
    quieter = sorted(m for m, d in shifts.items() if d < -CONTENTION_TOLERANCE)
    busier = sorted(m for m, d in shifts.items() if d > CONTENTION_TOLERANCE)
    faster = p_value <= alpha and effect > noise_floor
    if faster and quieter:
        return {**result, **stats, "verdict": "INCONCLUSIVE",
                "reason": "faster, but the host was measurably quieter during the after run (" + ", ".join(
                    f"{m} {cb[m]} -> {ca[m]}" for m in quieter) + "), so the speed-up cannot be credited to the "
                    "change; run both under the same conditions"}
    if not faster and busier:
        return {**result, **stats, "verdict": "INCONCLUSIVE",
                "reason": "not faster, but the host was measurably busier during the after run (" + ", ".join(
                    f"{m} {cb[m]} -> {ca[m]}" for m in busier) + "), which may mask the change; run both under the "
                    "same conditions"}
    reason = ("faster beyond the before run's noise, unlikely by chance, on a host no quieter than before" if faster
              else "not faster beyond chance" if p_value > alpha else "faster, but within the before run's own noise")
    return {**result, **stats, "verdict": "VERIFIED" if faster else "NOT_IMPROVED", "reason": reason}


def enroll_node(journal: Journal, body: dict, command_digest: str) -> dict:
    required = {"node_id", "node_public_key", "light_cone"}
    if set(body) != required:
        raise ValueError("NODE_ENROLL needs node_id, node_public_key, light_cone")
    cone = LightCone.from_dict(body["light_cone"])
    if bytes.fromhex(body["node_public_key"]).__len__() != 32:
        raise ValueError("node key must be a 32-byte Ed25519 public key")
    record = {"node_id": body["node_id"], "node_public_key": body["node_public_key"], "light_cone": cone.to_dict(),
              "founder_authority_inherited": False, "command_digest": command_digest}
    journal.record("node.enrolled", record, key=body["node_id"])
    return record
