# Cross-organ mission — evidence (2026-10-14)

Run: `python scripts/cross_organ_mission.py --daleobanks <dir> --daleobanks-python <py> --wealthmachine <dir> --wealthmachine-python <py> --out <dir>` → `RESULT: PASS` (`run.log`).

| Process | Checkout | Code exercised |
|---|---|---|
| DALEOBANKS | `a8b00b9` (branch `claude/measurement-truth-repairs`, DALEOBANKS PR #89) | `IdeaRefinery.intake/refine` → `packet_to_wire` → `bridge_transport.build_headers` |
| WealthMachineIntelligence | `ec82b80` (`main`) | `verify_headers` → `OpportunityIntakeService.evaluate_packet` → signed report to the Kernel |
| Kernel | this branch | `verify_headers` (both), canonical adapters, `EventSpine` on a persisted `EvidenceLedger`, appraisal, checkpoints |
| Witnesses | Kernel `provenance/witness.py`, run inside each organ's interpreter with that organ's key and durable state file | cosign / refuse |

Results (`mission-result.json`):
- Trace from retained ledger evidence: `signal_observed → opportunity_adapted → assessment_adapted → assessment_appraised`, then an open obligation. Chain intact (8 records).
- The adapter left `governing_bottleneck` unresolved. It is kept as an open obligation, not answered by the harness.
- Appraisal: a fresh WealthMachine process re-derived the same verdict, score, risk, readiness, plan and reasons from the same signed packet. All five Kernel invariants held. Tier: multi-process reproduction plus invariant check. **Not external acceptance.**
- Witnessing: both organs cosigned the baseline (first use) and the post-episode checkpoint (consistency proof, not first use). The 2-of-2 quorum accepted.
- Attacks, all refused:
  - packet replay (nonce);
  - tampered assessment (signature);
  - equivocating checkpoint at the same size (both witnesses);
  - rewritten and extended history (both witnesses: no valid append-only proof).
- External effects: none. Spend: none (no paid calls). Founder approval: pending. Nothing was executed in the world.

Files in `work/`: the Kernel ledger, each organ's witness state (no keys), and the DALEOBANKS decision ledger. The bridge key and witness keys were random per run and never written.

Limits:
- The bridge transport uses one shared HMAC key for all organs, so it authenticates "a holder of the bridge key", not a specific organ.
- Witness cosignatures are HMAC, so the quorum verifier holds the witness keys.
- Reproduction shows determinism, not correctness.
