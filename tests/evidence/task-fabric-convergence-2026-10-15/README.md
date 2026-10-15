# Section 16 Task Fabric on the converged Mind — 2026-10-15

Directive section 16: "Integrate with ... existing Task Fabric, Worker Leases, evaluator, and orchestration
contracts" and "DALEOBANKS may consume cognitive results for truthful research ... Never publish, message others,
spend, or activate live accounts solely to demonstrate integration."

**Lineage:** the third byte-identical repeat of the Seed Genome directive (2026-10-15T12:21:07Z), already recorded
in `docs/intent/sources/GREG-SEED-GENOME-DIRECTIVE-REISSUE-2026-10-13-source.md`. This residual was named open in
the requirement map ("Task Fabric/leases").

## The existing mechanism

GREG's Task Fabric is `worker.commission`. One WorkOrder becomes one lease (`lease.json`): a short-lived passport
for a temporary worker under a single Kernel grant. Its independent evaluator is `worker.appraise`, which works on
a fresh clone with the patch re-applied, rechecks scope and protected surfaces, and re-runs acceptance. The
`daleobanks_post` and `research_post` missions use a document-mode order: a worker drafts a post from a source,
and DALEOBANKS verifies it before the publish request.

## The defect, reproduced first (`reproduction.log`, at the pristine base `b8626600`)

- `worker.appraise` ACCEPTED a document order whenever the deliverable file existed. A draft that dropped its
  source's hedge, or removed a negation, was ACCEPTED.
- `daleobanks_post`: those same drafts passed `draft_verified` (DALEOBANKS's own checks plus figures against the
  source), and the mission moved on to the publish request. Only the light cone stopped it there: publishing is
  external contact and waits for a founder decision.

The media case (#183) could not reach this path, because it needs every claim declared when the mission is signed.
A worker writes its draft after signing.

## What was built (`e7feee67`, hardened in `2f468014`)

| Where | Change |
|---|---|
| `greg/cognition/restatement.py` | The sentence-by-sentence rule, moved here from `daleobanks_bridge` and re-exported under its old name: every sentence must be a claim the evidence family answered as written. It now names the Mind's own reason when the Mind answered nothing (for example, a quote the input lacks); before, it said "not a sentence of this draft". |
| `greg/workers.py` | A document order may carry `bound_claims`: `{"claims": file, "quality", "expires_at"}`. Quality and freshness are the signer's declaration, never the worker's. The contract is validated before any worker runs. The lease records the contract and names its evaluator. The worker is told to list each sentence with its supporting input spans. |
| `worker.appraise` | Asks the Mind about every sentence (`cognition.evidence` through the canonical `reason()` entry). The inputs are **GREG's copies at the base commit**, made before the worker ran, never the worker's tree. The Mind runs **through the body's registry**, so a quarantine holds. A contract signed into the mission's sensor params applies over the recorded one, and a record that differs from it is rejected. The full receipts travel in the appraisal's Gate receipt, on the canonical ledger. |
| `greg/missions.py` | `worker.appraise` gets the body's registry view and no ledger. |
| `greg/templates.py` | `daleobanks_post` signs the contract by default, and so does `research_post`, which builds on it. The publish request requires `draft_appraised`. `bound_claims=False` reproduces the old mission byte for byte. |

### Found re-reading the change before pushing (`2f468014`)

- **A pre-existing crash:** `commission` collected the worker's diff as locale-decoded text, so a worker that wrote
  non-UTF-8 bytes crashed the adapter. Reproduced at `b8626600`. The patch is now collected as the bytes that
  `change.patch` and its digest already hold.
- **Decoding:** GREG decodes its copies of the inputs as UTF-8 itself, not in the body's locale. A deliverable,
  claims file or input that is not UTF-8 text is a finding, never an exception.
- **A malformed signed contract** is rejected, never used.
- **Inputs:** `bound_claims` needs at least one input, each with its own file name, because two inputs with one
  name collide in GREG's copy.

## On the real DALEOBANKS checkout (`real-daleobanks-missions.log`)

- **DALEOBANKS:** checkout `a8341ba`, read only. Its own EthicsGuard, Critic and PromptFirewall ran in their own
  process. The checkout was left clean.
- **The worker:** a scripted test double that writes fixed files.
- **The source:** a synthetic three-sentence summary.

| Draft | DALEOBANKS's own checks | `draft_verified` | The Mind (`worker.appraise`) | Publish request reached | Mission |
|---|---|---|---|---|---|
| faithful (two claims) | pass | VERIFIED | ACCEPTED | yes, held for the founder | WAITING |
| hedge dropped | pass | VERIFIED | REJECTED: certainty | no | BLOCKED |
| negation removed | pass | VERIFIED | REJECTED: negation | no | BLOCKED |
| scope widened | pass | VERIFIED | REJECTED: scope | no | BLOCKED |
| direction reversed | pass | VERIFIED | REJECTED: direction | no | BLOCKED |
| name substituted | pass | VERIFIED | REJECTED: named term | no | BLOCKED |
| a sentence no binding covers | pass | VERIFIED | REJECTED: uncovered text | no | BLOCKED |
| no claims file | pass | VERIFIED | REJECTED: nothing checkable | no | BLOCKED |

DALEOBANKS's own checks passed all eight drafts. What held back the seven is the Task Fabric's evaluator asking the
Mind. Each worker ran once. A rejected draft blocks the mission truthfully ("no admissible strategy") and does not
trigger a second paid draft; a re-draft is a new signed mission.

## Verification

- `fabric-tests.log`: `tests/unit/test_greg_task_fabric.py`, 36 passed with the real checkout set
  (`GREG_TEST_DALEOBANKS`). Without it, the one real-organ test skips.
- `mutants.log`: 45 of 45 caught. Ten target this change:
  - the evaluator never asks the Mind;
  - the inputs are read from the worker's tree;
  - the signed contract is not compared with the record;
  - the record's contract replaces the signed one;
  - the evaluator ignores the body's registry;
  - the engine hands the evaluator no registry;
  - the lease omits what the worker is judged by;
  - the publish request skips the appraisal;
  - a worker's non-text bytes crash the commission;
  - GREG's copy of an input is read in another encoding.

  The two media mutants whose code moved into `restatement.py` were retargeted, not dropped.
- `test_greg_bindings.py`: its assertion on `research_post`'s publish precondition was updated to the stronger one,
  `["draft_verified", "draft_appraised"]`.
- `full-suite.log`: at `2f468014`, 3859 passed, 5 failed, 25 skipped. The five are the environmental Landlock tests (a confined child's `PermissionError` in `site.py` with this session's venv). They fail identically at the base `b8626600` (`environment-failures-at-base.log`) and pass in CI.

## Limits and what is not done

- **No real frontier worker ran.** A Claude Code worker spends under its budget cap, and no spend is authorized
  here. A real worker's ability to write correct bindings is unmeasured.
- **The worker is not OS-sandboxed** (a pre-existing, stated limit). The defences that do not depend on it are
  three: the inputs are read from the base commit, the contract is signed into the mission, and the mismatch with
  the record is rejected.
- **Inherited from the refuter:** a flag can be a legitimate rewording, and antonyms and magnitude go unseen.
  Finding no change is not entailment.
- **Not covered:** repository work orders are not judged by the Mind; multilingual explanation and audience
  feedback need a permitted local model.
- **No live use.**

Nothing was posted, sent, spent or activated. Authority delta:
- the evaluator reads the body's registry, which it does not write;
- the publish request needs one more check;
- VEPMC: 0.
