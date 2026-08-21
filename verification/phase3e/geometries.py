"""Capability catalogues for Phase 3E.

The harness provides capability cells, their accepted and produced TYPES,
resources and neighbourhoods. It never provides the target graph, the role
sequence, a predetermined attachment structure, a ranked selection, or the
intended alternative route. Which chain satisfies the contract is discovered by
the substrate.
"""
from __future__ import annotations

from substrate.v3 import Capability, Cell3, FunctionContract, Tissue3

# -- deterministic transformations ------------------------------------------
NORM = lambda s: str(s).strip().lower()
SUM = lambda s: f"sum:{len(s)}"
PAR = lambda s: f"par:{sum(ord(c) for c in s) % 97}"
AGREE2 = lambda a, b: "ACCEPT" if a == b else "REJECT"
AGREE3 = lambda a, b, c: "ACCEPT" if (a == b or b == c or a == c) else "REJECT"
PASS = lambda v: v
WRAP = lambda v: f"w({v})"
UNWRAP = lambda v: v[2:-1] if str(v).startswith("w(") else v

ACCEPT_INVARIANT = lambda v: v.value == "ACCEPT"


def cap(name, accepts, produces, fn, cost=1.0, domain="shared", cls=""):
    return Capability(name, accepts, produces, fn, cost, domain, cls or name)


def _tissue(cells, contract, connect="full", rng=None, sparsity=0.6):
    t = Tissue3(cells, contract)
    ids = list(t.cells)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if connect == "full" or rng is None or rng.random() < sparsity:
                t.connect(a, b)
            else:
                t.connect(a, b) if a in ("@env", "@sink") or b in ("@env", "@sink") else None
    return t


CONTRACT = FunctionContract("fn:dual-check", "RAW", "VERDICT", ACCEPT_INVARIANT)
CONTRACT3 = FunctionContract("fn:triple-check", "RAW", "VERDICT", ACCEPT_INVARIANT)


def _fam_chain(fam, domain=None, checker=SUM, cls_check="check"):
    d = domain or f"d.{fam}"
    return [cap(f"norm.{fam}", ("RAW",), "NORM", NORM, 1.0, d, "normalize"),
            cap(f"chk.{fam}", ("NORM",), "CHK", checker, 1.0, d, cls_check)]


def _cells(caps):
    return [Cell3(cell_id=f"{c.klass()}.{i}", capability=c) for i, c in enumerate(caps)]


# ---------------------------------------------------------------------------
# The ten held-out function geometries.
# Each returns (tissue, contract, notes).
# ---------------------------------------------------------------------------

def recursively_missing_branch(rng):
    """The join's second arm requires a chain that does not exist until
    recruited three levels down."""
    caps = (_fam_chain("nu") + _fam_chain("xi")
            + [cap("deep.a", ("NORM",), "MID", WRAP, 1.0, "d.deep", "deepen"),
               cap("deep.b", ("MID",), "CHK", lambda v: SUM(UNWRAP(v)), 1.0,
                   "d.deep", "flatten"),
               cap("rec", ("CHK", "CHK"), "VERDICT", AGREE2, 1.0, "d.rec", "reconcile")])
    return _tissue(_cells(caps), CONTRACT), CONTRACT, "second arm needs a 3-deep chain"


def two_independent_self_recruiting_joins(rng):
    caps = (_fam_chain("nu") + _fam_chain("xi") + _fam_chain("om")
            + [cap("j1", ("CHK", "CHK"), "MID", AGREE2, 1.0, "d.j1", "join1"),
               cap("j2", ("CHK", "MID"), "VERDICT",
                   lambda a, b: "ACCEPT" if b == "ACCEPT" else "REJECT",
                   1.0, "d.j2", "join2")])
    return _tissue(_cells(caps), CONTRACT), CONTRACT, "two joins, each self-recruiting"


def nested_quorum_delayed_evidence(rng):
    caps = (_fam_chain("nu") + _fam_chain("xi") + _fam_chain("om")
            + [cap("q", ("CHK", "CHK", "CHK"), "VERDICT", AGREE3, 1.0, "d.q", "quorum")])
    return _tissue(_cells(caps), CONTRACT3), CONTRACT3, "3-input quorum"


def late_arriving_alternative_supplier(rng):
    caps = (_fam_chain("nu") + _fam_chain("xi")
            + [cap("slow", ("NORM",), "CHK", SUM, 3.0, "d.slow", "check"),
               cap("rec", ("CHK", "CHK"), "VERDICT", AGREE2, 1.0, "d.rec", "reconcile")])
    return _tissue(_cells(caps), CONTRACT), CONTRACT, "expensive alternative exists"


