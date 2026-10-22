"""Backcast GPS: where GREG stands on the developmental path, from its own evidence.

The path (greg/path.json) runs from the current node to the founder's destination.
Founder corrections reroute it; they do not delete it (INTENT-2026-09-30-DEVELOPMENTAL-
INHERITANCE). Every founder-intended capability horizon stays on it at the node where
it becomes buildable, classified by present feasibility, never claimed as present.

Exactly one node is operationally primary: the first whose exit evidence does not
hold. A ledger predicate reports structural evidence, not external founder/body
verification, and it moves the path only at the founder tier (one rule, N1-N7).
Exit evidence comes from the body's ledger where a predicate exists; a node
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

from greg import asks, metrics
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
    """N1: one VEPMC closure (all nine conditions) whose mission was signed at the founder tier."""
    result = metrics.vepmc(journal)
    rows = result["missions"]
    best = min(rows, key=lambda r: len(r["missing"])) if rows else None
    counted = [r["mission_id"] for r in rows if r["counts"]]
    passed, refused = _at_founder_tier(journal, {m: [m] for m in counted})
    return _tiered({"value": len(passed), "structural_value": len(counted),
                    "closest_closure": ({"mission_id": best["mission_id"], "missing": best["missing"]}
                                        if best else None),
                    "external_confirmation_required": result["external_confirmation_required"]},
                   structural=bool(counted), passed=passed, refused=refused)


def genesis_closure(journal: Journal) -> dict:
    """N2: a VEPMC-counting closure whose mission first resolved a genuinely absent capability."""
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
    passed, refused = _at_founder_tier(journal, {c["mission_id"]: [c["mission_id"]] for c in closures})
    founders = [c for c in closures if c["mission_id"] in passed]
    return _tiered({"value": len(founders), "structural_value": len(closures), "closures": closures,
                    "distinct_capabilities": len({c["capability_id"] for c in founders}),
                    "structural_distinct_capabilities": len({c["capability_id"] for c in closures}),
                    "generality": "unproven until a second closure on an unrelated function"},
                   structural=bool(closures), passed=passed, refused=refused)


# -- the founder tier gate, one rule for N1 through N7 -----------------------------------------
# Every ledger predicate proves a closure's structure, and each returns that as ``structurally_met``.
# A structure built with a test key, a fixture or a --no-passphrase rehearsal is real evidence that the
# machinery works. It is not the founder's closure, and N1's own kill condition forbids counting it.
# ``met``, the only field ``position`` reads, therefore also needs every closure the result rests on to
# be signed by the enrolled founder key at the founder tier (greg/metrics.py founder_tier). Short of that
# the result is a STRUCTURAL_CANDIDATE that names why each closure was refused. (#137 verifier condition
# for N3, N4, N6 and N7; #138's structural-candidate gate for N1 and N2 (673726a) uses the same rule
# instead of a hardcoded ``met=False``, so a genuine founder run can still clear N1.) Neither tier is an
# external verification: the ledger cannot prove whose machine this is or who held the key, and the founder
# tier is the key holder's unverified claim of custody (a direct self-attestation reaches it; review of
# 2026-10-14).
FOUNDER_TIER_RULE = ("the founder's path moves only on a closure signed by the enrolled founder key at the founder "
                     "tier; a test key, a fixture or a --no-passphrase rehearsal is structural evidence only "
                     "through the supported tools")
# The tier is the key holder's claim, not verified custody (greg/metrics.py CUSTODY_CLAIM); a met result
# says so, so no reader takes FOUNDER_TIER for proof that the key is protected or is Alfonso's.


def _at_founder_tier(journal: Journal | None, groups: dict) -> tuple[list, dict]:
    """(names of evidence groups whose every mission is at the founder tier, {mission: why not} for the rest)."""
    tiers = metrics.founder_tier(journal)
    passed, refused = [], {}
    for name, missions in groups.items():
        why = {m: (tiers.get(m) or {}).get("why_not", "not registered on this ledger") for m in missions
               if (tiers.get(m) or {}).get("tier") != metrics.FOUNDER_TIER}
        if missions and not why:
            passed.append(name)
        refused.update(why)
    return passed, refused


def _tiered(result: dict, *, structural: bool, passed: list, refused: dict) -> dict:
    met = bool(structural and passed)
    out = {**result, "met": met, "structurally_met": bool(structural),
           "evidence_level": metrics.FOUNDER_TIER if met else
           (metrics.STRUCTURAL_CANDIDATE if structural else "NONE")}
    if met:
        out["founder_tier_basis"] = metrics.CUSTODY_CLAIM
    if structural and not met:
        out["blocker"] = FOUNDER_TIER_RULE
        out["not_founder_tier"] = refused or {"(none)": "the result names no closure to attest"}
    return out


# A business case need not stop for an approval or survive a deliberate interruption to be real;
# it must be the founder's, on his body, appraised and accepted (N3, PR #68 node 4 definition).
N3_CONDITIONS = ("founder_signed", "interface_detached", "persistent_runtime", "real_capability",
                 "appraised_verified", "founder_accepted", "founder_body")
INTERNAL_CLASSES = ("read_only", "internal_write")
OBSERVED = "the deliverable is observed"        # the only withdrawal reason that counts a person's work done


def business_loop_closed(journal: Journal) -> dict:
    """One customer case closed in commercial order with GREG taking no external action.

    The ledger proves: the founder-signed mission named the buyer, price and acceptance terms
    before anything ran; payment was reconciled to the cent by ``business.reconcile``; every act
    that reached a person outside the body was ``human.*`` work whose ask closed only when its
    evidence was observed (a step the person declined is not observed work); no write of GREG's
    own landed on a file that a person's step is measured by (a statement GREG wrote is not a
    payment); GREG's own actions stayed read-only or internal; the separate appraiser verified
    the closure and Alfonso accepted it. That the buyer is a real customer is attested by that
    acceptance, not provable from the ledger.
    """
    from greg.capabilities import BUILTINS
    specs = {e.payload["mission_id"]: e.payload["spec"] for e in journal.replay("mission.registered")}
    rows = {r["mission_id"]: r for r in metrics.vepmc(journal)["missions"]}
    withdrawn = {e.payload["request_id"]: e.payload.get("why", "") for e in journal.replay("decision.withdrawn")}
    refusals = [e.payload for e in journal.replay("human.refusal_honored")]
    cases, incomplete = [], []
    for mid, spec in specs.items():
        paid = [c["check_id"] for c in spec.get("success_checks", [])
                if c["sensor"].get("capability") == "business.reconcile"]
        if not paid or mid not in rows:
            continue
        missing = [c for c in N3_CONDITIONS if not rows[mid][c]]
        if rows[mid].get("fixture_evidence"):       # simulated evidence never moves the path (FOUNDER_TIER_RULE)
            missing.append("no_fixture_evidence")
        observed = [e.payload for e in journal.replay("mission.observed")
                    if e.payload["mission_id"] == mid and e.payload["check_id"] in paid]
        if not (observed and observed[-1]["passed"]):
            missing.append("payment_reconciled")
        external = sorted({a.payload.get("capability") for a in journal.replay("mission.action")
                           if a.payload["mission_id"] == mid and a.payload.get("status") == "DONE"
                           and (a.payload.get("capability") not in BUILTINS
                                or BUILTINS[a.payload["capability"]][0].consequence_class not in INTERNAL_CLASSES)})
        if external:
            missing.append(f"greg_external_action:{','.join(map(str, external))}")
        missing += [f"greg_wrote_human_evidence:{aid}" for aid in _greg_wrote_human_evidence(journal, mid, spec)]
        human = [e.payload for e in journal.replay("decision.requested")
                 if e.payload["mission_id"] == mid and e.payload["kind"] == "HUMAN_WORK"]
        if not human:
            missing.append("no_person_did_the_outward_work")
        # N6's rule: only an ask withdrawn because its evidence was observed counts as the work done.
        if [h["request_id"] for h in human if not withdrawn.get(h["request_id"], "").startswith(OBSERVED)]:
            missing.append("human_work_not_observed")
        missing += [f"person_declined:{r['action_id']}" for r in refusals if r["mission_id"] == mid]
        (incomplete if missing else cases).append({"mission_id": mid, **({"missing": missing} if missing else {}),
                                                   "human_steps": len(human)})
    passed, refused = _at_founder_tier(journal, {c["mission_id"]: [c["mission_id"]] for c in cases})
    return _tiered({"value": len(passed), "structural_value": len(cases), "cases": cases, "incomplete": incomplete,
                    "reality": "order, reconciliation and GREG's own effects are proven from the ledger; that the "
                               "buyer is a real customer is attested by Alfonso's acceptance, not provable here"},
                   structural=bool(cases), passed=passed, refused=refused)


def _acceptances(journal: Journal, missions) -> list[str]:
    """Critique ids of Alfonso's signed accepting critiques of these missions' closures (or appraisals).

    For an ``external`` node this is the recorded external evidence ``position`` requires: the person or
    the second venture is attested by the founder's signed acceptance, which the ledger cannot produce
    by itself (review of 2026-10-14: the label was otherwise inert)."""
    missions = set(missions)
    if journal is None or not missions:
        return []
    targets = {e.event_id for kind in ("mission.achieved", "mission.appraised") for e in journal.replay(kind)
               if e.payload.get("mission_id") in missions}
    return sorted({e.payload["critique_id"] for e in journal.replay("critique.recorded")
                   if e.payload.get("verdict") == "accept" and e.payload.get("target_event_id") in targets})


def _greg_wrote_human_evidence(journal: Journal, mid: str, spec: dict) -> list[str]:
    """Action ids of GREG's own completed writes that landed on a file a person's step is measured by.

    A check that a ``human.*`` (or ``professional.*``) step advances, and that step's ``declined_if``,
    read evidence only a person may produce. If GREG wrote that file, the check measured GREG, not the
    person: a statement GREG filed is not a payment (review of 2026-10-14). The written path comes from
    the action's own receipt, never from the spec's intent."""
    import os
    from greg import asks
    from greg.capabilities import BUILTINS
    person = [s for s in spec.get("strategies", []) if asks.human_work(s.get("function"))]
    advanced = {c for s in person for c in s.get("advances", [])}
    sensors = [c["sensor"] for c in spec.get("success_checks", []) if c["check_id"] in advanced]
    sensors += [s["declined_if"]["sensor"] for s in person if s.get("declined_if")]
    evidence = {os.path.realpath(p) for p in ((x.get("params") or {}).get("path") for x in sensors)
                if isinstance(p, str)}
    wrote = []
    for event in journal.replay("mission.action"):
        action = event.payload
        manifest = BUILTINS.get(action.get("capability"), (None,))[0]
        if (action["mission_id"] != mid or action.get("status") != "DONE" or not action.get("receipt")
                or manifest is None or manifest.consequence_class == "read_only"):
            continue
        record = journal.ledger.find(action["receipt"])
        output = (record.payload.get("result") or {}).get("output") if record is not None else None
        path = output.get("path") if isinstance(output, dict) else None
        if isinstance(path, str) and os.path.realpath(path) in evidence:
            wrote.append(action["action_id"])
    return sorted(set(wrote))


N4_CONDITIONS = ("founder_signed", "interface_detached", "persistent_runtime", "real_capability",
                 "appraised_verified", "founder_body")


def sop_compounding(journal: Journal) -> dict:
    """A ratified SOP whose own runs on the body cut founder interventions and model cost per outcome.

    The procedure was proposed from at least three verified closures and ratified by Alfonso; at
    least three later missions are exact runs of its workflow, each founder-signed, hosted on the
    designated body, receipted and appraised VERIFIED; none failed appraisal, was rejected or was
    abandoned; and founder interventions per verified outcome fell while GREG's model cost per
    outcome did not rise (and fell, if it was ever above zero). Approval boundaries a run no longer
    meets were moved into the founder's signature on that run, never inherited.
    """
    from greg import sop
    rows = {r["mission_id"]: r for r in metrics.vepmc(journal)["missions"]}
    met, incomplete, evidence = [], [], {}
    for p in sop.trend(journal)["procedures"]:
        runs = [r["mission_id"] for r in p.get("sop_runs", {}).get("missions", [])]
        off_body = sorted({c for mid in runs for c in N4_CONDITIONS if not rows.get(mid, {}).get(c)})
        missing = list(p.get("why_not", [])) + [f"sop_run_not_{c}" for c in off_body]
        # Simulated evidence never moves the path: not in a run, nor in a closure the procedure learned from.
        learned = [r["mission_id"] for r in p["baseline"].get("missions", [])]
        missing += [f"fixture_evidence:{m}" for m in learned + runs if rows.get(m, {}).get("fixture_evidence")]
        summary = {"procedure_id": p["procedure_id"], "state": p["state"],
                   "before": {k: v for k, v in p["baseline"].items() if k != "missions"},
                   **({"after": {k: v for k, v in p["sop_runs"].items() if k != "missions"}}
                      if "sop_runs" in p else {})}
        (incomplete if missing else met).append({**summary, **({"missing": missing} if missing else {})})
        if not missing:                   # the closures that taught it and the runs from it: all carry the tier
            evidence[p["procedure_id"]] = [r["mission_id"] for r in p["baseline"].get("missions", [])] + runs
    passed, refused = _at_founder_tier(journal, evidence)
    return _tiered({"value": len(passed), "structural_value": len(met), "procedures": met, "incomplete": incomplete,
                    **({} if met or incomplete else {"missing": ["no SOP proposed yet: three verified closures of "
                                                                 "one procedure come first"]}),
                    "reality": "interventions, model cost and appraisal are measured from the ledger; whether the "
                               "outcomes mattered in the world is the founder's critique, not provable here"},
                   structural=bool(met), passed=passed, refused=refused)


def human_work_shared(journal: Journal) -> dict:
    """Alfonso, GREG and a named person closed one piece of work together.

    The ledger proves: the founder-signed mission named the person, the relationship and the
    acceptance terms; GREG wrote the handoff before any person was asked anything; each of the
    person's steps (those they may decline) closed because its evidence was observed, never
    by an answer; Alfonso's own review closed the same way; no write of GREG's own landed on a
    file those steps are measured by; GREG's actions stayed read-only or internal; the separate appraiser verified the closure and Alfonso accepted it. A refusal is
    honored when GREG asked that step nothing more afterwards; a declined case is not a
    completed one. That the person is real and the relationship lawful is attested by
    Alfonso's acceptance, not provable here.
    """
    from greg.capabilities import BUILTINS
    seq = {r.payload.get("event_id"): r.seq for r in journal.ledger.by_type("event")}
    specs = {e.payload["mission_id"]: e.payload["spec"] for e in journal.replay("mission.registered")}
    rows = {r["mission_id"]: r for r in metrics.vepmc(journal)["missions"]}
    withdrawn = {e.payload["request_id"]: e.payload["why"] for e in journal.replay("decision.withdrawn")}
    refusals = [e for e in journal.replay("human.refusal_honored")]
    cases, incomplete = [], []
    for mid, spec in specs.items():
        person = [s for s in spec.get("strategies", []) if "declined_if" in s]
        if not person:
            continue
        missing = [c for c in N3_CONDITIONS if not rows.get(mid, {}).get(c)]
        if rows.get(mid, {}).get("fixture_evidence"):  # simulated evidence never moves the path
            missing.append("no_fixture_evidence")
        asked = [e for e in journal.replay("decision.requested")
                 if e.payload["mission_id"] == mid and e.payload["kind"] == "HUMAN_WORK"]
        by_step = {}
        for e in asked:
            by_step.setdefault(e.payload.get("action_id"), []).append(e)
        reviews = [s["action_id"] for s in spec["strategies"] if s.get("function") == "human.founder_review"]
        for step in [s["action_id"] for s in person] + reviews:
            if not any(withdrawn.get(e.payload["request_id"], "").startswith(OBSERVED) for e in by_step.get(step, [])):
                missing.append(f"{'founder_review' if step in reviews else 'person_step'}_not_observed:{step}")
        for refusal in (r for r in refusals if r.payload["mission_id"] == mid):
            missing.append(f"person_declined:{refusal.payload['action_id']}")
            if any(seq.get(e.event_id, 0) > seq.get(refusal.event_id, 0)
                   for e in by_step.get(refusal.payload["action_id"], [])):
                missing.append(f"refusal_not_honored:{refusal.payload['action_id']}")
        writes = [seq.get(a.event_id, 0) for a in journal.replay("mission.action")
                  if a.payload["mission_id"] == mid and a.payload.get("status") == "DONE"]
        if asked and not (writes and min(writes) < min(seq.get(e.event_id, 0) for e in asked)):
            missing.append("handoff_not_before_asks")
        external = sorted({a.payload.get("capability") for a in journal.replay("mission.action")
                           if a.payload["mission_id"] == mid and a.payload.get("status") == "DONE"
                           and (a.payload.get("capability") not in BUILTINS
                                or BUILTINS[a.payload["capability"]][0].consequence_class not in INTERNAL_CLASSES)})
        if external:
            missing.append(f"greg_external_action:{','.join(map(str, external))}")
        missing += [f"greg_wrote_human_evidence:{aid}" for aid in _greg_wrote_human_evidence(journal, mid, spec)]
        (incomplete if missing else cases).append({"mission_id": mid, **({"missing": missing} if missing else {}),
                                                   "person_steps": len(person)})
    passed, refused = _at_founder_tier(journal, {c["mission_id"]: [c["mission_id"]] for c in cases})
    return _tiered({"value": len(passed), "structural_value": len(cases), "cases": cases, "incomplete": incomplete,
                    "external_evidence": _acceptances(journal, passed),
                    "reality": "handoff order, observed evidence, honored refusals and GREG's own effects are proven "
                               "from the ledger; that the person is real and the relationship lawful is attested by "
                               "Alfonso's acceptance, not provable here"},
                   structural=bool(cases), passed=passed, refused=refused)


def venture_compounding(journal: Journal) -> dict:
    """A capability proven in one venture made a second venture faster or cheaper, and the second
    venture's verified revenue funds every obligation and reserve with surplus left to reinvest.

    The transplant is a ratified SOP taught by one venture's verified cases and run, at least
    twice, as closed N3 cases in another venture, with fewer founder interventions, less model
    spend or less time per outcome and no quality failure. The books run that venture's reconciled
    revenue through capital/allocation-policy.yaml against the amounts Alfonso signed; GREG moves
    and allocates no money. Whether a second venture could stand alone is Alfonso's judgment.
    """
    from greg import venture_books
    moved = venture_books.transfers(journal)
    proven = [t for t in moved if t["faster_or_cheaper"]]
    ledgers = venture_books.books(journal)
    funded = [b for b in ledgers if b["venture"] in {t["to_venture"] for t in proven}
              and venture_books.reinvestable(b)]
    missing = []
    if not moved:
        missing.append("no ratified procedure from one venture has run in another")
    elif not proven:
        missing.append("no transplant was faster or cheaper: " + "; ".join(
            f"{t['procedure_id']} {t['from_venture']}->{t['to_venture']}: {', '.join(t.get('why_not', []))}"
            for t in moved))
    if proven and not funded:
        missing.append("the second venture's verified revenue leaves no surplus after signed obligations and "
                       "reserves (or none were signed)")
    # Every closure the result rests on carries the tier: the runs that taught the procedure, the runs in
    # the second venture, and the cases whose revenue funds that venture's books.
    into = {b["venture"] for b in funded}
    evidence = sorted({m for t in proven if t["to_venture"] in into
                       for m in [*t.get("taught", []), *t.get("missions", [])]}
                      | {m for b in funded for m in b.get("cases", [])})
    passed, refused = _at_founder_tier(journal, {"N7": evidence})
    return _tiered({"value": len(funded) if passed else 0, "structural_value": len(funded), "transfers": moved,
                    "external_evidence": _acceptances(journal, {m for b in funded for m in b.get("cases", [])})
                    if passed else [],
                    "books": ledgers, **({"missing": missing} if missing else {}),
                    "reality": "transfer, reconciliation and the waterfall are computed from the ledger; GREG moves no "
                               "money; whether the second venture could stand alone is Alfonso's judgment"},
                   structural=not missing, passed=passed, refused=refused)


EXTERNAL_GATE = ("an external node passes only on recorded external evidence (Alfonso's signed acceptance of the "
                 "closures it rests on); the ledger predicate alone does not cross it")

PREDICATES = {"vepmc_at_least_one": vepmc_at_least_one, "genesis_closure": genesis_closure,
              "business_loop_closed": business_loop_closed, "sop_compounding": sop_compounding,
              "human_work_shared": human_work_shared, "venture_compounding": venture_compounding}


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
            if node["evidence_source"] == "external" and passed and not measured.get("external_evidence"):
                # An external gate is crossed on recorded external evidence, never on the ledger predicate alone.
                passed = False
                measurements[node["id"]]["external_gate"] = EXTERNAL_GATE
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
    # Later nodes this ledger already meets: reported as measured, never as achieved, because the
    # path's order is the dependency order. Without this a founder who closed N6 or N7 while an
    # earlier node had no predicate saw his own verified work nowhere.
    met_ahead = [{"id": n["id"], "title": n["title"]} for n in data["nodes"][ids.index(active["id"]) + 1:]
                 if measurements[n["id"]].get("met")] if active else []
    open_kinds = set()
    if journal is not None:
        # An answer row counts only as the verified fold counts it (MissionBook.answers), as on every founder surface.
        from greg.missions import MissionBook
        book = MissionBook(journal)
        open_kinds = {r.get("kind") for r in asks.open_requests(
            journal.replay("decision.") + journal.replay("mission.achieved") + journal.replay("mission.lifecycle"),
            counted=book.answers, uncounted=book.unverified)}
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
        "met_ahead": met_ahead,
        "horizons": {"total": len(horizons),
                     "at_active_node": [h["id"] for h in horizons if active and h["node"] == active["id"]],
                     "by_feasibility": {f: sorted(h["id"] for h in horizons if h["feasibility"] == f)
                                        for f in FEASIBILITY if any(h["feasibility"] == f for h in horizons)}},
        "destination": data["destination"],
        "rule": "a correction reroutes; it does not delete. Not now is not never.",
    }


def measure(journal: Journal | None, node_id: str, data: dict | None = None) -> dict:
    """One node's own exit measurement, read directly even when an earlier node blocks the path.

    ``position`` stops at the first node whose exit evidence does not hold; N5 has no ledger predicate
    yet, so it can never pass and N6/N7 never show there (review of 2026-10-14). Reading a later node
    here moves nothing: the path still stops where ``position`` says, and this says so."""
    data = data or load()
    nodes = {n["id"]: n for n in data["nodes"]}
    if node_id not in nodes:
        raise PathError(f"unknown node {node_id}; known: {sorted(nodes)}")
    node = nodes[node_id]
    out = {"id": node_id, "title": node["title"], "gate": node["gate"], "evidence_source": node["evidence_source"],
           "exit_evidence": node["exit_evidence"]}
    if node["evidence_source"] == "repository":
        out["measurement"] = {"source": "repository", "attested": node["attested"]}
    elif node.get("predicate") and journal is not None:
        out["measurement"] = {"source": "ledger", **PREDICATES[node["predicate"]](journal)}
    else:
        out["measurement"] = {"source": node["evidence_source"],
                              "not_yet_measurable": "no body ledger here: measure on the body" if node.get("predicate")
                              else "no ledger predicate yet; never counted as passed"}
    where = position(journal, data)
    active = (where["active"] or {}).get("id")
    out["path_stops_at"] = active
    if active and [n["id"] for n in data["nodes"]].index(node_id) > [n["id"] for n in data["nodes"]].index(active):
        out["on_the_path"] = (f"not yet: the path stops at {active} until its exit evidence holds; this measurement "
                              "is reported, not counted")
    return out


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
