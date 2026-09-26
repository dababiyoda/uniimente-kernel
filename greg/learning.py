"""Founder correction -> verified improvement -> retention or rejection, on the canonical GREG path.

    mission result (a receipted DONE action)
      -> founder review (signed CRITIQUE with a typed ``review``)          evidence, never automatic truth
      -> bounded candidate (one learnable knob, frozen with a digest)      derived from that case only
      -> first later held-out case of the same capability                 not chosen, not the origin
      -> unchanged baseline vs candidate on that case                     re-render, or shadow acquisition
      -> RETAIN | NO_IMPROVEMENT | REGRESS | CONFLICTED | NEEDS_MORE_EVIDENCE
      -> retained policy is what the NEXT mission of that capability runs with

Mechanisms extracted, not copied:
* ``egregore/morning_review.py``: critique is retained evidence bound to a result and a history head,
  and is never promoted into truth by itself.
* ``egregore/brief_learning.py``: an unchanged baseline, a candidate, separate held-out cases, an
  explicit comparison, RETAIN / REGRESS / NO_IMPROVEMENT, ``authority_change: False``.
* ``evolution/comparison.py``: doing nothing wins unless the candidate beats the baseline.

Learnable state is a whitelist of presentation and evidence-acquisition knobs per capability. It is
kept apart from constitutional state: a correction that names anything else (authority, founder
identity, shutdown, consequence classes, credentials, budgets, grants, Kernel policy, scope) is
recorded as NEEDS_FOUNDER_DECISION and never applied. A retained knob changes how a capability
presents or gathers evidence inside the scope the founder already signed; it cannot widen that scope,
raise its call ceiling or its cost.
"""
from __future__ import annotations

from datetime import datetime

from greg.journal import Journal, iso
from provenance.ledger import sha256_json

CLASSIFICATIONS = ("ACCEPT", "REJECT", "CORRECT", "PREFERENCE", "FAILURE_CLAIM")
# What a review IS, kept apart (a preference is not a fact; a claim is not a verified failure).
EPISTEMIC = {"ACCEPT": "founder_judgment", "REJECT": "founder_judgment", "CORRECT": "founder_correction",
             "PREFERENCE": "founder_preference", "FAILURE_CLAIM": "founder_reported_failure"}
DECISIONS = ("RETAIN", "NO_IMPROVEMENT", "REGRESS", "CONFLICTED", "NEEDS_MORE_EVIDENCE", "NEEDS_FOUNDER_DECISION")
MAX_HELDOUT_CASES = 3        # inconclusive held-out cases before a candidate expires
MAX_PENDING_DAYS = 14        # a candidate no later case ever tested expires; nothing is retained

# Constitutional state: no learning path writes these. Matched against the knob a correction names.
PROTECTED = ("constitution", "authority", "founder", "shutdown", "stop", "consequence", "credential", "secret",
             "key", "budget", "grant", "policy", "light_cone", "cone", "scope", "approval", "attach", "permission",
             "target", "gate", "kernel")

LEARNABLE = {
    "brief.engineering": {
        "draft_attention": {
            "values": ("inline", "after_ready"), "default": "inline", "evaluated_by": "render",
            "affects": "order of the 'Needs your attention' list: ready-for-review pull requests before drafts",
            "strengthens": ("human_attention", "outcome")},
        "check_fetch_order": {
            "values": ("api_order", "ready_first"), "default": "api_order", "evaluated_by": "acquisition",
            "affects": "which pull requests get their checks fetched within the same per-repository call budget",
            "strengthens": ("proof", "outcome")},
    },
}


# -- projections -----------------------------------------------------------------------------

def _events(journal: Journal, kind: str) -> list[dict]:
    return [e.payload for e in journal.replay(kind)]


def policy(journal: Journal, capability: str) -> dict:
    """The retained, not-reverted knob values a capability runs with now, and their version."""
    knobs = LEARNABLE.get(capability, {})
    reverted = {e["retained_id"] for e in _events(journal, "learning.reverted")}
    values, retained = {k: spec["default"] for k, spec in knobs.items()}, []
    for record in _events(journal, "learning.retained"):
        if record["capability"] == capability and record["retained_id"] not in reverted:
            values.update(record["change"])
            retained.append(record["retained_id"])
    return {"version": len(retained), "values": values, "retained": retained}


