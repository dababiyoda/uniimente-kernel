"""#34 Path attribution: which content sequences produced subscribers and customers, measured from observed journeys.

Input: the observed step log of the #50 engine (or any journey log with the same
shape: session, kind, node, at). Nothing here is assumed from platform claims;
every number is a count over recorded journeys.

  paths        each session's ordered consumed nodes and how it ended
               (converted = join or buy; left; open)
  conversion   measured conversion by exact path and by node, with Wilson lower
               bounds so a path seen twice is not reported as "100%"
  removal      Markov removal effect (Anderl et al.): a first-order chain over
               observed transitions; a node's attribution is the share of total
               conversion probability lost when it is removed. Attribution sums to
               the measured conversion, never more.
  platform     when steps carry a ``source`` (platform, referrer), the same measures
               are reported per source, so the institution can see which platform
               feeds which depth and which actually ends in owned relationships

The report names its sample sizes; where the sample is small it says so rather
than smoothing a story out of noise.
"""
from __future__ import annotations

import math
from collections import defaultdict

CONVERTING = ("join", "buy")
MIN_SAMPLE = 5


def journeys(steps: list[dict]) -> list[dict]:
    by = defaultdict(list)
    for s in sorted(steps, key=lambda s: (s["session"], s["at"])):
        by[s["session"]].append(s)
    out = []
    for session, rows in by.items():
        path = [r["node"] for r in rows if r["kind"] == "consume"]
        end = next((r["kind"] for r in rows if r["kind"] in CONVERTING + ("leave",)), "open")
        out.append({"session": session, "path": path, "end": end, "converted": end in CONVERTING,
                    "source": rows[0].get("source", "direct") if rows else "direct"})
    return out


def wilson_lower(k: int, n: int, z: float = 1.96) -> float:
    if n == 0:
        return 0.0
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - spread) / denom)


def conversion_by_path(js: list[dict]) -> list[dict]:
    agg = defaultdict(lambda: [0, 0])
    for j in js:
        agg[tuple(j["path"])][0] += j["converted"]
        agg[tuple(j["path"])][1] += 1
    rows = [{"path": list(p), "sessions": n, "converted": k, "rate": round(k / n, 4), "rate_lower_bound": round(wilson_lower(k, n), 4),
             "sample": "small" if n < MIN_SAMPLE else "ok"} for p, (k, n) in agg.items()]
    return sorted(rows, key=lambda r: (-r["rate_lower_bound"], -r["sessions"], r["path"]))


def _chain(js: list[dict]) -> tuple[dict, set]:
    """First-order Markov chain over observed transitions: START -> nodes -> CONVERT | NULL."""
    counts = defaultdict(lambda: defaultdict(int))
    nodes = set()
    for j in js:
        prev = "START"
        for n in j["path"]:
            counts[prev][n] += 1
            nodes.add(n)
            prev = n
        counts[prev]["CONVERT" if j["converted"] else "NULL"] += 1
    probs = {s: {t: c / sum(ts.values()) for t, c in ts.items()} for s, ts in counts.items()}
    return probs, nodes


def _conversion_probability(probs: dict, removed: str | None = None, iterations: int = 200) -> float:
    """P(reach CONVERT from START) by value iteration; a removed node routes its mass to NULL."""
    value = {s: 0.0 for s in probs}
    value["CONVERT"], value["NULL"] = 1.0, 0.0
    for _ in range(iterations):
        new = dict(value)
        for s, ts in probs.items():
            if s == removed:
                new[s] = 0.0
                continue
            new[s] = sum(p * (0.0 if t == removed else value.get(t, 0.0)) for t, p in ts.items())
        if max(abs(new[k] - value[k]) for k in value) < 1e-12:
            value = new
            break
        value = new
    return value.get("START", 0.0)


