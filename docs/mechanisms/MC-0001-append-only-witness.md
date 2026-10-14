# MC-0001 — Witnessed append-only checkpoints

Status: **experiment — capability built and tested; not attached to any live path.**
Founder lineage: directive of 2026-10-13, §4–§5 (REA mechanism extraction and recombination), §17 cases 11, 32 and 41 (self-consistent forged receipt, obsolete implementation silently becoming authoritative, an improvement that destroys reconstruction of prior decisions).
Evidence: `tests/evidence/append-only-witness-20261014/`.

## 1. Residual CapabilityDeficit

`provenance/proof.py` proves that a record is included in a committed Merkle root. Two things were missing:

- **No append-only proof.** Nothing proved that a later checkpoint extends an earlier one. A host that rewrites record *k*, rebuilds the hash chain and re-checkpoints gets a valid chain, a valid root and valid inclusion proofs. The test `test_existing_inclusion_proofs_cannot_detect_a_rewritten_history` reproduces this.
- **The verifier still trusts the host.** The root an auditor checks against is published by the host, on the host's own ledger. `closure/kernel_registry.py` says "no trust in the ledger host, ever". That holds for inclusion against a root the auditor already trusts. It does not hold for where that root comes from.

Searched first, and found absent: all 164 remote Kernel branches had no consistency-proof or cosigning implementation. The existing primitives (hash chain, inclusion proofs, HMAC commit witness) are reused.

## 2. REA investigation (real run)

| Item | Value |
|---|---|
| Tool | `rea-agents@6.1.0` (npm integrity `sha512-xsXFiXEt…CnI7Q==`; same version as the `REA-Reverse-Engineering-Anything` fork) |
| Operation | `analyze-javascript-application <dir> --json` |
| Target | `@sigstore/verify@4.1.2` shipped npm tarball: Apache-2.0, sha1 `d4521f0d…0ae9`, sha256 `d0dc6eb9…28b5` |
| Rights | Apache-2.0 public package. Static analysis of the published artifact only. No DRM, authentication or access control involved. |
| Evidence ID | `ev_8c44d0826b64a4af3441a42d898ad0be5b97a244b3d42d1e5010b3d34d0834af` |
| Bundle | `rea/rea-sigstore-verify.json.gz`. Uncompressed sha256 `a754b4c8…96c1`, 245 nodes, 412 edges, coverage `complete`. |
| Subgraph | `rea/tlog-extract.json`: 30 `dist/tlog/*` nodes and their import/export edges |
| REA's own limits | Inert parse only; nothing was executed. Static imports do not prove runtime execution. Dynamic paths may be unresolved. |

**Why REA and not only source reading.** The question was what the **distributed artifact** that consumers actually execute enforces, not what the upstream repository intends. REA reconstructed the shipped module graph `verifier.js → tlog/index.js → {checkpoint.js, merkle.js, set.js, body verifiers}`. That pointed reading at `checkpoint.js` (sha256 `b4881c6a…b6d`) and `merkle.js` (`2874340d…ff3`).

**Observed in the shipped code** (static reading, not runtime proof):
- `verifySignedNote` returns `signatures.some(...)`. One verifying signature from any trusted log key is enough, and extra cosignatures are not required.
- `verifyMerkleInclusion` uses RFC 6962 inner/border decomposition, checks the hash count and binds the proof to the checkpoint root.
- `checkpoint.js` and `merkle.js` contain no consistency-proof verification. Append-only checking between checkpoints is left to monitors and witnesses outside this package.

## 3. Mechanism Card (donor: transparency-log checkpoint verification)

