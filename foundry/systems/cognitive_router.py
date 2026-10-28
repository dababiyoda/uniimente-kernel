"""#25 Cognitive Router: choose the model route by verified quality, price, privacy and latency.

GREG's ModelRouter (greg/models.py) stays the single owner of how a call is
made: preference order, demotion after failures, no shopping a refusal to
another vendor, spend bounded under a signed budget. This module owns how the
order is *chosen*, and the memory that choice is made from:

  quality   per (route, task class): verified-outcome reputation (#41 scoring,
            lower confidence bound) from recorded judgments, not vendor claims
  price     observed cost per call, exponentially weighted; a route with no
            observation inherits its configured price or is ranked last
  latency   observed p50 seconds, exponentially weighted
  privacy   each route declares a privacy class (``local``, ``contracted``,
            ``public``); a request's ``privacy`` requirement excludes routes
            below it, before any scoring. Exclusion is not failover: a request
            that may only run locally fails rather than leaks.

Selection is Pareto-aware: a route is dropped when another route is at least
as good on every axis and better on one; survivors are ordered by a weighted
score whose weights come from the request's priority (``quality``, ``cost`` or
``latency``). The chosen order is handed to the Kernel router. Every decision is
recorded with the axis values it used so the choice can be audited and later
compared with the outcome; an outcome recorded against a decision updates the
memory the next decision reads.

Memory and governance survive provider loss: routes are data; when one
disappears, its history stays and the next decision simply excludes it.
"""
from __future__ import annotations

import json
from pathlib import Path

from foundry.systems import reputation

PRIVACY_RANK = {"public": 0, "contracted": 1, "local": 2}
PRIORITIES = {"quality": (0.6, 0.2, 0.2), "cost": (0.25, 0.55, 0.2), "latency": (0.25, 0.2, 0.55),
              "balanced": (0.4, 0.3, 0.3)}
EWMA = 0.3


class RouterPolicyError(ValueError):
    pass


def _load(root: Path) -> dict:
    p = Path(root) / "router.json"
    return json.loads(p.read_text()) if p.exists() else {"routes": {}, "outcomes": [], "decisions": []}


def _save(root: Path, state: dict) -> None:
    Path(root).mkdir(parents=True, exist_ok=True)
    tmp = Path(root) / "router.tmp"
    tmp.write_text(json.dumps(state, sort_keys=True))
    tmp.replace(Path(root) / "router.json")


def declare(root: Path, name: str, *, provider: str, privacy: str, price_per_call_usd: float | None = None) -> dict:
    if privacy not in PRIVACY_RANK:
        raise RouterPolicyError(f"privacy class must be one of {sorted(PRIVACY_RANK)}")
    state = _load(root)
    state["routes"][name] = {"provider": provider, "privacy": privacy, "configured_price": price_per_call_usd,
                             "cost_ewma": None, "latency_ewma": None, "calls": 0, "available": True}
    _save(root, state)
    return {"route": name, "privacy": privacy}


def mark(root: Path, name: str, *, available: bool) -> dict:
    state = _load(root)
    if name not in state["routes"]:
        raise RouterPolicyError(f"unknown route {name}")
    state["routes"][name]["available"] = available
    _save(root, state)
    return {"route": name, "available": available}


def observe(root: Path, name: str, *, task: str, verdict: str, cost_usd: float, latency_s: float, at: str,
            evidence: str) -> dict:
    """An outcome for a route on a task: a verified judgment plus what it cost and took."""
    state = _load(root)
    r = state["routes"].get(name)
    if r is None:
        raise RouterPolicyError(f"unknown route {name}")
    r["cost_ewma"] = cost_usd if r["cost_ewma"] is None else (1 - EWMA) * r["cost_ewma"] + EWMA * cost_usd
    r["latency_ewma"] = latency_s if r["latency_ewma"] is None else (1 - EWMA) * r["latency_ewma"] + EWMA * latency_s
    r["calls"] += 1
    state["outcomes"].append({"subject": name, "context": task, "verdict": verdict, "at": at, "evidence": [evidence]})
    _save(root, state)
    return {"route": name, "calls": r["calls"]}


def _axes(state: dict, task: str, now: str) -> dict[str, dict]:
    rep = reputation.score(state["outcomes"], now=now)["subjects"]
    quality = {(s["subject"], s["context"]): s["lower_bound"] for s in rep}
    out = {}
    for name, r in state["routes"].items():
        if not r["available"]:
            continue
        price = r["cost_ewma"] if r["cost_ewma"] is not None else r["configured_price"]
        out[name] = {"quality": quality.get((name, task), quality.get((name, "*"), 0.5)),
                     "cost_usd": price, "latency_s": r["latency_ewma"], "privacy": r["privacy"],
                     "observed_calls": r["calls"]}
    return out