def removal_effects(js: list[dict]) -> dict:
    probs, nodes = _chain(js)
    if not nodes:
        return {"total_conversion_probability": 0.0, "attribution": {}}
    base = _conversion_probability(probs)
    effects = {n: max(0.0, base - _conversion_probability(probs, removed=n)) for n in sorted(nodes)}
    total = sum(effects.values())
    conversions = sum(j["converted"] for j in js)
    attribution = {n: round(conversions * e / total, 3) if total else 0.0 for n, e in effects.items()}
    return {"total_conversion_probability": round(base, 4), "removal_effect": {n: round(e, 4) for n, e in effects.items()},
            "attributed_conversions": attribution, "sums_to_measured_conversions": round(sum(attribution.values()), 3)}


def by_source(js: list[dict]) -> dict:
    out = defaultdict(lambda: {"sessions": 0, "converted": 0, "mean_depth": 0.0})
    for j in js:
        o = out[j["source"]]
        o["sessions"] += 1
        o["converted"] += j["converted"]
        o["mean_depth"] += len(j["path"])
    for o in out.values():
        o["mean_depth"] = round(o["mean_depth"] / o["sessions"], 2)
        o["rate_lower_bound"] = round(wilson_lower(o["converted"], o["sessions"]), 4)
    return dict(sorted(out.items()))


def report(steps: list[dict]) -> dict:
    js = journeys(steps)
    return {"sessions": len(js), "conversions": sum(j["converted"] for j in js), "paths": conversion_by_path(js),
            "removal": removal_effects(js), "by_source": by_source(js)}


def _from_territory(args, root):
    """Measure the #50 engine's own observations (its store is the sibling system-50 directory)."""
    import json
    from pathlib import Path
    p = Path(root).parent / "system-50" / "territory.json"
    steps = json.loads(p.read_text())["steps"] if p.exists() else []
    return report(steps)


QUERY_OPS = {"report": lambda a, r: report(a["steps"]), "report_territory": _from_territory}
APPLY_OPS: dict = {}


def sample_steps() -> list[dict]:
    steps = []
    def visit(session, source, path, end):
        prev = None
        for i, n in enumerate(path):
            steps.append({"session": session, "kind": "consume", "node": n, "from": prev, "at": f"2026-10-13T12:{i:02d}:00Z",
                          "source": source})
            prev = n
        steps.append({"session": session, "kind": end, "node": path[-1], "from": prev, "at": "2026-10-13T12:59:00Z", "source": source})
    for i in range(8):
        visit(f"a{i}", "owned-newsletter", ["why-proof", "pod-basics", "audit-kit", "offer"], "buy" if i < 6 else "leave")
    for i in range(10):
        visit(f"b{i}", "platform-x", ["why-proof", "disputes"], "leave" if i < 9 else "join")
    for i in range(4):
        visit(f"c{i}", "platform-x", ["why-proof", "pod-basics", "audit-kit"], "leave" if i < 3 else "buy")
    visit("d0", "direct", ["why-proof", "pod-basics", "audit-kit", "offer"], "buy")
    visit("d1", "direct", ["pod-basics"], "buy")      # a path seen once: reported as small-sample, not as a 100% story
    return steps


def exercise(root) -> dict:
    r = report(sample_steps())
    top = r["paths"][0]
    small = [p for p in r["paths"] if p["sample"] == "small" and p["rate"] == 1.0]
    return {"sessions": r["sessions"], "conversions": r["conversions"],
            "top_path": top["path"], "top_path_rate": top["rate"], "top_path_lower_bound": top["rate_lower_bound"],
            "single_session_path_lower_bound": small[0]["rate_lower_bound"] if small else None,
            "removal_attribution": r["removal"]["attributed_conversions"],
            "attribution_sums_to_conversions": abs(r["removal"]["sums_to_measured_conversions"] - r["conversions"]) < 0.01,
            "by_source": r["by_source"],
            "disputes_attracts_but_does_not_convert": r["removal"]["attributed_conversions"].get("disputes", 0)
            < r["removal"]["attributed_conversions"].get("pod-basics", 0)}
