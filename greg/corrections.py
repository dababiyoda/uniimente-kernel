"""Founder corrections as bounded, evidence-tested hypotheses in the one routing path.

A founder-signed CRITIQUE may carry a ``correction``. It becomes a typed hypothesis
about which *already-authorized* strategies GREG should prefer or avoid in a class of
future situations, then lives or dies by later evidence:

    CRITIQUE (signed) -> correction.proposed (CANDIDATE)
      -> applied when it changes a later choice in MissionEngine._pursue
      -> correction.trial from retained evidence (re-observed checks, or a signed
         founder accept/reject of the changed behaviour)
      -> RETAINED (and the critique's regression obligation is closed) or REGRESSED

The same ranking path serves empirical learning (``routing.py``: receipts ->
reliability) and founder correction: a correction only adds a leading sort key over
candidates the mission already admits. It never creates a candidate, widens the light
cone, raises a budget or skips the Authority Office, which still judges every action.

Scope is typed, taken from the criticized strategy -- capability, route, target,
the sensor capability of the checks it advances, and declared-input params -- never
free-text similarity. ``binding: true`` makes a founder RULE: it is never regressed
by evidence, but contrary evidence is still surfaced for founder review.
"""
from __future__ import annotations

from fnmatch import fnmatch

from greg.journal import Journal

ADJUSTMENTS = ("avoid", "prefer")
CLOSE_CONDITIONS = ("checks", "founder_accepts")
ACTIVE = ("CANDIDATE", "RETAINED", "RULE")
BASE_FIELDS = ("capability", "route", "target", "check_sensor")


class CorrectionError(ValueError):
    pass


def strategy_facts(strategy: dict, manifest, spec: dict) -> dict:
    """Typed facts a correction scope can match against."""
    advances = set(strategy.get("advances", []))
    sensors = sorted({c["sensor"]["capability"] for c in spec.get("success_checks", []) if c["check_id"] in advances})
    facts = {"capability": manifest.capability_id if manifest else strategy.get("capability"),
             "route": manifest.route if manifest else None, "target": strategy.get("target"),
             "check_sensor": sensors}
    declared = set((manifest.inputs or {}).keys()) if manifest else set()
    for name, value in (strategy.get("params") or {}).items():
        if name in declared and isinstance(value, (str, int, float, bool)):
            facts[f"params.{name}"] = value
    return facts


def matches(scope: dict, facts: dict) -> bool:
    for key, want in scope.items():
        have = facts.get(key)
        if key == "check_sensor":
            if want not in (have or []):
                return False
        elif key == "target":
            if have is None or not fnmatch(have, want):
                return False
        elif have != want:
            return False
    return True


def propose(journal: Journal, registry, critique: dict, target, body: dict) -> dict:
    """Turn a signed critique of a mission action into a CANDIDATE correction."""
    if target.type != "greg.mission.action" or not target.payload.get("capability"):
        raise CorrectionError("a correction must criticize a retained mission action")
    allowed = {"adjustment", "scope", "scope_values", "close_condition", "min_trials", "binding"}
    if not isinstance(body, dict) or set(body) - allowed:
        raise CorrectionError(f"correction takes {sorted(allowed)}")
    adjustment = body.get("adjustment", "avoid")
    if adjustment not in ADJUSTMENTS:
        raise CorrectionError(f"adjustment must be one of {ADJUSTMENTS}")
    mission_id, action_id = target.payload["mission_id"], target.payload["action_id"]
    spec = next((e.payload["spec"] for e in journal.replay("mission.registered")
                 if e.payload["mission_id"] == mission_id), None)
    strategy = next((s for s in (spec or {}).get("strategies", []) if s["action_id"] == action_id), None)
    if strategy is None:
        raise CorrectionError("criticized action has no strategy in its signed mission")
    manifest = registry.manifests.get(target.payload["capability"])
    facts = strategy_facts(strategy, manifest, spec)
    fields = body.get("scope") or ["capability", "check_sensor"]
    scope = {}
    for name in fields:
        if name not in BASE_FIELDS and not (name.startswith("params.") and name in facts):
            raise CorrectionError(f"scope field {name!r} is not a typed fact of the criticized strategy")
        if name == "check_sensor":
            if len(facts["check_sensor"]) != 1:
                raise CorrectionError("check_sensor scope needs exactly one advanced sensor")
            scope[name] = facts["check_sensor"][0]
        else:
            scope[name] = facts[name]
    if adjustment == "prefer":
        values = body.get("scope_values")
        if not isinstance(values, dict) or not values or "capability" not in values:
            raise CorrectionError("prefer needs explicit scope_values naming at least a capability")
        scope = dict(values)
    if "capability" not in scope:
        raise CorrectionError("a correction scope always names a capability (no unscoped bans)")
    evidence_type = critique["evidence_type"]
    close = body.get("close_condition") or ("checks" if evidence_type == "objective_failure" else "founder_accepts")
    if close not in CLOSE_CONDITIONS:
        raise CorrectionError(f"close_condition must be one of {CLOSE_CONDITIONS}")
    min_trials = body.get("min_trials", 1)
    if not isinstance(min_trials, int) or not 1 <= min_trials <= 5:
        raise CorrectionError("min_trials must be an integer 1..5")
    helped = ("the alternative GREG chose because of this correction re-observes its advanced checks passing"
              if close == "checks" else
              "Alfonso signs an accepting critique of the alternative's action or closure")
    hurt = ("the alternative executed and its advanced checks stayed failing"
            if close == "checks" else "Alfonso signs a rejecting critique of the alternative's action or closure")
    record = {"correction_id": "corr-" + critique["critique_id"][5:], "critique_id": critique["critique_id"],
              "regression_id": (critique.get("regression") or {}).get("regression_id"),
              "adjustment": adjustment, "scope": scope, "evidence_type": evidence_type,
              "criticized": {"mission_id": mission_id, "action_id": action_id, "event_id": target.event_id,
                             "receipt": target.payload.get("receipt"), "status": target.payload.get("status")},
              "applies_to": "future choices among already-authorized strategies whose typed facts match scope",
              "change": f"{adjustment} matching strategies ahead of the baseline ranking",
              "close_condition": close, "min_trials": min_trials,
              "retain_if": f"{helped} on {min_trials} eligible later choice(s) with no contrary trial",
              "regress_if": f"{hurt} on {min_trials} eligible later choice(s) with no supporting trial",
              "falsifier": hurt, "binding": bool(body.get("binding", False)),
              "state": "RULE" if body.get("binding") else "CANDIDATE"}
    journal.record("correction.proposed", record, key=record["correction_id"])
    return record


