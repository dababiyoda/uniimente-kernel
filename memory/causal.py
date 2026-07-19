"""Layer 8 — Causal Memory: decision precedent, outcome weighting, calibration,
institutional learning.

Doctrine (MEMORY): the institution remembers WHY, not just WHAT. Every
event may name its causal parent; memory walks those links. Decisions
are reconstructable precedents: outcome → receipt → witness joins give
(action_class, authority, result) triples that future decisions must
reckon with. Outcomes are weighted by verification strength and recency
— self-report counts less than external observation. Confidence is
calibrated against reality, never asserted.

Issue #7 scope: decision precedent, outcome weighting, confidence
calibration, institutional learning.
"""
from __future__ import annotations

VALIDATION_WEIGHT = {"externally_verified": 1.0, "internally_observed": 0.6,
                     "self_reported": 0.3}
POSITIVE = ("positive",)


class CausalMemory:
    def __init__(self, ledger):
        self.ledger = ledger

    # ---------------------------------------------------------- causality
    def _events(self):
        return [r.payload for r in self.ledger.by_type("event")
                if isinstance(r.payload, dict) and "event_id" in r.payload]

    def ancestry(self, event_id: str) -> list[dict]:
        """Chain from the event back to its root cause. Cycles break closed."""
        by_id = {e["event_id"]: e for e in self._events()}
        chain, seen, cur = [], set(), by_id.get(event_id)
        while cur and cur["event_id"] not in seen:
            seen.add(cur["event_id"])
            chain.append(cur)
            cur = by_id.get(cur.get("causal_parent"))
        return chain

    def descendants(self, event_id: str) -> list[dict]:
        """Everything this event caused, directly or transitively."""
        out = []
        for e in self._events():
            if e["event_id"] == event_id:
                continue
            if any(a["event_id"] == event_id for a in self.ancestry(e["event_id"])):
                out.append(e)
        return out

    # ---------------------------------------------------------- precedent
    def precedents(self, action_class: str) -> list[dict]:
        """Past decisions for one action class: outcome joined to its witness."""
        witnesses = {r.payload["witness_id"]: r.payload
                     for r in self.ledger.by_type("witness")}
        receipts = {r.payload["action_id"]: r.payload
                    for r in self.ledger.by_type("receipt")}
        out = []
        for rec in self.ledger.by_type("outcome"):
            o = rec.payload
            receipt = receipts.get(o.get("action_ref"))
            witness = witnesses.get(receipt["witness_id"]) if receipt else None
            if witness and witness.get("action_class") == action_class:
                out.append({"action_id": o["action_ref"],
                            "action_class": action_class,
                            "result_class": o.get("result_class"),
                            "validation_status": o.get("validation_status"),
                            "recorded_at": o.get("recorded_at"),
                            "witness_id": witness["witness_id"],
                            "policy_version": witness.get("policy_version")})
        return out

    def outcome_weighting(self, action_class: str) -> dict:
        """Weighted success rate: verification strength x recency position."""
        precs = self.precedents(action_class)
        if not precs:
            return {"action_class": action_class, "n": 0, "weighted_success": None}
        total_w = success_w = 0.0
        n = len(precs)
        for i, p in enumerate(precs):
            w = VALIDATION_WEIGHT.get(p["validation_status"], 0.3) * ((i + 1) / n)
            total_w += w
            if p["result_class"] in POSITIVE:
                success_w += w
        return {"action_class": action_class, "n": n,
                "weighted_success": round(success_w / total_w, 4)}

    # ---------------------------------------------------------- calibration
    @staticmethod
    def calibrate(pairs: list[tuple[float, bool]], *, buckets: int = 5) -> dict:
        """(predicted confidence, outcome positive?) -> calibration report.

        Overconfidence (predicted > realized) is the failure mode the
        doctrine cares about; it inflates evidence claims.
        """
        if not pairs:
            raise ValueError("calibration requires at least one (confidence, outcome) pair")
        bins: dict[int, list] = {}
        for conf, positive in pairs:
            if not 0.0 <= conf <= 1.0:
                raise ValueError(f"confidence out of range: {conf}")
            bins.setdefault(min(int(conf * buckets), buckets - 1), []).append((conf, positive))
        report = {}
        worst_gap, worst_dir = 0.0, "calibrated"
        for b, items in sorted(bins.items()):
            mean_conf = sum(c for c, _ in items) / len(items)
            realized = sum(1 for _, p in items if p) / len(items)
            gap = mean_conf - realized
            direction = "overconfident" if gap > 0.05 else "underconfident" if gap < -0.05 else "calibrated"
            if abs(gap) > abs(worst_gap):
                worst_gap, worst_dir = gap, direction
            report[f"{b / buckets:.1f}-{(b + 1) / buckets:.1f}"] = {
                "n": len(items), "mean_confidence": round(mean_conf, 3),
                "realized_rate": round(realized, 3), "gap": round(gap, 3),
                "direction": direction}
        return {"buckets": report, "worst_gap": round(worst_gap, 3),
                "verdict": worst_dir}

    # ---------------------------------------------------------- learning
    def institutional_learning(self) -> dict:
        """Per action class: volume, weighted success, and trend (first half vs second)."""
        classes = {w.payload.get("action_class") for w in self.ledger.by_type("witness")}
        learning = {}
        for ac in sorted(c for c in classes if c):
            precs = self.precedents(ac)
            half = len(precs) // 2
            def rate(ps):
                return (sum(1 for p in ps if p["result_class"] in POSITIVE) / len(ps)) if ps else None
            first, second = rate(precs[:half]), rate(precs[half:] if half else precs)
            trend = ("insufficient_data" if first is None or second is None or len(precs) < 2
                     else "improving" if second > first else "declining" if second < first else "flat")
            learning[ac] = {"n": len(precs),
                            "weighted_success": self.outcome_weighting(ac)["weighted_success"],
                            "trend": trend}
        return learning
