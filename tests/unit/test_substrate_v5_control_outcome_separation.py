"""Commit 5: a command and an outcome are two facts, not one.

PRE-REGISTERED BEFORE THE CORRESPONDING RUNTIME CHANGE, as strict xfail
throughout. THIRTEEN OF SIXTEEN ARE NOW ACTIVE: each was satisfied by the 5B
runtime split and its marker removed afterwards, in a separate commit. THREE
REMAIN XFAIL and are named at the bottom of this docstring -- the split is in
place, the stranded-child consequence is not yet resolved.

The description below is the state of the runtime WHEN THIS FILE WAS WRITTEN,
retained deliberately: it records what was wrong, and therefore what the active
tests are now holding closed.

WHY THIS FILE EXISTS. The runtime already distinguished the two semantic
classes -- `PARENT_CONTROL_KINDS` and `CHILD_OUTCOME_KINDS` -- and then routed
both through `_record_terminal`, which offered ONE first-wins slot per edge and
flipped `terminal_status` the moment it was filled.

So a parent that commands `SearchCancelled` downward occupies the edge's only
outcome slot, marks the edge terminal, and writes `refunded_credit` and
`consumed_credit` from its own message. The child's later evidence about what
actually happened to that edge and its credit can never become authoritative:
`_record_terminal` returns False and files the disagreement as a conflict.

Measured on a traced complete-graph repair before this file was written:

    5 of 6 edge terminal records were emitted by the edge's own OPENER
    1 of 6 carried real child evidence
    3 canonical nodes, INCLUDING THE ROOT, kept children_outstanding
    CHILD_EDGES_RECONCILED_FROM_EVIDENCE   0
    TERMINALS_WITH_UNRECONCILED_CHILDREN   5

That contradicts the doctrine `_may_emit` states verbatim:

    "Edge closure is what a receiver accepted, not what a sender asserted."

THE DEFECT IS NOT THAT COMMANDS ARE RECORDED. They must be: a command is an
authenticated fact about what was requested, and conflicting commands are a
finding. The defect is that CONTROL INTENT AND OBSERVED OUTCOME ARE STORED AS
ONE FIRST-WINS FACT, so the party owed the answer can supply it.

    a command  says WHAT WAS REQUESTED   -- it never proves the transition
                                            completed, however well
                                            authenticated its sender is
    an outcome says WHAT ACTUALLY HAPPENED -- only the receiving endpoint can
                                            emit it, and only it closes credit

MOST SPECIFICATIONS BELOW ARE WRITTEN AGAINST OBSERVABLE BEHAVIOUR RATHER THAN
AGAINST A PRESUMED SCHEMA, deliberately. A test that merely asserted
`search_edge_lifecycle` exists would fail with an AttributeError on any runtime
that had not yet been written, which proves nothing about conflation and would
pass the moment a dict was added. These fail because a command currently closes
an edge, which is the actual defect.

Where a schema IS required -- separate control and outcome channels, and their
conflict lists -- `_lifecycle` names it explicitly and says why.
"""
from __future__ import annotations

import pathlib
import random
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "verification" / "phase3g"))

import pytest

import substrate.v5 as v5
from substrate.v5 import ENV, SINK, C, reset

import fixtures as F

PAYLOAD_A = "  Claim-77  "
PAYLOAD_B = "  Claim-78  "
SEEDS = tuple(range(60))

separation = pytest.mark.xfail(
    strict=True,
    reason="control/outcome separation at the edge lifecycle is not implemented")


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


def _ctx(**kw):
    base = dict(causally_refused_sources=frozenset(),
                must_differ_from_suppliers=frozenset(),
                maximum_supplier_cost=99.0,
                cooldown_excluded_suppliers=frozenset(),
                constraint_generation=0, policy_snapshot=())
    base.update(kw)
    return v5.SearchContext(**base)


def _kind(x):
    return getattr(x, "kind", x)


def _counter(name):
    assert name in C.d, (
        f"the runtime defines no {name} counter, so the behaviour it names "
        f"cannot be measured and this specification cannot be satisfied")
    return C[name]


