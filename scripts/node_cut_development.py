"""DEVELOPMENT ONLY measurements for the ``graph_node_cut_exact`` genome (minimum S-T vertex cut).

    taskset -c 1 python -I scripts/node_cut_development.py [--skip-natops] [--out DIR]

Writes, under ``docs/evidence/greg-node-cut-2026-10-21/``:

* ``latency.json``      the bounds derivation: in-process solve + independent verify latency on probe graphs up to
                        the declared bounds (random streams ``graph_node_cut_exact/latency/...``, distinct from the
                        instance generator's ``graph_node_cut_exact/<seed>`` streams);
* ``development.json``  the genome against the baseline, the second greedy, ``flow_maxflow`` (in process and through
                        ``cortex.reason`` on the node-split translation) and an independent ILP, on the genome's own
                        development seeds 0-9 and on the natops-2026-10-21 DEVELOPMENT part (545 instances, already
                        exposed in ``docs/evidence/greg-natural-ops-2026-10-21/development*.json``);
* ``overhead.json``     where a ``cortex.reason`` call's time goes (worker spawn, imports, compute, verification) and
                        prototype timings for the options in the README's proposal (none of them is on the path).

Held-out discipline: the natops extractor materialises the whole pool in memory (as the frozen extractor does); the
development filter (``split.part == "development"``) is applied before any arm, truth or size statistic runs, the
development ids are checked against the published ``development.json``, and held-out instances are discarded unread.
No held-out seed of any admission (1000-1029, 1100-1129, 1200-1399), no P8 seed and no natops held-out item is used.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from greg.cognition.genomes import node_cut as N  # noqa: E402

OUT = ROOT / "docs" / "evidence" / "greg-node-cut-2026-10-21"
LABEL = "DEVELOPMENT ONLY: exploratory, not confirmatory, not admission; genome dev seeds 0-9 and the natops " \
        "development part only"
NATOPS = ROOT / "docs" / "evidence" / "greg-natural-ops-2026-10-21" / "development.json"
DEV_SEEDS = tuple(range(10))
LATENCY_LIMIT_S = 20.0


def _med(xs):
    return round(statistics.median(xs), 6) if xs else None


def _p90(xs):
    return round(sorted(xs)[int(0.9 * (len(xs) - 1))], 6) if xs else None


def _host():
    try:
        load = Path("/proc/loadavg").read_text().split()[:3]
    except OSError:
        load = None
    return {"loadavg": load, "affinity": sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None,
            "python": platform.python_version()}


def _versions():
    import networkx
    import numpy
    import scipy
    return {"networkx": networkx.__version__, "scipy": scipy.__version__, "numpy": numpy.__version__}


# ------------------------------------------------------------------ latency probe -> declared bounds
def _dense(r, n, m):
    names = [f"pkg{r.randint(0, 9)}.mod{i:05d}" for i in range(n)]
    pairs = set()
    while len(pairs) < m:
        u, v = r.randrange(n), r.randrange(n)
        if u != v and (u, v) != (0, n - 1):
            pairs.add((u, v))
    return {"edges": sorted([names[u], names[v]] for u, v in pairs), "source": names[0], "target": names[n - 1]}


def _layered(width, layers):
    edges, prev = [], ["S"]
    for layer in range(layers):
        cur = [f"L{layer}_{i:03d}" for i in range(width)]
        edges += [[a, b] for a in prev for b in cur]
        prev = cur
    edges += [[a, "T"] for a in prev]
    return {"edges": edges, "source": "S", "target": "T"}


def _long_sparse(r, n, extra):
    names = [f"pkg{r.randint(0, 9)}.mod{i:05d}" for i in range(n)]
    pairs = {(i, i + 1) for i in range(n - 1)}
    while len(pairs) < n - 1 + extra:
        u = r.randrange(n - 2)
        v = min(n - 1, u + r.randint(2, 50))
        if (u, v) != (0, n - 1):
            pairs.add((u, v))
    return {"edges": sorted([names[u], names[v]] for u, v in pairs), "source": names[0], "target": names[-1]}


LEVELS = (1250, 2500, 5000, 10_000)     # edge caps probed; 10,000 is the cognition path's input-list limit


def _probe_cases(cap):
    """Probe graphs with at most ``cap`` edges, chosen to be slow for augmenting paths: many disjoint paths (dense,
    layered), long paths (long sparse) and the native dependency shape at its largest."""
    import math
    for seed in DEV_SEEDS[:3]:
        n = int(cap * 0.68)
        data = N.dependency_graph(random.Random(f"graph_node_cut_exact/latency/{seed}/{cap}"), n)
        if 1 <= len(data["edges"]) <= cap:
            yield f"dependency n={n} seed={seed}", data
        for div in (66, 33, 10, 5):
            n = max(cap // div, int(math.sqrt(2 * cap)) + 2)          # enough ordered pairs for cap edges
            yield f"dense n={n} m={cap} seed={seed}", _dense(
                random.Random(f"graph_node_cut_exact/latency-dense/{seed}/{cap}/{div}"), n, cap)
        n = int(cap * 0.9)
        yield f"long sparse n={n} seed={seed}", _long_sparse(
            random.Random(f"graph_node_cut_exact/latency-long/{seed}/{cap}"), n, cap - n + 1)
    w2 = int(math.sqrt(cap)) - 1
    w3 = int(math.sqrt(cap / 2)) - 1
    yield f"layered {w2} wide x 2", _layered(w2, 2)
    yield f"layered {w3} wide x 3", _layered(w3, 3)
    yield f"layered 20 wide x {cap // 400}", _layered(20, cap // 400)


def latency_probe(repeats=3):
    """Measure every probe level and derive the bounds: the largest level whose slowest solve + verify stayed under the
    target. The genome's declared MAX_EDGES / MAX_NODES must equal the derived level (checked; the run fails
    otherwise)."""
    saved = N.MAX_NODES, N.MAX_EDGES
    N.MAX_NODES = N.MAX_EDGES = max(LEVELS)       # probe above the declared bounds; restored below
    levels = []
    try:
        for cap in LEVELS:
            rows = []
            for name, data in _probe_cases(cap):
                nodes = {v for e in data["edges"] for v in e}
                solve, verify, cpu, status, k = [], [], [], None, None
                for _ in range(repeats):
                    c0 = time.thread_time()
                    t0 = time.perf_counter()
                    out = N.node_cut_solve(data, {})
                    t1 = time.perf_counter()
                    checks = N.node_cut_verify(data, out["output"], out["certificate"]) if out["output"] else {}
                    t2 = time.perf_counter()
                    cpu.append(time.thread_time() - c0)
                    solve.append(t1 - t0)
                    verify.append(t2 - t1)
                    status, k = out["status"], (out["output"] or {}).get("k")
                    if out["output"] and not all(checks.values()):
                        raise SystemExit(f"latency probe {name}: the verifier refuted the engine")
                rows.append({"case": name, "vertices": len(nodes), "edges": len(data["edges"]), "status": status,
                             "k": k, "solve_max_s": round(max(solve), 4), "verify_max_s": round(max(verify), 4),
                             "total_max_s": round(max(a + b for a, b in zip(solve, verify)), 4),
                             "cpu_total_max_s": round(max(cpu), 4)})
            worst = max(r["cpu_total_max_s"] for r in rows)
            levels.append({"edge_cap": cap, "worst_cpu_total_s": worst,
                           "worst_wall_total_s": max(r["total_max_s"] for r in rows),
                           "under_target": worst < N.LATENCY_TARGET_S,
                           "max_vertices_probed": max(r["vertices"] for r in rows), "host": _host(), "rows": rows})
            print(f"latency level {cap}: worst cpu {worst} s, wall {levels[-1]['worst_wall_total_s']} s", flush=True)
    finally:
        N.MAX_NODES, N.MAX_EDGES = saved
    ok = [lv["edge_cap"] for lv in levels if lv["under_target"]]
    # the largest level under target with every smaller level under target too (monotone; a noisy dip above is not used)
    derived = 0
    for lv in levels:
        if not lv["under_target"]:
            break
        derived = lv["edge_cap"]
    return {"label": LABEL, "host": _host(), "versions": _versions(), "repeats": repeats,
            "latency_target_s": N.LATENCY_TARGET_S, "levels": levels, "levels_under_target": ok,
            "derived_bounds": {"max_edges": derived, "max_vertices": derived},
            "declared_bounds": {"max_edges": N.MAX_EDGES, "max_vertices": N.MAX_NODES},
            "declared_equals_derived": (N.MAX_EDGES, N.MAX_NODES) == (derived, derived),
            "rule": ("bounds = the largest probed edge cap such that every probe at it and at every smaller cap "
                     "finished solve + independent verify in under the target CPU seconds of the calling thread (max "
                     "of 3 repeats; CPU time, because wall-clock on this shared host inflates with load: an earlier "
                     "probe at load ~4 measured 0.84 s wall for 'layered 70 wide x 3' at 9,940 edges); wall-clock is "
                     "recorded beside it; the vertex bound is set equal (long sparse probes reach 0.9x the edge cap "
                     "in vertices)"),
            "note": "through cortex.reason the 64 KiB request limit binds first (about 1,000-1,300 edges at natural "
                    "module-name lengths)"}


# ------------------------------------------------------------------ arms
def _timed(fn, *args):
    t0 = time.perf_counter()
    try:
        out = fn(*args)
        err = None
    except Exception as exc:          # an arm that raises abstains; the reason is recorded
        out, err = None, f"{type(exc).__name__}: {str(exc)[:160]}"
    return out, time.perf_counter() - t0, err


def candidate_in_process(data):
    out = N.node_cut_solve(data, {})
    if out["status"] != "ANSWER":
        return {"cut": None, "status": out["status"]}
    checks = N.node_cut_verify(data, out["output"], out["certificate"])
    return {"cut": out["output"]["cut"], "refuted": not all(checks.values())}


def practitioner(data):
    import networkx as nx
    g = nx.DiGraph([tuple(e) for e in data["edges"]])
    return {"cut": sorted(nx.minimum_node_cut(g, data["source"], data["target"]))}


_REGISTRY = None


def registry():
    """Evaluation-only registry view with both genomes pinned ATTACHED in memory (no body state changes)."""
    global _REGISTRY
    if _REGISTRY is None:
        from greg.cognition.cortex import registry_view
        _REGISTRY = registry_view()
        _REGISTRY.set_state("cognition.graph_node_cut_exact", "ATTACHED")
        _REGISTRY.set_state("cognition.flow_maxflow", "ATTACHED")
    return _REGISTRY


def via_reason(pid, operation, data):
    from greg.cognition.cortex import reason
    r = reason({"problem_id": pid[:128], "operation": operation, "data": data,
                "geometry": {"latency_limit": LATENCY_LIMIT_S}}, registry=registry())
    return r


def candidate_reason(data, pid):
    r = via_reason(pid, "min_vertex_cut", data)
    out = r.get("output") if r["abstention_state"] in ("NONE", "REFUTED") else None
    return {"cut": out["cut"] if isinstance(out, dict) else None, "state": r["abstention_state"],
            "refuted": r["abstention_state"] == "REFUTED", "verifier": (r.get("evaluator_result") or {}).get("verdict"),
            "missing": (r.get("missing_information") or [])[:1]}


def flow_reason(data, pid):
    r = via_reason(pid, "max_flow", N.split_network(data))
    state = r["abstention_state"]
    cut = None
    if state in ("NONE", "REFUTED") and isinstance(r.get("output"), dict):
        cut = []
        for u, v, c in r["output"]["cut_edges"]:
            if not (u.endswith("#in") and v == u[:-3] + "#out" and c == 1):
                cut = None
                break
            cut.append(u[:-3])
    return {"cut": sorted(cut) if cut is not None else None, "state": state, "refuted": state == "REFUTED",
            "missing": (r.get("missing_information") or [])[:1]}


def compiled_reason(data, pid):
    from greg.cognition.cortex import reason
    r = reason({"problem_id": pid[:128], "compile": {"geometry": {"consequence_class": "read_only",
                                                                   "latency_budget": LATENCY_LIMIT_S},
                                                      "data": data}}, registry=registry())
    sel = r.get("selected_receipt") if isinstance(r.get("selected_receipt"), dict) else {}
    out = sel.get("output") if sel.get("abstention_state") in ("NONE", "REFUTED") else None
    return {"cut": out["cut"] if isinstance(out, dict) else None, "selected": r.get("method_or_composition_selected"),
            "state": sel.get("abstention_state", r.get("state")), "refuted": sel.get("abstention_state") == "REFUTED"}


# ------------------------------------------------------------------ scoring
def _category(data, k, arm_out):
    """CORRECT iff a set of intermediate vertices that separates S from T and has size k; any other returned cut is
    WRONG; no cut is ABSTAIN. A refuted answer is WRONG whatever its cut."""
    if arm_out is None or arm_out.get("cut") is None:
        return "ABSTAIN"
    if arm_out.get("refuted"):
        return "WRONG"
    s = N.node_cut_score(data, {"k": k}, {"cut": arm_out["cut"]})
    return s["category"].upper()


def summarise(rows, arms):
    out = {}
    for arm in arms:
        cats = [r["arms"][arm]["result"] for r in rows if arm in r["arms"]]
        secs = [r["arms"][arm]["seconds"] for r in rows if arm in r["arms"]]
        out[arm] = {"n": len(cats), "correct": cats.count("CORRECT"), "wrong": cats.count("WRONG"),
                    "abstain": cats.count("ABSTAIN"), "median_seconds": _med(secs), "p90_seconds": _p90(secs)}
        sub = [r for r in rows if arm in r["arms"]]
        for region in ("within_flow_maxflow_bounds", "beyond_flow_maxflow_bounds"):
            part = [r["arms"][arm]["result"] for r in sub if r["subregion"] == region]
            out[arm][region] = {"n": len(part), "correct": part.count("CORRECT"), "wrong": part.count("WRONG"),
                                "abstain": part.count("ABSTAIN")}
    return out


def paired(rows, a, b):
    rank = {"CORRECT": 2, "ABSTAIN": 1, "WRONG": 0}
    wins = sum(1 for r in rows if rank[r["arms"][a]["result"]] > rank[r["arms"][b]["result"]])
    losses = sum(1 for r in rows if rank[r["arms"][b]["result"]] > rank[r["arms"][a]["result"]])
    ratios = [r["arms"][a]["seconds"] / r["arms"][b]["seconds"] for r in rows if r["arms"][b]["seconds"] > 0]
    return {"a": a, "b": b, "wins": wins, "losses": losses, "ties": len(rows) - wins - losses,
            "median_latency_ratio_a_over_b": _med(ratios)}


IN_PROCESS = {"candidate": candidate_in_process, "betweenness_greedy": N.betweenness_greedy,
              "degree_greedy": N.degree_greedy, "flow_maxflow_in_process": N.competitor_flow_maxflow,
              "ilp": N.competitor_ilp, "practitioner": practitioner}
REASON = {"candidate_reason": candidate_reason, "flow_maxflow_reason": flow_reason, "compiled_reason": compiled_reason}


def run_items(items, k_of, tag):
    rows = []
    for name, data in items:
        k = k_of(name, data)
        row = {"item": name, "vertices": len({v for e in data["edges"] for v in e}), "edges": len(data["edges"]),
               "k": k, "subregion": N.subregion(data), "arms": {}}
        for arm, fn in IN_PROCESS.items():
            out, secs, err = _timed(fn, data)
            row["arms"][arm] = {"result": _category(data, k, out), "seconds": round(secs, 6),
                                **({"error": err} if err else {}),
                                **({"status": out.get("status")} if isinstance(out, dict) and out.get("status") else {})}
        for arm, fn in REASON.items():
            out, secs, err = _timed(fn, data, f"nodecut-dev/{tag}/{name}/{arm}")
            row["arms"][arm] = {"result": _category(data, k, out), "seconds": round(secs, 6),
                                **({"error": err} if err else {}),
                                **{key: out[key] for key in ("state", "selected", "missing") if out and key in out}}
        rows.append(row)
    return rows


def synthetic_dev():
    items, truths = [], {}
    for seed in DEV_SEEDS:
        data, truth = N.node_cut_instance(seed)
        items.append((f"seed{seed}", data))
        truths[f"seed{seed}"] = truth["k"]
    return run_items(items, lambda name, data: truths[name], "synthetic")


def natops_dev():
    from cortex.evaluation.natural_ops import extract as E, run as R, split as S, truth as T
    published = json.loads(NATOPS.read_text())
    pool = E.extract(R.BASE)["instances"]
    dev = [i for i in pool if S.part(i["instance_id"]) == "development"]
    del pool                                       # held-out instances are discarded unread
    if {i["instance_id"] for i in dev} != {r["instance_id"] for r in published["rows"]}:
        raise SystemExit("development ids differ from the published natops development part")
    truths = {}
    items = []
    for inst in sorted(dev, key=lambda i: i["instance_id"]):
        data = {"edges": inst["edges"], "source": inst["source"], "target": inst["target"]}
        truths[inst["instance_id"]] = T.truth(inst)["k"]   # Menger + HiGHS ILP; must agree
        items.append((inst["instance_id"], data))
    return run_items(items, lambda name, data: truths[name], "natops")


# ------------------------------------------------------------------ overhead
def _run_isolated_median(argv, n=7):
    from greg.capabilities import run_isolated
    xs = []
    for _ in range(n):
        t0 = time.perf_counter()
        proc = run_isolated(argv, cwd=ROOT, timeout=60)
        xs.append(time.perf_counter() - t0)
        if proc.returncode:
            raise SystemExit(proc.stderr[-400:])
    return _med(xs)


def _import_profile(family, data):
    """-X importtime of the real solver worker on one request: cumulative microseconds by top-level package."""
    import re
    from greg.cognition.contracts import ProblemGeometry, canonical
    request = canonical({"data": data, "geometry": asdict(ProblemGeometry(epistemic_class="optimization"))})
    proc = subprocess.run([sys.executable, "-I", "-X", "importtime", str(ROOT / "greg/cognition/worker.py"), family,
                           request], capture_output=True, text=True, cwd=ROOT, timeout=60)
    by = {}
    for line in proc.stderr.splitlines():
        m = re.match(r"import time:\s+\d+ \|\s+(\d+) \|(\s*)(\S+)", line)
        if m and len(m.group(2)) <= 2:
            top = m.group(3).split(".")[0]
            by[top] = by.get(top, 0) + int(m.group(1))
    return {"total_ms": round(sum(by.values()) / 1000, 1),
            "by_package_ms": {k: round(v / 1000, 1) for k, v in sorted(by.items(), key=lambda kv: -kv[1])[:8]}}


def _fork_from_warm_parent(data, n=15):
    """Prototype of the zygote option (NOT on the path): a parent that has already imported the worker's modules
    forks one child per request; the child solves, writes JSON to a pipe and exits. Wall time per request."""
    import networkx  # noqa: F401  (warm the parent as a zygote would)
    import greg.cognition.solvers  # noqa: F401
    from greg.cognition.genomes import library
    library.executables()
    xs = []
    for _ in range(n):
        t0 = time.perf_counter()
        r, w = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(r)
            out = library.run("graph_node_cut_exact", data, {"latency_limit": 5.0, "compute_limit": 10000})
            os.write(w, json.dumps(out["output"]).encode())
            os._exit(0)
        os.close(w)
        chunks = []
        while True:
            b = os.read(r, 65536)
            if not b:
                break
            chunks.append(b)
        os.close(r)
        os.waitpid(pid, 0)
        json.loads(b"".join(chunks))
        xs.append(time.perf_counter() - t0)
    return _med(xs)


def overhead(natops_rows):
    import greg.cognition.cortex as C
    data = N.node_cut_instance(0)[0]
    phases = {"numeric": [], "verify": []}
    numeric, verify = C._numeric, C.independent_verify

    def timed_numeric(*a, **kw):
        t0 = time.perf_counter()
        try:
            return numeric(*a, **kw)
        finally:
            phases["numeric"].append(time.perf_counter() - t0)

    def timed_verify(*a, **kw):
        t0 = time.perf_counter()
        try:
            return verify(*a, **kw)
        finally:
            phases["verify"].append(time.perf_counter() - t0)
    breakdown = {}
    C._numeric, C.independent_verify = timed_numeric, timed_verify
    try:
        for arm, op, make in (("graph_node_cut_exact", "min_vertex_cut", lambda d: d),
                              ("flow_maxflow", "max_flow", N.split_network)):
            phases["numeric"].clear()
            phases["verify"].clear()
            totals, compute = [], []
            for seed in DEV_SEEDS:
                d = N.node_cut_instance(seed)[0]
                if arm == "flow_maxflow" and N.subregion(d) != "within_flow_maxflow_bounds":
                    continue
                t0 = time.perf_counter()
                r = via_reason(f"nodecut-dev/overhead/{arm}/{seed}", op, make(d))
                totals.append(time.perf_counter() - t0)
                if r["abstention_state"] != "NONE":
                    raise SystemExit(f"overhead run {arm} {seed}: {r['abstention_state']}")
                from greg.cognition.genomes import library
                item = library.executables()[arm]
                t0 = time.perf_counter()
                out = item.solve(make(d), {})
                item.verify(make(d), out["output"], out["certificate"])
                compute.append(time.perf_counter() - t0)
            breakdown[arm] = {"n": len(totals), "reason_total_s": _med(totals),
                              "solver_process_s": _med(phases["numeric"]),
                              "verifier_process_s": _med(phases["verify"]),
                              "parent_remainder_s": _med([t - a - b for t, a, b in
                                                          zip(totals, phases["numeric"], phases["verify"])]),
                              "in_process_solve_plus_verify_s": _med(compute)}
    finally:
        C._numeric, C.independent_verify = numeric, verify
    py = sys.executable
    pre = f"import sys;sys.dont_write_bytecode=True;sys.path.insert(0,{str(ROOT)!r});"
    spawn = {
        "python_-I_pass_isolated_s": _run_isolated_median([py, "-I", "-c", "pass"]),
        "import_worker_modules_isolated_s": _run_isolated_median(
            [py, "-I", "-c", pre + "import greg.cognition.solvers;from greg.cognition.genomes import library;"
                                   "library.executables()"]),
        "import_networkx_isolated_s": _run_isolated_median([py, "-I", "-c", "import networkx"]),
        "lazy_prototype_import_one_genome_plus_networkx_s": _run_isolated_median(
            [py, "-I", "-c", pre + "import greg.cognition.genomes.node_cut, networkx"]),
    }
    natops_reason = [r["arms"]["candidate_reason"]["seconds"] for r in natops_rows] if natops_rows else []
    return {"label": LABEL, "host": _host(), "reason_breakdown": breakdown, "spawn_and_import": spawn,
            "worker_import_profile_solve": _import_profile("graph_node_cut_exact", data),
            "worker_import_profile_flow_maxflow": _import_profile("flow_maxflow", N.split_network(data)),
            "prototype_fork_from_warm_parent_per_request_s": _fork_from_warm_parent(data),
            "natops_dev_candidate_reason_median_s": _med(natops_reason)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-natops", action="store_true")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    lat = latency_probe()
    lat["head"] = head
    (args.out / "latency.json").write_text(json.dumps(lat, indent=1, sort_keys=True) + "\n")
    print("latency derived", lat["derived_bounds"], "declared", lat["declared_bounds"], flush=True)
    synth = synthetic_dev()
    natops = [] if args.skip_natops else natops_dev()
    arms = list(IN_PROCESS) + list(REASON)
    dev = {"label": LABEL, "head": head, "host": _host(), "versions": _versions(),
           "genome": {"family": "graph_node_cut_exact", "version": N.INTELLIGENCES[0].genome.version},
           "synthetic_dev_seeds": {"seeds": list(DEV_SEEDS), "summary": summarise(synth, arms),
                                   "paired": [paired(synth, "candidate", b) for b in arms if b != "candidate"],
                                   "rows": synth}}
    if natops:
        dev["natops_development"] = {
            "n": len(natops), "source": "docs/evidence/greg-natural-ops-2026-10-21 development part (545)",
            "summary": summarise(natops, arms),
            "paired": [paired(natops, "candidate_reason", b) for b in ("flow_maxflow_reason", "compiled_reason")]
            + [paired(natops, "candidate", b) for b in arms if b not in ("candidate",)],
            "rows": natops}
    (args.out / "development.json").write_text(json.dumps(dev, indent=1, sort_keys=True) + "\n")
    ovh = overhead(natops)
    ovh["head"] = head
    (args.out / "overhead.json").write_text(json.dumps(ovh, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in dev.items() if k in ("synthetic_dev_seeds",)}["synthetic_dev_seeds"]["summary"],
                     indent=1))
    if natops:
        print(json.dumps(dev["natops_development"]["summary"], indent=1))
    print(json.dumps({k: v for k, v in ovh.items() if k != "host"}, indent=1))


if __name__ == "__main__":
    main()
