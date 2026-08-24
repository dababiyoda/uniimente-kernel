# Frozen continuity artifacts for the Package 3 repair experiment

Byte-identical freeze-time copies of the twelve artifacts pinned in
`evolution/repair/spec.CONTINUITY_ARTIFACT_SHA256`: the five constitutional
documents, the three authority documents, the three identity registries and
`policy/consequence_gate.py`.

**Every file here carries a `.frozen` suffix, and that is load-bearing.**

The first version of this corpus stored them under their real names. That made
`policy/consequence_gate.py` importable — PEP 420 namespace packages need no
`__init__.py` — so the remedy for CONTRADICTION-0002 had quietly created a
genuine **second path to external effect**, sitting in the tree under a
reassuring directory name. CI check 3 ("one source of authority") failed on the
push and was right to: `**/consequence_gate.py` found two.

Fixed by suffixing, not by excluding this directory from that check. An
exclusion would have let the check keep passing while the importable duplicate
stayed on disk — weakening the check to accommodate the defect it correctly
found. A frozen artifact is a byte record of what the law *was*; the suffix
makes it unloadable as law, unimportable as code, and invisible to every glob
that looks for the real thing.

Read them through `spec.frozen_path(relative)`, which maps a pinned relative
path to where its bytes actually live. Amendment 004.

Every file here was verified against its pinned hash **before** it was written,
and the sha256 over their concatenated bytes equals `CONTINUITY_COMBINED_SHA256`
exactly:

    c1d621a80671d1f39f75e3d525561b45795a978d7d15b1eee7d43546140e63aa

## Why this exists

`continuity_fingerprint()` used to read the **live** tree, so a sealed
historical experiment asserted freeze-time hashes against files the institution
is entitled to amend. The institution could not lawfully change its own
constitution without the experiment failing — growth reading as breakage.

Same defect as CONTRADICTION-0001, on a more serious subject. Same remedy,
ratified by the founder as CONTRADICTION-0002 Option A. See
`docs/release/package-3/AMENDMENT-002-frozen-continuity.md`.

## What this corpus does and does not change

**No expectation value moved, and neither did the seal.** Amendment 001 had to
move `SPEC_SHA256` because the corpus binding lived inside a frozen table. The
continuity binding never did — the pins are relative paths, and the root they
were joined to lived in `harness.py`. So:

    spec.spec_hash()         == spec.SPEC_SHA256          unchanged
    spec.expectations_hash() == spec.EXPECTATIONS_SHA256  unchanged

Proven by `test_amendment_002_moved_no_expectation_and_did_not_move_the_seal`.

## This is NOT the live tripwire

This directory answers exactly one question: **can the Package 3 run be
reproduced?** It will keep answering *yes* forever, by construction. That is
correct, and it is also the adversarial weakness of the remedy — a frozen check
that always passes could be mistaken for evidence that the live constitution is
intact.

It is not evidence of that. It stopped looking at the live institution the
moment it was repointed here.

The live question — *has anything changed the Constitution without
authorisation?* — belongs to **`governance/integrity/`**, which reads the live
tree, replays an append-only chain of founder-authorised amendments, and reports
`UNAUTHORISED_CHANGE`, `MISSING` or `UNGOVERNED_ADDITION`. Run it with:

    python -m governance.integrity

Neither reading may be presented as the other. Two tests pin the separation:
`test_the_sealed_experiment_is_no_longer_the_live_tripwire` and
`test_the_two_readings_may_disagree_without_either_being_wrong`.

## Expected divergence

`policy/consequence_gate.py` is about to change in the live tree — Witness v2
emission, authorised by the same ruling. When it does, the copy here stays at its
freeze-time bytes and the sealed experiment keeps reproducing, while
`governance/integrity` records the change as an authorised amendment.

That divergence is the remedy working, not drift.
