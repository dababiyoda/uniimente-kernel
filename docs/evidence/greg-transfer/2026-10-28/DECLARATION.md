# Does earlier competence make a later, different mission better? Transfer-test declaration (2026-10-28)

**Status: declared and committed BEFORE any instance of namespace `greg-transfer-2026-10-28` was generated.** The
executable form is `scripts/greg_transfer_eval.py` (`CRITERIA`, `summarise`), committed in the same commit as this
file and `tests/integration/test_greg_transfer_eval.py`. Nothing below changes after the run. If a prediction fails,
the failure is recorded and neither the harness nor GREG is tuned against these instances.

**Authority:** the founder directive of 2026-10-28 ("UNIIMENTE / GREG: TRUE ABSOLUTE OPUS MAXIMUS"):
- section 9C asks to prove transfer, comparing replay with the same family and with a different family;
- section 11 sets the learning test: "a later appropriately different mission performs better because earlier work
  left behind valid competence".

The claim is recorded on board #96. Authority delta: none. The founder key in this run is a per-run test key, not
Alfonso's. Nothing is sent, published, spent, merged or decided.

## 1. The effect and the residual deficit

- **Effect sought:** a capability GREG formed for one mission makes a later mission cheaper in founder attention and
  in construction work. The later answer must still be correct and certified, and no authority may be gained.
- **What exists:**
  - Capability Genesis forms and qualifies a construction (`greg/genesis.py`, `greg/recombine.py`) and registers it.
  - The founder attaches it.
  - The Competency Compiler routes later problems to attached capabilities.
- **What no test has measured:** whether a second, *different* mission on the same body actually reuses the first
  mission's competence. Reuse would show as fewer asks, no repeated qualification and no repeated deficit. Nor has
  any test measured whether that reuse extends across problem families, or whether it stays correct and inside
  authority.

This experiment measures exactly that, on the canonical mission path, against a body without the earlier mission.

## 2. Arms

For every hidden task, two fresh bodies are built (`tests/greg_fixtures.make_body`, fake clock):

| Arm | What it runs |
|---|---|
| experienced | first ONE construction mission, then the task mission |
| control | only the task mission |

**The construction mission** asks the fifteen-step mission's staffing problem (`CONSTRUCTION` equals
`tests/integration/test_greg_mind_constructs_capability.STAFFING`, asserted by a test). The Mind compiles it, and
Genesis forms `graph.max_flow` and the `staffing-via-maxflow` construction.

**Both missions** are `compiled_question` missions on the canonical path: Competency Compiler, Capability Genesis,
the appraiser and the ledger.

**The founder's answers:** the test founder answers every `CAPABILITY_ATTACH` ask by signing an attach of exactly the
VERIFIED capabilities the ask names. It answers nothing else and attaches nothing unasked.

**The only manipulation is the earlier mission.**

## 3. Tiers, sizes and instances

| Tier | n | Function | Instances |
|---|---:|---|---|
| replay | 1 | `assignment.staffing` | the construction problem itself |
| same_family | 12 | `assignment.staffing` | `staffing_instance`: 2-4 workers, 2-4 orders, 2-3 skills |
| cross_family | 12 | `assignment.matching` (reduces through staffing onto max flow) | `matching_instance`: 2-5 per side |
| unrelated | 12 | `project.crash` (LP engine) | `crash_instance`: 2-4 tasks, deadline at or below the normal length |

- **Generation:** `random.Random(f"greg-transfer-2026-10-28:{tier}:{i}")`, a string namespace that no qualification
  oracle and no integer-seeded generator in the exposure ledger uses.
- **Negative control:** `unrelated` is it. Nothing the construction forms applies to project crashing, so a measured
  transfer there means the measurement is wrong.

## 4. Declared criteria (mechanical; `summarise`)

- **work** (per mission): CAPABILITY_ATTACH asks + Genesis qualifications passed + deficits opened, counted for the
  task mission only.
- **Relations:** each task is **better**, **same** or **worse**, as `work(experienced)` is <, = or > `work(control)`.
- **correct:** the arm's mission is ACHIEVED, its answer carries the problem-level certificate, and the answer equals
  GREG's brute-force oracle on the original problem (staffing is also checked by exhaustive enumeration).

