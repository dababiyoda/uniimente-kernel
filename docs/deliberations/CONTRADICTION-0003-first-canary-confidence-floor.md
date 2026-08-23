# CONTRADICTION-0003 — the confidence floor forbids an honest first canary

**Status:** RESOLVED 2026-08-23 — Options A + B, ratified by
`FOUNDER-RULING-2026-08-23`. The analysis below is preserved verbatim as it
stood when the contradiction was open; §8 records what was applied.
**Found:** 2026-08-23, by running CANARY-0001's rehearsal through the real Gate.
**Required:** a founder decision. Policy floors are constitutional.

---

## 1. What happened

The consequence-inert rehearsal of CANARY-0001 was built and run against the
real Consequence Gate. It did not complete. The Gate refused:

```
evidence confidence 0.55 below floor 0.70 for external_contact
```

The refusal is correct. `policy.engine.EVIDENCE_THRESHOLDS` sets a floor of
0.70 for `external_contact`, and the packet preregisters a predicted confidence
of **0.55**.

Neither number is wrong. That is the contradiction.

## 2. Why 0.55 is the honest number

CANARY-0001 is the institution's first external act. The chain has never run
against reality, no platform integration has been exercised, and no calibration
data exists. The honest prior for a first integration is closer to a coin flip
than to confidence.

`tests/unit/test_graduation_packet.py::test_the_prediction_is_not_flattering`
asserts `0.3 <= predicted_confidence <= 0.7` precisely so that a future editor
cannot quietly raise it. Preregistering a confidence is only worth doing if you
are willing to be wrong in public; a number chosen to clear a gate defeats the
mechanism before the experiment starts.

## 3. Why 0.70 is also right

A floor on external contact is sound policy. Acting on the outside world with
poorly evidenced beliefs is exactly what an institution like this should refuse,
and 0.70 is a defensible line.

## 4. The actual defect: one field, two meanings

`evidence_confidence` is being asked to carry two different quantities:

- **"How well-evidenced is the belief that this action is correct?"** — what the
  floor is protecting against. A high bar is right here.
- **"How likely is this to work?"** — what a preregistered canary prediction
  records, and what calibration later measures against reality.

For routine actions these track together and nobody notices. For a *first*
canary they are opposite by construction: the belief that we should run it is
very well evidenced (that is the whole argument in
`graduation/candidates.py`), while the belief that it will succeed is
deliberately uncertain — the uncertainty is the reason to run it.

## 5. The bootstrap this creates

Stated plainly, because it is the part that matters:

> To act externally you need confidence ≥ 0.70. Confidence comes from
> calibration. Calibration comes from comparing predictions against external
> outcomes. External outcomes require acting externally.

The institution cannot take a genuinely novel external action. It can only take
actions it is already confident about, and the only route to that confidence is
the actions it cannot take.

Worse, the floor creates pressure in the exact direction the institution exists
to resist: the cheapest way past it is to write 0.75 instead of 0.55. Nothing
would catch that but the test named above, and that test exists only because
this was written down. A policy that rewards inflating a predicted confidence is
a policy that manufactures the miscalibration the Bridge D calibration loop was
built to detect.

## 6. Options

**A. Split the field.** `evidence_confidence` keeps its current meaning and
governs the floor. Add `predicted_success_probability` for the calibration
join. Bridge D calibrates on the second; policy gates on the first. Costs a
field on `Proposal` and in witness contract v2 — which is not yet emitted, so
the cost is at its lowest right now.

**B. Reinterpret the floor as confidence in containment.** For a preregistered
canary the question the floor should ask is not "will it work" but "are we sure
this is bounded, reversible, killable and observable". CANARY-0001 scores very
high on that: zero budget, single-use grant, 15-minute TTL, deletable, digest-
verified. Requires deciding what the floor means, which is a constitutional
reading, not an edit.

