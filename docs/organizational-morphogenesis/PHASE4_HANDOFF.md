# Phase 4 handoff — Cathedral Metabolism, CMC-002

## Latest repair continuation — 2026-09-05

**This section supersedes the historical stop notices below.** Alfonso authorized
the repair. Both lines are preserved at checkpoint
`6b2547298eb2ef7c452bb5699f9e59a562b7d4d9`, descended from remote `3e0f489`.
Read `CMC_002_REPAIR_RECONCILIATION.md`, the exact source ruling and updated
ownership ledger. This is a narrow CMC-002 repair, not a third formal pass.

Caller acceptance and evaluator-name claims are refused. CMC VERIFIED/CLOSED
requires a retained fixed-process appraisal binding source/result/mission/task/
worker/lease/policy. Missing or conflicting evidence quarantines intact submitted
tasks; corrupted ledger history is refused without appending to it. Uncertain
appraisal completion cannot trigger blind retry. This is a trusted-host
simulation boundary, not cryptographic provenance or privileged-host isolation.

Canonical selector: `routing/mission_selector.py`; egregore path is an import
shim, local fact API an adapter. Remote OMNIMORPH compiler is subordinate.
Earlier direct/static probe remains a test-only comparator. No source history,
failures or dissent were deleted or force-pushed.

Observed results, with raw logs under `phase4/evidence/repair-*`:

- Final focused: **78 passed**, 11.85s.
- Integration + task fabric + founder-command boundary + inventory:
  **207 passed**, 12.12s.
- Schema references: **25 schemas / 42 local refs passed**; all metaschemas valid.
- Exact manual repair source validates; it is NOT authenticated.
- Authority singleton check: **one each of six governed artifacts**.
- Retained appraisal ledgers: **16 records** accepted simulation, **15 records**
  disagreement/quarantine; both chains intact.
- Initial repair failures retained: **1 failed/49 passed**, then **4 failed/63
  passed**, followed by **67 passed** before the expanded controls.
- First broader run: **4 failed/1,438 passed**, 166.15s. Three are preserved
  baseline seam failures. The fourth identified the new process site; the
  inventory now explicitly names it and keeps UNMEDIATED_BY_STATIC_READING.
  A fixed-entrypoint/timeout/no-shell check was added.
- Final broader rerun: **3 failed / 1,440 passed**, 163.55s. The remaining three
  failures are the preserved CapabilityAdvertisementLike, RoutingDecisionLike
  and ProvenanceNodeLike seam checks. The combined tree is not globally green.
  Remote CI remains unobserved; no CI success is inferred from local results.

Commands ran from the Phase-4 checkout with system Python 3.12 and existing
`PYTHONPATH=/workspace/scratch/c1c408c41c36/tmp/phase3-venv/lib/python3.12/site-packages`.
No dependency or credential installation was performed:

```sh
python -m pytest tests/integration/test_protected_mission_appraisal.py tests/integration/test_cathedral_metabolism_runtime.py tests/unit/test_mission_resolution.py tests/unit/test_mission_compiler.py tests/unit/test_cathedral_metabolism.py -q
python -m pytest tests/integration tests/unit/test_side_effect_inventory.py tests/unit/test_organizational_task_fabric.py tests/unit/test_founder_authentication_gap.py -q
python -m pytest -q
python scripts/ci/check_schema_refs.py
python scripts/ci/check_authority_singleton.py
git diff --check
```

Also executed: schema metaschema validation, manual direction content-digest
validation and both new EvidenceLedger chain checks. Earlier pytest
unavailability, lost/UNKNOWN run, import failure and baseline failures remain
in the historical evidence below.

Reality: **actual CMC 0 → 0**. Founder interventions per verified outcome and
authenticated-intention-to-closure time remain NOT_MEASURED. No VDM, LIVE,
HARDENED, autonomy, authentication or organizational superiority claim.
The complete institutional metabolism and cross-organ economic closure remain
the destination; this repair does not complete or redefine UNIIMENTE.

