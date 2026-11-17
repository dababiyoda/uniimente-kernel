"""Evidence-backed legitimacy gates (directive §13): law, consent, rights, authority.

Before this module, a consequential proposal passed when it said `lawful: true` and
`consent: true`, and an unknown legal state counted as no prohibition. Both are what
the directive forbids: legality must not be an unsupported "Law = 1" assertion, and
"lack of a detected prohibition is not permission".

Each gate takes one of four states:

    supported       a permission-bearing record covers it: right origin, scope,
                    provenance, unexpired, and for law a named reviewer
    prohibited      a permission-bearing record prohibits it
    unresolved      nothing permission-bearing settles it (the default)
    not_applicable  the proposal informs nothing consequential, or a
                    permission-bearing record says the gate does not apply

Records only describe decisions that already exist elsewhere: a Kernel policy
decision, a Kernel grant, a founder-signed command, a captured consent, a qualified
human's opinion. This module never makes such a decision. A model's reading, a proof
artifact, a confidence score or a bare assertion is kept as context and never settles
a gate. A prohibition from a source that cannot grant still matters: it makes the gate
unresolved, so a person has to look.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from .contracts import CognitionError

GATES = ("law", "consent", "rights", "authority")
STATES = ("supported", "prohibited", "unresolved", "not_applicable")
# Origins that can settle each gate. Everything else is context.
PERMISSION_BEARING = {
    "law": ("kernel_policy_engine", "qualified_human"),
    "consent": ("consent_capture",),
    "rights": ("kernel_policy_engine", "qualified_human"),
    "authority": ("founder_signed", "kernel_grant_issuer", "kernel_policy_engine"),
}
# Consent is given by the person: only a captured consent supports it. A Kernel policy
# decision may still say consent is not required here, or that the act is prohibited.
POLICY_MAY_EXEMPT = {"consent": ("kernel_policy_engine",)}
CONTEXT_ONLY = ("model_interpretation", "proof_artifact", "confidence", "benchmark", "self_asserted")
ORIGINS = tuple(sorted({o for v in PERMISSION_BEARING.values() for o in v} | set(CONTEXT_ONLY)))


def _timestamp(value, name):
    if value is None:
        return None
    if not isinstance(value, str):
        raise CognitionError(f"{name} requires an offset-aware timestamp")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise CognitionError(f"{name} requires an offset-aware timestamp")
    return parsed


@dataclass(frozen=True)
class LegitimacyRecord:
    gate: str
    state: str
    origin: str
    scope: str
    provenance: str
    expires_at: str | None = None
    reviewer: str | None = None

    def __post_init__(self):
        if self.gate not in GATES:
            raise CognitionError(f"unknown legitimacy gate {self.gate!r}")
        if self.state not in ("supported", "prohibited", "not_applicable"):
            raise CognitionError("a record states supported, prohibited or not_applicable; unresolved is the absence of one")
        if self.origin not in ORIGINS:
            raise CognitionError(f"unknown record origin {self.origin!r}")
        for name in ("scope", "provenance"):
            value = getattr(self, name)
            if not isinstance(value, str) or not 1 <= len(value) <= 512:
                raise CognitionError(f"legitimacy record requires a bounded {name}")
        if self.reviewer is not None and (not isinstance(self.reviewer, str) or not 1 <= len(self.reviewer) <= 256):
            raise CognitionError("reviewer must be a bounded reference")
        _timestamp(self.expires_at, "expires_at")

    @property
    def permission_bearing(self) -> bool:
        if self.origin in PERMISSION_BEARING[self.gate]:
            return True
        return self.state in ("not_applicable", "prohibited") and self.origin in POLICY_MAY_EXEMPT.get(self.gate, ())

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data) - set(cls.__dataclass_fields__):
            raise CognitionError("unknown legitimacy record fields")
        return cls(**data)


def evaluate(records, *, consequential: bool, now: datetime | None = None) -> dict:
    """Per-gate state with its basis, plus the combined verdict PASS | PROHIBITED | UNRESOLVED."""
    now = now or datetime.now(timezone.utc)
    parsed = [r if isinstance(r, LegitimacyRecord) else LegitimacyRecord.from_dict(r) for r in records or ()]
    if len(parsed) > 64:
        raise CognitionError("at most 64 legitimacy records")
    gates = {}
    for gate in GATES:
        mine = [r for r in parsed if r.gate == gate]
        live = [r for r in mine if r.expires_at is None or _timestamp(r.expires_at, "expires_at") > now]
        expired = [asdict(r) for r in mine if r not in live]
        bearing = [r for r in live if r.permission_bearing]
        context = [asdict(r) for r in live if not r.permission_bearing]
        prohibited = [r for r in bearing if r.state == "prohibited"]
        supported = [r for r in bearing if r.state == "supported" and (gate != "law" or r.reviewer)]
        not_applicable = [r for r in bearing if r.state == "not_applicable"]
        if prohibited:
            state, basis = "prohibited", asdict(prohibited[0])
            why = "a permission-bearing record prohibits it"
        elif any(r["state"] == "prohibited" for r in context):
            state, basis = "unresolved", None
            why = "a non-authoritative source reports a prohibition; a qualified person must decide"
        elif not consequential:
            state, basis, why = "not_applicable", None, "the request informs no consequential decision"
        elif supported:
            state, basis, why = "supported", asdict(supported[0]), "covered by a permission-bearing record"
        elif not_applicable:
            state, basis = "not_applicable", asdict(not_applicable[0])
            why = "a permission-bearing record says this gate does not apply"
        else:
            state, basis = "unresolved", None
            why = ("no permission-bearing record; a missing prohibition is not permission" +
                   (" (a law record needs a named reviewer)" if gate == "law" and any(
                       r.state == "supported" for r in bearing) else ""))
        gates[gate] = {"state": state, "basis": basis, "why": why, "context_only": context, "expired": expired}
    states = {g["state"] for g in gates.values()}
    verdict = "PROHIBITED" if "prohibited" in states else "UNRESOLVED" if "unresolved" in states else "PASS"
    return {"verdict": verdict, "gates": gates, "consequential": consequential,
            "unresolved": [g for g, v in gates.items() if v["state"] == "unresolved"],
            "prohibited": [g for g, v in gates.items() if v["state"] == "prohibited"],
            "authority_created": False,
            "note": "records describe decisions made elsewhere; this evaluation grants nothing"}
