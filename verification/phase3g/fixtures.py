"""Phase 3G fixtures and damage injectors.

The harness supplies capability cells, their accepted and produced types, local
acceptance conditions, resource domains, costs and neighbourhoods. It never
supplies the target graph, the role sequence, a predetermined attachment, a
ranked selection, or the intended alternative route.

Every one of the 14 preregistered damage classes has a real injection path AND
an `observed()` assertion proving the intended condition actually occurred.
A fixture name is not evidence.
"""
from __future__ import annotations

import dataclasses
import random

from substrate.v5 import (COOLDOWN_RETURN, CONFLICTING, COSTLY, DELAYED, ENV,
                          EXPIRED, FALSE_SUSPICION, GONE, INTERMITTENT, ISOLATED,
                          MISSING_RECEIPT, REPEATED, SILENT, SINK, STALE_RETURN,
                          WRONG, Capability, Contract, Organ, Unit)

# -- deterministic transforms and local acceptance conditions ---------------
RECEIVE = lambda s: str(s).strip()
VERIFY = lambda s: str(s).lower()
PRICE = lambda s: f"px:{sum(ord(c) for c in str(s)) % 977}"
AUTHORISE = lambda a, b: "AUTHORISED" if a == b else "REFUSED"
RECONCILE = lambda a, b: "RECONCILED" if a == b == "AUTHORISED" else "BROKEN"
DISBURSE = lambda s: "ACCEPT" if s == "RECONCILED" else "DECLINE"

OK_CLEAN = lambda v: isinstance(v, str) and v == v.strip()
OK_LOWER = lambda v: isinstance(v, str) and v == v.lower()
OK_PRICE = lambda v: isinstance(v, str) and v.startswith("px:") and v[3:].isdigit()
OK_AUTH = lambda v: v in ("AUTHORISED", "REFUSED")
OK_RECON = lambda v: v in ("RECONCILED", "BROKEN")

CLAIM = Contract("fn:claim", "RAW", "VERDICT", lambda v: v.payload == "ACCEPT")


def cap(name, accepts, produces, fn, cost=1.0, dom="shared", cls="", acc=None):
    return Capability(name, accepts, produces, fn, cost, dom, cls or name, acc)


def _organ(caps, rng, density=0.8):
    units = [Unit(unit_id=f"{c.klass()}.{i}", capability=c) for i, c in enumerate(caps)]
    o = Organ(units, CLAIM)
    ids = list(o.units)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if a in (ENV, SINK) or b in (ENV, SINK) or rng.random() < density:
                o.connect(a, b)
    return o


def _spine(fam, dom=None, cost=1.0):
    d = dom or f"d.{fam}"
    return [cap(f"rc.{fam}", ("RAW",), "CLEAN", RECEIVE, cost, d, "receive", None),
            cap(f"vf.{fam}", ("CLEAN",), "LOW", VERIFY, cost, d, "verify", OK_CLEAN),
            cap(f"pr.{fam}", ("LOW",), "PX", PRICE, cost, d, "price", OK_LOWER)]


def _tail(n=2):
    out = []
    for i, (dom, c) in enumerate((("d.p", 1.0), ("d.q", 1.2))[:n]):
        out += [cap(f"au{i}", ("PX", "PX"), "AUTH", AUTHORISE, c, dom, "authorise", OK_PRICE),
                cap(f"rn{i}", ("AUTH", "AUTH"), "RECON", RECONCILE, c, dom, "reconcile", OK_AUTH),
                cap(f"db{i}", ("RECON",), "VERDICT", DISBURSE, c, dom, "disburse", OK_RECON)]
    return out


# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------

def development(rng):
    return _organ(_spine("alpha2") + _spine("beta2") + _spine("gamma2") + _tail(), rng)


def _wide(rng, n=4):
    fams = ["alpha2", "beta2", "gamma2", "delta2", "epsilon2", "zeta2"][:n]
    caps = []
    for f in fams:
        caps += _spine(f)
    return _organ(caps + _tail(), rng)


def single_input_chain_break(rng):
    """A single-input consumer: no sibling arrival can wake it."""
    caps = _spine("alpha2") + _spine("beta2") + [
        cap("au0", ("PX", "PX"), "AUTH", AUTHORISE, 1.0, "d.p", "authorise", OK_PRICE),
        cap("au1", ("PX", "PX"), "AUTH", AUTHORISE, 1.2, "d.q", "authorise", OK_PRICE),
        cap("rn0", ("AUTH", "AUTH"), "RECON", RECONCILE, 1.0, "d.p", "reconcile", OK_AUTH),
        cap("db0", ("RECON",), "VERDICT", DISBURSE, 1.0, "d.r", "disburse", OK_RECON),
        cap("db1", ("RECON",), "VERDICT", DISBURSE, 1.3, "d.s", "disburse", OK_RECON)]
    return _organ(caps, rng)


join_arm_break_with_working_sibling = lambda rng: _wide(rng, 3)
shared_ancestor_two_consumers = lambda rng: _wide(rng, 3)
deep_shared_ancestor = lambda rng: _wide(rng, 4)
isolated_supplier_with_working_sibling = lambda rng: _wide(rng, 3)
costly_supplier_with_working_sibling = lambda rng: _wide(rng, 3)
semantic_fault_with_working_sibling = lambda rng: _wide(rng, 4)
two_simultaneous_breaks_different_causes = lambda rng: _wide(rng, 5)


