# NC-4A/4B — who retires a need generation, and by what authority

Evidence only. No runtime file, no test file, no marker changed.

```
python verification/phase3g/root_retirement_authority.py
python verification/phase3g/root_retirement_authority.py --verify-results
```

Machine-readable: `ROOT_RETIREMENT_AUTHORITY.json`. The trace wraps `open_needs`
itself rather than the functions that touch it, so a retirement through a path
nobody thought to wrap still appears, and the performer is read from the live
stack rather than inferred from a name.

## Finding 1 — the closure reason is wrong for one of three

```
n_auth=3 density=0.6 seed 5        3 retirements, all three closed a canonical root

    2   SATISFIED_BY_ALTERNATE_BOND      _settle, bond not from this root
    1   LEGACY_SEARCH_EXHAUSTED          _prove_exhaustion on the legacy ledger
```

NC-3 records `closure_reason = "need_satisfied_elsewhere"` on all three. For the
third that is **false**: nothing satisfied it. Its generation was retired because
a *legacy* search ledger proved itself exhausted, and the canonical root — still
`PROPOSAL_PENDING`, holding a proposal and 3.0 credit — was closed as collateral.

That is the counterexample already visible in the fixture as
`slot_bonded = false` alongside `closure_reason = need_satisfied_elsewhere`. The
predicate `open_needs[slot] != need_id` is sound; the *reason attached to it* is
overbroad, and an overbroad reason in the runtime is a false institutional
record, not a cosmetic issue.

The dense fixtures retire one generation each, both `CANONICAL_ROOT_COMMITTED` —
this root's own settlement, which is not an abandonment at all.

## Finding 2 — the legacy ledger holds retirement authority over canonical roots

```
CANONICAL_ROOTS_RETIRED_BY_LEGACY_AUTHORITY = 1
```

Structural, and readable without the trace:

```
_emit_need          open_needs[slot] = nid
                    AND self._search[nid] = new_search_ledger()   <- LEGACY
step()              for slot in open_needs:
                        if widen(slot): break                     <- legacy ledger
                        _prove_exhaustion(slot, nid)              <- legacy ledger
_prove_exhaustion   open_needs.pop(slot)
                    closed_needs.add(nid)
```

Every canonical repair root is created with a legacy ledger shadowing it, and
`step()` drives that legacy ledger on every pass. The migration disabled legacy
repair *messages*; it did not remove legacy repair *retirement authority*.

```
legacy repair need messages            14
eligible proposals committed            0
canonical roots retired by legacy       1
```

## Finding 3 — corrupting the legacy ledger changes canonical repair

```
canonical_repair_is_independent_of_legacy_ledger = FALSE
```

The probe re-runs the same repair with the canonical lifecycle untouched and the
legacy ledger falsified in three ways — emptied, marked settled, marked closed —
and compares the resulting canonical root states. They differ.

A disabled subsystem whose corruption changes canonical outcomes is not disabled.
This is the decisive evidence: it is not merely that a legacy function *happens*
to retire a generation, it is that legacy *state* is load-bearing for canonical
decisions. `DUAL_REPAIR_SEARCHES` reads 0 throughout, so the counter that exists
to detect exactly this reports nothing — the eleventh instrument-liveness
instance in this workstream.

## What this means for NC-3

NC-3 is not withdrawn. It closes real liabilities and the measured discharge —
13 stranded edges to 0, 18.0 credit to 0.0 — stands. But it **masked** this
defect rather than exposing it: by closing the collaterally-retired root cleanly,
it removed the visible symptom of an authority violation while leaving the
violation in place, and it labelled the result with a reason that is false for
that root.

Closing a liability created by an unauthorized decision is not the same as
preventing the unauthorized decision.

## What the remedy must produce

```
CANONICAL_ROOTS_RETIRED_BY_UNAUTHORIZED_LEGACY_AUTHORITY = 0
ROOT_RETIREMENTS_WITH_UNATTRIBUTED_CAUSE                 = 0
FALSE_ALTERNATE_SATISFACTION_CLAIMS                      = 0
canonical_repair_is_independent_of_legacy_ledger         = TRUE
```

and a neutral state `CLOSING_RETIRED_GENERATION` with reason
`obligation_generation_retired`, carrying a separate `retirement_cause` — so that
only `SATISFIED_BY_ALTERNATE_BOND` may increment an alternate-satisfaction
counter, and legacy exhaustion, supersession and unknown retirement are never
called "satisfied elsewhere".

Candidate remedies are compared in NC-4B′ before any runtime change. The smallest
that produces the above is preferred, and no second need registry may be created:
the existing generation identity (`unit:slot:activation`) already distinguishes
owners if an owner field is attached to it.

## Not established

No runtime change and none was made. The remedy is not chosen here. Gate F
**UNMEASURED**, Gate G **UNMEASURED**, R8 **PROHIBITED**, no external effect. No
development freeze is claimed: 24 strict xfails, 1 unexplained skip, retirement
causes unattributed in the runtime's own record, and legacy retirement authority
still live.