def _lifecycle(o, edge):
    """The edge's lifecycle record, with SEPARATE control and outcome channels.

    ONE record per edge -- two competing registries would recreate the same
    ambiguity in a new place. The requirement is not a second store; it is that
    the single store stop conflating two different facts.
    """
    rec = getattr(o, "search_edge_lifecycle", None)
    assert rec is not None, (
        "the organ exposes no per-edge lifecycle record with separate control "
        "and outcome channels, so a command and an outcome cannot be told "
        "apart at all")
    r = rec.get(edge)
    assert r is not None, f"no lifecycle record for edge {edge}"
    for field in ("controls", "outcomes", "accepted_control",
                  "accepted_outcome", "control_conflicts", "outcome_conflicts"):
        assert field in r, (
            f"the lifecycle record for {edge} has no {field!r} channel; "
            f"controls and outcomes must be separately addressable")
    return r


def _pair():
    """An origin, a real NEIGHBOUR of it, and a key. Seed-scanned, hard asserted."""
    for seed in SEEDS:
        o = _build_raw(4, seed, 0.8)
        F.prepare(o)
        reset()
        o.commission()
        if not o.result_ok(o.run_item(PAYLOAD_A)):
            continue
        j = _join(o)
        if j is None or len(j.bonds) != 2:
            continue
        slot = min(j.bonds)
        o.units[j.bonds[slot].supplier].silent = True
        reset()
        ctx = _ctx()
        key = v5.SearchKey.build(
            need_id="probe:sep", work_item_generation=2,
            origin_unit=j.unit_id, origin_slot=slot,
            wanted_type=j.capability.accepts[slot], context=ctx)
        nbrs = sorted(n for n in j.neighbours if n not in (ENV, SINK))
        if len(nbrs) < 2:
            continue
        target = o.units[nbrs[0]]
        others = sorted(n for n in target.neighbours
                        if n not in (ENV, SINK, j.unit_id))
        if others and j.unit_id in target.neighbours:
            return o, j, target, o.units[others[0]], ctx, key, seed
    raise AssertionError(
        "no origin adjacent to a receiver with a second neighbour across the "
        "pre-registered seeds; failing to build the structure is a failure of "
        "this specification, not a reason to skip it")


def _open(o, sender, target, key, edge, allocation=6.0):
    """The SENDER creates the edge, exactly as `_expand_canonical` does."""
    sender._record_probe(edge, sender.unit_id, target.unit_id, key,
                         allocation=allocation)
    return o.search_edge_probes[edge]


def _edge_state(o, edge):
    e = o.search_edges.get(edge, {})
    return (e.get("terminal_status", "open"), e.get("terminal_outcome"),
            e.get("refunded_credit", 0.0), e.get("consumed_credit", 0.0))


# ---------------------------------------------------------------------------
# 1. A parent command is not an outcome
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("command", ["SearchCancelled", "SearchCommitted",
                                     "SearchNeedClosed"])
def test_a_parent_command_does_not_occupy_the_child_outcome_slot(command):
    """The opener commands. It does not get to answer on the child's behalf.

    Today `_record_terminal` files the command in the edge's single outcome
    slot, and every later child outcome is dropped as a conflict.
    """
    o, j, nbr, other, ctx, key, seed = _pair()
    edge = "e/sep/cmd"
    _open(o, j, nbr, key, edge)
    reset()

    j._emit_terminal(command, key, edge, nbr.unit_id, proposal_id="p1")

    rec = _lifecycle(o, edge)
    assert rec["accepted_outcome"] is None, (
        f"{command} was recorded as the edge's accepted OUTCOME; a command "
        f"states what was requested, never what happened")
    assert rec["controls"], f"{command} was not recorded as a control at all"
    assert _kind(rec["controls"][0]) == command
    assert _counter("OUTCOME_SLOT_OCCUPIED_BY_CONTROL") == 0
    assert _counter("PARENT_CONTROLS_RECORDED_AS_CHILD_OUTCOMES") == 0


@pytest.mark.parametrize("command", ["SearchCancelled", "SearchCommitted"])
def test_a_parent_command_does_not_close_the_edge(command):
    """OBSERVABLE TODAY, and it is what actually breaks closure.

    `_record_terminal` sets `terminal_status` to terminal and writes
    `refunded_credit` / `consumed_credit` from the COMMAND's own fields, so the
    edge reads as settled with credit numbers the child never confirmed.
    """
    o, j, nbr, other, ctx, key, seed = _pair()
    edge = "e/sep/close"
    _open(o, j, nbr, key, edge)
    reset()

    j._emit_terminal(command, key, edge, nbr.unit_id, refund=6.0,
                     proposal_id="p1")

    status, outcome, refunded, consumed = _edge_state(o, edge)
    assert status == "open", (
        f"a {command} command flipped the edge to {status!r}; only an accepted "
        f"child outcome may close a transport edge")
    assert outcome is None, f"the command was recorded as the edge's outcome"
    assert refunded == 0.0 and consumed == 0.0, (
        f"the command wrote credit evidence ({refunded} refunded, {consumed} "
        f"consumed) that no child ever confirmed")