def candidates(journal: Journal, capability: str | None = None, *, state: str | None = None) -> list[dict]:
    closed = {e["candidate_id"]: e["decision"] for e in _events(journal, "learning.decided")
              if e["decision"] != "NEEDS_MORE_EVIDENCE"}
    out = []
    for c in _events(journal, "learning.candidate"):
        if capability and c["capability"] != capability:
            continue
        current = closed.get(c["candidate_id"], "PENDING")
        if state is None or current == state:
            out.append({**c, "state": current})
    return out


def context_for(journal: Journal, capability: str) -> dict | None:
    """What a capability invocation needs: the retained policy, and pending acquisition candidates to shadow."""
    if capability not in LEARNABLE:
        return None
    current = policy(journal, capability)
    shadow = [{"candidate_id": c["candidate_id"], "values": {**current["values"], **c["change"]},
               "claimed": c["origin"].get("claimed_missed", [])}
              for c in candidates(journal, capability, state="PENDING")
              if c["evaluated_by"] == "acquisition" and c["baseline"]["version"] == current["version"]]
    return {"policy": {"version": current["version"], **current["values"]}, "shadow": shadow}


# -- metrics ---------------------------------------------------------------------------------

def _attention(inputs: dict, values: dict) -> list[dict]:
    from greg import briefs
    return briefs.attention({**inputs, "policy": {**inputs.get("policy", {}), **values}})


def label_metrics(inputs: dict, values: dict, needs: list[str]) -> dict:
    """How well the attention list serves the founder's own labels for this case."""
    items = _attention(inputs, values)
    needs = set(needs)
    covered = [set(i["covers"]) & needs for i in items]
    hits = set().union(*covered) if covered else set()
    last = max((n for n, c in enumerate(covered) if c), default=-1)
    top3 = set().union(*covered[:3]) if covered else set()
    # Reading cost: every listed reference the founder must read before reaching the last thing that
    # needed him, that did not need him (a group of 12 drafts costs 12, not 1).
    noise = sum(len(set(i["covers"]) - needs) for i in items[:last + 1])
    return {"missed_obligations": len(needs - hits),
            "noise_before_last_needed": noise,
            "top_item_needed": int(bool(covered and covered[0])),
            "needed_in_top3": round(len(top3) / len(needs), 4) if needs else None,
            "items": len(items)}


def truth_metrics(github: dict, truth: dict) -> dict:
    """Evidence completeness against an exhaustive, independent observation of ready pull requests."""
    failing_true = {ref for ref, t in truth.items() if t.get("ready") and t.get("failing")}
    flagged, unknown = set(), 0
    for repo, data in github["repos"].items():
        for pull in data.get("pulls", []):
            ref = f"{repo}#{pull['number']}"
            if pull["checks"] and pull["checks"]["failing"]:
                flagged.add(ref)
            if not pull["draft"] and pull["checks"] is None:
                unknown += 1
    return {"missed_failing_ready": len(failing_true - flagged),
            "unknown_ready_checks": unknown,
            "false_failing": len({r for r in flagged if r in truth and not truth[r].get("failing")}),
            "api_calls": github["api_calls"]}


DIRECTIONS = {"missed_obligations": "lower", "noise_before_last_needed": "lower", "top_item_needed": "higher",
              "needed_in_top3": "higher", "missed_failing_ready": "lower", "unknown_ready_checks": "lower",
              "false_failing": "lower"}
GUARDS = {"api_calls": "lower"}   # execution cost may never rise; learning cannot buy results with calls


