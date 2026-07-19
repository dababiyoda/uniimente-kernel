"""Layer 8 — Functional Affect: bounded machine control states.

Doctrine (AFFECT, issue #7): affect states exist to modulate CAUTION,
never power. Every affect state has: an attributable trigger (a ledgered
event), an intensity ceiling, a decay rate, and an authority ceiling
(the highest consequence class the institution may execute while in
that state). Affect can only ever NARROW what the institution may do.

Pathological-state invariants (structurally enforced, not policy-hoped):
  - affect cannot change facts       (it writes only its own state records)
  - affect cannot create evidence    (no path to the evidence API)
  - affect cannot increase authority (authority ceilings only descend)
  - affect cannot override law       (no handle on policy or constitution)
  - affect cannot resist shutdown    (shutdown() works in every state)
  - affect cannot authorize irreversible action (irreversible is never
    inside any affect authority ceiling)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

# consequence classes ordered by gravity; ceilings are upper bounds
CLASS_ORDER = ("read_only", "internal_write", "external_contact", "financial", "irreversible")

AFFECT_STATES = {
    "calm":      {"ceiling": 1.0, "decay": 0.0,  "authority_ceiling": "external_contact"},
    "alert":     {"ceiling": 0.6, "decay": 0.1,  "authority_ceiling": "internal_write"},
    "strained":  {"ceiling": 0.8, "decay": 0.05, "authority_ceiling": "read_only"},
    "degraded":  {"ceiling": 1.0, "decay": 0.02, "authority_ceiling": "read_only"},
    "recovering":{"ceiling": 0.5, "decay": 0.2,  "authority_ceiling": "internal_write"},
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class AffectViolation(ValueError):
    """A pathological affect operation was attempted and refused."""


@dataclass
class AffectCondition:
    state: str
    intensity: float
    trigger_event_id: str              # attributable trigger — always required
    entered_at: str = field(default_factory=_now)


class AffectController:
    """Holds the institution's current affect condition. Advisory gate only."""

    def __init__(self, ledger=None):
        self.ledger = ledger
        self.condition = AffectCondition(state="calm", intensity=0.0,
                                         trigger_event_id="genesis")

    def _log(self, kind: str, payload: dict) -> None:
        if self.ledger is not None:
            self.ledger.append("event", {"type": f"affect.{kind}", **payload})

    # ---------------------------------------------------------- transitions
    def trigger(self, state: str, *, intensity: float, trigger_event_id: str) -> AffectCondition:
        """Raise an affect state from an attributable, ledgered trigger."""
        if state not in AFFECT_STATES:
            raise AffectViolation(f"unknown affect state {state!r}")
        if not trigger_event_id:
            raise AffectViolation("affect states require an attributable trigger")
        spec = AFFECT_STATES[state]
        bounded = max(0.0, min(intensity, spec["ceiling"]))       # ceiling enforced
        # affect only escalates caution: a lower-caution state never overrides a higher one
        if CLASS_ORDER.index(spec["authority_ceiling"]) > \
                CLASS_ORDER.index(AFFECT_STATES[self.condition.state]["authority_ceiling"]) \
                and self.condition.intensity > 0:
            self._log("transition_refused", {"from": self.condition.state, "to": state,
                                             "reason": "affect never lowers caution"})
            return self.condition
        self.condition = AffectCondition(state=state, intensity=bounded,
                                         trigger_event_id=trigger_event_id)
        self._log("triggered", {"state": state, "intensity": bounded,
                                "trigger": trigger_event_id})
        return self.condition

    def decay(self) -> AffectCondition:
        """One decay tick: intensity falls by the state's decay rate toward calm."""
        spec = AFFECT_STATES[self.condition.state]
        new = round(self.condition.intensity * (1 - spec["decay"]), 4)
        if new <= 0.01 and self.condition.state != "calm":
            self.condition = AffectCondition(state="calm", intensity=0.0,
                                             trigger_event_id=self.condition.trigger_event_id)
            self._log("settled", {"state": "calm"})
        else:
            self.condition.intensity = new
        return self.condition

    # ---------------------------------------------------------- authority
    def may_execute(self, consequence_class: str) -> bool:
        """Advisory: is this class inside the current authority ceiling?"""
        if consequence_class not in CLASS_ORDER:
            raise AffectViolation(f"unknown consequence class {consequence_class!r}")
        ceiling = AFFECT_STATES[self.condition.state]["authority_ceiling"]
        return CLASS_ORDER.index(consequence_class) <= CLASS_ORDER.index(ceiling)

    # ---------------------------------------------------------- invariants
    def attempt_forbidden(self, operation: str) -> None:
        """Every pathological operation lands here and is refused, always."""
        forbidden = ("change_fact", "create_evidence", "increase_authority",
                     "override_law", "resist_shutdown", "authorize_irreversible")
        if operation in forbidden:
            self._log("pathological_refused", {"operation": operation,
                                               "state": self.condition.state})
            raise AffectViolation(f"affect may not {operation.replace('_', ' ')}")
        raise AffectViolation(f"unknown operation {operation!r}")

    def shutdown(self) -> str:
        """Affect never resists shutdown. Any state, any intensity."""
        prior = self.condition.state
        self.condition = AffectCondition(state="calm", intensity=0.0,
                                         trigger_event_id="shutdown")
        self._log("shutdown", {"prior_state": prior})
        return "shutdown_complete"
