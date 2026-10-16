"""Backcast GPS: where GREG stands on the developmental path, from its own evidence.

The path (greg/path.json) runs from the current node to the founder's destination.
Founder corrections reroute it; they do not delete it (INTENT-2026-09-30-DEVELOPMENTAL-
INHERITANCE). Every founder-intended capability horizon stays on it at the node where
it becomes buildable, classified by present feasibility, never claimed as present.

Exactly one node is operationally primary: the first whose exit evidence does not
hold. Exit evidence comes from the body's ledger where a predicate exists; a node
without a predicate is never counted as passed, however much code exists for it.
Repository-attested nodes (N0) are labeled as such. Nothing here writes history,
grants authority or changes the destination.

Mechanism extracted from PR #68's planning model (node gate, single bottleneck metric,
exit evidence, pivot and kill conditions; a claim without evidence refs is
'unresolved'), wired to GREG's ledger-derived metrics.
"""
from __future__ import annotations

import json
from pathlib import Path
import re

from greg import metrics
from greg.journal import Journal

PATH_FILE = Path(__file__).with_name("path.json")
FEASIBILITY = ("CURRENTLY_BUILDABLE", "BUILDABLE_AFTER_PREREQUISITE", "REQUIRES_RESEARCH",
               "REQUIRES_ECONOMIC_SCALE", "REQUIRES_HARDWARE_MATURITY", "REQUIRES_LEGAL_INSTITUTIONAL_CAPACITY",
               "FRONTIER", "CURRENTLY_SCIENCE_FICTION")
EVIDENCE_STATUS = ("verified_by_execution", "verified_by_inspection", "asserted", "unresolved")
EVIDENCE_SOURCES = ("repository", "ledger", "external")
# Directive 2026-10-07 sections 25-26: every frontier capability keeps its backcast; none disappears.
BUILDABILITY = ("BUILDABLE_NOW", "EXPERIMENTAL_NOW", "FRONTIER_RESEARCH", "SCIENCE_FICTION_DESCENDANT")
BACKCAST_FIELDS = ("destination", "current_precursor", "missing_capabilities", "active_gate", "gate_crossing_evidence",
                   "dependencies", "single_bottleneck_metric", "nearest_falsifiable_experiment", "buildability_status",
                   "risk", "authority_implications", "activation_condition")


class PathError(ValueError):
    pass


def load(path: Path = PATH_FILE) -> dict:
    data = json.loads(Path(path).read_text())
    validate(data)
    return data


def validate(data: dict) -> None:
    nodes = data.get("nodes") or []
    ids = [n["id"] for n in nodes]
    if len(ids) != len(set(ids)) or not ids:
        raise PathError("node ids must be present and unique")
    for node in nodes:
        for field in ("title", "outcome", "gate", "sbm", "exit_evidence", "evidence_source", "evidence_status"):
            if not node.get(field):
                raise PathError(f"{node['id']}: missing {field}")
        if node["evidence_source"] not in EVIDENCE_SOURCES:
            raise PathError(f"{node['id']}: unknown evidence source")
        if node["evidence_status"] not in EVIDENCE_STATUS:
            raise PathError(f"{node['id']}: unknown evidence status")
        if node["evidence_status"] != "unresolved" and not node.get("evidence_refs"):
            raise PathError(f"{node['id']}: evidence without refs must be 'unresolved' (PR #68 invariant)")
        predicate = node.get("predicate")
        if predicate is not None and predicate not in PREDICATES:
            raise PathError(f"{node['id']}: unknown predicate {predicate!r}")
        if node["evidence_source"] == "repository" and not node.get("attested"):
            raise PathError(f"{node['id']}: a repository-attested node must say what is attested")
        for kind in node.get("may_be_pulled_forward_by", []):
            if not isinstance(kind, str) or not kind.isupper():
                raise PathError(f"{node['id']}: pull-forward triggers are decision kinds")
    for horizon in data.get("horizons") or []:
        for field in ("covers", "intended_effect", "node", "feasibility", "current_reality",
                      "nearest_precursor", "activation_evidence", "founder_sources"):
            if not horizon.get(field):
                raise PathError(f"horizon {horizon.get('id')}: missing {field}")
        if horizon["node"] not in ids:
            raise PathError(f"horizon {horizon['id']}: unknown node {horizon['node']}")
        if horizon["feasibility"] not in FEASIBILITY:
            raise PathError(f"horizon {horizon['id']}: unknown feasibility {horizon['feasibility']}")
        if horizon["feasibility"] != "CURRENTLY_BUILDABLE" and not horizon.get("prerequisite") \
                and horizon["feasibility"] not in ("FRONTIER",):
            raise PathError(f"horizon {horizon['id']}: a later capability names its prerequisite")
    horizon_ids = {h["id"] for h in data.get("horizons") or []}
    for item in data.get("frontier_backcasts") or []:
        missing = [f for f in BACKCAST_FIELDS if not item.get(f)]
        if missing:
            raise PathError(f"frontier {item.get('id')}: missing {missing}")
        if item["buildability_status"] not in BUILDABILITY:
            raise PathError(f"frontier {item['id']}: unknown buildability {item['buildability_status']}")
        if item.get("node") not in ids or item.get("horizon") not in horizon_ids:
            raise PathError(f"frontier {item['id']}: unknown node or horizon")