def book(journal: Journal) -> dict[str, dict]:
    """Current correction states, projected from retained history (restart-safe)."""
    out = {}
    for e in journal.replay("correction.proposed"):
        out[e.payload["correction_id"]] = {**e.payload, "trials": [], "contradicted": False}
    for e in journal.replay("correction.trial"):
        c = out.get(e.payload["correction_id"])
        if c:
            c["trials"].append(e.payload)
    for e in journal.replay("correction.state"):
        c = out.get(e.payload["correction_id"])
        if c:
            c["state"] = e.payload["state"]
    for c in out.values():
        results = {t["result"] for t in c["trials"]}
        c["contradicted"] = (c["state"] in ("RETAINED", "RULE") and "did_not_help" in results) or \
                            (c["state"] == "CANDIDATE" and results == {"helped", "did_not_help"})
    return out


def rank(corrections: dict, candidates: list[dict]) -> dict:
    """Correction-aware ordering of already-admitted candidates.

    ``candidates`` are dicts with action_id, facts and baseline_key, in baseline order.
    Returns the new order plus the evidence needed to reconstruct both decisions.
    """
    active = [c for c in corrections.values() if c["state"] in ACTIVE]
    bias, hits, conflicts = {}, {}, []
    for cand in candidates:
        avoid = [c["correction_id"] for c in active if c["adjustment"] == "avoid" and matches(c["scope"], cand["facts"])]
        prefer = [c["correction_id"] for c in active if c["adjustment"] == "prefer" and matches(c["scope"], cand["facts"])]
        if avoid and prefer:
            conflicts.append({"action_id": cand["action_id"], "avoid": avoid, "prefer": prefer,
                              "rule": "contradicting corrections neutralize each other; founder review"})
            bias[cand["action_id"]] = 0
        else:
            bias[cand["action_id"]] = 1 if avoid else (-1 if prefer else 0)
        hits[cand["action_id"]] = avoid + prefer
    if candidates and len({bias[c["action_id"]] for c in candidates}) == 1 and any(bias.values()):
        conflicts.append({"action_id": None, "all": sorted({h for v in hits.values() for h in v}),
                          "rule": "every admissible strategy is equally corrected; baseline order kept; founder review"})
    ordered = sorted(candidates, key=lambda c: (bias[c["action_id"]], c["baseline_key"]))
    baseline, chosen = candidates[0]["action_id"] if candidates else None, ordered[0]["action_id"] if ordered else None
    responsible = sorted(set(hits.get(baseline, [])) | set(hits.get(chosen, []))) if baseline != chosen else []
    return {"ordered": ordered, "baseline_choice": baseline, "correction_choice": chosen,
            "changed_by": responsible, "bias": {k: v for k, v in bias.items() if v}, "conflicts": conflicts}