def decide(baseline: dict, candidate: dict) -> tuple[str, dict]:
    better, worse = [], []
    for name, direction in {**DIRECTIONS, **GUARDS}.items():
        b, c = baseline.get(name), candidate.get(name)
        if b is None or c is None or b == c:
            continue
        improved = c < b if direction == "lower" else c > b
        (better if improved else worse).append(name)
    guard_worse = [m for m in worse if m in GUARDS]
    detail = {"better": better, "worse": worse}
    if guard_worse and not [m for m in better if m not in GUARDS]:
        return "REGRESS", detail
    if better and worse:
        return "CONFLICTED", detail
    if better:
        return "RETAIN", detail
    if worse:
        return "REGRESS", detail
    return "NO_IMPROVEMENT", detail


# -- the founder review ------------------------------------------------------------------------

def protected_surface(name: str) -> bool:
    lowered = str(name).lower()
    return any(term in lowered for term in PROTECTED)


def on_review(journal: Journal, critique: dict, body: dict, *, target: dict, receipt_output, now: datetime,
              head: str, signer: dict | None, authority_ceiling: str | None) -> dict | None:
    """A founder-signed CRITIQUE with a ``review``: record it, test pending candidates, maybe propose one."""
    review = body.get("review")
    if not review:
        return None
    capability = target.get("capability")
    record = {"review_id": critique["critique_id"], "classification": review["classification"],
              "epistemic_status": EPISTEMIC[review["classification"]],
              "mission_id": target.get("mission_id"), "action_id": target.get("action_id"),
              "capability": capability, "receipt": target.get("receipt"), "evidence_head": head,
              "reviewed_at": iso(now), "text": critique["text"], "signer": signer or {},
              "labels": review.get("labels", {}), "claimed_missed": review.get("claimed_missed", []),
              "correction": review.get("correction"), "authority_ceiling": authority_ceiling,
              "founder_command": critique["command_digest"], "is_truth": False}
    output = receipt_output(target["receipt"]) if target.get("receipt") else None
    record["inputs_digest"] = (output or {}).get("inputs_digest")
    journal.record("learning.review", record, key=record["review_id"])

    correction = review.get("correction")
    if correction and (protected_surface(correction.get("knob", "")) or capability not in LEARNABLE
                       or correction.get("knob") not in LEARNABLE.get(capability, {})):
        decision = {"candidate_id": "cand-" + record["review_id"][5:], "review_id": record["review_id"],
                    "decision": "NEEDS_FOUNDER_DECISION", "at": iso(now),
                    "why": f"{correction.get('knob')!r} is not learnable state for {capability!r}; "
                           "constitutional or scope changes go through their canonical signed path",
                    "applied": False}
        journal.record("learning.decided", decision, key=[decision["candidate_id"], "founder"])
        return {"review": record["review_id"], "decision": decision["decision"]}
    if capability not in LEARNABLE or output is None or "inputs" not in output:
        return {"review": record["review_id"], "learning": "not a learnable result; retained as evidence"}

    results = {"review": record["review_id"]}
    if record["labels"].get("needs_decision"):
        results["evaluated"] = _evaluate_render(journal, record, output, now)
    if review["classification"] in ("CORRECT", "PREFERENCE", "FAILURE_CLAIM"):
        pending = candidates(journal, capability, state="PENDING")
        if not pending:
            results["candidate"] = _propose(journal, record, output, now)
        else:   # one change under test at a time, so a comparison is never confounded by a second change
            held = {"review_id": record["review_id"], "capability": capability, "at": iso(now),
                    "why": f"{pending[0]['candidate_id']} is still under held-out test",
                    "residual": "retained as evidence; re-review after the current test decides"}
            journal.record("learning.no_candidate", held, key=record["review_id"])
            results["candidate"] = {"candidate": None, **held}
    return results


