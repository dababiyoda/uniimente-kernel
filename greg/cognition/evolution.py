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

Pre-registration: a cycle that writes a record runs against a committed freeze (``freeze``: the digests of every
file the cycle can execute or read - the static import closure, as the admission harness freezes it - the rule and
its constants, the settings - generations, population, search seed and the search policy (``SEARCH_POLICIES``) with
every configuration it declares, re-derived by the cycle and never trusted from the file - the split and both
evaluator seals) and refuses any difference at the start, before
every evaluation and before writing. Every repository file either process executes must be in that closure at its
frozen digest: the sandbox hashes the bytes it compiles and never reads repository bytecode; the parent's run is a
clean room (``python -m greg.cognition.evolution --freeze F --out O``: a fresh detached checkout of HEAD, entered
through ``evolution_room.py``, whose source-only loader hashes what it compiles and reads no bytecode). The freeze and the trusted files must equal their committed blobs, compared by content.
A held-out split is looked at once: only under a freeze, and never a split an earlier cycle or freeze looked at.
The parent checks that the sandbox cannot read the evaluator's module once confined.

Candidates are data. A code-level candidate space (a candidate that is a program) is refused by construction
(``Target.validate``) and stays refused until these latent channels are closed, each with a test: the sandbox
must not receive regenerable instance identity (seeds), must not be able to recover truth by matching inputs
against generators it can import, and its confinement must be checked by the parent rather than reported by the
child. Signal and abstract-socket scoping (Landlock ABI >= 6) and the withdrawn repository listing are in place.

A shipped evolvable configuration is pinned to its genome's version (``EVOLVABLE_CONFIG_PINS``): adopting any
configuration changes the version, so the admission evidence measured at the old version stops routing until
re-admission.
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


KINDS = ("choice", "float")


@dataclass(frozen=True)
class Target:
    name: str
    space: dict
    incumbent: dict

    def __post_init__(self):
        unknown = sorted(k for k, (kind, _) in self.space.items() if kind not in KINDS)
        if unknown:
            raise EvolutionError(f"{self.name}: unknown kinds for {unknown}; a space declares only {KINDS}")

    def validate(self, config) -> dict:
        if not isinstance(config, dict):
            raise EvolutionError("a candidate configuration is a mapping")
        for key in config:
            if protected(key):
                raise EvolutionError(f"{key!r} is constitutional or evaluation state; evolution can never change it")
        if set(config) != set(self.space):
            raise EvolutionError(f"a candidate must set exactly the {self.name} space: {sorted(self.space)}")
        out = {}
        for key, (kind, values) in self.space.items():
            value = config[key]
            if kind == "choice":
                # canonically equal, so equal value AND type at every depth: True == 1, 2.0 == 2 and [0, 0.02] ==
                # [0.0, 0.02] compare equal in Python but are not the declared choices
                try:
                    form = canonical(value)
                except (TypeError, ValueError) as exc:          # NaN, infinity or an unserialisable value
                    raise EvolutionError(f"{key}={value!r} is outside the declared space: {exc}") from None
                if not any(form == canonical(v) for v in values):
                    raise EvolutionError(f"{key}={value!r} is outside the declared space")
                out[key] = value
            elif kind == "float":
                if type(value) not in (int, float) or not math.isfinite(value) \
                        or not values[0] <= value <= values[1]:
                    raise EvolutionError(f"{key}={value!r} is outside [{values[0]}, {values[1]}]")
                out[key] = float(value) + 0.0       # one form per value: 1 -> 1.0 and -0.0 -> 0.0, so one config id
            else:
                raise EvolutionError(f"{key}: unknown kind {kind!r}")
        return json.loads(canonical(out))


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


# Each cycle on this target draws its own split; earlier splits stay reproducible by name. Cycle 2 (2026-10-09) stopped
# at the stress gate, so its held-out seeds 8000-8059 were never looked at; they stay registered to it.
# Cycle 7 (designed 2026-10-21, NOT current): 120 train and 120 held-out seeds in the 8600-9199 extension, the sizes
# the review-seed pilot scored best (docs/evidence/greg-protected-evolution/2026-10-21-immune-7). That pilot judged the
# target NOT_VIABLE under the frozen rule by its declared threshold, so the split is registered (its seeds are reserved
# and checked) but IMMUNE_CURRENT_SPLIT stays "cycle-2"; making "cycle-7" current is the session owner's decision.
IMMUNE_SPLITS = {"cycle-2": (IMMUNE_TRAIN_SEEDS, IMMUNE_HELDOUT_SEEDS),
                 "cycle-7": (tuple(range(8600, 8720)), tuple(range(8720, 8840)))}
IMMUNE_CURRENT_SPLIT = "cycle-2"


def immune_split_seeds(name: str = IMMUNE_CURRENT_SPLIT) -> tuple[tuple, tuple, set]:
    """A named immune split's train and held-out seeds and the seeds it must avoid, or EvolutionError. Generates
    nothing: a split is checked before any of its instances exists."""
    from .genomes import admission
    if name not in IMMUNE_SPLITS:
        raise EvolutionError(f"unknown immune split {name!r}")
    train_seeds, heldout_seeds = IMMUNE_SPLITS[name]
    reserved = (set(admission.DEV_SEEDS) | set(admission.HELDOUT_SEEDS) | admission.spent_seeds()
                | {s for other, seeds in IMMUNE_SPLITS.items() if other != name for part in seeds for s in part}
                | {s for seeds in CR_SPLITS.values() for part in seeds for s in part}
                | {s for seeds in CR_CANARY_SEEDS.values() for s in seeds})
    if (reserved & (set(train_seeds) | set(heldout_seeds)) or set(train_seeds) & set(heldout_seeds)
            or len(set(train_seeds)) != len(train_seeds) or len(set(heldout_seeds)) != len(heldout_seeds)
            or not (set(train_seeds) | set(heldout_seeds)) <= set(admission.P8_RESERVED)):
        raise EvolutionError("P8 immune seeds overlap the admission seeds or another P8 split")
    return train_seeds, heldout_seeds, reserved


