"""Standing method grants: the founder pre-authorizes a reviewed set of read-only cognition methods, once.

Problem (reproduced by ``tests/unit/test_greg_cognition_genesis.py``): a signed mission whose question fits a
registered, verified, read-only intelligence (``cognition.queue_erlang``, DEFAULT for its geometry on frozen
held-out evidence) stopped and asked for a CAPABILITY_ATTACH every time the method was withheld. Even a signed
read-only ``auto_attach`` never attaches a cognition method, by design: an attach is global and outlives the
mission. So each new question in a family the founder had already reviewed cost a founder action.

Mechanism: a founder-signed ``METHOD_GRANT`` command names, exactly,

* ``capabilities``: the registered cognition methods it covers (each must be a read-only ``cognition.*``
  capability; nothing else is grantable);
* ``targets``: the mission targets (data) it covers, as exact names or ``prefix*`` patterns;
* ``until``: when it ends (at most 30 days after it is issued);
* ``max_uses``: how many answers it may serve.

While it is live, a covered mission's cognition step sees those methods as usable in a per-call registry view.
The body's registry is never changed, so nothing is attached, and the grant ends the moment it expires, is used
up, or is revoked (``METHOD_GRANT_REVOKE``). A founder ``CAPABILITY_DETACH`` or a quarantine of one method
withholds it at once, grant or not. A step served under a grant is recorded as ``method_grant.used``, with its
receipt.

What a grant never does: it attaches nothing, widens no light cone, grants no spend, sending, publication,
deployment, credential or permission change, and it applies only to steps the signed mission already
authorizes (its own capability, target, ceiling and budget). It covers only read-only missions. Building is
not installing, installing is not activating, and activating grants no consequence authority.
"""
from __future__ import annotations

from datetime import datetime, timedelta
import fnmatch
import json
import re

from provenance.ledger import sha256_json

ISSUE_KIND, REVOKE_KIND = "METHOD_GRANT", "METHOD_GRANT_REVOKE"
MAX_WINDOW = timedelta(days=30)
MAX_CAPABILITIES, MAX_TARGETS, MAX_USES = 32, 16, 1000
_ID = re.compile(r"^[a-z0-9][a-z0-9_.:-]{2,95}$")
_CAP = re.compile(r"^cognition\.[A-Za-z0-9_.:@-]{1,120}$")
_TARGET = re.compile(r"^[A-Za-z0-9_.:/@-]{1,160}\*?$")


class GrantError(ValueError):
    """A malformed or out-of-bounds grant command. Retained as data, never executed."""


def _time(text, name) -> datetime:
    try:
        value = datetime.fromisoformat(str(text).replace("Z", "+00:00"))
    except ValueError:
        raise GrantError(f"{name} must be an ISO 8601 time") from None
    if value.tzinfo is None:
        raise GrantError(f"{name} must carry a time zone")
    return value


def validate_issue(body: dict, now: datetime) -> dict:
    """The grant exactly as signed, or GrantError. Bounds are checked at issue, in the body's own clock."""
    if not isinstance(body, dict) or set(body) != {"grant_id", "capabilities", "targets", "until", "max_uses",
                                                   "purpose"}:
        raise GrantError("a method grant takes exactly grant_id, capabilities, targets, until, max_uses and purpose")
    gid, caps, targets = body["grant_id"], body["capabilities"], body["targets"]
    if not isinstance(gid, str) or not _ID.match(gid):
        raise GrantError("grant_id: 3-96 lowercase letters, digits and _ . : -")
    if not isinstance(caps, list) or not 1 <= len(caps) <= MAX_CAPABILITIES or len(set(caps)) != len(caps) \
            or not all(isinstance(c, str) and _CAP.match(c) and "*" not in c for c in caps):
        raise GrantError(f"capabilities: 1-{MAX_CAPABILITIES} distinct exact cognition.* identities, no wildcards")
    if not isinstance(targets, list) or not 1 <= len(targets) <= MAX_TARGETS or len(set(targets)) != len(targets) \
            or not all(isinstance(t, str) and _TARGET.match(t) and t != "*" for t in targets):
        raise GrantError(f"targets: 1-{MAX_TARGETS} distinct exact names or prefix* patterns; '*' alone is refused")
    until = _time(body["until"], "until")
    if not now < until <= now + MAX_WINDOW:
        raise GrantError(f"until must be in the future and at most {MAX_WINDOW.days} days away")
    uses = body["max_uses"]
    if isinstance(uses, bool) or not isinstance(uses, int) or not 1 <= uses <= MAX_USES:
        raise GrantError(f"max_uses: an integer from 1 to {MAX_USES}")
    if not isinstance(body["purpose"], str) or not body["purpose"].strip() or len(body["purpose"]) > 500:
        raise GrantError("purpose: a short statement of what the grant is for")
    return {"grant_id": gid, "capabilities": list(caps), "targets": list(targets), "until": until.isoformat(),
            "max_uses": uses, "purpose": body["purpose"].strip()}


def validate_revoke(body: dict) -> dict:
    if not isinstance(body, dict) or set(body) - {"grant_id", "reason"} or "grant_id" not in body \
            or not isinstance(body["grant_id"], str) or not _ID.match(body["grant_id"]):
        raise GrantError("a revocation takes grant_id and an optional reason")
    return {"grant_id": body["grant_id"], "reason": str(body.get("reason", ""))[:500]}


