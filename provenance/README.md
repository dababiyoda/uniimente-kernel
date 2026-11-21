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
- `recovery.py` — `recover_torn_tail(path, constitution_hash, recovered_by=, reason=, expected_head=None,
  acknowledged_risks=())`: the explicit, accountable repair for a ledger whose last line was torn by a crash
  mid-append. Holding the writer lock throughout, it verifies every complete line in memory and accepts only a
  tail one interrupted append can leave: a byte prefix of the next record's line as the writer serializes it, NUL
  padding, or a zero-filled run. Anything else is refused, including a fork, a foreign field, control bytes and a
  NUL hole inside the content.

  Before touching the ledger it writes the torn bytes to `<ledger>.torn-<16 hex of the prior head>-<sha256>` and a
  `.json` sidecar holding the exact `ledger.torn_tail_quarantined` event line to apply. Both writes are atomic and
  durable. It then applies that plan in place: the event over the torn bytes, a cut to its length, then the
  newline, with an fsync after each step. The file never ends with a newline until the event is durable, so no
  restarting writer can append before the repair is recorded, and a later call completes a plan that a crash
  interrupted.

  A torn append never returned to its caller, so it is quarantined and never re-admitted. Risks a byte check cannot
  exclude must be acknowledged by name:
  - `unanchored`: no `expected_head` was given;
  - `complete_record`: the record's hash was written, so a checkpoint cannot tell it from one acknowledged and
    damaged later;
  - `stop_record`: the torn bytes show a seal, suspension, founder control, capability detach, goal revocation,
    supersession or pause, or a stop-like event, which must be re-issued.

  Quarantine files this chain does not record are reported, never chained. Opening a torn ledger still fails
  closed, and nothing calls recovery automatically. Tests: `tests/unit/test_ledger_recovery.py`,
  `tests/integration/test_ledger_recovery_kill.py`.
- `proof.py` — Merkle inclusion proofs (Layer 10): `LedgerProver.
  checkpoint()` anchors a Merkle root over all prior record hashes in a
  ledger checkpoint record; `prove()/verify()` give O(log n) inclusion
  proofs for any committed record against that root — verification needs
  only root + proof, never trust in the ledger host. Domain-separated
  hashing (leaf/node prefixes); odd leaves promote, never duplicate.
  Tampering with any committed record fails its proof.

## The proof sentence

> This exact machine, acting for this exact entity, received this exact
> permission, under this exact law, using this exact evidence, to create
> this exact result.

## Buildability standard (14 conditions)

- **Existing mechanism**: hash-chained append-only log + HMAC signatures (Git/blockchain primitives, no token).
- **Defined interface**: `append/verify_chain/seal/find/by_type`; `sign/verify/new_witness`; `recover_torn_tail`.
- **Bounded authority**: records only; cannot authorize or execute.
- **Available dependencies**: Python 3 stdlib only.
- **Security model**: tamper-evident chain; signatures verified at commit; key from environment; corrupted persistence refuses to load.
- **Failure modes**: chain break, payload hash mismatch, sequence break, signature forgery — all detected, all terminal.
- **Acceptance tests**: `tests/unit/test_provenance.py`; `tests/unit/test_ledger_recovery.py` (torn-tail recovery).
- **Recovery path**: rebuild by replay; seal marks shutdown propagation; corrections never rewrite history; a torn final line from a crash mid-append is quarantined and replaced in place by a chained record of the recovery (`recover_torn_tail`), never re-admitted.
- **Resource ceiling**: append O(1); verify O(n) on demand; JSONL growth bounded by event rate.
- **Operating cost**: one SHA-256 per record; negligible.
- **Legal operator**: records attach to the legal principal of the originating action.
- **Handoff state**: the ledger IS the handoff state; verify-on-load proves integrity.
- **Replaceable**: storage backend swappable (memory/JSONL/Postgres later); the hash chain is the invariant.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `evidence_ledger`.
