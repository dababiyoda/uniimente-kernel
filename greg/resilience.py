"""Resilience and antifragility evidence from GREG's own ledger; organ-versus-whole decoupling warnings.

Founder directive 2026-10-07, sections 21-22. Read-only projections over retained ``greg.*`` events:

* failure -> recovery episodes per (mission, success check), from ``mission.observed``: mean and median
  recovery time, recurrence after recovery, recovery without a founder decision in between, and the
  diversity of the recovery paths (distinct actions that ran during the episode);
* common-cause candidates: one capability failing in two or more missions within an hour;
* dependency concentration over completed actions (Herfindahl index and top share);
* performance after failure per capability (completion rate of the next actions vs the previous ones);
* an honest per-capability verdict. ANTIFRAGILE_EVIDENCE requires repeated failures, measurably better
  operation afterwards AND a recorded learning artifact (a closed critique regression, an evaluated
  improvement, an excluded strategy). Ordinary redundancy (several strategies) is reported as recovery
  diversity and never earns the label;
* decoupling: a local metric improving while the whole-system outcome degrades (a capability's
  completion rate rising while the share of passing success checks falls) is a critical warning.

Nothing here writes, acts, retries or creates failures: section 21 forbids inducing failures in live
environments; controlled tests use synthetic journals.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import statistics

FAILED_ACTIONS = ("FAILED", "ERROR", "UNCERTAIN")
LEARNING_EVENTS = ("critique.regression_closed", "improvement.evaluated", "improvement.proposed",
                   "mission.strategy_excluded")
MIN_FAILURES = 3
MATERIAL = 0.1
WINDOW = 5


def _at(event) -> datetime:
    raw = (event.payload or {}).get("at") or getattr(event, "occurred_at", None)
    moment = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError("resilience needs timezone-aware event times")
    return moment


def _events(journal, prefix):
    return sorted(journal.replay(prefix), key=_at)


def episodes(journal) -> list[dict]:
    """Failure -> recovery episodes per (mission, check), in time order."""
    actions = _events(journal, "mission.action")
    answers = _events(journal, "decision.answered")
    state, open_, recovered_before, out = {}, {}, defaultdict(int), []
    for event in _events(journal, "mission.observed"):
        p = event.payload
        key = (p["mission_id"], p["check_id"])
        when = _at(event)
        if not p["passed"] and state.get(key) != "failing":
            open_[key] = {"mission_id": key[0], "check_id": key[1], "failed_at": when,
                          "recurrence": recovered_before[key] > 0}
        elif p["passed"] and state.get(key) == "failing" and key in open_:
            ep = open_.pop(key)
            start = ep["failed_at"]
            ran = [a.payload for a in actions if a.payload.get("mission_id") == key[0] and start <= _at(a) <= when
                   and a.payload.get("status") == "DONE"]
            founder = any(a.payload.get("mission_id") == key[0] and start <= _at(a) <= when for a in answers)
            out.append({**ep, "recovered_at": when, "seconds": (when - start).total_seconds(),
                        "founder_intervened": founder,
                        "recovery_actions": sorted({r["action_id"] for r in ran}),
                        "recovery_capabilities": sorted({r.get("capability", "?") for r in ran})})
            recovered_before[key] += 1
        state[key] = "passing" if p["passed"] else "failing"
    for ep in open_.values():
        out.append({**ep, "recovered_at": None, "seconds": None, "founder_intervened": None,
                    "recovery_actions": [], "recovery_capabilities": []})
    return sorted(out, key=lambda e: (e["failed_at"], e["mission_id"], e["check_id"]))


def common_causes(journal, window: timedelta = timedelta(hours=1)) -> list[dict]:
    failed = [e for e in _events(journal, "mission.action") if e.payload.get("status") in FAILED_ACTIONS]
    by_cap = defaultdict(list)
    for e in failed:
        by_cap[e.payload.get("capability", "?")].append(e)
    out = []
    for cap, events in sorted(by_cap.items()):
        for i, first in enumerate(events):
            near = [e for e in events[i:] if _at(e) - _at(first) <= window]
            missions = sorted({e.payload["mission_id"] for e in near})
            if len(missions) >= 2:
                out.append({"capability": cap, "missions": missions, "first_at": _at(first).isoformat(),
                            "failures": len(near)})
                break
    return out


def concentration(journal) -> dict:
    done = defaultdict(int)
    for e in journal.replay("mission.action"):
        if e.payload.get("status") == "DONE":
            done[e.payload.get("capability", "?")] += 1
    total = sum(done.values())
    if not total:
        return {"completed_actions": 0, "herfindahl": None, "top": None}
    shares = {k: v / total for k, v in done.items()}
    top = max(shares.items(), key=lambda kv: (kv[1], kv[0]))
    return {"completed_actions": total, "herfindahl": round(sum(s * s for s in shares.values()), 4),
            "top": {"capability": top[0], "share": round(top[1], 4)}}


def after_failure(journal) -> dict:
    """Per capability: completion rate of the WINDOW actions after each failure vs the WINDOW before."""
    by_cap = defaultdict(list)
    for e in _events(journal, "mission.action"):
        status = e.payload.get("status")
        if status == "DONE" or status in FAILED_ACTIONS:
            by_cap[e.payload.get("capability", "?")].append((_at(e), status == "DONE"))
    learned_at = [_at(e) for kind in LEARNING_EVENTS for e in journal.replay(kind)]
    out = {}
    for cap, seq in sorted(by_cap.items()):
        failures = [i for i, (_, ok) in enumerate(seq) if not ok]
        before = [ok for i in failures for _, ok in seq[max(0, i - WINDOW):i]]
        after = [ok for i in failures for _, ok in seq[i + 1:i + 1 + WINDOW]]
        pre = statistics.fmean(before) if before else None
        post = statistics.fmean(after) if after else None
        learning = bool(failures) and any(t >= seq[failures[0]][0] for t in learned_at)
        if len(failures) < MIN_FAILURES or pre is None or post is None:
            verdict = "INSUFFICIENT_EVIDENCE"
        elif post >= pre + MATERIAL and learning:
            verdict = "ANTIFRAGILE_EVIDENCE"
        elif post >= pre + MATERIAL:
            verdict = "IMPROVED_AFTER_FAILURE_WITHOUT_LEARNING_RECORD"
        elif post <= pre - MATERIAL:
            verdict = "FRAGILE"
        else:
            verdict = "ROBUST"
        out[cap] = {"failures": len(failures), "completion_before": pre, "completion_after": post,
                    "learning_artifact_after_failure": learning, "verdict": verdict}
    return out


def _theil_sen(points: list[tuple[float, float]]) -> float | None:
    slopes = [(y2 - y1) / (x2 - x1) for i, (x1, y1) in enumerate(points) for x2, y2 in points[i + 1:] if x2 != x1]
    return statistics.median(slopes) if slopes else None


def decoupling(local: list[tuple[float, float]], whole: list[tuple[float, float]], *, min_points: int = 4) -> dict:
    """WARNING when the local metric trends up while the whole-system outcome trends down (Theil-Sen)."""
    if len(local) < min_points or len(whole) < min_points:
        return {"state": "INSUFFICIENT_EVIDENCE", "local_points": len(local), "whole_points": len(whole)}
    ls, ws = _theil_sen(local), _theil_sen(whole)
    warn = ls is not None and ws is not None and ls > 0 and ws < 0
    return {"state": "DECOUPLING_WARNING" if warn else "COUPLED_OR_UNCLEAR", "local_slope": ls, "whole_slope": ws}


def decoupling_from_journal(journal) -> list[dict]:
    """Each capability's daily completion rate (local) against the daily share of passing checks (whole)."""
    whole_days = defaultdict(list)
    for e in journal.replay("mission.observed"):
        whole_days[_at(e).date()].append(1.0 if e.payload["passed"] else 0.0)
    if not whole_days:
        return []
    origin = min(whole_days)
    whole = [((d - origin).days, statistics.fmean(v)) for d, v in sorted(whole_days.items())]
    per_cap = defaultdict(lambda: defaultdict(list))
    for e in journal.replay("mission.action"):
        status = e.payload.get("status")
        if status == "DONE" or status in FAILED_ACTIONS:
            per_cap[e.payload.get("capability", "?")][_at(e).date()].append(1.0 if status == "DONE" else 0.0)
    out = []
    for cap, days in sorted(per_cap.items()):
        local = [((d - origin).days, statistics.fmean(v)) for d, v in sorted(days.items())]
        out.append({"capability": cap, **decoupling(local, whole)})
    return out


