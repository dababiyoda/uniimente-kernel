"""INHERITED R6 LEXICAL-ORDERING DEFECT — outside Single-Flight acceptance.

    classification: INHERITED_R6_LEXICAL_ORDERING_DEFECT
    status:         STRICT_XFAIL
    scope:          OUTSIDE_SINGLE_FLIGHT_ACCEPTANCE

Kept in its own file so it can never sit inside the Single-Flight acceptance
denominator, and so the activation commit that removes Single-Flight xfail
markers cannot remove this one by touching a shared file.

WHY IT IS NOT A SINGLE-FLIGHT REQUIREMENT. Single-Flight Echo Search is scoped to
REPAIR, and `test_I_formation_is_untouched_by_the_repair_protocol` requires
formation to stay exactly at the R6 behaviour of 16 events and 1012 messages.
Single-Flight therefore cannot both leave formation unchanged and repair a
formation-level lexical-ID dependence -- those requirements are incompatible.
Most of the measured damage here is at formation.

Do not credit Single-Flight with fixing this if it changes. Do not blame
Single-Flight if it stays. Removing it needs a later mechanism concerned with
deterministic, identity-neutral selection.

MEASURED AT R6 over 12 topology-preserving permutations of this fixture:

    capability topology changed      0 / 12   (the relabelling is honest)
    formation FAILED                 4 / 12
    formed structure differed        8 / 12   (in capability terms)
    repair outcome differed          2 / 12

The test that previously carried this name did NOT permute identifiers -- it ran
the same fixture twice with n_auth 2 and 4, so the risk was claimed as covered
while going untested. The substrate sorts unit ids in several places
(sorted(neighbours), sorted(consumers), the interior pool), so this is
load-bearing rather than cosmetic.
"""
from __future__ import annotations

import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "verification" / "phase3g"))

import pytest

from substrate.v5 import ENV, SINK, reset

import fixtures as F

PAYLOAD_A = "  Claim-77  "
PAYLOAD_B = "  Claim-78  "

# This marker is NOT the Single-Flight `spec` marker and must survive the
# Single-Flight activation commit.
inherited = pytest.mark.xfail(
    strict=True,
    reason="INHERITED_R6_LEXICAL_ORDERING_DEFECT: formation and settled "
           "structure depend on lexical unit-ID order at the R6 baseline; "
           "outside Single-Flight acceptance")


def _build_raw(n_auth=4, seed=7, density=0.8):
    caps = F._spine("alpha2") + F._spine("beta2") + F._spine("gamma2")
    for i in range(n_auth):
        caps.append(F.cap(f"au{i}", ("PX", "PX"), "AUTH", F.AUTHORISE,
                          1.0 + 0.1 * i, f"d.a{i}", "authorise", F.OK_PRICE))
    caps.append(F.cap("rn0", ("AUTH", "AUTH"), "RECON", F.RECONCILE,
                      1.0, "d.p", "reconcile", F.OK_AUTH))
    caps.append(F.cap("db0", ("RECON",), "VERDICT", F.DISBURSE,
                      1.0, "d.r", "disburse", F.OK_RECON))
    return F._organ(caps, random.Random(seed), density)


def _join(o, want="AUTH"):
    for u in o.units.values():
        if u.capability.accepts.count(want) == 2:
            return u
    return None


# ---------------------------------------------------------------------------
# Unit-ID permutation: a real topology-preserving bijection
#
# The test previously carrying this name did NOT permute identifiers. It ran the
# same fixture twice with n_auth 2 and 4, so the known lexical-ordering risk was
# claimed as covered while going completely untested. The substrate sorts unit
# ids in several places -- sorted(neighbours), sorted(consumers), the interior
# pool -- so this is load-bearing, not cosmetic.
#
# MEASURED AT R6 over 12 permutations of this fixture:
#
#     capability topology changed      0 / 12   (the relabelling is honest)
#     formation FAILED                 4 / 12
#     formed structure differed        8 / 12   (in capability terms)
#     repair outcome differed          2 / 12
#
# So lexical unit-ID ordering already affects the R6 baseline, at formation and
# at repair. This test is therefore strict xfail: it is a real invariance the
# mechanism must eventually satisfy, and it does not hold today.
# ---------------------------------------------------------------------------