def test_a_child_outcome_is_accepted_after_a_parent_command():
    """THE PAIRED POSITIVE CONTROL, and the whole point of the split.

    A runtime that simply refused to record commands would pass every negative
    case above. This one fails unless the child's answer LANDS after the
    command, which is exactly what the first-wins slot prevents today.
    """
    o, j, nbr, other, ctx, key, seed = _pair()
    edge = "e/sep/answer"
    _open(o, j, nbr, key, edge)
    reset()

    j._emit_terminal("SearchCancelled", key, edge, nbr.unit_id, proposal_id="p1")
    nbr._emit_terminal("SearchExhausted", key, edge, j.unit_id, refund=4.0,
                       handling_cost=2.0)

    rec = _lifecycle(o, edge)
    assert rec["accepted_outcome"] is not None, (
        "the child's outcome was dropped because the parent's command already "
        "occupied the slot")
    assert _kind(rec["accepted_outcome"]) == "SearchExhausted"
    assert rec["accepted_control"] is not None, "the command was lost instead"
    assert _kind(rec["accepted_control"]) == "SearchCancelled"

    status, outcome, refunded, consumed = _edge_state(o, edge)
    assert status == "terminal", "the child's outcome did not close the edge"
    assert outcome == "SearchExhausted", (
        f"the edge closed as {outcome!r}; the authoritative outcome must be the "
        f"child's answer, not the parent's request")
    assert refunded == 4.0 and consumed == 2.0, (
        "the edge's credit was not taken from the child's own evidence")


# ---------------------------------------------------------------------------
# 2. Replay and conflict, in each channel independently
# ---------------------------------------------------------------------------

def test_exact_command_replay_is_inert_and_conflicting_commands_are_recorded():
    o, j, nbr, other, ctx, key, seed = _pair()
    edge = "e/sep/replay/cmd"
    _open(o, j, nbr, key, edge)
    reset()

    j._emit_terminal("SearchCancelled", key, edge, nbr.unit_id, proposal_id="p1")
    rec = _lifecycle(o, edge)
    after_first = (len(rec["controls"]), _kind(rec["accepted_control"]))

    for _ in range(3):
        j._emit_terminal("SearchCancelled", key, edge, nbr.unit_id,
                         proposal_id="p1")
    rec = _lifecycle(o, edge)
    assert (len(rec["controls"]), _kind(rec["accepted_control"])) == after_first, (
        "an exact command replay was recorded a second time")
    assert not rec["control_conflicts"], "a replay was filed as a conflict"

    j._emit_terminal("SearchCommitted", key, edge, nbr.unit_id, proposal_id="p1")
    rec = _lifecycle(o, edge)
    assert rec["control_conflicts"], (
        "a contradictory second command was accepted silently; two commands "
        "disagreeing about an edge is a finding, not noise")
    assert _kind(rec["accepted_control"]) == "SearchCancelled", (
        "a later contradictory command overwrote the accepted one")


def test_exact_outcome_replay_is_inert_and_conflicting_outcomes_are_recorded():
    o, j, nbr, other, ctx, key, seed = _pair()
    edge = "e/sep/replay/out"
    _open(o, j, nbr, key, edge)
    reset()

    nbr._emit_terminal("SearchExhausted", key, edge, j.unit_id, refund=3.0)
    rec = _lifecycle(o, edge)
    before = (len(rec["outcomes"]), _kind(rec["accepted_outcome"]),
              _edge_state(o, edge))

    for _ in range(3):
        nbr._emit_terminal("SearchExhausted", key, edge, j.unit_id, refund=3.0)
    rec = _lifecycle(o, edge)
    assert (len(rec["outcomes"]), _kind(rec["accepted_outcome"]),
            _edge_state(o, edge)) == before, (
        "an exact outcome replay was not inert -- it re-recorded, or refunded "
        "a second time")
    assert not rec["outcome_conflicts"]
    assert _counter("DUPLICATE_TERMINAL_RESOLUTIONS") == 0

    nbr._emit_terminal("SearchCoalesced", key, edge, j.unit_id, refund=1.0)
    rec = _lifecycle(o, edge)
    assert rec["outcome_conflicts"], (
        "a contradictory second outcome was accepted silently")
    assert _kind(rec["accepted_outcome"]) == "SearchExhausted", (
        "a later contradictory outcome replaced the accepted one")