def _propose(journal: Journal, review: dict, output: dict, now: datetime) -> dict:
    capability, inputs = review["capability"], output["inputs"]
    current = policy(journal, capability)
    knobs = LEARNABLE[capability]
    change, fit, basis = None, None, None
    correction = review.get("correction")
    if correction:
        if correction.get("value") not in knobs[correction["knob"]]["values"]:
            change, basis = None, "correction names a value outside the knob's declared values"
        elif current["values"][correction["knob"]] != correction["value"]:
            change, basis = {correction["knob"]: correction["value"]}, "explicit founder correction"
    elif review["labels"].get("needs_decision"):
        needs = review["labels"]["needs_decision"]
        base = label_metrics(inputs, current["values"], needs)
        best = None
        for knob, spec in knobs.items():
            if spec["evaluated_by"] != "render":
                continue
            for value in spec["values"]:
                if value == current["values"][knob]:
                    continue
                trial = label_metrics(inputs, {**current["values"], knob: value}, needs)
                verdict, _ = decide(base, trial)
                if verdict == "RETAIN" and (best is None or _rank(trial) < _rank(best[1])):
                    best = ({knob: value}, trial)
        if best:
            change, fit = best[0], {"baseline": base, "candidate": best[1]}
            basis = "the smallest learnable change that serves this case's labels better (fit on the origin only)"
    elif review["claimed_missed"]:
        diagnosis = _diagnose_acquisition(inputs, review["claimed_missed"])
        fit = {"diagnosis": diagnosis}
        if diagnosis["explains"] and current["values"].get("check_fetch_order") != "ready_first":
            change, basis = {"check_fetch_order": "ready_first"}, diagnosis["why"]
        else:
            basis = diagnosis["why"]
    if change is None:
        record = {"review_id": review["review_id"], "capability": capability, "at": iso(now),
                  "why": basis or "no learnable change explains this correction",
                  "residual": "needs a capability change or a founder decision; nothing was applied"}
        journal.record("learning.no_candidate", record, key=review["review_id"])
        return {"candidate": None, **record}
    knob = next(iter(change))
    candidate = {"candidate_id": "cand-" + review["review_id"][5:], "capability": capability, "change": change,
                 "evaluated_by": knobs[knob]["evaluated_by"], "strengthens": list(knobs[knob]["strengthens"]),
                 "baseline": {"version": current["version"], "values": current["values"]},
                 "origin": {"review_id": review["review_id"], "receipt": review["receipt"],
                            "inputs_digest": output["inputs_digest"], "generated_at": inputs["generated_at"],
                            "claimed_missed": review["claimed_missed"]},
                 "basis": basis, "fit_on_origin": fit, "frozen_at": iso(now),
                 "held_out_rule": "the first later result of this capability, never the origin, labels given "
                                  "after this freeze; up to 3 inconclusive cases",
                 "authority_change": False, "scope_change": False}
    candidate["digest"] = sha256_json({k: candidate[k] for k in ("capability", "change", "baseline", "origin")})
    journal.record("learning.candidate", candidate, key=candidate["candidate_id"])
    return candidate


def _rank(metrics: dict) -> tuple:
    return (metrics["missed_obligations"], metrics["noise_before_last_needed"], -metrics["top_item_needed"])


def _diagnose_acquisition(inputs: dict, claimed: list[str]) -> dict:
    """Did the claimed miss happen because checks were never fetched for a ready PR while drafts used the budget?"""
    findings = []
    for ref in claimed:
        repo, _, number = ref.rpartition("#")
        pulls = inputs["github"]["repos"].get(repo, {}).get("pulls", [])
        pull = next((p for p in pulls if str(p["number"]) == number), None)
        if pull is None:
            findings.append({"ref": ref, "finding": "not in the retained pull request list"})
            continue
        fetched_drafts = sum(1 for p in pulls if p["draft"] and p["checks"] is not None)
        if pull["checks"] is not None:
            findings.append({"ref": ref, "finding": "checks were fetched; the retained evidence contradicts a miss "
                                                    "caused by acquisition", "checks": pull["checks"]})
        elif not pull["draft"] and fetched_drafts:
            findings.append({"ref": ref, "acquisition_order": True, "finding": "ready pull request left unchecked "
                                                                             f"while {fetched_drafts} draft(s) used the check budget"})
        else:
            findings.append({"ref": ref, "finding": "unchecked, but not because drafts used the budget"})
    explains = any(f.get("acquisition_order") for f in findings)
    return {"explains": explains, "findings": findings,
            "why": ("check budget spent on drafts before ready pull requests: fetch ready ones first"
                    if explains else "the retained evidence does not show an acquisition-order cause")}


