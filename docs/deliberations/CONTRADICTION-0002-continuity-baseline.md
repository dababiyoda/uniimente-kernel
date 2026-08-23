# CONTRADICTION-0002 — the continuity baseline is bound to live files

**Status:** open. Reported, not resolved.
**Found:** 2026-08-22, while implementing ruling 3 of `FOUNDER-RULING-2026-08-22`.
**Requires:** a founder decision. Not taken unilaterally, for the reason in §5.

---

## 1. The finding

`evolution/repair/spec.CONTINUITY_ARTIFACT_SHA256` pins twelve files by SHA-256:
the five constitutional documents, the three authority documents, the three
identity registries, and `policy/consequence_gate.py`.

`tests/unit/test_repair_spec_frozen.py::test_continuity_hashes_describe_the_real_artifacts_now`
asserts those hashes against the **live** files. Its own docstring states the
intent:

> The continuity baseline must be true **at freeze time**, or the later
> before/after comparison proves nothing.

Freeze time. But the assertion runs against whatever is on disk today.

**This is CONTRADICTION-0001 in a second location.** Identical shape: a sealed
historical experiment bound to live artifacts, so the institution growing reads
as the institution breaking. Amendment 001 fixed the manifest corpus by pointing
it at a byte-identical freeze-time copy. The continuity pins were not examined at
the time and have the same defect.

The difference is what they pin. CONTRADICTION-0001 bound an experiment to
`organs/`. This one binds it to the **Constitution, the authority matrix, and
the Consequence Gate** — so the institution currently cannot amend its own
constitution without a sealed experiment failing.

## 2. How it surfaced

Not by inspection. Ruling 3 required the durable action record to preserve
`evidence_confidence`, `consequence_class` and the effective exposure ceiling,
so that the institution can reconstruct *what did we believe, how confident were
we, under exactly what authority did we act, what exposure was permitted*.

The contract is built and tested: `provenance/witness_v2.py`, 31 tests.

Adopting it needs one change: `policy/consequence_gate.py` must pass three
values into `new_witness`. It already holds all three — `Proposal` carries
`consequence_class` and `evidence_confidence`, and the gate holds
`grant["spending_limit_usd"]` at the moment it reserves budget. It calls
`new_witness` and drops them.

So the fix is roughly three lines, and it is blocked, because the gate is one of
the twelve pinned files.

## 3. Why it cannot be worked around quietly

Three routes were considered and all three are wrong:

**Update the pin.** `CONTINUITY_ARTIFACT_SHA256` lives inside `_FROZEN_TABLES`,
so changing it moves `SPEC_SHA256` *and* `EXPECTATIONS_SHA256` — the hash
established under Amendment 001 to prove no expectation value moved. The first
constitutional amendment would silently invalidate the proof built to protect
expectations. That is a signal the pin is in the wrong place, not an obstacle to
route around.

**Subclass the gate.** `run()` calls module-level `new_witness` with no seam, so
overriding step 9 means duplicating all fourteen steps. Two live gate
implementations is precisely the multiple-active-authority the Final Build Order
§3 forbids.

**Write v2 witnesses somewhere else.** Any writer that is not the gate is a
second authority path for durable records. Worse than the gap.

## 4. What was done instead

Everything that does not require touching a pinned file:

- `provenance/witness_v2.py` — versioned contract, version-aware
  canonicalisation, legacy reading, tamper detection, version negotiation,
  downgrade refusal. v1 signatures still verify byte-for-byte.
- `UNRECORDED` — v1 records read as *absent*, never as `0.0`. A calibration
  built on imputed confidence would measure the imputation.
- Bridge D reads confidence through the versioned reader;
  `WitnessReading.calibratable` is False for every v1 record, permanently.
- Bridge G prefers the witness and falls back to the actor's passport for v1,
  reporting `authority_source` so a reviewer can tell a standing ceiling from an
  exercised one.
- Both gap constants rewritten to say the contract exists and is unadopted.

The result is a contract that starts working the moment the gate can emit it,
and reports nothing rather than something convenient until then.

## 5. Why this is a founder decision

Two of the standing rules point the same way.

*No component may expand its own authority.* Unpinning the files that pin the
Constitution, on my own initiative, to unblock my own work, is the shape of
exactly that — however good the reason.

*Aspiration does not constitute current capability.* The remedy is
straightforward and its correctness is not the question. The question is who
gets to decide that constitutional artifacts stop being pinned by a sealed
experiment, and that is not a build session.

## 6. The options

**A. Freeze copies, as Amendment 001 did.** Copy the twelve artifacts to
`evolution/repair/continuity/`, point the historical check at the copies, let
the live files evolve under the amendment policy. Consistent with the remedy
already approved for the identical defect. Cost: the pins stop being a tripwire
on constitutional change, so that duty must move somewhere explicit.

**B. Amend the pin for `policy/consequence_gate.py` only.** Narrowest possible
change. Cost: moves `SPEC_SHA256` and `EXPECTATIONS_SHA256` a second time,
weakening the Amendment 001 proof, and leaves the same trap for the next
constitutional edit.

**C. Do nothing.** The v2 contract stays built and unadopted; calibration stays
impossible; every extraction keeps over-estimating authority from the passport.
The wall stays honest, and the gap the ruling asked to close stays open.

**Recommendation: A.** It applies the remedy already ratified for the same
defect, and it separates two duties that were accidentally fused — *reproduce a
historical experiment* and *notice unauthorised constitutional change*. The
second is real and deserves its own mechanism under the amendment policy, rather
than being a side effect of an experiment's baseline.

No option is applied. The gap register carries this as open.