def immune_split(name: str = IMMUNE_CURRENT_SPLIT) -> tuple[dict, dict, list[str]]:
    """Seeded negative-selection instances reserved for P8, disjoint from every admission seed, every other P8
    target's seeds and every other cycle's split on this target (``immune_split_seeds``). They come from the
    Gaussian generator that cycle 2 (2026-10-09) sampled, kept byte-identical when the admission generator gained
    native regimes (collective.BENCHMARK_REVISION), with that cycle's dimension buckets. The excluded list names the
    admission seeds only, as cycle 2 recorded it."""
    from .genomes import admission, collective
    train_seeds, heldout_seeds, _ = immune_split_seeds(name)
    reserved = set(admission.DEV_SEEDS) | set(admission.HELDOUT_SEEDS)

    def item(seed):
        data, truth = collective.immune_gaussian_instance(seed)
        return f"s{seed}", {"data": data, "truth": truth, "category": collective.immune_dimension_band(data)}
    return (dict(item(s) for s in train_seeds), dict(item(s) for s in heldout_seeds),
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


# Cycle 3 (2026-10-14): the constraint-release search policy, where admission v2 measured headroom (random
# restart beat the incumbent 15-5 on fresh seeds). Seeds inside P8's reserved range, used by no earlier cycle.
CR_TRAIN_SEEDS = tuple(range(7200, 7260))
CR_HELDOUT_SEEDS = tuple(range(7300, 7390))
# Each cycle on this target draws its own split; earlier splits stay reproducible by name. Cycle 4 (2026-10-15):
# admission v3 still measured headroom (random restart 13-10 against version 1.2.0). Cycle 5 (pre-registered
# 2026-10-16): the cover/1 search on a split no earlier cycle, freeze, admission or immune seed has drawn, with 180
# held-out items (a review-seed pilot measured that 90 leaves a real advantage kept about half the time).
CR_SPLITS = {"cycle-3": (CR_TRAIN_SEEDS, CR_HELDOUT_SEEDS),
             "cycle-4": (tuple(range(7400, 7460)), tuple(range(7500, 7590))),
             "cycle-5": (tuple(range(7600, 7660)), tuple(range(7700, 7880))),
             # cycle 6 (pre-registered 2026-10-21): 120 train and 240 held-out items, the sizes two review-seed pilots
             # chose by rules declared before each ran (docs/evidence/greg-protected-evolution/2026-10-16-cr-6/pilot)
             "cycle-6": (tuple(range(7880, 8000)), tuple(range(8060, 8300)))}
CR_CURRENT_SPLIT = "cycle-6"
# Seeds a kept proposal's canary measures (scripts/p8_cr6_canary.py), never a later cycle's split.
CR_CANARY_SEEDS = {"cycle-6": tuple(range(8300, 8540))}


def cr_target() -> Target:
    from .genomes import developmental
    return Target("constraint_release", developmental.CR_CONFIG_SPACE, dict(developmental.CR_DEFAULT_CONFIG))


def cr_split_seeds(name: str = CR_CURRENT_SPLIT) -> tuple[tuple, tuple, set]:
    """A named split's train and held-out seeds and the seeds it must avoid, or EvolutionError. Generates nothing:
    a split is checked before any of its instances exists."""
    from .genomes import admission
    if name not in CR_SPLITS:
        raise EvolutionError(f"unknown constraint-release split {name!r}")
    train_seeds, heldout_seeds = CR_SPLITS[name]
    reserved = (set(admission.DEV_SEEDS) | set(admission.HELDOUT_SEEDS) | admission.spent_seeds()
                | {s for seeds in IMMUNE_SPLITS.values() for part in seeds for s in part}
                | {s for other, seeds in CR_SPLITS.items() if other != name for part in seeds for s in part}
                | {s for seeds in CR_CANARY_SEEDS.values() for s in seeds})
    if (reserved & (set(train_seeds) | set(heldout_seeds)) or set(train_seeds) & set(heldout_seeds)
            or len(set(train_seeds)) != len(train_seeds) or len(set(heldout_seeds)) != len(heldout_seeds)
            or not (set(train_seeds) | set(heldout_seeds)) <= set(admission.P8_RESERVED)):
        raise EvolutionError("P8 constraint-release seeds overlap admission or earlier P8 seeds")
    return train_seeds, heldout_seeds, reserved


def cr_split(name: str = CR_CURRENT_SPLIT) -> tuple[dict, dict, list[str]]:
    """Seeded scheduling instances reserved for P8, disjoint from every admission seed, every other P8 target's
    seeds and every other cycle's split on this target (``cr_split_seeds``)."""
    from .genomes import developmental
    train_seeds, heldout_seeds, reserved = cr_split_seeds(name)

    def item(seed):
        data, truth = developmental.constraint_release_instance(seed)
        return f"s{seed}", {"data": data, "truth": truth, "category": developmental.constraint_release_subregion(data)}
    return (dict(item(s) for s in train_seeds), dict(item(s) for s in heldout_seeds),
            sorted(f"s{s}" for s in reserved))


def _cr_stress(items: dict) -> dict:
    """Adversarial derivations of train items: a lean evaluation budget; a validation split cut to four cases."""
    out = {}
    for key, item in items.items():
        d = item["data"]
        out[f"lean:{key}"] = {"data": {**d, "budget": 16}, "truth": item["truth"]}
        out[f"fewval:{key}"] = {"data": {**d, "validation": d["validation"][:4]}, "truth": item["truth"]}
    return out


def _cr_spec() -> TargetSpec:
    from .genomes import developmental

    def bucket(item):
        return [("due_dates", item["category"]), ("processing_times", item["truth"]["family"]["processing_times"])]
    return TargetSpec(
        name="constraint_release", target=cr_target, split=cr_split, score=developmental.constraint_release_score,
        baseline=developmental.constraint_release_random_restart, verify=developmental.constraint_release_verify,
        stress=_cr_stress, buckets=bucket,
        failure_metric="normalised tardiness gap to the exact optimum on held-out cases vs random-restart search "
                       "with the same budget and retain rule",
        proposal={"module": "greg/cognition/genomes/developmental.py", "constant": "CR_DEFAULT_CONFIG",
                  "canary": "re-admit develop_constraint_release with the proposed configuration on fresh seeds "
                            "before adoption; keep comparing with the incumbent and random restart after adoption"})


TARGET_SPECS = {"forecast_quantile": _forecasting_spec, "immune_detect": _immune_spec, "constraint_release": _cr_spec}
# Each evolvable target's shipped configuration, pinned to the genome version its admission evidence measured.
# Adopting a configuration (a reviewed change; founder decision) must bump the genome's version and this pin
# together, so evidence measured on the old configuration routes as stale until re-admission.
EVOLVABLE_CONFIG_PINS = {
    "forecast_quantile": ("forecast_quantile", "1.1.0",
                          "sha256:1214fa9e37a47f722bd1a2c0f05a81f4e88c4c201b755b3958665bb5f0de2382"),
    "immune_detect": ("collective_immune", "1.0.2",
                      "sha256:68b55c07dbdc2b44ce47e6644cc47beaa669cca996da0c4ed35ae70fa9366262"),
    "constraint_release": ("develop_constraint_release", "1.2.0",
                           "sha256:111751096c0d4bf7944981c16390f423bfcb196081502df233dd1ac55811ba10"),
}


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


# ------------------------------------------------------------------ search policy (a trusted setting, frozen)
# How the trusted parent explores the closed space. It is a setting of the cycle, written into the freeze with every
# configuration it declares, never something a candidate sets. Cycles 1-4 ran mutate-incumbent/1, which starts from
# mutants of the incumbent: cycle 4's five generations never moved p_restart above 0.339 although the space allows
# 1.0. cover/1 (cycle 5's design, informed by that record and by a pilot on review seeds) also evaluates a declared
# cover of the space in generation 1, so a region far from the incumbent is reachable by construction.
SEARCH_POLICIES = {
    "mutate-incumbent/1": "generation 1 is population - 1 mutants of the incumbent; each later generation is "
                          "population children by crossover of two of the best max(2, population // 3) "
                          "configurations so far, then mutation (cycles 1-4)",
    "cover/1": "as mutate-incumbent/1, and generation 1 also evaluates, after the mutants and from its own random "
               "stream, a declared cover of the closed space: the incumbent with one key at a time moved to each "
               "bound of a float and to each other choice, then a Latin hypercube of `lhs` points (each float range "
               "cut into `lhs` equal strata, one point per stratum; choices balanced); the freeze lists every "
               "configuration",
}
DEFAULT_SEARCH = "mutate-incumbent/1"
MAX_LHS = 64


def _axis_cover(target: Target) -> list[dict]:
    """The incumbent with one key moved at a time: each float to each bound, each choice to each other value."""
    out = []
    for key, (kind, values) in sorted(target.space.items()):
        for value in (values if kind == "choice" else (values[0], values[1])):
            out.append(target.validate({**target.incumbent, key: value}))
    return out


def _latin_hypercube(target: Target, n: int, seed: int) -> list[dict]:
    """``n`` configurations: each float range cut into n equal strata with one point per stratum (rounded as a
    mutation rounds), each choice taking its values in turn; every column shuffled independently. Its own random
    stream, so the search's stream is the same draw for draw with or without a cover."""
    rng = random.Random(f"cover/1:{seed}")
    columns = {}
    for key, (kind, values) in sorted(target.space.items()):
        if kind == "float":
            lo, hi = values
            column = [min(hi, max(lo, round(lo + (hi - lo) * (i + rng.random()) / n, 3))) for i in range(n)]
        else:
            column = [values[i % len(values)] for i in range(n)]
        rng.shuffle(column)
        columns[key] = column
    return [target.validate({key: columns[key][i] for key in target.space}) for i in range(n)]


def search_setting(target: Target, policy: str = DEFAULT_SEARCH, *, seed: int, lhs: int = 0) -> dict:
    """The search setting a freeze records: the policy, its parameter and every configuration it declares."""
    if policy not in SEARCH_POLICIES:
        raise EvolutionError(f"unknown search policy {policy!r}; declared: {sorted(SEARCH_POLICIES)}")
    if policy == "mutate-incumbent/1":
        if lhs:
            raise EvolutionError("mutate-incumbent/1 declares no cover")
        return {"policy": policy}
    if type(lhs) is not int or not 0 <= lhs <= MAX_LHS:
        raise EvolutionError(f"cover/1: lhs is an integer in [0, {MAX_LHS}]")
    seen, initial = {config_id(target.incumbent)}, []
    for config in _axis_cover(target) + (_latin_hypercube(target, lhs, seed) if lhs else []):
        if config_id(config) not in seen:
            seen.add(config_id(config))
            initial.append(config)
    return {"policy": policy, "lhs": lhs, "initial": initial}


def checked_search_setting(target: Target, setting, *, seed: int) -> dict:
    """``setting`` if it is exactly what its declared policy produces for this target and seed (a frozen list of
    configurations is re-derived and compared, never trusted), else EvolutionError."""
    if setting is None:
        return search_setting(target, seed=seed)
    if not isinstance(setting, dict) or set(setting) - {"policy", "lhs", "initial"}:
        raise EvolutionError("a search setting is {policy, lhs, initial}")
    want = search_setting(target, setting.get("policy"), seed=seed, lhs=setting.get("lhs", 0))
    if canonical(setting) != canonical(want):
        raise EvolutionError("FROZEN_INPUT_CHANGED: the search setting is not what its declared policy produces")
    return want


def run_search(target: Target, evaluate, *, generations: int, population: int, seed: int, incumbent_loss: float,
           initial=()) -> dict:
    """The trusted parent's search inside the closed space. ``evaluate(config)`` returns its loss per train item;
    the incumbent enters at ``incumbent_loss`` (the cycle passes its recorded, rounded train loss). Returns the
    lineage, the number of configurations evaluated and the one with the lowest train mean loss (ties by id)."""
    rng = random.Random(seed)
    incumbent_id = config_id(target.incumbent)
    lineage, scored = [], {}

    def consider(config, parents, ops, generation):
        cid = config_id(config)
        if cid not in scored:
            scored[cid] = (statistics.fmean(evaluate(config).values()), config)
            lineage.append({"id": cid, "generation": generation, "parents": parents, "ops": ops, "config": config,
                            "train_mean_loss": round(scored[cid][0], 6)})
    scored[incumbent_id] = (incumbent_loss, target.incumbent)
    lineage.append({"id": incumbent_id, "generation": 0, "parents": [], "ops": ["incumbent"],
                    "config": target.incumbent, "train_mean_loss": incumbent_loss})
    for _ in range(population - 1):
        child, ops = mutate(target, target.incumbent, rng)
        consider(child, [incumbent_id], ops, 1)
    axis = {config_id(c) for c in _axis_cover(target)}
    for config in initial:
        config = target.validate(config)
        consider(config, [], ["cover:axis" if config_id(config) in axis else "cover:lhs"], 1)
    for generation in range(2, generations + 1):
        elite = sorted(scored.values(), key=lambda v: v[0])[:max(2, population // 3)]
        for _ in range(population):
            a, b = rng.sample(elite, 2) if len(elite) > 1 else (elite[0], elite[0])
            child, ops = crossover(target, a[1], b[1], rng)
            child, more = mutate(target, child, rng)
            consider(child, [config_id(a[1]), config_id(b[1])], ops + more, generation)
    best_loss, best = min(scored.values(), key=lambda v: (v[0], config_id(v[1])))
    return {"lineage": lineage, "evaluated": len(scored),
            "candidate": {"id": config_id(best), "config": best, "train_mean_loss": best_loss}}


# ------------------------------------------------------------------ isolation
def _method_module(target_name: str) -> str:
    from .evolution_sandbox import TARGETS
    return TARGETS[target_name][0].replace(".", "/") + ".py"


def run_candidate(target: Target, config: dict, problems: list[dict], *, require_confinement: bool = True,
                  probe_read: str | None = None, timeout: int = 600, expected_module: str | None = None,
                  expected_code: dict | None = None) -> dict:
    """Execute one validated configuration on problem inputs in the confined sandbox.

    The parent checks the child rather than trusting its report alone. Confinement comes first: where it is
    required the sandbox must have confined itself and must fail to read a repository file once confined (by
    default this module, which holds the evaluator). Then the code: every repository file the sandbox executed
    is reported by the digest of the bytes it compiled, and each must equal ``expected_code`` (the freeze's
    closure; a file the freeze does not cover is refused) or, without a freeze, the file as this process reads
    it. ``expected_module`` pins the method module alone (METHOD_CHANGED)."""
    from greg.capabilities import run_isolated
    request = {"target": target.name, "config": target.validate(config),
               "problems": [{"id": p["id"], "data": p["data"]} for p in problems], "confine": require_confinement,
               "probe_read": probe_read or str(Path(__file__).resolve())}
    proc = run_isolated([sys.executable, "-I", "-B", str(SANDBOX)], cwd=ROOT, timeout=timeout,
                        input_bytes=json.dumps(request).encode())
    if proc.returncode:
        raise EvolutionError(f"sandbox exited {proc.returncode}: {proc.stderr[-300:].decode(errors='replace')}")
    result = json.loads(proc.stdout)
    if require_confinement and not result.get("confined"):
        raise EvolutionError(result.get("error") or "candidate ran without filesystem confinement")
    if require_confinement and probe_read is None and not str(result.get("probe")).startswith("DENIED"):
        raise EvolutionError("CONFINEMENT_UNVERIFIED: the sandbox could read the evaluator's module")
    if result.get("error"):
        raise EvolutionError(result["error"])
    method = _method_module(target.name)
    loaded = result.get("loaded") or {}
    expected = expected_module or (expected_code or {}).get(method) or _sha(ROOT / method)
    if loaded.get(method) != expected or (result.get("imported") or {}).get("sha256") != expected:
        raise EvolutionError(f"METHOD_CHANGED: the sandbox imported {method} at {loaded.get(method)}, not the "
                             f"expected {expected}")
    for path, sha in loaded.items():
        if path == method:
            continue
        if expected_code is not None and path not in expected_code:
            raise EvolutionError(f"FROZEN_INPUT_CHANGED: the sandbox executed {path}, which the freeze does not "
                                 f"cover")
        want = expected_code[path] if expected_code is not None else (
            _sha(ROOT / path) if (ROOT / path).is_file() else None)
        if sha != want:
            raise EvolutionError(f"FROZEN_INPUT_CHANGED: the sandbox executed {path} at {sha}, not {want}")
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


def _loss_number(value) -> bool:
    """A loss the gate can rank: a real number that is finite or +inf (a wrong answer). NaN, -inf, bools, None
    and strings are malformed."""
    return type(value) in (int, float) and not math.isnan(value) and value != -math.inf


def stress_worsened(kind: dict) -> bool:
    """One stress set's verdict. More wrong answers (infinite losses) than the incumbent is worse. With equal wrong
    answers the means are both infinite, so ``worsened`` alone never fired (found by the cycle-7 design pilot,
    2026-10-21: a candidate with 3 wrong answers against the incumbent's 2 passed). Fewer wrong answers is better;
    equal counts compare the items both answered under the same 5% tolerance.

    Fails closed (worsened) on anything it cannot rank: a set ``stress_summary`` marked malformed, a NaN or -inf
    mean, a wrong-answer block with non-integer or negative counts, or non-finite answered means where items were
    both answered. NaN compares False and -inf + inf is NaN, so at 239a87f each of these PASSED the gate
    (independent stress-gate audit, 2026-10-21)."""
    if kind.get("malformed"):
        return True
    if not (_loss_number(kind.get("incumbent")) and _loss_number(kind.get("candidate"))):
        return True
    wrong = kind.get("wrong")
    if wrong is None:
        return worsened(kind["incumbent"], kind["candidate"])
    counts = [wrong.get(k) for k in ("incumbent", "candidate", "both_answered")] if isinstance(wrong, dict) else [None]
    if not all(type(c) is int and c >= 0 for c in counts):
        return True
    if wrong["candidate"] != wrong["incumbent"]:
        return wrong["candidate"] > wrong["incumbent"]
    if wrong["both_answered"] == 0:
        return False
    means = (wrong.get("incumbent_answered_mean"), wrong.get("candidate_answered_mean"))
    if not all(type(m) in (int, float) and math.isfinite(m) for m in means):
        return True
    # equal wrong answers: compare the items both answered, under the same tolerance
    return worsened(*means)


def stress_summary(incumbent: dict, candidate: dict) -> dict:
    """Per stress kind (item keys ``"<kind>:<train key>"``): both mean losses and, when any loss is infinite, the
    wrong-answer counts and the means over the items both answered. Items are grouped by their exact kind and paired
    by key, never by position: a kind that prefixes another (``lean`` and ``leaner``) or two loss maps in different
    orders cannot mix or misalign items (independent stress-gate audit, 2026-10-21). Both maps must score the same
    items. A set holding a loss that is NaN, -inf or not a number is reported as ``malformed`` with no means, and
    ``stress_worsened`` fails it; only +inf counts as a wrong answer."""
    if set(incumbent) != set(candidate):
        raise EvolutionError(f"STRESS_UNPAIRED: the incumbent and candidate stress losses cover different items: "
                             f"{sorted(set(incumbent) ^ set(candidate))[:10]}")
    out = {}
    for kind in sorted({k.split(":")[0] for k in incumbent}):
        keys = [k for k in incumbent if k.split(":")[0] == kind]
        ki, kc = [incumbent[k] for k in keys], [candidate[k] for k in keys]
        bad = {"incumbent": sum(not _loss_number(v) for v in ki), "candidate": sum(not _loss_number(v) for v in kc)}
        if bad["incumbent"] or bad["candidate"]:       # NaN, -inf or not a number: unrankable, so the gate fails
            out[kind] = {"incumbent": None, "candidate": None, "malformed": bad}
            continue
        out[kind] = {"incumbent": round(statistics.fmean(ki), 6), "candidate": round(statistics.fmean(kc), 6)}
        if any(math.isinf(v) for v in ki + kc):        # wrong answers: the means alone cannot rank them
            finite = [(a, b) for a, b in zip(ki, kc) if not (math.isinf(a) or math.isinf(b))]
            out[kind]["wrong"] = {"incumbent": sum(map(math.isinf, ki)), "candidate": sum(map(math.isinf, kc)),
                                  "both_answered": len(finite),
                                  "incumbent_answered_mean": round(statistics.fmean(a for a, _ in finite), 6)
                                  if finite else None,
                                  "candidate_answered_mean": round(statistics.fmean(b for _, b in finite), 6)
                                  if finite else None}
    return out


def outputs_verified(verify, items: dict, outputs: dict) -> bool:
    """Every ANSWER verifies independently. An abstention (output None) is not an answer and is not verified;
    the sealed score already rates it below a correct answer."""
    return all(all(verify(items[k]["data"], v["output"], v["certificate"]).values())
               for k, v in outputs.items() if v.get("output") is not None)


def sign_test(wins: int, losses: int) -> float:
    n = wins + losses
    return 1.0 if n == 0 else sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


# ------------------------------------------------------------------ pre-registration (the cycle's freeze)
# Named floor of what a cycle trusts: this controller, the sandbox and its confinement, the network isolation, the
# genome contract, the cognition contracts, the improvement module's protected terms and the admission harness
# that reserves seeds. The frozen closure is wider: the static import closure of the controller, the sandbox, the
# target's genome module and all of greg/cognition (code that imports genomes by name), as the admission harness
# freezes it, plus the target's finite data. At run time every repository file either process executes must be
# in it (``_loaded_repository_files`` here; the sandbox reports the bytes it compiled).
TRUSTED_CLOSURE = ("greg/cognition/evolution.py", "greg/cognition/evolution_sandbox.py",
                   "greg/cognition/evolution_room.py", "greg/isolation.py",
                   "greg/capabilities.py", "tools/offline_test.py", "greg/cognition/genomes/contract.py",
                   "greg/cognition/contracts.py", "greg/improvement.py", "greg/cognition/genomes/admission.py")
TARGET_DATA = {"forecast_quantile": ("cortex/evaluation/data/m4_weekly.json.gz",)}
# /3 (cycle 5): the settings carry the search policy and every configuration it declares
FREEZE_SCHEMA = "greg-protected-evolution-freeze/3"
EVIDENCE = ROOT / "docs" / "evidence" / "greg-protected-evolution"


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


def trusted_closure(target_name: str) -> list[str]:
    from cortex.evaluation.closure import code_closure
    spec = TARGET_SPECS[target_name]()
    entry = ("greg/cognition/evolution.py", "greg/cognition/evolution_sandbox.py", spec.proposal["module"],
             _method_module(target_name))
    static = code_closure(entry, packages=("greg/cognition",),
                          extra=("tools/offline_test.py", *TARGET_DATA.get(target_name, ())), root=ROOT)
    return sorted({*static, *TRUSTED_CLOSURE, *entry})


def _code(target_name: str) -> dict:
    return {p: _sha(ROOT / p) for p in trusted_closure(target_name)}


def _blob_id(data: bytes) -> str:
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _dirty(paths) -> list[str]:
    """Paths whose bytes differ from the committed blob at HEAD, or that HEAD does not track. Compared by content,
    not through ``git status``, so an index flag (skip-worktree, assume-unchanged) or an ignore rule cannot hide an
    edit."""
    paths = sorted(set(paths))
    out = subprocess.run(["git", "ls-tree", "-r", "-z", "HEAD", "--", *paths], cwd=ROOT, capture_output=True)
    if out.returncode:
        return paths
    committed = {}
    for entry in out.stdout.decode().split("\0"):
        if entry:
            meta, path = entry.split("\t", 1)
            committed[path] = meta.split()[2]
    dirty = []
    for path in paths:
        file = ROOT / path
        if path not in committed or not file.is_file() or _blob_id(file.read_bytes()) != committed[path]:
            dirty.append(path)
    return dirty


def _installed(path: Path) -> bool:
    """An installed package, even inside the repository (a virtualenv under it): not repository code."""
    return bool({"site-packages", "dist-packages"} & set(path.parts)) or Path(sys.prefix).resolve() in path.parents


def _loaded_repository_files() -> set[str]:
    """Every repository file this process has executed (a module whose file lies under the repository)."""
    out = set()
    for module in list(sys.modules.values()):
        path = getattr(module, "__file__", None)
        if path:
            resolved = Path(path).resolve()
            if ROOT in resolved.parents and not _installed(resolved):
                out.add(resolved.relative_to(ROOT).as_posix())
    return out


def _clean_room_violations(code: dict | None) -> list[str]:
    """Why this process cannot vouch that the frozen code is the code it ran (empty when it can): a working tree
    that is not a fresh checkout (any untracked or ignored file, __pycache__ included), repository bytecode it may
    have read instead of the hashed source, and (given the freeze's ``code``) repository files it executed outside
    the freeze, or compiled source that differs from it. ``python -m greg.cognition.evolution --freeze F --out O``
    provides the clean room: a fresh detached checkout of HEAD, checked out with git hooks disabled, an empty
    bytecode prefix with nothing written, and ``evolution_room.py`` as the entry, which installs a source-only
    loader before any repository module is imported.

    Scope: this defends the record against a dirty or stale working tree and against the run's own code. It cannot
    defend against whoever controls the machine, who can write any record; re-executing the frozen cycle at the
    recorded commit is that check."""
    import importlib.machinery
    found = []
    entry = getattr(importlib.machinery.SourceFileLoader.get_data, "executed", None)
    if entry is None:
        found.append("not started through the clean-room entry (greg/cognition/evolution_room.py), so bytecode may "
                     "have run instead of the hashed source")
    else:
        unhashed = sorted(_loaded_repository_files() - set(entry))
        if unhashed:
            found.append(f"repository modules loaded without the entry's loader: {unhashed[:10]}")
        if code is not None:
            unlike = sorted(p for p, sha in entry.items() if code.get(p) != sha)
            if unlike:
                found.append(f"compiled repository source outside or unlike the freeze: {unlike[:10]}")
    status = subprocess.run(["git", "status", "--porcelain", "--ignored", "--untracked-files=all"], cwd=ROOT,
                            capture_output=True, text=True)
    if status.returncode or status.stdout.strip():
        found.append(f"not a fresh checkout: {status.stdout.split(chr(10))[:5] if status.stdout else status.stderr}")
    prefix = getattr(sys, "pycache_prefix", None)
    if not prefix:
        found.append("no fresh bytecode prefix: repository bytecode in __pycache__ may have run instead of source")
    else:                              # nothing writes there (-B), so any file in it was there before the run
        held = sorted(str(p) for p in Path(prefix).rglob("*") if p.is_file()) if Path(prefix).is_dir() else []
        if held:
            found.append(f"the bytecode prefix is not empty: {held[:5]}")
    if code is not None:
        outside = sorted(_loaded_repository_files() - set(code))
        if outside:
            found.append(f"executed repository files the freeze does not cover: {outside[:10]}")
    return found


# Held-out splits of the cycles before freezes existed, by target (cycles 1-3; their evidence is pinned by its source
# commit). A split is spent only if its record shows the look; every later look is a committed freeze under EVIDENCE.
PRE_FREEZE_HELDOUT = {
    "2026-10-08/cycle-forecast-1": ("forecast_quantile", lambda: set(_FORECASTING_SPLIT(
        COMPLETED_FORECAST_CYCLES["2026-10-08/cycle-forecast-1"]["seed"],
        COMPLETED_FORECAST_CYCLES["2026-10-08/cycle-forecast-1"]["excluded_seeds"])[1])),
    "2026-10-09/cycle-immune-2": ("immune_detect", lambda: {f"s{s}" for s in IMMUNE_SPLITS["cycle-2"][1]}),
    "2026-10-14/cycle-cr-3": ("constraint_release", lambda: {f"s{s}" for s in CR_SPLITS["cycle-3"][1]})}


def _looked(cycle: str) -> bool:
    """Whether a pre-freeze cycle's record shows the held-out look (cycles 2 and 3 stopped at the stress gate)."""
    record = EVIDENCE / f"{cycle}.json"
    return not record.is_file() or "heldout" in json.loads(record.read_text())


def _spent_heldout(target_name: str, exclude: Path | None = None) -> dict:
    """Held-out item ids already looked at on this target, by the cycle or freeze that looked: one look per item."""
    spent = {name: ids() for name, (target, ids) in PRE_FREEZE_HELDOUT.items()
             if target == target_name and _looked(name)}
    for manifest in sorted(EVIDENCE.rglob("freeze.json")) if EVIDENCE.is_dir() else []:
        if exclude is not None and manifest.resolve() == Path(exclude).resolve():
            continue
        inputs = json.loads(manifest.read_text()).get("inputs", {})
        if inputs.get("target") == target_name:
            spent[str(manifest.relative_to(EVIDENCE))] = set(inputs.get("split", {}).get("heldout", []))
    return spent


def _unchecked_bytecode() -> list[str]:
    """Repository modules this process loaded whose cached bytecode is hash-based with source checking off: Python
    runs such a .pyc without reading the source (normal runs write timestamp bytecode, which Python validates
    against the source), so its presence means the hashed source may not be what ran here."""
    found = []
    for module in list(sys.modules.values()):
        cached = getattr(module, "__cached__", None)
        path = getattr(module, "__file__", None)
        if not cached or not path or ROOT not in Path(path).resolve().parents or not Path(cached).is_file():
            continue
        header = Path(cached).read_bytes()[:16]
        flags = int.from_bytes(header[4:8], "little") if len(header) == 16 else 0
        if flags & 0b1 and not flags & 0b10:
            found.append(Path(path).resolve().relative_to(ROOT).as_posix())
    return sorted(found)


def _registered_heldout(target_name: str) -> set:
    """Held-out item ids of every split registered for this target, spent or reserved for a later cycle. A test
    run (``allow_dirty_for_test``) never evaluates them: it would be an unrecorded look before pre-registration."""
    if target_name == "constraint_release":
        return {f"s{s}" for _, held in CR_SPLITS.values() for s in held}
    if target_name == "immune_detect":
        return {f"s{s}" for _, held in IMMUNE_SPLITS.values() for s in held}
    return set(_FORECASTING_SPLIT()[1]) | PRE_FREEZE_HELDOUT["2026-10-08/cycle-forecast-1"][1]()


def _freeze_commit(relative: str) -> str:
    """The commit that last changed the freeze, or why it cannot be named: in a shallow clone the history may stop
    before it, and ``git log`` would name the shallow boundary instead."""
    shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT, capture_output=True,
                             text=True).stdout.strip()
    if shallow != "false":
        return "unknown: a shallow clone's history may not reach the commit that added it"
    return subprocess.check_output(["git", "log", "-1", "--format=%H", "HEAD", "--", relative], cwd=ROOT,
                                   text=True).strip()


def _in_evidence(path: Path) -> bool:
    """A recorded cycle's freeze lives at docs/evidence/greg-protected-evolution/<run>/freeze.json, where the
    spent-split ledger reads every freeze."""
    resolved = Path(path).resolve()
    return resolved.name == "freeze.json" and EVIDENCE.resolve() in resolved.parents


def _refuse_spent(target_name: str, heldout, exclude: Path | None = None):
    clash = {name: len(ids & set(heldout)) for name, ids in _spent_heldout(target_name, exclude).items()
             if ids & set(heldout)}
    if clash:
        raise EvolutionError(f"SPLIT_SPENT: held-out items already looked at by {clash}; define a fresh split")


def _settings(generations, population, seed, search) -> dict:
    for name, value, low in (("generations", generations, 1), ("population", population, 2), ("seed", seed, 0)):
        if type(value) is not int or value < low:
            raise EvolutionError(f"{name} is an integer >= {low}")
    return {"generations": generations, "population": population, "seed": seed, "search": search}


def freeze_inputs(target_name: str, *, generations: int, population: int, seed: int, search: str = DEFAULT_SEARCH,
                  lhs: int = 0) -> dict:
    """What a cycle's pre-registration fixes before any candidate runs: the rule and its constants, the search
    settings (generations, population, seed and the search policy with every configuration it declares), the split
    (item ids) and both evaluators' seals (code, outcomes and inputs), and the digest of every file the cycle can
    execute or read. ``cycle`` refuses to report if any of them differs."""
    if target_name not in TARGET_SPECS:
        raise EvolutionError(f"unknown evolution target {target_name!r}")
    spec = TARGET_SPECS[target_name]()
    setting = search_setting(spec.target(), search, seed=seed, lhs=lhs)
    settings = _settings(generations, population, seed, setting)
    train_items, heldout_items, excluded = spec.split()
    return {"schema": FREEZE_SCHEMA, "target": target_name, "rule": RULE,
            "constants": {"failure_rate_trigger": FAILURE_RATE_TRIGGER, "train_gain_min": TRAIN_GAIN_MIN,
                          "stress_tolerance": STRESS_TOLERANCE, "alpha": ALPHA},
            "settings": settings,
            "split": {"train": sorted(train_items), "heldout": sorted(heldout_items), "excluded": len(excluded)},
            "seals": {"train": SealedEvaluator(train_items, spec.score).seal,
                      "heldout": SealedEvaluator(heldout_items, spec.score).seal},
            "code": _code(target_name)}


def freeze(target_name: str, path: Path, *, generations: int = 5, population: int = 8, seed: int = 20261008,
           search: str = DEFAULT_SEARCH, lhs: int = 0) -> dict:
    """Write a cycle's pre-registration. Refuses to overwrite one, refuses a trusted file whose bytes differ from
    HEAD (the freeze must describe committed code), and refuses a held-out split any earlier cycle or freeze has
    already looked at."""
    path = Path(path)
    if path.exists():
        raise EvolutionError("refusing to overwrite a cycle freeze; use a new path")
    dirty = _dirty(trusted_closure(target_name))
    if dirty:
        raise EvolutionError(f"DIRTY_TREE: commit the trusted files before freezing: {dirty}")
    inputs = freeze_inputs(target_name, generations=generations, population=population, seed=seed, search=search,
                           lhs=lhs)
    _refuse_spent(target_name, inputs["split"]["heldout"], exclude=path)
    manifest = {"frozen_at": datetime.now(timezone.utc).isoformat(), "inputs": inputs}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=1) + "\n")
    return manifest


