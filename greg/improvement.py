"""Verified learning: GREG keeps a change it learned only if it beats the unchanged behavior later.

One substrate, one lifecycle, two kinds of lever:

    experience (a delivered brief)
      -> evidence about it, typed: a founder PREFERENCE label ("flag this / not this") is what Alfonso
         wants; a founder FAILURE CLAIM ("this PR was failing and you missed it") is a claim to
         investigate, never automatic truth
      -> bounded candidate: the smallest change in ONE lever's closed space, recorded with the cases
         it was derived from
      -> SHADOW: production keeps running the current policy
      -> held-out evidence from LATER briefs only (never a derivation brief, one case per brief)
           preference lever  ("brief.attention"):   later founder labels; the brief's receipted inputs
                                                     are re-rendered under both policies (exact replay)
           evidence lever    ("brief.acquisition"):  an independent exhaustive observation made in the
                                                     same approved read; the candidate may never use
                                                     more calls than the current policy (no buying
                                                     results with calls), and the founder's claim must
                                                     be independently reproduced
      -> RETAIN on strictly fewer errors over >= HELD_OUT_MIN cases; REJECT on a tie or a loss;
         EXPIRE (no improvement, insufficient evidence) after MAX_PENDING_DAYS
      -> a retained policy is what the next brief runs with; it keeps being compared with the policy
         it replaced and is REVERTED if it later loses (or when Alfonso signs a rejection of it)
      -> a regression opened by the originating critique closes only when its close condition is
         proven by the retained evidence; a later reversion reopens it

Everything above is derived from the ledger: learning lives in durable institutional state, not in
process memory, so a fresh Body replays exactly the same policies.

Bounds (machine-checked, not only described). A lever's state is a closed schema defined next to
the capability that consumes it. ``validate_policy`` refuses any other key, any value outside the
declared set, and any name that touches constitutional state (PROTECTED); ``active_policy`` re-validates
what it reads, so even a forged ledger record cannot put a protected key into executable state.
No learned policy can change authority, founder identity, shutdown, credentials, budgets, scope,
targets, consequence classes, permissions, grants or Kernel policy, and none overrides a signed
mission parameter. Automatic retention is limited to these whitelisted, non-consequential levers.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from itertools import product

from greg import briefs
from greg.journal import Journal, iso
from provenance.ledger import sha256_json

HELD_OUT_MIN = 3
MAX_PENDING_DAYS = 14
MAX_LABELS = 50
CAPABILITY = "brief.engineering"

LEVERS = {
    "brief.attention": {"kind": "preference", "space": briefs.ATTENTION_SPACE,
                        "baseline": briefs.ATTENTION_BASELINE,
                        "judged_by": "later founder-signed labels on briefs the candidate was not derived from"},
    "brief.acquisition": {"kind": "evidence", "space": briefs.ACQUISITION_SPACE,
                          "baseline": briefs.ACQUISITION_BASELINE,
                          "judged_by": "independent exhaustive observation in later briefs, no extra calls"},
}
# Constitutional state. No lever may name it; a policy that does is refused before it can exist.
PROTECTED = ("constitution", "authority", "founder", "identity", "shutdown", "stop", "consequence",
             "credential", "secret", "key", "token", "budget", "spend", "grant", "policy_version", "kernel",
             "light_cone", "cone", "scope", "target", "approval", "attach", "permission", "gate", "capability")
EPISTEMIC = {"attention": "founder_preference", "failure_claim": "founder_reported_failure"}


class ImprovementError(ValueError):
    pass


# -- validation ---------------------------------------------------------------------------------

def _refs(values, field: str, limit: int = MAX_LABELS) -> list[str]:
    if not isinstance(values, list) or len(values) > limit or not all(
            isinstance(v, str) and 0 < len(v) <= 200 for v in values):
        raise ImprovementError(f"{field} must be a list of at most {limit} keys")
    return sorted(set(values))


def validate_labels(labels) -> dict:
    """A founder preference label on one delivered brief: {"missed": [keys], "noise": [keys]}."""
    if not isinstance(labels, dict) or set(labels) - {"missed", "noise"}:
        raise ImprovementError("attention labels are {missed: [keys], noise: [keys]}")
    out = {f: _refs(labels.get(f, []), f"attention.{f}") for f in ("missed", "noise")}
    if set(out["missed"]) & set(out["noise"]):
        raise ImprovementError("a key cannot be both missed and noise")
    return out


def validate_claim(claim) -> dict:
    """A founder failure claim: {"missed_failing": ["owner/repo#N", ...]}. Evidence, never truth."""
    if not isinstance(claim, dict) or set(claim) != {"missed_failing"}:
        raise ImprovementError("failure_claim is {missed_failing: [owner/repo#N]}")
    refs = _refs(claim["missed_failing"], "failure_claim.missed_failing", 20)
    if not refs or not all("#" in r and "/" in r for r in refs):
        raise ImprovementError("failure_claim.missed_failing names owner/repo#N pull requests")
    return {"missed_failing": refs}


def protected(name: str) -> bool:
    lowered = str(name).lower()
    return any(term in lowered for term in PROTECTED)


def validate_policy(policy, lever: str = "brief.attention") -> dict:
    if lever not in LEVERS or protected(lever):
        raise ImprovementError(f"{lever!r} is not a learnable lever")
    space = LEVERS[lever]["space"]
    if not isinstance(policy, dict):
        raise ImprovementError("a policy is a mapping")
    for key in policy:
        if protected(key):
            raise ImprovementError(f"{key!r} is constitutional state; learning can never change it")
    if set(policy) != set(space):
        raise ImprovementError(f"policy must set exactly the {lever} lever's fields")
    for field, value in policy.items():
        if value not in space[field]:
            raise ImprovementError(f"{field}={value!r} is outside the lever's space")
    return dict(policy)


def policy_id(policy: dict, lever: str = "brief.attention") -> str:
    return "pol-" + sha256_json({"lever": lever, "policy": validate_policy(policy, lever)})[7:19]


# -- durable state, all derived from the ledger -------------------------------------------------------

def _payloads(journal: Journal, kind: str) -> list[dict]:
    return [e.payload for e in journal.replay(kind)]


def _order(journal: Journal) -> dict:
    return {e.event_id: i for i, e in enumerate(journal.replay())}


def _decided(journal: Journal) -> dict[str, dict]:
    out = {}
    for kind in ("retained", "rejected", "reverted", "expired"):
        for data in _payloads(journal, "improvement." + kind):
            out.setdefault(data["candidate_id"], {})[kind] = data
    return out


def active_policy(journal: Journal, lever: str = "brief.attention") -> dict:
    """What briefs run with now: the last retained, not reverted, still-valid policy of this lever."""
    decided = _decided(journal)
    policy = dict(LEVERS[lever]["baseline"])
    for data in _payloads(journal, "improvement.retained"):
        if data.get("lever", "brief.attention") != lever or "reverted" in decided.get(data["candidate_id"], {}):
            continue
        try:
            policy = validate_policy(data["policy"], lever)   # a forged or corrupt record is never executed
        except ImprovementError:
            continue
    return policy


def _proposals(journal: Journal, lever: str | None = None) -> list[dict]:
    order = _order(journal)
    out = []
    for event in journal.replay("improvement.proposed"):
        data = event.payload
        if lever is None or data.get("lever", "brief.attention") == lever:
            out.append({**data, "lever": data.get("lever", "brief.attention"), "_seq": order[event.event_id]})
    return out


def _open(journal: Journal, lever: str) -> list[dict]:
    decided = _decided(journal)
    return [p for p in _proposals(journal, lever) if p["candidate_id"] not in decided]


def _monitored(journal: Journal, lever: str) -> dict | None:
    """The retained candidate whose policy is active now (compared against what it replaced)."""
    decided = _decided(journal)
    active = active_policy(journal, lever)
    for p in reversed(_proposals(journal, lever)):
        state = decided.get(p["candidate_id"], {})
        if "retained" in state and "reverted" not in state and p["policy"] == active:
            return {**p, "retained": state["retained"]}
    return None


def learned(journal: Journal) -> dict:
    """What the mission engine hands a capability: non-baseline active policies and shadows to evaluate."""
    out = {}
    for lever, spec in LEVERS.items():
        policy = active_policy(journal, lever)
        if policy != spec["baseline"]:
            out[lever] = policy
    shadows = [{"id": p["candidate_id"], "values": p["policy"]} for p in _open(journal, "brief.acquisition")]
    monitored = _monitored(journal, "brief.acquisition")
    if monitored:
        shadows.append({"id": "replaced:" + monitored["candidate_id"], "values": monitored["replaces"]})
    if shadows:
        out["shadow"] = shadows
    return out


# -- cases ----------------------------------------------------------------------------------------

def _receipt_output(ledger, receipt_hash):
    record = ledger.find(receipt_hash) if receipt_hash else None
    output = (record.payload.get("result") or {}).get("output") if record is not None else None
    if not isinstance(output, dict) or "inputs" not in output or \
            briefs.inputs_digest(output["inputs"]) != output.get("inputs_digest"):
        return None                     # not a brief, or its retained inputs do not match their digest
    return output


def _briefs(journal: Journal, ledger) -> list[dict]:
    order = _order(journal)
    out = []
    for event in journal.replay("mission.action"):
        data = event.payload
        if data.get("status") == "DONE" and data.get("capability") == CAPABILITY:
            output = _receipt_output(ledger, data.get("receipt"))
            if output is not None:
                out.append({"event_id": event.event_id, "seq": order[event.event_id], "output": output})
    return out


def labelled_cases(journal: Journal, ledger, *, every_label: bool = False) -> list[dict]:
    """Founder-labelled briefs, oldest label first. One brief is one case: only its LATEST label counts.

    ``every_label`` returns every label instead (superseded ones included), to map case ids to
    briefs and to keep a corrected label inspectable; it never feeds a decision.
    """
    briefs_by_event = {b["event_id"]: b for b in _briefs(journal, ledger)}
    order = _order(journal)
    latest, every = {}, []
    for event in journal.replay("critique.recorded"):
        data = event.payload
        brief = briefs_by_event.get(data["target_event_id"])
        if data.get("attention") is None or brief is None:
            continue
        inputs = brief["output"]["inputs"]
        labels = data["attention"]
        delivered = briefs.flagged_keys(inputs)
        latest[brief["event_id"]] = {
            "case_id": data["critique_id"], "seq": order[event.event_id], "brief_event_id": brief["event_id"],
            "brief_seq": brief["seq"], "inputs": inputs, "labels": labels,
            "truth": sorted((delivered - set(labels["noise"])) | set(labels["missed"])),
            "delivered_policy": briefs.attention_policy(inputs), "regression": data.get("regression")}
        every.append(latest[brief["event_id"]])
    return every if every_label else sorted(latest.values(), key=lambda c: c["seq"])


def errors(policy: dict, case: dict) -> int:
    """Disagreements with the founder's label: flagged but unwanted, plus wanted but not flagged."""
    return len(briefs.flagged_keys(case["inputs"], policy) ^ set(case["truth"]))


