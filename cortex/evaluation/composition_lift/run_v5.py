"""P6 v5: the first composition family whose first stage is a Layer 1 (basal) genome, on real NYC demand.

v1-v4 measured VPL on seven families; three were natural (F5 M4 demand: no lift; F6 bank arrivals: lift; F7
SNDlib backbones: lift, tied by the OR practitioner). No admitted Layer 1 or Layer 2 genome had been used in a
composition. F8 uses ``basal_kalman`` (operation ``kalman_track``, admitted DEFAULT_FOR_GEOMETRY) as the first
stage of recipe ``track_then_staff``. Nothing earlier is re-scored. The pre-registration is ``prereg-v5.json``
(checked by ``vpl_metrics.validate_preregistration``); ``--build`` refuses to write the suite without it.

F8, NATURAL: staff the next half hour of NYC Uber pickups against a standing plan. The data are every Uber pickup
in New York City from January to June 2015 (NYC TLC trip records released under FOIL, published by
FiveThirtyEight), aggregated to six disjoint streams of 48 half-hour pickup counts per day
(``cortex/evaluation/data/uber_nyc_2015_halfhour.json.gz``): Manhattan, Brooklyn, Queens excluding the airports,
Bronx, JFK Airport, LaGuardia Airport. An item is one (stream, date, decision block). The decision blocks are fixed
at 08:00, 13:00 and 18:00, decided with 30 minutes' notice: the payload holds today's counts through two blocks
before the decision block (through 07:30 for 08:00), the day's standing plan and the declared service layer.
Score the decision on the pickups that actually arrived in the decision block.

Decision layer, declared here before any held-out arm runs (a standard workforce formulation, not Uber's):

* clock: blocks are local wall-clock time in New York (the extract's ``CLOCK``). On 2015-03-08 (held out, daylight
  saving time starts) the hour 02:00-03:00 does not exist, so blocks 4-5 are MISSING, decided from the calendar
  alone (``build_uber_nyc_2015.local_block_seconds``), never zero counts: that date's payloads carry null for them
  (no tracker measurement, no EWMA ratio, left out of the cumulative ratio), and the standing plans that would
  average them (the next four Sundays) average the weeks that have the block. A decision block never falls in a
  missing hour, and no date in the data has a repeated hour (the harness refuses one);
* standing plan: per block, the mean count of the same block on the 4 previous same weekdays (that have the block);
* service: mean service time 1200 s, target wait 120 s, P(wait > target) <= 0.2, block 1800 s;
* cost: c * agents + P * max(0, required - agents), c = 1, P in {3, 10, 30} rotated by date index (days since
  2015-01-01, mod 3); ``required`` is the Erlang C requirement at the REALISED rate N_k / 1800, computed on the
  evaluation side (``solvers_b.erlang_truth``, the SciPy Poisson path, not the genome's solve);
* safe fallback: when an arm declines (abstains, or emits a malformed plan), the system staffs the standing plan by
  Erlang C; that fallback is what gets costed, and the declines are counted and reported per arm;
* tracker noise: q, r and the prior position variance per stream by maximum likelihood (grid, innovations
  likelihood of the genome's own scalar recursion) on development days only, prior mean [1, 0] and prior velocity
  variance q; computed deterministically when the suite is built and frozen with it.

Partition by date, fixed: 2015-01-01..01-28 history only (standing plans); 01-29..02-28 development (31 days, 558
items); 03-01..06-30 held out (122 days x 6 streams x 3 blocks = 2196 items).

Arms. GREG arms run through ``greg.cognition.cortex.reason`` with the genome families attached in an evaluation-only
registry view:

* ``kalman_alone``       constituent: the tracker's q* multiplier x plan, staffed by the 85% occupancy rule a
                         tracker without a queueing model would use;
* ``erlang_alone``       constituent: Erlang C at the latest observed block's rate (no view of the plan);
* ``static_composition`` / ``routed_composition``: ``track_then_staff``. The router matches geometry keys, so
                         routed is expected to equal static (reported; no routing claim);
* ``compiled``           the same request through the Competency Compiler: ``{compile: {geometry, data}}``;
* ``kalman_median_then_staff``  ablation: the tracker's median multiplier -> Erlang C (isolates the quantile).

Practitioner arms and one ablation run in process, outside GREG (staffing by ``erlang_truth``):

* ``standing_plan_then_staff``     the plan -> Erlang C (the fallback itself);
* ``cumulative_ratio_then_staff``  today-so-far / plan-so-far multiplier -> Erlang C;
* ``ewma_ratio_then_staff``        EWMA of the usable ratios (alpha per stream chosen on development) -> Erlang C;
* ``ewma_ratio_quantile_then_staff`` ablation: EWMA + z(q*) x its development residual sd -> Erlang C (a simpler
                                   tracker with a quantile: does Layer 1's tracker add anything over it?).

Verdict (frozen): F8 counts toward VPL when routed composition's total realised cost over the held-out items
(fallbacks costed) is below the best constituent's, it emits no more malformed plans than the best constituent (the
VPL definition's "no added false answers"), the one-sided exact sign test over items gives p < 0.05, and its median
latency is within the 60 s chain budget and at most 5x the best constituent's median. The best constituent is
chosen on held-out results (lowest total realised cost). A per-date sign test (streams and blocks summed per date),
per-stream results, abstention rates, practitioner and ablation comparisons and the compiled arm are reported
alongside, not as part of the rule.
"""
from __future__ import annotations