PERMUTATION_SEED = 4242
PERMUTATIONS = 5


def _relabel(o, mapping):
    """Rename units in place. Topology is preserved; only identifiers move.

    Called before `prepare`/`commission`, when the only structural state is
    `unit_id` and `neighbours`, so nothing is silently regenerated. ENV and SINK
    are never permuted.
    """
    units = list(o.units.values())
    remapped = {u.unit_id: {mapping.get(n, n) for n in u.neighbours}
                for u in units}
    for u in units:
        u.neighbours = remapped[u.unit_id]
        u.unit_id = mapping.get(u.unit_id, u.unit_id)
    o.units = {u.unit_id: u for u in units}
    return o


def _capability_topology(o):
    """Adjacency expressed in CAPABILITY terms, so renaming cannot change it.

    This is what proves a permutation did not accidentally regenerate a
    different structure.
    """
    return sorted((u.capability.name,
                   tuple(sorted(o.units[n].capability.name
                                for n in u.neighbours if n in o.units)))
                  for u in o.units.values())


def _formed_structure(o):
    """Settled bonds in CAPABILITY terms: consumer, slot, supplier."""
    return sorted((u.capability.name, s,
                   o.units[b.supplier].capability.name
                   if b.supplier in o.units else b.supplier)
                  for u in o.units.values() for s, b in u.bonds.items())


@inherited
def test_unit_id_permutation_preserves_semantics():
    o = _build_raw(4, 7)
    ids = [i for i in o.units if i not in (ENV, SINK)]
    assert len(ids) >= 6, "too few permutable units to be a real test"

    base = _build_raw(4, 7)
    F.prepare(base)
    reset()
    base.commission()
    assert base.result_ok(base.run_item(PAYLOAD_A)), "base fixture did not form"
    base_topology = _capability_topology(base)
    base_structure = _formed_structure(base)
    join = _join(base)
    assert join is not None and len(join.bonds) == 2, "base join did not form"
    slot = min(join.bonds)
    base_victim = join.bonds[slot].supplier
    base_victim_cap = base.units[base_victim].capability.name
    base.units[base_victim].silent = True
    reset()
    base_outcome = base.result_ok(base.run_item(PAYLOAD_B))
    base_independent = len({b.supplier for b in join.bonds.values()}) == len(join.bonds)

    rng = random.Random(PERMUTATION_SEED)
    failures = []
    for k in range(PERMUTATIONS):
        perm = ids[:]
        rng.shuffle(perm)
        mapping = dict(zip(ids, perm))
        assert len(set(mapping.values())) == len(ids), "mapping is not a bijection"
        assert ENV not in mapping and SINK not in mapping

        o = _relabel(_build_raw(4, 7), mapping)
        # The relabelling must not have regenerated a different structure.
        assert _capability_topology(o) == base_topology, (
            f"permutation {k} changed the capability topology, so it is a "
            f"different fixture rather than a renaming")
        F.prepare(o)
        reset()
        o.commission()

        if not o.result_ok(o.run_item(PAYLOAD_A)):
            failures.append(f"perm {k}: formation failed under renaming alone")
            continue
        if _formed_structure(o) != base_structure:
            failures.append(f"perm {k}: formed structure differs under renaming alone")
            continue

        victim = mapping[base_victim]           # the same UNIT, renamed
        assert o.units[victim].capability.name == base_victim_cap, (
            "the permutation did not damage the same semantic role")
        o.units[victim].silent = True
        reset()
        before = o.messages
        outcome = o.result_ok(o.run_item(PAYLOAD_B))
        j = _join(o)
        independent = len({b.supplier for b in j.bonds.values()}) == len(j.bonds)
        amp = round((o.messages - before) / max(1, len(o.units)), 2)

        if outcome != base_outcome:
            failures.append(f"perm {k}: restoration/escalation outcome "
                            f"{outcome} != base {base_outcome}")
        if independent != base_independent:
            failures.append(f"perm {k}: independence outcome differs")
        if amp > 12:
            failures.append(f"perm {k}: amplification {amp} exceeds 12")
        assert o.units[victim].silent, "the damage was not applied"

    assert not failures, (
        "renaming units changed behaviour:\n  " + "\n  ".join(failures))
