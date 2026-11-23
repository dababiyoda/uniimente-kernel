"""Abstention-to-resolution: the one founder decision that would let an abstaining cognition step answer.

A cognition receipt that abstains already says why (the cortex's disposition and eligibility, the compiler's missing
information, derived geometry and capability deficit), but in a form only a careful reader can act on. ``derive``
turns that into one typed ``resolution`` on the receipt:

* ``SUPPLY_INPUTS``: a route that answers the declared class exists, and the request carries none of its input;
* ``CORRECT_DECLARATION``: the request's own inputs fit another class than the one declared;
* ``ATTACH``: the capability that answers is built and verified, and only the founder's detach withholds it;
* ``SELECT_LOCAL_MODEL``: the answering route needs a local model no one has selected;
* ``HUMAN_HANDOFF``: the question belongs to a person (victim protection, human authority, contested judgment);
* ``FORM``: nothing catalogued answers; Capability Genesis searches, unchanged.

A resolution is a proposal read from the receipt, never a verified fact and never authority (``verified`` is always
False). The mission engine (``MissionEngine._resolution_ask``) turns it into one ask of an existing kind carrying an
unsigned prepared command; only the founder's signature acts. ``read`` is the one place the engine reads it.

Mechanism: #167's typed deficit (the Seed Cortex reports what is missing; nothing consumed it at runtime) recombined
with this line's mission engine and Capability Genesis (which consumed abstentions untyped). Pre-registered at
``docs/evidence/greg-abstention-resolution/2026-11-13/PREREGISTRATION.md``.
"""
from __future__ import annotations

KINDS = ("SUPPLY_INPUTS", "CORRECT_DECLARATION", "ATTACH", "SELECT_LOCAL_MODEL", "HUMAN_HANDOFF", "FORM")
AUTHORITY = "none: a proposal read from the receipt; GREG acts only on a signed founder command"
# The payload part each cortex solver organ reads, by the cortex's own route policy (cortex/routing.py _route_parts;
# CP-SAT is the second engine behind the one formal_model contract). tests/unit/test_greg_resolution.py keeps this
# equal to greg/cognition/bridge.py ORGANS (no silent drift).
PART_OF = {
    "cortex.formal.z3@0.2.0": "formal_model",
    "cortex.optimization.cpsat@0.2.0": "formal_model",
    "cortex.extraction.schedule@0.1.0": "schedule_request",
    "cortex.estimation.fermi@0.1.0": "estimation_model",
    "cortex.deterrence.accountability@0.1.0": "deterrence_model",
    "cortex.evidence_causal@0.1.0": "claim",
    "cortex.semantic@0.1.0": "sources",
}
# route policy order: the organ a part is routed to first comes first
POLICY = tuple(PART_OF)
_WITHHELD = "withheld by host registry"
_HANDOFF_STATES = ("REQUIRES_HUMAN_AUTHORITY", "CONTESTED", "GATE_UNRESOLVED")


def _resolution(kind: str, why: str, **fields) -> dict:
    return {"kind": kind, "why": why[:400], "verified": False, "authority": AUTHORITY, **fields}


def _supported(organ: str) -> tuple:
    from cortex.genome import seed_registry
    profile = seed_registry().profiles().get(organ)
    return tuple(profile.supported_geometries) if profile else ()


def _compile_class(cortex_class: str) -> str:
    from .bridge import _CLASS
    return _CLASS.get(cortex_class, cortex_class)


def _parts_for(compile_class: str) -> list:
    """The cortex parts whose organs serve ``compile_class`` (a compiler geometry name), in route policy order."""
    out = []
    for organ in POLICY:
        if any(_compile_class(c) == compile_class for c in _supported(organ)) and PART_OF[organ] not in out:
            out.append(PART_OF[organ])
    return out