def _dominated(a: dict, b: dict) -> bool:
    """b is at least as good as a on every axis and better on one (unknowns rank worst)."""
    def worse_or_equal(x, y, higher_better):
        if x is None:
            return True
        if y is None:
            return False
        return x <= y if higher_better else x >= y
    rows = [(a["quality"], b["quality"], True), (a["cost_usd"], b["cost_usd"], False), (a["latency_s"], b["latency_s"], False)]
    return all(worse_or_equal(x, y, h) for x, y, h in rows) and any(
        (x is None and y is not None) or (x is not None and y is not None and x != y) for x, y, _ in rows)


def choose(root: Path, *, task: str, privacy: str, priority: str, now: str, budget_usd: float | None = None) -> dict:
    if privacy not in PRIVACY_RANK or priority not in PRIORITIES:
        raise RouterPolicyError("unknown privacy class or priority")
    state = _load(root)
    axes = _axes(state, task, now)
    eligible = {n: a for n, a in axes.items() if PRIVACY_RANK[a["privacy"]] >= PRIVACY_RANK[privacy]}
    excluded = {n: f"privacy {a['privacy']} < required {privacy}" for n, a in axes.items() if n not in eligible}
    if budget_usd is not None:
        for n, a in list(eligible.items()):
            if a["cost_usd"] is not None and a["cost_usd"] > budget_usd:
                excluded[n] = f"observed cost {a['cost_usd']:.4f} > budget {budget_usd:.4f}"
                del eligible[n]
    if not eligible:
        decision = {"task": task, "privacy": privacy, "priority": priority, "order": [], "excluded": excluded, "at": now}
        state["decisions"].append(decision)
        _save(root, state)
        raise RouterPolicyError(f"no route satisfies the request: {excluded}")
    frontier = {n: a for n, a in eligible.items() if not any(_dominated(a, b) for m, b in eligible.items() if m != n)}
    dominated = sorted(set(eligible) - set(frontier))
    wq, wc, wl = PRIORITIES[priority]
    costs = [a["cost_usd"] for a in frontier.values() if a["cost_usd"] is not None] or [1.0]
    lats = [a["latency_s"] for a in frontier.values() if a["latency_s"] is not None] or [1.0]

    def norm(v, pool):
        if v is None:
            return 1.0                                   # unknown is treated as the worst observed
        hi = max(pool) or 1.0
        return v / hi
    scored = {n: round(wq * a["quality"] - wc * norm(a["cost_usd"], costs) - wl * norm(a["latency_s"], lats), 4)
              for n, a in frontier.items()}
    order = sorted(frontier, key=lambda n: (-scored[n], n)) + dominated
    decision = {"task": task, "privacy": privacy, "priority": priority, "order": order, "scores": scored,
                "axes": {n: eligible[n] for n in order}, "dominated": dominated, "excluded": excluded, "at": now}
    state["decisions"].append(decision)
    _save(root, state)
    return decision


class PolicyRouter:
    """GREG's ModelRouter with its route order chosen per request by the policy above.

    Routes must have ``.name`` matching a declared route. Governance is inherited: a
    refusal is terminal, spend stays bounded, a route excluded for privacy is never tried.
    """

    def __init__(self, root: Path, routes, *, clock=None, record=None):
        from greg.models import ModelRouter
        self.root, self.routes = Path(root), {r.name: r for r in routes}
        self.inner = ModelRouter(list(routes), clock=clock, record=record)
        self.clock = self.inner.clock

    def complete(self, system: str, user: str, *, task: str, privacy: str = "public", priority: str = "balanced",
                 budget_usd=None) -> dict:
        import time
        from greg.models import ModelRouter, RouteError
        now = self.clock().isoformat()
        decision = choose(self.root, task=task, privacy=privacy, priority=priority, now=now, budget_usd=budget_usd)
        ordered = [self.routes[n] for n in decision["order"] if n in self.routes]
        if not ordered:
            raise RouteError("no declared route is instantiated")
        sub = ModelRouter(ordered, demote_after=self.inner.demote_after, cooldown=self.inner.cooldown,
                          clock=self.inner.clock, record=self.inner.record)
        sub.health = {n: self.inner.health.get(n, h) for n, h in sub.health.items()}
        started = time.perf_counter()
        result = sub.complete(system, user, budget_usd=budget_usd)
        self.inner.health.update(sub.health)
        return {**result, "decision": decision, "latency_s": round(time.perf_counter() - started, 4)}


QUERY_OPS = {"choose": lambda a, r: choose(r, task=a["task"], privacy=a.get("privacy", "public"),
                                           priority=a.get("priority", "balanced"), now=a["now"],
                                           budget_usd=a.get("budget_usd")),
             "routes": lambda a, r: _axes(_load(r), a.get("task", "*"), a["now"])}
