# Infinite Goal Chase — first founder-facing sandbox closure

Decision: **EXPERIMENT**. Scope: **CONSTITUTIONAL / SANDBOX ONLY**.
Source: Alfonso's current 2026-09-05 master coding directive, sections 0–53,
and clarification: “First goal chase is related to the infinite goal chase and
far far sci-fi level goals”. Authorization is for code, tests, a dedicated branch
and draft PR. It does not authorize merge, deployment, real communication,
spending, credentials, physical operation or authority expansion.

## Inspection truth and ownership

Exact revisions and bounded inspection scope are in
[`goal-chase-v0-inspection.json`](goal-chase-v0-inspection.json).
Canonical base is `main@bcbb1ab4a0c42cda4a97aec42a11125753962762`.
The named source files were not retrieved; their quotations are current
user-supplied intent, not a claim that the full source files were inspected.

| Responsibility | Inspected owner | Decision for this slice |
|---|---|---|
| Institutional events and evidence | `events/spine.py`, `provenance/ledger.py` | Reuse one caller-owned ledger/spine |
| Durable work and waiting | `DurableWorkflow`, `events/engine.py` | Use canonical construction/resume seam and checkpoint truth |
| Authority, grants, budgets, consequence | `policy/engine.py`, `ConsequenceGate`, `GrantIssuer`, `BudgetOffice` | Reuse; simulated execution only |
| Identity | `PassportRegistry` | Fresh synthetic workload passport per process; identity grants nothing |
| Capability descriptors | `GenomeRegistry` | Reuse; descriptor plus frozen qualification and actual built-in required |
| Causal/outcome memory | `memory/causal.py` | Reuse canonical witness/receipt/outcome joins |
| Goal/decision presentation | No complete persistent loop on main | Thin `egregore/goal_chase.py` composition, no global runtime owner claim |
| Standing cognition | `egregore/runtime.py` | Preserve proposal-only boundary; trigger integration remains a callable seam |
| Organizational design | OMNIMORPH; draft #88/#90/#92 | Useful unmerged machinery; no dependency or activation in this experiment |
| Runtime composition | Competing draft #70/#87 | UNRESOLVED; neither is silently promoted |
| First-goal-chase branch | Four doctrine files beyond main | USEFUL_UNMERGED; preserves the same Infinite Goal Chase horizon |
| Media/operator transport | DALEOBANKS heartbeat and operator line | Organ-owned, coupled to its DB/Twilio; do not import into Kernel |
| Venture orchestration | WMI fixed specialist roster and loops | Specialist behavior, not institutional authority |
| PumpStation | Wallet/API main; simulation/benchmark drafts | No borrowed capital or swarm authority |
| RailScout | Main contains README only; governance drafts | Intended evidence-refinery boundary, not exercised capability |
| RESEARCH-IN | Research web/ingest scaffold | HTTP 200 “ingested” does not prove research evidence |
| Build Your Own X | Tutorial catalog | Mechanism reference, not an executable organ |

No existing implementation is deleted or superseded by this slice. The proposed
ownership map merged in #82 is evidence of responsibility, not proof that its
remaining integration choices are ratified. Relevant Kernel drafts were read at
their actual heads; metadata-only inspection is not described as a full audit.

## Founder intent trace and horizon

