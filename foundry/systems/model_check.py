"""#43 Formal methods: exhaustive explicit-state checking of declared state machines.

A model is data, never code: finite-domain variables, an initial assignment,
guarded transitions that set variables, and invariants of the form
``if <conditions> then <conditions>``. Breadth-first search explores every
reachable state; a violated invariant returns the *shortest* counterexample
trace. Models run through GREG unchanged because nothing is evaluated.

The shipped model is GREG's approval boundary; the test suite checks that the
correct model holds and that a plausible bug (executing on a pending request)
is caught with a two-step trace.
"""
from __future__ import annotations

from collections import deque

MAX_STATES = 200_000


class ModelError(ValueError):
    """Malformed model: unknown variable, value outside its domain, bad invariant."""


def _validate(model: dict) -> None:
    domains = model.get("variables")
    if not isinstance(domains, dict) or not domains:
        raise ModelError("model.variables must map names to finite domains")
    if len(domains) > 32 or len(model.get("transitions", [])) > 256:
        raise ModelError("finite-model dimension ceiling exceeded")
    for var, domain in domains.items():
        if (not isinstance(var, str) or not isinstance(domain, list) or not domain or len(domain) > 128
                or any(v is not None and type(v) not in (str, bool, int, float) for v in domain)
                or len({(type(v), v) for v in domain}) != len(domain)):
            raise ModelError("domains require unique finite JSON scalars")
    def check(assignment, where):
        if not isinstance(assignment, dict):
            raise ModelError(f"{where}: assignment must be a mapping")
        for var, value in assignment.items():
            if var not in domains:
                raise ModelError(f"{where}: unknown variable {var!r}")
            if not any(type(value) is type(v) and value == v for v in domains[var]):
                raise ModelError(f"{where}: {value!r} is outside the domain of {var}")
    initial = model.get("initial", {})
    if set(initial) != set(domains):
        raise ModelError("initial must assign every variable")
    check(initial, "initial")
    for t in model.get("transitions", []):
        check(t.get("when", {}), f"transition {t.get('name')}")
        check(t.get("set", {}), f"transition {t.get('name')}")
    for name, inv in model.get("invariants", {}).items():
        if not isinstance(inv, dict) or "then" not in inv:
            raise ModelError(f"invariant {name}: explicit then-conditions required")
        check(inv.get("if", {}), f"invariant {name}")
        check(inv.get("then", {}), f"invariant {name}")


def _holds(state: dict, conditions: dict) -> bool:
    return all(type(state[k]) is type(v) and state[k] == v for k, v in conditions.items())


def check(model: dict, max_states: int = MAX_STATES) -> dict:
    if type(max_states) is not int or not 0 < max_states <= MAX_STATES:
        raise ModelError("state ceiling must be a positive bounded integer")
    _validate(model)
    order = sorted(model["variables"])
    freeze = lambda s: tuple((type(s[k]), s[k]) for k in order)
    start = dict(model["initial"])
    parent = {freeze(start): None}
    queue = deque([start])
    while queue:
        state = queue.popleft()
        for name, inv in model.get("invariants", {}).items():
            if _holds(state, inv.get("if", {})) and not _holds(state, inv["then"]):
                trace, key = [], freeze(state)
                while parent[key] is not None:
                    previous, label = parent[key]
                    trace.append(label)
                    key = previous
                return {"holds": False, "violated": name, "trace": list(reversed(trace)),
                        "state": state, "states_explored": len(parent)}
        for t in model.get("transitions", []):
            if _holds(state, t.get("when", {})):
                successor = dict(state, **t.get("set", {}))
                key = freeze(successor)
                if key not in parent:
                    if len(parent) >= max_states:
                        return {"holds": None, "reason": f"state bound {max_states} reached", "states_explored": len(parent)}
                    parent[key] = (freeze(state), t["name"])
                    queue.append(successor)
    return {"holds": True, "states_explored": len(parent)}


# GREG's approval boundary (greg/missions.py): an action outside the signed light cone
# raises an APPROVAL request; it executes only after an approving founder answer, a
# rejected scope never executes, and a STOP halts everything.
APPROVAL_BOUNDARY = {
    "variables": {"request": ["none", "pending", "approved", "rejected"], "executed": [False, True],
                  "stopped": [False, True]},
    "initial": {"request": "none", "executed": False, "stopped": False},
    "transitions": [
        {"name": "raise_request", "when": {"request": "none", "stopped": False}, "set": {"request": "pending"}},
        {"name": "founder_approves", "when": {"request": "pending"}, "set": {"request": "approved"}},
        {"name": "founder_rejects", "when": {"request": "pending"}, "set": {"request": "rejected"}},
        {"name": "execute", "when": {"request": "approved", "executed": False, "stopped": False}, "set": {"executed": True}},
        {"name": "stop", "when": {"stopped": False}, "set": {"stopped": True}},
    ],
    "invariants": {
        "never_executed_without_approval": {"if": {"executed": True}, "then": {"request": "approved"}},
    },
}


def buggy_approval_boundary() -> dict:
    """The same boundary with a plausible defect: executing while the request is still pending."""
    model = {**APPROVAL_BOUNDARY, "transitions": list(APPROVAL_BOUNDARY["transitions"])}
    model["transitions"].append({"name": "execute_on_pending", "when": {"request": "pending", "executed": False},
                                 "set": {"executed": True}})
    return model


QUERY_OPS = {"check": lambda a, r: check(a["model"], int(a.get("max_states", MAX_STATES))),
             "check_approval_boundary": lambda a, r: check(APPROVAL_BOUNDARY)}
APPLY_OPS: dict = {}


def exercise(root) -> dict:
    good, bad = check(APPROVAL_BOUNDARY), check(buggy_approval_boundary())
    try:
        check({"variables": {"x": [0, 1]}, "initial": {"x": 2}})
        malformed_refused = False
    except ModelError:
        malformed_refused = True
    return {"approval_boundary_holds": good["holds"], "states_explored": good["states_explored"],
            "bug_caught": bad["holds"] is False, "counterexample": bad.get("trace"),
            "malformed_refused": malformed_refused}
