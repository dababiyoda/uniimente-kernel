# events

Institutional event spine. Typed CloudEvents-compatible envelopes per contracts/event.schema.json. Organs exchange governed events only; direct organ-to-organ calls are prohibited.

**Status — Phase 4, first slice landed:** the canonical implementation is `sdk-python/uniimente_kernel/events.py` (kernel SDK v0.6.0). `EventSpine` builds contract-conformant envelopes and persists them through the hash-chained `DecisionLedger`; every event names its `causal_parent` (null only for origin events), so any outcome walks back to the evidence and approvals that permitted it. Organs import the SDK module; they do not own event machinery locally.

- Contract: `contracts/event.schema.json` (parity enforced by C12, `verifier/verify_events.py`)
- Tests: `sdk-python/tests/test_events.py`
- Later Phase 4 slices land here: durable transport between organs, routing, retries, approval waits, state reconstruction, outcome capture (kernel issue #4).
