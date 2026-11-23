# Invention Ledger

Deliverable E. The master prompt asks for the Mechanism Recombination Foundry method (section 13). No skill by that name was invoked in this session, so its causal procedure was applied by hand and is recorded here step by step. Every precedent below was read at the cited source on 2026-10-15. Every trunk fact names a file or a test.

## 1. The three invention fields and the deficit each one shows

| Field | What the founder asks for | Deficit measured on the trunk |
|---|---|---|
| A. One machine, one provenance and authority across organs | One GREG whose organs exchange authenticated messages through one Kernel-led trace | Mostly closed. Organs run in their own interpreters and sign with the shared HMAC key; #174 per-organ keys are on the trunk, but the organs still pin the one-key boundary package (`ORGAN_MAP.md`, defect 4). Upgrading the pin is a founder decision |
| B. Deficit, then capable form, then resumption | A missing or broken function is formed or repaired, and the original mission resumes | Genesis forms and repairs functions (`greg/genesis.py`, `greg/recombine.py`). The gap is interruption: every interrupted non-read-only action stops its mission until the founder answers a reconciliation request, even when no consequence could have left the sandbox. Steps 7 and 7b of the ten-step proof each need a founder answer |
| C. Trusted paid or regenerative transaction closure | A real transaction closes with accepted proof and settlement | No real transaction exists. The rehearsal (`greg/venture_rehearsal.py`) closes a FIXTURE buyer, FIXTURE books and no payment rail. Closing this field needs a real buyer and founder authorization, so it is not buildable in this session |

Field B is where a real, buildable, measurable gap sits. Field A's residual is a founder decision. Field C's residual is an external dependency. The selected invention is therefore in field B. Fields A and C keep their configurations below so the next session can resume them.

## 2. Nearest direct precedents

