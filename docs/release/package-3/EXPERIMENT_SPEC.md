# Package 3 — Frozen Experiment Specification

**Status: FROZEN.** Machine-readable form: `evolution/repair/spec.py`.
Seal: `SPEC_SHA256 = 6f6d7dab40cf023dd69995511a3db298482c31b0bb39675d4a5c47f7c4ab7f4a`

This document and the module it describes were committed **before any
replacement candidate existed.** That ordering is the point: candidate code
cannot silently change the experiment it is judged by. An amendment is still
possible — it just breaks `tests/unit/test_repair_spec_frozen.py`, changes the
seal, and shows up in the diff as an amendment.

**Base:** `release/canonical-v1` @ `cb234faf932d239d79b0e7ab28e54f576b8a15bf`

---

## What is being tested

> Can UNIIMENTE detect the loss of a working specialist function, rank
> materially different replacements with its existing machinery, install one,
> and preserve identity, authority, memory, evidence and shutdown throughout?

This is a **governed functional-replacement experiment.** It is not autonomous
regeneration, not unscripted morphogenesis, and not open-ended self-repair.
See §8.

---

## 1. Subject: `linker/`, preserved unchanged

Three files, 186 lines, zero authority coupling, no durable state.

| File | sha256 (frozen) |
|---|---|
| `linker/__init__.py` | `e3b0c442…52b855` |
| `linker/linker.py` | `cc28da68…6e2c181` |
| `linker/manifest.py` | `b7b14a91…9aab8e33f` |
| **package** | `a42812d1ec701b71f71ca64f3d083939a42aeba4bece90d74713bd2c01a5e556` |

The original is **never deleted.** It is simultaneously the permanent
benchmark, the strongest conventional repair option, and the rollback target.
A test asserts these hashes on every CI run, so "preserved unchanged" is
checked rather than promised.

## 2. Target function — four exact edge triples

The detector is given the capability name
`institutional.cross_organ_edge_resolution` and its contract. It is never told
which module provides it.

```
daleobanks    --[wire-opportunity-packet]--> constitutional-controller
daleobanks    --[wire-opportunity-packet]--> wealthmachine
wealthmachine --[wire-venture-assessment]--> constitutional-controller
wealthmachine --[wire-venture-assessment]--> daleobanks
```
(organ ids are full SPIFFE URIs under `spiffe://uniimente.internal/organ/`)

Plus the refusal behaviour, which is half the function: 1 unproduced,
0 untyped, 11 unconsumed, 7 unresolved carried verbatim, 2 overlapping
authorities, `fully_connected = False`.

**The threshold is 4/4 = 1.0.** Three of four is 0.75 and is a *failure*, not a
ninety-percent pass. A 90% threshold on a four-item target would silently admit
3/4, so the threshold is stated as an exact fraction and
`test_four_of_four_is_the_threshold_and_three_of_four_fails` asserts that
`resolves(0.9)` is `False`.

## 3. Corpora

**Measurement (LIVE):** the real institution — `organs/*.manifest.yaml` against
`contracts/*.schema.json` at the baseline commit.

**Held-out:** four synthetic cases, inputs *and* expected outputs frozen here,
derived by hand from the contract rather than by running an implementation.
They share no organ id and no contract name with the live corpus.

| Case | What it isolates |
|---|---|
| HO-1 | self-loop only — an edge needs two distinct organs; a self-loop is neither edge nor refusal |
| HO-2 | untyped suppresses refusal accounting — reported untyped for both namers, and *not* as unconsumed/unproduced |
| HO-3 | fan-out and fan-in — cardinality must be exact, not merely non-zero |
| HO-4 | mixed refusals with a **global negative** — the case a purely local rule is least able to decide |

`test_held_out_expectations_are_internally_consistent_with_the_contract`
re-derives all four from the contract independently, so a hand-computation
error surfaces now, while fixing it is still honest — not after a candidate has
been failed by a wrong expectation.

## 4. Candidates and pre-registered predictions

