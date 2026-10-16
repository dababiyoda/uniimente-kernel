"""PR #155 lineage alternative (not a controller): routing-genome evolution against a hash-pinned evaluator.

Retained by the 2026-10-14 Mind-lineage convergence as an isolated, registered experimental alternative.
The canonical evolution controller is ``greg/cognition/evolution.py`` (PR #158 lineage: confined candidates,
sealed evaluator, recurring-failure cycles). Nothing on a runtime path imports this module; its only caller
is the historical runner ``cortex/evaluation/evolution/run.py`` (first run: REJECT, no headroom).

Original description:

Founder directive 2026-10-07 (section 13, step C):

    detect recurring cognitive failure -> characterise residual geometry -> generate candidate reasoning
    configuration -> isolate candidate -> frozen evaluator it cannot edit -> adversarial evaluation ->
    held-out evaluation -> baseline comparison -> retain / reject -> lineage record

What may mutate here: a *routing-policy genome* - data only, validated against a closed schema
(``SCHEMA``): the conditional-competence thresholds, the feature list and its fallback order. A candidate
cannot carry code, cannot name a key outside the schema, and has no field for authority, approval,
consequence class, credentials, budgets, shutdown, scope, evaluator, evidence or acceptance threshold;
any such key is refused and logged as an unauthorized mutation attempt.

The evaluator is a separate module run in a separate process (``evaluator_main``). Its source is pinned
by SHA-256 in the frozen manifest, re-hashed before and after every evaluation; a mismatch stops the run.
The candidate never receives the evaluator's data or path: it is passed on stdin as JSON and the
evaluator returns only a score record. Selection uses development data; the held-out partition is
evaluated once, for the final champion and the baseline, after selection has ended.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys

from .conditional_competence import FEATURES, MARGIN, MIN_EVIDENCE, SHRINK

SCHEMA = {
    "min_evidence": (float, 0.6, 12.0),
    "margin": (float, 0.0, 0.5),
    "shrink": (float, 0.0, 10.0),
    "features": (list, FEATURES),            # ordered subset of the frozen feature vocabulary
}
FORBIDDEN = ("authority", "approval", "consequence", "credential", "budget", "shutdown", "scope", "evaluator",
             "evidence_ref", "threshold_accept", "gate", "constitution", "founder", "grant")
BASELINE = {"min_evidence": MIN_EVIDENCE, "margin": MARGIN, "shrink": SHRINK, "features": list(FEATURES)}


class MutationRefused(ValueError):
    """A candidate tried to change something outside the nonconstitutional schema."""


def validate(candidate: dict) -> dict:
    if not isinstance(candidate, dict):
        raise MutationRefused("a candidate is a JSON object")
    bad = [k for k in candidate if k not in SCHEMA]
    if bad:
        hit = [k for k in bad if any(word in k.lower() for word in FORBIDDEN)]
        raise MutationRefused(("unauthorized mutation attempt: " if hit else "unknown key: ") + ", ".join(sorted(bad)))
    out = {}
    for key, (kind, *rule) in SCHEMA.items():
        value = candidate.get(key, BASELINE[key])
        if kind is float:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not rule[0] <= value <= rule[1]:
                raise MutationRefused(f"{key} outside [{rule[0]}, {rule[1]}]")
            out[key] = float(value)
        else:
            if not isinstance(value, list) or len(set(value)) != len(value) or set(value) - set(rule[0]):
                raise MutationRefused("features must be a duplicate-free subset of the frozen vocabulary")
            out[key] = list(value)
    return out


def mutate(parent: dict, rng: random.Random) -> tuple[dict, str]:
    child = json.loads(json.dumps(parent))
    move = rng.choice(("min_evidence", "margin", "shrink", "drop_feature", "add_feature", "swap_features"))
    if move in ("min_evidence", "margin", "shrink"):
        low, high = SCHEMA[move][1], SCHEMA[move][2]
        child[move] = round(min(high, max(low, child[move] * rng.choice((0.5, 0.75, 1.5, 2.0)) + rng.uniform(-.05, .05))), 4)
    elif move == "drop_feature" and len(child["features"]) > 1:
        child["features"].pop(rng.randrange(len(child["features"])))
    elif move == "add_feature":
        missing = [f for f in FEATURES if f not in child["features"]]
        if missing:
            child["features"].insert(rng.randrange(len(child["features"]) + 1), rng.choice(missing))
    elif move == "swap_features" and len(child["features"]) > 1:
        i, j = rng.sample(range(len(child["features"])), 2)
        child["features"][i], child["features"][j] = child["features"][j], child["features"][i]
    return validate(child), move


def sha256(path: Path) -> str:
    return "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()


class ProtectedEvaluator:
    """Runs a frozen evaluator module in a separate process; refuses if its source changed."""

    def __init__(self, module_path: Path, pinned: str, *, cwd: Path):
        self.module_path, self.pinned, self.cwd = Path(module_path), pinned, Path(cwd)

    def _check(self):
        current = sha256(self.module_path)
        if current != self.pinned:
            raise RuntimeError(f"EVALUATOR_CHANGED: {self.module_path} is {current}, frozen {self.pinned}")

    def __call__(self, candidate: dict, partition: str) -> dict:
        self._check()
        proc = subprocess.run([sys.executable, "-I", str(self.module_path), partition],
                              input=json.dumps(validate(candidate)).encode(), capture_output=True,
                              cwd=self.cwd, timeout=600)
        self._check()
        if proc.returncode:
            raise RuntimeError(f"evaluator failed: {proc.stderr.decode()[-500:]}")
        score = json.loads(proc.stdout)
        if set(score) - {"partition", "correct", "wrong", "no_decision", "n", "per_item"}:
            raise RuntimeError("evaluator returned fields outside its contract")
        return score


def evolve(evaluate: ProtectedEvaluator, *, generations: int, population: int, seed: int) -> dict:
    """Elitist (mu + lambda) search on development scores; returns the lineage and the champion."""
    rng = random.Random(seed)
    def fitness(score):        # correct first, then fewer wrong; ties keep the earlier (simpler) candidate
        return (score["correct"], -score["wrong"])
    baseline = validate(BASELINE)
    pool = [{"id": "g0-baseline", "parent": None, "move": None, "genome": baseline,
             "dev": evaluate(baseline, "dev")}]
    lineage = list(pool)
    for g in range(1, generations + 1):
        children = []
        for k in range(population):
            parent = rng.choice(pool)
            genome, move = mutate(parent["genome"], rng)
            children.append({"id": f"g{g}-{k}", "parent": parent["id"], "move": move, "genome": genome,
                             "dev": evaluate(genome, "dev")})
        lineage += children
        pool = sorted(pool + children, key=lambda c: fitness(c["dev"]), reverse=True)[:population]
    champion = pool[0]
    return {"lineage": lineage, "champion": champion, "baseline": lineage[0]}
