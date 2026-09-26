"""Verified learning: GREG keeps a change it learned only if it beats the unchanged behavior later.

    brief delivered -> Alfonso labels it (signed CRITIQUE: what it missed, what was noise)
      -> diagnosis: the smallest change in the lever's space that explains the correction
      -> candidate recorded with the cases it was derived from
      -> later briefs Alfonso labels (never the derivation cases) are HELD OUT
      -> exact counterfactual: each held-out brief's receipted inputs are re-rendered under
         the current policy and under the candidate, and scored against his labels
      -> RETAIN (strictly fewer errors over >= HELD_OUT_MIN cases) or REJECT (tie or worse)
      -> a retained policy keeps being compared with the one it replaced; if it loses on
         later held-out cases it is REVERTED
      -> the next brief uses whichever policy is active; its inputs record it

Why the counterfactual is exact, not simulated: a brief is a deterministic render of the
inputs its receipt retains, so "what would the brief have flagged under policy P" is a
replay of recorded reality, not a model of it.

Bounds. The only lever is ``brief.attention`` (what the brief flags for the founder),
a closed space defined next to the capability that consumes it. A policy cannot express
authority, budget, consequence class, credentials, targets, shutdown or external effects,
and it never overrides a founder-signed parameter. Every candidate, verdict and negative
result stays in the ledger. Labels are the founder's own signed critiques; unlabelled
briefs are not evidence.
"""
from __future__ import annotations

from itertools import product

from greg import briefs
from greg.journal import Journal, iso
from provenance.ledger import sha256_json

LEVER = "brief.attention"
HELD_OUT_MIN = 3
MAX_LABELS = 50


class ImprovementError(ValueError):
    pass


def validate_labels(labels) -> dict:
    """The founder's attention label on one delivered brief: {"missed": [...], "noise": [...]}."""
    if not isinstance(labels, dict) or set(labels) - {"missed", "noise"}:
        raise ImprovementError("attention labels are {missed: [keys], noise: [keys]}")
    out = {}
    for field in ("missed", "noise"):
        values = labels.get(field, [])
        if not isinstance(values, list) or len(values) > MAX_LABELS or not all(
                isinstance(v, str) and 0 < len(v) <= 200 for v in values):
            raise ImprovementError(f"attention.{field} must be a list of at most {MAX_LABELS} keys")
        out[field] = sorted(set(values))
    if set(out["missed"]) & set(out["noise"]):
        raise ImprovementError("a key cannot be both missed and noise")
    return out


def validate_policy(policy: dict) -> dict:
    if set(policy) != set(briefs.ATTENTION_SPACE):
        raise ImprovementError("policy must set exactly the attention lever's fields")
    for field, value in policy.items():
        if value not in briefs.ATTENTION_SPACE[field]:
            raise ImprovementError(f"{field}={value!r} is outside the lever's space")
    return dict(policy)


def policy_id(policy: dict) -> str:
    return "attn-" + sha256_json(validate_policy(policy))[7:19]


# -- cases: delivered briefs the founder labelled ------------------------------------------

def labelled_cases(journal: Journal, ledger) -> list[dict]:
    """Every founder-labelled brief, oldest label first, with the inputs its receipt retains."""
    events = {e.event_id: e for e in journal.replay("mission.action")}
    order = {e.event_id: i for i, e in enumerate(journal.replay())}   # one ordering across every fact
    cases = []
    for event in journal.replay("critique.recorded"):
        data = event.payload
        labels = data.get("attention")
        target = events.get(data["target_event_id"])
        if labels is None or target is None or target.payload.get("status") != "DONE" or not target.payload.get("receipt"):
            continue
        receipt = ledger.find(target.payload["receipt"])
        output = (receipt.payload.get("result") or {}).get("output") if receipt is not None else None
        if not isinstance(output, dict) or "inputs" not in output or \
                briefs.inputs_digest(output["inputs"]) != output.get("inputs_digest"):
            continue   # not a brief, or its retained inputs do not match their digest: not evidence
        inputs = output["inputs"]
        delivered = briefs.flagged_keys(inputs)
        truth = (delivered - set(labels["noise"])) | set(labels["missed"])
        cases.append({"case_id": data["critique_id"], "seq": order[event.event_id],
                      "brief_event_id": target.event_id, "inputs": inputs, "truth": sorted(truth),
                      "delivered_policy": briefs.attention_policy(inputs)})
    return cases


