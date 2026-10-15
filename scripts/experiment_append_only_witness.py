"""Compare witnessed append-only checkpoints against the strongest baselines.

Attack: the ledger host rewrites one record already covered by a checkpoint
an auditor has seen, rebuilds a valid chain and checkpoint, and presents it.
Honest control: the host only appends.

Arms (same frozen seed, same cases for every arm):
  B0 no change  - existing Kernel: auditor keeps the old root and checks
                  inclusion proofs + chain validity of what it is shown.
  B1 simple     - auditor keeps a full copy of the old records and
                  compares the prefix of the new log (static workflow).
  B2 donor      - Sigstore-style acceptance: any one trusted signature;
                  the host's own checkpoint key is trusted.
  NEW           - auditor keeps (size, root); 2-of-3 witness quorum; each
                  witness cosigns only with a valid consistency proof.

Usage: python scripts/experiment_append_only_witness.py [out.json]
"""
from __future__ import annotations

import hashlib
import hmac
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from provenance.consistency import merkle_root, prove_consistency  # noqa: E402
from provenance.proof import MerkleTree, verify_inclusion  # noqa: E402
from provenance.witness import Checkpoint, QuorumPolicy, Witness, WitnessRefused  # noqa: E402

SEED = 20261014
TRIALS = 400
HASH_BYTES = 71  # len("sha256:" + 64 hex)


def _h(tag: str) -> str:
    return "sha256:" + hashlib.sha256(tag.encode()).hexdigest()


def run(trials: int = TRIALS, seed: int = SEED) -> dict:
    rng = random.Random(seed)
    host_key = b"host-checkpoint-key"
    keys = {"wmi": b"k-wmi", "daleobanks": b"k-dale", "auditor": b"k-aud"}
    arms = {a: {"attacks": 0, "attacks_detected": 0, "honest": 0, "honest_accepted": 0,
                "auditor_state_bytes": 0, "bytes_transferred": 0, "seconds": 0.0}
            for a in ("B0_no_change", "B1_full_copy", "B2_donor_any_one", "NEW_witness_quorum")}

    for t in range(trials):
        m = rng.randint(4, 600)
        n = m + rng.randint(1, 600)
        log = [_h(f"{t}-{i}") for i in range(n)]
        attack = rng.random() < 0.5
        if attack:
            log[rng.randrange(m)] = _h(f"forged-{t}")
        old = [_h(f"{t}-{i}") for i in range(m)]
        old_root = merkle_root(old)
        new_root = merkle_root(log)

        def record(arm, detected, start, state, moved):
            a = arms[arm]
            a["seconds"] += time.perf_counter() - start
            a["auditor_state_bytes"] += state
            a["bytes_transferred"] += moved
            if attack:
                a["attacks"] += 1
                a["attacks_detected"] += int(detected)
            else:
                a["honest"] += 1
                a["honest_accepted"] += int(not detected)

        # B0: inclusion proofs of everything shown verify against the new root.
        start = time.perf_counter()
        tree = MerkleTree(log)
        probe = rng.randrange(n)
        proof = tree.prove(log[probe])
        detected = not (verify_inclusion(proof) and proof.root == new_root)
        record("B0_no_change", detected, start, 32 + 8, len(proof.steps) * 32 + 32)

        # B1: full prefix comparison.
        start = time.perf_counter()
        detected = log[:m] != old
        record("B1_full_copy", detected, start, m * HASH_BYTES, n * HASH_BYTES)

        # B2: host signs its own checkpoint; verifier needs any one trusted signature.
        start = time.perf_counter()
        note = f"kernel\n{n}\n{new_root}\n".encode()
        sig = hmac.new(host_key, note, hashlib.sha256).digest()
        detected = not hmac.compare_digest(sig, hmac.new(host_key, note, hashlib.sha256).digest())
        record("B2_donor_any_one", detected, start, 32 + 8, len(note) + 32)

        # NEW: witnesses that saw (m, old_root) must cosign; quorum 2 of 3.
        start = time.perf_counter()
        witnesses = [Witness(w, k) for w, k in keys.items()]
        for w in witnesses:
            w.cosign(Checkpoint("kernel", m, old_root))
        cp = Checkpoint("kernel", n, new_root)
        cproof = prove_consistency(log, m)
        for w in witnesses:
            try:
                w.cosign(cp, cproof)
            except WitnessRefused:
                pass
        accepted, _ = QuorumPolicy(keys, threshold=2).accepts(cp)
        record("NEW_witness_quorum", not accepted, start, 32 + 8,
               len(cproof.path) * 32 + len(cp.note) + 3 * 77)

    for a in arms.values():
        a["detection_rate"] = round(a["attacks_detected"] / a["attacks"], 4) if a["attacks"] else None
        a["honest_acceptance_rate"] = round(a["honest_accepted"] / a["honest"], 4) if a["honest"] else None
        a["mean_auditor_state_bytes"] = round(a["auditor_state_bytes"] / trials, 1)
        a["mean_bytes_transferred"] = round(a["bytes_transferred"] / trials, 1)
        a["mean_ms"] = round(1000 * a["seconds"] / trials, 4)
        for k in ("auditor_state_bytes", "bytes_transferred", "seconds"):
            del a[k]
    return {"seed": seed, "trials": trials, "log_sizes": "old 4..600, growth 1..600",
            "attack": "rewrite one record covered by the auditor's last checkpoint",
            "arms": arms}


if __name__ == "__main__":
    result = run()
    text = json.dumps(result, indent=2)
    if len(sys.argv) > 1:
        Path(sys.argv[1]).parent.mkdir(parents=True, exist_ok=True)
        Path(sys.argv[1]).write_text(text + "\n")
    print(text)
