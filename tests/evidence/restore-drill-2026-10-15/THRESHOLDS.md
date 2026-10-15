# Restore drill thresholds — declared before the drill (directive section 14)

Section 14: "Choose recovery-time, recovery-point, detection, containment, duplicate-effect, and authority-continuity
thresholds before testing. State the environment and failures covered." This file is committed before the
mechanism and before any drill run. The drill passes only if every row holds. A threshold is never relaxed after
a run; a miss is recorded as a miss.

## Failure covered

The body's machine is lost. All that remains:
- an Institutional Seed taken earlier with `greg foundry seed`;
- the founder's own key.

The original body may have kept running after the seed was taken. Whether it is now gone is unknown to the
restored copy, and only the founder can declare it.

## Environment

- **Machine:** one Linux container (this session).
- **The body:** a real GREG body, with its real ledger, real Ed25519 test keys and the real mission engine.
- **Clocks:** fake in-process clocks for the authority cases, the wall clock for the timed drill.
- **Not covered:** physical devices, a second living machine, network partitions and external services.

## Thresholds

| Kind | Threshold |
|---|---|
| Recovery time (RTO) | Restore, verification and first boot of a body with at least 200 ledger records finish in **at most 60 s** on this machine, measured by the wall clock. |
| Recovery point (RPO) | The recovery point is the seed's own recorded backup time. Everything after it is **unknown to the restored body and reported as such**. No claim about it is made, and nothing after it is reconstructed or guessed. |
| Detection | A tampered seed object, a tampered manifest, or a restored ledger whose chain or head differs from the head the seed recorded is **refused before the body opens**: 0 tampered restores boot. |
| Containment | The restored body takes **0 actions** until a founder command issued after the restore releases it. |
| Duplicate effect | **0** commands issued before the restore are accepted by the restored body. **0** approvals granted before the restore authorize an action there: the action is asked again. |
| Authority continuity | **0** device delegations made before the restore are usable on the restored body, so a revocation the original applied after the backup cannot be lost. The restore hold is released only by the founder key. The founder key enrolled at the recovery point is the only founder key trusted; a rotation after the recovery point is a **stated, unmet limit**. |
| Revocation persistence | A device revoked before the backup stays revoked; a device revoked after the backup is also unusable. |

## Stated limits (not thresholds)

- **The founder's declaration:** GREG cannot detect a second living copy of the same body without an external
  anchor. The founder's release of the hold is the declaration that the original is gone.
- **External consequences:** for an action the original may have taken after the recovery point, the restored
  body re-asks; it does not reconcile with the external system.