def _held_out(candidate: dict, cases: list[dict]) -> list[dict]:
    """Later briefs only: delivered after the candidate existed, never one it was derived from."""
    derived = set(candidate["derived_from_briefs"])
    return [c for c in cases if c["brief_seq"] > candidate["_seq"] and c["brief_event_id"] not in derived]


# -- evidence-acquisition metrics ----------------------------------------------------------------------

def truth_metrics(github: dict, truth: dict) -> dict:
    """Evidence completeness of one acquisition against the independent observation of ready PRs."""
    failing = {ref for ref, t in truth.items() if t["failing"]}
    fetched_failing, unknown = set(), 0
    for repo, data in github["repos"].items():
        for pull in data.get("pulls", []):
            ref = f"{repo}#{pull['number']}"
            if pull["checks"] and pull["checks"]["failing"]:
                fetched_failing.add(ref)
            if not pull["draft"] and pull["checks"] is None:
                unknown += 1
    return {"missed_failing_ready": len(failing - fetched_failing), "unknown_ready_checks": unknown,
            "api_calls": github["api_calls"]}


def evidence_score(metrics: dict) -> int:
    return metrics["missed_failing_ready"] + metrics["unknown_ready_checks"]


def _acquisition_cases(journal: Journal, ledger, shadow_id: str, after_seq: int, exclude: set) -> list[dict]:
    cases = []
    for brief in _briefs(journal, ledger):
        shadow = brief["output"].get("shadow") or {}
        if brief["seq"] <= after_seq or brief["event_id"] in exclude or shadow_id not in shadow.get("shadows", {}):
            continue
        if not shadow.get("truth_complete"):
            continue                      # an incomplete observation decides nothing
        cases.append({"brief_event_id": brief["event_id"], "seq": brief["seq"],
                      "production": truth_metrics(brief["output"]["inputs"]["github"], shadow["truth"]),
                      "shadow": truth_metrics(shadow["shadows"][shadow_id], shadow["truth"]),
                      "truth": shadow["truth"]})
    return cases


