# closure

Orthogonal loop closure — the exact standard the builder uses.

Two instruments:

- `framework.py` — **five orthogonal closures per module**: technical,
  authority, evidence, economic, regenerative. A module is complete only
  when all five close. A module passing only technical tests is not
  finished. Registrations live in `kernel_registry.py`; checks are real
  (they compile, issue, sign, execute, tamper, and verify).
- `whole_body.py` — **Whole-Body Closure Controller**: evaluates each
  proposed change across the 13 institutional loops (reality, epistemic,
  strategic, architectural, authority, execution, commercial, distribution,
  autonomy, regenerative, capital, continuity, meta-improvement) as
  `CLOSED`, `PARTIALLY_CLOSED`, `FALSELY_CLOSED`, or `OPEN`.
  **FALSELY_CLOSED** — internal metric satisfied without the intended
  external consequence — triggers investigation and regression.

## Buildability standard (14 conditions)

- **Existing mechanism**: executable check registry + verdict state machine.
- **Defined interface**: `ClosureRegistry.verify() -> (bool, reports)`; `WholeBodyClosureController.evaluate/applicable`.
- **Bounded authority**: judges; never executes or promotes by itself.
- **Available dependencies**: Python 3 stdlib + kernel modules under test.
- **Security model**: a crashing check fails closed; verdicts derive only from registered evidence.
- **Failure modes**: unregistered closure → fail; exception in check → fail closed with detail.
- **Acceptance tests**: `tests/unit/test_closure.py`, `tests/unit/test_whole_body.py`.
- **Recovery path**: re-run; closures are pure evaluations over current state.
- **Resource ceiling**: bounded by registered checks; each check self-limits.
- **Operating cost**: one full pass in seconds, reported per closure in ms.
- **Legal operator**: Alfonso (closure reports are evidence for his ratification decisions).
- **Handoff state**: reports are JSON-serializable; `verifier/runs/` preserves every run.
- **Replaceable**: new closures register without changing the framework.

## Orthogonal closures

The closure framework verifies itself: `test_closure.py` requires every
registered kernel module to close all five closures.
