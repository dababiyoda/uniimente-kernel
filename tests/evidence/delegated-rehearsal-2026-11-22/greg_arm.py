"""The GREG arms of the delegated rehearsal: one real Body, signed read-only missions, a scripted founder.

    python tests/evidence/delegated-rehearsal-2026-11-22/greg_arm.py {current|improved} {tampa|staffing} OUT.json

``current`` is GREG as it is without a method grant: every withheld family a mission reaches raises a CAPABILITY_ATTACH
ask, and the scripted founder answers each ask with exactly the attach it recommends (one signed command per
capability). ``improved`` differs only in one founder-signed CAPABILITY_GRANT over the reviewed read-only methods,
signed once before the task (counted as a founder act, not as an interruption).

Both arms get the same founder-authored typed translation of the evidence pack (``TASKS`` below): GREG has no
permitted local language model on this body, so it does not read the messy pack itself. Evidence triage (dropping
the promotional E2, the stale E3 and the typo E10) is in that translation, which favours both GREG arms over the
Claude arm; it is disclosed in RESULTS.md. Midway, the founder's correction arrives as one signed MISSION carrying the
corrected inputs, in both arms. Interruptions are founder asks GREG raised that had to be answered before the answer
was usable; founder acts are every signed command after the task started.
"""
from __future__ import annotations

import json
import resource
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from greg.body import Body  # noqa: E402
from greg.journal import iso  # noqa: E402
from tests.greg_fixtures import Clock, drop, make_body, mission, signed  # noqa: E402

GRANTED = ("cognition.probabilistic", "cognition.decision_preposterior", "cognition.information",
           "cognition.forecast_quantile", "cognition.newsvendor_compile")


def solve(target, params, check_id, field, value):
    step = {"capability": "cognition.solve", "target": f"cognition:{target}", "params": params}
    return ({"check_id": check_id, "description": check_id, "sensor": step,
             "predicate": {"op": "equals", "field": field, "value": value}},
            {"action_id": check_id, **step, "advances": [check_id], "rationale": check_id})


def net(corner, j, p, v, f):
    return solve(f"net-{corner}", {"problem_id": f"tampa:net-{corner}", "operation": "calculate",
                                   "data": {"expression": "j*(p-v)-f", "variables": {"j": j, "p": p, "v": v, "f": f}}},
                 f"net_{corner}", "abstention_state", "NONE")


def next_test(accounts, tag):
    payload = {"beta_evidence": {"alpha": 1, "beta": 1, "successes": 3, "failures": 22},
               "pilot_option": {"pilot_size": 30, "pilot_cost": 300},
               "decision_model": {"customers": accounts, "value_per_success": 730, "fixed_cost": 18000}}
    return solve(f"test-{tag}", {"problem_id": f"tampa:next-test-{tag}", "chain": {"recipe": "bayes_then_voi",
                                                                                   "payload": payload}},
                 f"next_test_{tag}", "state", "ANSWERED")


def vendor():
    return solve("vendor", {"problem_id": "tampa:vendor-claim", "operation": "treatment_effect",
                            "data": {"design": "observational", "treated": [], "control": [],
                                     "treatment": "vendor degreaser", "outcome": "fire claims"}},
                 "vendor_claim", "abstention_state", "UNIDENTIFIED")


def tampa():
    before = [net("low", 18, 350, 110, 2500), net("high", 30, 650, 60, 1500), next_test(400, "before"), vendor()]
    after = [next_test(250, "after")]                        # the correction changes the reachable accounts only
    return before, after


def staffing():
    """Transfer task: next month's cleaning-supply order from a demand history, then a corrected history."""
    def order(history, tag):
        payload = {"demand_histories": [{"name": "degreaser", "history": history, "over_cost": 4, "under_cost": 30}],
                   "newsvendor": {"capacity": 400, "weeks": 2, "scenarios": 5}}
        return solve(f"order-{tag}", {"problem_id": f"supply:order-{tag}", "chain": {"recipe": "forecast_then_allocate",
                                                                                    "payload": payload}},
                     f"order_{tag}", "state", "ANSWERED")
    # 72 synthetic daily litres (the forecaster needs 60 or more points); deterministic trend plus a weekly wobble.
    # A first draft gave it 12 weekly points: GREG abstained, rightly, but the founder only saw NO_STRATEGY
    # (RESULTS.md, "where it still stopped too early").
    history = [round(40 + 0.25 * d + (6, -3, 2, -5, 4, -1, 0)[d % 7], 2) for d in range(72)]
    corrected = history[:-7] + [round(v * 0.8, 2) for v in history[-7:]]     # last week's entries were 25% high
    return [order(history, "before")], [order(corrected, "after")]