# -- ledger predicates: exit evidence the body itself holds --------------------------------

def vepmc_at_least_one(journal: Journal) -> dict:
    result = metrics.vepmc(journal)
    rows = result["missions"]
    best = min(rows, key=lambda r: len(r["missing"])) if rows else None
    return {"met": result["VEPMC"] >= 1, "value": result["VEPMC"],
            "closest_closure": ({"mission_id": best["mission_id"], "missing": best["missing"]} if best else None),
            "external_confirmation_required": result["external_confirmation_required"]}


def genesis_closure(journal: Journal) -> dict:
    """A VEPMC-counting closure whose mission first resolved a genuinely absent capability."""
    from greg.capabilities import BUILTINS
    seq = {r.payload.get("event_id"): r.seq for r in journal.ledger.by_type("event")}
    counted = {r["mission_id"]: r for r in metrics.vepmc(journal)["missions"] if r["counts"]}
    achieved = {e.payload["mission_id"]: seq[e.event_id] for e in journal.replay("mission.achieved")}
    opened = {e.payload["deficit_id"]: e.payload["mission_id"] for e in journal.replay("deficit.opened")}
    closures = []
    for event in journal.replay("deficit.resolved"):
        data = event.payload
        mid = data.get("mission_id")
        if (data.get("deficit_id") in opened and opened[data["deficit_id"]] == mid
                and data.get("capability_id") not in BUILTINS and mid in counted
                and seq[event.event_id] < achieved.get(mid, -1)):
            closures.append({"mission_id": mid, "capability_id": data["capability_id"]})
    functions = {c["capability_id"] for c in closures}
    return {"met": bool(closures), "value": len(closures), "closures": closures,
            "distinct_capabilities": len(functions),
            "generality": "unproven until a second closure on an unrelated function"}


PREDICATES = {"vepmc_at_least_one": vepmc_at_least_one, "genesis_closure": genesis_closure}