APPLY_OPS = {"declare": lambda a, r: declare(r, a["name"], provider=a["provider"], privacy=a["privacy"],
                                             price_per_call_usd=a.get("price_per_call_usd")),
             "observe": lambda a, r: observe(r, a["name"], task=a["task"], verdict=a["verdict"],
                                             cost_usd=float(a["cost_usd"]), latency_s=float(a["latency_s"]),
                                             at=a["at"], evidence=a["evidence"]),
             "mark": lambda a, r: mark(r, a["name"], available=bool(a["available"]))}


class _ScriptedRoute:
    """A route whose answers follow a script, for exercise and tests (no network)."""
    def __init__(self, name, provider, script):
        self.name, self.provider, self.script = name, provider, list(script)

    def complete(self, system, user, *, budget_usd=None):
        from greg.models import Refusal, RouteError, TRANSIENT
        step = self.script.pop(0) if self.script else "ok"
        if step == "down":
            raise RouteError(f"{self.name} unreachable", kind=TRANSIENT)
        if step == "refuse":
            raise Refusal(f"{self.name} declined")
        return {"text": f"answer from {self.name}", "cost_usd": 0.01, "served_model": self.name}


def exercise(root) -> dict:
    root = Path(root)
    now = "2026-10-13T12:00:00Z"
    for name, provider, privacy, price in (("anthropic:opus", "anthropic", "contracted", 0.02),
                                           ("openai:gpt", "openai", "contracted", 0.015),
                                           ("local:llama", "local", "local", 0.001)):
        declare(root, name, provider=provider, privacy=privacy, price_per_call_usd=price)
    # evidence: the contracted routes have verified records on "summarize"; the local one is weaker and slow
    for n in range(8):
        observe(root, "anthropic:opus", task="summarize", verdict="VERIFIED", cost_usd=0.02, latency_s=2.0, at=now, evidence=f"a{n}")
    for n in range(8):
        observe(root, "openai:gpt", task="summarize", verdict="VERIFIED" if n < 6 else "REFUTED", cost_usd=0.012,
                latency_s=1.2, at=now, evidence=f"o{n}")
    for n in range(6):
        observe(root, "local:llama", task="summarize", verdict="VERIFIED" if n < 3 else "REFUTED", cost_usd=0.001,
                latency_s=6.0, at=now, evidence=f"l{n}")
    by_quality = choose(root, task="summarize", privacy="public", priority="quality", now=now)["order"]
    by_cost = choose(root, task="summarize", privacy="public", priority="cost", now=now)["order"]
    local_only = choose(root, task="summarize", privacy="local", priority="quality", now=now)
    refusals = {}
    try:
        choose(root, task="summarize", privacy="local", priority="quality", now=now, budget_usd=0.0001)
    except RouterPolicyError as exc:
        refusals["nothing_fits_budget_and_privacy"] = str(exc)[:80]
    # provider loss: the preferred route disappears; memory and governance stay
    mark(root, "anthropic:opus", available=False)
    after_loss = choose(root, task="summarize", privacy="public", priority="quality", now=now)["order"]
    mark(root, "anthropic:opus", available=True)
    # live failover through GREG's router: first route down, second answers; a refusal is terminal
    pr = PolicyRouter(root, [_ScriptedRoute("anthropic:opus", "anthropic", ["down"]),
                             _ScriptedRoute("openai:gpt", "openai", ["ok"]),
                             _ScriptedRoute("local:llama", "local", ["ok"])],
                      clock=lambda: __import__("datetime").datetime(2026, 10, 13, 12, 0, tzinfo=__import__("datetime").timezone.utc))
    answered = pr.complete("s", "u", task="summarize", privacy="public", priority="quality")
    pr2 = PolicyRouter(root, [_ScriptedRoute("anthropic:opus", "anthropic", ["refuse"]),
                              _ScriptedRoute("openai:gpt", "openai", ["ok"])], clock=pr.clock)
    try:
        pr2.complete("s", "u", task="summarize", privacy="public", priority="quality")
        refusals["refusal_shopped"] = False
    except Exception as exc:
        refusals["refusal_is_terminal"] = type(exc).__name__
    decisions = len(_load(root)["decisions"])
    return {"by_quality": by_quality, "by_cost": by_cost, "local_only": local_only["order"],
            "local_only_excluded": sorted(local_only["excluded"]), "after_provider_loss": after_loss,
            "failover_answered_by": answered["route"], "failover_tried": [t["outcome"] for t in answered["tried"]],
            "refusals": refusals, "decisions_recorded": decisions, "memory_kept_after_loss":
            _load(root)["routes"]["anthropic:opus"]["calls"] == 8}