# ------------------------------------------------------------------ the forecasting cycle
# Seeds whose series each completed forecasting cycle excluded, as that cycle ran (its evidence is pinned by its
# source commit). Replaying a cycle's split names the series it used, so a later admission can refuse them.
COMPLETED_FORECAST_CYCLES = {"2026-10-08/cycle-forecast-1": {"seed": 808, "excluded_seeds": (*range(0, 10),
                                                                                              *range(1000, 1030))}}


def forecasting_split(seed: int = 808, excluded_seeds=None) -> tuple[dict, dict, list[str]]:
    """M4 weekly series reserved for P8: not Micro/Industry (P6 F5) and not any admission instance: the
    development seeds and the held-out seeds of every admission freeze (compared as series, not seed numbers)."""
    from .genomes import admission, forecasting
    pool = forecasting.admission_series()
    if excluded_seeds is None:
        excluded_seeds = (*admission.DEV_SEEDS, *admission.HELDOUT_SEEDS, *sorted(admission.spent_seeds()))
    used = {forecasting.instance_key(s) for s in excluded_seeds}
    free = sorted((s for s in pool if s["id"] not in used), key=lambda s: int(s["id"][1:]))
    random.Random(seed).shuffle(free)
    half = len(free) // 2

    def item(s):
        return {"data": {"history": s["train"], "horizon": 13, "levels": list(forecasting.LEVELS),
                         "series_id": s["id"]}, "truth": {"actual": s["test"]}, "category": s["category"]}
    return ({s["id"]: item(s) for s in free[:half]}, {s["id"]: item(s) for s in free[half:]}, sorted(used))


