# Abstention-to-resolution routing: results (runs v1 and v2)

**Pre-registered verdicts: v1 FAILED_HARM, v2 NO_DIVIDEND.** Neither run supports a claim of a capability dividend
under the rule written before the runs. Both verdicts stand as recorded. Everything after "Post-hoc readings" was
computed after the results and decides nothing.

- Code measured (NEW): `1d6b1c1`, unchanged between v1 and v2.
- Baselines: B0 `55e6d74` (#184) and P `610c343` (#194 with #184 merged).
- Pre-registrations: [v1](PREREGISTRATION.md) and [v2](v2/PREREGISTRATION.md).
- Freezes: [`freeze.json`](freeze.json), [`suite-freeze.json`](suite-freeze.json) and [`v2/freeze.json`](v2/freeze.json).
- Instrument defects recorded before any v1 result: [INSTRUMENT-DEFECTS.md](INSTRUMENT-DEFECTS.md).

## What was measured

When cognition abstains on a signed mission's step, NEW puts a typed `resolution` on the receipt (the producer). The
mission engine turns it into one founder ask of an existing kind, carrying an unsigned prepared command (the
consumer). A simulated founder signs at most one command after three ticks. An item closes when, within three more
ticks, the original or successor mission is ACHIEVED and appraised VERIFIED.

## v2 (D1 and D2 corrected; new seed; base items disjoint from v1)

| arm | closure rate (frozen E1 denominator, 94) | harmful closures | Genesis openings, gold not FORM (E3) |
|---|---|---|---|
| B0 `55e6d74` | 0.000 | 30 (all UNANSWERED) | 43 |
| P `610c343` | 0.000 | 0 | 30 |
| A_producer (consumer removed) | 0.000 | 0 | 30 |
| A_consumer (producer removed) | 0.000 | 0 | 30 |
| S (P, parser founder) | 0.532 | 0 | 30 |
| **NEW** | **0.638** | **0** | **15** |

- **E1:** fail. NEW is 0.638 against a 0.80 threshold. The gain over B0 is +0.638, with a lower bound of 0.602 against
  a 0.30 threshold.
- **E2:** fail.
  - Against the best single side, NEW gains +0.638 with a lower bound of 0.602; this part passes.
  - Against the parser founder, NEW gains only +0.106 (lower bound 0.012) against a 0.15 threshold.
- **H1:** pass, with 0 of 90 harm-eligible items harmful.
- **F1:** fail on 3 of 30 FORM items (below).
- **F2:** pass; all 19 floor items still close unaided.

Per operator (NEW / S):

| Operator | NEW | S |
|---|---|---|
| SUPPLY_INPUTS | 29 / 30 | 2 / 30 |
| ATTACH | 16 / 30 | 14 / 30 |
| CORRECT_DECLARATION, eligible | 15 / 15 | 15 / 15 |
| UNANSWERED, closed after the attach | 13 / 30 | 0 |

- PROTECTION, FORM and DEPENDENCY never close in any arm, as required. DEPENDENCY has no items in v2, because v1
  used every semantic base.
- **E4:** all 60 of NEW's closures came from a prepared command. The founder supplied 29 values, the ones the
  perturbation removed, and composed nothing. S's 50 closures were all founder-composed.

## v1 (the frozen instrument, with D1 and D2)

| Arm | Closure rate | Harmful closures | Errors |
|---|---|---|---|
| NEW | 0.326 | 19 | 29 |
| S | 0.500 | 11 | 0 |
| B0, P and both single-sided ablations | 0 | B0 30, the others 0 | 0 |

The verdict is **FAILED_HARM**.

- All 29 errors are D1: the harness cannot fill a founder value inside a list, so no SUPPLY_INPUTS item can close.
- Each of the 19 harm events is a formal-part closure. One attach of Z3 answered the question while CP-SAT, the second
  engine, stayed detached. This is D2, which counts any still-detached organ as harm, against the pre-registered text.
- S shows the same pattern: 11 harm events.

## Findings that stand regardless of the verdicts

1. **Baseline harm, removed by the prerequisites.** In both runs, B0 brings all 30 UNANSWERED missions to ACHIEVED,
   appraised VERIFIED, while a payload part has no reader. P and NEW never do. This is cortex 0.2.2's effect (#194),
   not the dividend's.
2. **A real NEW defect (F1).** On 3 of 30 FORM items (`gene regulation`, whose `expression` input fits arithmetic),
   NEW proposed a re-declaration and blocked the mission, and Genesis never opened. It is fixed on the canonical port
   (`e23ea45b`): the proposal is offered beside Genesis and never replaces it. A regression test fails without the
   fix and a mutant guards it. That code is **not measured by either run**.
3. **Both single sides do nothing.** With either the producer or the consumer removed, no item closes in either run.
   The effect needs both halves.

## Post-hoc readings (computed after the results; they decide nothing)

- **D3:** `analyze.py` puts the floor partition into E1's denominator. The 19 CORRECT_DECLARATION items B0 closes
  unaided count as closure-eligible. NEW, correctly, asks nothing on them, so they score as not closed. S's parser
  founder signs a successor anyway and closes them. Found after v1's results. On the 75 eligible items only, NEW
  closes 60 (0.80) and S 31 (0.41).
  - This reading would meet the E1 rate exactly and widen the margin over S.
  - It is **not** a claim: changing the denominator after seeing results is the thing a pre-registration exists to
    prevent.
  - A run v3 with D3 corrected, new FORM geometries and the F1 fix in NEW is the honest next step.

## What GREG can do now that it could not before (integrated, sandbox tier, fixture founder key)

When a signed mission's cognition step abstains, GREG asks the founder the one question that would let it answer,
with the command already prepared:

- attach the detached organ, after which the mission resumes by itself;
- supply the input it lacks, filling only that value;
- correct the declaration its own inputs contradict;
- or hand the question to a person.

Before this, every such abstention ended in a generic "add or revise strategies" ask, and attaching the right organ
did not unblock the mission. This is measured in a harness with a test key, not on Alfonso's device. It is not a
measured reduction of his real burden.
