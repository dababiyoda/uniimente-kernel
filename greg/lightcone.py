"""Bounded competency scopes: the engineering form of a "cognitive light cone".

Michael Levin's TAME framework describes agents at every scale as feedback
systems pursuing goals, each bounded by a *cognitive light cone*: the spatial and
temporal extent of the states it can measure and try to change. Larger agents are
built from competent smaller agents whose goals they set rather than
micromanage. See Levin 2022, "Technological Approach to Mind Everywhere",
Frontiers in Systems Neuroscience, doi:10.3389/fnsys.2022.768201.

GREG uses the *effect*, not the biology (INTENT-0030). A ``LightCone`` is the
exact region of the world one competency may try to change:

* space      -> which capabilities, targets and data it may touch;
* magnitude  -> the highest consequence class and spend it may reach;
* time       -> the horizon until its mandate expires.

The institution is a hierarchy of such scopes: founder mandate -> mission ->
strategy -> worker lease -> single action. The invariant that makes the whole
safe is containment: a child scope is always inside its parent. Capability can
be copied downward; authority can never be enlarged downward or upward.
A light cone is a *bound*, never a grant: acting still requires the Kernel
Consequence Gate and a grant issued inside the cone.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from fnmatch import fnmatchcase

from capabilities.genome import CONSEQUENCE_CLASSES


class ScopeError(ValueError):
    """A scope is malformed or a child tried to escape its parent."""


def _rank(consequence_class: str) -> int:
    if consequence_class not in CONSEQUENCE_CLASSES:
        raise ScopeError(f"unknown consequence class {consequence_class!r}")
    return CONSEQUENCE_CLASSES.index(consequence_class)


def _instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ScopeError("horizon requires timezone")
    return parsed


@dataclass(frozen=True)
class LightCone:
    capabilities: frozenset[str]
    targets: tuple[str, ...]              # fnmatch patterns, e.g. "workspace:mission-7/*"
    max_consequence_class: str
    budget_usd: float
    horizon: str                          # RFC3339 expiry of this mandate
    data_classes: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self):
        _rank(self.max_consequence_class)
        if self.budget_usd < 0:
            raise ScopeError("budget may not be negative")
        if not self.targets:
            raise ScopeError("a scope must name at least one target pattern")
        if any(not isinstance(t, str) or not t or t.strip("*?") == "" for t in self.targets):
            raise ScopeError("unbounded target pattern is not a scope")
        if any(not c or c.strip("*?.") == "" for c in self.capabilities):
            raise ScopeError("unbounded capability pattern is not a scope")
        _instant(self.horizon)
        if self.max_consequence_class in ("financial", "irreversible"):
            raise ScopeError(f"{self.max_consequence_class} effects are never delegated to a scope; "
                             "each such action needs its own founder decision")

    @classmethod
    def from_dict(cls, value: dict) -> "LightCone":
        allowed = {"capabilities", "targets", "max_consequence_class", "budget_usd", "horizon", "data_classes"}
        if set(value) - allowed or not {"capabilities", "targets", "max_consequence_class",
                                        "budget_usd", "horizon"} <= set(value):
            raise ScopeError("unknown or missing scope field")
        return cls(capabilities=frozenset(value["capabilities"]), targets=tuple(value["targets"]),
                   max_consequence_class=value["max_consequence_class"],
                   budget_usd=float(value["budget_usd"]), horizon=value["horizon"],
                   data_classes=frozenset(value.get("data_classes", ())))

    def to_dict(self) -> dict:
        return {"capabilities": sorted(self.capabilities), "targets": list(self.targets),
                "max_consequence_class": self.max_consequence_class, "budget_usd": self.budget_usd,
                "horizon": self.horizon, "data_classes": sorted(self.data_classes)}

    def _capability_inside(self, capability: str) -> bool:
        # Patterns let a founder pre-authorize a function ("acquired.hash.sha256.*")
        # without knowing which installed tool Capability Genesis will find.
        return any(fnmatchcase(capability, pattern) for pattern in self.capabilities)

    def _target_inside(self, target: str) -> bool:
        return any(fnmatchcase(target, pattern) for pattern in self.targets)

    def admits(self, *, capability: str, target: str, consequence_class: str,
               cost_usd: float, spent_usd: float = 0.0, at: datetime | None = None) -> list[str]:
        """Return the reasons one action falls OUTSIDE this scope (empty = inside)."""
        at = at or datetime.now(timezone.utc)
        reasons = []
        if not self._capability_inside(capability):
            reasons.append(f"capability {capability!r} outside scope")
        if not self._target_inside(target):
            reasons.append(f"target {target!r} outside scope")
        if _rank(consequence_class) > _rank(self.max_consequence_class):
            reasons.append(f"{consequence_class} exceeds scope ceiling {self.max_consequence_class}")
        if cost_usd < 0 or spent_usd + cost_usd > self.budget_usd + 1e-9:
            reasons.append(f"cost {cost_usd} with {spent_usd} spent exceeds budget {self.budget_usd}")
        if at >= _instant(self.horizon):
            reasons.append("scope horizon has expired")
        return reasons

    def contains(self, child: "LightCone") -> list[str]:
        """Return the reasons ``child`` is NOT inside this scope (empty = contained)."""
        reasons = []
        extra = {c for c in child.capabilities if not self._capability_inside(c)}
        if extra:
            reasons.append(f"child adds capabilities {sorted(extra)}")
        for pattern in child.targets:
            # A child pattern is contained only if it names a sub-space of a
            # parent pattern. Literal targets are checked directly; wildcard
            # children must share a parent pattern's literal prefix.
            literal = pattern.split("*", 1)[0].split("?", 1)[0].split("[", 1)[0]
            if "*" in pattern or "?" in pattern or "[" in pattern:
                inside = any(p.endswith("*") and literal.startswith(p[:-1]) for p in self.targets)
            else:
                inside = self._target_inside(pattern)
            if not inside:
                reasons.append(f"child target {pattern!r} escapes parent targets")
        if _rank(child.max_consequence_class) > _rank(self.max_consequence_class):
            reasons.append("child consequence ceiling exceeds parent")
        if child.budget_usd > self.budget_usd + 1e-9:
            reasons.append("child budget exceeds parent")
        if _instant(child.horizon) > _instant(self.horizon):
            reasons.append("child horizon outlives parent")
        if child.data_classes - self.data_classes:
            reasons.append("child reaches additional data classes")
        return reasons

    def narrow(self, **changes) -> "LightCone":
        """Derive a child scope; refuses any change that would widen it."""
        values = self.to_dict()
        values.update(changes)
        child = LightCone.from_dict(values)
        problems = self.contains(child)
        if problems:
            raise ScopeError("; ".join(problems))
        return child
