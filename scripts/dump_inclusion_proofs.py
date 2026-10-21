"""Dump Kernel inclusion proofs for every index of trees 1..129 as JSON.

Input for scripts/sigstore_inclusion_oracle.cjs, which re-verifies them with
Sigstore's shipped RFC 6962 verifier (@sigstore/verify dist/tlog/merkle.js).
"""
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from provenance.proof import MerkleTree  # noqa: E402

hashes = ["sha256:" + hashlib.sha256(f"oracle-{i}".encode()).hexdigest() for i in range(130)]
cases = []
for n in range(1, 130):
    tree = MerkleTree(hashes[:n])
    for index in range(n):
        proof = tree.prove(hashes[index])
        cases.append({"n": n, "index": index, "leaf": hashes[index],
                      "hashes": [step.sibling for step in proof.steps], "root": tree.root})
print(json.dumps(cases))
