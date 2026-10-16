"""P8 protected evolutionary cognition: improve non-constitutional cognition only against a sealed evaluator.

Founder directive 2026-10-07 (step C). The only route by which GREG's cognition may change itself:

    detect recurring cognitive failure          (incumbent loses to the simple baseline on >= 25% of the
                                                  train split, measured by the sealed evaluator)
    -> characterise the residual geometry        (failure rate by category and history length)
    -> generate candidate configurations         (mutation + crossover inside a CLOSED parameter space;
                                                  a candidate is data, never code)
    -> isolate each candidate                    (evolution_sandbox.py: network-denied, scrubbed env,
                                                  Landlock-confined before it reads a problem; it receives
                                                  problem inputs only - real outcomes never enter it)
    -> frozen evaluator it cannot edit           (SealedEvaluator: outcomes held by this trusted process,
                                                  sealed by digest of evaluator code + outcomes + rule;
                                                  re-checked before every decision)
    -> adversarial evaluation                    (short histories and injected level shifts; every
                                                  candidate output must pass the genome's independent
                                                  verify; no stress set may worsen by > 5%)
    -> held-out evaluation vs the incumbent      (one look, at the end: one-sided sign test p < 0.05
                                                  over paired series AND lower mean loss -> RETAIN)
    -> lineage record + proposal                 (never applied: adopting a retained configuration is
                                                  a reviewed change / founder decision; rollback is the
                                                  incumbent configuration, recorded with its digest)

Candidates may change only the target's declared space (for the forecasting genome: fit window, rolling
origins, trend/damping grids, error model, interval scale). ``validate_config`` refuses any other key,
any value outside the space, and any name touching constitutional or evaluation state (``PROTECTED``:
greg.improvement's constitutional terms plus evaluator, threshold, acceptance, seal, label, truth,
score). Nothing here can change the Constitution, founder identity, authority, approvals, consequence
classes, credentials, budgets, shutdown, targets, frozen evidence, its own acceptance rule or the Gate.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import inspect
import json
import math
from pathlib import Path
import random
import statistics
import subprocess
import sys

from greg.improvement import PROTECTED as CONSTITUTIONAL
from .contracts import canonical, digest

ROOT = Path(__file__).resolve().parents[2]
SANDBOX = Path(__file__).with_name("evolution_sandbox.py")
PROTECTED = CONSTITUTIONAL + ("evaluator", "threshold", "acceptance", "seal", "freeze", "label", "truth", "score",
                              "verdict", "heldout", "held_out")
FAILURE_RATE_TRIGGER = 0.25
TRAIN_GAIN_MIN = 0.01              # a candidate must beat the incumbent's train loss by > 1% to go further
STRESS_TOLERANCE = 0.05
ALPHA = 0.05
RULE = ("trigger: incumbent worse than the simple baseline on >= 25% of train items; candidate advances if its "
        "train mean loss beats the incumbent's by > 1%; adversarial: every output verifies and no stress set "
        "worsens by > 5%; RETAIN iff on the held-out split the one-sided exact sign test over paired items gives "
        "p < 0.05 and the candidate's mean loss is lower; otherwise REJECT. Never applied automatically.")


class EvolutionError(ValueError):
    pass


def protected(name) -> bool:
    lowered = str(name).lower()
    return any(term in lowered for term in PROTECTED)


@dataclass(frozen=True)
class Target:
    name: str
    space: dict
    incumbent: dict

    def validate(self, config) -> dict:
        if not isinstance(config, dict):
            raise EvolutionError("a candidate configuration is a mapping")
        for key in config:
            if protected(key):
                raise EvolutionError(f"{key!r} is constitutional or evaluation state; evolution can never change it")
        if set(config) != set(self.space):
            raise EvolutionError(f"a candidate must set exactly the {self.name} space: {sorted(self.space)}")
        for key, (kind, values) in self.space.items():
            value = config[key]
            if kind == "choice" and value not in values:
                raise EvolutionError(f"{key}={value!r} is outside the declared space")
            if kind == "float" and (type(value) not in (int, float) or not values[0] <= value <= values[1]):
                raise EvolutionError(f"{key}={value!r} is outside [{values[0]}, {values[1]}]")
        return json.loads(canonical(config))


def forecasting_target() -> Target:
    from .genomes import forecasting
    return Target("forecast_quantile", forecasting.CONFIG_SPACE, dict(forecasting.DEFAULT_CONFIG))


@dataclass(frozen=True)
class TargetSpec:
    """Everything a cycle needs about one evolvable cognition target. The sandbox imports only the target
    modules allow-listed in evolution_sandbox.TARGETS; nothing here is chosen by a candidate."""
    name: str
    target: object                      # () -> Target
    split: object                       # () -> (train_items, heldout_items, excluded_ids)
    score: object                       # (data, truth, output) -> {"quality", "category"}
    baseline: object                    # data -> output (the simple method the trigger compares against)
    verify: object                      # (data, output, certificate) -> {check: bool}
    stress: object                      # items -> derived adversarial items
    buckets: object                     # item -> [(dimension, value)] for the residual geometry
    failure_metric: str
    proposal: dict = field(default_factory=dict)


def _forecasting_spec() -> TargetSpec:
    from .genomes import forecasting

    def bucket(item):
        n = len(item["data"]["history"])
        length = "short<=300" if n <= 300 else "medium<=1000" if n <= 1000 else "long>1000"
        return [("category", item["category"]), ("history_length", length)]
    return TargetSpec(
        name="forecast_quantile", target=forecasting_target, split=lambda: forecasting_split(),
        score=forecasting.score, baseline=forecasting.naive_gaussian, verify=forecasting.verify, stress=_stress,
        buckets=bucket, failure_metric="scaled pinball loss vs naive Gaussian baseline",
        proposal={"module": "greg/cognition/genomes/forecasting.py", "constant": "DEFAULT_CONFIG",
                  "canary": "run the forecasting admission and P6 F5 with the proposed configuration before "
                            "adoption; keep comparing with the incumbent after adoption"})


IMMUNE_TRAIN_SEEDS = tuple(range(7000, 7040))      # fresh for P8: admission uses 0-9 (dev) and 1000-1029
IMMUNE_HELDOUT_SEEDS = tuple(range(8000, 8060))


def immune_target() -> Target:
    from .genomes import collective
    return Target("immune_detect", collective.IMMUNE_CONFIG_SPACE, dict(collective.IMMUNE_DEFAULT_CONFIG))


def immune_split() -> tuple[dict, dict, list[str]]:
    """Seeded negative-selection instances reserved for P8, disjoint from every admission seed."""
    from .genomes import admission, collective
    reserved = set(admission.DEV_SEEDS) | set(admission.HELDOUT_SEEDS)
    if reserved & (set(IMMUNE_TRAIN_SEEDS) | set(IMMUNE_HELDOUT_SEEDS)):
        raise EvolutionError("P8 immune seeds overlap the admission seeds")

    def item(seed):
        data, truth = collective.immune_instance(seed)
        return f"s{seed}", {"data": data, "truth": truth, "category": collective.immune_subregion(data)}
    return (dict(item(s) for s in IMMUNE_TRAIN_SEEDS), dict(item(s) for s in IMMUNE_HELDOUT_SEEDS),
            sorted(f"s{s}" for s in reserved))


def _immune_stress(items: dict) -> dict:
    """Adversarial derivations of train items: scarce self samples; a five-fold tighter false-alarm budget."""
    out = {}
    for key, item in items.items():
        d = item["data"]
        out[f"scarce:{key}"] = {"data": {**d, "self_samples": d["self_samples"][:80]}, "truth": item["truth"]}
        out[f"strict:{key}"] = {"data": {**d, "max_false_alarm_rate": round(d["max_false_alarm_rate"] / 5, 6)},
                                "truth": item["truth"]}
    return out


def _immune_spec() -> TargetSpec:
    from .genomes import collective

    def bucket(item):
        return [("dimension", item["category"]), ("false_alarm_budget", str(item["data"]["max_false_alarm_rate"]))]
    return TargetSpec(
        name="immune_detect", target=immune_target, split=immune_split, score=collective.immune_score,
        baseline=collective.immune_zscore, verify=collective.immune_verify, stress=_immune_stress, buckets=bucket,
        failure_metric="F1 under the false-alarm tolerance vs the per-feature z-score baseline",
        proposal={"module": "greg/cognition/genomes/collective.py", "constant": "IMMUNE_DEFAULT_CONFIG",
                  "canary": "run the collective_immune admission with the proposed configuration before adoption; "
                            "keep comparing with the incumbent after adoption"})


TARGET_SPECS = {"forecast_quantile": _forecasting_spec, "immune_detect": _immune_spec}


def config_id(config: dict) -> str:
    return "cfg-" + digest(config)[7:19]


# ------------------------------------------------------------------ variation
def mutate(target: Target, config: dict, rng: random.Random) -> tuple[dict, list[str]]:
    out, ops = dict(config), []
    for key in rng.sample(sorted(target.space), k=rng.choice((1, 1, 2))):
        kind, values = target.space[key]
        if kind == "choice":
            choices = [v for v in values if v != out[key]]
            out[key] = rng.choice(choices)
        else:
            lo, hi = values
            out[key] = round(min(hi, max(lo, out[key] + rng.gauss(0, (hi - lo) / 6))), 3)
        ops.append(f"mutate:{key}")
    return target.validate(out), ops


def crossover(target: Target, a: dict, b: dict, rng: random.Random) -> tuple[dict, list[str]]:
    child = {k: (a[k] if rng.random() < 0.5 else b[k]) for k in target.space}
    return target.validate(child), ["crossover"]


# ------------------------------------------------------------------ isolation
def run_candidate(target: Target, config: dict, problems: list[dict], *, require_confinement: bool = True,
                  probe_read: str | None = None, timeout: int = 600) -> dict:
    """Execute one validated configuration on problem inputs in the confined sandbox."""
    from greg.capabilities import run_isolated
    request = {"target": target.name, "config": target.validate(config),
               "problems": [{"id": p["id"], "data": p["data"]} for p in problems], "confine": True}
    if probe_read is not None:
        request["probe_read"] = probe_read
    proc = run_isolated([sys.executable, "-I", str(SANDBOX)], cwd=ROOT, timeout=timeout,
                        input_bytes=json.dumps(request).encode())
    if proc.returncode:
        raise EvolutionError(f"sandbox exited {proc.returncode}: {proc.stderr[-300:].decode(errors='replace')}")
    result = json.loads(proc.stdout)
    if require_confinement and not result.get("confined"):
        raise EvolutionError(result.get("error") or "candidate ran without filesystem confinement")
    return result


# ------------------------------------------------------------------ sealed evaluator
class SealedEvaluator:
    """Holds the real outcomes in this trusted process only; scores outputs; refuses after any change."""

    def __init__(self, items: dict, score_fn):
        self._items = items                    # id -> {"data": ..., "truth": ...}
        self._score = score_fn
        self.seal = self._compute_seal()

    def _compute_seal(self) -> str:
        code = inspect.getsource(SealedEvaluator) + inspect.getsource(self._score) + RULE
        return digest({"code": hashlib.sha256(code.encode()).hexdigest(),
                       "outcomes": digest({k: v["truth"] for k, v in sorted(self._items.items())}),
                       "inputs": digest({k: v["data"] for k, v in sorted(self._items.items())})})

    def check(self):
        if self._compute_seal() != self.seal:
            raise EvolutionError("EVALUATOR_TAMPERED: the sealed evaluator or its outcomes changed")

    def problems(self) -> list[dict]:
        return [{"id": k, "data": v["data"]} for k, v in sorted(self._items.items())]

    def losses(self, outputs: dict) -> dict:
        self.check()
        out = {}
        for key, item in self._items.items():
            produced = outputs.get(key) or {}
            s = self._score(item["data"], item["truth"], produced.get("output"))
            out[key] = -s["quality"] if s["category"] != "wrong" else math.inf
        return out


def relative_gain(incumbent: float, candidate: float) -> float:
    """Fractional loss reduction, correct for losses of either sign (pinball loss > 0; -F1 <= 0).

    An infinite mean loss means at least one wrong answer: fewer wrong answers is an unbounded gain, equal
    infinities are no evidence of gain, and never NaN (NaN compares False and would slip through a gate)."""
    if math.isinf(incumbent) or math.isinf(candidate):
        return 0.0 if incumbent == candidate else (math.inf if candidate < incumbent else -math.inf)
    if incumbent == 0:
        return math.inf if candidate < 0 else 0.0
    return (incumbent - candidate) / abs(incumbent)


def worsened(incumbent: float, candidate: float, tolerance: float = STRESS_TOLERANCE) -> bool:
    """True when the candidate's loss is worse than the incumbent's by more than ``tolerance`` of its size."""
    return candidate > incumbent + tolerance * abs(incumbent)


def outputs_verified(verify, items: dict, outputs: dict) -> bool:
    """Every ANSWER verifies independently. An abstention (output None) is not an answer and is not verified;
    the sealed score already rates it below a correct answer."""
    return all(all(verify(items[k]["data"], v["output"], v["certificate"]).values())
               for k, v in outputs.items() if v.get("output") is not None)


def sign_test(wins: int, losses: int) -> float:
    n = wins + losses
    return 1.0 if n == 0 else sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


# ------------------------------------------------------------------ the forecasting cycle
def forecasting_split(seed: int = 808) -> tuple[dict, dict, list[str]]:
    """M4 weekly series reserved for P8: not Micro/Industry (P6 F5) and not any admission instance."""
    from .genomes import admission, forecasting
    pool = forecasting.admission_series()
    used = {forecasting.instance(s)[0]["series_id"] for s in (*admission.DEV_SEEDS, *admission.HELDOUT_SEEDS)}
    free = sorted((s for s in pool if s["id"] not in used), key=lambda s: int(s["id"][1:]))
    random.Random(seed).shuffle(free)
    half = len(free) // 2

    def item(s):
        return {"data": {"history": s["train"], "horizon": 13, "levels": list(forecasting.LEVELS),
                         "series_id": s["id"]}, "truth": {"actual": s["test"]}, "category": s["category"]}
    return ({s["id"]: item(s) for s in free[:half]}, {s["id"]: item(s) for s in free[half:]}, sorted(used))


def _stress(items: dict) -> dict:
    """Adversarial derivations of train items: short histories; a persistent level shift at the end."""
    out = {}
    for key, item in items.items():
        h, a = item["data"]["history"], item["truth"]["actual"]
        out[f"short:{key}"] = {"data": {**item["data"], "history": h[-70:]}, "truth": {"actual": a}}
        shifted = h[:-8] + [v * 1.3 for v in h[-8:]]
        out[f"shift:{key}"] = {"data": {**item["data"], "history": shifted}, "truth": {"actual": [v * 1.3 for v in a]}}
    return out


def cycle(*, generations: int = 5, population: int = 8, seed: int = 20261008, out: Path | None = None,
          require_confinement: bool = True, target_name: str = "forecast_quantile") -> dict:
    if target_name not in TARGET_SPECS:
        raise EvolutionError(f"unknown evolution target {target_name!r}")
    spec = TARGET_SPECS[target_name]()
    target = spec.target()
    train_items, heldout_items, excluded = spec.split()
    train = SealedEvaluator(train_items, spec.score)
    heldout = SealedEvaluator(heldout_items, spec.score)
    record = {"schema": "greg-protected-evolution/1", "target": target.name, "rule": RULE,
              "started_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "evaluator_seals": {"train": train.seal, "heldout": heldout.seal},
              "split": {"train": len(train_items), "heldout": len(heldout_items),
                        "excluded_admission_items": len(excluded)},
              "incumbent": {"config": target.incumbent, "id": config_id(target.incumbent)}}
    rng = random.Random(seed)

    def evaluate(config, evaluator):
        run = run_candidate(target, config, evaluator.problems(), require_confinement=require_confinement)
        return evaluator.losses(run["outputs"]), run

    # 1. detect a recurring failure (incumbent vs the simple baseline on the train split)
    incumbent_train, run0 = evaluate(target.incumbent, train)
    record["confinement"] = run0.get("confined")
    baseline_train = train.losses({k: {"output": spec.baseline(v["data"])} for k, v in train_items.items()})
    failing = [k for k in train_items if incumbent_train[k] > baseline_train[k]]
    rate = len(failing) / len(train_items)
    record["failure"] = {"metric": spec.failure_metric, "rate": round(rate, 4),
                         "trigger": FAILURE_RATE_TRIGGER, "incumbent_mean_train_loss":
                         round(statistics.fmean(incumbent_train.values()), 6)}
    if rate < FAILURE_RATE_TRIGGER:
        record["decision"] = "NO_RECURRING_FAILURE"
        return _finish(record, out)
    # 2. residual geometry
    geometry = {}
    for key, item in train_items.items():
        for dim, value in spec.buckets(item):
            g = geometry.setdefault(dim, {}).setdefault(value, {"n": 0, "failing": 0})
            g["n"] += 1
            g["failing"] += int(key in failing)
    record["residual_geometry"] = geometry
    # 3-4. isolated search inside the closed space
    lineage, scored = [], {}
    def consider(config, parents, ops, generation):
        cid = config_id(config)
        if cid not in scored:
            losses, _ = evaluate(config, train)
            scored[cid] = (statistics.fmean(losses.values()), config)
            lineage.append({"id": cid, "generation": generation, "parents": parents, "ops": ops, "config": config,
                            "train_mean_loss": round(scored[cid][0], 6)})
    scored[record["incumbent"]["id"]] = (record["failure"]["incumbent_mean_train_loss"], target.incumbent)
    lineage.append({"id": record["incumbent"]["id"], "generation": 0, "parents": [], "ops": ["incumbent"],
                    "config": target.incumbent, "train_mean_loss": record["failure"]["incumbent_mean_train_loss"]})
    for _ in range(population - 1):
        child, ops = mutate(target, target.incumbent, rng)
        consider(child, [record["incumbent"]["id"]], ops, 1)
    for generation in range(2, generations + 1):
        elite = sorted(scored.values(), key=lambda v: v[0])[:max(2, population // 3)]
        for _ in range(population):
            a, b = rng.sample(elite, 2) if len(elite) > 1 else (elite[0], elite[0])
            child, ops = crossover(target, a[1], b[1], rng)
            child, more = mutate(target, child, rng)
            consider(child, [config_id(a[1]), config_id(b[1])], ops + more, generation)
    record["search"] = {"generations": generations, "population": population, "evaluated": len(scored),
                        "lineage": lineage}
    best_loss, best = min(scored.values(), key=lambda v: (v[0], config_id(v[1])))
    best_id = config_id(best)
    record["candidate"] = {"id": best_id, "config": best, "train_mean_loss": round(best_loss, 6)}
    gain = relative_gain(record["failure"]["incumbent_mean_train_loss"], best_loss)
    if best_id == record["incumbent"]["id"] or gain <= TRAIN_GAIN_MIN:
        record["decision"] = "REJECT"
        record["reason"] = f"no candidate beat the incumbent's train loss by more than {TRAIN_GAIN_MIN:.0%}"
        return _finish(record, out)
    # 5. adversarial evaluation (derived stress sets + independent verification of every output)
    stress = SealedEvaluator(spec.stress(train_items), spec.score)
    inc_s, _ = evaluate(target.incumbent, stress)
    cand_s, cand_run = evaluate(best, stress)
    verified = outputs_verified(spec.verify, stress._items, cand_run["outputs"])
    adversarial = {}
    for kind in sorted({k.split(":")[0] for k in stress._items}):
        ki = [inc_s[k] for k in inc_s if k.startswith(kind)]
        kc = [cand_s[k] for k in cand_s if k.startswith(kind)]
        adversarial[kind] = {"incumbent": round(statistics.fmean(ki), 6), "candidate": round(statistics.fmean(kc), 6)}
    adversarial["all_outputs_verified"] = verified
    record["adversarial"] = adversarial
    if not verified or any(worsened(v["incumbent"], v["candidate"])
                           for k, v in adversarial.items() if isinstance(v, dict)):
        record["decision"] = "REJECT"
        record["reason"] = "adversarial evaluation failed"
        return _finish(record, out)
    # 6. one held-out look against the incumbent
    train.check()
    inc_h, _ = evaluate(target.incumbent, heldout)
    cand_h, _ = evaluate(best, heldout)
    wins = sum(1 for k in inc_h if cand_h[k] < inc_h[k] - 1e-12)
    losses = sum(1 for k in inc_h if inc_h[k] < cand_h[k] - 1e-12)
    p = sign_test(wins, losses)
    mean_inc, mean_cand = statistics.fmean(inc_h.values()), statistics.fmean(cand_h.values())
    heldout.check()
    record["heldout"] = {"n": len(inc_h), "candidate_wins": wins, "candidate_losses": losses,
                         "sign_test_p_one_sided": round(p, 6), "incumbent_mean_loss": round(mean_inc, 6),
                         "candidate_mean_loss": round(mean_cand, 6),
                         "relative_improvement": round(relative_gain(mean_inc, mean_cand), 4)}
    retain = p < ALPHA and mean_cand < mean_inc
    record["decision"] = "RETAIN" if retain else "REJECT"
    record["proposal"] = {"state": "PROPOSED_NOT_APPLIED", "change": {"module": spec.proposal["module"],
                          "constant": spec.proposal["constant"], "from": target.incumbent, "to": best},
                          "activation": "a reviewed change adopting the configuration; founder decision",
                          "rollback": {"to": record["incumbent"]["id"], "config": target.incumbent},
                          "canary": spec.proposal["canary"]} if retain else None
    return _finish(record, out)


def _finish(record: dict, out: Path | None) -> dict:
    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    record["authority_created"] = False
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            raise EvolutionError("refusing to overwrite an evolution record")
        out.write_text(json.dumps(record, indent=1) + "\n")
    return record


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--target", default="forecast_quantile", choices=sorted(TARGET_SPECS))
    args = ap.parse_args()
    result = cycle(out=args.out, target_name=args.target)
    print(json.dumps({k: result.get(k) for k in ("failure", "candidate", "adversarial", "heldout", "decision",
                                                 "reason")}, indent=1))