Intentionally untouched: main/Phase-3 branch, organ repositories, source
manifests/pins, EventSpine, EvidenceLedger, DurableWorkflow, StandingCognition
internals, authority/policy/identity registries, Consequence Gate, model
frameworks, CI definitions and frozen thresholds. TaskFabric changed only at
the CMC appraisal guard. Previous inspection tables are historical; no claim
that every repository was re-audited in this narrow repair.

Rollback: retain inactive branch, checkpoint and evidence; no service to
deactivate. Never restore caller-asserted verification as an active fallback.
Stop before merge, deployment, activation, external effects, money, credentials
or scope expansion. Review/new founder ruling remains required for those acts.

## Historical handoff and blockers — preserved, superseded by repair above

Latest continuation: bounded reconciliation was authorized, but inspection of
the further-advanced remote 3e0f489 reproduced the founder-specified missing
protected-evaluator hard stop. See PHASE4_RECONCILIATION_BLOCKER.md and its
preserved negative test. No reconciled commit or draft PR was made; previous
test results below do not apply to a combined tree.

## Publication blocker — NEEDS_FOUNDER_DECISION

Before the final evidence commit, the remote dedicated branch advanced from
`cbb1d277ec9082acecb82d8529f816bc17f70784` to
`62b7b0116f3c0fd57397f327eae26e166a358b82` without this session updating it.
The new commits add `contracts/capability-manifest.schema.json`,
`contracts/mission-resolution.schema.json`,
`docs/intent/INTENT-CMC-BUILD-2026-09-05.json`,
`omnimorph/mission_compiler.py`, and change `omnimorph/__init__.py`.
These overlap semantic ownership of this session's router/compiler work.
Only commit metadata and changed-path/stat summaries were inspected at this
stop; the concurrent implementation has not been reconciled or tested here.

No final implementation/evidence commit or draft PR was created by this
session. Prepared local changes are preserved. Nothing was force-pushed,
merged, deployed or activated. Tests below describe this local work against
the previous frozen base, not the new remote commit or a combined tree.
Founder direction is required to establish ownership and authorize a bounded
reconciliation before further implementation or branch updates.

## Outcome and binding scope

**EXPERIMENTAL / SIMULATION ONLY. Actual Cathedral Metabolism Closure: 0 → 0.**
The complete master directive and genuine persistent-founder-mission closure
remain unfinished. Read `CMC_SCOPE_SUPERSESSION_002.md` before the original
experiment freeze. The latest manual-relay ruling permits design/development
records, not runtime execution. No real mission, organization, runtime service,
external effect, money, deployment or self-modification was activated.

The new reserved CMC command boundary refuses every input, including a valid
content-bound manual direction record or claimed signature. This is a refusal
boundary, not a cryptographic authenticator and not institution-wide hardening
of all historical runtime APIs. Existing authentication gaps remain open.

## Inspection, intent and ownership

The exact repositories, branch names, commit SHAs, PR numbers, inspection depth,
unavailable sources and competing implementations are in
`PHASE4_INSPECTION_LEDGER.md`. PRs #70 and #87 remain competing evidence,
#90 supplies the existing task fabric, and this branch is stacked on #92.
No runtime branch has been made sovereign. Other conversations were available
only as visible messages and supplied summaries, not exhaustive transcripts.

| Semantic owner | This slice |
|---|---|
| contracts | Closed manual-founder-direction record schema; existing mission schema reused |
| governance | Record validation only; no command issuance or policy changes |
| routing | Eight-family proposal router; declared rules, no learned performance claim |
| omnimorph | Existing organization compiler supplies subordinate design alternatives |
| events | Existing EventSpine, TaskFabric and DurableWorkflow, unchanged |
| egregore | Existing Standing Cognition reused; reserved CMC command refusal boundary |
| verifier | Separate fixed read-only source appraisal |
| provenance | Existing EvidenceLedger, unchanged |
| authority / Consequence Gate | Unchanged; no new grants or external-effect path |