def evaluate(journal: Journal, now_iso: str) -> list[dict]:
    """Turn retained evidence about applied corrections into trials and state changes."""
    corrections = book(journal)
    order = {e.event_id: i for i, e in enumerate(journal.replay())}  # ledger order, not wall-clock
    actions = [e for e in journal.replay("mission.action")]
    observations = [(order[e.event_id], e.payload) for e in journal.replay("mission.observed")]
    critiques = [e.payload for e in journal.replay("critique.recorded")]
    achieved = {e.payload["mission_id"]: e.event_id for e in journal.replay("mission.achieved")}
    appraised = {}
    for e in journal.replay("mission.appraised"):
        appraised.setdefault(e.payload["mission_id"], []).append(e.event_id)
    specs = {e.payload["mission_id"]: e.payload["spec"] for e in journal.replay("mission.registered")}
    ineffective = {(e.payload["mission_id"], e.payload["action_id"]) for e in journal.replay("routing.outcome")
                   if e.payload["verdict"] == "ineffective"}
    written = []
    judged = {(t["correction_id"], t["applied_event"]) for c in corrections.values() for t in c["trials"]}
    for applied in journal.replay("correction.applied"):
        a = applied.payload
        done = [e for e in actions if e.payload["mission_id"] == a["mission_id"]
                and e.payload["action_id"] == a["chosen"] and e.payload["status"] == "DONE"
                and order[e.event_id] > order[applied.event_id]]
        if not done:
            continue  # inconclusive: the changed behaviour has not executed yet
        act = done[0]
        strategy = next(s for s in specs[a["mission_id"]]["strategies"] if s["action_id"] == a["chosen"])
        for cid in a["changed_by"]:
            c = corrections.get(cid)
            if c is None or (cid, applied.event_id) in judged:
                continue
            result, evidence = None, {"alternative_action_event": act.event_id, "receipt": act.payload.get("receipt")}
            if c["close_condition"] == "checks":
                later = [o for i, o in observations if o["mission_id"] == a["mission_id"]
                         and o["check_id"] in strategy["advances"] and i > order[act.event_id]]
                if (a["mission_id"], a["chosen"]) in ineffective:
                    result = "did_not_help"
                elif later and all(o["passed"] for o in later[:len(strategy["advances"])]):
                    result, evidence["observed"] = "helped", [o["check_id"] for o in later]
            else:
                targets = {act.event_id, achieved.get(a["mission_id"]), *appraised.get(a["mission_id"], [])}
                verdicts = [k for k in critiques if k["target_event_id"] in targets and k["verdict"] in ("accept", "reject")]
                if verdicts:
                    result = "helped" if verdicts[-1]["verdict"] == "accept" else "did_not_help"
                    evidence["founder_critique"] = verdicts[-1]["critique_id"]
            if result is None:
                continue  # insufficient evidence: stay unresolved
            trial = {"correction_id": cid, "applied_event": applied.event_id, "mission_id": a["mission_id"],
                     "baseline_choice": a["baseline_choice"], "chosen": a["chosen"], "result": result,
                     "close_condition": c["close_condition"], "evidence": evidence, "at": now_iso}
            journal.record("correction.trial", trial, key=[cid, applied.event_id])
            written.append(trial)
    corrections = book(journal)
    for cid, c in corrections.items():
        if c["state"] != "CANDIDATE":
            continue
        helped = [t for t in c["trials"] if t["result"] == "helped"]
        hurt = [t for t in c["trials"] if t["result"] == "did_not_help"]
        state = None
        if len(helped) >= c["min_trials"] and not hurt:
            state = "RETAINED"
        elif len(hurt) >= c["min_trials"] and not helped:
            state = "REGRESSED"
        if state is None:
            continue
        basis = helped if state == "RETAINED" else hurt
        journal.record("correction.state", {"correction_id": cid, "state": state, "from": "CANDIDATE",
                                            "trials": [t["applied_event"] for t in basis], "at": now_iso},
                       key=[cid, state])
        written.append({"correction_id": cid, "state": state})
        if state == "RETAINED" and c.get("regression_id"):
            last = basis[-1]
            journal.record("critique.regression_closed", {
                "regression_id": c["regression_id"], "correction_id": cid, "critique_id": c["critique_id"],
                "evidence_inspected": [t["evidence"] for t in basis],
                "check": c["retain_if"], "result": "satisfied",
                "prior_behavior": c["criticized"], "changed_behavior": {"mission_id": last["mission_id"],
                                                                        "baseline_choice": last["baseline_choice"],
                                                                        "chosen": last["chosen"]},
                "reason": f"{len(basis)} held-out trial(s) met the declared close condition "
                          f"({c['close_condition']}) with no contrary trial",
                "disposition": "RETAINED", "at": now_iso}, key=[c["regression_id"], "closed"])
    return written


def review(journal: Journal) -> dict:
    """What the founder should see: every correction, and every contradiction."""
    corrections = book(journal)
    rows, attention = [], []
    for cid, c in sorted(corrections.items()):
        tally = {"helped": sum(t["result"] == "helped" for t in c["trials"]),
                 "did_not_help": sum(t["result"] == "did_not_help" for t in c["trials"])}
        rows.append({"correction_id": cid, "state": c["state"], "adjustment": c["adjustment"], "scope": c["scope"],
                     "close_condition": c["close_condition"], "trials": tally, "contradicted": c["contradicted"]})
        if c["contradicted"] or c["state"] == "REGRESSED":
            attention.append({"correction_id": cid, "state": c["state"], "trials": tally,
                              "message": "Founder correction says to " + c["adjustment"] + f" {c['scope']}, but "
                                         "subsequent evidence indicates it may be harmful or overbroad. "
                                         "Founder review recommended."})
    conflicts = [e.payload for e in journal.replay("correction.conflict")]
    return {"corrections": rows, "founder_review": attention, "conflicts": conflicts}