# ---------------------------------------------------------------------------
# 3. Neither channel weakens the 2D direction and identity rules
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("attack", ["unknown_edge", "wrong_key",
                                    "wrong_destination", "wrong_direction"])
def test_a_command_that_cannot_be_justified_is_refused_in_the_control_channel(attack):
    """The split must not become a second door into the edge record.

    2D bound EMISSION. A separate control channel that skipped those checks
    would reintroduce every attack 2D closed, under a new name.
    """
    o, j, nbr, other, ctx, key, seed = _pair()
    edge = "e/sep/attack"
    if attack != "unknown_edge":
        _open(o, j, nbr, key, edge)
    emit_key = key
    if attack == "wrong_key":
        emit_key = v5.SearchKey.build(
            need_id="probe:elsewhere", work_item_generation=2,
            origin_unit=j.unit_id, origin_slot=key.origin_slot,
            wanted_type=key.wanted_type, context=ctx)
    to = nbr.unit_id if attack != "wrong_destination" else other.unit_id
    # `wrong_direction`: the edge's TARGET may not issue a parent command.
    emitter = j if attack != "wrong_direction" else nbr
    reset()

    emitter._emit_terminal("SearchCancelled", emit_key, edge, to)

    # NON-VACUITY FIRST. 2D already refuses all four of these, so without this
    # the case passes against a runtime that has no control channel whatsoever
    # -- it XPASSed on exactly that. What is being specified here is that the
    # NEW channel does not become a second door, which cannot be checked until
    # the channel exists.
    lc = getattr(o, "search_edge_lifecycle", None)
    assert lc is not None, (
        "there is no control channel yet, so 'the control channel refuses this "
        "attack' is not yet a meaningful statement")
    rec = lc.get(edge)
    if rec is not None:
        assert not rec["controls"], f"{attack}: an unjustified command was recorded"
        assert rec["accepted_control"] is None
    assert _edge_state(o, edge)[0] == "open"
    assert (_counter("UNKNOWN_EDGE_TERMINAL_EMISSIONS")
            + C["UNAUTHENTICATED_TERMINAL_EMISSIONS"]) == 1, (
        f"{attack}: no attributable emission violation was recorded")


def test_only_the_receiving_endpoint_may_emit_an_outcome():
    """An outcome from anyone but the receiver is not evidence.

    PAIRED CONTROL: the legitimate receiver's outcome must be accepted in the
    same fixture, so a runtime that refuses every outcome fails.
    """
    o, j, nbr, other, ctx, key, seed = _pair()
    edge = "e/sep/who"
    _open(o, j, nbr, key, edge)
    reset()

    other._emit_terminal("SearchExhausted", key, edge, j.unit_id, refund=6.0)
    lc = getattr(o, "search_edge_lifecycle", {}) or {}
    rec = lc.get(edge)
    if rec is not None:
        assert rec["accepted_outcome"] is None, (
            "a stranger's outcome was accepted as the edge's evidence")
    assert _edge_state(o, edge)[0] == "open"

    nbr._emit_terminal("SearchExhausted", key, edge, j.unit_id, refund=6.0)
    rec = _lifecycle(o, edge)
    assert rec["accepted_outcome"] is not None, (
        "the legitimate receiver's outcome was also refused, so the negative "
        "case above proves nothing")


# ---------------------------------------------------------------------------
# 4. A coalesced arrival still owns its own transport liability
# ---------------------------------------------------------------------------

