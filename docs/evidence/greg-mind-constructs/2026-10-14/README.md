# The Mind and Capability Genesis close one loop (2026-10-14)

Second leap under `INTENT-20261013-FRONTIER-LEAP-RECOMBINE`, built on #169 (the whole-machine
convergence branch, which already contains RECOMBINE from #164). One agent wrote, attacked and
reviewed this change. That is not independent peer review.

## Original deficit

The canonical path is Goal → Problem Geometry → Intelligence → Capability Formation → … → Goal
Resumption. On #169 the Intelligence → Capability Formation edge was open in four places:

1. **The deficit named nothing Genesis could build.** When the Competency Compiler (Layer 5) found no admitted method, its `CapabilityDeficit` named `cognition.<geometry>:<subgeometry>`. No Genesis route can form that, so every such mission ended as a founder ask, even when GREG could construct the needed function (`assignment.staffing`, `assignment.matching`, `project.crash`).
2. **The Mind could not use what Genesis built.** The compiler chose only among catalogued families and recipes, so an attached construction was invisible to it.
3. **Independent appraisal could not see formed capabilities.** The appraiser re-observes cognition with a registry built from built-ins only, so a correct mission closed through a construction was refuted (reproduced: verdict `REFUTED`, "CAPABILITY_DEFICIT != ANSWERED").
4. **Repair and the founder path stalled.**
   - A construction that faulted while the Mind used it was not attributed to the construction, so self-repair never ran.
   - When the founder attached the engine a construction needs, nothing ever formed the construction, because the step that reported the deficit does not repeat.

## Source mechanisms (inspected)

The existing GREG code, read on this branch:

- `greg/cognition/compiler.py`: candidates, ranking, deficit, execution;
- `greg/cognition/cortex.py`: `reason`, `registry_view`;
- `greg/missions.py`: `_observe`, `_self_repair`, `_blocker_resolved`, `_watch_while_blocked`, `_escalate_capability`, `_capability_ask`;
- `greg/appraisal.py`;
- `greg/genesis.py`: `restore`, `repair`, the `constructed` route;
- `greg/recombine.py`;
- `greg/console.py`: `_attachable`.

No external project was needed. Every mechanism used here already existed in the repository and was
connected rather than re-implemented. REA was not used, because the source was available and is the stronger evidence.

## Mechanism extraction, mutation, recombination

**Extracted primitives:**

- typed deficits;
- registry-gated eligibility, which the Mind already applies to cognition families;
- certificate-carrying constructions;
- the two-strike self-repair;
- founder-scoped `auto_attach`;
- idempotent asks keyed by scope;
- restore-time re-pinning.

**Mutations:**

1. **Recognition by declared inputs.** The deficit names a *constructible function* when the request carries a reduction's declared inputs (`recombine.fits`), instead of naming a geometry label.
2. **Constructions as candidates.** An attached, read-only construction is admitted as a compiler candidate (`CONSTRUCTED_VERIFIED`). It is invoked with its own manifest, and its problem-level certificate becomes the receipt's evidence.
3. **Fault attribution.** A fault inside a construction is attributed to that construction (`capability_fault`), not to cognition, so the existing repair machinery sees it.
4. **Read-only restore for the appraiser.** Restore gains `record=False`, so the appraiser can rebuild formed capabilities from a read-only ledger, re-pinning packages and reduction digests without writing anything.
5. **A one-shot unblock.** It fires when a construction's engine becomes attached, forms the construction at that moment, and opens a *new* ask naming it, because content-keyed deduplication would otherwise swallow the re-block.

**Recombined behaviour:**

1. The Mind recognizes a problem.
2. Genesis constructs the missing capability under founder scope.
3. The Mind answers with a certificate.
4. An independent process re-derives that answer.
5. Faults repair across levels.

None of the parts did this alone.

## Implementation

| File | Change |
|---|---|
| `greg/recombine.py` | `Reduction.epistemic_classes`; `fits(data)` |
| `greg/cognition/compiler.py` | `constructed_candidates`, `_run_constructed`, a constructible deficit (`function`, `constructible.chain`, `constructible.engine`, `search_order` including `constructed`), `CONSTRUCTED_VERIFIED` rank |
| `greg/missions.py` | `capability_fault` attribution in `_observe`; `construction_ready` unblock and forming the construction on unblock; `awaiting` asks in `_escalate_capability`; the engine listed as attachable in `_capability_ask`; self-repair in `_watch_while_blocked` |
| `greg/genesis.py` | `construction_engine`, `construction_ready`, `restore(record=False)` (`_restore_note`) |
| `greg/appraisal.py` | `_formed_registry`: the appraiser restores formed capabilities read-only |
| `greg/templates.py` | `compiled_question` (`compiled-question`): founder-signed scope for constructions |
| `tests/integration/test_greg_mind_constructs_capability.py` | five end-to-end tests on a real body |

## Authority

**Permitted:** the Mind uses a construction only while it is ATTACHED, read-only, and provided by
`composed:`. Attachment stays a founder act: a signed command, or a mission's signed
`allow_construction`, which names the construction pattern and its engine in the light cone and sets a
read-only `auto_attach`.

**Unchanged:**

- Unsigned missions construct nothing into service. They ask, first for the engine, then for the construction.
- The appraiser writes nothing.
- No answer creates authority (`authority_created: false`).

**Note for reviewers.** A construction attached for one mission is usable by the Mind for any
mission that may call `cognition.solve`. That is the same rule as every other attached cognition family
(attachment is a founder-level act), and it is stated here so it can be reviewed.

## Evidence

All end-to-end tests below run on a real `Body`, with signed missions, real NetworkX and SciPy engines, and the real appraiser:

1. **Signed construction scope.** Deficit names `assignment.staffing`; Genesis acquires the max-flow engine and constructs; the Mind answers (8 of 9 staffed, bottleneck Dock1/Dock2 with a certificate); the mission is ACHIEVED; the independent appraisal is **VERIFIED**.
2. **No signed scope.**
   - The block names `assignment.staffing`, and the ask lists the engine as attachable.
   - The founder attaches the engine, the construction is formed and stays VERIFIED (never self-attached), and a new ask names it.
   - There is exactly one unblock (no churn). The founder attaches the construction, and the mission is ACHIEVED.
3. **The engine lies after attach.** The Mind's receipt carries the `capability_fault`. The two-strike repair quarantines the construction and the engine, re-forms the construction over SciPy, and the mission is ACHIEVED. No lie became an answer.
4. **No reduction fits.** The behaviour is unchanged: the deficit is `cognition.optimization:protein folding`, and nothing is pre-authorized.
5. **Detached construction.** It is never used by the Mind.

Negative results found while building (each fixed, each now a test):

- appraisal refutation of correct closures;
- the stalled founder path;
- content-keyed deduplication silently dropping a re-block;
- no repair while blocked.

## System impact

GREG's Mind can now hand a problem it cannot solve to Capability Genesis, *in a form Genesis can
build*, and solve it once the construction is admitted. The closure is independently re-derivable. This is the first
working Intelligence → Capability Formation → Intelligence edge on the canonical path.

## Classification and continuation

**BUILDABLE**, as implemented. The general capability, "the Mind forms any missing epistemic function", is
**EXPERIMENTAL**: coverage is bounded by the reduction library (three functions). Next:

1. Reductions chosen by missions that real founder goals need.
2. A words front end for compiled questions.
3. Goal Gravity (#160, joined in #169) waking a compiled question when its inputs change.
4. Measuring VPL on a family only construction serves.