_FORECASTING_SPLIT = forecasting_split          # as defined, for replaying completed cycles' splits


def used_instance_keys(family: str) -> set[str]:
    """Data identities a completed P8 cycle trained or was evaluated on, for genomes that sample a finite pool."""
    if family != "forecast_quantile":
        return set()
    used = set()
    for cycle in COMPLETED_FORECAST_CYCLES.values():
        train, held, _ = forecasting_split(cycle["seed"], cycle["excluded_seeds"])
        used |= set(train) | set(held)
    return used


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
          require_confinement: bool = True, target_name: str = "forecast_quantile", freeze: Path | None = None,
          allow_dirty_for_test: bool = False, launcher: str | None = None, search: dict | None = None) -> dict:
    """One protected-evolution cycle.

    A cycle that writes a record (``out``) must name its pre-registered freeze (``freeze``, written by
    ``freeze()`` and committed before the run): the trusted code, the rule, the settings, the split and both
    evaluator seals must equal it at the start, before every evaluation and before the record is written, and
    every repository file each sandbox executed must match its frozen digest. A recorded cycle also requires
    that the freeze and every trusted file equal their committed blobs at HEAD, that confinement is required,
    and the clean room (``_clean_room_violations``): run it with ``python -m greg.cognition.evolution --freeze F
    --out O``. Only a test writing outside the evidence tree may pass ``allow_dirty_for_test``, and its record
    says so.

    The held-out split is evaluated only by a run that writes its record under a freeze: a development run (no
    freeze) or an unrecorded one stops before it, so the one held-out look cannot be spent, unrecorded, searching
    for a setting to pre-register."""
    if target_name not in TARGET_SPECS:
        raise EvolutionError(f"unknown evolution target {target_name!r}")
    if out is not None and freeze is None:
        raise EvolutionError("FREEZE_REQUIRED: a cycle that writes a record must name its pre-registered freeze")
    if allow_dirty_for_test and out is not None and (ROOT / "docs" / "evidence") in Path(out).resolve().parents:
        raise EvolutionError("allow_dirty_for_test never writes into the evidence tree")
    recorded = out is not None and not allow_dirty_for_test
    if recorded and not require_confinement:
        raise EvolutionError("CONFINEMENT_REQUIRED: a recorded cycle never runs candidates unconfined")
    if recorded:                       # before the target's modules are imported, so planted bytecode is still there
        violations = _clean_room_violations(None)
        if violations:
            raise EvolutionError(f"CLEAN_ROOM_REQUIRED: {violations}; run a recorded cycle with "
                                 f"python -m greg.cognition.evolution --freeze F --out O")
    spec = TARGET_SPECS[target_name]()
    target = spec.target()
    search_cfg = checked_search_setting(target, search, seed=seed)      # a declared policy, re-derived, never trusted
    settings = _settings(generations, population, seed, search_cfg)
    manifest = json.loads(Path(freeze).read_text())["inputs"] if freeze is not None else None
    closure = trusted_closure(target_name)
    dirty = _dirty(closure)
    if dirty and not allow_dirty_for_test and (out is not None or manifest is not None):
        raise EvolutionError(f"DIRTY_TREE: trusted files differ from HEAD: {dirty}")
    freeze_record = "NONE: a development run, not evidence"
    if freeze is not None:
        resolved = Path(freeze).resolve()
        relative = resolved.relative_to(ROOT).as_posix() if ROOT in resolved.parents else None
        committed = relative is not None and not _dirty([relative])
        if recorded and not (committed and _in_evidence(resolved)):
            raise EvolutionError(f"FREEZE_NOT_COMMITTED: a recorded cycle's freeze must be "
                                 f"docs/evidence/greg-protected-evolution/<run>/freeze.json, equal to its committed "
                                 f"blob at HEAD: {freeze}")
        freeze_record = {"path": relative or str(freeze), "sha256": _sha(resolved), "committed": committed}
        if committed:
            freeze_record["commit"] = _freeze_commit(relative)

    def check_frozen():
        if manifest is None:
            return
        if manifest.get("schema") != FREEZE_SCHEMA or manifest["target"] != target_name or manifest["rule"] != RULE:
            raise EvolutionError("FROZEN_INPUT_CHANGED: the freeze names another target, schema or rule")
        if canonical(manifest["settings"]) != canonical(settings):
            raise EvolutionError("FROZEN_INPUT_CHANGED: the search settings differ from the freeze")
        if manifest["constants"] != {"failure_rate_trigger": FAILURE_RATE_TRIGGER, "train_gain_min": TRAIN_GAIN_MIN,
                                     "stress_tolerance": STRESS_TOLERANCE, "alpha": ALPHA}:
            raise EvolutionError("FROZEN_INPUT_CHANGED: the rule's constants differ from the freeze")
        now = _code(target_name)
        changed = sorted(p for p in set(now) | set(manifest["code"]) if now.get(p) != manifest["code"].get(p))
        if changed:
            raise EvolutionError(f"FROZEN_INPUT_CHANGED: trusted files differ from the freeze: {changed}")
        if recorded:
            violations = _clean_room_violations(manifest["code"])
            if violations:
                raise EvolutionError(f"CLEAN_ROOM_REQUIRED: {violations}; run a recorded cycle with "
                                     f"python -m greg.cognition.evolution --freeze F --out O")

    check_frozen()
    train_items, heldout_items, excluded = spec.split()
    train = SealedEvaluator(train_items, spec.score)
    heldout = SealedEvaluator(heldout_items, spec.score)
    if manifest is not None and (manifest["seals"] != {"train": train.seal, "heldout": heldout.seal}
                                 or manifest["split"]["train"] != sorted(train_items)
                                 or manifest["split"]["heldout"] != sorted(heldout_items)):
        raise EvolutionError("EVALUATOR_TAMPERED: the evaluators' seals or split differ from the freeze")
    if manifest is not None:
        _refuse_spent(target_name, heldout_items, exclude=Path(freeze))
    record = {"schema": "greg-protected-evolution/1", "target": target.name, "rule": RULE,
              "started_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "source_dirty": dirty,
              "freeze": freeze_record,
              "execution": {"recorded": recorded, "require_confinement": require_confinement,
                            "clean_room": "checked: fresh checkout, empty bytecode prefix, executed code inside "
                                          "the freeze" if recorded else "not checked",
                            "launcher_stated": launcher,
                            "allow_dirty_for_test": allow_dirty_for_test},
              "evaluator_seals": {"train": train.seal, "heldout": heldout.seal},
              "split": {"train": len(train_items), "heldout": len(heldout_items),
                        "excluded_admission_items": len(excluded)},
              "incumbent": {"config": target.incumbent, "id": config_id(target.incumbent)}}

    def evaluate(config, evaluator):
        check_frozen()
        run = run_candidate(target, config, evaluator.problems(), require_confinement=require_confinement,
                            expected_code=manifest["code"] if manifest else None)
        return evaluator.losses(run["outputs"]), run

    def finish():
        check_frozen()
        if not recorded:
            outside = sorted(_loaded_repository_files() - set(closure))
            record["execution"]["executed_outside_closure"] = {"count": len(outside), "first": outside[:20]}
        return _finish(record, out)

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
        return finish()
    # 2. residual geometry
    geometry = {}
    for key, item in train_items.items():
        for dim, value in spec.buckets(item):
            g = geometry.setdefault(dim, {}).setdefault(value, {"n": 0, "failing": 0})
            g["n"] += 1
            g["failing"] += int(key in failing)
    record["residual_geometry"] = geometry
    # 3-4. isolated search inside the closed space, by the frozen search policy
    found = run_search(target, lambda config: evaluate(config, train)[0], generations=generations,
                   population=population, seed=seed, incumbent_loss=record["failure"]["incumbent_mean_train_loss"],
                   initial=search_cfg.get("initial", ()))
    record["search"] = {"generations": generations, "population": population, "policy": search_cfg["policy"],
                        "evaluated": found["evaluated"], "lineage": found["lineage"]}
    best_loss, best, best_id = (found["candidate"]["train_mean_loss"], found["candidate"]["config"],
                                found["candidate"]["id"])
    record["candidate"] = {"id": best_id, "config": best, "train_mean_loss": round(best_loss, 6)}
    gain = relative_gain(record["failure"]["incumbent_mean_train_loss"], best_loss)
    if best_id == record["incumbent"]["id"] or gain <= TRAIN_GAIN_MIN:
        record["decision"] = "REJECT"
        record["reason"] = f"no candidate beat the incumbent's train loss by more than {TRAIN_GAIN_MIN:.0%}"
        return finish()
    # 5. adversarial evaluation (derived stress sets + independent verification of every output)
    stress = SealedEvaluator(spec.stress(train_items), spec.score)
    inc_s, _ = evaluate(target.incumbent, stress)
    cand_s, cand_run = evaluate(best, stress)
    verified = outputs_verified(spec.verify, stress._items, cand_run["outputs"])
    adversarial = stress_summary(inc_s, cand_s)
    adversarial["all_outputs_verified"] = verified
    record["adversarial"] = adversarial
    if not verified or any(stress_worsened(v) for k, v in adversarial.items() if isinstance(v, dict)):
        record["decision"] = "REJECT"
        record["reason"] = "adversarial evaluation failed"
        return finish()
    # 6. one held-out look against the incumbent, only by a run that records it under a pre-registered freeze
    if manifest is None or out is None:
        record["decision"] = "STOPPED_BEFORE_HELDOUT"
        record["reason"] = ("only a recorded run under a pre-registered freeze (with a fresh split) evaluates the "
                            "held-out split; a development or unrecorded run stops here")
        return finish()
    if allow_dirty_for_test and set(heldout_items) & _registered_heldout(target_name):
        raise EvolutionError("a test run never evaluates a registered held-out split; use development instances")
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
    # reported, never part of the decision: the candidate against the trigger's baseline on the same held-out items
    base_h = heldout.losses({k: {"output": spec.baseline(v["data"])} for k, v in heldout_items.items()})
    bw = sum(1 for k in base_h if cand_h[k] < base_h[k] - 1e-12)
    bl = sum(1 for k in base_h if base_h[k] < cand_h[k] - 1e-12)
    record["heldout"]["candidate_vs_baseline"] = {
        "baseline": spec.failure_metric, "wins": bw, "losses": bl, "sign_test_p_one_sided": round(sign_test(bw, bl), 6),
        "baseline_mean_loss": round(statistics.fmean(base_h.values()), 6), "role": "reported; not in the rule"}
    retain = p < ALPHA and mean_cand < mean_inc
    record["decision"] = "RETAIN" if retain else "REJECT"
    record["proposal"] = {"state": "PROPOSED_NOT_APPLIED", "change": {"module": spec.proposal["module"],
                          "constant": spec.proposal["constant"], "from": target.incumbent, "to": best},
                          "activation": "a reviewed change adopting the configuration; founder decision",
                          "rollback": {"to": record["incumbent"]["id"], "config": target.incumbent},
                          "canary": spec.proposal["canary"]} if retain else None
    return finish()


