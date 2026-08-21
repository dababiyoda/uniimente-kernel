# NC-0 — causal need closure: exact generation-bound diagnosis

Evidence only. No runtime file, no test file, no marker changed.
`substrate/v5.py` is byte-identical to `bc13bc3`.

```
python verification/phase3g/need_closure_diagnose.py
python verification/phase3g/need_closure_diagnose.py --verify-results
```

Machine-readable results: `NEED_CLOSURE_CAUSAL_DIAGNOSIS.json`. The instrument
exits nonzero unless every finding holds, and carries a negative control that
restores each root's `need_id` as its unit's live open need — the one condition
under which settlement would be accepted. Every abandonment verdict must vanish.
A predicate that answered "abandoned" unconditionally would score identically
without it.

## The predicate

The skip that abandons a root is one line:

```python
# _settle_pending_roots
if key.origin_slot in self.bonds:
    continue
```

The measurement says **that is not the discriminating condition**. The truthful
predicate reads the obligation generation, not the bond:

```
root_obligation_retired(root) :=
        node is not terminal
    and node is not already closing
    and unit.open_needs.get(key.origin_slot) != key.need_id
```

Every field is local to the unit that owns the root. Nothing is read from the
organ, from another unit, or from a global index — a predicate needing global
topology could not run inside the protocol it governs.

It is truthful because `settle_search_offer` already refuses on exactly this:

```python
nid = self.open_needs.get(slot)
if nid is None or nid != key.need_id:
    self._reject_precondition(payload, "wrong_need_generation")
    return False
```

Once the unit's open need for that slot is cleared or replaced, the root can
**never settle anything again**, whatever arrives on it. That is the operational
definition of abandonment, and it holds whether or not a bond occupies the slot.

## Measured

| fixture | seed | open roots | states |
|---|---|---|---|
| `n_auth=4 density=1.0` | 0 | 1 | 1 × `7_ROOT_ALREADY_TERMINAL` |
| `n_auth=5 density=0.8` | 0 | 1 | 1 × `7_ROOT_ALREADY_TERMINAL` |
| `n_auth=3 density=0.6` | 5 | 3 | **3 × `2b_OBLIGATION_GENERATION_RETIRED`** |

```
ALTERNATE_SATISFIED_OPEN_ROOTS          3     (nonzero denominator)
abandoned roots holding liability       3     (all of them)
abandoned credit in flight             18.0
```

The dense fixtures every LC-2 specification uses contain **no abandoned root at
all** — their single root is already terminal. The condition exists only at
sparse density, which is the same blind spot LC-2a found from the edge side.

## The three abandoned roots

```
authorise.9   authorise.9:0:0   PROPOSAL_PENDING  accepted_proposal_id None
              children_outstanding 3   proposals_outstanding 3   credit 9.0
              slot bonded: YES   settled_by authorise.9:0:0
              settled_from_search_offer FALSE      supplier price.8

authorise.9   authorise.9:1:0   PROPOSAL_PENDING  accepted_proposal_id None
              children_outstanding 2   proposals_outstanding 2   credit 6.0
              slot bonded: YES   settled_by authorise.9:1:0
              settled_from_search_offer FALSE      supplier price.5

reconcile.12  reconcile.12:0:1  PROPOSAL_PENDING  accepted_proposal_id None
              children_outstanding 1   proposals_outstanding 1   credit 3.0
              slot bonded: NO
```

All three have `open_needs[slot] is None`.

**`settled_from_search_offer` is FALSE on both bonds.** They were not created by
the canonical Single-Flight settlement — `settle_search_offer` sets that flag and
also sets `accepted_proposal_id` and calls `_commit_wave`, and neither happened.
They were created by the **legacy Need/Offer path**, which filled the obligation
while the canonical root was still in flight. Corroborating counters on the same
run:

```
LEGACY_REPAIR_NEED_MESSAGES      14
ELIGIBLE_PROPOSALS_COMMITTED      0
UNIQUE_PROPOSAL_DECISIONS         1
DUAL_REPAIR_SEARCHES              0     <-- names this exact hazard, reads zero
```

`DUAL_REPAIR_SEARCHES` exists to detect two active searches for one obligation.
It reads zero while two roots are demonstrably abandoned by a second path
settling their slots. **Tenth instance of the instrument-liveness defect in this
workstream, this time in the runtime's own counter**, and it is recorded here
rather than fixed, because fixing it is a separate change from closing the roots.

The third root has no bond at all, so no bond-based predicate could have caught
it. Its generation was retired some other way and it is stranded identically.
That is the decisive argument for reading the generation rather than the slot.

## Why the bond test is the wrong test

The generation test **subsumes** the bond test on every measured root:

- both bonded roots also have a retired generation, so the generation test
  catches them and adds *why* as provenance rather than as the condition;
- the unbonded root is caught only by the generation test;
- a root whose slot is bonded by its own canonical settlement
  (`settled_from_search_offer` true **and** `accepted_proposal_id` set) is state
  `1_SAME_ROOT_COMMITTED` — it won, and closing it would be wrong.

The states the current one-line skip conflates, and what each is owed:

```
0   NOT_SKIPPED                     slot unmet; root live            do nothing
1   SAME_ROOT_COMMITTED             this root won                    do nothing
2   SATISFIED_ELSEWHERE             legacy path filled it            CLOSE
2b  OBLIGATION_GENERATION_RETIRED   can never settle again           CLOSE
3   UNRELATED_SLOT_BONDED           different slot                   do nothing
4   STALE_GENERATION_BOND           older generation                 do nothing
4a  BOND_WITHOUT_PROVENANCE         unattributable                   do nothing
5   LATER_GENERATION_EXISTS         unit reopened past this root     do nothing
6   ROOT_ALREADY_CLOSING            in flight                        do nothing
7   ROOT_ALREADY_TERMINAL           nothing owed                     do nothing
```

Closing on 3, 4 or 5 destroys a live search. Refusing to close on 2 or 2b
strands the liability, which is the present behaviour.

## What this corrects

The `daa1032` commit message and the PR body named the bottleneck as *"a root
whose obligation was satisfied through another path is abandoned, not closed"*
and pointed at `if key.origin_slot in self.bonds`. That is right in outline and
wrong in the discriminator: one of the three abandoned roots has no bond, and
the bonded ones are already caught by the generation test. The bond is
provenance for *why* the generation retired; it is not the condition.

Third hypothesis refinement in this mechanism, each falsified by executing it
rather than by argument.

## Not established

No runtime change and none was made. No closure mechanism exists yet — NC-1
preregisters the contract, NC-2 compares mechanisms, NC-3 implements. Whether
`SearchNeedClosed` is the correct downward kind, and what travels back up, is
decided in NC-2 and is **not** assumed here. Gate F **UNMEASURED**, Gate G
**UNMEASURED**, R8 **PROHIBITED**, no external effect.
