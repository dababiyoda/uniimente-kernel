"""Read-only rehearsal: founder interruptions and blocked time with and without one standing method grant.

Each arm runs on a fresh real Body (real Genesis, real compiler, the real frozen evidence index). The questions
come from the registered genomes' own instance generators (synthetic inputs; no external data). Baseline: the
founder answers each CAPABILITY_ATTACH ask the moment it appears. Grant: the founder signs one METHOD_GRANT
before the missions arrive. Run: PYTHONPATH=. python docs/evidence/greg-method-grants/2026-11-22/rehearse.py
"""
from __future__ import annotations

from datetime import timedelta
import json
import sys
import tempfile
import time
from pathlib import Path

from greg.body import Body
from greg.cognition.genomes import library
from tests.greg_fixtures import Clock, make_body, mission, signed

SETS = {"business": ["queue_erlang", "newsvendor_compile", "knapsack_bnb", "mc_expectation", "info_experiment"],
        # a materially different task family: strategic, deductive, search and forecasting questions
        "transfer": ["game_minimax", "prove_resolution", "search_astar", "mech_vcg", "forecast_quantile"]}
FAMILIES = SETS["business"]
TICKS = 8


def question(name, item, seed):
    mid = f"m:{name.replace('_', '-')}-{seed}"
    params = {"problem_id": f"rehearsal:{mid}", "compile": {"geometry": {"geometry": item.genome.epistemic_class},
                                                            "data": item.instance(seed)[0]}}
    return mid, mission(mid, checks=[{
        "check_id": "answered", "description": "a competent method answered",
        "sensor": {"capability": "cognition.solve", "target": "cognition:rehearsal", "params": params},
        "predicate": {"op": "equals", "field": "state", "value": "ANSWERED"}}],
        strategies=[], capabilities=["cognition.solve"], targets=("cognition:*",), ceiling="read_only")


def arm(kind: str, seeds=(2, 3)) -> dict:
    ex = library.executables()
    with tempfile.TemporaryDirectory() as tmp:
        home, key, body_id, _ = make_body(Path(tmp))
        clock = Clock()
        started = time.monotonic()
        founder_actions, blocked_ticks, answered_by = 0, 0, {}
        with Body(home, clock=clock) as body:
            body.boot()
            reviewed = ["cognition." + f for f in FAMILIES]
            if kind == "suggested_grant":
                # the founder reviews what the compiler would use on sample questions (seeds 0 and 1, never the
                # questions the missions then ask), and signs that set
                from greg import method_grants
                samples = [question(n, ex[n], s)[1]["success_checks"][0]["sensor"]["params"]
                           for n in FAMILIES for s in (0, 1)]
                reviewed = method_grants.suggest(body.registry, samples)["methods_to_review"]
            if kind in ("grant", "grant_and_answers", "suggested_grant"):
                body.apply(signed(key, body_id, "METHOD_GRANT", {
                    "grant_id": "g:rehearsal", "capabilities": reviewed,
                    "targets": ["cognition:rehearsal"], "until": (clock() + timedelta(days=7)).isoformat(),
                    "max_uses": 50, "purpose": "reviewed business-decision methods"}))
                founder_actions += 1
            mids = []
            for name in FAMILIES:
                for seed in seeds:
                    mid, spec = question(name, ex[name], seed)
                    body.apply(signed(key, body_id, "MISSION", spec))
                    mids.append(mid)
            seen_asks, asked = set(), []
            for _ in range(TICKS):
                body.tick()
                clock.advance(31)
                for m in mids:
                    if body.engine.book.missions[m].status not in ("ACHIEVED",):
                        blocked_ticks += 1
                if kind in ("baseline", "grant_and_answers"):
                    for e in body.journal.replay("decision.requested"):
                        p = e.payload
                        if p["kind"] == "CAPABILITY_ATTACH" and p["request_id"] not in seen_asks:
                            seen_asks.add(p["request_id"])
                            cid = p["authority_requested"].get("attach")
                            if cid and body.registry.state.get(cid) == "VERIFIED":
                                body.apply(signed(key, body_id, "CAPABILITY_ATTACH", {"capability_id": cid}))
                                founder_actions += 1
                                asked.append(cid)
            for r in body.ledger.by_type("receipt"):
                out = (r.payload.get("result") or {}).get("output")
                if isinstance(out, dict) and out.get("state") == "ANSWERED" and str(out.get("problem_id", "")).startswith("rehearsal:"):
                    answered_by[out["problem_id"]] = out.get("method_or_composition_selected")
            achieved = sum(body.engine.book.missions[m].status == "ACHIEVED" for m in mids)
            attached_after = sorted(c for c, s in body.registry.state.items() if s == "ATTACHED"
                                    and c in {f"cognition.{n}" for n in library.executables()})
            uses = len(list(body.journal.replay("method_grant.used")))
        return {"arm": kind, "missions": len(mids), "achieved": achieved, "founder_actions": founder_actions,
                "mission_ticks_not_achieved": blocked_ticks, "methods_left_attached_globally": attached_after,
                "grant_uses_recorded": uses, "granted": reviewed if kind != "baseline" else [], "attach_asks_answered": asked,
                "attach_asks_open": sorted({e.payload["authority_requested"].get("attach") for e in body.journal.replay(
                    "decision.requested") if e.payload["kind"] == "CAPABILITY_ATTACH"} - set(asked) - {None}), "answered_by": dict(sorted(answered_by.items())),
                "wall_seconds": round(time.monotonic() - started, 1)}


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "business"
    FAMILIES[:] = SETS[which]
    results = [arm("baseline"), arm("grant"), arm("grant_and_answers"), arm("suggested_grant")]
    out = Path(__file__).with_name(f"results-{which}.json")
    out.write_text(json.dumps(results, indent=1) + "\n")
    json.dump([{k: v for k, v in r.items() if k != "answered_by"} for r in results], sys.stdout, indent=1)