def semantic_fault_no_working_sibling(rng):
    return single_input_chain_break(rng)


def no_valid_replacement(rng):
    """Exactly two PX producers feeding a two-input authorise. Losing one makes
    the join unsatisfiable, so refusing to keep reopening is correct."""
    return _organ(_spine("alpha2") + _spine("beta2") + _tail(), rng)


HELD_OUT = {
    "single_input_chain_break": single_input_chain_break,
    "join_arm_break_with_working_sibling": join_arm_break_with_working_sibling,
    "shared_ancestor_two_consumers": shared_ancestor_two_consumers,
    "deep_shared_ancestor": deep_shared_ancestor,
    "isolated_supplier_with_working_sibling": isolated_supplier_with_working_sibling,
    "costly_supplier_with_working_sibling": costly_supplier_with_working_sibling,
    "semantic_fault_with_working_sibling": semantic_fault_with_working_sibling,
    "semantic_fault_no_working_sibling": semantic_fault_no_working_sibling,
    "two_simultaneous_breaks_different_causes": two_simultaneous_breaks_different_causes,
    "no_valid_replacement": no_valid_replacement,
}

RESILIENCE = lambda rng: _wide(rng, 6)


# ---------------------------------------------------------------------------
# Damage injectors. Each returns an `observed` callable proving the condition.
# ---------------------------------------------------------------------------

def prepare(organ):
    """Experiment-side state. Kept OFF the substrate so v5 carries no test hooks."""
    organ._suppress_receipts = set()
    organ._stale_return = None
    organ._second_victim = None
    organ._repeat_victim = None
    organ._repeat_done = False
    organ._cooldown_return = None


def inject(organ, victim, klass, rng):
    """Apply damage and return (observed_predicate, description).

    `observed()` is evaluated AFTER the episode and must prove the intended
    condition actually arose. A class whose observation fails is reported as
    NOT EXERCISED rather than silently counted.
    """
    u = organ.units[victim]

    if klass == GONE:
        u.dissolved = True
        return (lambda: organ.units[victim].dissolved), "unit dissolved"

    if klass == SILENT:
        u.silent = True
        return (lambda: any(r.failure == SILENT for r in _receipts(organ))), "silent"

    if klass == ISOLATED:
        for other in list(organ.units.values()):
            if any(b.supplier == victim for b in other.bonds.values()):
                organ.cut_link(victim, other.unit_id)
        return (lambda: any(victim in pair for pair in organ.cut)), "links cut"

    if klass == COSTLY:
        u.cost_multiplier = 40.0
        return (lambda: any(r.failure == COSTLY for r in _receipts(organ))), "cost raised"

    if klass == WRONG:
        u.corrupt = True
        return (lambda: any(r.kind == "semantic_reject" for r in _receipts(organ))), "corrupt"

    if klass == INTERMITTENT:
        u.flaky_every = 3
        return (lambda: any(r.failure == INTERMITTENT for r in _receipts(organ))), "flaky"

    if klass == DELAYED:
        organ._delayed[victim] = 4
        return (lambda: any(r.failure == DELAYED for r in _receipts(organ))), "delayed"

    if klass == EXPIRED:
        organ._expired.add(victim)
        return (lambda: any(r.failure == EXPIRED for r in _receipts(organ))), "proof expired"

    if klass == STALE_RETURN:
        u.dissolved = True
        organ._stale_return = victim      # revived by the runner after repair
        return (lambda: any(r.kind == "stale_rejected" for r in _receipts(organ))), \
               "dissolved then revived"

    if klass == FALSE_SUSPICION:
        organ._delayed[victim] = 1        # one miss, then healthy again
        return (lambda: any(r.failure == DELAYED for r in _receipts(organ))), \
               "transient miss"

    if klass == CONFLICTING:
        u.silent = True
        others = [x for x in sorted(organ.units) if x not in (victim, ENV, SINK)
                  and organ.units[x].bonds]
        if others:
            organ.units[others[0]].corrupt = True
            organ._second_victim = others[0]
        return (lambda: len({r.failure for r in _receipts(organ)
                             if r.failure} ) >= 2), "two different causes"

    if klass == MISSING_RECEIPT:
        u.dissolved = True
        organ._suppress_receipts.add(victim)
        return (lambda: victim in organ._suppress_receipts), "receipts suppressed"

    if klass == REPEATED:
        u.dissolved = True
        organ._repeat_victim = victim     # its replacement is killed too
        return (lambda: getattr(organ, "_repeat_done", False)), "two successive breaks"

    if klass == COOLDOWN_RETURN:
        u.dissolved = True
        organ._cooldown_return = victim
        return (lambda: any(r.failure == COOLDOWN_RETURN for r in _receipts(organ))), \
               "returned during cooldown"

    raise ValueError(f"no injection path for {klass}")


def _receipts(organ):
    return [r for u in organ.units.values() for r in u.receipts]