def position(journal: Journal | None, data: dict | None = None) -> dict:
    """The one operationally primary node and what stands between GREG and its exit."""
    data = data or load()
    achieved, active, measurements = [], None, {}
    for node in data["nodes"]:
        if node["evidence_source"] == "repository":
            passed = node["attested"].startswith("ACHIEVED")
            measurements[node["id"]] = {"source": "repository", "attested": node["attested"]}
        elif node.get("predicate") and journal is not None:
            measured = PREDICATES[node["predicate"]](journal)
            measurements[node["id"]] = {"source": "ledger", **measured}
            passed = measured["met"]
        else:
            passed = False
            why = ("no body ledger here: measure on the body" if node.get("predicate")
                   else "no ledger predicate yet; never counted as passed")
            measurements[node["id"]] = {"source": node["evidence_source"], "not_yet_measurable": why}
        if passed and active is None:
            achieved.append(node["id"])
        elif active is None:
            active = node
    ids = [n["id"] for n in data["nodes"]]
    following = data["nodes"][ids.index(active["id"]) + 1] if active and ids.index(active["id"]) + 1 < len(ids) \
        else None
    open_kinds = set()
    if journal is not None:
        answered = {e.payload["request_id"] for e in journal.replay("decision.")
                    if e.type in ("greg.decision.answered", "greg.decision.withdrawn")}
        open_kinds = {e.payload.get("kind") for e in journal.replay("decision.requested")
                      if e.payload["request_id"] not in answered}
    pull_forward = [{"node": n["id"], "title": n["title"], "triggered_by": sorted(open_kinds & set(n["may_be_pulled_forward_by"]))}
                    for n in data["nodes"] if open_kinds & set(n.get("may_be_pulled_forward_by", []))]
    horizons = data.get("horizons", [])
    return {
        "reality_status": "RETAINED_EVIDENCE_PROJECTION",
        "achieved": achieved,
        "active": None if active is None else {
            "id": active["id"], "title": active["title"], "gate": active["gate"], "sbm": active["sbm"],
            "exit_evidence": active["exit_evidence"], "measurement": measurements[active["id"]],
            "smallest_next_build": active.get("smallest_next_build"),
            "pivot_condition": active.get("pivot_condition"), "kill_condition": active.get("kill_condition")},
        "next": None if following is None else {"id": following["id"], "title": following["title"],
                                                  "gate": following["gate"]},
        "pull_forward_seams": pull_forward,
        "horizons": {"total": len(horizons),
                     "at_active_node": [h["id"] for h in horizons if active and h["node"] == active["id"]],
                     "by_feasibility": {f: sorted(h["id"] for h in horizons if h["feasibility"] == f)
                                        for f in FEASIBILITY if any(h["feasibility"] == f for h in horizons)}},
        "destination": data["destination"],
        "rule": "a correction reroutes; it does not delete. Not now is not never.",
    }


# -- developmental inheritance: rules for placing lineages on the path ---------------------

CLASSES = ("ALREADY_ACHIEVED_NODE", "CURRENT_NODE_IMPLEMENTATION", "NEXT_NODE_INPUT", "FUTURE_NODE_CAPABILITY",
           "PORTABLE_MECHANISM", "REQUIRES_ADAPTATION", "TEMPORARILY_DEFERRED",
           "SUPERSEDED_IMPLEMENTATION_ASSUMPTION", "GENUINELY_OBSOLETE", "HISTORICAL_EVIDENCE")
AXES = ("current_hardware", "sequence", "timing", "provider", "interface", "implementation_mechanism", "scale",
        "maturity_level", "budget", "authority", "immediate_priority", "final_intended_effect")
INHERITANCE_QUESTIONS = ("q1_original_capability", "q2_still_in_destination", "q3_assumption_that_became_false",
                         "q4_replace_without_discarding", "q5_portable_parts", "q6_later_node_parts",
                         "q7_extract_into_current_path", "q8_incompatible_with_corrected_destination",
                         "q9_cheapest_distinguishing_test")
OBSOLESCENCE_BASES = ("effect_no_longer_wanted", "replaced_by_stronger_canonical", "violates_current_constraints")
TERMINAL_WORDS = ("OUTDATED", "OBSOLETE", "STALE", "SUPERSEDED", "ARCHIVE", "ARCHIVED", "DEPRECATED", "DEAD")