def coupled_versus_independent_supplier(rng):
    """Two ways to satisfy the join: one shares a resource domain with the
    consumer, one does not. The substrate is told neither."""
    caps = (_fam_chain("nu", domain="d.hot") + _fam_chain("xi", domain="d.hot")
            + _fam_chain("om", domain="d.cool")
            + [cap("rec", ("CHK", "CHK"), "VERDICT", AGREE2, 1.0, "d.hot", "reconcile")])
    return _tissue(_cells(caps), CONTRACT), CONTRACT, "coupled and independent both available"


def partitioned_demand_route(rng):
    caps = (_fam_chain("nu") + _fam_chain("xi") + _fam_chain("om")
            + [cap("rec", ("CHK", "CHK"), "VERDICT", AGREE2, 1.0, "d.rec", "reconcile")])
    return _tissue(_cells(caps), CONTRACT), CONTRACT, "partition forces another route"


def cyclic_affordances_requiring_loop_suppression(rng):
    """NORM->MID and MID->NORM both exist. Without lineage suppression the
    demand walk does not terminate."""
    caps = (_fam_chain("nu") + _fam_chain("xi")
            + [cap("up", ("NORM",), "MID", WRAP, 1.0, "d.cy", "up"),
               cap("down", ("MID",), "NORM", UNWRAP, 1.0, "d.cy", "down"),
               cap("rec", ("CHK", "CHK"), "VERDICT", AGREE2, 1.0, "d.rec", "reconcile")])
    return _tissue(_cells(caps), CONTRACT), CONTRACT, "NORM<->MID cycle"


def misleading_type_compatible_supplier(rng):
    """`liar` produces CHK and type-checks perfectly, but computes nonsense.
    Only real execution can tell."""
    caps = (_fam_chain("nu") + _fam_chain("xi")
            + [cap("liar", ("NORM",), "CHK", lambda s: "LIE", 0.4, "d.lie", "check"),
               cap("rec", ("CHK", "CHK"), "VERDICT", AGREE2, 1.0, "d.rec", "reconcile")])
    return _tissue(_cells(caps), CONTRACT), CONTRACT, "cheap liar is type-valid"


def two_causally_different_satisfying_structures(rng):
    caps = (_fam_chain("nu") + _fam_chain("xi")
            + [cap("par.a", ("NORM",), "CHK", PAR, 1.0, "d.p", "parity"),
               cap("par.b", ("NORM",), "CHK", PAR, 1.0, "d.q", "parity"),
               cap("rec", ("CHK", "CHK"), "VERDICT", AGREE2, 1.0, "d.rec", "reconcile")])
    return _tissue(_cells(caps), CONTRACT), CONTRACT, "sum-pair or parity-pair both work"


def orchestration_correctly_superior(rng):
    """A strict 5-stage chain with exactly one valid ordering and no
    redundancy. A planner that is handed the graph should win here."""
    caps = [cap("s1", ("RAW",), "T1", NORM, 1.0, "d.s", "s1"),
            cap("s2", ("T1",), "T2", WRAP, 1.0, "d.s", "s2"),
            cap("s3", ("T2",), "T3", lambda v: UNWRAP(v).upper(), 1.0, "d.s", "s3"),
            cap("s4", ("T3",), "CHK", SUM, 1.0, "d.s", "s4"),
            cap("s5", ("CHK", "CHK"), "VERDICT", AGREE2, 1.0, "d.s", "s5"),
            cap("s4b", ("T3",), "CHK", SUM, 1.0, "d.t", "s4")]
    return _tissue(_cells(caps), CONTRACT), CONTRACT, "linear chain, orchestration favoured"


HELD_OUT = {
    "recursively_missing_branch": recursively_missing_branch,
    "two_independent_self_recruiting_joins": two_independent_self_recruiting_joins,
    "nested_quorum_delayed_evidence": nested_quorum_delayed_evidence,
    "late_arriving_alternative_supplier": late_arriving_alternative_supplier,
    "coupled_versus_independent_supplier": coupled_versus_independent_supplier,
    "partitioned_demand_route": partitioned_demand_route,
    "cyclic_affordances_requiring_loop_suppression": cyclic_affordances_requiring_loop_suppression,
    "misleading_type_compatible_supplier": misleading_type_compatible_supplier,
    "two_causally_different_satisfying_structures": two_causally_different_satisfying_structures,
    "orchestration_correctly_superior": orchestration_correctly_superior,
}


def development(rng):
    """Development geometry: a plain redundant dual-check. Deliberately unlike
    the held-out set."""
    caps = (_fam_chain("nu") + _fam_chain("xi") + _fam_chain("om")
            + [cap("rec", ("CHK", "CHK"), "VERDICT", AGREE2, 1.0, "d.rec", "reconcile")])
    return _tissue(_cells(caps), CONTRACT), CONTRACT, "development"
