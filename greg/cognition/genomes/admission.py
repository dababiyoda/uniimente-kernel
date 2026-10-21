"""Admission harness: a method earns a place in the repertoire by native competence (directive section 15).

    native problem family -> simple baseline -> candidate -> strongest reasonable competitor
      -> held-out evaluation -> cost/latency normalisation -> falsification -> admission outcome

Protocol (frozen by ``--freeze`` before any held-out instance runs; ``--run`` refuses changed code):

* Development seeds ``DEV_SEEDS`` are for builders (``--dev``). Held-out seeds ``HELDOUT_SEEDS`` are run
  once, by this harness, for every genome in the freeze.
* Every arm (candidate ``solve``, ``baseline``, ``competitor``) runs every held-out instance in-process
  with wall-clock timing; the candidate's output is also passed through the genome's independent
  ``verify``, and a refuted candidate output is scored ``wrong`` (a false answer) with a quality one unit
  below abstaining, so it can never win a comparison.
* Quality is the genome's native score (higher is better); differences at or below the genome's
  tolerance are ties. Paired one-sided exact sign tests compare candidate with each other arm.
* One canonical-path smoke run per genome sends a held-out instance through
  ``greg.cognition.cortex.reason`` (isolated worker, verifier, CognitiveReceipt) with the family attached
  in an evaluation-only registry view - the same founder-pin mechanism P4 used; no body is changed.

Admission rule (``RULE``; recorded in every evidence file):
  COMPOSITION_ONLY  the genome declares no standalone decision (intermediate representation only);
  REJECTED          more wrong answers than the baseline, or significantly worse than the baseline;
  EXPERIMENTAL      no demonstrated edge over the simple baseline (quality not significantly better
                    and not an equal-quality, >=1.25x cheaper answer);
  SUPERSEDED        the competitor is significantly better and the candidate wins no instance, or the
                    two tie on every instance and the competitor is >=1.25x cheaper;
  NICHE_CAPABILITY  beats the baseline but is significantly worse than the competitor while winning
                    some instances, or adds wrong answers relative to the competitor, or ties the
                    competitor on quality while costing >=1.25x more;
  DEFAULT_FOR_GEOMETRY beats the baseline and is not significantly worse than the competitor, with no more
                    wrong answers and either significantly better quality or no worse than 1.25x the
                    competitor's median latency.
Latency is wall-clock in this container; the rule uses medians so one slow run cannot flip it.

Diagnostics (recorded since 2026-10-16; reported, never inputs to ``decide`` or the rule):
* per call, the calling thread's CPU time (``time.thread_time``) as ``cpu_seconds`` beside the wall-clock
  ``seconds``; its window encloses the wall-clock window, which is unchanged. It counts only the calling thread:
  work a method does on other threads or in other processes (a solver's worker threads, a multithreaded BLAS) is
  not in it, so it can understate such a method's cost;
* per genome, each arm's median CPU seconds (``diagnostics.median_cpu_seconds``);
* in the results header, the host's load at the start and end of the run (``host_load``: /proc/loadavg, this
  process's CPU affinity and the other Python processes by state).
A loaded host inflates wall-clock latency, unevenly across arms; these fields let a reader see how loaded the
host was and compare the CPU clock. Results written before 2026-10-16 (admission v1-v3) carry none of them, and
every reader here accepts both shapes.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from greg.cognition.genomes import library  # noqa: E402
from greg.cognition.genomes.contract import CATEGORIES, GenomeError  # noqa: E402

DEV_SEEDS = tuple(range(0, 10))
HELDOUT_SEEDS = tuple(range(1000, 1030))
# protected-evolution partitions (greg/cognition/evolution.py); 8060-8599 were added on 2026-10-21 for cycle 6 and
# no earlier freeze, admission run or pilot used them
P8_RESERVED = range(7000, 8600)
COST_RATIO = 1.25
ALPHA = 0.05
RULE = ("COMPOSITION_ONLY if no standalone decision; REJECTED if more wrong than baseline or significantly worse "
        "than baseline; EXPERIMENTAL if no significant edge over baseline (nor equal quality at >=1.25x lower "
        "median latency); SUPERSEDED if competitor significantly better and candidate wins none, or all ties and "
        "competitor >=1.25x cheaper; NICHE_CAPABILITY if beats baseline but significantly worse than competitor "
        "with some wins, or more wrong than competitor, or ties competitor at >=1.25x cost; DEFAULT_FOR_GEOMETRY "
        "if beats baseline, not significantly worse than competitor, no more wrong, and significantly better or "
        "<=1.25x competitor median latency. A competitor declared non-deployable (an oracle upper bound) is a "
        "reported reference: it neither supersedes nor demotes, so a candidate that beats its baseline without "
        "more wrong answers is DEFAULT_FOR_GEOMETRY. One-sided exact sign tests, alpha 0.05, 30 held-out seeds "
        "recorded in the freeze.")
EVIDENCE = ROOT / "docs" / "evidence" / "greg-genome-admission"


def sign_test(wins: int, losses: int) -> float:
    n = wins + losses
    return 1.0 if n == 0 else sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


# Each call is timed twice: wall-clock seconds (``time.perf_counter``, the rule's latency) and the calling thread's
# CPU seconds (``time.thread_time``, a reported diagnostic). The CPU clock is read before the wall clock starts and
# after it stops, so the wall-clock window is the one admission always measured.
def _candidate(item, data):
    cpu = time.thread_time()
    started = time.perf_counter()
    try:
        out = item.solve(data, {"latency_s": 5.0, "compute": 100000})
    except (GenomeError, ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
        seconds = time.perf_counter() - started
        cpu = time.thread_time() - cpu
        return None, seconds, cpu, {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    seconds = time.perf_counter() - started
    cpu = time.thread_time() - cpu
    if out["status"] != "ANSWER":
        return None, seconds, cpu, {"status": out["status"], "missing": out["missing"]}
    try:
        checks = item.verify(data, out["output"], out["certificate"])
    except Exception as exc:          # a verifier crash is a failed check, never a pass
        checks = {"verifier_error": False, "detail": f"{type(exc).__name__}"}
    refuted = not all(bool(v) for k, v in checks.items() if k != "detail")
    return out["output"], seconds, cpu, {"refuted": refuted, "checks": {k: bool(v) for k, v in checks.items()
                                                                          if k != "detail"}}


def _arm(fn, data):
    cpu = time.thread_time()
    started = time.perf_counter()
    try:
        out = fn(data)
    except (GenomeError, ValueError, TypeError, KeyError, ZeroDivisionError) as exc:
        seconds = time.perf_counter() - started
        cpu = time.thread_time() - cpu
        return None, seconds, cpu, {"error": f"{type(exc).__name__}: {str(exc)[:200]}"}
    seconds = time.perf_counter() - started
    return out, seconds, time.thread_time() - cpu, {}


def evaluate(item, seeds) -> list[dict]:
    rows = []
    for seed in seeds:
        data, truth = item.instance(seed)
        row = {"seed": seed, "subregion": item.subregion(data) if item.subregion else None, "arms": {}}
        for arm in ("candidate", "baseline", "competitor"):
            if arm == "candidate":
                out, seconds, cpu, info = _candidate(item, data)
            else:
                out, seconds, cpu, info = _arm(getattr(item, arm), data)
            s = item.score(data, truth, out)
            if s["category"] not in CATEGORIES:
                raise GenomeError(f"{item.genome.intelligence_id}: score category {s['category']!r}")
            if info.get("refuted"):
                # A refuted answer is a false answer: strictly worse than abstaining, never a win.
                s = {"quality": float(item.score(data, truth, None)["quality"]) - 1.0, "category": "wrong"}
            row["arms"][arm] = {"quality": float(s["quality"]), "category": s["category"],
                                "seconds": round(seconds, 6), "cpu_seconds": round(cpu, 6),   # cpu: diagnostic
                                **({"refuted": True} if info.get("refuted") else {}),
                                **({"info": info} if info else {})}
        rows.append(row)
    return rows


def compare(rows, a, b, tol) -> dict:
    wins = sum(1 for r in rows if r["arms"][a]["quality"] > r["arms"][b]["quality"] + tol)
    losses = sum(1 for r in rows if r["arms"][b]["quality"] > r["arms"][a]["quality"] + tol)
    return {"wins": wins, "losses": losses, "ties": len(rows) - wins - losses,
            "p_better": round(sign_test(wins, losses), 6), "p_worse": round(sign_test(losses, wins), 6)}


def decide(item, rows) -> tuple[str, dict]:
    tol = item.tolerance
    stats = {}
    for arm in ("candidate", "baseline", "competitor"):
        cats = [r["arms"][arm]["category"] for r in rows]
        stats[arm] = {**{c: cats.count(c) for c in CATEGORIES},
                      "mean_quality": round(statistics.fmean(r["arms"][arm]["quality"] for r in rows), 6),
                      "median_seconds": round(statistics.median(r["arms"][arm]["seconds"] for r in rows), 6)}
    vb, vk = compare(rows, "candidate", "baseline", tol), compare(rows, "candidate", "competitor", tol)
    c, b, k = stats["candidate"], stats["baseline"], stats["competitor"]
    lat_c, lat_b, lat_k = c["median_seconds"], b["median_seconds"], k["median_seconds"]
    cheaper_than_baseline = vb["wins"] == vb["losses"] == 0 and lat_c * COST_RATIO <= lat_b
    beats_baseline = vb["p_better"] < ALPHA or cheaper_than_baseline
    if not item.genome.standalone_decision:
        status = "COMPOSITION_ONLY"
    elif c["wrong"] > b["wrong"] or vb["p_worse"] < ALPHA:
        status = "REJECTED"
    elif not beats_baseline:
        status = "EXPERIMENTAL"
    elif not getattr(item, "competitor_deployable", True):
        status = "DEFAULT_FOR_GEOMETRY"          # the best deployable method here; the oracle gap is reported
    elif vk["p_worse"] < ALPHA:
        status = "NICHE_CAPABILITY" if vk["wins"] > 0 else "SUPERSEDED"
    elif vk["wins"] == vk["losses"] == 0 and lat_k * COST_RATIO <= lat_c:
        status = "SUPERSEDED"
    elif c["wrong"] > k["wrong"]:
        status = "NICHE_CAPABILITY"
    elif vk["p_better"] < ALPHA or lat_c <= lat_k * COST_RATIO:
        status = "DEFAULT_FOR_GEOMETRY"
    else:
        status = "NICHE_CAPABILITY"
    subregions = {}
    if item.subregion:
        for name in sorted({r["subregion"] for r in rows}):
            sub = [r for r in rows if r["subregion"] == name]
            subregions[name] = {"n": len(sub), "vs_baseline": compare(sub, "candidate", "baseline", tol),
                                "vs_competitor": compare(sub, "candidate", "competitor", tol)}
    detail = {"arms": stats, "vs_baseline": vb, "vs_competitor": vk, "subregions": subregions}
    if not getattr(item, "competitor_deployable", True):
        detail["competitor_role"] = "reference upper bound (not deployable): gap reported, never superseding"
    return status, detail


DIAGNOSTICS = ("reported diagnostics, never inputs to the admission decision: the rule decides on wall-clock "
               "medians only. cpu_seconds is the calling thread's CPU time per call (time.thread_time; work on "
               "other threads or processes is not in it); diagnostics.median_cpu_seconds is its median per arm; "
               "host_load is the host's load at the start and end of the run")


def diagnostics(rows) -> dict:
    """Per arm, the median thread CPU seconds of ``rows``: reported beside the wall-clock medians ``decide`` uses,
    never an input to it. Rows written before these diagnostics existed (admission v1-v3) have no ``cpu_seconds``;
    their medians are None, never a mix of measured and missing calls."""
    medians = {}
    for arm in ("candidate", "baseline", "competitor"):
        values = [r["arms"][arm].get("cpu_seconds") for r in rows]
        medians[arm] = (round(statistics.median(values), 6) if values and all(v is not None for v in values)
                        else None)
    return {"median_cpu_seconds": medians, "note": DIAGNOSTICS}


def _python_processes(cpus: set, proc: Path) -> dict | None:
    """Other Python processes on this host, counted by the state of their main thread, and how many running ones
    last ran on one of ``cpus``. A process is Python when its command name (<proc>/<pid>/stat) or the program it
    was started as (the first word of <proc>/<pid>/cmdline, the interpreter for a script run by its #! line)
    starts with "python". None without a readable ``proc``."""
    me = os.getpid()
    try:
        pids = [p for p in os.listdir(proc) if p.isdigit() and int(p) != me]
    except OSError:
        return None
    states, on_ours = {}, 0
    for pid in pids:
        try:
            stat = (proc / pid / "stat").read_text()
            name = stat[stat.index("(") + 1:stat.rindex(")")]
            fields = stat[stat.rindex(")") + 2:].split()       # fields[0] is field 3 (state), fields[36] field 39
            program = Path((proc / pid / "cmdline").read_bytes().split(b"\0")[0].decode(errors="replace")).name
        except (OSError, ValueError):                          # the process exited while it was being read
            continue
        if not fields or not (name.startswith("python") or program.startswith("python")):
            continue
        states[fields[0]] = states.get(fields[0], 0) + 1
        if fields[0] == "R" and len(fields) > 36 and fields[36].isdigit() and int(fields[36]) in cpus:
            on_ours += 1
    return {"count": sum(states.values()), "by_state": dict(sorted(states.items())),
            "running_last_on_our_cpus": on_ours}


def host_load(proc: Path = Path("/proc")) -> dict:
    """How loaded the host is now: /proc/loadavg, this process's CPU affinity and the other Python processes. A
    reported diagnostic (a loaded host inflates wall-clock latency, unevenly across arms), never an input to the
    admission decision. A field this host cannot report is None."""
    out = {"at": datetime.now(timezone.utc).isoformat()}
    try:
        one, five, fifteen, entities = (proc / "loadavg").read_text().split()[:4]
        runnable, total = entities.split("/")
        out["loadavg"] = {"1m": float(one), "5m": float(five), "15m": float(fifteen), "runnable": int(runnable),
                          "entities": int(total)}
    except (OSError, ValueError):
        out["loadavg"] = None
    try:
        affinity = sorted(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        affinity = None
    out["cpu_affinity"], out["cpu_count"] = affinity, os.cpu_count()
    out["other_python_processes"] = _python_processes(set(affinity or ()), proc)
    return out


# The converged tree's operation-family admission freezes (v3 on): each declares an inclusive held-out seed range
# under inputs.seeds (round-3 review of #179, finding 5). #155's earlier operation runs (1001-1040, 2001-2040,
# 3001-3040) used other generators than the genome harness; their overlap with genome and pilot ranges is recorded
# under review L3 and not registered here, so no instance was reused.
OPERATION_FREEZES = ("cortex/evaluation/genome_admission/freeze-ops-v*.json",)


def spent_seeds(exclude: Path | None = None) -> set[int]:
    """Held-out seeds already used by any admission freeze in the evidence tree, genome or operation family."""
    out = set()
    for manifest in EVIDENCE.glob("*/freeze.json") if EVIDENCE.exists() else []:
        if exclude is not None and manifest.parent == exclude:
            continue
        out |= set(json.loads(manifest.read_text())["inputs"].get("heldout_seeds", []))
    for pattern in OPERATION_FREEZES:
        for manifest in ROOT.glob(pattern):
            seeds = json.loads(manifest.read_text()).get("inputs", {}).get("seeds")
            if isinstance(seeds, list) and len(seeds) == 2 and all(isinstance(x, int) for x in seeds):
                out |= set(range(seeds[0], seeds[1] + 1))
    return out


def reused_instances(families, heldout, spent) -> dict:
    """Per family that samples a finite real-data pool: held-out seeds whose data identity was already drawn by a
    development seed, an earlier admission freeze or a completed P8 cycle (or twice within this held-out set)."""
    from greg.cognition import evolution
    out = {}
    for family in families:
        key = getattr(library.executables()[family], "instance_key", None)
        if key is None:
            continue
        used = {key(s) for s in (*DEV_SEEDS, *sorted(spent))} | evolution.used_instance_keys(family)
        keys = [key(s) for s in heldout]
        clash = sorted({k for k in keys if k in used} | {k for k in keys if keys.count(k) > 1})
        if clash:
            out[family] = {"reused": len(clash), "of": len(keys)}
    return out


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _module_file(family: str) -> Path:
    item = library.executables()[family]
    module = sys.modules[item.solve.__module__]
    return Path(module.__file__)


FREEZE_EXTRA = ("cortex/evaluation/data/m4_weekly.json.gz", "tools/offline_test.py",
                "requirements-cortex.txt", "requirements-cognition.txt")


def inputs(families, heldout=HELDOUT_SEEDS) -> dict:
    """Everything a held-out run can execute or read: the import closure of this harness and the isolated
    worker (the smoke runs through the canonical cortex path), all of ``greg/cognition`` (the library imports
    genome modules by name), the M4 data and the dependency versions. The 2026-10-13-v1 freeze hashed only
    the genome modules; its run is pinned by its commit (496c85b)."""
    from cortex.evaluation.closure import code_closure, dependency_versions
    files = code_closure(("greg/cognition/genomes/admission.py", "greg/cognition/worker.py"),
                         packages=("greg/cognition",), extra=FREEZE_EXTRA, root=ROOT)
    return {"rule": RULE, "dev_seeds": list(DEV_SEEDS), "heldout_seeds": list(heldout),
            "families": sorted(families), "code": {p: _sha(ROOT / p) for p in files},
            "dependencies": dependency_versions()}


def source_dirty(paths, root: Path = ROOT) -> list[str]:
    """The frozen files whose bytes are not their blob at HEAD (modified, staged, untracked or absent from HEAD);
    every path when git cannot tell. The freeze digests bind the bytes a run executes; this binds them to the
    recorded ``source_commit``, as P8's ``source_dirty`` does (2026-10-15 independent review)."""
    paths = sorted(paths)
    try:
        tree = subprocess.run(["git", "ls-tree", "-r", "-z", "HEAD", "--", *paths], cwd=root,
                              capture_output=True, check=True).stdout
        work = subprocess.run(["git", "hash-object", "--", *paths], cwd=root, capture_output=True, text=True,
                              check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        return paths
    committed = {}
    for entry in filter(None, tree.split(b"\0")):
        meta, _, name = entry.partition(b"\t")
        committed[name.decode()] = meta.split()[2].decode()
    return [p for p, blob in zip(paths, work) if committed.get(p) != blob] if len(work) == len(paths) else paths


def report_header(target: Path, frozen: dict) -> dict:
    """What results.json records about the run before any genome result: the freeze, the commit, whether the
    frozen files were the committed ones and the host's load as the run starts (a diagnostic; ``close_report`` adds
    the load at the end)."""
    return {"schema": "greg-genome-admission/1", "freeze_sha256": _sha(target / "freeze.json"),
            "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "source_dirty": source_dirty(frozen["inputs"]["code"]),
            "platform": platform.platform(), "python": sys.version.split()[0], "rule": RULE,
            "diagnostics": DIAGNOSTICS, "host_load": {"start": host_load()}, "genomes": {}}


def genome_entry(item, rows, status: str, detail: dict, canonical: dict) -> dict:
    """One genome's entry in results.json: the decision and its detail (``decide``), the per-arm CPU diagnostics
    (never an input to the decision), the canonical-path smoke and every held-out row."""
    return {"intelligence_id": item.genome.intelligence_id, "layer": item.genome.layer,
            "version": item.genome.version, "baseline": item.genome.baseline, "competitor": item.genome.competitor,
            "status": status, **detail, "diagnostics": diagnostics(rows), "canonical_path": canonical,
            "heldout": rows}


def close_report(report: dict) -> dict:
    """The end of a run: its finishing time and the host's load as it ends (a diagnostic)."""
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    report.setdefault("host_load", {})["end"] = host_load()
    return report


def smoke(family: str, seed: int = HELDOUT_SEEDS[0]) -> dict:
    """One held-out instance through GREG's canonical cognition path, family attached for evaluation only."""
    from greg.cognition.cortex import reason, registry_view
    item = library.executables()[family]
    data, _ = item.instance(seed)
    registry = registry_view()
    cid = f"cognition.{family}"
    if cid not in registry.manifests:
        return {"state": "NOT_REGISTERED", "capability": cid}
    registry.set_state(cid, "ATTACHED")
    receipt = reason({"problem_id": f"admission:{family}", "operation": item.genome.operation, "data": data,
                      "geometry": {"latency_limit": 30}}, registry=registry)
    return {"capability": cid, "abstention_state": receipt["abstention_state"], "method": receipt["method"],
            "verifier": receipt["evaluator_result"].get("verdict"), "proof_type": receipt["proof_type"],
            "latency_s": round(receipt["latency"], 4), "authority_created": receipt["authority_created"],
            "receipt_id": receipt["receipt_id"]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", metavar="FAMILY", help="run development seeds for one family (builders)")
    ap.add_argument("--freeze", metavar="RUN_ID", help="freeze code and protocol for every library family")
    ap.add_argument("--run", metavar="RUN_ID", help="run the frozen held-out admission")
    ap.add_argument("--only", nargs="*", help="restrict --freeze to these families")
    ap.add_argument("--heldout-start", type=int, default=HELDOUT_SEEDS[0],
                    help="first of 30 fresh held-out seeds, recorded in the freeze (spent ranges are refused)")
    args = ap.parse_args(argv)
    families = sorted(library.executables())
    if args.dev:
        item = library.executables()[args.dev]
        start = host_load()
        rows = evaluate(item, DEV_SEEDS)
        status, detail = decide(item, rows)
        print(json.dumps({"family": args.dev, "partition": "dev", "status_if_heldout_matched": status,
                          **detail, "diagnostics": diagnostics(rows),
                          "host_load": {"start": start, "end": host_load()}}, indent=1))
        return
    if args.freeze:
        target = EVIDENCE / args.freeze
        manifest = target / "freeze.json"
        if manifest.exists():
            raise SystemExit("refusing to overwrite an existing admission freeze; use a new run id")
        target.mkdir(parents=True, exist_ok=True)
        chosen = sorted(args.only) if args.only else families
        heldout = tuple(range(args.heldout_start, args.heldout_start + len(HELDOUT_SEEDS)))
        if set(heldout) & (spent_seeds(exclude=target) | set(DEV_SEEDS) | set(P8_RESERVED)):
            raise SystemExit("those held-out seeds are development, P8-reserved or spent by an earlier admission "
                             "run; choose fresh ones")
        reused = reused_instances(chosen, heldout, spent_seeds(exclude=target))
        if reused:
            raise SystemExit(f"fresh seed numbers draw data already used: {reused}; a genome that samples a finite "
                             f"pool needs unused data, not unused seed numbers")
        manifest.write_text(json.dumps({"frozen_at": datetime.now(timezone.utc).isoformat(),
                                        "inputs": inputs(chosen, heldout)}, indent=2) + "\n")
        print(manifest)
        return
    if not args.run:
        raise SystemExit("--dev, --freeze or --run required")
    target = EVIDENCE / args.run
    frozen = json.loads((target / "freeze.json").read_text())
    chosen = frozen["inputs"]["families"]
    heldout = tuple(frozen["inputs"]["heldout_seeds"])
    if frozen["inputs"] != inputs(chosen, heldout):
        raise SystemExit("FROZEN_INPUT_CHANGED: admission results cannot be reported")
    if (target / "results.json").exists():
        raise SystemExit("refusing to overwrite admission results")
    report = report_header(target, frozen)
    for family in chosen:
        item = library.executables()[family]
        rows = evaluate(item, heldout)
        status, detail = decide(item, rows)
        try:
            canonical = smoke(family, heldout[0])
        except Exception as exc:       # recorded, never hidden; a failing smoke blocks DEFAULT below
            canonical = {"state": "SMOKE_FAILED", "error": f"{type(exc).__name__}: {str(exc)[:300]}"}
        if canonical.get("verifier") not in ("STRUCTURALLY_VERIFIED", None) or canonical.get("state") == "SMOKE_FAILED":
            status = {"DEFAULT_FOR_GEOMETRY": "NICHE_CAPABILITY"}.get(status, status)
        report["genomes"][family] = genome_entry(item, rows, status, detail, canonical)
        print(json.dumps({"family": family, "status": status, "vs_baseline": detail["vs_baseline"],
                          "vs_competitor": detail["vs_competitor"]}), flush=True)
    close_report(report)
    (target / "results.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({f: g["status"] for f, g in report["genomes"].items()}, indent=1))


if __name__ == "__main__":
    main()
