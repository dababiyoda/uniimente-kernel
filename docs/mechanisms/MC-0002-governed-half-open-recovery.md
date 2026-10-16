# MC-0002 — Governed half-open recovery

Status: **experiment.** The capability is built and tested on a body. It is not attached to any live path.
Machine-readable card: `MC-0002-governed-half-open-recovery.json`. It carries all twenty directive fields; `tests/integration/test_greg_capability_recovery.py` checks that the card stays complete.
Evidence: `docs/evidence/greg-recovery/2026-10-14/`.

## Residual CapabilityDeficit

A capability quarantined for an in-service fault never returned without the founder. If every provider for a function was quarantined by transient faults, the function was lost, and missions escalated even after the fault had cleared. The nearest precursor in GREG is route demotion with a cooldown in `greg/models.py`, which covers model routes only.

## REA investigation (real run)

| Item | Value |
|---|---|
| Tool | `rea-agents@6.1.0`, run via `npx` with install scripts disabled |
| Operation | `analyze-javascript-application <dir> --json` |
| Target | `opossum@10.0.0` published tarball. Apache-2.0. Tarball sha256 `6bc54f2d…c637`. |
| Rights | A public Apache-2.0 package. Static analysis of the shipped artifact only; nothing was executed. |
| Evidence ID | `ev_bda547f2ecf27a6f41d199efc4b0f67d73c1fe52b0c6d0afb699ad9de213781b` |
| Graph | 13,071 semantic nodes and 19,361 relations. 2,708 dynamic calls are unresolved. |

**Established statically, then confirmed in the source text:**
- `_startTimer` schedules a `setTimeout` into `_halfOpen`. The delay is the constant `resetTimeout`.
- `on('success')` closes the breaker when it is half-open.
- `fail()` re-opens it while half-open.

**Not established:** runtime behaviour, and how deployments tune the thresholds.

## Mutation

The donor admits a component back on **one live success**. GREG instead:

- probes in the sandbox on a fresh frozen-oracle seed;
- restores **eligibility only**: VERIFIED, never ATTACHED;
- **doubles the wait** after each failed probe and each prior quarantine, capped at 24 h;
- **stops** after more than three in-service quarantines, or five failed probes, and leaves the decision to the founder;
- recovers **engines before the constructions built on them**. A construction probes through its own pinned engine via a probe-only registry view.

Re-admission goes through the existing Genesis route, so attaching still needs the founder or the mission's signed read-only scope.
