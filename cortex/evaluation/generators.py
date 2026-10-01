"""Deterministic synthetic data for evaluation fixtures.

The generators live in the evaluation package, never in an organ, so no route
can read the true effect it is asked to estimate.
"""
from __future__ import annotations

import random


def confounded(*, n: int, effect: float, confounding: float, seed: int, strata: int = 3,
               noise: float = 1.0) -> list[dict]:
    """Discrete confounder z raises both treatment probability and outcome.

    True average effect of t on y is ``effect``. The naive difference in means is
    biased upward by ``confounding``.
    """
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        z = rng.randrange(strata)
        p = 0.2 + 0.6 * z / max(strata - 1, 1)
        t = 1 if rng.random() < p else 0
        y = effect * t + confounding * z + rng.gauss(0.0, noise)
        rows.append({"z": z, "t": t, "y": round(y, 4)})
    return rows


def expand(payload: dict) -> dict:
    """Replace a ``causal_spec.data_generator`` block with generated rows."""
    spec = payload.get("causal_spec")
    if isinstance(spec, dict) and "data_generator" in spec:
        gen = dict(spec.pop("data_generator"))
        kind = gen.pop("kind")
        if kind != "confounded":
            raise ValueError(f"unknown generator {kind!r}")
        spec["data"] = confounded(**gen)
    return payload
