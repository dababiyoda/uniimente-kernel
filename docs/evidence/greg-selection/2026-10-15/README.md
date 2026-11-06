# Portfolio decisions under prerequisites, and capability formation as Goal Gravity perception (2026-10-15)

Third leap under `INTENT-20261013-FRONTIER-LEAP-RECOMBINE` (directive re-issued 2026-10-15), built on #175
(the #173 convergence line with governed recovery). One agent wrote, attacked and reviewed this change. That
is not independent peer review.

## Original deficits

1. **No certified answer to "which projects to take when some require others".** GREG could staff, match and
   crash schedules (RECOMBINE). It had no function for the decision a founder makes most often: which offers,
   projects or investments to fund when some depend on shared prerequisites. A greedy rule ("take what pays
   on its own") misses exactly the profitable cases. Example: two offers each lose money alone but share a
   platform, so together they earn.
2. **A capability change was invisible to Goal Gravity.** A founder-signed goal bound to a mission that was
   blocked on a missing capability stayed asleep after that capability was formed, recovered or attached.
   It woke only on mission observations, intake or its review cadence. Capability Genesis and Goal Gravity
   were two loops that did not see each other.

## Source mechanisms (inspected)

| Source | What was taken |
|---|---|
| Picard, *Management Science* 22(11) (1976); Rhys, and Balinski, *Management Science* 17(3) (1970) | Maximum-weight closure as a minimum cut: profit source arcs, cost sink arcs, uncuttable requirement arcs |
| Ford & Fulkerson (1956) | Max-flow/min-cut duality |
| This repository: `greg/recombine.py`, `greg/genesis.py`, `greg/cognition/network.py`, `greg/goal_gravity.py`, `egregore/relevance.py`, `egregore/gravity.py` | Reduction contract, chain compiler, max-flow certificate, the body sensorium (`_sense`), wake scoring |

REA was not used. The mechanisms are published mathematics and repository source, which is stronger
evidence than binary reconstruction.

## Mechanism extraction, mutation, recombination

**Selection.**

- **Kept primitive:** the Picard network.
- **Mutation, certificate transport:** the engine's maximum flow is read back as *funding*, meaning which
  profitable item's value would have to pay for which costs. GREG then re-proves it from the original items
  alone:
  1. the chosen set is closed under its requirements;
  2. the funding is a feasible flow along requirements only;
  3. profit equals total profit minus funded value. By weak duality, that bounds every closed set.
- **Result:** the answer explains itself. "Pilot is left out: its whole 3 would go to the Lab it needs (cost 5)."

**Perception.**

- **Kept primitive:** the sensorium's rule that only ledgered, Gate- or Genesis-derived changes become
  observations.
- **Mutation:** a capability state change (formed or recovered = VERIFIED, ATTACHED, QUARANTINED, DETACHED)
  becomes an observation about every open mission blocked on that function, or on a construction whose
  engine provides it. The observed value is the state itself, so each transition is a distinct change.

**Recombined behaviour:**

1. Capability formation, recovery or a founder attach wakes the goal that was waiting on it, on the next turn.
2. The awake goal pulls its missions' timing.
3. The new portfolio function is one such capability, constructed by Genesis over an engine GREG already
   qualified.

## Implementation

| File | Change |
|---|---|
| `greg/recombine.py` | `normalize/encode/decode/certify_selection`, `direct_selection` (nothing profitable: proved with no engine), `selection_brute_force`, `oracle_selection`, reduction `selection-via-maxflow` with its Mechanism Card |
| `greg/goal_gravity.py` | `_sense` reads `greg.capability.registered` / `greg.capability.state`; `_blocked_on`; `CAPABILITY_USABLE` |
| `scripts/qualify_recombine.py` | selection included in the reuse measurement |
| `scripts/ci/check_cortex_mutants.py` | 3 selection mutants (recombine group); new "capability perception" group (3 mutants) |
| `tests/unit/test_greg_recombine.py` | 5 selection tests, including a signed mission on a real Body and the Mind recognizing a portfolio question |
| `tests/integration/test_greg_capability_wakes_goal.py` | goal wakes on attach and on formation, with no authority created; the blocked-on rule |

## Authority

- Selection is read-only. It answers a question and commits no money; nothing is funded, bought or signed.
- Waking is timing only. The test shows that after the wake the construction stays VERIFIED; only the founder
  attaches it, or a signed read-only `auto_attach` does. Guardian and Treasury are untouched.

## Evidence

- **Tests:** `tests/unit/test_greg_recombine.py` 24 passed; `test_greg_capability_wakes_goal.py` 2 passed.
  Goal Gravity, recovery, Mind-construction, recombine, packaging and First Mission suites: 165 passed. The seed
  genome frozen inputs are unchanged.
- **Mutants:** 6 new, all caught locally. 110 cortex mutant patterns, none stale.
- **Stress (`results.json`, 60 seeds, Python 3.11.15, NetworkX 3.6.1, SciPy 1.17.1):**
  - `selection.closure`: 720 cases per engine; 133 proved without an engine; 587 through NetworkX and 587
    through SciPy; 0 wrong, 0 refused.
  - Constructing it over the already-qualified engine took 0.23 s for 12 oracle cases, with no re-qualification
    and no new solver code.
- **Negative results:**
  1. The first fixture meant to show a shared prerequisite did not show one (its optimum was 0). It was corrected.
  2. The first perception design observed a boolean "usable". The founder's attach then changed nothing,
     because the engine was already VERIFIED, so the goal did not wake. It now observes the state.
- VEPMC 0. No founder use, no external outcome.

## Classification

- **BUILDABLE**, as implemented.
- "GREG notices every change that makes a goal feasible" is **EXPERIMENTAL**. Coverage now includes capability
  changes, mission observations, intake and the developmental path, but not yet external world events beyond
  intake.

## Continuation

1. Recovery probes for builder-made and CLI capabilities.
2. A words front end for portfolio questions.
3. Goal plans that name a constructible function, so a goal can *request* formation rather than only wake
   on it.
4. Measuring founder attention saved across a long-running body.
