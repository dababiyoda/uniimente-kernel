"""Condition-specific competence: §14 antifragility v3 (tests/evidence/antifragility-v3-2026-10-22/PREREGISTRATION.md).

#189 found that competence summed across strata cannot learn a method's weakness in one condition. This module keys
live evidence on a declared condition of the request and lets that evidence reorder founder-attached, admitted fits
in that cell only. It works in three parts:

* ``condition_key``: the cell, ``(geometry, dimension band)``. The dimension is ``len(shift)``, a property the
  request already carries. The bands are declared here and in the pre-registration.
* ``adapter``: the declared input translation that lets the admitted ``blackbox_multistart_lbfgsb`` genome read the
  catalog's black-box request. It maps every field exactly and adds nothing. It is used only in a shadow trial or
  after the cell preference fires: the genome's admission measured 2-10 dimensions, and at 11-30 it runs on the
  cell's own paired evidence, never on its admission verdict.
* ``preference``: a one-sided exact sign test on a cell's discordant shadow pairs. It fires when p < ALPHA with at
  least MIN_DISCORDANT discordant pairs.

Nothing here attaches, admits, rewrites an admission verdict or touches any other cell. A preference can only
reorder fits that are already founder-attached and admitted. Building the evidence is pure: it reads paired records
and writes nothing.
"""
from __future__ import annotations

import math
import random
from typing import Iterable

POLICY = "greg-condition-competence/0.1"
BANDS = ((10, "d<=10"), (30, "d11-30"))            # declared before any run; a request above 30 d has no cell
ALPHA = 0.05
MIN_DISCORDANT = 5
SHADOW_CEILING_PER_CELL = 36
INCUMBENT = "cognition.swarm"
ALTERNATIVE = "cognition.blackbox_multistart_lbfgsb"
ADMITTED_ENVELOPE = "2-10 dimensions (genome admission v5, seeds 1400-1429)"
SHUFFLE_SEED = "antifragility-v3-shuffle"


def dimension(data: dict) -> int | None:
    shift = data.get("shift") if isinstance(data, dict) else None
    return len(shift) if isinstance(shift, list) and shift else None


def condition_key(geometry: str, data: dict) -> str | None:
    """The cell a request falls in, or None when the request declares no dimension the bands cover."""
    d = dimension(data)
    if d is None:
        return None
    for edge, label in BANDS:
        if d <= edge:
            return f"{geometry}|{label}"
    return None


def adapter(data: dict) -> dict:
    """The catalog black-box request -> the multistart genome's native inputs. An exact translation: function ->
    objective, the (uniform) box -> lower/upper, budget -> evaluations, dimension = len(shift); shift and seed are
    copied. A non-uniform box cannot be expressed natively and is refused rather than approximated."""
    bounds = data.get("bounds")
    if not isinstance(bounds, list) or not bounds or any(not isinstance(b, list) or len(b) != 2 for b in bounds):
        raise ValueError("adapter: bounds must be a list of [lower, upper] pairs")
    lows, highs = {b[0] for b in bounds}, {b[1] for b in bounds}
    if len(lows) != 1 or len(highs) != 1:
        raise ValueError("adapter: the multistart genome takes one box for every coordinate; refused, not "
                         "approximated")
    shift = data["shift"]
    if len(bounds) != len(shift):
        raise ValueError("adapter: bounds and shift disagree on the dimension")
    return {"objective": data["function"], "dimension": len(shift), "lower": lows.pop(), "upper": highs.pop(),
            "shift": list(shift), "evaluations": data["budget"], "seed": data["seed"]}


def sign_test(wins: int, losses: int) -> float:
    """One-sided exact sign test: P(X >= wins) for X ~ Binomial(wins + losses, 1/2)."""
    n = wins + losses
    if n == 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(wins, n + 1)) / 2 ** n


def cell_evidence(pairs: Iterable[dict], *, shuffle: bool = False) -> dict:
    """Paired shadow records -> per-cell discordant counts.

    A pair is ``{"cell", "claim", "incumbent_pass", "alternative_pass"}``, one per claim identity: a re-observed
    claim counts once. ``shuffle`` is the pre-registered S ablation: each pair is assigned to a band by a seeded fair
    coin, independent of its dimension, so a gain that survives it did not come from the condition key."""
    seen, cells = set(), {}
    rnd = random.Random(SHUFFLE_SEED)
    for p in pairs:
        if p["claim"] in seen:
            continue
        seen.add(p["claim"])
        cell = p["cell"]
        if shuffle:
            geometry = cell.split("|", 1)[0]
            cell = f"{geometry}|{BANDS[rnd.randrange(len(BANDS))][1]}"
        c = cells.setdefault(cell, {"pairs": 0, "alternative_only": 0, "incumbent_only": 0})
        c["pairs"] += 1
        c["alternative_only"] += bool(p["alternative_pass"]) and not p["incumbent_pass"]
        c["incumbent_only"] += bool(p["incumbent_pass"]) and not p["alternative_pass"]
    return cells


def preference(cell: str | None, evidence: dict) -> dict | None:
    """The cell preference, or None. Fires when the alternative's discordant wins give p < ALPHA with at least
    MIN_DISCORDANT discordant pairs. The record names its basis: live paired evidence, outside the admitted
    envelope, not a re-admission."""
    if cell is None or cell not in evidence:
        return None
    c = evidence[cell]
    w, l = c["alternative_only"], c["incumbent_only"]
    p = sign_test(w, l)
    fired = w + l >= MIN_DISCORDANT and p < ALPHA
    return {"policy": POLICY, "cell": cell, "pairs": c["pairs"], "alternative_only": w, "incumbent_only": l,
            "p_one_sided": round(p, 6), "alpha": ALPHA, "min_discordant": MIN_DISCORDANT, "fired": fired,
            "prefer": ALTERNATIVE if fired else None,
            "basis": (f"live paired evidence in cell {cell}; outside the admitted envelope ({ADMITTED_ENVELOPE}); "
                      "not a re-admission") if fired else None}


def shadow_due(cell: str | None, incumbent_unmet_in_cell: int, shadows_in_cell: int) -> bool:
    """A shadow trial is due when the incumbent has at least one settled VERIFIED_UNMET outcome in this cell and the
    cell's shadow ceiling is not spent."""
    return cell is not None and incumbent_unmet_in_cell >= 1 and shadows_in_cell < SHADOW_CEILING_PER_CELL
