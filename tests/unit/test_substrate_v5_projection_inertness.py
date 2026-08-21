"""5G-V: `search_edge_terminals` holds no decision authority. Proved, not counted.

A counter asserting "the legacy projection was never read for a decision" is
only as good as its increment sites. If a read is added somewhere the counter
does not instrument, the counter still reads zero and reports success. That is
how a dead counter becomes worse than no counter: it converts an unchecked
property into a checked-looking one.

So this proves the property by consequence instead. Two identical organs take
the same damage and the same repair. One of them has its compatibility
projection turned hostile: every write is corrupted on arrival, and prior
entries are destroyed as it goes. If any decision anywhere still consults that
store, the twins must diverge -- in the result, the canonical nodes, the
settlement, the credit reconciliation, or the message and event counts.

If they do not diverge, no decision consulted it, whether or not anyone
remembered to instrument the read.

The static half of the argument lives in the 5G-W commit message: after that
commit `search_edge_terminals` has exactly one write, one initialisation and
zero reads in the whole runtime. This is the dynamic half, and it is the half
that survives someone adding a read later.
"""
from __future__ import annotations

import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
for _p in (str(_ROOT), str(_ROOT / "verification" / "phase3g"), str(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from substrate.v5 import C, reset            # noqa: E402

from test_substrate_v5_single_flight_live_path import (   # noqa: E402
    PAYLOAD_B, _damaged, _nodes, _normalized_settlement, _second_victim,
)


class _HostileProjection(dict):
    """A compatibility projection that lies about everything it is told.

    Not merely emptied. An emptied store answers "no such edge", which is a
    coherent answer a reader might handle correctly by accident. This answers
    with the WRONG edge data: every write lands mangled, and one earlier entry
    is destroyed on each write, so a reader that consults it gets confident
    wrong answers rather than obvious absence.

    `writes` is the non-vacuity witness. A hostile store nothing ever writes to
    proves nothing, so the test asserts this is non-zero before comparing.
    """

    def __init__(self):
        super().__init__()
        self.writes = 0

    def __setitem__(self, key, value):
        self.writes += 1
        if len(self) > 1:
            super().__delitem__(next(iter(self)))
        super().__setitem__(key, {
            "from_unit": "FORGED", "to_unit": "FORGED",
            "search_key": None, "outcomes": [],
        })

    def setdefault(self, key, default=None):
        """EVERY write path, not just the one the current runtime happens to use.

        A hostile store that only intercepts `__setitem__` is hostile only for
        as long as nobody writes through `setdefault`. The historical control
        path did exactly that, so an instrument missing this would report
        "corruption did not land" against the very runtime it needs to
        distinguish -- and a guard that cannot fail against the defect it names
        is not a guard.
        """
        if key not in self:
            self[key] = default
        return super().__getitem__(key)


def _fingerprint(o):
    """Everything a projection read could plausibly perturb, in stable form."""
    lifecycle = getattr(o, "search_edge_lifecycle", {}) or {}
    return {
        "nodes": sorted(f"{u}|{k.need_id}" for u, k in _nodes(o)),
        "settlement": _normalized_settlement(o),
        "messages": o.messages,
        "events": o.events_dispatched,
        "accepted_controls": sorted(
            f"{e}|{r['accepted_control'].kind}"
            for e, r in lifecycle.items() if r.get("accepted_control")),
        "accepted_outcomes": sorted(
            f"{e}|{r['accepted_outcome'].kind}|{r['accepted_outcome'].refund}"
            for e, r in lifecycle.items() if r.get("accepted_outcome")),
        "conflicts": sorted(
            f"{e}|{len(r['control_conflicts'])}|{len(r['outcome_conflicts'])}"
            for e, r in lifecycle.items()),
        "credit": sorted(
            f"{u}|{k.need_id}|{round(n['child_refunds_received'], 9)}"
            f"|{round(n['consumed_credit'], 9)}|{len(n['child_confirmed'])}"
            f"|{len(n['children_outstanding'])}"
            for (u, k), n in _nodes(o).items()),
    }


def _run_twin(hostile):
    """One organ through TWO real repairs. Returns its fingerprint.

    Two repairs, not one, for the reason the `_search` inertness test records:
    corrupting a projection and then running an item on an already-repaired
    organ may initiate no canonical repair at all, so the corrupted store never
    goes near a decision and the comparison proves nothing.
    """
    o, j, slot, victim, seed = _damaged(4)
    if hostile:
        o.search_edge_terminals = _HostileProjection()
    reset()
    o.run_item(PAYLOAD_B)
    nodes_after_first = len(_nodes(o))

    second = _second_victim(o, j, victim)
    assert second is not None, (
        "no causally necessary second damage target; without one the second "
        "repair below cannot be forced and this test would be vacuous")
    o.units[second].silent = True
    reset()
    result = o.run_item(PAYLOAD_B)

    assert len(_nodes(o)) > nodes_after_first, (
        "the second damage triggered no new canonical repair, so no decision "
        "was taken while the projection was hostile")
    assert C["REPAIR_REOPENS"] > 0, (
        "the second damage produced no reopen, so it was not causally active")
    return o, seed, second, result, _fingerprint(o)


def test_a_hostile_compatibility_projection_changes_nothing():
    """THE ONE-SOURCE-OF-TRUTH PROOF, by consequence rather than by counter."""
    control, seed_c, second_c, result_c, fp_c = _run_twin(hostile=False)
    exp, seed_e, second_e, result_e, fp_e = _run_twin(hostile=True)

    # The twins must be the same experiment, or a difference proves nothing.
    assert seed_e == seed_c and second_e == second_c, (
        f"twins diverged before the comparison (seed {seed_c} vs {seed_e}, "
        f"second victim {second_c} vs {second_e}); any difference below would "
        f"be fixture selection, not projection inertness")

    # NON-VACUITY. A hostile store nobody writes to is not hostile.
    assert exp.search_edge_terminals.writes > 0, (
        "nothing ever wrote the compatibility projection, so corrupting it "
        "could not have affected any decision and this test proves nothing")

    # And the corruption must have actually landed, not just been counted.
    assert all(r["from_unit"] == "FORGED"
               for r in exp.search_edge_terminals.values()), (
        "the hostile projection does not actually hold forged data")

    assert control.result_ok(result_c), "the control twin produced no valid result"
    assert exp.result_ok(result_e), (
        "the hostile twin produced no valid result, so the compatibility "
        "projection still carries decision authority")

    for field in sorted(fp_c):
        assert fp_e[field] == fp_c[field], (
            f"{field} diverged under a hostile compatibility projection, so "
            f"some decision still reads `search_edge_terminals`:\n"
            f"  control    {fp_c[field]}\n"
            f"  hostile    {fp_e[field]}")


def test_the_projection_is_derived_only_from_accepted_outcomes():
    """Whatever survives in the projection came from the outcome channel.

    Paired with the test above. That one proves the store is not READ for a
    decision; this one proves what is WRITTEN to it, so "inert" cannot be
    satisfied by a store that quietly accumulates commands nobody happens to
    read yet.
    """
    o, j, slot, victim, seed = _damaged(4)
    reset()
    o.run_item(PAYLOAD_B)

    proj = o.search_edge_terminals
    lifecycle = getattr(o, "search_edge_lifecycle", {}) or {}
    assert proj, "no projection was produced, so this test cannot check its shape"

    controls = [e for e, r in lifecycle.items() if r.get("accepted_control")]
    assert controls, (
        "no control was recorded anywhere, so 'the projection holds no "
        "controls' is true for the wrong reason")

    for edge, rec in proj.items():
        outs = rec["outcomes"]
        assert len(outs) == 1, (
            f"edge {edge} projects {len(outs)} entries; the projection is "
            f"assigned from exactly one accepted outcome")
        canonical = (lifecycle.get(edge) or {}).get("accepted_outcome")
        assert canonical is not None, (
            f"edge {edge} appears in the projection with no accepted outcome "
            f"in the canonical lifecycle, so the projection is not derived")
        assert outs[0] is canonical, (
            f"edge {edge} projects an object that is not its accepted outcome")

    for edge in controls:
        canonical = lifecycle[edge]
        if canonical.get("accepted_outcome") is None:
            assert edge not in proj, (
                f"edge {edge} was only COMMANDED and still appears in the "
                f"outcome projection")
