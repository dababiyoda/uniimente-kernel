# Retained-capability compounding, 2026-11-05

**What this measures.** The second of the founder's two achievements, verbatim from the Goal Set (2026-10-22, re-sent
2026-11-04 and 2026-11-05): "GREG subsequently completes a different mission measurably better because of a
capability it developed, verified and retained during the first."

`greg/compounding.py` reads it from the ledger:

- **Formed.** Mission A opened a deficit for a function, and a capability that is not built in passed verification
  *under that deficit*. It then served A by either route: Genesis resolved the deficit with it, or it waited for the
  founder, who attached it (the Mind's constructions; the attach is the formation point). A was appraised VERIFIED
  after that. Re-attaching an already-verified capability develops nothing and is not a formation.
- **Reused.** A later, *different* mission B (registered after the formation) used that same capability in a passing,
  receipted observation or a DONE action, before its own VERIFIED appraisal. Through the Mind a mission names only
  `cognition.solve`; the construction that answered is read from the receipt (`method_or_composition_selected`), with
  every engine it is built on. B opened no deficit for the function. At
  least one such use came before any quarantine or detach. A use is credited only to the latest formation before it.
- **Priced.** The predicate reports what A paid for the function (builder calls, booked build cost, verifications,
  seconds blocked on the deficit) and that B paid none of it.

"Different" means not the same problem asked again (signed content with id, horizon and provenance masked). Each row
says whether B ran the same procedure on new inputs or a different procedure.

Path node N2 counts the formation and N4 counts ratified SOP runs; until now nothing counted this at runtime.
**Relation to #213** (`scripts/greg_transfer_eval.py`, adopted on #196 at `3a2ba265`): that pre-registered laboratory
experiment showed transfer under controlled arms. This is its runtime counterpart, reading the effect on any body's
own ledger, the founder's included. Running #213's harness exposed that the first version of this measure saw
**nothing** on the Mind's path (founder-attached constructions, `cognition.solve` uses); both routes are now read. The morning
report's "what I learned" answer (`q9_learned.capabilities_reused`) now carries it. `capability_compounding()` applies
the founder-tier rule every path node uses.

## Run (`run.json`, produced by the integration test's own fixtures, test keys)

| | builder calls | deficits opened | state |
|---|---|---|---|
| Mission A (`m:runbook`), forms `markdown.unchecked_count` | 2 (one wrong candidate refused, one passed 6/6 vectors) | 1 | ACHIEVED |
| Mission B (`m:release`), a different document and check, same body, after a restart | **0** | **0** | ACHIEVED |
| Counterfactual: mission B alone on a body that never formed it | 2 | 1 | ACHIEVED |

The counterfactual is the ablation: removing the retained capability restores exactly the detour A paid. The reuse
record names A, B, the capability, and the avoided acquisition (`builder_calls` 2, `verifications` 2).

**Evidence level: STRUCTURAL_CANDIDATE.** Test keys, a fixture body, and a deterministic builder. `met` is false and
says why (founder tier). Two figures read zero in this run, and that is the run's truth, not the mechanism's ceiling:

- `build_cost_usd`: the static test builder books $0.
- `blocked_seconds`: the build completes within one body tick, so the deficit's open interval is 0 s.

The decisive differences here are builder calls and verifications avoided. With a paid builder (Claude Code, an
API model) the same record prices the booked cost.

## The Mind's path (#213's own harness, test namespace `compounding-test-2026-11-05`)

| Later mission | Credited reuses of the construction mission's formations | Formed by the later mission itself |
|---|---|---|
| same family (new staffing problem) | `assignment.staffing` and the `graph.max_flow` engine under it | none |
| cross family (matching) | the `graph.max_flow` engine | `assignment.matching` (its own deficit; not credited to A) |
| unrelated (project crashing, negative control) | **none** | its own |

## Tests

- `tests/integration/test_greg_retained_capability_compounding.py` (8): reuse across a restart; the counterfactual
  body; the same problem asked again refused; a mission registered before formation refused; a quarantined capability
  re-formed by B credited to B; and the Mind's path through #213's harness (same family, cross family, unrelated control).
- `tests/unit/test_greg_compounding.py` (33): exact event orders for every condition of both formation routes, the
  price, unknown or boolean cost kept unknown, re-formation credited once, the relation, a bounded runtime for the
  morning report, and the founder-tier gate.
- **Ablation:** 26 single-condition mutants of the first version and 15 of the routes added after #213, each caught.

## Independent adversarial review (a separate agent, given the code, not this summary)

All findings were reproduced by the reviewer; each now has a regression test.

| Finding | Severity | Fix |
|---|---|---|
| A re-attach of an already-verified capability (Genesis `verified_detached`, Goal Gravity) counted as a formation, and stole the credit from the mission that built it | high | a formation needs a passing `genesis.verified` of the attached capability under that deficit (`built:<digest>` mapped to `built.<fn>.<digest12>`) |
| A failed or transient observation counted as a use | medium | an observation counts only when it passed with no failure class |
| A use after B's verdict, or A's verdict before A had the capability, counted | medium | uses must precede B's verified appraisal; the formation must precede A's |
| Quadratic replays inside every morning report (21 s at 11,200 events) | medium | each event kind replayed once and indexed; 150 formations x 150 reuses is bounded by a test |
| One use after a quarantine refused a pair that had a valid earlier use | low | each use judged on its own |
| An unregistered mission passed the order and procedure checks | low | a pair with an unregistered mission is refused |
| `cost_usd: true` priced as $1 | low | booleans are an unknown cost |

Accepted as limits, stated rather than fixed:
- ~~A capability attached by founder command after `deficit.awaiting_attach` is not seen~~: superseded; it is now read (the attach is the formation point).
- "Different" excludes only the same problem asked again; any change of inputs makes a mission different, and the row's `relation` says how.
- Each reuse reports its formation's whole price; several reuses of one formation must not be summed as total savings.

## What it does not show

- That B could not have obtained the function another way, or that either outcome mattered in the world.
- Generality across unrelated functions. One function is exercised here; N2's own note, "unproven until a second closure
  on an unrelated function", still stands.
- Anything on the founder's device. VEPMC is 0; this changes nothing about N1.

Authority: none. The measure is read-only and records nothing.