import argparse
from datetime import date as Date, datetime, timedelta, timezone
from functools import lru_cache
import gzip
import json
import math
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from cortex.evaluation.composition_lift import run as V1  # noqa: E402
from cortex.evaluation.data.build_uber_nyc_2015 import local_block_seconds  # noqa: E402

SUITE = HERE / "suite-v5.json"
MANIFEST = HERE / "freeze-v5.json"
PREREG = HERE / "prereg-v5.json"
DATA = ROOT / "cortex/evaluation/data/uber_nyc_2015_halfhour.json.gz"
CHAIN_BUDGET_S = 60.0
LATENCY_MULTIPLIER = 5.0
STAFFING = {"block_seconds": 1800.0, "mean_service_time": 1200.0, "target_wait": 120.0,
            "max_wait_probability": 0.2, "agent_cost": 1.0}
PENALTIES = (3.0, 10.0, 30.0)                  # shortage penalty per missing agent, rotated by date index
DECISION_BLOCKS = (16, 26, 36)                 # 08:00, 13:00, 18:00
LEAD = 2                                       # observed through block k - 2: decided with 30 minutes' notice
PLAN_WEEKS = 4
OCCUPANCY_RULE = 0.85
PARTITION = {"history": ("2015-01-01", "2015-01-28"), "dev": ("2015-01-29", "2015-02-28"),
             "heldout": ("2015-03-01", "2015-06-30")}
STREAM_IDS = {"Manhattan": "manhattan", "Brooklyn": "brooklyn", "Queens (excluding JFK and LaGuardia)": "queens",
              "Bronx": "bronx", "JFK Airport": "jfk", "LaGuardia Airport": "lga"}
PRIOR_MEAN = (1.0, 0.0)
Q_GRID = tuple(10 ** (x / 4) for x in range(-32, -3))            # 1e-8 .. 10^-1, quarter decades
R_GRID = tuple(10 ** (x / 4) for x in range(-20, 1))             # 1e-5 .. 1
PRIOR_VAR_GRID = tuple(10 ** (x / 4) for x in range(-16, 1))     # 1e-4 .. 1
ALPHA_GRID = tuple(i / 20 for i in range(1, 21))
CONSTITUENTS = {"F8": ("kalman_alone", "erlang_alone")}
PRACTITIONERS = {"F8": ("standing_plan_then_staff", "cumulative_ratio_then_staff", "ewma_ratio_then_staff")}
ABLATIONS = {"F8": ("ewma_ratio_quantile_then_staff", "kalman_median_then_staff")}
IN_PROCESS = ("standing_plan_then_staff", "cumulative_ratio_then_staff", "ewma_ratio_then_staff",
              "ewma_ratio_quantile_then_staff")
EVAL_ATTACH = ("cognition.basal_kalman", "cognition.queue_erlang")
ENTRY_POINTS = ("cortex/evaluation/composition_lift/run_v5.py", "greg/cognition/worker.py")
FROZEN_EXTRA = ("cortex/evaluation/data/uber_nyc_2015_halfhour.json.gz",
                "cortex/evaluation/data/build_uber_nyc_2015.py",
                "cortex/evaluation/composition_lift/prereg-v5.json", "docs/evidence/greg-mind-evidence-index.json",
                "tools/offline_test.py", "requirements-cortex.txt", "requirements-cognition.txt")
VERDICT_RULE = ("F8 (natural, continuous cost, fallbacks costed): routed total realised cost < best constituent "
                "total, routed malformed plans <= best constituent malformed plans, one-sided exact sign test over "
                "held-out items p < 0.05, routed median latency <= 60 s and <= 5x the best constituent's median. "
                "Best constituent chosen on held-out results (lowest total realised cost). Per-date sign test, "
                "per-stream results, abstention rates, practitioner, ablation and compiled-arm comparisons "
                "reported, not part of the rule. VPL = families meeting their rule.")


def code_closure() -> list[str]:
    """Every repository file the run can execute or read, hashed by the freeze (the v3 closure rule)."""
    from cortex.evaluation.closure import code_closure as closure
    return closure(ENTRY_POINTS, packages=("greg/cognition",), extra=FROZEN_EXTRA, root=ROOT)


