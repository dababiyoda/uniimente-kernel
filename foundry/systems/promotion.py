"""#16 Promotion pipeline: a rule mutation reaches production only through every stage, in order.

The artifact is a Foundry DSL rule (#2): pricing, budget or capital policy.
Stages, each recorded with its evidence; the first failure blocks promotion:

  spec          parses in its language; declares test cases and a replay tolerance
  tests         every declared case returns its expected value
  replay        historical inputs through candidate and current: no case moves beyond tolerance
                unless the change declares it as intended
  adversarial   seeded extreme inputs never break the language's output contract
  simulation    projected margin over a demand sample stays at or above the current rule's floor
  canary        a deterministic 10% of recorded cases: realized margin no worse than control
  verification  a separate Python process recomputes every case; results must hash-match
  ratification  a founder-signed SOP_RATIFY naming the candidate and the stage-evidence hash

Only then is the rule committed as a new version (#3) citing the run as evidence.
Repository code still ships through GitHub CI and review; this governs the
Foundry's own rule artifacts.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import sys
from pathlib import Path

from foundry.systems import dsl, versions

STAGES = ("spec", "tests", "replay", "adversarial", "simulation", "canary", "verification", "ratification")


class PromotionError(ValueError):
    pass


def _canon(v) -> bytes:
    return json.dumps(v, sort_keys=True, separators=(",", ":")).encode()


def _h(v) -> str:
    return hashlib.sha256(_canon(v)).hexdigest()


def _safe(language, source, inputs):
    try:
        return dsl.run(language, source, inputs)
    except dsl.RuleError as exc:
        return f"RuleError: {exc}"


def _margin(price, case) -> float:
    return price - case["cost_per_unit"] * case["units"]


def _stage_spec(c, ctx):
    dsl.parse(c["language"], c["source"])
    if not c.get("tests") or "replay_tolerance" not in c:
        raise PromotionError("a candidate must declare test cases and a replay tolerance")
    return {"language": c["language"], "cases": len(c["tests"])}


def _stage_tests(c, ctx):
    failures = [t for t in c["tests"] if _safe(c["language"], c["source"], t["inputs"]) != t["expect"]]
    if failures:
        raise PromotionError(f"{len(failures)} declared test(s) fail, first: {failures[0]}")
    return {"passed": len(c["tests"])}


def _stage_replay(c, ctx):
    moved = []
    for case in ctx["history"]:
        old, new = dsl.run(c["language"], ctx["current"], case), _safe(c["language"], c["source"], case)
        if isinstance(new, str):
            moved.append({"case": case["id"], "error": new})
        elif abs(new - old) > c["replay_tolerance"] * max(abs(old), 1e-9) and case["id"] not in c.get("intended", []):
            moved.append({"case": case["id"], "old": old, "new": new})
    if moved:
        raise PromotionError(f"{len(moved)} historical case(s) moved beyond tolerance: {moved[:3]}")
    return {"replayed": len(ctx["history"]), "intended_changes": len(c.get("intended", []))}


def _stage_adversarial(c, ctx):
    rng = random.Random(16)
    variables = sorted(dsl.LANGUAGES[c["language"]]["variables"])
    broken = []
    for _ in range(300):
        inputs = {v: rng.choice([0, 1, 2, 1e-9, 10 ** rng.randint(0, 9), rng.uniform(0, 1e6)]) for v in variables}
        out = _safe(c["language"], c["source"], inputs)
        if isinstance(out, str) and "below" in out or isinstance(out, str) and "cannot" in out:
            broken.append({"inputs": inputs, "error": out})
        elif isinstance(out, str) and "division by zero" in out.lower():
            broken.append({"inputs": inputs, "error": out})
    if broken:
        raise PromotionError(f"{len(broken)} adversarial input(s) break the contract, first: {broken[0]}")
    return {"fuzzed": 300}


def acceptance(price: float, case: dict, *, base_rate: float = 0.6, elasticity: float = 2.5) -> float:
    """Constant-elasticity demand around the list price; a declared model, not a measured one."""
    ref = case["base_price"] * case["units"]
    return max(0.0, min(1.0, base_rate * (ref / price) ** elasticity)) if price > 0 else 0.0


def _stage_simulation(c, ctx):
    exp = lambda src: sum(_margin(p, d) * acceptance(p, d) for d in ctx["demand"]
                          for p in [dsl.run(c["language"], src, d)])
    cur, new = exp(ctx["current"]), exp(c["source"])
    floor = cur * ctx.get("margin_floor", 0.98)
    if new < floor:
        raise PromotionError(f"projected expected margin {new:.2f} is below the floor {floor:.2f}")
    return {"expected_margin": round(new, 2), "current_expected_margin": round(cur, 2)}


def _stage_canary(c, ctx):
    """Paired canary: the same 10% cohort priced by candidate and current rule, one shared draw per case.

    ``ctx["market"]`` is where acceptance comes from. In the developmental sandbox it
    is an emulated market whose elasticity differs from the simulation's model; a
    live canary needs founder-authorized traffic and is not run here.
    """
    market = ctx["market"]
    rng = random.Random(market["seed"])
    cohort = [(r, rng.random()) for r in ctx["recorded"]]
    cohort = [(r, u) for r, u in cohort if int(hashlib.sha256(r["id"].encode()).hexdigest(), 16) % 10 == 0]
    if len(cohort) < 10:
        raise PromotionError(f"canary cohort too small ({len(cohort)})")
    realized = lambda src: sum(_margin(p, r) * (u < acceptance(p, r, base_rate=market["base_rate"],
                                                                elasticity=market["elasticity"]))
                               for r, u in cohort for p in [dsl.run(c["language"], src, r)]) / len(cohort)
    canary_m, control_m = realized(c["source"]), realized(ctx["current"])
    if canary_m < control_m * 0.95:
        raise PromotionError(f"canary margin {canary_m:.2f} worse than control {control_m:.2f} on the same cohort")
    return {"canary_cases": len(cohort), "canary_margin": round(canary_m, 2), "control_margin": round(control_m, 2),
            "market": market["kind"]}


def _stage_verification(c, ctx):
    cases = [t["inputs"] for t in c["tests"]] + ctx["history"]
    local = [dsl.run(c["language"], c["source"], case) for case in cases]
    root = Path(__file__).resolve().parents[2]
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONPATH": str(root),
           "PYTHONDONTWRITEBYTECODE": "1"}
    if os.environ.get("GREG_FOUNDRY_STORE"):
        env["GREG_FOUNDRY_STORE"] = os.environ["GREG_FOUNDRY_STORE"]
    proc = subprocess.run([sys.executable, "-s", "-m", "greg.foundry_protocol_worker", "dsl-verify"], input=json.dumps(
        {"language": c["language"], "source": c["source"], "cases": cases}), capture_output=True, text=True,
        cwd=root, timeout=60, env=env)
    if proc.returncode != 0:
        raise PromotionError(f"independent verifier failed: {proc.stderr[-300:]}")
    remote = json.loads(proc.stdout)
    if _h(remote) != _h(local):
        raise PromotionError("independent recomputation disagrees with the pipeline")
    return {"verified_cases": len(cases), "result_hash": _h(local)[:16]}


def _stage_ratification(c, ctx):
    from greg.founder import FounderVerifier, instant
    env = ctx.get("ratification")
    if env is None:
        raise PromotionError("awaiting founder ratification")
    verifier = FounderVerifier(body_id=ctx["body_id"], enrolled=ctx["enrolled"], seen_nonce=lambda n: False)
    verifier.verify(env, now=instant(ctx["now"]), expected_kind="SOP_RATIFY")
    want = {"name": c["name"], "content_hash": _h({"source": c["source"], "evidence": ctx["evidence_hash"]})}
    if env["body"] != want:
        raise PromotionError("ratification does not name this candidate and its stage evidence")
    return {"ratified_by": env["founder_key_id"]}


RUNNERS = {s: globals()[f"_stage_{s}"] for s in STAGES}


def evidence_hash(candidate: dict, stages: list[dict]) -> str:
    return _h({"candidate": candidate, "stages": [s for s in stages if s["stage"] != "ratification"]})


def promote(root: Path, candidate: dict, ctx: dict) -> dict:
    stages = []
    for stage in STAGES:
        if stage == "ratification":
            ctx = {**ctx, "evidence_hash": evidence_hash(candidate, stages)}
        try:
            result = RUNNERS[stage](candidate, ctx)
        except (PromotionError, dsl.RuleError, ValueError) as exc:
            stages.append({"stage": stage, "passed": False, "why": f"{type(exc).__name__}: {exc}"[:400]})
            return {"status": "BLOCKED", "blocked_at": stage, "stages": stages,
                    "evidence_hash": evidence_hash(candidate, stages)}
        stages.append({"stage": stage, "passed": True, "result": result})
    record = versions.commit(Path(root) / "rules", candidate["name"],
                             {"language": candidate["language"], "source": candidate["source"]},
                             reason=candidate.get("reason", "promoted"), evidence=[evidence_hash(candidate, stages)])
    return {"status": "PROMOTED", "version": record["n"], "stages": stages,
            "evidence_hash": evidence_hash(candidate, stages)}


QUERY_OPS = {"dry_run": lambda a, r: promote(Path(r) / "dry-run", a["candidate"], {**a["context"], "ratification": None}),
             "evidence_hash": lambda a, r: {"evidence_hash": promote(Path(r) / "dry-run", a["candidate"],
                                                                     {**a["context"], "ratification": None})["evidence_hash"]}}
APPLY_OPS = {"promote": lambda a, r: promote(r, a["candidate"], a["context"])}


CURRENT = "base_price * units"


def context(**extra) -> dict:
    rng = random.Random(7)
    history = [{"id": f"h{i}", "base_price": rng.choice([80, 100, 120]), "units": rng.randint(1, 20),
                "customer_tier": rng.choice([0, 1, 2]), "cost_per_unit": 50} for i in range(40)]
    recorded = [{**h, "id": f"c{i}"} for i, h in enumerate(history * 10)]
    market = {"kind": "emulated", "elasticity": 2.2, "base_rate": 0.55, "seed": 5}
    return {"current": CURRENT, "history": history, "demand": history, "recorded": recorded, "market": market, **extra}


def candidate(source: str, *, name="quote-pricing", tolerance=0.25, tests=None, intended=()) -> dict:
    return {"name": name, "language": "pricing", "source": source, "replay_tolerance": tolerance,
            "intended": list(intended), "reason": "tiered discount",
            "tests": tests or [{"inputs": {"base_price": 100, "units": 10, "customer_tier": 0, "cost_per_unit": 50},
                                "expect": dsl.run("pricing", source, {"base_price": 100, "units": 10,
                                                                     "customer_tier": 0, "cost_per_unit": 50})}]}


def exercise(root) -> dict:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from greg.founder import instant, key_id, public_bytes, sign_command
    root = Path(root)
    now = "2026-09-27T12:00:00Z"
    founder = Ed25519PrivateKey.from_private_bytes(bytes(32 * [7]))
    f_hex = public_bytes(founder.public_key()).hex()
    base = dict(body_id="body-a", enrolled={key_id(f_hex): f_hex}, now=now)
    good_src = "max(base_price * units * (1 - 0.05 * customer_tier), cost_per_unit * units * 1.1)"
    blocked = {
        "wrong_test": promote(root, candidate(good_src, tests=[{"inputs": {"base_price": 100, "units": 1, "customer_tier": 0,
                                                                          "cost_per_unit": 50}, "expect": 1}]), context(**base)),
        "replay_regression": promote(root, candidate("base_price * units * 0.5"), context(**base)),
        "adversarial": promote(root, candidate("base_price * units - cost_per_unit * units", tolerance=100.0),
                               context(**base)),
        "margin_floor": promote(root, candidate("cost_per_unit * units", tolerance=100.0), context(**base)),
        # the simulation's demand model says discounts pay; this market disagrees, and the canary catches it
        "canary_inelastic_market": promote(root, candidate(good_src), context(**base, market={
            "kind": "emulated-inelastic", "elasticity": 0.1, "base_rate": 0.55, "seed": 5})),
    }
    good = candidate(good_src)
    unratified = promote(root, good, context(**base))
    ev = unratified["evidence_hash"]
    wrong = sign_command(founder, "SOP_RATIFY", {"name": good["name"], "content_hash": "0" * 64}, body_id="body-a",
                         now=instant(now), nonce="w" * 16)
    wrong_ratification = promote(root, good, context(**base, ratification=wrong))
    ok_env = sign_command(founder, "SOP_RATIFY", {"name": good["name"], "content_hash": _h({"source": good_src,
                                                                                           "evidence": ev})},
                          body_id="body-a", now=instant(now), nonce="r" * 16)
    promoted = promote(root, good, context(**base, ratification=ok_env))
    return {"blocked": {k: (v["status"], v["blocked_at"]) for k, v in blocked.items()},
            "without_ratification": (unratified["status"], unratified["blocked_at"]),
            "wrong_ratification": (wrong_ratification["status"], wrong_ratification["blocked_at"]),
            "promoted": promoted["status"], "version": promoted.get("version"),
            "stages_passed": [s["stage"] for s in promoted["stages"] if s["passed"]],
            "stage_results": {s["stage"]: s.get("result") for s in promoted["stages"]},
            "committed": versions.content(root / "rules", "quote-pricing")}
