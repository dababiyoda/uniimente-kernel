# FM-STATE-1 — truthful capability inventory

Source: controlling full-machine correction, `docs/intent/INTENT-20261001-FULL-MACHINE-COMPLETION.json`, and inspection of `greg/body.py:status`. The read-only inventory registered every builtin as ATTACHED, ignoring disabled defaults and retained detach/quarantine. This misled the same console and authenticated phone interface used by the machine. It did not change actual Body execution state.

Decision: RETAIN the verified correction. Owner: GREG body/interface maintainer. Authority: reversible implementation only; no attachment or permission change. Trigger: lifecycle/default/registry contract changes. Rollback: revert the shared projection helper while preserving ledger history, then retain the inaccurate-inventory defect as an open blocker. Kill condition: observer code initializes a writer, attaches a descriptor, launches a generated adapter, or presents retained lifecycle state as fresh integrity/authority proof.

## Pass 1

Compare current behavior (incorrect ATTACHED inventory), do nothing (preserve the defect), omit inventory (truthful but removes useful machine state), initialize Body during reads (complete execution reconstruction but may write/repair), and replay canonical metadata with shared builtin defaults (selected).

One coding agent performed all five analytical perspectives; these are not independent reviewers or human approval. Founder-Intent Steward requires the fixed Body + Organs + Mind boundary and preserved future families. Systems Architect shares existing registry/default/state semantics, with no new authority plane. Adversarial Reviewer attacks false attachment and replayed old approvals. Operator/Maintainer requires reads to work beside a running writer. Evidence/Welfare Guardian distinguishes lifecycle metadata, current dependencies, fresh artifact integrity and actual task permission.

Mechanism: `_builtin_registry` supplies the same catalog defaults to Body.open and status; `_replay_capability_states` applies canonical state events in order. The status observer includes retained formed-manifest metadata without constructing its executable adapter or invoking Genesis restoration. A supplied state has no promotion score; the canonical registry validates it. Inventory explicitly states its integrity and permission limits.

Downsides: FM-STATE-A, retained metadata can become stale after source damage (diagnostic: observer's disclosed integrity limit; current execution restoration remains the integrity gate). FM-STATE-B, a malformed canonical state may prevent inventory display (diagnostic: strict registry validation rather than invented availability). FM-STATE-C, sharing a helper concentrates a bug between execution and observation (diagnostic: compare real runtime state against both interfaces after independently signed transitions).

## Pass 2

The same five perspectives reattack the correction. Steward checks that VERIFIED future descriptors remain visible and unactivated. Architect rejects a second persistence/permission service. Adversary replays an earlier signed attach after a later signed detach, restarts the Body and compares the observer. Operator forbids Body.open in the read-only status path and checks unchanged ledger bytes. Welfare Guardian refuses to infer authority, professional competence or fresh source integrity from a lifecycle label.

Native evidence: `tests/unit/test_greg_status_capabilities.py` uses real laboratory Ed25519 commands, signed attachment/detachment, replay and restart. Console snapshot/planner inventory and authenticated phone status match runtime states. Recorded builtin and formed-descriptor quarantine remain quarantined without initializing a writer. Existing interface/remote regression checks also pass: 24 tests in 4.85 seconds, `/workspace/scratch/status-projection-full-machine-tests.log`. Laboratory identity does not authenticate Alfonso or establish founder-device completion.

FM-STATE-A ACCEPTED, owner operator, trigger source/dependency damage: retain the integrity-limit disclosure and execution-time integrity verification. FM-STATE-B ACCEPTED, owner ledger maintainer, trigger malformed state: fail visibly and repair through the existing authority path. FM-STATE-C EXPERIMENT, owner adversarial maintainer, trigger a new lifecycle event: keep signed-history comparison tests. No lifecycle, grant, shutdown or paid-inference authority changed. After this integrated dependency, continue the next unblocked requirement of the complete machine.
