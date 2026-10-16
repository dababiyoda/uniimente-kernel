# Evidence bundle: Goal Gravity (INTENT-20261013-GOAL-GRAVITY)

Deterministic, model-free runs on synthetic JSONL ledgers with test passports, the development witness key and
grants minted by the tests from the loop's own proposals. These logs prove the mechanism on this tree; they are not
evidence of any external effect (tier: IMPLEMENTED / UNIT-TESTED / INTEGRATION-TESTED; not SANDBOX-VERIFIED, not
EXTERNALLY VERIFIED, not FOUNDER-ACCEPTED).

| File | What it records |
|---|---|
| `pytest-baseline-main-19fa33c.log` | kernel `main` before any change |
| `pytest-full-suite.log`, `verifier-v2.log`, `ci-check-*.log` | first increment (commit `ef4f5c7`) |
| `pytest-full-suite-increment-2.log` | second increment: full suite (seam, contracts, deficits, reconciliation, verification, controls) |
| `verifier-v2-increment-2.log` | verifier V1–V5 after the second increment (closures incl. `egregore-goal-gravity`) |
| `ci-check-*-increment-2.log` | schema-reference and authority-singleton checks after the second increment |
| `validators-increment-2.log` | deliberation and intent-record validators |
