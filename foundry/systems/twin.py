"""#42 Digital twin: a shadow model of GREG's operations, compared with reality on every outcome.

For each capability the twin predicts, before reality answers, the probability
the next appraisal is VERIFIED and the cost of the next action. Each observed
outcome records the prediction error (Brier score, absolute cost error) and
recalibrates the model (discounted Beta counts, exponentially weighted cost).
When the rolling Brier score over the recent window exceeds the long-run error
by a margin, the twin raises a drift alert and recalibrates hard: it forgets
the stale regime and refits to the recent window. State persists, so the twin
keeps learning across restarts. It runs in shadow: it predicts and reports,
and never acts. Twins/twin.py (amendment rehearsal) is unchanged.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

WINDOW, MARGIN, DISCOUNT, COST_ALPHA = 8, 0.2, 0.97, 0.3


def _load(root: Path) -> dict:
    p = Path(root) / "twin.json"
    return json.loads(p.read_text()) if p.exists() else {"capabilities": {}, "alerts": []}


def _save(root: Path, state: dict) -> None:
    Path(root).mkdir(parents=True, exist_ok=True)
    tmp = Path(root) / "twin.tmp"
    tmp.write_text(json.dumps(state, sort_keys=True))
    tmp.replace(Path(root) / "twin.json")


def _cap(state: dict, capability: str) -> dict:
    return state["capabilities"].setdefault(capability, {"a": 1.0, "b": 1.0, "cost": None, "errors": [],
                                                         "history": [], "n": 0, "cooldown": 0})


def predict(root: Path, capability: str) -> dict:
    c = _cap(_load(root), capability)
    return {"capability": capability, "p_verified": round(c["a"] / (c["a"] + c["b"]), 4),
            "expected_cost_usd": None if c["cost"] is None else round(c["cost"], 4), "observations": c["n"]}


def _step(c: dict, *, verified: bool, cost_usd: float, at: str, adaptive: bool) -> tuple[float, float | None, dict | None]:
    p = c["a"] / (c["a"] + c["b"])
    brier = (p - (1.0 if verified else 0.0)) ** 2
    cost_error = None if c["cost"] is None else abs(c["cost"] - cost_usd)
    c["errors"].append(brier)
    c["history"].append(1 if verified else 0)
    c["n"] += 1
    decay = DISCOUNT if adaptive else 1.0
    c["a"], c["b"] = decay * c["a"] + verified, decay * c["b"] + (not verified)
    c["cost"] = cost_usd if c["cost"] is None else (1 - COST_ALPHA) * c["cost"] + COST_ALPHA * cost_usd
    c["cooldown"] = max(0, c.get("cooldown", 0) - 1)
    alert = None
    if adaptive and c["n"] >= 2 * WINDOW and not c["cooldown"]:
        recent = sum(c["errors"][-WINDOW:]) / WINDOW
        longrun = sum(c["errors"][:-WINDOW]) / len(c["errors"][:-WINDOW])
        if recent > longrun + MARGIN:
            wins = sum(c["history"][-WINDOW:])
            c["a"], c["b"] = 1.0 + wins, 1.0 + WINDOW - wins     # forget the stale regime, refit to the recent one
            c["cooldown"] = WINDOW                               # one alert per regime change, not per observation
            alert = {"at": at, "recent_brier": round(recent, 4), "longrun_brier": round(longrun, 4),
                     "refit_p_verified": round(c["a"] / (c["a"] + c["b"]), 4)}
    return brier, cost_error, alert


def observe(root: Path, capability: str, *, verified: bool, cost_usd: float, at: str, adaptive: bool = True) -> dict:
    """Score the standing prediction against reality, then recalibrate."""
    state = _load(root)
    brier, cost_error, alert = _step(_cap(state, capability), verified=verified, cost_usd=cost_usd, at=at,
                                     adaptive=adaptive)
    if alert:
        alert = {"capability": capability, **alert}
        state["alerts"].append(alert)
    _save(root, state)
    return {"brier": round(brier, 4), "cost_error": None if cost_error is None else round(cost_error, 4),
            "drift_alert": alert}


def from_greg(events: list[dict]) -> list[dict]:
    """(capability, verified, cost, at) per appraised closure, in journal order."""
    cost: dict[str, float] = {}
    last_cap: dict[str, str] = {}
    out = []
    for e in sorted(events, key=lambda e: (e["at"], e["event_id"])):
        kind, p = e["type"].removeprefix("greg."), e["payload"]
        if kind == "mission.action" and p.get("status") == "DONE":
            last_cap[p["mission_id"]] = p.get("capability")
            cost[p["mission_id"]] = float(p.get("cost_usd") or 0.0)
        elif kind == "mission.appraised" and p.get("mission_id") in last_cap:
            out.append({"capability": last_cap[p["mission_id"]], "verified": p.get("verdict") == "VERIFIED",
                        "cost_usd": cost.get(p["mission_id"], 0.0), "at": e["at"]})
    return out


def replay(root: Path, events: list[dict]) -> dict:
    results = [observe(root, o["capability"], verified=o["verified"], cost_usd=o["cost_usd"], at=o["at"])
               for o in from_greg(events)]
    return {"observed": len(results), "alerts": [r["drift_alert"] for r in results if r["drift_alert"]]}


QUERY_OPS = {"predict": lambda a, r: predict(r, a["capability"]),
             "alerts": lambda a, r: {"alerts": _load(r)["alerts"]}}
APPLY_OPS = {"observe": lambda a, r: observe(r, a["capability"], verified=bool(a["verified"]),
                                             cost_usd=float(a["cost_usd"]), at=a["at"]),
             "replay_greg": lambda a, r: replay(r, a["events"])}


def evaluate(p_before: float, p_after: float, *, seeds: int = 100, n: int = 90, change: int = 30) -> dict:
    """Mean post-change Brier of the recalibrating twin vs a static one over seeded streams."""
    fresh = lambda: {"a": 1.0, "b": 1.0, "cost": None, "errors": [], "history": [], "n": 0, "cooldown": 0}
    total = {"adaptive": 0.0, "static": 0.0}
    for seed in range(seeds):
        rng = random.Random(seed)
        stream = [rng.random() < (p_before if i < change else p_after) for i in range(n)]
        for name, adaptive in (("adaptive", True), ("static", False)):
            c = fresh()
            errs = [_step(c, verified=ok, cost_usd=0.0, at="-", adaptive=adaptive)[0] for ok in stream]
            total[name] += sum(errs[change:]) / (n - change) / seeds
    return {k: round(v, 4) for k, v in total.items()}


def exercise(root) -> dict:
    root = Path(root)
    rng = random.Random(42)
    alerts = []
    for i in range(60):
        ok = rng.random() < (0.9 if i < 30 else 0.3)
        r = observe(root, "wmi.assess", verified=ok, cost_usd=0.02 if i < 30 else 0.05,
                    at=f"2026-09-{1 + i // 3:02d}T{(i % 3) * 8:02d}:00:00Z")
        if r["drift_alert"]:
            alerts.append({"index": i, **r["drift_alert"]})
    drift, stationary = evaluate(0.9, 0.3), evaluate(0.8, 0.8)
    return {"regime_change_at": 30, "drift_alerts": alerts, "prediction_after_restart": predict(root, "wmi.assess"),
            "brier_after_drift": drift, "brier_without_drift": stationary,
            "recalibration_helps_under_drift": drift["adaptive"] < drift["static"],
            "cost_without_drift": round(stationary["adaptive"] - stationary["static"], 4)}