# ------------------------------------------------------------------ registry and canonical calls
_REGISTRY = None


def registry():
    global _REGISTRY
    if _REGISTRY is None:
        from greg.cognition.cortex import registry_view
        _REGISTRY = registry_view()
        for cid in EVAL_ATTACH:
            _REGISTRY.set_state(cid, "ATTACHED")       # evaluation-only founder pin, in memory
    return _REGISTRY


def reason(params):
    from greg.cognition.cortex import reason as canonical
    return canonical(params, registry=registry())


def op(pid, operation, data):
    r = reason({"problem_id": pid[:128], "operation": operation, "data": data, "geometry": {"latency_limit": 20}})
    return r["output"] if r["abstention_state"] == "NONE" and isinstance(r.get("output"), dict) else None


def chain(item, recipe=None):
    c = {"question": "staff the next half hour against the standing plan", "payload": item["payload"],
         "max_latency_s": CHAIN_BUDGET_S}
    if recipe:
        c["recipe"] = recipe
    started = time.perf_counter()
    r = reason({"problem_id": item["item_id"], "chain": c})
    return (r["answer"] if r["state"] == "ANSWERED" else None), time.perf_counter() - started, r


def compiled(item):
    started = time.perf_counter()
    r = reason({"problem_id": item["item_id"] + "/compiled",
                "compile": {"geometry": {"consequence_class": "read_only"}, "data": item["payload"]}})
    answer = r.get("result") if r["state"] == "ANSWERED" else None
    return answer, time.perf_counter() - started, r


