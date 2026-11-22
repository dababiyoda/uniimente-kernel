"""Summarise the Stage A scale run of CuBFF itself (131,072 programs, up to 16,000 epochs) from its CSV logs.

    python tests/evidence/bff-reference-2026-11-22/differential/scale.py LOG_DIR OUT.json

Each seed was run as
    bin/main --lang bff_noheads --num 131072 --seed S --max_epochs 16000 --print_interval 256 --save_interval 256
             --clear_interval 2048 --eval_selfrep --stopping_selfrep_count 13108 --disable_output --log seedS.csv
CuBFF writes epoch, brotli_size, soup_size, higher_entropy and number_selfreps every 256 epochs.

Transition criterion, fixed before any seed was looked at: at least 13,108 programs (10% of the soup) score >= 5 on
CuBFF's own CheckSelfRep at a logged epoch. The first logged epoch meeting it is recorded together with the
higher-order entropy jump. A seed that stops before 16,000 epochs without meeting it is "unfinished" and is not
counted either way. The 95% interval is exact (Clopper-Pearson).
"""
import csv
import json
import sys
from math import comb
from pathlib import Path

THRESHOLD, MAX_EPOCHS = 13108, 16000


def binom_cdf(k, n, p):
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def clopper_pearson(k, n, alpha=0.05):
    def solve(f):
        lo, hi = 0.0, 1.0
        for _ in range(100):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) else (lo, mid)
        return (lo + hi) / 2
    lower = 0.0 if k == 0 else solve(lambda p: 1 - binom_cdf(k - 1, n, p) < alpha / 2)
    upper = 1.0 if k == n else solve(lambda p: binom_cdf(k, n, p) > alpha / 2)
    return lower, upper


log_dir, out = Path(sys.argv[1]), Path(sys.argv[2])
seeds = []
for path in sorted(log_dir.glob("seed*.csv"), key=lambda p: int(p.stem[4:])):
    rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(path.open())]
    hit = next((r for r in rows if r["number_selfreps"] >= THRESHOLD), None)
    last = rows[-1] if rows else None
    if hit:
        before = rows[rows.index(hit) - 1] if rows.index(hit) else hit
        outcome = {"outcome": "transition", "transition_epoch": int(hit["epoch"]),
                   "selfreps_at_transition": int(hit["number_selfreps"]),
                   "higher_entropy_before": before["higher_entropy"], "higher_entropy_at": hit["higher_entropy"]}
    elif last and last["epoch"] >= MAX_EPOCHS:
        outcome = {"outcome": "no transition by 16,000 epochs", "max_selfreps": int(max(r["number_selfreps"] for r in rows)),
                   "max_higher_entropy": max(r["higher_entropy"] for r in rows)}
    else:
        outcome = {"outcome": "unfinished", "last_epoch": int(last["epoch"]) if last else 0}
    seeds.append({"seed": int(path.stem[4:]), "logged_rows": len(rows), **outcome})

finished = [s for s in seeds if s["outcome"] != "unfinished"]
k, n = sum(s["outcome"] == "transition" for s in finished), len(finished)
lo, hi = clopper_pearson(k, n) if n else (0.0, 1.0)
summary = {"finished_seeds": n, "transitions": k, "rate": k / n if n else None,
           "clopper_pearson_95": [round(lo, 4), round(hi, 4)], "paper_rate_reference": 0.4,
           "paper_rate_inside_interval": lo <= 0.4 <= hi,
           "verdict": ("inconclusive: too few seeds to test the paper's ~40%" if n < 20 else
                       "compatible with ~40%" if lo <= 0.4 <= hi else "incompatible with ~40%")}
result = {"cubff_commit": "f212e849027c98fcf4b242eccfb5fed435223e23", "programs": 131072, "max_epochs": MAX_EPOCHS,
          "criterion": f"number_selfreps >= {THRESHOLD} (10% of the soup) at a logged epoch",
          "summary": summary, "seeds": seeds}
out.write_text(json.dumps(result, indent=1) + "\n")
print(json.dumps(summary))
