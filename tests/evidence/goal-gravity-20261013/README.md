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
| `verifier-v2-increment-3.log` | verifier V1–V5 after the third increment; run records `verifier/runs/v2-2026-10-14T11-15-34.044978+00-00.json` (review fixes) and `verifier/runs/v2-2026-10-14T11-20-31.555889+00-00.json` (after merging main #170) |
| `ci-check-*-increment-3.log` | schema references, authority singleton and sealed-developmental checks after the third increment |
| `validators-increment-3.log` | both deliberation records and both intent records; main's competency-compiler record fails the skill schema identically on `main` (format conflict, noted in the log) |
| `review-probes-increment-3.log` | every adversarial-review reproduction run against a clean checkout of `81c90c7` (each finding reproduces) and against the fixed tree (none does), with the expected passes explained |
| `defect-repro-increment-4.log` | reproduction, on a clean checkout of `6ce6b3f`, of the open-attempt defect the fourth increment fixes: a route whose first outcome was `unknown` was re-planned by a grantless wake and dispatched a second time (two Gate dispatch claims) |
| `pytest-full-suite-increment-4.log` | fourth increment (return report, wake schedule, open-attempt guard, review fixes): full suite |
| `pytest-full-suite-py311-increment-4.log` | the same tree on Python 3.11, the interpreter CI uses |
| `verifier-v2-increment-4.log` | verifier V1–V5 after the fourth increment; run records `verifier/runs/v2-2026-10-14T16-33-18.942539+00-00.json` (implementation) and `verifier/runs/v2-2026-10-14T17-07-22.304199+00-00.json` (with records and evidence) |
| `ci-check-*-increment-4.log` | schema references, authority singleton and sealed-developmental checks after the fourth increment |
| `validators-increment-4.log` | the fourteen supplementary-materials intent records, the Goal Gravity intent record and the fourth-increment deliberation record against the protocol validators (first run failed on two records; the log says what changed) |
| `pdf-extraction-increment-4.json` | the three founder-supplied PDFs read page by page: intent candidates, cross-document conflicts, mechanism status table, effect translations and evidence-tier warnings (all three PDFs are AI-generated documents the founder forwarded; treated as mechanism sources, not as founder authority) |
| `review-increment-4.json` | the independent adversarial review of the fourth increment: every finding raised, the three skeptic verdicts per finding, which were confirmed, and the disposition of each (fixed with a regression test, or why not) |

Third-increment tier is unchanged: IMPLEMENTED, UNIT-TESTED, INTEGRATION-TESTED on synthetic ledgers with synthetic
verifiers. Capability qualification runs repository tests in a pytest subprocess, which is not a sandbox, so nothing
here is SANDBOX-VERIFIED. The review's refuting verifiers did not run, so the findings are confirmed by reproduction,
not by an independent verifier.

Fourth-increment tier is unchanged: IMPLEMENTED, UNIT-TESTED, INTEGRATION-TESTED on synthetic JSONL ledgers (the
integration test reopens the ledger file once per simulated day of a three-day absence). The return report is a fold of
records the loop already writes; its money section carries declared estimates and reconciliation flags, never a payment
or settlement record, and the log says so. No host scheduler has called `turn()` on its own clock, so the wake schedule
is verified only as a view over durable state. Nothing here is SANDBOX-VERIFIED, EXTERNALLY VERIFIED or FOUNDER-ACCEPTED.