def errors(policy: dict, case: dict) -> int:
    """Disagreements with the founder's label: flagged but unwanted, plus wanted but not flagged."""
    return len(briefs.flagged_keys(case["inputs"], policy) ^ set(case["truth"]))


# -- state -------------------------------------------------------------------------------

def _decided(journal: Journal) -> dict[str, dict]:
    out = {}
    for kind in ("improvement.retained", "improvement.rejected", "improvement.reverted"):
        for event in journal.replay(kind):
            out.setdefault(event.payload["candidate_id"], {})[kind.split(".")[1]] = event.payload
    return out


def active_policy(journal: Journal) -> dict:
    """The policy briefs use now: the last retained candidate that was not reverted, else the baseline."""
    reverted = {e.payload["candidate_id"] for e in journal.replay("improvement.reverted")}
    retained = [e.payload for e in journal.replay("improvement.retained") if e.payload["candidate_id"] not in reverted]
    return dict(retained[-1]["policy"]) if retained else dict(briefs.ATTENTION_BASELINE)


def learned(journal: Journal) -> dict:
    """What the mission engine hands capabilities: only non-baseline, held-out-verified policies."""
    policy = active_policy(journal)
    return {LEVER: policy} if policy != briefs.ATTENTION_BASELINE else {}


# -- the loop ------------------------------------------------------------------------------

def _derive(cases: list[dict], current: dict) -> tuple[dict | None, dict]:
    """Smallest change in the lever's space that strictly reduces errors on the training cases."""
    base = sum(errors(current, c) for c in cases)
    best, best_key = None, None
    fields = sorted(briefs.ATTENTION_SPACE)
    for values in product(*(briefs.ATTENTION_SPACE[f] for f in fields)):
        policy = dict(zip(fields, values))
        err = sum(errors(policy, c) for c in cases)
        changed = sum(policy[f] != current[f] for f in fields)
        key = (err, changed, repr(sorted(policy.items())))
        if err < base and (best_key is None or key < best_key):
            best, best_key = policy, key
    return best, {"current_errors": base, "candidate_errors": None if best is None else best_key[0],
                  "fields_changed": None if best is None else best_key[1]}


def _recently_lost(journal: Journal, candidate: dict, current: dict, cases: list[dict]) -> bool:
    """Anti-thrash: a change that was rejected or reverted between the same two policies waits for new evidence."""
    pair = {policy_id(candidate), policy_id(current)}
    for kind in ("improvement.rejected", "improvement.reverted"):
        for event in journal.replay(kind):
            data = event.payload
            other = data.get("replaces") or data.get("restores")
            if {policy_id(data["policy"]), policy_id(other)} == pair and \
                    sum(c["seq"] > data["decided_after_seq"] for c in cases) < HELD_OUT_MIN:
                return True
    return False