def _diagnose(inputs: dict, claimed: list[str]) -> dict:
    """Does the retained evidence show the claimed miss was an acquisition-order effect?"""
    findings = []
    for ref in claimed:
        repo, _, number = ref.rpartition("#")
        pulls = inputs["github"]["repos"].get(repo, {}).get("pulls", [])
        pull = next((p for p in pulls if str(p["number"]) == number), None)
        fetched_drafts = sum(1 for p in pulls if p["draft"] and p["checks"] is not None)
        if pull is None:
            findings.append({"ref": ref, "finding": "not in the retained pull request list"})
        elif pull["checks"] is not None:
            findings.append({"ref": ref, "finding": "its checks were fetched; the evidence contradicts an "
                                                    "acquisition cause", "checks": pull["checks"]})
        elif not pull["draft"] and fetched_drafts:
            findings.append({"ref": ref, "acquisition_order": True,
                             "finding": f"ready pull request left unchecked while {fetched_drafts} draft(s) used "
                                        "the check budget"})
        else:
            findings.append({"ref": ref, "finding": "unchecked, but not because drafts used the budget"})
    explains = any(f.get("acquisition_order") for f in findings)
    return {"explains": explains, "findings": findings,
            "why": ("check budget spent on drafts before ready pull requests: fetch ready ones first" if explains
                    else "the retained evidence does not show an acquisition-order cause")}


