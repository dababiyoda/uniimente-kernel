"""Bounded spontaneous-emergence runs of the Python reference soup (developmental/bff.py).

    python tests/evidence/bff-reference-2026-11-22/run.py SEED EPOCHS PROGRAMS WALL_SECONDS OUT.json

Every 100 epochs: the share of bytes that are instructions, lzma-based higher-order entropy, distinct programs, and
CuBFF's self-replication score over a fixed sample of 32 programs. Stops at EPOCHS, at WALL_SECONDS, or once half the
sample scores as self-replicating. A soup of 1,024 is 128 times smaller than CuBFF's default, so a run that sees no
transition says nothing against the paper's rate; it is a measured outcome of this reference at this scale.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from developmental import bff  # noqa: E402

seed, epochs, n, wall, out = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4]), Path(sys.argv[5])
soup, rows, t0, mutations = bff.Soup(n, seed=seed), [], time.monotonic(), 0
sample = [(i * 7919) % n for i in range(32)]
stopped = "epochs"
while soup.epoch < epochs:
    mutations += soup.step()
    if soup.epoch % 100 == 0 or soup.epoch == 1:
        data = bytes(soup.programs)
        scores = [bff.selfrep_score(soup.program(i), seed=seed, n=n, index=i) for i in sample]
        rows.append({"epoch": soup.epoch, "wall_s": round(time.monotonic() - t0, 1), "ops_total": soup.ops,
                     "mutations_total": mutations, "op_fraction": round(bff.op_fraction(data), 4),
                     "higher_order_entropy_lzma": round(bff.entropy_measures(data)["higher_order_entropy"], 4),
                     "distinct_programs": len({soup.program(i) for i in range(n)}),
                     "sample_selfrep": sum(s >= bff.SELFREP_THRESHOLD for s in scores), "max_score": max(scores)})
        print(json.dumps(rows[-1]), flush=True)
        if rows[-1]["sample_selfrep"] >= 16:
            stopped = "transition: half the sample self-replicates"
            break
    if time.monotonic() - t0 > wall:
        stopped = "wall-clock cap"
        break
out.write_text(json.dumps({"seed": seed, "programs": n, "epochs_run": soup.epoch, "stopped": stopped,
                           "final_digest": soup.digest(), "reference": bff.SOURCE, "rows": rows}, indent=1) + "\n")
