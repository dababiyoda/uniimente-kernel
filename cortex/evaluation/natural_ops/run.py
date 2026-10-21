"""Natural dependency-control-point family (natops-2026-10-21): development, freeze and the one confirmatory run.

    python -I cortex/evaluation/natural_ops/run.py --development   # exploratory part only; writes development.json
    python -I cortex/evaluation/natural_ops/run.py --freeze        # writes freeze.json (held-out ids + digests); scores nothing
    python -I cortex/evaluation/natural_ops/run.py --heldout       # the confirmatory run; refuses unless the freeze holds

Evidence label: NATURAL repository data (this repository's own import graphs), consequence-inert, exact
mathematical truth; NOT external validation. See ``PREREGISTRATION.md`` in the evidence directory.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from cortex.evaluation.natural_ops import arms as A, extract as E, split as S, truth as T  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "docs" / "evidence" / "greg-natural-ops-2026-10-21"
FREEZE = EVIDENCE / "freeze.json"
BASE = "9a6b3330ef5bcfbd617d9a50b183077238204750"
ALPHA = 0.05
LATENCY_RATIO = 1.25
BOOTSTRAP = 2000
BOOTSTRAP_SEED = 20261021
CONSTITUENTS = ("betweenness_greedy", "flow_maxflow")
FROZEN_FILES = (
    "cortex/evaluation/natural_ops/__init__.py", "cortex/evaluation/natural_ops/extract.py",
    "cortex/evaluation/natural_ops/truth.py", "cortex/evaluation/natural_ops/split.py",
    "cortex/evaluation/natural_ops/arms.py", "cortex/evaluation/natural_ops/run.py",
    "greg/cognition/cortex.py", "greg/cognition/worker.py", "greg/cognition/verification.py",
    "greg/cognition/compiler.py", "greg/cognition/catalog.py", "greg/cognition/contracts.py",
    "greg/cognition/genomes/flow.py", "greg/cognition/genomes/contract.py", "greg/cognition/genomes/library.py",
    "docs/evidence/greg-mind-evidence-index.json",
    "docs/evidence/greg-natural-ops-2026-10-21/PREREGISTRATION.md",
)


class FreezeError(Exception):
    pass


# ------------------------------------------------------------------ digests and the freeze
def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def code_digests(root: Path = ROOT) -> dict:
    return {p: sha256_file(root / p) for p in FROZEN_FILES}


def versions() -> dict:
    import networkx
    import numpy
    import scipy
    return {"python": platform.python_version(), "networkx": networkx.__version__, "scipy": scipy.__version__,
            "numpy": numpy.__version__}


def pool(root: Path = ROOT) -> dict:
    return E.extract(BASE, cwd=root)


def make_freeze(data: dict, root: Path = ROOT) -> dict:
    _, held = S.split(data["instances"])
    return {"family": "natops-2026-10-21 dependency control points", "base_commit": BASE,
            "n_pool": len(data["instances"]), "n_heldout": len(held),
            "heldout": sorted([i["instance_id"], i["subgraph_digest"]] for i in held),
            "pool_digest": E.digest([[i["instance_id"], i["subgraph_digest"]] for i in data["instances"]]),
            "code": code_digests(root), "versions": versions(),
            "decision": {"alpha": ALPHA, "latency_ratio": LATENCY_RATIO, "constituents": list(CONSTITUENTS),
                         "bootstrap": BOOTSTRAP, "bootstrap_seed": BOOTSTRAP_SEED}}


def check_freeze(frozen: dict, data: dict, root: Path = ROOT, *, require_clean: bool = True) -> list:
    """Raise FreezeError unless every frozen input equals the current one. Returns the held-out instances."""
    problems = []
    if frozen.get("base_commit") != BASE:
        problems.append("base commit differs")
    current = make_freeze(data, root)
    for key in ("heldout", "pool_digest", "n_pool", "n_heldout", "decision"):
        if frozen.get(key) != current[key]:
            problems.append(f"{key} differs from the freeze")
    for path, dig in frozen.get("code", {}).items():
        if current["code"].get(path) != dig:
            problems.append(f"code changed since the freeze: {path}")
    if set(frozen.get("code", {})) != set(FROZEN_FILES):
        problems.append("frozen file list differs")
    if frozen.get("versions") != current["versions"]:
        problems.append("interpreter or distribution versions differ")
    if require_clean:
        dirty = subprocess.run(("git", "status", "--porcelain", "--untracked-files=no"), cwd=root,
                               capture_output=True, text=True, check=True).stdout.strip()
        if dirty:
            problems.append("working tree is not clean")
        tracked = subprocess.run(("git", "ls-files", "--error-unmatch", str(FREEZE.relative_to(root))), cwd=root,
                                 capture_output=True)
        if tracked.returncode:
            problems.append("freeze is not committed")
    if problems:
        raise FreezeError("; ".join(problems))
    ids = {i for i, _ in frozen["heldout"]}
    return [i for i in data["instances"] if i["instance_id"] in ids]


# ------------------------------------------------------------------ statistics
def sign_test_greater(wins: int, losses: int) -> float:
    """One-sided exact sign test P(X >= wins | n = wins + losses, p = 1/2)."""
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def wilson(k: int, n: int, z: float = 1.959964) -> list:
    if n == 0:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]


def median_ratio_ci(a: list, b: list, seed: int = BOOTSTRAP_SEED) -> dict:
    """median(a) / median(b) with a paired percentile bootstrap 95% interval."""
    if not a or not b:
        return {"ratio": None, "ci95": [None, None]}
    rng = random.Random(seed)
    n = len(a)
    ratios = []
    for _ in range(BOOTSTRAP):
        idx = [rng.randrange(n) for _ in range(n)]
        mb = statistics.median(b[i] for i in idx)
        ratios.append(statistics.median(a[i] for i in idx) / mb if mb > 0 else math.inf)
    ratios.sort()
    mb = statistics.median(b)
    return {"ratio": round(statistics.median(a) / mb, 4) if mb > 0 else None,
            "ci95": [round(ratios[int(0.025 * BOOTSTRAP)], 4), round(ratios[int(0.975 * BOOTSTRAP) - 1], 4)]}


def holm(pvalues: dict) -> dict:
    order = sorted(pvalues, key=pvalues.get)
    m, out, running = len(order), {}, 0.0
    for rank, key in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[key]))
        out[key] = round(running, 6)
    return out


# ------------------------------------------------------------------ scoring and summary
def run_items(instances, arms=tuple(A.ARMS), log=print):
    rows = []
    for n, inst in enumerate(instances):
        try:
            tr = T.truth(inst)
        except T.TruthError as exc:
            rows.append({"instance_id": inst["instance_id"], "truth": None, "truth_error": str(exc)})
            log(f"{n} {inst['instance_id']} TRUTH_DISAGREEMENT {exc}")
            continue
        row = {"instance_id": inst["instance_id"], "commit": inst["commit"], "source": inst["source"],
               "target": inst["target"], "target_class": inst["target_class"], "n_nodes": inst["n_nodes"],
               "n_edges": inst["n_edges"], "k": tr["k"], "arms": {}}
        for name in arms:
            try:
                out = A.ARMS[name](inst)
            except Exception as exc:          # recorded on the arm, the run goes on
                out = {"cut": None, "state": "ARM_EXCEPTION", "missing": [f"{type(exc).__name__}: {exc}"[:200]],
                       "seconds": None, "cpu_seconds": None}
            result = T.score(inst, tr["k"], out.get("cut"))
            if out.get("refuted"):
                result = "WRONG"           # a refuted receipt is a false answer whatever its cut
            out["result"] = result
            row["arms"][name] = out
        rows.append(row)
        log(f"{n} {inst['instance_id']} k={tr['k']} " + " ".join(f"{a}={row['arms'][a]['result'][0]}" for a in arms))
    return rows


def summarise(rows, arms=tuple(A.ARMS)):
    scored = [r for r in rows if r.get("truth", 1) is not None and "arms" in r]
    out = {}
    for a in arms:
        res = [r["arms"][a] for r in scored]
        c = sum(x["result"] == "CORRECT" for x in res)
        w = sum(x["result"] == "WRONG" for x in res)
        ab = sum(x["result"] == "ABSTAIN" for x in res)
        secs = [x["seconds"] for x in res if x.get("seconds") is not None]
        cpu = [x["cpu_seconds"] for x in res if x.get("cpu_seconds") is not None]
        tf = {}
        for x in res:
            if x.get("translation_failure"):
                tf[x["translation_failure"]] = tf.get(x["translation_failure"], 0) + 1
        abst = [x for x in res if x["result"] == "ABSTAIN"]
        out[a] = {"n": len(res), "correct": c, "wrong": w, "abstain": ab, "correct_rate_ci95": wilson(c, len(res)),
                  "abstain_out_of_genome_bounds": sum(1 for x in abst if x.get("in_bounds") is False),
                  "abstain_in_bounds": sum(1 for x in abst if x.get("in_bounds") is not False),
                  "translation_failures": tf, "refuted": sum(1 for x in res if x.get("refuted")),
                  "arm_exceptions": sum(1 for x in res if x.get("state") == "ARM_EXCEPTION"),
                  "median_seconds": round(statistics.median(secs), 6) if secs else None,
                  "p90_seconds": round(sorted(secs)[int(0.9 * (len(secs) - 1))], 6) if secs else None,
                  "total_cpu_seconds": round(sum(cpu), 3), "money_usd": 0.0,
                  "subprocesses": sum(x.get("subprocesses", 0) or 0 for x in res),
                  "via_reason": any(x.get("via_reason") for x in res)}
        if a == "composition":
            out[a]["stage1_accepted"] = sum(1 for x in res if x.get("stage") == "baseline_certified_k1")
        if a == "compiled":
            sel = {}
            for x in res:
                sel[str(x.get("selected"))] = sel.get(str(x.get("selected")), 0) + 1
            out[a]["selected"] = sel
    return out


def paired(rows, a, b):
    scored = [r for r in rows if "arms" in r]
    wins = sum(1 for r in scored if r["arms"][a]["result"] == "CORRECT" and r["arms"][b]["result"] != "CORRECT")
    losses = sum(1 for r in scored if r["arms"][b]["result"] == "CORRECT" and r["arms"][a]["result"] != "CORRECT")
    lat = [(r["arms"][a]["seconds"], r["arms"][b]["seconds"]) for r in scored
           if r["arms"][a].get("seconds") is not None and r["arms"][b].get("seconds") is not None]
    faster = sum(1 for x, y in lat if x < y)
    slower = sum(1 for x, y in lat if x > y)
    return {"a": a, "b": b, "wins": wins, "losses": losses, "p_a_better": round(sign_test_greater(wins, losses), 6),
            "p_a_worse": round(sign_test_greater(losses, wins), 6),
            "latency_a_faster": faster, "latency_a_slower": slower,
            "p_a_faster": round(sign_test_greater(faster, slower), 6),
            "median_latency_ratio_a_over_b": median_ratio_ci([x for x, _ in lat], [y for _, y in lat])}


def decide(rows, summary):
    """The pre-registered rule (PREREGISTRATION.md, 'Decision rule')."""
    best = max(CONSTITUENTS, key=lambda a: (summary[a]["correct"], -summary[a]["wrong"],
                                            -(summary[a]["median_seconds"] or math.inf)))
    cmp = paired(rows, "composition", best)
    comp, cons = summary["composition"], summary[best]
    ratio = cmp["median_latency_ratio_a_over_b"]["ratio"]
    no_more_wrong = comp["wrong"] <= cons["wrong"]
    if cmp["p_a_worse"] < ALPHA or comp["wrong"] > cons["wrong"]:
        verdict = "REGRESSION"
    elif cmp["p_a_better"] < ALPHA and no_more_wrong and ratio is not None and ratio <= LATENCY_RATIO:
        verdict = "LIFT"
    elif (cmp["p_a_better"] >= ALPHA and no_more_wrong and ratio is not None and ratio <= 1 / LATENCY_RATIO
          and cmp["p_a_faster"] < ALPHA):
        verdict = "EFFICIENCY_ONLY"
    else:
        verdict = "NO_LIFT"
    return {"best_single_constituent": best, "primary": cmp, "verdict": verdict,
            "vpl_counts": verdict == "LIFT"}


def secondary(rows, summary):
    pairs = [("composition", "practitioner"), ("flow_maxflow", "practitioner"), ("degree_greedy", "flow_maxflow"),
             ("compiled", "flow_maxflow"), ("betweenness_greedy", "degree_greedy"),
             ("betweenness_greedy", "flow_maxflow")]
    out = {f"{a}_vs_{b}": paired(rows, a, b) for a, b in pairs}
    p = {}
    for key, v in out.items():
        p[key + ":better"] = v["p_a_better"]
        p[key + ":worse"] = v["p_a_worse"]
    adj = holm(p)
    for key, v in out.items():
        v["holm_p_a_better"] = adj[key + ":better"]
        v["holm_p_a_worse"] = adj[key + ":worse"]
    return out


def slices(rows):
    out = {}
    for cls in ("organ_or_evidence", "internal"):
        sub = [r for r in rows if r.get("target_class") == cls]
        out[cls] = {"n": len(sub), **{a: sum(1 for r in sub if r["arms"][a]["result"] == "CORRECT")
                                      for a in A.ARMS}}
    ks = {}
    for r in rows:
        if "arms" in r:
            ks[str(r["k"])] = ks.get(str(r["k"]), 0) + 1
    out["k_distribution"] = dict(sorted(ks.items(), key=lambda kv: int(kv[0])))
    out["commits"] = len({r["commit"] for r in rows if "commit" in r})
    return out


def report(rows, header):
    summary = summarise(rows)
    return {**header, "summary": summary, "decision": decide(rows, summary), "secondary": secondary(rows, summary),
            "slices": slices(rows), "truth_disagreements": [r for r in rows if r.get("truth") is None and "arms" not in r],
            "rows": rows}


# ------------------------------------------------------------------ entry
def main(argv):
    mode = argv[1] if len(argv) > 1 else ""
    data = pool()
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(("git", "rev-parse", "HEAD"), cwd=ROOT, capture_output=True, text=True).stdout.strip()
    if mode == "--development":
        dev, _ = S.split(data["instances"])
        rows = run_items(dev)
        out = report(rows, {"part": "development", "label": "EXPLORATORY; not confirmatory", "head": head,
                            "base_commit": BASE, "n": len(dev), "commits_read": data["commits"]})
        (EVIDENCE / "development.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
        print(json.dumps({"summary": out["summary"], "decision": out["decision"]}, indent=1))
    elif mode == "--freeze":
        frozen = make_freeze(data)
        FREEZE.write_text(json.dumps(frozen, indent=1, sort_keys=True) + "\n")
        print(f"froze {frozen['n_heldout']} held-out of {frozen['n_pool']}")
    elif mode == "--heldout":
        frozen = json.loads(FREEZE.read_text())
        held = check_freeze(frozen, data)          # raises before any held-out instance is scored
        log_lines = []

        def log(line):
            log_lines.append(line)
            print(line, flush=True)
        log(f"freeze holds; head {head}; {len(held)} held-out instances; versions {json.dumps(versions())}")
        rows = run_items(held, log=log)
        out = report(rows, {"part": "heldout", "label": "CONFIRMATORY; NATURAL repository data; consequence-inert; "
                            "not external validation", "head": head, "base_commit": BASE, "n": len(held),
                            "freeze_sha256": sha256_file(FREEZE), "versions": versions()})
        # the inputs must still be the frozen ones after the look
        check_freeze(frozen, pool(), require_clean=False)
        log(f"verdict {out['decision']['verdict']} (best single constituent {out['decision']['best_single_constituent']})")
        (EVIDENCE / "results.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
        (EVIDENCE / "run.log").write_text("\n".join(log_lines) + "\n")
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