def learn(journal: Journal, ledger, now) -> list[dict]:
    """Advance the loop from retained history. Idempotent; returns the records it wrote."""
    written = []
    cases = labelled_cases(journal, ledger)
    decided = _decided(journal)
    proposals = [e.payload for e in journal.replay("improvement.proposed")]

    for cand in proposals:
        outcome = decided.get(cand["candidate_id"], {})
        if "rejected" in outcome or "reverted" in outcome:
            continue
        if "retained" in outcome:
            # keep comparing a retained policy with the one it replaced, on labels given after retention
            since = outcome["retained"]["decided_after_seq"]
            later = [c for c in cases if c["seq"] > since]
            if len(later) >= HELD_OUT_MIN:
                kept = sum(errors(cand["policy"], c) for c in later)
                prior = sum(errors(cand["replaces"], c) for c in later)
                if kept > prior:
                    record = {"candidate_id": cand["candidate_id"], "lever": LEVER, "policy": cand["policy"],
                              "restores": cand["replaces"], "cases": [c["case_id"] for c in later],
                              "decided_after_seq": later[-1]["seq"],
                              "errors": {"retained": kept, "restored": prior}, "at": iso(now),
                              "why": "lost to the policy it replaced on later founder-labelled briefs"}
                    journal.record("improvement.reverted", record, key=[cand["candidate_id"], "reverted"])
                    written.append(record)
            continue
        held_out = [c for c in cases if c["seq"] > cand["proposed_after_seq"] and c["case_id"] not in cand["derived_from"]]
        for case in held_out:
            record = {"candidate_id": cand["candidate_id"], "case_id": case["case_id"],
                      "errors": {"current": errors(cand["replaces"], case), "candidate": errors(cand["policy"], case)}}
            journal.record("improvement.evaluated", record, key=[cand["candidate_id"], case["case_id"]])
        if len(held_out) < HELD_OUT_MIN:
            continue
        current = sum(errors(cand["replaces"], c) for c in held_out)
        candidate = sum(errors(cand["policy"], c) for c in held_out)
        verdict = "retained" if candidate < current else "rejected"
        record = {"candidate_id": cand["candidate_id"], "lever": LEVER, "policy": cand["policy"],
                  "replaces": cand["replaces"], "held_out": [c["case_id"] for c in held_out],
                  "errors": {"current": current, "candidate": candidate}, "decided_after_seq": held_out[-1]["seq"],
                  "at": iso(now), "rule": f"retain only on strictly fewer errors over >= {HELD_OUT_MIN} "
                                          "held-out founder-labelled briefs; ties and regressions are rejected"}
        journal.record("improvement." + verdict, record, key=[cand["candidate_id"], verdict])
        written.append(record)
        decided = _decided(journal)

    open_candidates = [p for p in proposals if p["candidate_id"] not in decided]
    if not open_candidates and cases:
        current = active_policy(journal)
        latest = cases[-1]
        if errors(current, latest) > 0:
            candidate, stats = _derive(cases, current)
            if candidate is not None and _recently_lost(journal, candidate, current, cases):
                candidate, stats = None, {**stats, "suppressed": "this change lost its last held-out test; it may be "
                                                                  f"proposed again after {HELD_OUT_MIN} new labelled briefs"}
            if candidate is None:
                record = {"case_id": latest["case_id"], "lever": LEVER, "current": current, **stats,
                          "why": stats.get("suppressed") or "no policy in the lever's space reduces the founder's "
                                                            "corrections"}
                journal.record("improvement.no_candidate", record, key=[latest["case_id"], policy_id(current)])
                written.append(record)
            else:
                cid = "impr-" + sha256_json({"policy": candidate, "replaces": current,
                                             "derived_from": [c["case_id"] for c in cases]})[7:23]
                record = {"candidate_id": cid, "lever": LEVER, "policy": candidate, "replaces": current,
                          "policy_id": policy_id(candidate), "derived_from": [c["case_id"] for c in cases],
                          "proposed_after_seq": latest["seq"], "training": stats, "at": iso(now),
                          "state": "SHADOW", "authority_changed": False}
                journal.record("improvement.proposed", record, key=cid)
                written.append(record)
    return written


def report(journal: Journal, ledger) -> dict:
    """Founder corrections per labelled brief, by the policy that produced each brief."""
    cases = labelled_cases(journal, ledger)
    by_policy = {}
    for case in cases:
        pid = policy_id(case["delivered_policy"])
        row = by_policy.setdefault(pid, {"policy": case["delivered_policy"], "briefs": 0, "corrections": 0})
        row["briefs"] += 1
        row["corrections"] += errors(case["delivered_policy"], case)
    for row in by_policy.values():
        row["corrections_per_brief"] = round(row["corrections"] / row["briefs"], 3)
    return {"lever": LEVER, "active_policy": active_policy(journal), "labelled_briefs": len(cases),
            "by_policy": by_policy,
            "proposed": [e.payload["candidate_id"] for e in journal.replay("improvement.proposed")],
            "retained": [e.payload["candidate_id"] for e in journal.replay("improvement.retained")],
            "rejected": [e.payload["candidate_id"] for e in journal.replay("improvement.rejected")],
            "reverted": [e.payload["candidate_id"] for e in journal.replay("improvement.reverted")],
            "no_candidate": len(journal.replay("improvement.no_candidate"))}
