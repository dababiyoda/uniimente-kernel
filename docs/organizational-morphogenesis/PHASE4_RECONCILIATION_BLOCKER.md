# Bounded reconciliation inspection — evaluator hard stop

Continuation: Alfonso subsequently authorized the narrow repair. The original
counterexample below is preserved unchanged as negative evidence; it is not
an outstanding request for the same authorization. See
`CMC_002_REPAIR_RECONCILIATION.md` and the latest `PHASE4_HANDOFF.md` section
for the repaired, simulation-only combined tree and current test results.

Status: **NEEDS_FOUNDER_DECISION**. Recorded observation: 2026-09-05T13:45:29Z.
No branch update, reconciled implementation commit, draft PR, merge, deployment,
activation, credential or external effect occurred in this continuation.

## Authorization and inspected versions

The latest visible founder ruling permits bounded reconciliation of 62b7b01
with preserved local work. It explicitly requires a pause if reconciliation
reveals a missing evaluator, authority leak, unsafe retry or incomplete lineage.
That ruling does not authorize treating manual direction as runtime authentication.

Local HEAD remains cbb1d277ec9082acecb82d8529f816bc17f70784 with the previously
prepared local implementation/evidence preserved. The remote branch had advanced
from the originally identified 62b7b0116f3c0fd57397f327eae26e166a358b82 to
3e0f489c07e1fc89d3f3b3ad5779398e2045eb98 when refreshed for reconciliation.

Inspected at 62b7b01: complete mission compiler and mission-resolution schema.
Inspected at 3e0f489: changed-path/stat inventory; mission selector; runtime
composition export; mission-runtime source including submit/verify/replay
boundaries; its integration tests; the concurrent founder-intent record.
Some whole-file tool output was truncated; decisive methods were reread
separately. This is not an exhaustive audit of the new runtime.
GitHub connector also confirmed PR #92 remains open and draft.
No claim that its current head or the shared remote branch will remain static.

The additional remote work includes egregore/cathedral_runtime.py,
egregore/mission_resolution.py, runtime composition, and their tests. Neither
remote line was altered, force-pushed, deleted or silently replaced.

## Confirmed missing protected appraisal

At 3e0f489, CathedralMetabolismRuntime.verify_task:
- checks nonempty evidence/dissent reference strings;
- checks that the chosen verifier identity string differs from worker/coordinator;
- accepts a caller-supplied accepted boolean, defaulting to true;
- computes an assessment digest locally and transitions the task to VERIFIED;
- does not resolve those reference strings or invoke an independent evaluator.

This differs materially from the preserved local probe's fixed source-byte
appraisal. A different identity string does not establish that an independent
appraisal occurred. The problem is not a request to build cryptographic identity:
the missing step is actual protected evaluation of the submitted evidence.

**Executed counterexample:** in an isolated copy of the pinned remote source,
a fabricated result with evidence:DOES_NOT_EXIST and dissent:DOES_NOT_EXIST is
accepted by verify_task with another evaluator identity and accepted=True.
The safety assertion expecting refusal fails. The control asserting refusal of
the worker's own identity passes: **1 failed, 1 passed in 0.54s**.

The mission and identities are synthetic and use an in-memory EventSpine.
No real runtime was activated; no provider, money or external consequence ran.
This demonstrates a simulation protocol defect, not a live exploit or proof
that any actual mission or external action occurred.

## Exact diagnostic environment and retained evidence

Archive:
git archive 3e0f489c07e1fc89d3f3b3ad5779398e2045eb98 | tar -x -C /workspace/scratch/c1c408c41c36/tmp/cmc-reconciliation-inspection.cIk3eq

Initial command from that archive:
PYTHONPATH=/workspace/scratch/c1c408c41c36/tmp/phase3-venv/lib/python3.12/site-packages python -m pytest tests/integration/test_cathedral_metabolism_runtime.py -q

Result: collection error, exit 2, in 0.50s. Existing Foundry/OMNIMORPH cold-import
cycle: cannot import GateActivationReceipt from partially initialized omnimorph.
No implementation repair was applied to the archive. Instead the diagnostic
pre-imported foundry to expose runtime behavior despite the import-order defect:

PYTHONPATH=/workspace/scratch/c1c408c41c36/tmp/phase3-venv/lib/python3.12/site-packages python -c 'import foundry; import pytest; raise SystemExit(pytest.main(["tests/integration/test_reconciliation_evaluator_boundary.py", "-q"]))'

Result: exit 1; 1 failed, 1 passed in 0.54s.
Test source: phase4/evidence/evaluator-boundary-test.py.txt.
Raw output: phase4/evidence/evaluator-boundary-negative.txt.
The added diagnostic test is the only archive change; runtime source is unmodified.

The earlier 36-pass focused result and 1256-pass/3-fail broad result remain
historical local-tree evidence. They are NOT reconciled-tree results.
No reconciled tree was admitted for broad testing because this hard stop fired.

## Ownership disposition and bounded next decision

The founder's owner map remains governing: contracts own shared meaning;
OMNIMORPH owns subordinate capability/organization compilation; mission routing
owns higher-order selection; egregore owns persistent metabolism; existing events
own transition truth; verifier/provenance own appraisal/evidence; Kernel/Gate
alone own authority/consequence.

No canonical choice between the two selector implementations was silently made.
Both remain preserved pending the protection boundary being resolved.
No new two-pass architectural deliberation was finalized; this is a diagnostic
hard-stop record, not a third pass on a prior decision.

Recommended narrow follow-up ruling: permit reconciliation to replace the
caller-asserted verification path with mandatory protected appraisal of retained
result/source evidence, binding mission/task/result digests and preserving
dissent. Keep the old implementation in history as failed evidence. Reject
missing or forged appraisal; do not add authentication, authority or effects.
Then rerun this negative control, focused tests and broad suites before draft PR.

Actual Cathedral Metabolism Closure remains 0. VDM, authentication, autonomy,
HARDENED, LIVE and organizational superiority are not established.
Rollback is stop and retain the unchanged branch plus local evidence.