1. **Source identity and digest.** `@sigstore/verify@4.1.2`, `dist/tlog/checkpoint.js`, `dist/tlog/merkle.js` (digests above).
2. **Primitive operation.** Accept a log statement when a signature from a trusted key covers (origin, size, root), and when a leaf hashes up to that root.
3. **State maintained.** The verifier keeps none beyond the trusted key set. The log keeps the leaf sequence.
4. **Input / output.** Input: entry, inclusion path and signed note. Output: accept, or throw `VerificationError`.
5. **Transition rules.** Parse the note, verify a signature, check the root against the inclusion path. Any failure rejects.
6. **Actors / beneficiaries.** Log operator, signer and relying verifier. The relying party benefits.
7. **Authority boundary.** Whoever holds a trusted log key. Log and signer are the same party.
8. **Hidden / visible information.** The verifier sees only the size, the root and its path. The rest of the log is hidden.
9. **Resources.** O(log n) hashes per check and one signature verification.
10. **Incentives.** The operator is trusted not to equivocate. Misbehaviour is caught only by external monitors.
11. **Feedback.** None inside the verifier.
12. **Failure mode.** A compromised or colluding log key can present different histories to different verifiers (split view). The verifier cannot tell.
13. **Recovery mode.** Outside the package (monitors, key rotation).
14. **Proof emitted.** Inclusion against a signed root.
15. **Causal invariant.** A leaf is in the tree the signer committed to.
16. **Mission geometry.** Any "did this record exist under that commitment" question.
17. **Adaptation opportunity.** Separate the signer from the log, require several signers, and make each signer check that the log only grows.
18. **Limits / uncertain claims.** Static reading does not show how upstream Sigstore monitors and witnesses are deployed. This card claims nothing about Sigstore's overall ecosystem security.

**Without product names:** *a short, signed commitment to an ordered set lets anyone check membership cheaply, but only as honestly as the single signer is.*

## 4. Mutations

| # | Operator | Original behaviour | Resulting behaviour | Invariant retained | New capability | New failure introduced |
|---|---|---|---|---|---|---|
| M1 | Authority separation | The log's own key makes a checkpoint acceptable | Origin signatures count for nothing. Only distinct witnesses count. | Commitment = (origin, size, root) | The host cannot self-certify | Liveness now depends on witnesses being reachable |
| M2 | Any-one → quorum (incentive/authority change) | `some()`: one trusted signature suffices | k-of-n distinct registered witnesses. Duplicates, unknown signers and copies count once or not at all. | Signatures cover the canonical note | No single compromised party can certify a fork | k must be tuned. A quorum of fresh witnesses is trust-on-first-use. |
| M3 | Failure-to-learning conversion | A bad statement is rejected and forgotten | A witness refuses to cosign anything that doesn't provably extend what it saw, and keeps `SplitViewEvidence` | Rejection is fail-closed | Refusals become reviewable evidence of attempted rewrites | Storage for refusals. HMAC evidence is not publicly transferable. |
| M4 | Source-of-truth replacement (added primitive) | Verifier trusts the latest signed root | Verifier carries (size, root) forward and demands an RFC 9162 consistency proof | RFC 6962 tree shape (Kernel roots unchanged) | Append-only check with O(1) auditor state | Proofs bind roots, not sizes. Sizes are bound by the cosigned note. |

M1 and M2 change authority and incentives, not only an interface.

## 5. Candidates (raw → selected)

