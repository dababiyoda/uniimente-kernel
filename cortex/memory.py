"""Routing memory: learning conditional on verified outcomes (build prompt item 10).

A ``RoutingMemoryRecord`` links problem, geometry, selected method, recommendation,
authorization (where applicable), consequence, observed outcome and attribution.

Rules enforced here:

* Only ``verified_success`` and ``observed_failure`` move competence. Unresolved
  outcomes and absent feedback are recorded and change nothing.
* A prediction, model output or self-assessment cannot settle competence; such
  records are refused.
* Attribution is per role (hypothesis generation, flaw detection, calibration
  improvement, resource consumption, failed assumption) and carries its own
  uncertainty; credit is never assigned blindly to the final solver.
* Competence is scoped to method x geometry x conditions x version, bounded per
  record (weight <= 1, taken from memory.causal.VALIDATION_WEIGHT) and shrunk
  toward the method's pooled record. Defaults change only after
  ``MIN_OUTCOME_EVIDENCE`` weighted outcomes and a gap larger than the margin.
* Every record carries the ledger head it was appended to, so any prefix can be
  restored (rollback) by recomputation. Nothing is overwritten.
* The ledger has no path to permissions, consequence ceilings, evaluators, the
  genome registry or constitutional authority. It can reorder eligible routes;
  it cannot make an ineligible or disabled route eligible.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from memory.causal import VALIDATION_WEIGHT

from .contracts import CortexError, digest

OUTCOME_STATUSES = ("verified_success", "observed_failure", "unresolved", "absent_feedback")
SETTLING = ("verified_success", "observed_failure")
REFUSED_PROVENANCE = ("model_output", "prediction", "self_assessment")
PROVENANCE_KINDS = ("external_observation", "internal_observation", "human_report") + REFUSED_PROVENANCE
ROLES = ("hypothesis_generation", "flaw_detection", "calibration_improvement", "resource_consumption",
         "failed_assumption", "final_answer")
MIN_OUTCOME_EVIDENCE = 5.0
SHRINKAGE = 2.0          # pseudo-observations pulling a cell toward its method pool
DEFAULT_MARGIN = 0.10    # estimated competence gap required before reordering defaults
GENESIS = "sha256:" + "0" * 64


@dataclass(frozen=True)
class RoutingMemoryRecord:
    record_id: str
    receipt_id: str
    problem_id: str
    geometry: str
    conditions: tuple[str, ...]
    method: str
    method_version: str
    recommendation: str
    authorization_ref: str | None
    consequence_class: str
    outcome_status: str
    outcome_provenance: Mapping[str, Any]
    attribution: tuple[Mapping[str, Any], ...]
    policy_version: str
    rollback_ref: str
    competence_update: Mapping[str, Any]

    def to_dict(self) -> dict:
        return {"record_id": self.record_id, "receipt_id": self.receipt_id, "problem_id": self.problem_id,
                "geometry": self.geometry, "conditions": list(self.conditions), "method": self.method,
                "method_version": self.method_version, "recommendation": self.recommendation,
                "authorization_ref": self.authorization_ref, "consequence_class": self.consequence_class,
                "outcome_status": self.outcome_status, "outcome_provenance": dict(self.outcome_provenance),
                "attribution": [dict(a) for a in self.attribution], "policy_version": self.policy_version,
                "rollback_ref": self.rollback_ref, "competence_update": dict(self.competence_update)}


class CompetenceLedger:
    """Append-only routing memory. A projection, never an authority."""

    def __init__(self, records: Iterable[RoutingMemoryRecord] = ()):
        self._records: list[RoutingMemoryRecord] = list(records)

    # ------------------------------------------------------------ state
    @property
    def head(self) -> str:
        return self._records[-1].record_id if self._records else GENESIS

    def records(self) -> list[RoutingMemoryRecord]:
        return list(self._records)

    def _counts(self, records, method=None, geometry=None, conditions=None, version=None):
        success = failure = 0.0
        for r in records:
            if r.outcome_status not in SETTLING:
                continue
            if method is not None and r.method != method:
                continue
            if version is not None and r.method_version != version:
                continue
            if geometry is not None and r.geometry != geometry:
                continue
            if conditions is not None and tuple(r.conditions) != tuple(conditions):
                continue
            w = float(r.competence_update.get("weight", 0.0))
            if r.outcome_status == "verified_success":
                success += w
            else:
                failure += w
        return success, failure

    def estimate(self, method: str, version: str, geometry: str, conditions: tuple[str, ...] = (),
                 *, upto: int | None = None) -> dict:
        records = self._records if upto is None else self._records[:upto]
        ps, pf = self._counts(records, method=method, version=version)
        pool = (ps + 1.0) / (ps + pf + 2.0)                     # Beta(1,1) prior, as greg/routing.py
        cs, cf = self._counts(records, method, geometry, conditions, version)
        n = cs + cf
        cell = (cs + SHRINKAGE * pool) / (n + SHRINKAGE)
        basis = "cell" if n >= MIN_OUTCOME_EVIDENCE else ("method_pool" if ps + pf > 0 else "prior")
        return {"method": method, "version": version, "geometry": geometry, "conditions": list(conditions),
                "estimate": round(cell, 4), "weighted_outcomes": round(n, 4), "basis": basis}

    # ------------------------------------------------------------ learning
    def settle(self, *, receipt: Mapping[str, Any], method: str, method_version: str, outcome_status: str,
               provenance: Mapping[str, Any], attribution: Iterable[Mapping[str, Any]],
               conditions: tuple[str, ...] = (), authorization_ref: str | None = None) -> RoutingMemoryRecord:
        if outcome_status not in OUTCOME_STATUSES:
            raise CortexError(f"unknown outcome status {outcome_status!r}")
        kind = provenance.get("kind")
        if kind not in PROVENANCE_KINDS:
            raise CortexError(f"unknown provenance kind {kind!r}")
        if kind in REFUSED_PROVENANCE and outcome_status in SETTLING:
            raise CortexError(f"{kind} cannot settle competence")
        attribution = tuple(dict(a) for a in attribution)
        for a in attribution:
            if a.get("role") not in ROLES:
                raise CortexError(f"unknown attribution role {a.get('role')!r}")
            u = a.get("uncertainty")
            if u not in ("low", "medium", "high"):
                raise CortexError("attribution requires an uncertainty of low, medium or high")
        if outcome_status in SETTLING and not any(a.get("method") == method for a in attribution):
            raise CortexError("a settling outcome must attribute a role to the method being updated")
        unsigned = dict(receipt)
        if unsigned.pop("receipt_id", None) != digest(unsigned):
            raise CortexError("receipt content address mismatch; refusing to settle")
        geometry = receipt["geometry"]["epistemic_class"] or "unresolved"
        selected = receipt["route"]["selected"]
        key = f"{method}@{method_version}"
        ran = _ran(receipt)
        if key not in selected and key not in ran:
            raise CortexError(f"a receipt can only settle a method and version it actually selected or ran; "
                              f"{key!r} is not among {sorted(set(selected) | set(ran))}")
        if outcome_status in SETTLING and key not in ran:
            raise CortexError(f"a receipt can only settle a method and version that actually ran; {key!r} "
                              f"produced no result ({receipt.get('coverage')})")
        if outcome_status == "verified_success" and key not in _ran(receipt, answered=True):
            # A lead that ran and failed (a timeout superseded by a fallback) may settle its failure, never the
            # success of the engine that answered (review of the 0.2.2 port).
            raise CortexError(f"{key!r} ran but produced no answer in this receipt; only an observed failure "
                              f"can settle it")
        if outcome_status in SETTLING and any(
                r.receipt_id == receipt["receipt_id"] and r.method == method and r.method_version == method_version
                and r.outcome_status in SETTLING for r in self._records):
            raise CortexError("this receipt already settled this method and version; one decision is one "
                              "observation, and a correction must be an explicit supersession")
        # A composed route settles under the geometry of the payload part it served,
        # not under the receipt's first structural class.
        geometry = (receipt["route"].get("part_geometries") or {}).get(key) or geometry
        weight = VALIDATION_WEIGHT.get(provenance.get("validation_status"), 0.0) if outcome_status in SETTLING else 0.0
        weight = min(weight, 1.0)  # bounded update
        before = self.estimate(method, method_version, geometry, conditions)
        body = {"receipt_id": receipt["receipt_id"], "problem_id": receipt["problem"]["problem_id"],
                "geometry": geometry, "conditions": list(conditions), "method": method,
                "method_version": method_version, "recommendation": receipt["disposition"]["kind"],
                "authorization_ref": authorization_ref,
                "consequence_class": receipt["geometry"]["consequence_class"],
                "outcome_status": outcome_status, "outcome_provenance": dict(provenance),
                "attribution": [dict(a) for a in attribution], "policy_version": receipt["versions"]["policy"],
                "rollback_ref": self.head}
        provisional = RoutingMemoryRecord(record_id="pending", competence_update={"weight": weight},
                                          **{k: (tuple(v) if isinstance(v, list) and k in ("conditions",) else v)
                                             for k, v in body.items() if k != "attribution"},
                                          attribution=attribution)
        after = CompetenceLedger(self._records + [provisional]).estimate(method, method_version, geometry, conditions)
        update = {"weight": weight, "before": before["estimate"], "after": after["estimate"],
                  "delta": round(after["estimate"] - before["estimate"], 4), "bounded": True,
                  "changes": "ordering among eligible routes only"}
        record = RoutingMemoryRecord(record_id=digest({**body, "competence_update": update}),
                                     competence_update=update,
                                     **{k: (tuple(v) if k == "conditions" else v)
                                        for k, v in body.items() if k != "attribution"},
                                     attribution=attribution)
        self._records.append(record)
        return record

    def rollback(self, to_ref: str) -> "CompetenceLedger":
        """Return a ledger restored to the state after ``to_ref`` (GENESIS = empty). History is kept."""
        if to_ref == GENESIS:
            return CompetenceLedger()
        for i, r in enumerate(self._records):
            if r.record_id == to_ref:
                return CompetenceLedger(self._records[:i + 1])
        raise CortexError(f"unknown rollback reference {to_ref}")

    # ------------------------------------------------------------ routing use
    def reorder(self, eligible_keys: list[str], geometry, *, conditions: tuple[str, ...] = (),
                margin: float = DEFAULT_MARGIN, part_geometries: Mapping[str, str] | None = None) -> list[str]:
        """Permute *eligible* routes only. Needs sufficient evidence and a margin to move a default.

        In a composition each route is scored under the geometry of the payload part it serves
        (``part_geometries``), the same cell ``settle`` writes it to."""
        scored = []
        for index, key in enumerate(eligible_keys):
            method, _, version = key.partition("@")
            cell = (part_geometries or {}).get(key) or geometry.epistemic_class or "unresolved"
            est = self.estimate(method, version, cell, conditions)
            scored.append((est, index, key))
        if any(e["basis"] != "cell" for e, _, _ in scored):
            return list(eligible_keys)  # insufficient outcome evidence: keep the policy default
        best = max(scored, key=lambda t: t[0]["estimate"])
        default = scored[0]
        if best[2] != default[2] and best[0]["estimate"] - default[0]["estimate"] > margin:
            return [best[2]] + [k for k in eligible_keys if k != best[2]]
        return list(eligible_keys)


def _ran(receipt: Mapping[str, Any], *, answered: bool = False) -> set[str]:
    """Route keys that ran: the final per-route results and every engine attempt the formal slot ran before a
    fallback or as a cross-check (route.attempts). ``answered``: only rows that produced an answer."""
    rows = list((receipt.get("output") or {}).get("per_route") or []) + list(receipt["route"].get("attempts") or [])
    out = set()
    for r in rows:
        if answered and r.get("answer") is None:
            continue
        organ = str(r.get("organ_id"))
        out.add(organ if "@" in organ else f"{organ}@{r.get('organ_version')}")
    return out


def records_from_causal_memory(causal_memory, *, prefix: str = "cortex/") -> list[dict]:
    """Adapter: read Kernel causal-memory precedents whose action class is
    ``cortex/<method>@<version>/<geometry>`` as settlement candidates.

    Only real Kernel outcomes (outcome -> receipt -> witness joins) appear here.
    The caller still settles each through ``CompetenceLedger.settle``.
    """
    out = []
    classes = {w.payload.get("action_class") for w in causal_memory.ledger.by_type("witness")}
    for action_class in sorted(c for c in classes if c and c.startswith(prefix)):
        _, method_version, geometry = action_class.split("/", 2)
        for p in causal_memory.precedents(action_class):
            out.append({"method_version": method_version, "geometry": geometry,
                        "result_class": p["result_class"], "validation_status": p["validation_status"],
                        "action_id": p["action_id"], "witness_id": p["witness_id"],
                        "policy_version": p.get("policy_version")})
    return out
