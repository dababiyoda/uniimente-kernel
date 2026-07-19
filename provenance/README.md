# provenance

Layers 3+10 — Time machine: state history, belief history, authority
history, the append-only hash-chained Evidence Ledger, and the Commit
Witness. Signed receipts for high-consequence records.

## Files

- `ledger.py` — `EvidenceLedger`: append-only, hash-chained (each record
  carries its predecessor's hash), genesis anchored to the constitution
  hash. `verify_chain()` independently reconstructs and verifies every
  link. Corrections are new records with correction ancestry; negative
  evidence is never deleted. Optional JSONL persistence with
  verify-on-load (a corrupted store refuses to load).
- `commit_witness.py` — `CommitWitness` + `WitnessSigner`: binds
  authorization to the exact payload, exact target, policy version,
  constitution version, current authority, current capability, current
  budget, and expected outcome. HMAC-SHA256 signed. Proof remains valid
  even if the original model disappears.

## The proof sentence

> This exact machine, acting for this exact entity, received this exact
> permission, under this exact law, using this exact evidence, to create
> this exact result.

## Buildability standard (14 conditions)

- **Existing mechanism**: hash-chained append-only log + HMAC signatures (Git/blockchain primitives, no token).
- **Defined interface**: `append/verify_chain/seal/find/by_type`; `sign/verify/new_witness`.
- **Bounded authority**: records only; cannot authorize or execute.
- **Available dependencies**: Python 3 stdlib only.
- **Security model**: tamper-evident chain; signatures verified at commit; key from environment; corrupted persistence refuses to load.
- **Failure modes**: chain break, payload hash mismatch, sequence break, signature forgery — all detected, all terminal.
- **Acceptance tests**: `tests/unit/test_provenance.py`.
- **Recovery path**: rebuild by replay; seal marks shutdown propagation; corrections never rewrite history.
- **Resource ceiling**: append O(1); verify O(n) on demand; JSONL growth bounded by event rate.
- **Operating cost**: one SHA-256 per record; negligible.
- **Legal operator**: records attach to the legal principal of the originating action.
- **Handoff state**: the ledger IS the handoff state; verify-on-load proves integrity.
- **Replaceable**: storage backend swappable (memory/JSONL/Postgres later); the hash chain is the invariant.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `evidence_ledger`.
