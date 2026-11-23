# A goal can ask for a capability, not only wake on one (2026-10-15)

Fourth leap under `INTENT-20261013-FRONTIER-LEAP-RECOMBINE`, stacked on #187 (`selection.closure` and
capability perception). One agent wrote, attacked and reviewed this change. That is not independent peer
review.

## Original deficit

A founder-signed goal's plan node could already declare `requires_capabilities`. A missing one only became
a recorded `capability` deficit on the goal (`egregore/gravity.py`), and nothing formed it. Capability
Genesis ran only when a mission step hit a missing function. So a capability a goal needed, which no
mission step had reached yet, was never formed. The goal stayed blocked until the founder noticed and
built or attached something by hand.

## Effect (falsifiable)

When a woken, admitted, unstopped goal's active plan node requires `<function>@function`, and no usable
implementation exists:

- GREG forms the function in the sandbox under the first open, unpaused mission the goal binds.
- Each verified result waits for the founder's signed `CAPABILITY_ATTACH`.
- The goal perceives each step: engine formed, engine attached, construction formed, construction attached.
- The goal's deficit closes once an attached implementation serves the function.

Falsified if any of the following happens:

- the goal attaches something;
- the goal commissions a builder or spends a build budget;
- the goal blocks its mission;
- a stopped goal asks;
- the deficit closes without an attached implementation.

## Existing mechanisms reused (nothing new as architecture)

| Mechanism | Where |
|---|---|
| Plan-node `requires_capabilities` and GPS missing-capability fix | `egregore/goals.py`, `egregore/gps.py` |
| The Genesis ladder (attached → verified-detached → constructed / package / installed → builder → founder) | `greg/genesis.py resolve` |
| RECOMBINE constructions and their engines | `greg/recombine.py`, `_recombine_route` |
| Capability perception in the body sensorium | `greg/goal_gravity.py _sense` (#187) |
| Founder attach surface (`attach_waiting` from `deficit.awaiting_attach`) | `greg/body.py`, `greg/console.py` |

The residual deficit was small. It needed:

- a function-level requirement (`<function>@function` present iff any implementation is usable);
- a form-only mode of `Genesis.resolve` (`form_for_goal`);
- the call from a woken goal (`_form_requested`);
- perception of goal-requested formations (`_goal_formations`);
- deficit closure on attach (`_close_goal_formations`).

## Authority envelope

`Genesis.form_for_goal` forms only. While it runs:

- `_attach` records `deficit.awaiting_attach` and attaches nothing, even when the mission's own signed
  read-only `auto_attach` would cover it. The test signs such a mission adversarially.
- `_attach_dependency` attaches no engine.
- `_builder_route` refuses before any builder or build budget is touched.

The goal never blocks its mission. GREG installs nothing on this path, as before. A function that only a person may perform
(`asks.human_work`), one Genesis cannot form without a builder, a revoked requirement, a stopped or
unadmitted goal, and a goal with no open mission are all left alone. Authority delta: none.

## Evidence

- `tests/integration/test_greg_goal_requests_formation.py`: 4 tests.
  - The full real-body sequence: a standing note mission that never uses `selection.closure`, plus a goal
    requiring it.
    1. GREG asks and acquires the max-flow engine, which waits for the founder.
    2. The founder attaches the engine, and the goal wakes.
    3. GREG forms the construction, which waits for the founder.
    4. The founder attaches the construction, and the deficit resolves with `resume: goal <id>`.
    5. The requirement reads present.
  - Fake-based skip conditions.
  - Function-level presence.
  - No builder: a builder and a signed build budget are present, the builder is never touched, and nothing
    is built.
- Mutants: group `goal-requested formation` in `scripts/ci/check_cortex_mutants.py`. All 6 are caught:
  - attach via auto_attach;
  - builder commissioned;
  - formation not perceived;
  - deficit never closes;
  - function requirement never present;
  - stopped goal asks.

  There are 116 patterns in total and none is stale.
- Neighbouring suites: goal gravity, genesis, recombine, recovery, capability-wakes-goal and the Mind
  construction suites. 288 tests passed locally.

## Known limits

- Formation runs only on a turn where the goal woke. A goal that never wakes asks nothing (by design: timing
  follows the goal's own wake conditions and review cadence).
- The founder's attention saved is not measured here. The founder still signs two attaches when the engine
  is absent. That is the same number as on the mission path, and it now happens before any mission step
  needs the function, not after one fails.
- Classification: BUILDABLE (built and tested here). VEPMC: 0. No external effect was produced.