`ARCHITECTURE-OWNERSHIP-CMC-PHASE4.yaml` records the additive ownership and
the narrow lazy Foundry facade needed to avoid an existing cold-import cycle.
Its canonical source, owner and removal condition are explicit. No new
orchestration package, authority engine, identity registry or Event Spine.

Founder source: `FOUNDER-DIRECTION-CMC-SCOPE-002.json`, including verbatim text
and content digest. Source authoring timestamp and opaque conversation/message
IDs were not exposed; they remain null, with the relay observation timestamp
separately labeled and a descriptive conversation reference. These missing
metadata are not inferred, authenticated or considered resolved.

## Mechanisms, mutations and exactly two passes

The original preregistration, mechanism cards, three mutations per imported
mechanism, eight-side control mapping and negative predictions are retained in
`CATHEDRAL_METABOLISM_EXPERIMENT.md`. The skills caused inspection and ownership
reconciliation before implementation, explicit preservation of the conventional
baseline, and bounded rather than unrestricted recombination.

The original DEC-CMC-001 was frozen at commit
`4ffa224de88a1a0ec976ae530274a96ad9abb5e6`.
The explicit founder scope change opened linked DEC-CMC-002, frozen at
`cbb1d277ec9082acecb82d8529f816bc17f70784`.
**Each has exactly two formal strengthening passes.** The second is a new
superseding decision, not a hidden third pass. Five documented role perspectives
were produced by one assistant; they are not five independent reviewers.

Retained primitives: checkpointed event replay, idempotent task identity,
bounded leases, content-bound evidence, independent appraisal, explicit
exception/pause, and controlled dissolution. Material changes include
proposal-only selection, reference-only authority, reconciliation instead of
blind redispatch, and preserving disagreement even at simulated closure.
No blockchain, live credentials, new model framework or broad agent hierarchy
was added. Record integrity is not source truth or founder authentication.

## Candidate mechanisms and measured comparison

The router compares all eight required families: no action/wait/refusal;
direct capability; single model/tool; existing workflow; static DurableWorkflow;
fixed specialists; human escalation; and OMNIMORPH temporary organization.
Only the direct and static audit paths were executed in simulation. Other
families have eligibility/rationale comparisons, not empirical performance data.
OMNIMORPH activation is prohibited. The direct Linker audit is selected for
this one declared-route question; static DurableWorkflow remains the strongest
conventional comparator and is preferred by the test rule for multiple tasks.

| Recorded simulated episode | Direct audit | Static comparator |
|---|---:|---:|
| Deliberate interruption after task submission | 1 | 1 |
| Audit invocations after restart and closure | 1 | 1 |
| Ledger entries at synthetic closure | 21 | 26 |
| Mission transition events | 8 | 8 |
| Actual model calls | 0 | 0 |
| Authenticated founder commands | 0 | 0 |
| Actual founder mission closures | 0 | 0 |

Both retain the same audit result and required dissent. The five-entry
difference describes this frozen case, not general superiority. Shell elapsed
times are recorded in `phase4/evidence/comparison.json`; they include startup
and do not establish p50/p95 latency, RTO/RPO guarantees or human time saved.
A test compares five manual harness advances with one automatic harness
advance to the same result. This is not a measurement of Alfonso's effort.

Complete hash-linked raw traces are retained as
`phase4/evidence/direct-simulation.jsonl` and `static-simulation.jsonl`.
They bind source snapshots and implementation digests. Synthetic identities,
leases, clocks and continuation are explicitly test fixtures. There is no
claim of real workload credential issuance or authenticated human acceptance.

## What the probe actually exercises

One immutable mission fixture and trigger flow through existing Standing
Cognition with two deterministic hypotheses, a proposal router, a real
read-only InstitutionalLinker audit, TaskFabric and independent fixed appraisal.
A subprocess exits deliberately with code 75 after submission. A new process
reconciles the submitted receipt without invoking the audit twice. It pauses
with one source-pin exception. Only a clearly synthetic test continuation can
advance the simulation. The normal rerun leaves the closed ledger unchanged.