| Precedent | What it does | What it lacks for GREG |
|---|---|---|
| Presumed Abort, two-phase commit in R* ([Mohan, Lindsay and Obermarck, ACM TODS 11(4), 1986](https://pdos.csail.mit.edu/6.824/papers/rstar.pdf); [summary](https://blog.acolyer.org/2016/01/12/presume-abort-commit/)) | A recovering participant that finds no commit record presumes the transaction aborted, which saves log forces and messages | It reasons only about protocol state. It cannot say whether a side effect escaped before the crash, which is exactly what GREG's no-blind-retry rule protects |
| Kubernetes Job pod failure policy, `action: Ignore` on `DisruptionTarget` ([Kubernetes docs](https://v1-34.docs.kubernetes.io/docs/tasks/job/pod-failure-policy/)) | A pod killed by a disruption, not by its own fault, does not count toward the retry limit | The classification is of the cause, set by the cluster operator. It carries no proof about effects and no per-workload authority |
| Temporal activities ([error handling](https://docs.temporal.io/best-practices/error-handling); [fixed-count retries](https://docs.temporal.io/design-patterns/fixed-count-retries)) | At-least-once activities, retried by policy; duplicates are absorbed by idempotency keys in the downstream system | Retry safety is a programmer's declaration. Nothing proves that an external system will drop the duplicate |
| GREG's own `retry_safe` manifests (`greg/missions.py`, UNCERTAIN branch) | A read-only, idempotent capability is retried after an interruption without asking | Covers only read-only capabilities. A worker that writes is never covered, however confined |
| GREG's #157 envelope (`greg/worker_isolation.py`) | Bubblewrap namespaces: private filesystem view, closed or relayed network, no credentials for the script worker | Confines the effect but does not use that fact after an interruption |

## 3. Mechanism cards (atoms)

| Card | Atom | State transition | Authority it needs | Failure it handles |
|---|---|---|---|---|
| MC-B1 Dispatch claim and receipt | A claim is journaled before an effect; a receipt after it | claim, then receipt (DONE); claim without receipt on restart (UNCERTAIN) | The Gate's grant for that attempt | Crash between effect and acknowledgement |
| MC-B2 Founder reconciliation | The founder states whether an UNCERTAIN effect happened | UNCERTAIN, then RECONCILED_NOT_EXECUTED (retry) or DONE | A founder-signed DECISION | Unknowable effects |
| MC-B3 Consequence-inert envelope | The script worker runs with the network namespace closed, no credentials, no spend, and writes only inside a private clone that is discarded before any retry | prepared, then ran or refused; never falls back to supervision | None (it confers none) | A worker that would otherwise reach outside its clone |
| MC-B4 Order evidence | A completed work order writes `evidence.json`, outside the worker's writable view; a retry reuses it by order digest | absent, then COMPLETED or NO_CHANGE | None | Re-running finished work |
| MC-B5 Signed standing scope | A founder-signed mission field pre-authorizes a narrow class, as `auto_attach` does for read-only constructions | absent or exact value | Founder signature on the mission | Founder attention spent on routine cases |

## 4. Mutation operators (at least three per core mechanism)

| Core mechanism | Operator | Result | Changes authority, incentive or consequence? |
|---|---|---|---|
| MC-B2 Founder reconciliation | Delegate: replace the per-incident founder answer with a founder-signed standing mandate for one class | Standing reconciliation | **Authority**: the founder decides once per mission instead of once per incident |
| | Condition: require a proof that the effect domain was closed before the delegated answer may be given | Proof-carrying reconciliation | Consequence: only inert actions qualify |
| | Bound: cap delegated answers per action, then return to the founder | No interruption loop | Consequence |
| MC-B3 Inert envelope | Invert: use the envelope's guarantees after the fact as evidence, not only before as prevention | Evidence of inertness | No |
| | Pin: forbid the supervised fallback for the inert provider | Inertness cannot be weakened by a body setting | Consequence |
| | Digest: record the provider code digest in the proof | An edited provider class is visible to an appraiser | No |
| MC-B1 Claim and receipt | Re-key: bind the delegated record to the same (mission, action, attempt) as the claim | One outcome per attempt in routing and resilience | No |
| | Annotate: attach the failed predicates to the founder request when the proof fails | The founder sees why GREG could not settle it | Incentive: GREG gains nothing by asking; the founder decides faster |
| | Price: only a provider with no paid route qualifies; the cap held for the attempt is released because nothing could be charged | No possible spend is ever settled without the founder | **Consequence** |

## 5. Raw configurations

| # | Field | Configuration | Verdict |
|---:|---|---|---|
| 1 | B | Status quo: the founder reconciles every UNCERTAIN action | Baseline |
| 2 | B | Presumed abort for every UNCERTAIN action: retry without asking | Rejected: a paid or networked worker could run twice with real effects |
| 3 | B | Extend `retry_safe` to any capability the author declares idempotent | Rejected: a declaration, not a proof; a worker's writes are not idempotent across clones |
| 4 | B | Proof-carrying standing reconciliation for consequence-inert dispatches, under a founder-signed mandate | **Selected** |
| 5 | B | Configuration 4 without the mandate: the engine settles inert cases on its own | Rejected: the machine would settle its own uncertainty, which is self-authorization |
| 6 | B | Configuration 4 plus a separate appraiser process that must co-sign before each retry | Finalist: adds a process launch per interruption; the re-derivation is adopted as an appraiser check instead (round 2) |
| 7 | B | Checkpoint and restore the interrupted worker process (CRIU) | Rejected: privileged, host-specific, and restores process state that the discarded clone already makes unnecessary |
| 8 | B | Always discard the clone and retry regardless of spend | Rejected: spend can be doubled |
| 9 | C | Book the signed cap when spend is unknown (status quo) | Baseline, kept |
| 10 | C | Reconcile provider-reported spend against a provider invoice | Deferred: needs a real paid route, which is not authorized |
| 11 | C | Escrow each order's budget and release it only on independent appraisal | Finalist for the first real Venture Cell; needs a real payment rail |
| 12 | A | Upgrade both organs to a per-organ-key boundary package | Decided 2026-10-23; implemented on DALEOBANKS #96 and WealthMachineIntelligence #44 (organ `main` merge open) |
| 13 | A | One causal trace id across organ messages and mission receipts | Exists: `organ_bridge.bound_facts` binds organ observations to mission receipts |
| 14 | A | Organ quorum: a second WMI process reproduces each assessment | Exists in #178's exchange |

## 6. Ranking

Criteria, in order: new observable capability; authority neutrality (nothing widens without the founder's signature); measured effect against the simplest alternative; cost per use; reversibility.

1. **Configuration 4**, proof-carrying standing reconciliation. It removes founder interventions for a class the envelope already proves inert, adds no authority the founder did not sign, costs one predicate evaluation, and is reversed by omitting one mission field.
2. **Configuration 6**, appraiser co-signature. Stronger independence, at a process launch per interruption. Its re-derivation is adopted inside configuration 4.
3. **Configuration 11**, escrowed order budgets. The right shape for field C, blocked on a real payment rail.

## 7. Round one: five constraints turned into mechanism changes

| Constraint | Mechanism change |
|---|---|
| No blind retry of an uncertain effect | Retry only on a recorded proof that the effect domain was closed. The proof is data an appraiser can re-check, not a judgment |
| Intelligence never creates authority | The mandate is a founder-signed mission field with one exact value. The engine evaluates predicates; it decides nothing else |
| Spend stays inside the signed cap | Only a provider with no paid route (no credentials, no network) qualifies. A first draft required a signed cost of zero; that excluded every script mission, because the work order requires a positive budget, so the condition moved to the provider |
| The supervised worker setting exists | Only a provider that can never fall back to supervision qualifies, so the body setting cannot make an action inert |
| Founder attention is scarce | When the proof fails, the request names the failed predicates |

## 8. Round two: elevation and new failure geometry

| Attack on the round-one design | Change |
|---|---|
| Interruption loop: a body that crashes on every run would retry forever | At most two standing reconciliations per action, then the founder |
| Forged evidence: a worker writes or deletes `evidence.json` to steer the proof | `evidence.json` sits outside the inert worker's writable view (the clone and its runtime only); a non-inert worker never qualifies |
| Edited provider: someone changes the script worker to open the network | The proof records the digest of `greg/workers.py`, which is a protected surface, so an appraiser sees the code that made the claim |
| Mandate replay across missions | The proof binds the mission's command digest |
| Founder STOP during the retry | Unchanged: STOP is checked before every dispatch |
| Independence | `inert_interruption_proof` is a pure function of its inputs. Five predicates re-derive later from retained records alone; the order-evidence observation is made at settlement and recorded in the proof, because the retry then writes completed evidence |

## 9. Selected mechanism and measured effect

**Built** on the canonical surfaces, no new subsystem:

- `greg/workers.py`: `inert_interruption_proof` (six predicates: founder mandate, `worker.commission`, internal consequence only, a provider whose class declares `CONSEQUENCE_INERT`, no completed order evidence, fewer than two earlier standing settlements) and the script worker's declared `GUARANTEES`.
- `greg/missions.py`: the UNCERTAIN branch records a `RECONCILED_NOT_EXECUTED` action with `route: standing_reconciliation`, the mandate digest and the proof, then retries once. Otherwise it asks the founder, naming the unmet predicates.
- `contracts/greg-mission.schema.json`: the optional `standing_reconciliation: {"consequence_inert": true}` field. `greg/routing.py` counts the record as a reconciliation; `greg/planner.py` strips the field from model drafts.

**Measured** on the same scenario, a real SIGKILL of the supervised body process while the script worker is mid-run, in one ten-step proof run on 2026-10-15:

| Measure | 7b, no mandate | 7c, founder-signed mandate |
|---|---|---|
| Founder questions | 1 | 0 |
| Completed worker runs | 1 | 1 |
| Duplicate consequences | 0 | 0 |
| Commission statuses | UNCERTAIN, RECONCILED_NOT_EXECUTED, DONE | UNCERTAIN, RECONCILED_NOT_EXECUTED, DONE |
| Separate-process appraisal | VERIFIED | VERIFIED |

Unit controls (`tests/unit/test_greg_standing_reconciliation.py`, 21 tests): each predicate alone withholds the settlement; completed evidence is never settled as "not executed"; an instance attribute cannot make a provider inert; a networked provider under the mandate is still asked and told why; a crash loop is settled twice and then handed to the founder; the mission's held cap is released; a model draft never carries the mandate.

**Against the simplest alternatives.** The status quo costs one founder question per interruption. Presumed abort (configuration 2) also costs none, but would re-run a networked or paid worker whose first run may have acted; the proof refuses those providers: in the tests the Claude Code, Codex and a local CLI provider each fail the provider predicate, and the local CLI case still asks the founder on the mission path. Extending `retry_safe` (configuration 3) would rest on a declaration with no recorded proof.

**Falsification.** The claim fails if an action settled under the mandate is shown to have had an effect outside its discarded clone, if a settled attempt yields two completed runs, or if a provider without the class declaration is ever settled. The second and third are automated tests. The first rests on the envelope's guarantees, tested in `tests/unit/test_greg_worker_isolation.py`.

**Stated limits.** An interruption caused by a founder STOP is also settled under the mandate; the retry still waits until the founder restarts the body. The founder-intervention effect is measured on one scenario, not yet on founder use.

## 10. What stays open

- Field A: merging the per-organ-key pin upgrade into the organs' `main` (DALEOBANKS #96, WealthMachineIntelligence #44).
- Field C: a real buyer, a real payment rail and escrowed settlement (external dependency and founder authorization).
- Configuration 6 as a hard pre-retry gate, if an interruption class ever carries more than local consequence.