**Tier verdict**, the first rule that applies:

| Verdict | Rule |
|---|---|
| INVALID | the control arm is not correct on some task (the harness failed, not transfer) |
| NEGATIVE_TRANSFER | on some task the experienced arm is incorrect, or does more work than control |
| TRANSFER | at least ceil(0.9 n) tasks are better |
| NO_TRANSFER | at least ceil(0.9 n) tasks are the same |
| MIXED | anything else |

**The experiment is VALID only if all of these hold:**
- the unrelated tier is NO_TRANSFER **with no task better**;
- the contamination check rebuilt at least one qualification instance;
- no hidden instance (other than the declared replay) equals an instance Genesis qualified on;
- no receipt created authority;
- nothing attached itself.

Otherwise it is INVALID, and no tier verdict is a finding.

**Contamination:** every (oracle, seed) that Genesis qualified on is recorded in each arm's journal. The rebuild uses
the reduction's own oracle (`reduction:<id>`) or the catalog engine's oracle. Each hidden instance is compared in the
function's normalized form.

**Reported, not judged:**
- wall seconds per arm;
- ticks to closure;
- asks of every kind;
- appraisal verdicts;
- registry size;
- the method each arm answered with.

## 5. Predictions, made before the run

| Tier | Prediction | Reason |
|---|---|---|
| replay | TRANSFER | The same problem is routed to the attached construction: no deficit, no ask, no qualification (work 0 against about 6). |
| same_family | TRANSFER | Fresh staffing problems reuse the attached construction. **Risk:** if the compiler routes an instance to a method that needs no Genesis on either body, that task is `same` and the tier can fall to MIXED. |
| cross_family | TRANSFER | Matching reduces through staffing. The experienced body forms only the matching construction over what it holds (work about 3); the control must also acquire the max-flow engine (work about 6). |
| unrelated | NO_TRANSFER | Both bodies acquire the LP engine (or prove an impossible deadline with no engine) identically. |

These predictions follow from the mechanism, so the replay and same-family tiers are close to certain *if the path
reuses what it registered*. The experiment's information is therefore not the direction of the effect. It is:

1. whether the canonical path in fact reuses competence, rather than re-qualifying, re-asking or answering wrongly;
2. whether the reuse composes across a family boundary (`cross_family`);
3. whether the negative control and the contamination check hold.

**What this is not.** It is capability reuse through a governed registry, not statistical learning. No parameter is
fitted and no routing weight changes. A verdict here is evidence about these tiers and sizes on this harness only.

## 6. Development before this declaration (disclosed)

| Run | Namespace | n per tier | Verdicts |
|---|---|---|---|
| dev1 | `greg-transfer-dev` | 1 | replay, same_family and cross_family TRANSFER; unrelated NO_TRANSFER; VALID |
| dev2 | `greg-transfer-dev` | 1 | the same, with 87 qualification instances checked and none contaminated |

dev1's contamination check was **vacuous**: the harness read no qualification seeds, so "no contamination" proved
nothing. The fix reads each deficit's recorded acceptance (`deficit.opened.acceptance`) and any recovery probes.
`summarise` now requires that at least one instance was rebuilt.

After dev2, and before this declaration, writing the unit tests exposed a second weakness. With n = 12, NO_TRANSFER
needs only 11 tasks the same, so a single transfer on the negative control would have left the experiment VALID.
The rule was tightened: the unrelated tier must have **no** task better.

Other runs, none in the hidden namespace:
- the unit tests (namespace `greg-transfer-unit`);
- one live cross-family pair in CI (namespace `greg-transfer-ci`).

## 7. Run once, reproduce

    D=docs/evidence/greg-transfer/2026-10-28
    PYTHONPATH=. python scripts/greg_transfer_eval.py --out $D/results.json

The script:
- refuses `--n` with the declared namespace;
- refuses an existing output;
- records its own sha256 in `results.json`.

`tests/integration/test_greg_transfer_eval.py::test_the_recorded_run_re_derives_from_its_own_rows` re-derives the
summary from the committed raw rows. It also regenerates every hidden instance from the declared generator, and every
expected answer from the oracle.

**Reality tier:** LABORATORY, in-process bodies on one host. It is not founder-device evidence and not external
evidence. VEPMC stays 0.