@separation
def test_two_inbound_edges_coalescing_to_one_node_close_separately():
    """Single-flight is about the NODE. It is not about the edges.

    Two authenticated arrivals for one SearchKey create one canonical node and
    TWO transport liabilities. The second must still be answered on its own
    edge -- and this is precisely the edge that strands a parent today, because
    the coalescing unit adopts one edge and the other matches neither its
    adopted edge nor any child it opened.
    """
    o, j, nbr, other, ctx, key, seed = _pair()
    first, second = "e/sep/coal/1", "e/sep/coal/2"
    _open(o, j, nbr, key, first)
    _open(o, other, nbr, key, second)
    reset()

    nbr.deliver_search(key, first, 6.0, lineage=(j.unit_id,),
                       sender=j.unit_id, context=ctx)
    nbr.deliver_search(key, second, 6.0, lineage=(j.unit_id,),
                       sender=other.unit_id, context=ctx)

    assert key in nbr.canonical_searches, "neither arrival was adopted"
    assert len(nbr.canonical_searches) == 1, (
        "two canonical nodes were opened for one SearchKey")

    for edge, opener in ((first, j), (second, other)):
        rec = _lifecycle(o, edge)
        assert rec["accepted_outcome"] is not None, (
            f"{edge} was left with no child-owned outcome; a coalesced arrival "
            f"still owes its opener an answer on its own edge")
        assert rec["accepted_outcome"].from_unit == nbr.unit_id, (
            f"{edge} was closed by somebody other than the receiving endpoint")
    assert _counter("CLOSED_CHILD_EDGES_WITHOUT_CHILD_EVIDENCE") == 0


# ---------------------------------------------------------------------------
# 5. THE SINGLE BOTTLENECK METRIC, on a real repair
# ---------------------------------------------------------------------------

@separation
def test_every_closed_child_edge_on_a_live_repair_carries_child_evidence():
    """The metric, with a mandatory nonzero denominator.

    This is the assertion the traced run failed before this file existed:
    5 of 6 edge records were the opener's own assertion, and three nodes --
    including the root -- kept children outstanding forever.
    """
    o, j, slot, victim, seed = _damaged(4, density=1.0)
    reset()

    o.run_item(PAYLOAD_B)

    closed = _counter("CLOSED_CHILD_EDGES")
    assert closed > 0, (
        "no child edge was closed at all, so the ratio below has no "
        "denominator and would be vacuously satisfied")
    assert _counter("CLOSED_CHILD_EDGES_WITH_ACCEPTED_CHILD_OUTCOME") == closed
    assert _counter("CLOSED_CHILD_EDGES_WITHOUT_CHILD_EVIDENCE") == 0
    assert _counter("PARENT_CONTROLS_RECORDED_AS_CHILD_OUTCOMES") == 0
    assert _counter("OUTCOME_SLOT_OCCUPIED_BY_CONTROL") == 0
    assert _counter("TERMINALS_WITH_UNRECONCILED_CHILDREN") == 0
    assert _counter("CHILD_EDGES_RECONCILED_FROM_EVIDENCE") > 0, (
        "nothing was reconciled from child evidence, so the reconciliation "
        "path is inert rather than satisfied")
    assert C["UNAUTHENTICATED_TERMINAL_CONTROLS"] == 0
    assert C["MALFORMED_TERMINAL_EVIDENCE"] == 0
    assert C["UNSUPPORTED_CHILD_CANCELLATION_CREDIT"] == 0
    assert C["UNAUTHORIZED_EXTERNAL_EFFECTS"] == 0
    assert _counter("INHERITED_AUTHORITY_EVENTS") == 0


@separation
def test_no_closed_node_finishes_with_children_outstanding():
    """The observable consequence, stated as its own requirement.

    A node that reached a terminal status while still holding outstanding
    children is waiting for a message that will never arrive.
    """
    o, j, slot, victim, seed = _damaged(4, density=1.0)
    reset()

    o.run_item(PAYLOAD_B)

    nodes = {(u.unit_id, k): n for u in o.units.values()
             for k, n in getattr(u, "canonical_searches", {}).items()}
    assert nodes, "no canonical nodes were created"
    finished = {ident: n for ident, n in nodes.items()
                if n["status"] in ("COMMITTED", "CLOSED", "EXHAUSTED")}
    assert finished, "no node reached a terminal status"
    stranded = {uid: sorted(n["children_outstanding"])
                for (uid, k), n in finished.items() if n["children_outstanding"]}
    assert not stranded, (
        f"nodes reached a terminal status while still owed answers by their "
        f"own children: {stranded}")


def _damaged(n_auth=4, density=0.8):
    """Seed-scanned then HARD ASSERTED. Never skips."""
    for seed in SEEDS:
        o = _build_raw(n_auth, seed, density)
        F.prepare(o)
        reset()
        o.commission()
        if not o.result_ok(o.run_item(PAYLOAD_A)):
            continue
        j = _join(o)
        if j is None or len(j.bonds) != 2:
            continue
        if len({b.supplier for b in j.bonds.values()}) != 2:
            continue
        slot = min(j.bonds)
        victim = j.bonds[slot].supplier
        o.units[victim].silent = True
        return o, j, slot, victim, seed
    raise AssertionError(
        "no formed independently-supplied join across the pre-registered "
        "seeds; failing to construct the structure is a failure of this "
        "specification, not a reason to skip it")


