"""P4 conditional competence: where a formal engine works, not only whether it worked in a class.

Founder review of #155 (INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT): the class-level ledger
pooled competence per epistemic class and learned nothing the fixed policy did not already do. This
memory keys competence on problem conditions computed from the signed formal model and falls back
hierarchically when a condition is sparse:

    exact conditions -> drop the least informative feature, one at a time -> epistemic class
      -> method (global) -> Beta(1, 1) prior

Each level's estimate is shrunk toward its parent ((s + k * parent) / (n + k)), so a sparse cell
borrows strength instead of overreacting. A default order changes only at the most specific level
where every eligible engine has at least ``MIN_EVIDENCE`` weighted outcomes, and only when the
challenger's estimate beats the default by more than ``MARGIN``.

Records are the content-addressed ``cortex.memory.RoutingMemoryRecord`` rows settled by GREG
(``learned_routing.py``); the conditions tuple carries the features as ``name=value`` strings. This
object only implements ``reorder(keys, geometry)``, the interface the frozen 0.2.1 router already
calls: it can permute eligible engines and nothing else (no eligibility, budget, gate, verifier or
authority path). It is bound to one problem's features before the router runs.
"""
from __future__ import annotations

from typing import Iterable, Mapping

SETTLING = ("verified_success", "observed_failure")
FEATURES = ("kind", "ops", "domain", "budget", "size", "density")   # dropped from the right
MIN_EVIDENCE = 3.0
MARGIN = 0.10
SHRINK = 2.0
POLICY = "greg-conditional-competence/0.1"


def _bucket(value: float, edges: Iterable[float], labels: Iterable[str]) -> str:
    for edge, label in zip(edges, labels):
        if value <= edge:
            return label
    return list(labels)[-1]


def features(payload: Mapping) -> dict:
    """Deterministic conditions of a formal problem (body and worker compute the same)."""
    model = payload.get("formal_model") if isinstance(payload, Mapping) else None
    if not isinstance(model, Mapping):
        return {}
    variables = [v for v in model.get("variables") or [] if isinstance(v, Mapping)]
    constraints = [c for c in model.get("constraints") or [] if isinstance(c, Mapping)]
    query = model.get("query") if isinstance(model.get("query"), Mapping) else {}
    widths = [float(v.get("hi", 0)) - float(v.get("lo", 0)) for v in variables
              if isinstance(v.get("hi"), (int, float)) and isinstance(v.get("lo"), (int, float))]
    relations: dict[str, int] = {}
    for c in constraints:
        expr = c.get("expr")
        op = expr[0] if isinstance(expr, list) and expr and isinstance(expr[0], str) else "other"
        relations[op] = relations.get(op, 0) + 1
    primary = max(sorted(relations), key=lambda k: relations[k]) if relations else "none"
    n = max(len(variables), 1)
    budget = float(((payload.get("resources") or {}).get("max_latency_s", 30.0)))
    return {
        "kind": str(query.get("kind", "feasibility")),
        "ops": primary,
        "domain": "bool" if widths and max(widths) <= 1 else ("small" if widths and max(widths) <= 16 else "wide"),
        "budget": _bucket(budget, (1.0, 3.0, 10.0), ("<=1s", "<=3s", "<=10s", ">10s")),
        "size": _bucket(len(variables), (10, 30, 100, 300, 1000), ("<=10", "<=30", "<=100", "<=300", "<=1000",
                                                                    ">1000")),
        "density": _bucket(len(constraints) / n, (0.5, 2.0), ("<=0.5", "<=2", ">2")),
    }


def conditions(feats: Mapping) -> tuple[str, ...]:
    return tuple(f"{k}={feats[k]}" for k in FEATURES if k in feats)


def _parse(conds: Iterable[str]) -> dict:
    out = {}
    for item in conds:
        key, _, value = str(item).partition("=")
        out[key] = value
    return out


class ConditionalCompetence:
    def __init__(self, records: Iterable, *, min_evidence: float = MIN_EVIDENCE, margin: float = MARGIN,
                 shrink: float = SHRINK):
        self.records = [r for r in records if r.outcome_status in SETTLING]
        self.min_evidence, self.margin, self.shrink = min_evidence, margin, shrink
        self.bound: dict | None = None

    def bind(self, feats: Mapping) -> "ConditionalCompetence":
        other = ConditionalCompetence([], min_evidence=self.min_evidence, margin=self.margin, shrink=self.shrink)
        other.records, other.bound = self.records, dict(feats)
        return other

    def _counts(self, method: str, version: str, geometry: str | None, fixed: Mapping) -> tuple[float, float]:
        s = f = 0.0
        for r in self.records:
            if r.method != method or r.method_version != version:
                continue
            if geometry is not None and r.geometry != geometry:
                continue
            conds = _parse(r.conditions)
            if any(conds.get(k) != v for k, v in fixed.items()):
                continue
            w = float(r.competence_update.get("weight", 0.0))
            if r.outcome_status == "verified_success":
                s += w
            else:
                f += w
        return s, f

    def levels(self, method: str, version: str, geometry: str, feats: Mapping) -> list[dict]:
        """Shrunk estimates from global to exact; each row names its level and evidence."""
        s, f = self._counts(method, version, None, {})
        est = (s + 1.0) / (s + f + 2.0)
        rows = [{"level": "global", "estimate": est, "n": s + f}]
        s, f = self._counts(method, version, geometry, {})
        est = (s + self.shrink * est) / (s + f + self.shrink)
        rows.append({"level": "class", "estimate": est, "n": s + f})
        present = [k for k in FEATURES if k in feats]
        for depth in range(1, len(present) + 1):
            fixed = {k: feats[k] for k in present[:depth]}
            s, f = self._counts(method, version, geometry, fixed)
            est = (s + self.shrink * est) / (s + f + self.shrink)
            rows.append({"level": "+".join(present[:depth]), "estimate": est, "n": s + f})
        return rows

    def explain(self, keys: list[str], geometry_class: str) -> dict:
        feats = self.bound or {}
        table = {k: self.levels(k.partition("@")[0], k.partition("@")[2], geometry_class or "unresolved", feats)
                 for k in keys}
        depth = None
        for i in range(len(next(iter(table.values()), [])) - 1, -1, -1):
            if all(rows[i]["n"] >= self.min_evidence for rows in table.values()):
                depth = i
                break
        return {"policy": POLICY, "features": feats, "decision_level": None if depth is None else
                next(iter(table.values()))[depth]["level"],
                "estimates": {k: (None if depth is None else round(rows[depth]["estimate"], 4)) for k, rows in
                              table.items()}, "depth": depth}

    def reorder(self, keys, geometry, **_):
        keys = list(keys)
        if self.bound is None or len(keys) < 2:
            return keys
        info = self.explain(keys, getattr(geometry, "epistemic_class", None))
        if info["depth"] is None:
            return keys                                   # not enough evidence anywhere: fixed policy
        est = info["estimates"]
        best = max(keys, key=lambda k: (est[k], -keys.index(k)))
        if best != keys[0] and est[best] - est[keys[0]] > self.margin:
            return [best] + [k for k in keys if k != best]
        return keys
