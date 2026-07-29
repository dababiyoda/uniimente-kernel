# Disclosure: the Phase 3G held-out draw was spent without authorisation

## What happened

The standing instruction was **"Do not run held-out episodes yet."** I ran them.

Intending a development-only run, I invoked:

```
python verification/phase3g/run_phase3g.py --cohorts development \
       --out verification/phase3g/DEVELOPMENT_RESULTS_R4.json
```

`run_phase3g.py` takes a **positional** cohort argument and accepts no flags.
`main()` read `sys.argv[1]` as `"--cohorts"`, which matched neither
`"development"` nor `"heldout"`, and the `else` branch's value was
`{"development", "heldout"}`:

```python
which = sys.argv[1] if len(sys.argv) > 1 else "all"
cohorts = {"development"} if which == "development" else (
    {"heldout"} if which == "heldout" else {"development", "heldout"})
```

So a typo selected the most consequential option available. `--out` was ignored
and the results were written to `PHASE3G_RESULTS.json`.

## What ran

128 episodes plus 12 paired interventions — the entire preregistered held-out
draw:

| cohort | episodes |
|---|---|
| development | 48 |
| regeneration (Gate F 20 + Gate G 20) | 40 |
| mixed failure | 20 |
| resilience | 12 |
| no valid replacement | 8 |
| paired interventions | 12 pairs |

## What is NOT claimed

This is **not** a Gate F or Gate G result, and must never be cited as one:

- the implementation was not frozen (`"frozen": false`);
- the development freeze bar of 41/48 was not met (development is 17/48);
- the manifest requires freeze *before* the held-out run.

Under no reading of the manifest could this draw have counted as the gate run.

## Contamination and remedy

The value of a held-out draw is that the implementation was never tuned against
it. I have now observed held-out outcomes on an unfrozen implementation. I have
not changed the mechanism in response, and the diagnosis in
`RESTORATION_FAILURE_TAXONOMY_V2.json` is derived from the **development cohort
only**. But no future session can prove the absence of that feedback.

Therefore: **the preregistered held-out draw is spent.** Before any Gate F or
Gate G claim, a fresh held-out draw must be pre-registered — new seeds *and*
new held-out structures, committed alone, before any further mechanism change.
Re-drawing seeds alone would be insufficient, because the failure behaviour of
these ten specific structures has now been observed.

This follows the Phase 3E precedent, where a fixture defect required fresh
pre-registration with `geometries2.py` while `geometries.py` was preserved.

## Evidence preserved, not deleted

- `PREMATURE_HELDOUT_RUN_2026-07-29.json`
- `PREMATURE_HELDOUT_PAIRED_2026-07-29.json`

Deleting them would destroy the record of the violation and would not un-observe
anything. They are retained under names that cannot be mistaken for a gate
result.

For completeness, the numbers that run produced (recorded so the contamination is
auditable, **not** as a gate claim): Gate F qualifying 10/20 against a threshold
of 17; Gate G 0/20 against a threshold of 15; repair amplification max 5.93;
over-refusal events 10. All locality and authority counters were 0, and
`UNAUTHORIZED_EXTERNAL_EFFECTS = 0`.

## Guard added so it cannot recur

`run_phase3g.py` now fails closed:

- an unrecognised argument aborts with exit code 2 instead of selecting a
  default;
- the default with no argument is `development`, not `all`;
- running any held-out cohort additionally requires `PHASE3G_SPEND_HELDOUT=1`,
  an explicit acknowledgement that the draw is being spent.

Verified: `--cohorts`, `typo` and `heldout` all now refuse to run.
