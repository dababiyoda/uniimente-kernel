# I.G7 design record: an acceptance verdict the code under test cannot decide

Status: design chosen, not built. Gap: `acceptance/missions.json` Mission I, G7. Source: a design workflow on
2026-10-15 (three independent designs, a maintainer judge; the research agent, the attacker judge and the
synthesis were stopped by the model provider's safeguards and produced nothing, so this record rests on the
designs and the maintainer judge only).

## The problem

`worker.appraise` (greg/workers.py) re-runs a worker's patch against the order's acceptance commands and reads
their exit code. The patched code is imported by those commands and runs inside the same pytest process that
reports the result, so nothing that process reports can be trusted against code running in it. A change built to
end the process early, or to alter the runner's reports, can turn a failing run into a passing exit code.
File-level substitution of the evaluator (editing a named test, adding a `conftest.py`) is already refused (I.G6).

## Already landed

- fbb1a01: GREG's own acceptance runs of a worker's patch, in commission and in the appraisal, are confined like
  the worker (Landlock: the clone writable, the runtime read-only). Before, they ran with only the network
  isolated, so the patch's code could reach the Body home when GREG ran it. This was found by the maintainer
  judge and confirmed by a probe; it narrows what a patch can reach, not what it can make the verdict say.

## Chosen design (Angle B, with four grafts)

1. **Two processes, data only between them.** The frozen tests run in an ordinary pytest session in a parent
   that never executes the worker's bytes. The patched code is imported only in a confined child, fresh per test
   item. The parent reaches it through an import finder that turns in-repository imports it cannot satisfy from
   the base snapshot into held modules; calls cross as JSON of exact builtin types (None, bool, int, float, str,
   bytes, list, tuple, dict with str keys). Anything else stays in the child as an opaque handle, and a handle
   never decides a comparison, truthiness, ordering, membership, hashing or type check: such a test is reported
   UNCOVERED, never passed.
2. **The trust boundary is the worker-writable surface.** The parent's snapshot is the base tree minus the
   order's `allowed_paths`, plus the frozen evaluator (named targets, their directories, the base conftest files
   on their path, root runner configuration). Base helpers outside the writable surface therefore run in the
   parent from base. The child's view is the patched tree minus the frozen evaluator and minus `.git`.
3. **Positive per-test evidence.** ACCEPTED needs a results record written by the parent: every frozen item
   collected and passed, two nonce canaries reported correctly (one must pass, one must fail). Exit codes can
   only reject. A lost child, a timeout or a refused operation is an oracle event that a frozen
   `except Exception` cannot absorb; a skip counts only when it comes from a frozen marker evaluated in the
   parent.
4. **Both processes confined (graft from Angle A).** The parent: the runtime and its snapshot read-only, its
   results directory and pytest's base temp writable. The child: its view read-only plus a per-test scratch
   directory, signal and abstract-socket scoping where Landlock ABI >= 6 allows. Handles carry the child
   generation and a stale one is refused.
5. **Measured coverage (graft from Angle C).** Run the oracle over this kernel's own suite and record how many
   tests it holds, how many are UNCOVERED and why, so the coverage claim is measured rather than asserted.

Verdict rules, in order: oracle incomplete or a canary misreported: REJECTED. Any frozen item failed, skipped
from the child, or missing: REJECTED. A worker-authored or unholdable command failed: REJECTED. Still accepted
but some tests UNCOVERED or a command could not be held: NEEDS_FOUNDER_DECISION, naming each. The in-process
run stays as secondary evidence (`independent_tests`, schema unchanged); new keys `held_tests` and
`acceptance_basis`.

Size: about 520 lines of production code (`greg/acceptance_oracle.py`, `greg/acceptance_child.py`, small
changes to `greg/isolation.py`, `greg/capabilities.py`, `greg/workers.py`) and about 350 lines of tests. The new
files and the changed ones are protected surfaces, so the change goes through founder-authorized review.
`worker.appraise` stays read-only; no authority is created.

## Rejected alternatives

- **Angle A** (a judge that holds only the named tests, a zygote forking per-test hosts): its trust boundary
  sits at "named tests versus everything else", so an unnamed base helper inside the writable surface could be
  forged; more machinery (uid drop, descriptor passing) for less security than B.
- **Angle C** (judge-style input/output checking): the most honest on what it judges, but a static census found
  it can hold about 0.6% of this kernel's own tests (0.2–3.1% across eight suites). Its held-out mechanism is
  kept as the candidate for the new gap below.
- **In-process canaries and a results pipe only** (B's own cheapest prototype): catches early exits and generic
  report patching, but code in the same process can always target the plugin itself.

## Residuals to record when it lands

- Authoring-time special-casing of visible frozen tests is not excluded: the worker sees them in its clone. A
  held-out set the worker never sees is the remedy (new gap I.G8).
- Orders accepted only by tests the worker wrote (`run_changed_tests`) have no independent judge; they stay
  exit-code, now confined, labelled. Whether they may still be ACCEPTED automatically is a founder decision.
- Shapes the oracle cannot hold give NEEDS_FOUNDER_DECISION, never ACCEPTED.
- Expectations computed by the code under test, or kept inside the writable surface, are forgeable by
  construction.
- Hosts without Landlock ABI >= 6 get the process split without filesystem confinement or signal scoping, and
  say so; the corresponding tests skip, and a skip is not a pass.
- The trusted computing base is the interpreter, pytest and its installed plugins, and the base configuration.

## Why it is not built yet

Its acceptance tests are, necessarily, patches written to defeat an evaluator. While designing it, the model
provider's safeguards stopped three agents and one of this session's own test drafts. Building it needs either
an environment where that test corpus can be written and reviewed, or a human author for the hostile fixtures.
That is recorded as the gap's dependency; the design itself does not change.