def summary(journal) -> dict:
    eps = episodes(journal)
    closed = [e for e in eps if e["recovered_at"] is not None]
    times = [e["seconds"] for e in closed]
    paths = defaultdict(set)
    for e in closed:
        paths[(e["mission_id"], e["check_id"])].add(tuple(e["recovery_actions"]))
    report = {
        "reality_status": "RETAINED_EVIDENCE_PROJECTION",
        "episodes": {"failures": len(eps), "recovered": len(closed), "open": len(eps) - len(closed),
                     "mean_recovery_seconds": statistics.fmean(times) if times else None,
                     "median_recovery_seconds": statistics.median(times) if times else None,
                     "recurrence_rate": (sum(e["recurrence"] for e in eps) / len(eps)) if eps else None,
                     "recovered_without_founder": (sum(not e["founder_intervened"] for e in closed) / len(closed))
                     if closed else None,
                     "recovery_path_diversity": {f"{m}/{c}": len(v) for (m, c), v in sorted(paths.items())}},
        "common_cause_candidates": common_causes(journal),
        "dependency_concentration": concentration(journal),
        "after_failure": after_failure(journal),
        "decoupling": decoupling_from_journal(journal),
        "rule": "redundancy is recovery diversity, not antifragility; ANTIFRAGILE_EVIDENCE needs >= 3 failures, "
                "completion after failures >= 0.1 above before, and a recorded learning artifact",
        "induces_failures": False, "writes": 0,
    }
    report["warnings"] = ([f"decoupling: {d['capability']} improves while system checks degrade"
                           for d in report["decoupling"] if d["state"] == "DECOUPLING_WARNING"]
                          + [f"common cause: {c['capability']} failed in {len(c['missions'])} missions"
                             for c in report["common_cause_candidates"]]
                          + [f"fragile: {cap}" for cap, v in report["after_failure"].items()
                             if v["verdict"] == "FRAGILE"])
    return report
