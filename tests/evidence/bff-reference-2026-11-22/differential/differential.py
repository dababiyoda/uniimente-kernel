"""Differential test of developmental/bff.py against the CuBFF binary (commit f212e849, built with `make CUDA=0`).

    python tests/evidence/bff-reference-2026-11-22/differential/differential.py CUBFF_SRC HARNESS OUT.json

CUBFF_SRC is a CuBFF checkout at f212e849027c98fcf4b242eccfb5fed435223e23 with bin/main built; HARNESS is
harness.cc from this directory compiled against it (see README.md). Neither is committed here. The script:

1. runs `bin/main --lang bff_noheads --num 1024 --seed S --max_epochs 257 --save_interval 64` for S in {0, 1} and
   compares every checkpoint's soup bytes with developmental.bff.Soup(1024, seed=S) stepped to the header's epoch;
2. runs 800 tapes through CuBFF's own Bff::Evaluate (via the harness) and developmental.bff.evaluate, and compares
   final tapes and operation counts;
3. scores 64 soup programs and 50 programs that CuBFF scores above zero with CuBFF's CheckSelfRep
   (Simulation<Bff>::EvalParsedSelfrep) and developmental.bff.selfrep_score.

It records what it observes. It never edits either side to make them agree.
"""
import hashlib
import json
import os
import random
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from developmental import bff  # noqa: E402

src, harness, out = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
sha = lambda b: hashlib.sha256(b).hexdigest()  # noqa: E731


def harness_run(lines):
    return subprocess.run([harness], input="".join(lines), capture_output=True, text=True, check=True).stdout.split("\n")


# 1. soup checkpoints
soups, checkpoints = {}, []
for seed in (0, 1):
    d = Path(tempfile.mkdtemp())
    subprocess.run([str(src / "bin/main"), "--lang", "bff_noheads", "--num", "1024", "--seed", str(seed),
                    "--max_epochs", "257", "--save_interval", "64", "--checkpoint_dir", str(d), "--disable_output"],
                   check=True)
    soup = bff.Soup(1024, seed=seed)
    for f in sorted(d.glob("*.dat")):
        raw = f.read_bytes()
        reset_index, num, epochs = struct.unpack("<3Q", raw[:24])
        cubff = raw[24:]
        while soup.epoch < epochs:
            soup.step()
        py = bytes(soup.programs)
        checkpoints.append({"seed": seed, "file": f.name, "header": {"reset_index": reset_index, "num_programs": num,
                            "epochs_completed": epochs}, "cubff_sha256": sha(cubff), "python_sha256": sha(py),
                            "match": cubff == py, "differing_bytes": sum(a != b for a, b in zip(cubff, py))})
        print(json.dumps(checkpoints[-1]), flush=True)
        soups[seed] = cubff

# 2. single tapes
rng = random.Random(20261122)
alphabet = b"[]+-.,<>{}\x00"
cases = [("uniform", bytes(rng.randrange(256) for _ in range(128))) for _ in range(300)]
cases += [("instruction-heavy", bytes(rng.choice(alphabet) for _ in range(128))) for _ in range(300)]
for seed in (0, 1):
    for _ in range(100):
        a, b = rng.randrange(1024), rng.randrange(1024)
        cases.append((f"soup-seed{seed}-epoch321-pair", soups[seed][a * 64:a * 64 + 64] + soups[seed][b * 64:b * 64 + 64]))
tapes = []
for (kind, tape), line in zip(cases, harness_run(f"E {t.hex()}\n" for _, t in cases)):
    cubff_final, cubff_ops = line.split()
    py = bytearray(tape)
    py_ops = bff.evaluate(py)
    tapes.append({"kind": kind, "input_hex": tape.hex(), "cubff_final_sha256": sha(bytes.fromhex(cubff_final)),
                  "python_final_sha256": sha(bytes(py)), "cubff_ops": int(cubff_ops), "python_ops": py_ops,
                  "match": cubff_final == py.hex() and int(cubff_ops) == py_ops})

# 3. CheckSelfRep. CuBFF's EvalParsedSelfrep(program, epoch, seed) uses seed SplitMix64(SplitMix64(seed) ^
# SplitMix64(epoch)) with one program at index 0, which is bff.Soup(..., seed=seed).stream(epoch), n=1, index=0.
selfrep_cases = []
for seed in (0, 1):
    for _ in range(32):
        i = rng.randrange(1024)
        selfrep_cases.append(("soup-epoch321", seed, rng.randrange(1, 10000), soups[seed][i * 64:i * 64 + 64]))
hunt, cores = random.Random(7), [b"[[{.>]-]", b"[[{.>]-]]-]>.{[[", b"[{.>]", b"[<,}]", b"[[{.>]-]]-]>.{[["]
pool = []
for _ in range(20000):
    core = hunt.choice(cores)
    zero_pad = hunt.choice([True, False])
    rest = bytes(64 - len(core)) if zero_pad else bytes(hunt.randrange(256) for _ in range(64 - len(core)))
    p = bytearray(core + rest)
    for _ in range(hunt.randrange(4)):
        p[hunt.randrange(64)] = hunt.choice(alphabet)
    if hunt.random() < 0.5:
        p = p[::-1]
    pool.append((hunt.randrange(4), hunt.randrange(1, 5000), bytes(p)))
scored = [(int(c), s, e, p) for c, (s, e, p) in zip(harness_run(f"S {p.hex()} {s} {e}\n" for s, e, p in pool), pool)]
positive = [x for x in scored if x[0] > 0]
hunt.shuffle(positive)
picked = sorted(positive, key=lambda x: -x[0])[:20] + positive[:30]
selfrep_cases += [("hunted-nonzero", s, e, p) for _, s, e, p in picked]
selfrep = []
for (kind, seed, epoch, prog), c in zip(selfrep_cases, harness_run(f"S {p.hex()} {s} {e}\n" for _, s, e, p in selfrep_cases)):
    py = bff.selfrep_score(prog, seed=bff.Soup(2, seed=seed).stream(epoch), n=1, index=0)
    selfrep.append({"kind": kind, "cubff_seed": seed, "epoch": epoch, "program_hex": prog.hex(),
                    "cubff_score": int(c), "python_score": py, "match": int(c) == py})

result = {"cubff": {"repository": "https://github.com/paradigms-of-intelligence/cubff",
                    "commit": "f212e849027c98fcf4b242eccfb5fed435223e23", "build": "make CUDA=0"},
          "summary": {"checkpoints": len(checkpoints), "checkpoint_mismatches": sum(not r["match"] for r in checkpoints),
                      "tapes": len(tapes), "tape_mismatches": sum(not r["match"] for r in tapes),
                      "selfrep": len(selfrep), "selfrep_mismatches": sum(not r["match"] for r in selfrep)},
          "checkpoints": checkpoints, "tapes": tapes, "selfrep": selfrep}
out.write_text(json.dumps(result, indent=1) + "\n")
print(json.dumps(result["summary"]))