TASKS = {"tampa": tampa, "staffing": staffing}


def _mission(mid, pairs):
    checks, strategies = zip(*pairs)
    return mission(mid, checks=list(checks), strategies=list(strategies), capabilities=["cognition.solve"],
                   targets=("cognition:*",), ceiling="read_only")


def _drive(body, key, body_id, clock, mid, counts, *, rounds=12):
    for _ in range(rounds):
        body.tick()
        if body.engine.book.missions[mid].status == "ACHIEVED":
            return True
        answered = {e.payload["request_id"] for e in body.journal.replay("decision.")
                    if e.type in ("greg.decision.answered", "greg.decision.withdrawn")}
        for ask in body.journal.replay("decision.requested"):
            a = ask.payload
            if a["request_id"] in counts["seen"] or a["request_id"] in answered:
                continue
            counts["seen"].add(a["request_id"])
            counts["interruptions"] += 1
            counts["asks"].append({"kind": a["kind"], "why": a.get("why_now", "")[:200], "recommendation": a.get("recommendation", "")[:300]})
            if a["kind"] == "CAPABILITY_ATTACH":     # the founder does what the ask recommends: attach each one
                for cid in a.get("authority_requested", {}).get("capabilities", []):
                    if body.registry.state.get(cid) != "ATTACHED":
                        body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))
                        counts["founder_acts"] += 1
        clock.advance(31)
    return body.engine.book.missions[mid].status == "ACHIEVED"


def _answers(body):
    out = {}
    for rec in body.ledger.by_type("receipt"):
        o = (rec.payload.get("result") or {}).get("output")
        if not isinstance(o, dict):
            continue
        pid = o.get("problem_id") or (o.get("chain") or {}).get("problem_id") or ""
        if o.get("schema", "").startswith("greg.cognition.chain") or "recipe" in o:
            out[pid or o.get("recipe")] = {"state": o.get("state"), "answer": o.get("answer")}
        elif pid:
            out[pid] = {"abstention_state": o.get("abstention_state"), "output": o.get("output"),
                        "method": o.get("method")}
    return out


def run(arm, task):
    t0, c0 = time.monotonic(), resource.getrusage(resource.RUSAGE_SELF).ru_utime + \
        resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime
    before, after = TASKS[task]()
    with tempfile.TemporaryDirectory() as tmp:
        home, key, body_id, _ = make_body(Path(tmp))
        clock = Clock()
        counts = {"interruptions": 0, "founder_acts": 0, "asks": [], "seen": set()}
        with Body(home, clock=clock) as body:
            if arm == "improved":
                start = clock()
                body.apply(signed(key, body_id, "CAPABILITY_GRANT", {
                    "grant_id": "rehearsal-read-only", "data_classes": [], "max_uses": 500,
                    "capabilities": {c: body.registry.manifests[c].digest() for c in GRANTED},
                    "not_before": iso(start), "expires_at": iso(start + timedelta(days=7)),
                    "purpose": "read-only analysis for the delegated rehearsal"}))
            body.apply(signed(key, body_id, "MISSION", _mission(f"m:{task}-first", before)))
            body.boot()
            first = _drive(body, key, body_id, clock, f"m:{task}-first", counts)
            body.apply(signed(key, body_id, "MISSION", _mission(f"m:{task}-corrected", after)))   # the correction
            counts["founder_acts"] += 1
            second = _drive(body, key, body_id, clock, f"m:{task}-corrected", counts)
            answers = _answers(body)
    c1 = resource.getrusage(resource.RUSAGE_SELF).ru_utime + resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime
    return {"arm": arm, "task": task, "first_mission_achieved": first, "corrected_mission_achieved": second,
            "interruptions": counts["interruptions"], "founder_acts_after_start": counts["founder_acts"],
            "asks": counts["asks"], "answers": answers, "wall_s": round(time.monotonic() - t0, 2),
            "cpu_s": round(c1 - c0, 2), "money_usd": 0.0, "model_calls": 0}


if __name__ == "__main__":
    arm, task, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    result = run(arm, task)
    out.write_text(json.dumps(result, indent=2, sort_keys=True, default=str) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k not in ("answers", "asks")}, indent=1))