# ---------------------------------------------------------------------------
# 6. The canonical record and its projection may not disagree
# ---------------------------------------------------------------------------

@separation
def test_the_canonical_lifecycle_and_its_projection_cannot_diverge():
    """`search_edge_lifecycle` is canonical. Everything else is derived.

    THE FRAGILITY THIS NAMES. Two structures are currently mutated
    INDEPENDENTLY: `_record_control` and `_record_outcome` each write
    `search_edge_lifecycle`, and each also writes `search_edge_terminals`. The
    projection was retained deliberately, because eight active specifications
    still read the old structure to ask "did the opener command this edge" --
    which was defensible inside a runtime-only commit and is not acceptable as
    the frozen R8 evidence architecture.

    The concrete disagreement is already reachable. A command-only edge has

        lifecycle accepted_outcome  None          (correct: nothing closed it)
        search_edges terminal_status 'open'       (correct)
        projection ["outcomes"]     [the COMMAND] (a control, filed under a key
                                                   every reader of that field
                                                   interprets as an outcome)

    so the same edge answers "was an outcome recorded" differently depending on
    which structure is asked. That is the divergence, and it is a property of
    having two independently written stores rather than of any single write.

    NON-VACUOUS BY CONSTRUCTION. A live repair is required to exercise at least
    one control AND at least one outcome before anything is compared, so an
    empty organ -- or one that never emitted either -- fails instead of
    trivially agreeing.
    """
    o, j, slot, victim, seed = _damaged(4, density=1.0)
    reset()

    o.run_item(PAYLOAD_B)

    lifecycle = getattr(o, "search_edge_lifecycle", None)
    assert lifecycle, (
        "no canonical lifecycle records exist, so there is nothing to compare "
        "a projection against and this test would pass vacuously")
    controls = [e for e, r in lifecycle.items() if r["accepted_control"] is not None]
    outcomes = [e for e, r in lifecycle.items() if r["accepted_outcome"] is not None]
    assert controls, "the run exercised no parent control"
    assert outcomes, "the run exercised no child outcome"

    divergences = []
    for edge, rec in sorted(lifecycle.items()):
        accepted = rec["accepted_outcome"]
        edge_row = o.search_edges.get(edge, {})
        status = edge_row.get("terminal_status", "open")
        # 1. Closure must follow the accepted OUTCOME, in both directions.
        if accepted is None and status == "terminal":
            divergences.append((edge, "closed with no accepted outcome"))
        if accepted is not None and status != "terminal":
            divergences.append((edge, "accepted outcome did not close the edge"))
        if accepted is not None:
            if edge_row.get("terminal_outcome") != accepted.kind:
                divergences.append((edge, "terminal_outcome disagrees"))
            if abs(edge_row.get("refunded_credit", 0.0) - accepted.refund) > 1e-9:
                divergences.append((edge, "refunded_credit disagrees"))
            if abs(edge_row.get("consumed_credit", 0.0)
                   - accepted.handling_cost) > 1e-9:
                divergences.append((edge, "consumed_credit disagrees"))
        # 2. ANY retained projection must be derived from the outcome channel
        #    alone. A control appearing in a field readers treat as an outcome
        #    is exactly the ambiguity the split exists to remove.
        proj = (getattr(o, "search_edge_terminals", {}) or {}).get(edge)
        if proj is not None:
            proj_outs = [x for x in proj.get("outcomes", [])]
            for x in proj_outs:
                if _kind(x) in v5.PARENT_CONTROL_KINDS:
                    divergences.append(
                        (edge, f"projection carries the control {_kind(x)} in a "
                               f"field named 'outcomes'"))
            if accepted is None and proj_outs:
                divergences.append((edge, "projection has an outcome the "
                                          "canonical record does not"))
            if accepted is not None and not proj_outs:
                divergences.append((edge, "projection lost the accepted outcome"))

    assert not divergences, (
        f"the canonical lifecycle and its projection disagree on "
        f"{len(divergences)} point(s): {divergences[:6]}")
    assert _counter("CANONICAL_LIFECYCLE_PROJECTION_DIVERGENCES") == 0
