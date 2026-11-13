# autonomy

Layer 13 — autonomy licensing: evidence-earned, exact by construction,
immediately revocable.

## Organs

- `levels.py` — the A0–A9 ladder: A0 observe, A1 classify, A2 recommend,
  A3 simulate, A4 prepare, A5 execute reversible low-risk actions, A6
  operate bounded recurring workflows, A7 form temporary subordinate
  organs, A8 steward one bounded operating domain, A9 **reserved human
  sovereignty — never granted by the system**.
- `levels.py` — `AutonomyTuple`: autonomy is assigned to exact
  capabilities, never personalities. Nine dimensions: Capability ×
  Domain × Action × Resource × Target × ConsequenceClass × Environment ×
  Budget × Duration. A different tuple reads as zero autonomy.
- `levels.py` — `AutonomyAuthority.issue/promote/regress/renew`:
  promotion requires ALL ten criteria (weakest-link rule): repeated
  successful external outcomes, calibrated prediction, clean completion,
  policy fidelity, security, recovery, complete reconciliation, lower
  founder intervention, non-negative regenerative effect, independent
  verification. A missing outcome record blocks promotion. Autonomy
  rises slowly and falls immediately: severe failure (harm, concealment,
  unauthorized effect, reconciliation forgery, rights violation) zeroes
  the license and deactivates it; renewal requires a fresh, complete
  evidence cycle and reactivates at A0, never at the old level.
  `issue` is not a way past the ladder: a starting level above A0 needs a
  named human `authorized_by`, recorded in the license history and on the
  ledger; A0 needs none because it grants nothing, A9 is refused regardless,
  and a starting level never buys a promotion. The authorizer is compared as
  a person reads it (`identity/text.py` fold: invisible characters removed,
  NFKC, look-alike letters folded, case-folded): any spelling that names
  UNIIMENTE (`uniimente`, `UNIIMENTE Kernel`, `spiffe://uniimente.internal/…`,
  fullwidth or Cyrillic look-alikes), a workload URI, or the subject itself is
  refused. The level must be an `int` in A0–A8 (NaN, floats and bools are
  refused). Every transition is appended to the ledger before the license
  changes, so no autonomy exists unrecorded; a regression the ledger refuses
  still drops the license to A0, inactive. Callers get copies, never the
  authority's own records. Honest limit: `authorized_by` is a caller-supplied
  string (attributable, not unforgeable) until it is bound to a decision
  signed by Alfonso's enrolled founder key (`greg/founder.py`); the closure
  probes use a clearly synthetic authorizer, never his name.

## Recorded proof

`tests/unit/test_autonomy.py` (59 tests): exactness of the tuple key,
A9 refusal at issue and at the A8 ceiling, weakest-link refusals
(security gap, missing outcome records, rising founder intervention),
immediate severe-failure collapse, renewal discipline, issuance above
A0 refused without a named, recorded human authorizer, self-authorization
refused however it is spelled, non-integer levels refused, ledger-first
transitions, and copies handed out.

## Buildability standard (14 conditions)

- **Existing mechanism**: capability licensing, privilege ladders — standard access-control engineering, no novel science.
- **Defined interface**: `AutonomyAuthority.issue/promote/regress/renew/level_of`; typed dataclasses throughout.
- **Bounded authority**: the authority cannot grant A9, cannot waive the promotion criteria, cannot mint autonomy above A0 without a named human authorizer, and records every transition on the ledger with its evidence.
- **Available dependencies**: Python 3 stdlib + `provenance.ledger`.
- **Security model**: weakest-link promotion; severe failure → A0 + inactive immediately; inactive licenses cannot promote; renewal needs fresh complete evidence.
- **Failure modes**: `ValueError` on unmet criteria, A9 attempts, inactive-license promotion, premature renewal — all refusals ledgered.
- **Acceptance tests**: `tests/unit/test_autonomy.py` (59 tests).
- **Recovery path**: regression is the recovery path — autonomy falls to a level with a clean evidence base; renewal rebuilds from A0.
- **Resource ceiling**: one ledger append per transition; license lookup is O(1).
- **Operating cost**: constant per transition; evidence assembly is the caller's bounded work.
- **Legal operator**: Alfonso (A9 is his alone; every license transition is visible to him on the ledger).
- **Handoff state**: license state reconstructs from the ledgered transition history (`issued/promoted/regressed/renewed`).
- **Replaceable**: evidence assembly and the ledger are injected; criteria set is data, not code.

## Orthogonal closures

Verified by `closure/kernel_registry.py` → module `autonomy`.