def validate_placements(record: dict, path: dict | None = None) -> None:
    """Enforce INTENT-2026-09-30-DEVELOPMENTAL-INHERITANCE on a placement record.

    A correction reroutes: every placement names what it was trying to do, whether that
    is still intended, the class and node it has now, and which axis changed. Retiring
    or superseding anything substantial answers the nine-question inheritance test;
    genuine obsolescence needs one of the three founder-given bases with references.
    """
    node_ids = {n["id"] for n in (path or load())["nodes"]}
    seen = set()
    for p in record.get("placements") or []:
        pid = p.get("id")
        if not pid or pid in seen:
            raise PathError(f"placement ids must be present and unique: {pid!r}")
        seen.add(pid)
        cls = p.get("classification")
        if cls not in CLASSES:
            hint = " (never a terminal 'outdated' label: decompose by changed axis)" \
                if str(cls).upper().split("_")[0] in TERMINAL_WORDS else ""
            raise PathError(f"{pid}: unknown classification {cls!r}{hint}")
        for field in ("lineage", "intended_effect", "intended_effect_status", "node"):
            if not p.get(field):
                raise PathError(f"{pid}: missing {field}")
        if p["node"] not in node_ids:
            raise PathError(f"{pid}: unknown node {p['node']}")
        axes = p.get("changed_axes")
        if not isinstance(axes, list) or set(axes) - set(AXES):
            raise PathError(f"{pid}: changed_axes must be a list drawn from {AXES}")
        if "final_intended_effect" in axes and not p.get("founder_source_for_destination_change"):
            raise PathError(f"{pid}: only an explicit founder decision changes the destination; cite it")
        if p["intended_effect_status"] != "active" and not p.get("founder_source_for_destination_change"):
            raise PathError(f"{pid}: an intended effect stops being active only by explicit founder decision")
        if cls in ("SUPERSEDED_IMPLEMENTATION_ASSUMPTION", "GENUINELY_OBSOLETE"):
            if not axes:
                raise PathError(f"{pid}: name the axis that changed before superseding anything")
            answers = p.get("inheritance_test") or {}
            missing = [q for q in INHERITANCE_QUESTIONS if not str(answers.get(q, "")).strip()]
            if missing:
                raise PathError(f"{pid}: temporal inheritance test unanswered: {missing}")
        if cls == "GENUINELY_OBSOLETE":
            basis = p.get("obsolescence_basis") or {}
            if basis.get("kind") not in OBSOLESCENCE_BASES or not basis.get("refs"):
                raise PathError(f"{pid}: genuine obsolescence needs one of {OBSOLESCENCE_BASES} with references")
            if basis["kind"] == "effect_no_longer_wanted" and not p.get("founder_source_for_destination_change"):
                raise PathError(f"{pid}: 'effect no longer wanted' requires the founder's own words")
        archived = p.get("archived")
        if archived is not None:                  # directive section 76: leave the active tree only when justified
            if cls not in ("SUPERSEDED_IMPLEMENTATION_ASSUMPTION", "GENUINELY_OBSOLETE"):
                raise PathError(f"{pid}: only a superseded or genuinely obsolete implementation leaves the active tree")
            if not re.fullmatch(r"[0-9a-f]{7,40}", str(archived.get("last_commit", ""))) or not archived.get("paths"):
                raise PathError(f"{pid}: an archive names the last commit that contained it and every path removed")
            if not p.get("surviving_mechanisms") or not archived.get("behaviours_carried"):
                raise PathError(f"{pid}: an archive names the canonical mechanism and tests that now carry its effect")
        if cls in ("REQUIRES_ADAPTATION", "TEMPORARILY_DEFERRED", "PORTABLE_MECHANISM",
                   "SUPERSEDED_IMPLEMENTATION_ASSUMPTION") and not (p.get("adaptation") or p.get("inheritance_test")):
            raise PathError(f"{pid}: say what adapts, ports or reroutes")
        if cls != "HISTORICAL_EVIDENCE" and not (p.get("activation_evidence") or p.get("inheritance_test")):
            raise PathError(f"{pid}: say what evidence would activate the next step")