# -- the loop ----------------------------------------------------------------------------------------

def _recently_lost(journal: Journal, lever: str, candidate: dict, current: dict, new_evidence: int) -> bool:
    """Anti-thrash: a change rejected, reverted or expired between the same two policies waits for new evidence."""
    pair = {policy_id(candidate, lever), policy_id(current, lever)}
    for kind in ("improvement.rejected", "improvement.reverted", "improvement.expired"):
        for data in _payloads(journal, kind):
            if data.get("lever", "brief.attention") != lever:
                continue
            other = data.get("replaces") or data.get("restores")
            try:
                same = {policy_id(data["policy"], lever), policy_id(other, lever)} == pair
            except ImprovementError:
                continue
            if same and new_evidence(data) < HELD_OUT_MIN:
                return True
    return False


def _derive(cases: list[dict], current: dict) -> tuple[dict | None, dict]:
    """Smallest change in the attention space that strictly reduces errors on the training cases."""
    base = sum(errors(current, c) for c in cases)
    best, best_key = None, None
    fields = sorted(briefs.ATTENTION_SPACE)
    for values in product(*(briefs.ATTENTION_SPACE[f] for f in fields)):
        policy = dict(zip(fields, values))
        err = sum(errors(policy, c) for c in cases)
        key = (err, sum(policy[f] != current[f] for f in fields), repr(sorted(policy.items())))
        if err < base and (best_key is None or key < best_key):
            best, best_key = policy, key
    return best, {"current_errors": base, "candidate_errors": None if best is None else best_key[0],
                  "fields_changed": None if best is None else best_key[1]}


def verdict(current_errors: int, candidate_errors: int) -> str:
    """The one meaning of RETAIN: strictly fewer errors. A tie is a rejection; doing nothing wins ties."""
    return "retained" if candidate_errors < current_errors else "rejected"


def _record_decision(journal: Journal, verdict: str, record: dict) -> dict:
    journal.record("improvement." + verdict, record, key=[record["candidate_id"], verdict])
    return record


def _expire(journal: Journal, now: datetime, written: list):
    for cand in _proposals(journal):
        if cand["candidate_id"] in _decided(journal):
            continue
        proposed_at = datetime.fromisoformat(cand["at"].replace("Z", "+00:00"))
        if now - proposed_at >= timedelta(days=MAX_PENDING_DAYS):
            written.append(_record_decision(journal, "expired", {
                "candidate_id": cand["candidate_id"], "lever": cand["lever"], "policy": cand["policy"],
                "replaces": cand["replaces"], "decision": "NO_IMPROVEMENT", "at": iso(now), "applied": False,
                "decided_after_seq": len(journal.replay()),
                "why": f"insufficient held-out evidence within {MAX_PENDING_DAYS} days; nothing retained"}))


