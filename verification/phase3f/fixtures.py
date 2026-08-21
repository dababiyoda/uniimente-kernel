"""Phase 3F fixtures. Fresh capability classes, contracts, transforms, layouts.

The harness gives work units: available capabilities, their accepted and
produced types, resource domains, costs, and a local neighbourhood. It never
gives the target graph, an intermediate role sequence, a predetermined
attachment, a ranked selection, or the intended alternative route.
"""
from __future__ import annotations

import random

from substrate.v4 import Capability, Contract, Organ, Unit, Value

# -- deterministic transforms ----------------------------------------------
INTAKE = lambda s: str(s).strip()
NORMALISE = lambda s: str(s).lower()
ENRICH = lambda s: f"{s}|len={len(s)}"
ATTEST = lambda s: f"att:{sum(ord(c) for c in str(s)) % 9973}"
ATTEST2 = lambda s: f"att:{sum(ord(c) for c in str(s)) % 9973}"      # agrees
CROSS = lambda a, b: "AGREED" if a == b else "DISPUTED"
SETTLE = lambda s: "SETTLED" if s == "AGREED" else "REJECTED"
ADJUDICATE = lambda a, b: "ACCEPT" if a == b == "SETTLED" else "DECLINE"
EMIT = lambda s: s

ACCEPTED = Contract("fn:claim-settlement", "RAW", "VERDICT",
                    lambda v: v.payload == "ACCEPT")


def cap(name, accepts, produces, fn, cost=1.0, dom="shared", cls=""):
    return Capability(name, accepts, produces, fn, cost, dom, cls or name)


def _organ(caps, contract, rng, density=0.75):
    units = [Unit(unit_id=f"{c.klass()}.{i}", capability=c) for i, c in enumerate(caps)]
    o = Organ(units, contract)
    ids = list(o.units)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if a in ("@env", "@sink") or b in ("@env", "@sink") or rng.random() < density:
                o.connect(a, b)
    return o


def _spine(fam, dom=None, attest=ATTEST, cost=1.0):
    d = dom or f"d.{fam}"
    return [cap(f"in.{fam}", ("RAW",), "CLEAN", INTAKE, cost, d, "intake"),
            cap(f"nm.{fam}", ("CLEAN",), "NORM", NORMALISE, cost, d, "normalise"),
            cap(f"en.{fam}", ("NORM",), "RICH", ENRICH, cost, d, "enrich"),
            cap(f"at.{fam}", ("RICH",), "ATT", attest, cost, d, "attest")]


def _tail(n=2):
    """Two routes to VERDICT, so a lost terminal is recoverable."""
    out = []
    for i, (dom, c) in enumerate((("d.x", 1.0), ("d.y", 1.3))[:n]):
        out += [cap(f"cx{i}", ("ATT", "ATT"), "AGREE", CROSS, c, dom, "crosscheck"),
                cap(f"st{i}", ("AGREE",), "SET", SETTLE, c, dom, "settle"),
                cap(f"aj{i}", ("SET", "SET"), "VERDICT", ADJUDICATE, c, dom, "adjudicate")]
    return out


# ---------------------------------------------------------------------------
# Ten held-out structures
# ---------------------------------------------------------------------------

def interior_join_supplier_lost(rng):
    return _organ(_spine("sigma") + _spine("tau") + _spine("upsilon") + _tail(),
                  ACCEPTED, rng)


def interior_chain_midpoint_lost(rng):
    return _organ(_spine("sigma") + _spine("tau") + _spine("phi") + _tail(),
                  ACCEPTED, rng)


def quorum_member_semantically_wrong(rng):
    bad = lambda s: "att:WRONG"
    return _organ(_spine("sigma") + _spine("tau") + _spine("chi", attest=bad)
                  + _spine("psi") + _tail(), ACCEPTED, rng)


def deep_interior_two_levels_down(rng):
    return _organ(_spine("sigma") + _spine("tau") + _spine("upsilon")
                  + _spine("phi") + _tail(), ACCEPTED, rng)


def interior_supplier_isolated(rng):
    return _organ(_spine("sigma") + _spine("tau") + _spine("upsilon") + _tail(),
                  ACCEPTED, rng)


def interior_supplier_too_expensive(rng):
    return _organ(_spine("sigma") + _spine("tau") + _spine("upsilon", cost=1.0)
                  + _tail(), ACCEPTED, rng)


def two_simultaneous_interior_failures(rng):
    return _organ(_spine("sigma") + _spine("tau") + _spine("upsilon")
                  + _spine("phi") + _spine("chi") + _tail(), ACCEPTED, rng)


def stale_supplier_returns_after_replacement(rng):
    return _organ(_spine("sigma") + _spine("tau") + _spine("upsilon") + _tail(),
                  ACCEPTED, rng)


def intermittent_interior_supplier(rng):
    return _organ(_spine("sigma") + _spine("tau") + _spine("upsilon") + _tail(),
                  ACCEPTED, rng)


def no_valid_replacement_exists(rng):
    """Exactly two attest capabilities feeding a two-input crosscheck.

    It forms healthily. Losing either attest leaves only one ATT producer, and
    a join may not take one supplier twice, so NO valid replacement exists. The
    correct behaviour is a bounded escalation, not an infinite retry - and
    refusing to keep reopening is the right decision, not a failure."""
    return _organ(_spine("sigma") + _spine("tau") + _tail(), ACCEPTED, rng)


HELD_OUT = {
    "interior_join_supplier_lost": interior_join_supplier_lost,
    "interior_chain_midpoint_lost": interior_chain_midpoint_lost,
    "quorum_member_semantically_wrong": quorum_member_semantically_wrong,
    "deep_interior_two_levels_down": deep_interior_two_levels_down,
    "interior_supplier_isolated": interior_supplier_isolated,
    "interior_supplier_too_expensive": interior_supplier_too_expensive,
    "two_simultaneous_interior_failures": two_simultaneous_interior_failures,
    "stale_supplier_returns_after_replacement": stale_supplier_returns_after_replacement,
    "intermittent_interior_supplier": intermittent_interior_supplier,
    "no_valid_replacement_exists": no_valid_replacement_exists,
}


def development(rng):
    return _organ(_spine("sigma") + _spine("tau") + _spine("upsilon") + _tail(),
                  ACCEPTED, rng)


def resilience(rng):
    """Deliberately over-provisioned: damage should NOT cost the result."""
    return _organ(_spine("sigma") + _spine("tau") + _spine("upsilon")
                  + _spine("phi") + _spine("chi") + _spine("psi") + _tail(),
                  ACCEPTED, rng)
