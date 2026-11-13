"""PR #155 lineage: Dawid-Skene vs the simpler one-step weighted vote on sparse, multi-class, structured-error crowds.

Admission v2 (seeds 2001-2040) admitted Dawid-Skene over majority vote but found it statistically tied with
the one-step agreement-weighted vote. This pre-registered test asks whether its full confusion model earns its
complexity on the geometry it is built for. Every parameter is declared here before any run; seeds 3001-3040
were never generated before. Path is lineage-unique (founder decision of 2026-10-14, a832c73).

Geometry per seed: n = 100-200 items; k = 4, 5 or 6 classes with random class weights; m = 8-15 observers,
each labelling every item with probability U(.10, .30) (sparse); items with fewer than 2 votes receive
labels from random additional observers until they have 2. Observer kinds (probabilities .25/.35/.25/.15):

* expert:   correct with probability U(.80, .95), otherwise a uniformly random other class;
* average:  correct with probability U(1/k + .15, 1/k + .35), otherwise uniform other class;
* confuser: a systematic swap - true class c is labelled (c + 1) mod k with probability .6, else c;
* spammer:  a uniformly random class.

Arms: candidate Dawid-Skene (``SOLVERS["crowd"]``, the shipped settings); baseline majority vote; competitor
one-step agreement-weighted vote (accuracy from agreement with the majority, Nitzan-Paroush log-odds
weights, clipped at 0); reference (not in the rule) the Bayes posterior that knows every observer's true
confusion matrix and the class weights. Metric: item error rate. Ties broken by lowest class index for every
vote. Rule (frozen): v1's admission status rule; the decisive question is candidate vs competitor - Dawid-
Skene earns its complexity only if it beats the one-step vote with one-sided sign test p < 0.05.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from cortex.evaluation.genome_admission import run as V1  # noqa: E402
from greg.cognition.solvers import SOLVERS  # noqa: E402

SEEDS = range(3001, 3041)
GEOMETRY = {"compute_limit": 100000, "latency_limit": 10.0}
MANIFEST = HERE / "freeze-v1.json"
FROZEN_CODE = ["cortex/evaluation/pr155_crowd_sparse/run.py", "cortex/evaluation/genome_admission/run.py",
               "greg/cognition/repertoire.py", "greg/cognition/solvers.py"]


def instance(seed):
    r = random.Random(seed)
    k, n, m = r.choice((4, 5, 6)), r.randint(100, 200), r.randint(8, 15)
    weights = [r.random() + .2 for _ in range(k)]
    prior = [w / sum(weights) for w in weights]
    truth = [r.choices(range(k), weights)[0] for _ in range(n)]
    kinds = [r.choices(("expert", "average", "confuser", "spammer"), (.25, .35, .25, .15))[0] for _ in range(m)]
    acc = [r.uniform(.80, .95) if t == "expert" else r.uniform(1 / k + .15, 1 / k + .35) if t == "average" else None
           for t in kinds]
    cover = [r.uniform(.10, .30) for _ in range(m)]

    def confusion(j):                     # P(label | true) rows for observer j
        if kinds[j] == "spammer":
            return [[1 / k] * k for _ in range(k)]
        if kinds[j] == "confuser":
            return [[.4 if l == c else .6 if l == (c + 1) % k else 0.0 for l in range(k)] for c in range(k)]
        a = acc[j]
        return [[a if l == c else (1 - a) / (k - 1) for l in range(k)] for c in range(k)]
    matrices = [confusion(j) for j in range(m)]

    def label(j, t):
        return r.choices(range(k), matrices[j][t])[0]
    votes = [dict() for _ in range(n)]
    for i in range(n):
        for j in range(m):
            if r.random() < cover[j]:
                votes[i][j] = label(j, truth[i])
        while len(votes[i]) < 2:
            j = r.randrange(m)
            if j not in votes[i]:
                votes[i][j] = label(j, truth[i])
    return k, n, m, prior, truth, kinds, matrices, votes


def _vote(v, weights, k):
    score = [0.0] * k
    for j, l in v.items():
        score[l] += weights.get(j, 0.0)
    return max(range(k), key=lambda c: (score[c], -c))


def bench(seed):
    k, n, m, prior, truth, kinds, matrices, votes = instance(seed)
    classes = [f"c{c}" for c in range(k)]
    data = {"classes": classes, "labels": [{"item_id": f"i{i}", "observer_id": f"o{j}", "independence_group": f"o{j}",
                                            "label": classes[l]} for i in range(n) for j, l in votes[i].items()]}
    out = SOLVERS["crowd"](data, GEOMETRY)
    ds = [classes.index(out["output"]["labels"][f"i{i}"]) for i in range(n)]
    majority = [_vote(v, {j: 1.0 for j in range(m)}, k) for v in votes]
    agree = {j: (sum(1 for i in range(n) if j in votes[i] and votes[i][j] == majority[i]) + 1) /
                (sum(1 for i in range(n) if j in votes[i]) + 2) for j in range(m)}

    def logodds(a):
        a = min(max(a, 1e-3), 1 - 1e-3)
        return max(0.0, math.log((k - 1) * a / (1 - a)))
    one_step = [_vote(v, {j: logodds(agree[j]) for j in range(m)}, k) for v in votes]

    def bayes(v):
        logs = [math.log(prior[c]) + sum(math.log(max(matrices[j][c][l], 1e-12)) for j, l in v.items())
                for c in range(k)]
        return max(range(k), key=lambda c: (logs[c], -c))
    oracle = [bayes(v) for v in votes]

    def error(labels):
        return sum(1 for a, b in zip(labels, truth) if a != b) / n
    return {"candidate": error(ds), "baseline": error(majority), "competitor": error(one_step),
            "reference": error(oracle), "k": k, "n": n, "m": m, "kinds": kinds}


def inputs():
    return {"code": {p: "sha256:" + hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in FROZEN_CODE},
            "seeds": [SEEDS.start, SEEDS.stop - 1]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.freeze:
        if MANIFEST.exists():
            raise SystemExit("refusing to overwrite an existing freeze; create a new version")
        MANIFEST.write_text(json.dumps({"frozen_at": datetime.now(timezone.utc).isoformat(), "inputs": inputs()},
                                       indent=2) + "\n")
        return
    if json.loads(MANIFEST.read_text())["inputs"] != inputs():
        raise SystemExit("FROZEN_INPUT_CHANGED: results cannot be reported")
    rows = [{"seed": s, **bench(s)} for s in SEEDS]
    status = V1.status([{k: r[k] for k in ("candidate", "baseline", "competitor")} for r in rows])
    w = sum(1 for r in rows if r["candidate"] < r["reference"] - 1e-9)
    l = sum(1 for r in rows if r["reference"] < r["candidate"] - 1e-9)
    report = {"schema": "pr155-crowd-sparse/1", "lineage": "PR #155", "manifest_sha256": "sha256:" + hashlib.sha256(
        MANIFEST.read_bytes()).hexdigest(), "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "status": status, "earns_complexity_over_one_step": status.get("vs_competitor", {}).get("p_better", 1) < 0.05,
              "reference_oracle": {"wins": w, "losses": l},
              "mean_error": {a: round(statistics.fmean(r[a] for r in rows), 6)
                             for a in ("candidate", "baseline", "competitor", "reference")},
              "rows": rows}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "earns_complexity_over_one_step", "reference_oracle",
                                             "mean_error")}, indent=1))


if __name__ == "__main__":
    main()