def _learn_preferences(journal: Journal, ledger, now: datetime, written: list):
    lever = "brief.attention"
    cases = labelled_cases(journal, ledger)
    for cand in _proposals(journal, lever):
        state = _decided(journal).get(cand["candidate_id"], {})
        if "rejected" in state or "reverted" in state or "expired" in state:
            continue
        if "retained" in state:
            since = state["retained"]["decided_after_seq"]
            later = [c for c in cases if c["brief_seq"] > since]
            if len(later) >= HELD_OUT_MIN:
                kept = sum(errors(cand["policy"], c) for c in later)
                prior = sum(errors(cand["replaces"], c) for c in later)
                if kept > prior:
                    written.append(_record_decision(journal, "reverted", {
                        "candidate_id": cand["candidate_id"], "lever": lever, "policy": cand["policy"],
                        "restores": cand["replaces"], "cases": [c["case_id"] for c in later],
                        "decided_after_seq": later[-1]["seq"], "errors": {"retained": kept, "restored": prior},
                        "at": iso(now), "by": "held-out evidence",
                        "why": "lost to the policy it replaced on later founder-labelled briefs"}))
                    _reopen_regressions(journal, cand, now)
            continue
        held_out = _held_out(cand, cases)
        for case in held_out:
            journal.record("improvement.evaluated", {
                "candidate_id": cand["candidate_id"], "lever": lever, "case_id": case["case_id"],
                "errors": {"current": errors(cand["replaces"], case), "candidate": errors(cand["policy"], case)}},
                key=[cand["candidate_id"], case["case_id"]])
        if len(held_out) < HELD_OUT_MIN:
            continue
        held_out = held_out[:HELD_OUT_MIN]           # decided on exactly the first eligible cases
        current = sum(errors(cand["replaces"], c) for c in held_out)
        candidate = sum(errors(cand["policy"], c) for c in held_out)
        decision = verdict(current, candidate)
        record = _record_decision(journal, decision, {
            "candidate_id": cand["candidate_id"], "lever": lever, "policy": cand["policy"],
            "replaces": cand["replaces"], "held_out": [c["case_id"] for c in held_out],
            "errors": {"current": current, "candidate": candidate}, "decided_after_seq": held_out[-1]["seq"],
            "at": iso(now), "rule": f"retain only on strictly fewer errors over {HELD_OUT_MIN} held-out "
                                    "founder-labelled briefs; ties and regressions are rejected"})
        written.append(record)
        if decision == "retained":
            _close_regressions(journal, cand, record, held_out, now)

    if _open(journal, lever) or not cases:
        return
    current = active_policy(journal, lever)
    latest = cases[-1]
    if errors(current, latest) == 0:
        return
    candidate, stats = _derive(cases, current)
    if candidate is not None and _recently_lost(
            journal, lever, candidate, current,
            lambda d: sum(c["brief_seq"] > d["decided_after_seq"] for c in cases)):   # new BRIEFS, not re-labels
        candidate, stats = None, {**stats, "suppressed": "this change lost its last held-out test; it may be "
                                                         f"proposed again after {HELD_OUT_MIN} new labelled briefs"}
    if candidate is None:
        written.append(journal.record("improvement.no_candidate", {
            "case_id": latest["case_id"], "lever": lever, "current": current, **stats,
            "why": stats.get("suppressed") or "no policy in the lever's space reduces the founder's corrections"},
            key=[latest["case_id"], policy_id(current, lever)]).payload)
        return
    derived = [c["case_id"] for c in cases]
    cid = "impr-" + sha256_json({"lever": lever, "policy": candidate, "replaces": current,
                                 "derived_from": derived, "after": latest["seq"]})[7:23]
    written.append(journal.record("improvement.proposed", {
        "candidate_id": cid, "lever": lever, "kind": "preference", "policy": candidate, "replaces": current,
        "policy_id": policy_id(candidate, lever), "derived_from": derived,
        "derived_from_briefs": [c["brief_event_id"] for c in cases], "proposed_after_seq": latest["seq"],
        "training": stats, "at": iso(now), "state": "SHADOW", "authority_changed": False,
        "evidence_basis": "founder_preference"}, key=cid).payload)