# ------------------------------------------------------------------ F8 data, plans and partition
@lru_cache(maxsize=1)
def uber() -> dict:
    with gzip.open(DATA, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def streams() -> list[str]:
    return list(STREAM_IDS)


def dates(part: str) -> list[str]:
    first, last = (Date.fromisoformat(d) for d in PARTITION[part])
    return [(first + timedelta(days=i)).isoformat() for i in range((last - first).days + 1)]


def date_index(day: str) -> int:
    return uber()["dates"].index(day)


def day_counts(stream: str, i: int) -> list[int | None]:
    """The date's 48 local wall-clock block counts, null for a block of a local hour that does not exist (from the
    calendar: 2015-03-08 blocks 4-5, daylight saving time starts). That block's zero is structural, not demand, so it
    is missing; a pickup recorded in it would contradict the extract's clock and is refused, as is a repeated hour."""
    day = uber()["dates"][i]
    out = []
    for b, (n, seconds) in enumerate(zip(uber()["counts"][stream][i], local_block_seconds(day))):
        if seconds == 0:
            if n:
                raise ValueError(f"{stream} {day} block {b}: pickups in a local hour that does not exist")
            out.append(None)
        elif seconds != STAFFING["block_seconds"]:
            raise ValueError(f"{day} block {b} lasts {seconds} s (a repeated local hour): not handled")
        else:
            out.append(n)
    return out


def standing_plan(stream: str, i: int) -> list[float]:
    """Per block, the mean count of that block on the 4 previous same weekdays (all inside the data); a week whose
    block does not exist (missing) is left out of that block's mean, which averages the weeks that have it."""
    if i < 7 * PLAN_WEEKS:
        raise ValueError("a standing plan needs four previous same weekdays")
    weeks = [day_counts(stream, i - 7 * w) for w in range(1, PLAN_WEEKS + 1)]
    plan = []
    for b in range(len(weeks[0])):
        have = [week[b] for week in weeks if week[b] is not None]
        if not have:
            raise ValueError(f"block {b} exists on none of the four previous same weekdays")
        plan.append(sum(have) / len(have))
    return plan


def _floats(counts: list) -> list:
    return [None if n is None else float(n) for n in counts]


def requirement(arrivals: float) -> int:
    """Evaluation-side Erlang C requirement at a rate of ``arrivals`` per block (SciPy Poisson path)."""
    return _erlang(round(float(arrivals), 9))


@lru_cache(maxsize=None)
def _erlang(arrivals: float) -> int:
    if arrivals <= 0:
        return 0
    from greg.cognition.genomes.solvers_b import erlang_truth
    return erlang_truth({"arrival_rate": arrivals / STAFFING["block_seconds"],
                         "mean_service_time": STAFFING["mean_service_time"], "target_wait": STAFFING["target_wait"],
                         "max_wait_probability": STAFFING["max_wait_probability"]})


# ------------------------------------------------------------------ development calibration (frozen in the suite)
def _ratio_days(stream: str, part: str = "dev") -> list[list]:
    from greg.cognition.composition import plan_ratios
    out = []
    for day in dates(part):
        i = date_index(day)
        out.append(plan_ratios(_floats(day_counts(stream, i)), standing_plan(stream, i)))
    return out


def kalman_loglik_grid(series: list[list], q, r, prior_var, final_state=False):
    """Innovations log-likelihood of the genome's scalar constant-velocity recursion (dt = 1, prior mean [1, 0],
    prior variance [prior_var, q]) summed over days, for arrays of (q, r, prior_var). ``final_state`` also returns
    the last day's final position and position variance (what ``kalman_track`` reports for that series)."""
    import numpy as np
    total = np.zeros_like(q)
    x = p11 = None
    for zs in series:
        x, v = np.full_like(q, PRIOR_MEAN[0]), np.full_like(q, PRIOR_MEAN[1])
        p11, p12, p22 = prior_var.copy(), np.zeros_like(q), q.copy()
        for k, z in enumerate(zs):
            if k > 0:
                x = x + v
                p11, p12, p22 = p11 + 2 * p12 + p22 + q / 4, p12 + p22 + q / 2, p22 + q
            if z is None:
                continue
            s = p11 + r
            nu = z - x
            total = total - 0.5 * (np.log(2 * math.pi * s) + nu * nu / s)
            k1, k2 = p11 / s, p12 / s
            x, v = x + k1 * nu, v + k2 * nu
            p11, p12, p22 = (1 - k1) * p11, (1 - k1) * p12, p22 - k2 * p12
    return (total, x, p11) if final_state else total


def kalman_mle(stream: str) -> dict:
    import numpy as np
    q, r, pv = (a.ravel() for a in np.meshgrid(np.array(Q_GRID), np.array(R_GRID), np.array(PRIOR_VAR_GRID),
                                                indexing="ij"))
    ll = kalman_loglik_grid(_ratio_days(stream), q, r, pv)
    best = int(np.argmax(ll))
    found = {"q": float(q[best]), "r": float(r[best]), "prior_var": float(pv[best])}
    edges = [k for k, grid in (("q", Q_GRID), ("r", R_GRID), ("prior_var", PRIOR_VAR_GRID))
             if found[k] in (grid[0], grid[-1])]
    return {**found, "loglik": round(float(ll[best]), 6), "at_grid_edge": edges}


def tracker(fit: dict) -> dict:
    return {"q": fit["q"], "r": fit["r"], "prior": {"mean": list(PRIOR_MEAN), "var": [fit["prior_var"], fit["q"]]}}


def ewma(zs: list, alpha: float) -> float:
    m = 1.0
    for z in zs:
        if z is not None:
            m = alpha * z + (1 - alpha) * m
    return m


def ewma_fit(stream: str) -> dict:
    """Alpha minimising the squared error of the EWMA's lead-2 ratio prediction over development days (every
    block with a usable ratio), and the residual sd at that alpha (for the quantile ablation)."""
    days = _ratio_days(stream)
    best = None
    for alpha in ALPHA_GRID:
        errors = [zs[k] - ewma(zs[:k - LEAD + 1], alpha) for zs in days for k in range(LEAD, len(zs))
                  if zs[k] is not None]
        sse = sum(e * e for e in errors)
        if best is None or sse < best[0]:
            best = (sse, alpha, len(errors))
    return {"alpha": best[1], "sigma": math.sqrt(best[0] / best[2]), "residuals": best[2]}


def calibrate() -> dict:
    return {s: {"kalman": kalman_mle(s), "ewma": ewma_fit(s)} for s in streams()}


# ------------------------------------------------------------------ items and scoring
def f8(stream: str, day: str, block: int, calibration: dict) -> dict:
    from greg.cognition.composition import staffing_quantile
    if block not in DECISION_BLOCKS:
        raise ValueError("not a declared decision block")
    i = date_index(day)
    plan = standing_plan(stream, i)
    counts = day_counts(stream, i)
    penalty = PENALTIES[i % len(PENALTIES)]
    staffing = {**STAFFING, "shortage_penalty": penalty}
    actual = counts[block]
    if actual is None:
        raise ValueError(f"{day}: decision block {block} is in a local hour that does not exist")
    required = requirement(actual)
    return {"item_id": f"F8-{STREAM_IDS[stream]}-{day}-{block // 2:02d}{30 * (block % 2):02d}", "family": "F8",
            "stream": stream, "date": day, "date_index": i, "block": block,
            "payload": {"observed_today": counts[:block - LEAD + 1],
                        "standing_plan": {"blocks": plan, "decision_block": block},
                        "staffing": staffing, "tracker": tracker(calibration[stream]["kalman"])},
            "practitioner": dict(calibration[stream]["ewma"]),
            "fallback": {"agents": requirement(plan[block]), "rule": "standing plan staffed by Erlang C"},
            "truth": {"actual": actual, "required": required, "shortage_penalty": penalty,
                      "quantile_level": staffing_quantile(staffing), "hindsight_cost": STAFFING["agent_cost"] * required}}


def items(part: str, calibration: dict) -> list[dict]:
    if part not in ("dev", "heldout"):
        raise ValueError("items are development or held out")
    return [{**f8(s, d, b, calibration), "partition": part} for d in dates(part) for s in streams()
            for b in DECISION_BLOCKS]


def f8_cost(item, answer):
    """(realised cost, outcome, agents staffed): outcome is decided, fallback (the arm declined: the standing plan is
    staffed by Erlang C) or wrong (a malformed plan: the fallback is staffed and the plan is counted as false)."""
    agents = answer.get("agents") if isinstance(answer, dict) else None
    if agents is None:
        outcome, staffed = "fallback", item["fallback"]["agents"]
    elif type(agents) is not int or not 0 <= agents <= 40_000:
        outcome, staffed = "wrong", item["fallback"]["agents"]
    else:
        outcome, staffed = "decided", agents
    truth = item["truth"]
    cost = STAFFING["agent_cost"] * staffed + truth["shortage_penalty"] * max(0, truth["required"] - staffed)
    return cost, outcome, staffed


# ------------------------------------------------------------------ arms
def _rate(planned: float, multiplier: float) -> float | None:
    from greg.cognition.composition import TRACK_FLOOR_MULTIPLIER
    rate = planned * max(multiplier, TRACK_FLOOR_MULTIPLIER) / STAFFING["block_seconds"]
    return rate if math.isfinite(rate) and rate > 0 else None


def _erlang_op(pid, rate):
    out = op(pid, "erlang_c_staffing", {"arrival_rate": rate, "mean_service_time": STAFFING["mean_service_time"],
                                        "target_wait": STAFFING["target_wait"],
                                        "max_wait_probability": STAFFING["max_wait_probability"]})
    return None if out is None else out["agents"]


def _tracked(pid, payload):
    """The tracker's stage exactly as the recipe runs it: (kalman output or None, data, decision-block plan)."""
    from greg.cognition.composition import TRACK_MIN_MEASUREMENTS, track_measurements
    data, usable, planned = track_measurements(payload)
    if usable < TRACK_MIN_MEASUREMENTS:
        return None, data, planned, 0
    return op(pid, "kalman_track", data), data, planned, 1


def run_arm(item, arm, static_recipe):
    from greg.cognition.composition import tracked_multiplier
    started, stages, state, answer = time.perf_counter(), 0, "constituent", None
    pid, payload = item["item_id"], item["payload"]
    level = item["truth"]["quantile_level"]
    if arm in ("static_composition", "routed_composition"):
        answer, seconds, r = chain(item, static_recipe if arm == "static_composition" else None)
        stages, state = len(r.get("stages", [])), r["state"]
    elif arm == "compiled":
        answer, seconds, r = compiled(item)
        stages, state = (r.get("resource_use") or {}).get("stages"), r["state"]
    else:
        planned = payload["standing_plan"]["blocks"][payload["standing_plan"]["decision_block"]]
        if arm in ("kalman_alone", "kalman_median_then_staff"):
            out, data, planned, stages = _tracked(f"{pid}/{arm}/track", payload)
            if out is not None:
                m = tracked_multiplier(out, data["r"], level) if arm == "kalman_alone" else out["positions"][-1]
                rate = _rate(planned, m)
                if rate is not None and arm == "kalman_alone":
                    answer = {"agents": math.ceil(rate * STAFFING["mean_service_time"] / OCCUPANCY_RULE - 1e-12)}
                elif rate is not None:
                    answer = {"agents": _erlang_op(f"{pid}/{arm}/staff", rate)}
                    stages += 1
        elif arm == "erlang_alone":
            latest = next((n for n in reversed(payload["observed_today"]) if n is not None), None)
            if latest is not None:                 # the latest block observed (k - 2 is never a missing block)
                answer = {"agents": _erlang_op(f"{pid}/{arm}", latest / STAFFING["block_seconds"])}
                stages = 1
        elif arm in IN_PROCESS:
            from greg.cognition.composition import plan_ratios
            observed = payload["observed_today"]
            blocks = payload["standing_plan"]["blocks"]
            if arm == "standing_plan_then_staff":
                m = 1.0
            elif arm == "cumulative_ratio_then_staff":
                seen = [(n, b) for n, b in zip(observed, blocks) if n is not None]   # missing blocks left out
                denominator = sum(b for _, b in seen)
                m = sum(n for n, _ in seen) / denominator if denominator > 0 else 1.0
            else:
                m = ewma(plan_ratios(_floats(observed), blocks), item["practitioner"]["alpha"])
                if arm == "ewma_ratio_quantile_then_staff":
                    from statistics import NormalDist
                    m += NormalDist().inv_cdf(level) * item["practitioner"]["sigma"]
            if arm == "standing_plan_then_staff":
                arrivals = planned
            else:
                rate = _rate(planned, m)
                arrivals = 0.0 if rate is None else rate * STAFFING["block_seconds"]
            answer = {"agents": requirement(arrivals)}
            state = "practitioner_in_process"
        else:
            raise ValueError(f"unknown arm {arm}")
        if isinstance(answer, dict) and answer.get("agents") is None:
            answer = None
        seconds = time.perf_counter() - started
    cost, outcome, staffed = f8_cost(item, answer)
    return {"result": outcome, "cost": cost, "agents": staffed, "seconds": round(seconds, 4), "stages": stages,
            "state": state, "answer": answer}


def arms_for(family):
    return (list(CONSTITUENTS[family]) + list(PRACTITIONERS[family]) + list(ABLATIONS[family])
            + ["static_composition", "routed_composition", "compiled"])


# ------------------------------------------------------------------ verdict
def _paired(rows, a, b):
    wins = sum(1 for r in rows if r["arms"][a]["cost"] < r["arms"][b]["cost"] - 1e-9)
    losses = sum(1 for r in rows if r["arms"][b]["cost"] < r["arms"][a]["cost"] - 1e-9)
    return wins, losses, V1.sign_test(wins, losses)


def _grouped(rows, key, a, b):
    groups = {}
    for r in rows:
        g = groups.setdefault(r[key], [0.0, 0.0])
        g[0] += r["arms"][a]["cost"]
        g[1] += r["arms"][b]["cost"]
    wins = sum(1 for x, y in groups.values() if x < y - 1e-9)
    losses = sum(1 for x, y in groups.values() if y < x - 1e-9)
    return {"groups": len(groups), "wins": wins, "losses": losses,
            "p_one_sided": round(V1.sign_test(wins, losses), 6)}


def _wilcoxon(rows, a, b):
    diffs = [r["arms"][a]["cost"] - r["arms"][b]["cost"] for r in rows]
    if not any(abs(d) > 1e-9 for d in diffs):
        return None
    from scipy.stats import wilcoxon
    return float(wilcoxon(diffs, alternative="less", zero_method="wilcox").pvalue)


def _coverage(rows, arm):
    by_q = {}
    for r in rows:
        by_q.setdefault(f"{r['truth']['quantile_level']:g}", []).append(
            int(r["arms"][arm]["agents"] >= r["truth"]["required"]))
    return {q: {"covered": round(statistics.fmean(v), 4), "items": len(v)} for q, v in sorted(by_q.items())}


def summarize(rows) -> dict:
    out, vpl, total = {}, 0, 0
    for family in CONSTITUENTS:
        fr = [r for r in rows if r["family"] == family]
        if not fr:
            continue
        total += 1
        arms = arms_for(family)
        totals = {a: round(sum(r["arms"][a]["cost"] for r in fr), 3) for a in arms}
        outcomes = {a: {k: sum(r["arms"][a]["result"] == k for r in fr) for k in ("decided", "fallback", "wrong")}
                    for a in arms}
        median = {a: round(statistics.median(r["arms"][a]["seconds"] for r in fr), 4) for a in arms}
        best = min(CONSTITUENTS[family], key=lambda a: totals[a])
        wins, losses, p = _paired(fr, "routed_composition", best)
        latency_ok = (median["routed_composition"] <= CHAIN_BUDGET_S
                      and median["routed_composition"] <= LATENCY_MULTIPLIER * median[best])
        lift = (totals["routed_composition"] < totals[best]
                and outcomes["routed_composition"]["wrong"] <= outcomes[best]["wrong"]
                and p < 0.05 and latency_ok)
        versus = {}
        for other in arms:
            if other != "routed_composition":
                w, l, q = _paired(fr, "routed_composition", other)
                versus[other] = {"wins": w, "losses": l, "sign_test_p_one_sided": round(q, 6),
                                 "cost_reduction": round(1 - totals["routed_composition"] / totals[other], 4)
                                 if totals[other] else None}
        per_stream = {}
        for s in sorted({r["stream"] for r in fr}):
            sr = [r for r in fr if r["stream"] == s]
            w, l, q = _paired(sr, "routed_composition", best)
            per_stream[s] = {"items": len(sr), "total": {a: round(sum(r["arms"][a]["cost"] for r in sr), 3)
                                                          for a in ("routed_composition", best,
                                                                    "ewma_ratio_quantile_then_staff",
                                                                    "standing_plan_then_staff")},
                             "routed_vs_best": {"wins": w, "losses": l, "p_one_sided": round(q, 6)},
                             "routed_fallback": sum(r["arms"]["routed_composition"]["result"] == "fallback"
                                                    for r in sr)}
        states = [r["arms"]["routed_composition"]["state"] for r in fr]
        out[family] = {"n": len(fr), "total_realised_cost": totals, "outcomes": outcomes,
                       "abstention_rate": {a: round(outcomes[a]["fallback"] / len(fr), 4) for a in arms},
                       "hindsight_optimal_cost": round(sum(r["truth"]["hindsight_cost"] for r in fr), 3),
                       "best_constituent": best, "routed_wins": wins, "routed_losses": losses,
                       "sign_test_p_one_sided": round(p, 6),
                       "wilcoxon_p_one_sided_vs_best": _wilcoxon(fr, "routed_composition", best),
                       "per_date_sign_test_vs_best": _grouped(fr, "date", "routed_composition", best),
                       "per_stream": per_stream, "versus": versus, "median_seconds": median,
                       "latency_rule": {"multiplier": LATENCY_MULTIPLIER, "budget_s": CHAIN_BUDGET_S,
                                        "ratio": round(median["routed_composition"] / median[best], 3)
                                        if median[best] else None, "met": latency_ok},
                       "coverage": {a: _coverage(fr, a) for a in ("routed_composition", best,
                                                                  "ewma_ratio_quantile_then_staff")},
                       "median_stages": {a: statistics.median(r["arms"][a]["stages"] or 0 for r in fr) for a in arms},
                       "translation_failure_rate": states.count("TRANSLATION_FAILED") / len(fr),
                       "composition_failure_rate": sum(s != "ANSWERED" for s in states) / len(fr),
                       "model_calls": 0, "money_usd": 0.0, "lift": lift}
        vpl += int(lift)
    out["VPL_v5"] = {"families_with_lift": vpl, "families": total, "rule": VERDICT_RULE}
    return out


# ------------------------------------------------------------------ suite / freeze / run
def build() -> dict:
    calibration = calibrate()
    return {"schema": "greg-composition-lift-suite/5", "calibration": calibration,
            "items": items("dev", calibration) + items("heldout", calibration)}


def inputs() -> dict:
    """JSON-normalised so the comparison with the stored freeze is exact (tuples become lists)."""
    return json.loads(json.dumps({
        "suite": V1._sha(SUITE), "prereg": V1._sha(PREREG),
        "code": {p: V1._sha(ROOT / p) for p in code_closure()}, "verdict_rule": VERDICT_RULE,
        "dependencies": __import__("cortex.evaluation.closure", fromlist=["dependency_versions"]).dependency_versions(),
        "chain_budget_s": CHAIN_BUDGET_S, "latency_multiplier": LATENCY_MULTIPLIER, "staffing": STAFFING,
        "penalties": PENALTIES, "decision_blocks": DECISION_BLOCKS, "lead": LEAD, "plan_weeks": PLAN_WEEKS,
        "occupancy_rule": OCCUPANCY_RULE, "partition": PARTITION, "prior_mean": PRIOR_MEAN,
        "grids": {"q": Q_GRID, "r": R_GRID, "prior_var": PRIOR_VAR_GRID, "alpha": ALPHA_GRID},
        "constituents": CONSTITUENTS, "practitioners": PRACTITIONERS, "ablations": ABLATIONS,
        "evaluation_attach": list(EVAL_ATTACH)}))


def static_choice(dev) -> tuple[str, dict]:
    """The recipe with the lowest total development cost (fallbacks costed) among recipes whose geometry fits every
    development item; a recipe that cannot run on an item (NO_RECIPE or a refused payload) is not a baseline."""
    from greg.cognition.composition import RECIPES
    from greg.cognition.contracts import CognitionError
    totals = {}
    for name in sorted(RECIPES):
        cost = 0.0
        for item in dev:
            try:
                answer, _, r = chain(item, name)
            except CognitionError:
                cost = None
                break
            if r["state"] == "NO_RECIPE":
                cost = None
                break
            cost += f8_cost(item, answer)[0]
        totals[name] = cost
    eligible = [n for n in sorted(totals) if totals[n] is not None]
    if not eligible:
        raise SystemExit("no recipe fits every development item: there is no static baseline")
    return min(eligible, key=lambda n: totals[n]), totals


def _run_item(index, item, static_recipe):
    arms = arms_for(item["family"])
    order = arms[index % len(arms):] + arms[:index % len(arms)]
    row = {"item_id": item["item_id"], "family": item["family"], "stream": item["stream"], "date": item["date"],
           "block": item["block"], "truth": item["truth"], "fallback": item["fallback"], "arms": {}}
    for arm in order:
        row["arms"][arm] = run_arm(item, arm, static_recipe)
    row["arms"] = {a: row["arms"][a] for a in arms}
    print(json.dumps({"i": index, "item": item["item_id"], "required": item["truth"]["required"],
                      "cost": {a: row["arms"][a]["cost"] for a in arms}}), flush=True)
    return row


def _pin(cores, counter):
    with counter.get_lock():
        slot = counter.value
        counter.value += 1
    os.sched_setaffinity(0, {cores[slot % len(cores)]})


def _job(job):
    return _run_item(*job)


def run_items(items_, static_recipe, workers=1, cores=None):
    """Each item runs whole on one process; with ``workers`` > 1 the items are spread over that many processes,
    each pinned to its own core, so per-item latency is still one core's. Rows come back in suite order."""
    jobs = [(index, item, static_recipe) for index, item in enumerate(items_)]
    if workers <= 1:
        return [_job(j) for j in jobs]
    import multiprocessing
    cores = sorted(cores or os.sched_getaffinity(0))
    if len(cores) < workers:
        raise SystemExit(f"{workers} workers need {workers} cores; {len(cores)} available")
    context = multiprocessing.get_context("fork")
    counter = context.Value("i", 0)
    with context.Pool(workers, initializer=_pin, initargs=(cores[:workers], counter), maxtasksperchild=None) as pool:
        return list(pool.imap(_job, jobs, chunksize=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--dev", type=Path, help="builders only: run the development items, never the held-out items "
                                             "(built in memory from the data; the suite is not needed or read)")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--workers", type=int, default=1, help="processes, one pinned core each (latency stays per core)")
    ap.add_argument("--cores", type=str, help="comma-separated cores for the workers (default: all available)")
    args = ap.parse_args()
    cores = [int(c) for c in args.cores.split(",")] if args.cores else None
    if args.build:
        if SUITE.exists():
            raise SystemExit("refusing to overwrite the suite; create a new version")
        from cortex.evaluation.composition_lift.vpl_metrics import validate_preregistration
        problems = validate_preregistration(json.loads(PREREG.read_text()))
        if problems:
            raise SystemExit(f"the pre-registration is incomplete: {problems}")
        SUITE.write_text(json.dumps(build()) + "\n")
        return
    if args.freeze:
        if MANIFEST.exists():
            raise SystemExit("refusing to overwrite an existing freeze; create a new version")
        MANIFEST.write_text(json.dumps({"frozen_at": datetime.now(timezone.utc).isoformat(), "inputs": inputs()},
                                       indent=2) + "\n")
        return
    if args.dev:
        calibration = calibrate()
        dev = items("dev", calibration)
        static_recipe, totals = static_choice(dev)
        rows = run_items(dev, static_recipe, args.workers, cores)
        args.dev.write_text(json.dumps({"partition": "dev", "calibration": calibration, "static_recipe": static_recipe,
                                        "recipe_dev_cost": totals, "rows": rows, "summary": summarize(rows)},
                                       indent=1) + "\n")
        print(json.dumps(summarize(rows), indent=1))
        return
    if json.loads(MANIFEST.read_text())["inputs"] != inputs():
        raise SystemExit("FROZEN_INPUT_CHANGED: results cannot be reported")
    if not args.out:
        raise SystemExit("--out required")
    suite = json.loads(SUITE.read_text())
    dev = [i for i in suite["items"] if i["partition"] == "dev"]
    heldout = [i for i in suite["items"] if i["partition"] == "heldout"]
    static_recipe, totals = static_choice(dev)
    print(json.dumps({"recipe_dev_cost": totals, "static_recipe": static_recipe}), flush=True)
    rows = run_items(heldout, static_recipe, args.workers, cores)
    report = {"schema": "greg-composition-lift-results/5", "manifest_sha256": V1._sha(MANIFEST),
              "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "platform": platform.platform(), "python": sys.version.split()[0], "workers": args.workers,
              "development": {"recipe_dev_cost": totals, "static_recipe": static_recipe},
              "calibration": suite["calibration"], "heldout": rows, "summary": summarize(rows),
              "limits": ["real pickups and real outcomes; the service time, waiting target, cost weights, decision "
                         "blocks and notice are a declared decision layer, not Uber's dispatch",
                         "blocks are local wall-clock time: 2015-03-08 02:00-03:00 does not exist, and its two blocks "
                         "are missing by the calendar (no measurement; left out of the next four Sundays' plans)",
                         "the requirement is the Erlang C model's at the realised rate: the outcome is real, the "
                         "queueing model is an assumption shared by every arm",
                         "items share dates and streams; the item sign test treats them as independent, so a "
                         "per-date sign test is reported alongside",
                         "one city, one half-year (2015); streams are boroughs and airports of one platform",
                         "practitioner arms run in process, outside GREG's isolated workers; their latency is not "
                         "comparable with the GREG arms'",
                         "one container; latency is this machine's"]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({"development": report["development"], "summary": report["summary"]}, indent=1))


if __name__ == "__main__":
    main()