Use this dated experiment ID rather than allocating another conflicting
`INTENT-0029` (already used independently by drafts #86 and #91).

| Intent group | Lifecycle | Implementation boundary |
|---|---|---|
| Persistent observe → bottleneck → bounded work → founder decision → resume → reconcile | active | Four-path sandbox acceptance experiment |
| Capability may expand; authority may not | active constitutional invariant | Existing policy/Gate plus exact signed sandbox request binding |
| Minimum necessary interruption; negative evidence; truthful closure | active | Durable dedupe, denial, quiet waiting, frozen evaluator |
| Generations 2–9+: tool breadth, computer use, multi-model cognition, capability acquisition, organizations, self-repair, external operations and physical embodiments | deferred with trigger | After the first complete proof, select one next missing control layer; preserve interchangeable capability/trigger/channel seams |
| Merge/deploy, real communications, money, accounts, credentials, devices, self-authorization | prohibited in this assignment | No such adapter is admitted |
| Canonical ownership of draft `runtime/` | conflicted outside slice | Founder decision before integration/promotion of either draft |

The first goal chase is an initial proof within the Infinite Goal Chase, including
its far-future aspirations. This experiment neither retires that destination nor
claims that later generations exist. The full current directive remains governing
intent; this table groups its requirements without converting aspirations into
permission.

## Material decision IGC-SANDBOX-V0 — exactly two strengthening passes

Five perspectives below are separate analyses by one coding agent, as allowed by
the repository protocol. They are not independent human review or agent consensus.

| Role | Position and evidence | Concern / recommendation |
|---|---|---|
| Founder-Intent Steward / Builder | A persistent, actionable founder boundary is the missing behavior | Keep the full horizon; EXPERIMENT |
| Systems Architect | Main already owns events, work, evidence, authority and capability descriptors | Composition must not choose #70/#87; EXPERIMENT |
| Adversarial Reviewer | Gate callback is not human authentication; checkpoints alone cannot guarantee exactly-once effects | Signed exact request plus reconciliation stop; EXPERIMENT with dissent |
| Operator and Maintainer | An event-driven callable and boring CLI are sufficient for four paths | Single writer; no scheduler or new service; EXPERIMENT |
| Evidence and Welfare Guardian / Constitutional Reviewer | Synthetic evidence proves only sandbox behavior; attention telemetry can be gamed | Null real-world metrics and retained negatives; EXPERIMENT |

### Pass 1 — structural strengthening

Compare on closure, authority, replay, cost, maintenance and reversibility:

| Alternative | Advantage | Liability | Disposition / revival evidence |
|---|---|---|---|
| Current baseline: direct DurableWorkflow + Gate | Existing tested machinery, lowest execution complexity | No persistent founder-facing goal projection/inbox | Protected execution baseline |
| Do nothing | Zero implementation cost | Closure stays zero | Revive if this cannot reuse canonical owners safely |
| Simplest viable: one script with checkpoints | Low code cost, easy demonstration | Ad hoc scope/authentication and missing replay semantics | Reject; revive only if it satisfies every gate more simply |
| Strongest competitor: stack on #87 + #90 | More developed identity/task/replay primitives | Disputed runtime owner, substantial unmerged dependency | Defer until owner/adoption decisions; preserve whole stack |
| Proposed reversible composition on main | Complete loop using canonical owners | D1 new goal contracts; D2 sandbox inbox; D3 dispatch/checkpoint gap | Bounded experiment in dedicated branch |

Strengthen once: D1 use only goal-domain records on existing EventSpine and keep
workflow cursor authoritative; D2 inject verification of synthetic signed inputs,
bind exact scope and expiry, then feed existing Gate approval callback; D3 check
canonical receipts before resume, never retry an ambiguous dispatch.

### Pass 2 — adversarial strengthening

Re-attack that design for hidden duplicate truth, state races, replay, spam,
authority/evidence substitution, evaluator contamination and false closure.

- D1 **experiment**: reconstruct projections on every operation, verify canonical
  chain and causal links, bind schema/evaluator/configuration hashes, refuse
  changed event IDs or conflicting intent. Owner: maintainer; trigger: any drift.
- D2 **accepted only in sandbox**: authentication demonstrates a test-key boundary,
  not real Alfonso identity or hostile-process isolation. Synthetic identity is
  unmistakable; private test key is never passed to a candidate or written to the
  event log. Owner: Alfonso/security reviewer; trigger: any proposed real adapter.
- D3 **accepted safety limitation**: a started action without complete Gate records
  stops at reconciliation; zero duplicate effects outranks automatic progress.
  Owner: operator; trigger: dispatch ambiguity.
- New W1: multiple JSONL writers race. Strengthening: exclusive nonblocking local
  file lock at the session boundary; a second session refuses.
- New W2: a candidate reports its own success or sees its judge. Strengthening:
  freeze evaluator before runtime, pass only observation/action snapshots to
  allowlisted trusted built-ins, separately evaluate their result. No generated
  code is loaded and no OS isolation is claimed.
- New W3: quiet-mode metrics hide decisions. Strengthening: count created requests
  and actual sandbox delivery separately, preserve denial and transport failure,
  report synthetic intervention minutes separately from unknown real minutes.

Final material decision: **EXPERIMENT**. No third strengthening pass is performed.
Later material design changes require a separately linked decision.

Material dissent remains: main's Gate/ledger have trusted-process limitations,
including development signing, mutable in-memory registries, no distributed lock,
and no real human-authentication channel. This experiment is admissible only
because effects and candidate code are restricted to deterministic sandbox
functions. Independent review, production identity, key custody and dispatch
reconciliation must precede any broader use. No success here resolves that dissent.

## System specification and mechanism lineage

Frozen contract/evaluator: `egregore/goal_chase_spec.json`,
`egregore/goal_chase_evaluator.py`, `tests/fixtures/goal_chase_v0_seal.json`.
All 23 acceptance gates are conjunctive. A partial episode counts zero.

| Primitive | Purpose/state/transition | Mutation and interaction | Authority / trust / proof / failure / recovery |
|---|---|---|---|
| Canonical event sourcing | Append facts, reconstruct state | Goal progress and founder attention become projections of one institution's history | Events are data; hash chain + causal references; corruption refuses replay |
| DurableWorkflow | Cursor/state checkpoints, approval waits | Goal discrepancy selects bounded work; founder decision releases only one exact step | Workflow never grants authority; checkpoint gap reconciles against receipts |
| Gate and capability security | Identity, policy, scoped grant, budget, witness | Capability availability can advance while consequence scope remains fixed | Policy/Gate decides; forged/widened/expired input refuses; no blind retry |
| Operator request/response | Exact request, pending/denied state | Notification becomes scarce-attention allocation with durable suppression | Transport supplies no authority; failure stays pending; identical denial stays denied |
| Genome + deterministic evaluation | Descriptor, qualification, result comparison | Missing competence emits a developmental deficit instead of imagined success | Registry is not permission; candidate has no evaluator or signing keys |
| Causal memory | Witness → receipt → outcome | Reconciled sandbox result informs next goal state and preserves losses | Simulation never becomes external reality; missing proof prevents closure |

Maintained state, information and resource flows remain inspectable in the event
trace. Proposed/rejected alternatives are retained. Observable thresholds are
freshness, exact scope, declared budget, one dispatch and all acceptance gates.
No blockchain, token, biological claim, vector-memory authority or new scheduler
is introduced.

## Authority and failure model

- Founder: external originating authority. Demo signer is explicitly synthetic.
- Model/candidate: data and recommendations only; no input can mint authority.
- Capability registry: descriptor lookup; qualification does not issue grants.
- Existing policy/Gate: sole authorization/receipt mechanism.
- Goal reducer: narrows to the signed sandbox goal and action; never opens a real channel.
- Channel adapter: deterministic test delivery keyed by message ID; no SMS, voice,
  email or push providers. A durable message is a replayable projection.
- Trigger: explicit caller event; no background scheduler, provider or model required.

Process crash, duplicate input, stale observations, missing capabilities,
denials, missing transport, forged decisions, corrupt records and uncertain
dispatch all retain their evidence and fail toward bounded waiting/refusal.
JSONL lock is local single-writer coordination, not distributed consensus.
Hash-chain integrity is not protection against a privileged attacker rewriting
and rehashing the entire file. Real key custody/anti-rollback remains FUTURE.

## Experiment, evidence and handoff

IMPLEMENTED and EXERCISED: the founder CLI composes the existing Kernel owners
through autonomous research, one reserved decision, durable waiting, validated
synthetic approval, bounded simulated execution and outcome reconciliation.
The first executable goal explicitly builds the Infinite Goal Chase foundation.
A deferred goal preserves advanced science, robotics, automated laboratories,
manufacturing, distributed embodiment and future facilities with prerequisite
goals and a founder review trigger. These remain FUTURE, not achieved capabilities.

The complete required final report, 23-gate mapping, environment, command results,
limitations and artifact hashes are in
[`goal-chase-v0-evidence/report.json`](goal-chase-v0-evidence/report.json).
The preserved [begin](goal-chase-v0-evidence/begin.txt) and
[approval/resume](goal-chase-v0-evidence/approve.txt) outputs are founder-readable.
The [canonical sandbox ledger](goal-chase-v0-evidence/sandbox.jsonl) retains
synthetic intent, observations, rejected sources, exact decisions and the
witness/receipt/outcome joins. It contains a PUBLIC synthetic test signature,
not a production credential or real Alfonso authorization.

Results: canonical baseline **495 passed**; final suite **569 passed**, including
**74 new tests**, zero failures/skips. Institutional verifier V1–V5 and schema,
authority-singleton and sealed-development checks passed. Five-role deliberation
with exactly two strengthening passes validates. All roles were analytical
perspectives of one coding agent, not independent human/agent reviews.

Negative results remain: the initial environment lacked pytest; an initial test
fixture used incorrect nested payload access (55 passed / 1 failed). The fixture
setup was corrected, and the original failure is retained. The frozen evaluator
and success contract were not changed. After environment continuation required
reinstalling the declared development dependencies, the final full suite passed
again in 7.31 seconds.

Replay proof uses separate begin/inspect/approve processes and identical pre-exit
snapshot/head checks. Abrupt process-exit tests additionally cover pending
approval, completed receipt before workflow checkpoint, and ambiguous dispatch.
The last case safely blocks for reconciliation and does not claim closure.

**VERIFIED_PERSISTENT_GOAL_CHASE_CLOSURES: 0 → 1 (SIMULATED / SANDBOX).**
Unauthorized external effects, duplicate consequences and untraceable transitions
are zero in the saved proof. One founder interruption; the fixture's 2 minutes
per sandbox outcome is synthetic. Real founder intervention minutes per verified
outcome remains null; real-world verified outcomes remain zero.

Reproduce in separate processes using a new ledger path:

```sh
python -m pip install -r requirements-dev.txt
python -m egregore.goal_chase_demo /tmp/igc-demo.jsonl --phase begin --output /tmp/igc-before.json
python -m egregore.goal_chase_demo /tmp/igc-demo.jsonl --phase inspect
python -m egregore.goal_chase_demo /tmp/igc-demo.jsonl --phase approve
python -m pytest -q
```

Use `--phase reject` instead of approve in a separate fresh episode to exercise
denial. `--expected-snapshot-hash` accepts the begin output's `snapshot_hash` for
an explicit restart equality assertion. The acceptance suite performs this check
automatically. No daemon, real notification provider or model is necessary.

Evidence maturity: mechanics are EXERCISED in the declared sandbox; later
generations and application integration remain PROPOSED/FUTURE. Nothing here is
HARDENED for production. Strongest counterevidence is the trusted-process,
fixed-function nature of the experiment and unresolved competing runtime drafts.
Final decision: **EXPERIMENT**. Independent review remains the next review gate.

Rollback: close the draft or revert this branch's additions; retain its evidence
and history. No production migration or runtime activation exists to undo.

Kill criteria: any unauthorized external effect, repeated simulated dispatch,
forged/widened approval accepted, lost denial/negative evidence, broken causal
lineage, changed frozen evaluator, new authority/event/task owner, or false closure.

Next review trigger: complete four-path plus fresh-process proof, then independent
review of this draft. Next named bottleneck after success: integration of the
founder projection/inbox with the founder-ratified runtime owner, without duplicate
authority or scheduling. Production communications and later generations remain
separately governed.