| # | Candidate | Verdict |
|---|---|---|
| 1 | Witnessed append-only checkpoints (M1–M4) | **Selected.** Closes a reproduced deficit. Measurable against baselines. |
| 2 | Kernel ledger publishes roots to the public Rekor log | Rejected for now: an external effect, which needs founder authority |
| 3 | Inclusion proofs only, plus more frequent checkpoints | Rejected: still 0% detection (baseline B0) |
| 4 | Full-copy mirroring by every organ | Kept as baseline B1: detects everything, but state grows O(n) |
| 5 | Cross-organ mutual witnessing (WMI ↔ DALEOBANKS ↔ Kernel) | Folded into #1 as the deployment shape. Organ wiring is deferred. |
| 6 | Evidence-tier certificates transported across organs | Deferred. Depends on #1 for an append-only substrate. |
| 7 | Solver certificate cross-checking via transparency | Rejected here: a different deficit (#161 lineage) |
| 8 | Time-stamped checkpoints using RFC 3161 TSA (`dist/timestamp`) | Rejected: adds an external dependency. Doesn't address rewrite. |
| 9 | SET (signed entry timestamp) promise model | Rejected: weaker than inclusion. Promises rather than proves. |
| 10 | Gossip of checkpoints among relying parties | Deferred: needs network transport. The witness already covers the core. |
| 11 | Merkle "refusal ledger" scoring witness reliability | Rejected: the incentive design has no measured need yet |
| 12 | Replace the HMAC witness with Ed25519 public cosignatures | Deferred: needs a dependency decision (`cryptography` is not a Kernel requirement). Drop-in for `_mac`. |

## 6. Strengthening rounds

**Round 1: transmute constraints.**
- The HMAC-only constraint became per-witness keys plus a registry that counts each witness once. Copied or forged signatures fail (`test_one_witness_counts_once_and_forgeries_fail`).
- The no-new-tree constraint became a check that the Kernel's existing tree is RFC 6962-shaped (roots identical for n=1..299). No checkpoint migration is needed.
- The "trust the host" constraint was converted by rule M1.

**Round 2: higher-order capability, then attack it.**
- Higher order: Kernel inclusion proofs are now verifiable by external standard tooling. Sigstore's shipped verifier accepted 8,385 of 8,385 Kernel proofs and rejected 8,385 of 8,385 tampered leaves. Organs or counterparties can audit Kernel evidence without running Kernel code.
- New fragilities found:
  - Sizes are not bound by the consistency proof. This was found by a failing test, now documented and covered by `test_sizes_are_bound_by_the_signed_note_not_the_proof`.
  - First-use trust.
  - A quorum of fresh witnesses accepts a fork.
  - In-memory witness state.

  All are recorded as genome failure modes.

## 7. Comparison (frozen seed 20261014, 400 trials, logs of 4–1,200 records)

| Arm | Detection of rewrites | Honest growth accepted | Mean auditor state | Mean transfer | Mean time |
|---|---|---|---|---|---|
| B0 existing Kernel (inclusion + chain) | **0 / 211** | 189 / 189 | 40 B | 332 B | 1.55 ms |
| B1 simplest: full-copy prefix compare | 211 / 211 | 189 / 189 | 22,353 B | 43,054 B | **0.01 ms** |
| B2 donor: any one trusted signature | **0 / 211** | 189 / 189 | 40 B | 108 B | 0.03 ms |
| **NEW: 2-of-3 witness quorum** | **211 / 211** | 189 / 189 | **40 B** | 607 B | 1.84 ms |

Verdict:
- NEW strictly dominates B0 and B2 on detection, with no false rejections.
- Against the simplest full-detection baseline (B1), NEW ties on detection and uses about 560× less auditor state and about 71× less transfer at these sizes. The gap grows linearly with log length.
- NEW is slower on CPU. Its timing includes host-side proof generation in pure Python.
- NEW wins only where state and bandwidth matter: many witnesses, long logs, cross-organ auditing. For a single local auditor with a small log, B1 is the simpler choice.

**Holdout.** `test_randomized_split_view_campaign` uses a different seed and a pool of up to 2,000 leaves: 300 random cases, every attack refused, every honest extension cosigned. Exhaustive checks:
- every honest proof for m ≤ n ≤ 64;
- every rewrite position for n ≤ 32;
- every single-hash corruption for n ≤ 32.

## 8. Negative results and limits (retained)

- The test expecting `(old, new+1)` relabelling to fail was wrong. RFC 9162 verification binds roots, not sizes. The test was corrected, not deleted.
- HMAC cosignatures are not publicly verifiable.
- Witness state is in memory.
- No live witness is deployed.
- The organs (WMI, DALEOBANKS) are not wired to cosign. This is building, not installation or activation.
- The REA findings are static inference from the shipped artifact. They are not runtime proof of Sigstore behaviour.

## 9. Authority

Read-only capability: no external effects, no budget, no new grants. `QuorumPolicy` decides only whether a checkpoint counts as witnessed. It does not authorize consequences. To detach, stop consulting it. Inclusion proofs and chain verification are unchanged.