def grants(journal) -> dict:
    """Every grant ever issued, with its revocation and use count, by grant id (a projection of the journal)."""
    out = {}
    if journal is None:
        return out
    for event in journal.replay("method_grant."):
        data = event.payload
        if event.type.endswith("method_grant.issued") and data["grant_id"] not in out:
            out[data["grant_id"]] = {**data, "revoked": None, "uses": 0}
        elif event.type.endswith("method_grant.revoked") and data["grant_id"] in out:
            out[data["grant_id"]]["revoked"] = out[data["grant_id"]]["revoked"] or data
        elif event.type.endswith("method_grant.used") and data["grant_id"] in out:
            out[data["grant_id"]]["uses"] += 1
    return out


def status(grant: dict, now: datetime) -> str:
    if grant["revoked"]:
        return "REVOKED"
    if now >= _time(grant["until"], "until"):
        return "EXPIRED"
    if grant["uses"] >= grant["max_uses"]:
        return "USED_UP"
    return "LIVE"


def _covers_target(grant: dict, target: str) -> bool:
    return any(fnmatch.fnmatchcase(target, t) if t.endswith("*") else target == t for t in grant["targets"])


def covering(journal, *, target: str, ceiling: str, now: datetime) -> list[dict]:
    """The live grants that apply to one step: a read-only mission's step on a covered target."""
    if ceiling != "read_only":
        return []
    return [g for g in grants(journal).values() if status(g, now) == "LIVE" and _covers_target(g, target)]


class GrantView:
    """One call's registry view: the granted methods count as usable; the body's registry is untouched.

    Only a method that is registered, read-only, in state VERIFIED and available is lifted. A founder-detached,
    quarantined or unregistered method stays withheld, and a method already ATTACHED is served as before."""

    def __init__(self, registry, live: list[dict]):
        self._registry = registry
        self.lifted = {}
        for grant in live:
            for cid in grant["capabilities"]:
                manifest = registry.manifests.get(cid)
                if (manifest is not None and manifest.consequence_class == "read_only"
                        and registry.state.get(cid) == "VERIFIED" and cid not in self.lifted):
                    self.lifted[cid] = grant["grant_id"]
        self.state = {**registry.state, **{cid: "ATTACHED" for cid in self.lifted}}

    def usable(self, capability_id: str) -> tuple[bool, str]:
        if capability_id in self.lifted:
            ok, why = self._registry.manifests[capability_id].available()
            return (ok, f"usable under method grant {self.lifted[capability_id]}") if ok else (ok, why)
        return self._registry.usable(capability_id)

    def set_state(self, *_args, **_kw):
        raise PermissionError("a method grant view is read-only; it never attaches or detaches")

    def __getattr__(self, name):
        return getattr(self._registry, name)


def view(registry, journal, *, target: str, ceiling: str, now: datetime):
    """The registry a covered cognition step sees: a GrantView when a live grant lifts something, else the
    registry itself."""
    live = covering(journal, target=target, ceiling=ceiling, now=now)
    if not live:
        return registry
    granted = GrantView(registry, live)
    return granted if granted.lifted else registry


def _selected(output) -> set[str]:
    """The method identities an answer says it used (compile and composition receipts)."""
    if not isinstance(output, dict):
        return set()
    names = set()
    for key in ("method_or_composition_selected", "method"):
        value = output.get(key)
        if isinstance(value, str):
            names.update(re.findall(r"cognition\.[A-Za-z0-9_.:@-]+", value) or [value])
        elif isinstance(value, list):
            names.update(v for v in value if isinstance(v, str))
    for stage in output.get("stages", []) if isinstance(output.get("stages"), list) else []:
        if isinstance(stage, dict) and isinstance(stage.get("method"), str):
            names.add(stage["method"])
    return names


def record_uses(journal, registry_view, *, mission_id: str, target: str, output, receipt_ref, now) -> list[str]:
    """After a DONE step: one ``method_grant.used`` per granted method the answer used. Returns their ids."""
    if not isinstance(registry_view, GrantView) or journal is None:
        return []
    used = sorted(_selected(output) & set(registry_view.lifted))
    for cid in used:
        gid = registry_view.lifted[cid]
        journal.record("method_grant.used", {"grant_id": gid, "capability_id": cid, "mission_id": mission_id,
                                             "target": target, "receipt": receipt_ref, "at": now.isoformat(),
                                             "authority_created": False},
                       key=["method_grant.used", gid, cid, mission_id, str(receipt_ref), sha256_json(target)])
    return used


def summary(journal, now: datetime) -> list[dict]:
    """Read-only: every grant with its status, what it covers and how much of it is used."""
    return [{"grant_id": g["grant_id"], "status": status(g, now), "capabilities": g["capabilities"],
             "targets": g["targets"], "until": g["until"], "uses": g["uses"], "max_uses": g["max_uses"],
             "purpose": g["purpose"], "authority_created": False}
            for g in sorted(grants(journal).values(), key=lambda g: g["grant_id"])]


def describe(grant: dict) -> str:
    return json.dumps({k: grant[k] for k in ("grant_id", "capabilities", "targets", "until", "max_uses")})
