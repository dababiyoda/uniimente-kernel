"""Learned cortex routing in shadow (path node P4): what the competence ledger would have routed.

The cortex router accepts a ``CompetenceLedger`` (``cortex/memory.py``) that may only reorder
*eligible* routes, needs five weighted outcomes per (method, geometry) cell and a 0.10 margin
before it moves a policy default, and can be rolled back to any prefix. GREG's path does not
pass it yet: live routing is the fixed policy. This module is the shadow that must earn a
promotion first.

It is a replayed projection, like settlement: it writes nothing and changes no route. For each
cortex receipt on the canonical ledger, in order, it rebuilds the competence ledger from the
outcomes GREG settled on *earlier* receipts only (no hindsight), asks it to reorder the receipt's
decision points (the formal engine order and a multi-route selection), and records whether the
shadow differs from what ran. Settled outcomes then score the live route; a differing shadow is
scored only when the shadow's first route also has a settled outcome on the same problem.

Exploration is the honest limit. Under the fixed policy CP-SAT always runs first on optimization
and Z3 first on feasibility, so the second engine never earns a cell from ordinary missions and
the ledger can never move the default. The only lawful exploration is a founder-signed mission
that pins an organ (``cognition.cortex.<organ>``), which ``cognition.solve`` already honours. The
report counts how many cells have the evidence a reorder needs, so "no change" is never mistaken
for "learned that the default is best". Promotion into live routing is a founder decision.
"""
from __future__ import annotations

from types import SimpleNamespace

from cortex.memory import DEFAULT_MARGIN, MIN_OUTCOME_EVIDENCE, CompetenceLedger

from .settlement import _valid_receipt, measured_outcomes

PROVENANCE = {"kind": "internal_observation", "validation_status": "internally_observed"}
VERSION = "greg.cognition.shadow/0.1"


def _cortex(record):
    output = (record.payload.get("result") or {}).get("output")
    if isinstance(output, dict) and output.get("proof_type") == "cortex_receipt" and _valid_receipt(output):
        return output["proof_artifact"]          # the complete cortex receipt GREG's envelope carries
    return None


def _ran_first(cortex: dict) -> list[str]:
    """Organ keys whose result the receipt carries, in the order they ran."""
    return [r["organ_id"] for r in cortex["output"].get("per_route", []) if r.get("organ_id")]


def _points(cortex: dict) -> list[dict]:
    route = cortex["route"]
    points = []
    order = (route.get("formal_plan") or {}).get("order") or []
    if len(order) > 1:
        points.append({"point": "formal_engine_order", "live": list(order)})
    if len(route.get("selected") or []) > 1:
        points.append({"point": "route_selection_order", "live": list(route["selected"])})
    return points


def _settle(ledger: CompetenceLedger, cortex: dict, passed: bool) -> None:
    for key in _ran_first(cortex)[:1]:                    # credit the route whose answer was observed
        method, _, version = key.partition("@")
        ledger.settle(receipt=cortex, method=method, method_version=version,
                      outcome_status="verified_success" if passed else "observed_failure",
                      provenance=PROVENANCE,
                      attribution=[{"method": method, "role": "final_answer", "uncertainty": "medium"}])


def shadow(journal, ledger) -> dict:
    """Replay every cortex receipt; return the shadow decisions and their scoring. Writes nothing."""
    index = {r.hash: i for i, r in enumerate(ledger.records)}
    settled = sorted(((index[o["receipt"]], o) for o in measured_outcomes(journal) if o["receipt"] in index),
                     key=lambda t: t[0])
    receipts = [(i, r) for i, r in enumerate(ledger.records) if r.record_type == "receipt"]
    by_hash = {r.hash: _cortex(r) for _, r in receipts}
    outcome_of = {}
    for _, o in settled:
        outcome_of.setdefault(o["receipt"], o["correct"])
    memory, cursor, decisions = CompetenceLedger(), 0, []
    for position, record in receipts:
        cortex = by_hash.get(record.hash)
        while cursor < len(settled) and settled[cursor][0] < position:
            earlier = by_hash.get(ledger.records[settled[cursor][0]].hash)
            if earlier is not None:
                _settle(memory, earlier, settled[cursor][1]["correct"])
            cursor += 1
        if cortex is None:
            continue
        geometry = SimpleNamespace(epistemic_class=cortex["geometry"]["epistemic_class"])
        for point in _points(cortex):
            proposed = memory.reorder(point["live"], geometry)
            estimates = [memory.estimate(*k.partition("@")[::2], geometry.epistemic_class or "unresolved")
                         for k in point["live"]]
            decisions.append({"receipt": record.hash, "receipt_id": cortex["receipt_id"],
                              "problem_id": cortex["problem"]["problem_id"], "geometry": geometry.epistemic_class,
                              **point, "shadow": proposed, "differs": proposed != point["live"],
                              "estimates": estimates, "ready": all(e["basis"] == "cell" for e in estimates),
                              "live_outcome": outcome_of.get(record.hash), "ledger_head": memory.head})
    return {"version": VERSION, "decisions": decisions, "summary": _summary(decisions, memory),
            "promotion": "founder decision; live routing stays the fixed policy",
            "authority_created": False}


def _summary(decisions: list[dict], memory: CompetenceLedger) -> dict:
    scored = [d for d in decisions if d["live_outcome"] is not None]
    cells = {}
    for r in memory.records():
        cell = cells.setdefault((r.method, r.method_version, r.geometry), 0.0)
        cells[(r.method, r.method_version, r.geometry)] = cell + float(r.competence_update.get("weight", 0.0))
    return {"decision_points": len(decisions), "ready": sum(d["ready"] for d in decisions),
            "shadow_differs": sum(d["differs"] for d in decisions),
            "live_scored": len(scored), "live_correct": sum(bool(d["live_outcome"]) for d in scored),
            "cells": [{"method": m, "version": v, "geometry": g, "weighted_outcomes": round(w, 4),
                       "enough_to_reorder": w >= MIN_OUTCOME_EVIDENCE} for (m, v, g), w in sorted(cells.items())],
            "rule": f"a reorder needs every compared cell at {MIN_OUTCOME_EVIDENCE:g} weighted outcomes and a "
                    f"{DEFAULT_MARGIN:g} estimated gap; ordinary missions never explore the second engine, a "
                    f"founder-pinned organ does"}
