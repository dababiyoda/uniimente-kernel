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
| `pytest-full-suite-increment-3.log` | third increment (Competency Compiler wiring plus its review fixes): full suite, Python 3.13 |
| `pytest-full-suite-py311-increment-3.log` | the same tree on Python 3.11, the interpreter CI uses |
| `verifier-v2-increment-3.log` | verifier V1–V5 after the third increment; run record `verifier/runs/v2-2026-10-14T11-15-34.044978+00-00.json` |
| `ci-check-*-increment-3.log` | schema references, authority singleton and sealed-developmental checks after the third increment |
| `validators-increment-3.log` | both deliberation records and both intent records; main's competency-compiler record fails the skill schema identically on `main` (format conflict, noted in the log) |
| `review-probes-increment-3.log` | every adversarial-review reproduction run against a clean checkout of `81c90c7` (each finding reproduces) and against the fixed tree (none does), with the expected passes explained |

Third-increment tier is unchanged: IMPLEMENTED, UNIT-TESTED, INTEGRATION-TESTED on synthetic ledgers with synthetic
verifiers. Capability qualification runs repository tests in a pytest subprocess, which is not a sandbox, so nothing
here is SANDBOX-VERIFIED. The review's refuting verifiers did not run, so the findings are confirmed by reproduction,
not by an independent verifier.