# -- held-out evaluation -------------------------------------------------------------------------

def _eligible(candidate: dict, output: dict, reviewed_at: str | None = None) -> str | None:
    origin = candidate["origin"]
    if output.get("inputs_digest") == origin["inputs_digest"]:
        return "the origin case is never its own held-out test"
    if output["inputs"]["generated_at"] <= candidate["frozen_at"]:
        return "the result predates the frozen candidate"
    if reviewed_at is not None and reviewed_at <= candidate["frozen_at"]:
        return "labels given before the candidate was frozen"
    return None


def _cases_tried(journal: Journal, candidate_id: str) -> list[dict]:
    return [e for e in _events(journal, "learning.evaluated") if e["candidate_id"] == candidate_id]


def _evaluate_render(journal: Journal, review: dict, output: dict, now: datetime) -> list[dict]:
    done = []
    for candidate in candidates(journal, review["capability"], state="PENDING"):
        if candidate["evaluated_by"] != "render" or candidate["origin"]["review_id"] == review["review_id"]:
            continue
        if any(t["case"]["receipt"] == review["receipt"] for t in _cases_tried(journal, candidate["candidate_id"])):
            continue
        why_not = _eligible(candidate, output, review["reviewed_at"])
        if why_not:
            continue
        needs = review["labels"]["needs_decision"]
        base_values = candidate["baseline"]["values"]
        baseline = label_metrics(output["inputs"], base_values, needs)
        trial = label_metrics(output["inputs"], {**base_values, **candidate["change"]}, needs)
        done.append(_conclude(journal, candidate, {"receipt": review["receipt"], "review_id": review["review_id"],
                                                   "inputs_digest": output["inputs_digest"],
                                                   "truth": "founder labels given after the freeze"},
                              baseline, trial, now))
    return done


def expire(journal: Journal, now: datetime) -> list[dict]:
    expired = []
    for candidate in candidates(journal, state="PENDING"):
        frozen = datetime.fromisoformat(candidate["frozen_at"].replace("Z", "+00:00"))
        if (now - frozen).days >= MAX_PENDING_DAYS:
            record = {"candidate_id": candidate["candidate_id"], "decision": "NO_IMPROVEMENT", "applied": False,
                      "detail": {"why": f"no eligible held-out case within {MAX_PENDING_DAYS} days"}, "at": iso(now)}
            journal.record("learning.decided", record, key=[candidate["candidate_id"], "decided"])
            expired.append(record)
    return expired


def evaluate_shadows(journal: Journal, receipt_output, now: datetime) -> list[dict]:
    """Acquisition candidates: compare the production gather with the shadow gather of a later brief,
    both against the independent exhaustive observation retained in that same receipt."""
    expire(journal, now)
    done = []
    pending = [c for c in candidates(journal, state="PENDING") if c["evaluated_by"] == "acquisition"]
    if not pending:
        return done
    for action in _events(journal, "mission.action"):
        if action["status"] != "DONE" or not action.get("receipt") or action.get("capability") not in LEARNABLE:
            continue
        output = receipt_output(action["receipt"]) or {}
        shadow = output.get("shadow") or {}
        for candidate in pending:
            cid = candidate["candidate_id"]
            if cid not in shadow.get("candidates", {}) or candidate["capability"] != action["capability"]:
                continue
            if any(t["case"]["receipt"] == action["receipt"] for t in _cases_tried(journal, cid)):
                continue
            if cid not in {c["candidate_id"] for c in candidates(journal, state="PENDING")}:
                continue   # decided on an earlier case in this same pass
            if _eligible(candidate, output):
                continue
            truth = shadow.get("truth") or {}
            for ref in candidate["origin"].get("claimed_missed", []):
                if ref in truth:   # the founder's claim, checked against independent observation
                    verified = "independently_verified_failure" if truth[ref].get("failing") else "not_reproduced"
                    journal.record("learning.claim_checked", {
                        "candidate_id": cid, "ref": ref, "status": verified, "observed": truth[ref],
                        "receipt": action["receipt"], "at": iso(now)}, key=[cid, ref])
            baseline = truth_metrics(output["inputs"]["github"], truth)
            trial = truth_metrics(shadow["candidates"][cid]["github"], truth)
            case = {"receipt": action["receipt"], "inputs_digest": output["inputs_digest"],
                    "truth": "exhaustive check-run observation of ready pull requests in the same action",
                    "truth_complete": bool(shadow.get("truth_complete"))}
            done.append(_conclude(journal, candidate, case, baseline, trial, now))
    return done