**C. An explicit founder exception for preregistered canaries.** A named grant
that permits one external act below the floor, on the basis that the low
confidence is the experiment's subject rather than a defect in its preparation.
Narrowest change; also the most likely to be reached for again later, which is
how exceptions become the rule.

**D. Do nothing.** CANARY-0001 stays unrunnable as preregistered. The wall
stays intact and the institution cannot graduate. Honest, and terminal.

**Recommendation: A**, with **B** as the reading that makes A coherent. They are
complementary rather than alternatives — A separates the two quantities, and B
says what the floor is for once they are separate. Doing A while witness v2 is
still unemitted means the durable record carries the right field from its first
write, rather than needing a v3 later.

**C is not recommended**, for the reason given: a mechanism that exists to be
invoked when the floor is inconvenient will be invoked when the floor is
inconvenient.

## 7. What was NOT done

The floor was not changed. The predicted confidence was not raised. No exception
was created. `policy.engine.EVIDENCE_THRESHOLDS` is untouched.

Raising 0.55 to 0.71 would have made the rehearsal green in one character, and
it is the single most tempting edit in this repository. It would also have been
the institution lying to itself about its first external act, in the exact place
the whole apparatus exists to prevent — and it would have looked like progress.

The refusal is preserved as the finding.
`tests/integration/test_graduation_rehearsal.py::test_the_gate_refuses_the_honest_first_canary_and_that_is_the_finding`
pins it, so if the floor or the prediction ever moves, the change is deliberate
and visible rather than a quiet unblocking.


---

## 8. Resolution (added 2026-08-23)

**Options A + B applied together**, as recommended in §6 — A separates the
quantities, B says what the floor is for once they are separate.

**A — the split.** `predicted_success_probability` is a new field on `Proposal`
and on Witness contract v2, added before v2 emitted a single durable record.
That window was the founder's "cleanest versioned contract design" condition and
it closed the moment the Gate started signing v2 witnesses, which happened in
the same session. `policy.engine.evaluate` never reads it — asserted over the
AST, because a single attribute access would re-fuse the two quantities while
every behavioural test still passed.

Calibration now keys on the prediction rather than on the admission confidence.
Grading "we were justified in acting" against an outcome would have measured the
institution's judgement about permission and called the difference forecast
error.

**B — what the floor protects.** External classes must now additionally declare
`contained`, `reversible`, `observable`, `killable` and `proportionate`. Fails
closed: an undeclared property is refused exactly like an absent one, and only
literal `True` counts — `"yes"`, `1` and `"false"` are all refused.

**Nothing was relaxed.** The floor is still 0.70. The sealed prediction is still
0.55. The seal is unmoved. A proposal must now clear *more* than before, not
less: the floor **and** five containment declarations **and** an external grant.

**A third defect surfaced, and it is the important one.** With the confidence
conflation removed, an honest first canary reached step 7 of the Gate for the
first time — and the Gate **issued its own capability grant**. An external act
was authorising itself. The evidence floor had been refusing these proposals
earlier in the pipeline, so the missing check had never been reachable, and the
two failures were indistinguishable from outside.

`authorized` is one of the seven properties the ruling named. It is now enforced
where it belongs: the Gate refuses to mint a grant for any consequence class
that reaches outside. Internal effects may still be self-granted; the
restriction is scoped to what leaves the institution.

I had asserted, in this session, that `authorized` was "already enforced by the
grant and identity checks". That was wrong, and was falsified within the hour by
a test written to protect the canary. The correction is kept visible in
`tests/unit/test_two_confidences.py` rather than tidied away, because the way it
was found — removing one conflation exposed another — is the reusable part.

**CANARY-0001 is unchanged in status.** The Gate now admits the *rehearsal*,
which is consequence-inert by construction. `authorized_by` is `None`, no code
path sets it, `proves_external_reality` returns a literal `False`, and CVO
remains 0. Gate admission is not execution authorisation, and the GO/NO-GO
remains the founder's.