Both manifest pins differ from inspected organ main heads. That is not proof
the pins are wrong: they may be intentional. Current-main interoperability and
actual organ execution remain unverified. No pin is updated automatically.
The evaluator checks the original source bytes and rederives the audit rather
than trusting worker prose. Its code separation is not privileged-host or
process security isolation. A hostile operator who edits the trusted verifier
or fabric is outside the demonstrated protection.

The selected interruption window is covered, not every possible crash window.
Other incomplete task states refuse and require reconciliation. No distributed
exactly-once, disk power-loss, malicious-host, all-window recovery or general
live-runtime safety claim is made.

## Files added and deliberately untouched

Added: `routing/mission_resolution.py`, `verifier/mission_audit.py`,
`governance/manual_direction.py`, `egregore/mission_commands.py`,
`contracts/manual-founder-direction.schema.json`,
`tests/experiments/cathedral_metabolism_probe.py`,
`tests/unit/test_cathedral_metabolism.py`, intent/deliberation/ownership
records and these evidence documents. The sole existing implementation edit is
the narrow `foundry/__init__.py` lazy import facade.

Intentionally unchanged: main, all organ repositories, runtime implementations
from #70/#87, EventSpine, TaskFabric, existing Standing Cognition, authority,
Consequence Gate, identity/agent registries, manifests/pins, model providers,
budgets/policies, CI workflow definitions, prior developmental competitors,
and the original unfinished OM-EXP-001 held-out experiment.

## Validation and negative evidence

See `phase4/evidence/validation.md` for commands actually run and exact final
results. The focused suite passed **36 tests in 5.31s** after an initial run
failed **8 tests, with 28 passing**. The first failure used the existing Standing
Cognition API incorrectly (ledger positional instead of keyword); its full
failure output is preserved, not relabeled as a pass.

The logged broader unit run has **1,256 passed and 3 failed**. The same three
seam-test failures reproduce on the frozen pre-implementation commit. They
remain unfixed and visible; the institutional verifier also reports FAIL.
Schema-reference and authority-singleton checks passed. Remote CI is not
represented as passed by this handoff.

Default Python initially could not import pytest. The old environment launcher
also referenced a missing interpreter. Existing installed Python-3.12 packages
were reused through PYTHONPATH; no dependency installation or credential work
was needed. Later actual passes close only that runner-availability gap.
The initial cold OMNIMORPH import exposed an existing Foundry import cycle;
the compatibility repair is tested in both import orders.

The first broader unit-suite invocation lost its final process result during
session handoff. It is **UNKNOWN**, not PASS. A separate logged rerun is the
only acceptable source of its final regression claim.

Evidence tiers: inspected-source facts = repository inspection; behavior and
counts = executed unit/subprocess simulation evidence; router generalization,
operational independence, founder-attention savings and organizational
intelligence = unproven hypotheses; authenticated founder acceptance, actual
CMC/VDM, autonomy, HARDENED, LIVE and production = not demonstrated.

## Rollback, dissent and continuation

Rollback: stop test invocation and retain the inactive draft branch/evidence.
No migration or live activation needs reversal. Do not delete losing paths,
failures or dissent; do not merge or deploy this slice automatically.

Kill/pause on scope ambiguity, missing source/evaluator evidence, integrity
failure, unauthorized command, authority expansion, unsettled obligations,
uncertain consequential effects, duplicated work or an attempt to label
synthetic direction as founder acceptance. Return NEEDS_FOUNDER_DECISION.
The direct and static outcomes are valid even though organization compilation
did not earn activation. One fixture cannot establish morphology advantage.

For Claude, Kimi, ChatGPT or another contributor: read latest scope record,
linked DEC-CMC-002, inspection ledger, frozen experiment and this handoff first;
check the dedicated branch and current PR heads before editing. Do not extend
the two frozen deliberations with a third pass. A new substantive decision
requires a linked record. Do not silently refresh input hashes or thresholds.

**Stop after the draft PR. NEEDS_FOUNDER_DECISION before any actual runtime
acceptance, cryptographic-authentication implementation involving authority or
credentials, activation, merge, deployment, external consequence or scope
expansion.** The manual-relay exception has not resolved that boundary.
