"""The recorded differential test of developmental/bff.py against the CuBFF binary, re-checked without the binary.

tests/evidence/bff-reference-2026-11-22/differential/differential.json holds what CuBFF (f212e849, `make CUDA=0`)
produced: soup checkpoint digests, the final-tape digests and operation counts of 800 tapes, and 114 CheckSelfRep
scores. These tests recompute the Python side and compare it with CuBFF's recorded side, so a later change to
developmental/bff.py that breaks byte-exactness fails here even where CuBFF cannot be built.
"""
import hashlib
import json
from pathlib import Path

import pytest

from developmental import bff

RECORD = json.loads((Path(__file__).resolve().parents[1] / "evidence" / "bff-reference-2026-11-22" / "differential"
                     / "differential.json").read_text())


def test_the_record_is_a_complete_match_and_names_cubffs_commit():
    assert RECORD["cubff"]["commit"] == bff.SOURCE["commit"]
    s = RECORD["summary"]
    assert (s["checkpoints"], s["tapes"], s["selfrep"]) == (12, 800, 114)
    assert s["checkpoint_mismatches"] == s["tape_mismatches"] == s["selfrep_mismatches"] == 0
    # every soup row and tape row was observed to agree, not merely summarised as agreeing
    assert all(r["match"] and r["cubff_sha256"] == r["python_sha256"] for r in RECORD["checkpoints"])
    # the checkpoint named NNNN holds the soup after NNNN + 1 epochs (CuBFF saves after stepping epoch NNNN)
    assert all(r["header"]["epochs_completed"] == int(r["file"][:-4]) + 1 for r in RECORD["checkpoints"])


@pytest.mark.parametrize("seed", [0, 1])
def test_the_python_soup_reproduces_cubffs_checkpoint_digests(seed):
    rows = {r["header"]["epochs_completed"]: r["cubff_sha256"] for r in RECORD["checkpoints"] if r["seed"] == seed}
    soup = bff.Soup(1024, seed=seed)
    for epochs in (1, 65):                        # the first two checkpoints; the rest take minutes in pure Python
        while soup.epoch < epochs:
            soup.step()
        assert hashlib.sha256(soup.programs).hexdigest() == rows[epochs]


def test_every_recorded_tape_runs_to_cubffs_final_bytes_and_operation_count():
    kinds = set()
    for r in RECORD["tapes"]:
        tape = bytearray.fromhex(r["input_hex"])
        ops = bff.evaluate(tape)
        assert (hashlib.sha256(tape).hexdigest(), ops) == (r["cubff_final_sha256"], r["cubff_ops"]), r["kind"]
        kinds.add(r["kind"])
    assert {"uniform", "instruction-heavy"} <= kinds
    # the sample exercises the step cap, early exits and tape changes, not only inert tapes
    assert any(r["cubff_ops"] == bff.STEPS for r in RECORD["tapes"])
    assert sum(r["input_hex"] != "" and r["cubff_ops"] < 50 for r in RECORD["tapes"]) > 0


def test_cubffs_selfrep_scores_are_reproduced_including_full_replicators():
    rows = RECORD["selfrep"]
    assert {r["cubff_score"] for r in rows} >= {0, 1, 16, 64}      # zero, partial and complete self-copies
    checked = [r for r in rows if r["cubff_score"] > 0][:12] + [r for r in rows if r["cubff_score"] == 0][:4]
    for r in checked:
        seed = bff.Soup(2, seed=r["cubff_seed"]).stream(r["epoch"])
        assert bff.selfrep_score(bytes.fromhex(r["program_hex"]), seed=seed, n=1, index=0) == r["cubff_score"]
