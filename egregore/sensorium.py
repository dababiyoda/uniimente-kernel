"""Computational modalities (directive section 8): what GREG can perceive of its own institution.

The "alien sensorium" compiles to measurable signals, not mystical language. This module
declares the modalities GREG perceives today and the ones it does not:

* **derived** modalities are deterministic computations over the one Evidence Ledger (open
  capability deficits, evidence conflicts, open obligations, opportunity density, ledger
  integrity, consequence refusal rate, relationship changes, goals behind their authorized
  trajectory). Each reading becomes an ordinary ``SignalEnvelope`` with typed observations
  (subject ``institution``), the ledger head hash it was computed at as its evidence reference,
  and the epistemic method ``deterministic_computation`` from the Competency Compiler's table.
  A reading is emitted only when its value changed: an unchanged gauge is telemetry, not
  experience.
* **external** modalities (liquidity stress, supply-chain stress, market friction, network
  integrity, scientific novelty, institutional trust) are declared *unobserved* with the sensor
  each needs. Nothing pretends to perceive them.

Goals subscribe to derived modalities with ordinary wake conditions (``metric`` on
``institution.<modality>``), so interoception feeds the same relevance router, world model and
GPS as every external sense. The sensorium reads; it never writes anything but experience.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable

from .contracts import SignalEnvelope, require_text
from .goals import iso, parse_time

SUBJECT = "institution"
SOURCE = "derived://egregore/sensorium"
WINDOW = timedelta(days=30)


@dataclass(frozen=True)
class Modality:
    name: str
    kind: str                 # "derived" | "external"
    unit: str
    description: str
    requires: str = ""        # for external modalities: the sensor that would make it observable

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "kind": self.kind, "unit": self.unit, "description": self.description,
                "requires": self.requires, "observed": self.kind == "derived"}


EXTERNAL = (
    Modality("liquidity_stress", "external", "ratio", "cash coverage of obligations", "a treasury/bank balance adapter"),
    Modality("supply_chain_stress", "external", "index", "lead-time and stock-out pressure", "a logistics or supplier feed adapter"),
    Modality("market_friction", "external", "index", "buyer pain and switching cost in target markets", "a WMI market-monitor or venture-assessment observation adapter"),
    Modality("network_integrity", "external", "ratio", "health of hosts, keys and connections", "host and network telemetry adapters"),
    Modality("scientific_novelty", "external", "count", "material new results in watched fields", "paper/preprint feed adapters"),
    Modality("institutional_trust", "external", "index", "how counterparties and audiences rate the institution", "DALEOBANKS audience and relationship-memory adapters"),
)


class Sensorium:
    """Derived interoceptive modalities over the ledger; emits SignalEnvelopes on change only."""

    def __init__(self, loop: Any):
        self.loop = loop
        self.derived: dict[str, tuple[Modality, Callable[[datetime], float]]] = {}
        for modality, fn in (
            (Modality("open_capability_deficits", "derived", "count", "capability deficits recorded and not resolved"), self._open_deficits),
            (Modality("evidence_conflicts", "derived", "count", "beliefs whose sources currently disagree"), self._conflicts),
            (Modality("open_obligations", "derived", "count", "unknown outcomes, open founder decisions and overdue plan nodes"), self._obligations),
            (Modality("opportunity_density", "derived", "ratio", "favorable intersections in the last 30 days per goal with opportunity factors"), self._opportunity_density),
            (Modality("ledger_integrity", "derived", "boolean-as-number", "1 when the evidence hash chain verifies, else 0"), self._integrity),
            (Modality("consequence_refusal_rate", "derived", "ratio", "share of Gate actions in the last 30 days that ended refused, denied, expired, revoked or failed"), self._refusal_rate),
            (Modality("relationship_changes", "derived", "count", "relationship beliefs integrated in the last 30 days"), self._relationship_changes),
            (Modality("goals_behind_target", "derived", "count", "goals with a plan node past its authorized target date"), self._behind),
        ):
            self.derived[modality.name] = (modality, fn)

    @property
    def execution_authority(self) -> str:
        return "none"

    def modalities(self) -> list[dict[str, Any]]:
        return [m.to_dict() for m, _ in self.derived.values()] + [m.to_dict() for m in EXTERNAL]

    # ------------------------------------------------------------ readings
    def readings(self, now: datetime | str) -> dict[str, float]:
        at = parse_time(now)
        return {name: float(fn(at)) for name, (_, fn) in self.derived.items()}

    def _last_emitted(self) -> dict[str, Any]:
        last: dict[str, Any] = {}
        for event in self.loop.world.experiences():
            if event.source != SOURCE:
                continue
            for o in event.observations:
                if o["subject"] == SUBJECT:
                    last[o["attribute"]] = o["value"]
        return last

    def signals(self, now: datetime | str) -> list[SignalEnvelope]:
        """One SignalEnvelope carrying every modality whose value changed since it was last integrated."""
        at = iso(parse_time(now))
        last = self._last_emitted()
        changed = [(name, value) for name, value in sorted(self.readings(at).items()) if last.get(name) != value]
        if not changed:
            return []
        head = require_text("ledger head", self.loop.ledger.head)
        return [SignalEnvelope.build(
            source=SOURCE, source_event_id=f"sensorium@{at}@{head[7:23]}", observed_at=at,
            payload={"observations": [{"subject": SUBJECT, "attribute": name, "value": value, "confidence": 1.0,
                                       "method": "deterministic_computation"} for name, value in changed],
                     "domain": "institution", "tags": ["interoception"]},
            evidence_refs=(head,), trust_level="attributed")]

    # ------------------------------------------------------------ derived modalities
    def _open_deficits(self, at: datetime) -> int:
        open_ids, resolved = set(), set()
        for r in self.loop.ledger.by_type(self.loop.classifier.DEFICIT_RECORD):
            d = r.payload.get("deficit")
            if not d:
                continue
            (resolved if d["disposition"] == "resolved_resume_original_goal" else open_ids).add(d["deficit_id"])
        return len(open_ids - resolved)

    def _conflicts(self, at: datetime) -> int:
        return sum(1 for b in self.loop.world.beliefs().values() if b.contradicted)

    def _obligations(self, at: datetime) -> int:
        unknown = sum(1 for g in self.loop.registry.goals() for i in self.loop._latest_by_route(g).values()
                      if i["evidence_state"] in ("attempted", "unknown"))
        decisions = sum(1 for a in self.loop.attention.open_asks() if a.get("kind") == "decision")
        overdue = sum(len(self.loop.advancement.behind_target(g, now=at)) for g in self.loop.registry.goals()
                      if self.loop.registry.state(g).status not in ("completed", "revoked", "superseded"))
        return unknown + decisions + overdue

    def _opportunity_density(self, at: datetime) -> float:
        with_factors = [g for g in self.loop.registry.goals() if self.loop.registry.get(g).opportunity_factors]
        if not with_factors:
            return 0.0
        recent = [r for r in self.loop.ledger.by_type(self.loop.detector.INTERSECTION_RECORD)
                  if at - parse_time(r.payload["report"]["detected_at"]) <= WINDOW]
        return round(len(recent) / len(with_factors), 6)

    def _integrity(self, at: datetime) -> int:
        ok, _ = self.loop.ledger.verify_chain()
        return 1 if ok else 0

    def _refusal_rate(self, at: datetime) -> float:
        terminal = {"recorded": 0, "bad": 0}
        for r in self.loop.ledger.by_type("event"):
            kind = str(r.payload.get("type", ""))
            if kind == "action.recorded":
                terminal["recorded"] += 1
            elif kind in ("action.refused", "action.denied", "action.expired", "action.revoked", "action.failed"):
                terminal["bad"] += 1
        total = terminal["recorded"] + terminal["bad"]
        return round(terminal["bad"] / total, 6) if total else 0.0

    def _relationship_changes(self, at: datetime) -> int:
        return sum(1 for e in self.loop.world.experiences() for c in e.changes
                   if c["key"].endswith(".relationship") and c["updated"] and at - parse_time(e.integrated_at) <= WINDOW)

    def _behind(self, at: datetime) -> int:
        return sum(1 for g in self.loop.registry.goals()
                   if self.loop.registry.state(g).status not in ("completed", "revoked", "superseded")
                   and self.loop.advancement.behind_target(g, now=at))