def _learn_evidence(journal: Journal, ledger, now: datetime, written: list):
    lever = "brief.acquisition"
    briefs_seen = {b["event_id"]: b for b in _briefs(journal, ledger)}
    for cand in _proposals(journal, lever):
        state = _decided(journal).get(cand["candidate_id"], {})
        if "rejected" in state or "reverted" in state or "expired" in state:
            continue
        if "retained" in state:
            since = state["retained"]["decided_after_seq"]
            later = _acquisition_cases(journal, ledger, "replaced:" + cand["candidate_id"], since, set())
            if len(later) >= HELD_OUT_MIN:
                kept = sum(evidence_score(c["production"]) for c in later)
                prior = sum(evidence_score(c["shadow"]) for c in later)
                if kept > prior:
                    written.append(_record_decision(journal, "reverted", {
                        "candidate_id": cand["candidate_id"], "lever": lever, "policy": cand["policy"],
                        "restores": cand["replaces"], "cases": [c["brief_event_id"] for c in later],
                        "decided_after_seq": later[-1]["seq"], "errors": {"retained": kept, "restored": prior},
                        "at": iso(now), "by": "independent observation",
                        "why": "missed more failing checks than the policy it replaced"}))
                    _reopen_regressions(journal, cand, now)
            continue
        cases = _acquisition_cases(journal, ledger, cand["candidate_id"], cand["_seq"],
                                   set(cand["derived_from_briefs"]))
        for case in cases:        # the founder's claim, checked against independent observation
            for ref in cand["claim"]["missed_failing"]:
                if ref in case["truth"]:
                    status = ("independently_verified_failure" if case["truth"][ref]["failing"]
                              else "not_reproduced")
                    journal.record("improvement.claim_checked", {
                        "candidate_id": cand["candidate_id"], "ref": ref, "status": status,
                        "observed": case["truth"][ref], "brief_event_id": case["brief_event_id"]},
                        key=[cand["candidate_id"], ref, case["brief_event_id"]])
            journal.record("improvement.evaluated", {
                "candidate_id": cand["candidate_id"], "lever": lever, "case_id": case["brief_event_id"],
                "production": case["production"], "candidate": case["shadow"]},
                key=[cand["candidate_id"], case["brief_event_id"]])
        if len(cases) < HELD_OUT_MIN:
            continue
        cases = cases[:HELD_OUT_MIN]
        current = sum(evidence_score(c["production"]) for c in cases)
        candidate = sum(evidence_score(c["shadow"]) for c in cases)
        extra_calls = [c["brief_event_id"] for c in cases if c["shadow"]["api_calls"] > c["production"]["api_calls"]]
        checked = [d for d in _payloads(journal, "improvement.claim_checked") if d["candidate_id"] == cand["candidate_id"]]
        verified = any(d["status"] == "independently_verified_failure" for d in checked)
        reasons = []
        if verdict(current, candidate) != "retained":
            reasons.append("not strictly fewer missed or unknown failing checks than the current policy")
        if extra_calls:
            reasons.append(f"used more calls than the current policy on {len(extra_calls)} case(s): an improvement "
                           "bought with calls does not count")
        if not verified:
            reasons.append("the founder's failure claim was not independently reproduced")
        decision = "rejected" if reasons else "retained"
        record = _record_decision(journal, decision, {
            "candidate_id": cand["candidate_id"], "lever": lever, "policy": cand["policy"],
            "replaces": cand["replaces"], "held_out": [c["brief_event_id"] for c in cases],
            "errors": {"current": current, "candidate": candidate}, "extra_call_cases": extra_calls,
            "claim": {"verified": verified, "checks": len(checked)}, "decided_after_seq": cases[-1]["seq"],
            "at": iso(now), "why": reasons,
            "rule": f"retain only on strictly fewer missed failing checks over {HELD_OUT_MIN} independently observed "
                    "briefs, never more calls, and an independently reproduced founder claim"})
        written.append(record)
        if decision == "retained":
            _close_regressions(journal, cand, record, [], now)

    # new candidates come only from founder failure claims, diagnosed against the retained evidence
    if _open(journal, lever):
        return
    order = _order(journal)
    current = active_policy(journal, lever)
    for event in journal.replay("critique.recorded"):
        data = event.payload
        brief = briefs_seen.get(data["target_event_id"])
        if data.get("failure_claim") is None or brief is None:
            continue
        if any(data["critique_id"] in p.get("derived_from", []) for p in _proposals(journal, lever)):
            continue
        if journal.replay("improvement.no_candidate") and any(
                d.get("case_id") == data["critique_id"] for d in _payloads(journal, "improvement.no_candidate")):
            continue
        claimed = data["failure_claim"]["missed_failing"]
        diagnosis = _diagnose(brief["output"]["inputs"], claimed)
        target = {"check_fetch_order": "ready_first"}
        if not diagnosis["explains"] or current == target:
            written.append(journal.record("improvement.no_candidate", {
                "case_id": data["critique_id"], "lever": lever, "current": current, "diagnosis": diagnosis,
                "why": diagnosis["why"] if not diagnosis["explains"] else "already fetching ready pull requests first",
                "claim_status": "founder_reported_failure (unverified)"},
                key=[data["critique_id"], policy_id(current, lever)]).payload)
            continue
        if _recently_lost(journal, lever, target, current,
                          lambda d: sum(b["seq"] > d["decided_after_seq"] for b in briefs_seen.values())):
            continue
        cid = "impr-" + sha256_json({"lever": lever, "policy": target, "replaces": current,
                                     "derived_from": [data["critique_id"]]})[7:23]
        written.append(journal.record("improvement.proposed", {
            "candidate_id": cid, "lever": lever, "kind": "evidence", "policy": target, "replaces": current,
            "policy_id": policy_id(target, lever), "derived_from": [data["critique_id"]],
            "derived_from_briefs": [brief["event_id"]], "proposed_after_seq": order[event.event_id],
            "claim": data["failure_claim"], "diagnosis": diagnosis, "at": iso(now), "state": "SHADOW",
            "authority_changed": False, "evidence_basis": "founder_reported_failure, to be independently verified"},
            key=cid).payload)
        return