def from_cortex(receipt: dict, payload: dict) -> dict | None:
    """A resolution for a cortex receipt (``proof_artifact`` of a cognitive receipt) and the payload it was asked."""
    from .bridge import ORGANS
    if not isinstance(receipt, dict):
        return None
    out = receipt.get("output") or {}
    state = out.get("state")
    disposition = receipt.get("disposition") or {}
    geometry = receipt.get("geometry") or {}
    klass = geometry.get("epistemic_class")
    eligibility = [e for e in receipt.get("eligibility") or [] if isinstance(e, dict)]
    if disposition.get("kind") == "handoff" or state in _HANDOFF_STATES:
        return _resolution("HUMAN_HANDOFF", str(disposition.get("reason") or state),
                           next_step=str(disposition.get("next_step") or "")[:400])
    if state == "INSUFFICIENT_EVIDENCE":
        eligible = [e["key"] for e in eligibility if e.get("eligible")]
        parts = [PART_OF[k] for k in POLICY if k in eligible]
        parts = list(dict.fromkeys(parts))
        if parts:
            return _resolution("SUPPLY_INPUTS", f"route(s) {eligible} answer {klass} and the request carries none of "
                                                f"their inputs", inputs=parts, epistemic_class=klass)
    withheld = [e["key"] for e in eligibility
                if e.get("reasons") and all(str(r).startswith(_WITHHELD) for r in e["reasons"])]
    if withheld and (out.get("answer") is None or receipt_unanswered(receipt)):
        # an organ that reads a part the request carries comes first: that part is the one left unanswered
        ordered = sorted(withheld, key=lambda k: (PART_OF.get(k) not in payload, POLICY.index(k) if k in POLICY else 99))
        capabilities = [ORGANS[k] for k in ordered if k in ORGANS]
        if capabilities:
            return _resolution("ATTACH", f"{capabilities} answer this and are built and verified; the founder's "
                                         f"detach withholds them", capabilities=capabilities)
    if state == "DEPENDENCY_UNAVAILABLE":
        routes = [r.get("organ_id") for r in out.get("per_route") or [] if isinstance(r, dict)]
        return _resolution("SELECT_LOCAL_MODEL", f"route(s) {routes} need a local model none is selected for",
                           routes=routes)
    if state in ("NO_ELIGIBLE_METHOD", "UNSUPPORTED_GEOMETRY"):
        from cortex.routing import _structural_classes
        fits = [c for c in _structural_classes(payload) if c != klass]
        if klass and fits and klass not in _structural_classes(payload):
            return _resolution("CORRECT_DECLARATION", f"declared {klass} but the inputs fit {fits}",
                               declare=fits[0], declared=klass)
        return _resolution("FORM", f"no catalogued route answers {klass}")
    return None


def receipt_unanswered(receipt: dict) -> bool:
    return "unanswered" in str((receipt.get("disposition") or {}).get("next_step", "")) or \
        "no eligible route" in str((receipt.get("disposition") or {}).get("reason", ""))


def from_compile(receipt: dict) -> dict | None:
    """A resolution for a compile receipt (greg/cognition/compiler.py ``run``)."""
    if not isinstance(receipt, dict):
        return None
    state = receipt.get("state")
    declared = (receipt.get("geometry") or {}).get("geometry")
    derived = receipt.get("derived_geometry") or {}
    if state == "HUMAN_JUDGMENT_REQUIRED":
        return _resolution("HUMAN_HANDOFF", "the compiled question needs a human judgment it cannot make")
    if state == "CAPABILITY_DEFICIT":
        deficit = receipt.get("capability_deficit") or {}
        unserviceable = (deficit.get("verification") or {}).get("unserviceable") or []
        if any(isinstance(u, dict) and "DETACHED" in str(u.get("why", "")) for u in unserviceable):
            # A compile family the founder detached is Capability Genesis's: its awaiting-attach blocker names every
            # candidate and never re-proposes the one just detached (test_greg_cognition_genesis.py). No resolution.
            return None
        fits = derived.get("fits_by_inputs") or []
        if derived.get("agrees") is False and fits:
            return _resolution("CORRECT_DECLARATION", f"declared {declared} but the inputs fit {fits}",
                               declare=fits[0], declared=declared)
        return _resolution("FORM", f"no catalogued method answers {deficit.get('function')}")
    if state == "ABSTAIN" and receipt.get("missing_information") and declared:
        parts = _parts_for(declared)
        if parts:
            return _resolution("SUPPLY_INPUTS", f"{declared} is answered by the cortex route(s) that read {parts}; "
                                                f"the request carries none of them", inputs=parts,
                               epistemic_class=declared)
        lacking = sorted((m for m in receipt["missing_information"] if isinstance(m, dict) and m.get("missing_inputs")),
                         key=lambda m: len(m["missing_inputs"]))
        if lacking:
            return _resolution("SUPPLY_INPUTS", f"{lacking[0].get('method')} answers {declared} and lacks "
                                                f"{lacking[0]['missing_inputs']}", inputs=list(lacking[0]["missing_inputs"]),
                               epistemic_class=declared)
    return None


def check(resolution) -> dict | None:
    """A well-formed resolution, or None. It never carries authority and is never verified."""
    if not isinstance(resolution, dict) or resolution.get("kind") not in KINDS:
        return None
    if resolution.get("verified") is not False or resolution.get("authority") != AUTHORITY:
        return None
    return resolution


def read(receipt) -> dict | None:
    """The resolution a cognition receipt carries, for the mission engine; None when it carries none."""
    return check(receipt.get("resolution")) if isinstance(receipt, dict) else None