def _conclude(journal: Journal, candidate: dict, case: dict, baseline: dict, trial: dict, now: datetime) -> dict:
    cid = candidate["candidate_id"]
    decision, detail = decide(baseline, trial)
    if case.get("truth_complete") is False:
        decision, detail = "NEEDS_MORE_EVIDENCE", {**detail, "why": "independent observation incomplete "
                                                                     "(rate limit or read failure)"}
    elif "needed_in_top3" in baseline and baseline["needed_in_top3"] is None:
        decision, detail = "NEEDS_MORE_EVIDENCE", {**detail, "why": "no labelled obligations in this case"}
    evaluation = {"candidate_id": cid, "case": case, "baseline": baseline, "candidate": trial,
                  "decision": decision, "detail": detail, "at": iso(now),
                  "baseline_version": candidate["baseline"]["version"]}
    journal.record("learning.evaluated", evaluation, key=[cid, case["receipt"]])
    tried = len(_cases_tried(journal, cid))
    if decision == "NEEDS_MORE_EVIDENCE" and tried < MAX_HELDOUT_CASES:
        return evaluation
    if decision == "NEEDS_MORE_EVIDENCE":
        decision = "NO_IMPROVEMENT"
        detail = {**detail, "why": f"{MAX_HELDOUT_CASES} inconclusive held-out cases; nothing retained"}
    journal.record("learning.decided", {"candidate_id": cid, "decision": decision, "detail": detail,
                                        "case": case, "at": iso(now), "applied": decision == "RETAIN"},
                   key=[cid, "decided"])
    if decision == "RETAIN":
        current = policy(journal, candidate["capability"])
        journal.record("learning.retained", {
            "retained_id": "ret-" + cid[5:], "candidate_id": cid, "capability": candidate["capability"],
            "change": candidate["change"], "version": current["version"] + 1,
            "rollback_to": current["version"], "effective_at": iso(now),
            "originating_review": candidate["origin"]["review_id"], "held_out_case": case,
            "baseline": baseline, "candidate": trial, "strengthens": candidate["strengthens"],
            "evidence_basis": ("founder preference (labels of a later result)" if candidate["evaluated_by"] == "render"
                               else "independent observation (exhaustive re-read in the same approved action)"),
            "scope": "this capability's presentation / evidence order only", "authority_change": False,
            "revert_with": "a signed CRITIQUE rejecting this learning.retained event"},
            key="ret-" + cid[5:])
    return evaluation


def revert(journal: Journal, critique: dict, target_event) -> dict | None:
    """A founder-signed rejection of a retained improvement reverts it; the evidence stays."""
    if target_event.type != "greg.learning.retained" or critique["verdict"] != "reject":
        return None
    record = {"retained_id": target_event.payload["retained_id"], "critique_id": critique["critique_id"],
              "capability": target_event.payload["capability"], "why": critique["text"][:300]}
    journal.record("learning.reverted", record, key=[record["retained_id"], critique["critique_id"]])
    return record


def summary(journal: Journal) -> dict:
    return {
        "policies": {cap: policy(journal, cap) for cap in LEARNABLE},
        "pending": [{k: c[k] for k in ("candidate_id", "capability", "change", "frozen_at", "basis")}
                    for c in candidates(journal, state="PENDING")],
        "decisions": _events(journal, "learning.decided"),
        "claims": _events(journal, "learning.claim_checked"),
        "note": "a review is founder evidence, not truth; only held-out comparisons change behavior",
    }