def learn(journal: Journal, ledger, now) -> list[dict]:
    """Advance every lever from retained history. Idempotent; returns the records it wrote."""
    written = []
    _expire(journal, now, written)
    _learn_preferences(journal, ledger, now, written)
    _learn_evidence(journal, ledger, now, written)
    return written


def founder_revert(journal: Journal, critique: dict, target_event, now) -> dict | None:
    """A founder-signed rejection of a retained improvement reverts it; the evidence stays."""
    if target_event.type != "greg.improvement.retained" or critique["verdict"] != "reject":
        return None
    data = target_event.payload
    record = {"candidate_id": data["candidate_id"], "lever": data.get("lever", "brief.attention"),
              "policy": data["policy"], "restores": data["replaces"], "by": "founder",
              "critique_id": critique["critique_id"], "decided_after_seq": len(journal.replay()),
              "at": iso(now), "why": critique["text"][:300]}
    _record_decision(journal, "reverted", record)
    cand = next((p for p in _proposals(journal) if p["candidate_id"] == data["candidate_id"]), None)
    if cand:
        _reopen_regressions(journal, cand, now)
    return record


# -- regression obligations ---------------------------------------------------------------------------

def _attention_corrected(condition: dict, case: dict, cand: dict) -> dict | None:
    """Did this later brief show the SAME labelled error, and did the candidate remove all of it?

    Every key the originating critique labelled must recur in this brief's labels and be corrected
    (missed -> now flagged, noise -> no longer flagged), with no increase in total errors. A partial
    fix is not a fix: a regression naming two errors does not close because one of them went away."""
    wanted = condition["labels"]
    for kind in ("missed", "noise"):
        if not set(wanted[kind]) <= set(case["labels"][kind]):
            return None
    before = briefs.flagged_keys(case["inputs"], cand["replaces"])
    after = briefs.flagged_keys(case["inputs"], cand["policy"])
    fixed = (all(k not in before and k in after for k in wanted["missed"])
             and all(k in before and k not in after for k in wanted["noise"]))
    if not fixed or errors(cand["policy"], case) > errors(cand["replaces"], case):
        return None
    return {"case_id": case["case_id"], "brief_event_id": case["brief_event_id"],
            "baseline_errors": errors(cand["replaces"], case), "candidate_errors": errors(cand["policy"], case)}