| ID | Mechanism | Predicted score | Qualifies? | Cost rank |
|---|---|---|---|---|
| `B0-restore` | re-enable the original | 1.0 | **No** — it *is* the original | 1 |
| `R1-contract-index` | index-first, then set algebra | 1.0 | Yes | 2 |
| `R2-constraint` | generate-and-test over named constraints | 1.0 | Yes | 3 |
| `R3-local-rule` | message-passing cells, no global resolver | **0.0** | No | 4 |

Material difference is required in **data flow and decision structure**, not
naming. R3 gets a fair shot: its round budget (`R3_ROUND_BUDGET = 2`) is fixed
in advance so it cannot be tuned to the answer.

**Recorded reasoning for the R3 prediction:** a cell that sees only its own
manifest can conclude "no producer among cells I have heard from", which is not
the global negative the contract requires. Predicted to pass LIVE, HO-1, HO-2
and HO-3 and to be at risk on HO-4. **If R3 scores 1.0, the Package 2
hub-dependence finding does not transfer to this topology, and that must be
reported as a failed prediction.**

## 5. Selection — the author does not pick the winner

Primary ranking is the existing `evolution/comparison.py` on the gated function
metric: the fraction of the four required triples resolved exactly, forced to
`0.0` if *any* required refusal, held-out case, or continuity check fails. So
the hard gates are folded into the metric rather than applied by hand
afterwards.

Ties on the primary metric break on the frozen secondary order —
`repair_cost`, `decision_points`, `runtime_ms`, `rollback_steps`,
`new_source_lines` — with the cost formula and weights frozen in §6.

The decision is a `RetainRegressKillDecision`, which structurally **cannot**
authorize promotion when the verifier is hypothesis-only. It may recommend. It
may not promote or activate anything.

## 6. Repair-cost meter

```
repair_cost =  1.0 × new_source_lines
            + 25.0 × new_module_dependencies
            +  4.0 × decision_points
            +  0.5 × runtime_ms
            + 50.0 × rollback_steps
```

Units are **repair points, not dollars.** The cash cost of this package is
$0.00 and no field here should ever be read as money.

## 7. Continuity, authority, rollback, kill

Twelve artifacts must be byte-identical before disable, after disable, after
install, and after rollback — five `.ucl` constitution files, three `authority/`
registries, three `identity/` registries, and `policy/consequence_gate.py`.
Combined: `c1d621a80671d1f39f75e3d525561b45795a978d7d15b1eee7d43546140e63aa`.

Authority invariants: no grant to any candidate; no candidate registers itself
as provider; no self-widening; the decision may recommend but not promote;
shutdown enforceable at every stage **including while the function is absent**;
zero unauthorized external effects enforced out-of-process; UNIIMENTE is never
a legal principal.

Rollback: the original linker is never deleted, so lifting the runtime disable
restores the original path in one step. Every stage is a separate revertable
commit.

Kill conditions: an attempted external effect; an attempted self-grant or
self-registration; any continuity artifact changing; shutdown becoming
unenforceable; the spec seal no longer matching.

## 8. Declared limitations — frozen before the result is known

These are recorded now so they cannot be trimmed once the result looks good.

1. **All four candidates were authored in one session by one author.**
   "Materially different" is bounded by one author's imagination. A stronger
   version would source a candidate from outside the session.
2. **The replaced component is stateless.** This answers *can function be
   restored* and says nothing about whether durable state survives replacement.
3. **The candidate set is fixed in advance.** Nothing generates novel
   implementations, so this is not unscripted morphogenesis.
4. Detection is blind to which module failed, but the capability contract it
   checks against was written by the same author as the candidates.
5. The held-out corpus is held out **in time** (frozen before candidates
   existed), not by an independent party.
6. No external effect, deployment, spending, or real-world data. Nothing here
   is externally verifiable evidence: the strongest verifier available is a
   deterministic invariant.

## 9. Failure is a result

A failure here is publishable, not a defect to hide. The most likely honest
outcome is that **restoring the original is the cheapest and safest repair**,
and that a structurally different replacement is proven viable as a *fallback*
rather than as the new default. The report will state which of the three
questions — did a different structure restore the function; was it better than
restoring the original; what should the operational default be — each piece of
evidence actually answers.