def _finish(record: dict, out: Path | None) -> dict:
    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    record["authority_created"] = False
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            raise EvolutionError("refusing to overwrite an evolution record")
        out.write_text(json.dumps(record, indent=1) + "\n")
    return record


def run_recorded(target_name: str, freeze: Path, out: Path, *, timeout: int = 6 * 3600) -> int:
    """Run a recorded cycle in a clean room: a fresh detached checkout of HEAD (no uncommitted edit, index flag,
    untracked file or __pycache__ of the working tree reaches it), a fresh, empty bytecode prefix with nothing
    written, and the source-only entry ``evolution_room.py``, so the code that runs is the committed code the
    freeze hashes. The freeze must be committed, and the launching tree must equal HEAD."""
    import os
    import tempfile
    resolved = Path(freeze).resolve()
    if not _in_evidence(resolved) or _dirty([resolved.relative_to(ROOT).as_posix()]):
        raise EvolutionError(f"FREEZE_NOT_COMMITTED: commit the freeze at "
                             f"docs/evidence/greg-protected-evolution/<run>/freeze.json before running it: {freeze}")
    # This launching process ran from the working tree: refuse it unless every file it executed, and every file the
    # cycle trusts, equals HEAD (an uncommitted edit here could reach the room through the launcher itself).
    dirty = _dirty(sorted(set(trusted_closure(target_name)) | _loaded_repository_files()))
    if dirty:
        raise EvolutionError(f"DIRTY_TREE: the launching tree differs from HEAD: {dirty}")
    unchecked = _unchecked_bytecode()
    if unchecked:
        raise EvolutionError(f"CLEAN_ROOM_REQUIRED: this launcher loaded never-checked repository bytecode for "
                             f"{unchecked}; delete the __pycache__ entries and launch again")
    relative = resolved.relative_to(ROOT).as_posix()
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    with tempfile.TemporaryDirectory(prefix="greg-p8-room-") as room:
        tree, prefix = Path(room) / "tree", Path(room) / "bytecode"
        prefix.mkdir()
        subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "worktree", "add", "--detach", str(tree), commit],
                       cwd=ROOT, check=True, capture_output=True)       # no repository hook runs in the room
        try:
            if any(prefix.iterdir()):
                raise EvolutionError("CLEAN_ROOM_REQUIRED: the room's bytecode prefix was written before the run")
            env = {k: v for k, v in os.environ.items() if not k.startswith("PYTHON")}
            proc = subprocess.run([sys.executable, "-E", "-s", "-B", "-P", "-X", f"pycache_prefix={prefix}",
                                   str(tree / "greg" / "cognition" / "evolution_room.py"),
                                   "--inside", "--target", target_name, "--freeze",
                                   relative, "--out", str(Path(out).resolve()), "--launcher",
                                   f"fresh detached checkout of {commit}"], cwd=tree, env=env, timeout=timeout)
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(tree)], cwd=ROOT, capture_output=True)
    return proc.returncode


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="forecast_quantile", choices=sorted(TARGET_SPECS))
    ap.add_argument("--write-freeze", type=Path, help="pre-register a cycle: write its freeze, then commit it")
    ap.add_argument("--freeze", type=Path, help="the committed freeze the cycle must match")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--generations", type=int, default=5, help="with --write-freeze")
    ap.add_argument("--population", type=int, default=8, help="with --write-freeze")
    ap.add_argument("--seed", type=int, default=20261008, help="with --write-freeze: the search seed")
    ap.add_argument("--search", default=DEFAULT_SEARCH, choices=sorted(SEARCH_POLICIES), help="with --write-freeze")
    ap.add_argument("--lhs", type=int, default=0, help="with --write-freeze and --search cover/1")
    ap.add_argument("--inside", action="store_true", help=argparse.SUPPRESS)      # the clean room's own process
    ap.add_argument("--launcher", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.write_freeze:
        inputs = freeze(args.target, args.write_freeze, generations=args.generations, population=args.population,
                        seed=args.seed, search=args.search, lhs=args.lhs)["inputs"]
        print(json.dumps({"seals": inputs["seals"], "settings": {**inputs["settings"], "search": {
            k: (len(v) if k == "initial" else v) for k, v in inputs["settings"]["search"].items()}}}, indent=1))
        raise SystemExit(0)
    if not (args.out and args.freeze):
        raise SystemExit("--out and --freeze are required (pre-register with --write-freeze first)")
    if not args.inside:
        raise SystemExit(run_recorded(args.target, args.freeze, args.out))
    frozen = json.loads((ROOT / args.freeze).read_text())["inputs"]["settings"]
    result = cycle(out=args.out, target_name=args.target, freeze=ROOT / args.freeze, launcher=args.launcher,
                   **frozen)
    print(json.dumps({k: result.get(k) for k in ("failure", "candidate", "adversarial", "heldout", "decision",
                                                 "reason")}, indent=1))