def _close_regressions(journal: Journal, cand: dict, decision: dict, held_out: list[dict], now):
    """Close a regression only through its own close condition, proven by the retained evidence.

    A RETAIN is not enough. Attention: the originating critique's exact labelled error is removed on
    HELD_OUT_MIN later briefs without increasing errors (the rule from #122, tightened to require the
    whole error). Failure claim: the claim was independently reproduced and the retained acquisition
    missed strictly fewer failing checks on the held-out briefs. A reversion reopens the regression."""
    critiques = {d["critique_id"]: d for d in _payloads(journal, "critique.recorded")}
    for critique_id in cand["derived_from"]:
        regression = (critiques.get(critique_id) or {}).get("regression")
        if not regression:
            continue
        condition = regression["close_condition"]
        if cand["lever"] == "brief.attention":
            if not isinstance(condition, dict) or condition.get("kind") != "held_out_attention_correction":
                continue                                   # a free-text obligation closes through its own check
            evidence = [e for e in (_attention_corrected(condition, c, cand) for c in held_out) if e]
            satisfied = len(evidence) >= condition["min_cases"]
            proof = {"held_out_evidence": evidence, "held_out_errors": decision["errors"]}
        else:
            satisfied = decision["claim"]["verified"] and verdict(decision["errors"]["current"],
                                                                  decision["errors"]["candidate"]) == "retained"
            proof = {"claim_independently_verified": decision["claim"]["verified"],
                     "held_out_errors": decision["errors"]}
        if not satisfied:
            journal.record("critique.regression_still_open", {
                "regression_id": regression["regression_id"], "candidate_id": cand["candidate_id"],
                "why": "retained, but the close condition was not demonstrated", "proof": proof, "at": iso(now)},
                key=[regression["regression_id"], cand["candidate_id"], "still_open"])
            continue
        journal.record("critique.regression_closed", {
            "regression_id": regression["regression_id"], "critique_id": critique_id,
            "candidate_id": cand["candidate_id"], "lever": cand["lever"], "baseline": cand["replaces"],
            "retained": cand["policy"], "held_out": decision["held_out"], "decision": "RETAIN",
            "close_condition": condition, "proof": proof, "at": iso(now), "authority_changed": False},
            key=[regression["regression_id"], cand["candidate_id"], "closed"])


def _reopen_regressions(journal: Journal, cand: dict, now):
    for data in _payloads(journal, "critique.regression_closed"):
        if data["candidate_id"] == cand["candidate_id"]:
            journal.record("critique.regression_reopened", {
                "regression_id": data["regression_id"], "candidate_id": cand["candidate_id"],
                "why": "the change that closed it was reverted", "at": iso(now)},
                key=[data["regression_id"], cand["candidate_id"], "reopened"])


def attention_close_condition(labels: dict) -> dict:
    return {"kind": "held_out_attention_correction", "labels": labels, "min_cases": HELD_OUT_MIN,
            "rule": f"the same labelled error (every key) is removed on {HELD_OUT_MIN} later briefs without "
                    "increasing total errors; a reversion reopens it"}


def claim_close_condition() -> str:
    return (f"the claimed failure is independently reproduced and a retained acquisition policy missed strictly "
            f"fewer failing checks than the replaced one on {HELD_OUT_MIN} later independently observed briefs")


def report(journal: Journal, ledger) -> dict:
    """Founder corrections per labelled brief by the policy that produced it, and every decision."""
    cases = labelled_cases(journal, ledger)
    effective = {case["brief_event_id"]: case["case_id"] for case in cases}
    by_policy = {}
    for case in cases:
        pid = policy_id(case["delivered_policy"])
        row = by_policy.setdefault(pid, {"policy": case["delivered_policy"], "briefs": 0, "corrections": 0})
        row["briefs"] += 1
        row["corrections"] += errors(case["delivered_policy"], case)
    for row in by_policy.values():
        row["corrections_per_brief"] = round(row["corrections"] / row["briefs"], 3)
    ids = lambda kind: [d["candidate_id"] for d in _payloads(journal, "improvement." + kind)]
    return {"levers": {lever: {"kind": spec["kind"], "judged_by": spec["judged_by"],
                               "active_policy": active_policy(journal, lever)} for lever, spec in LEVERS.items()},
            "labelled_briefs": len(cases), "by_policy": by_policy,
            "superseded_labels": [{"case_id": c["case_id"], "brief_event_id": c["brief_event_id"], "labels": c["labels"],
                                   "superseded_by": effective[c["brief_event_id"]]}
                                  for c in labelled_cases(journal, ledger, every_label=True)
                                  if c["case_id"] != effective[c["brief_event_id"]]],
            "proposed": ids("proposed"), "retained": ids("retained"), "rejected": ids("rejected"),
            "reverted": ids("reverted"), "expired": ids("expired"),
            "claims": _payloads(journal, "improvement.claim_checked"),
            "no_candidate": len(journal.replay("improvement.no_candidate"))}
