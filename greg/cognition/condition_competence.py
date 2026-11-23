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
ALTERNATIVE_FAMILY = "blackbox_multistart_lbfgsb"
ALTERNATIVE_VERSION = "1.0.0"
# The pre-registered arms: "on" (LEARN, PRE), "off" (CONTROL: no shadow pairing read, no preference), "pooled"
# (ablation A: one cell for every covered dimension), "shuffled" (ablation S: stress pairs assigned to a band by a
# seeded fair coin). Set only by the experiment harness and tests; production keeps "on".
MODE = "on"
# The condition key. "dimension" is v3's (geometry, dimension band). "dimension_objective" adds the request's declared
# objective name (v3b, tests/evidence/antifragility-v3b-2026-10-22/): both are read from the request alone. Set only by
# an experiment harness and tests; production keeps v3's key until an experiment supports another.
KEY = "dimension"
KEYS = ("dimension", "dimension_objective")


def dimension(data: dict) -> int | None:
    shift = data.get("shift") if isinstance(data, dict) else None
    return len(shift) if isinstance(shift, list) and shift else None


def condition_key(geometry: str, data: dict) -> str | None:
    """The cell a request falls in, or None when the request declares no dimension the bands cover. Under the pooled
    ablation every covered dimension shares one cell."""
    d = dimension(data)
    if d is None or d > BANDS[-1][0]:
        return None
    if MODE == "pooled":
        return f"{geometry}|all"
    for edge, label in BANDS:
        if d <= edge:
            objective = data.get("function")
            if KEY == "dimension_objective":
                return f"{geometry}|{label}|{objective}" if isinstance(objective, str) and objective else None
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
    pairs = [p for p in pairs if not (p["claim"] in seen or seen.add(p["claim"]))]
    # under the dimension-and-objective key the shuffle reassigns the objective among those the pairs carry
    objectives = sorted({p["cell"].split("|")[2] for p in pairs if p["cell"].count("|") == 2})
    for p in pairs:
        parts = p["cell"].split("|")
        if KEY == "dimension" and len(parts) == 3:
            parts = parts[:2]                                      # a coarser reader of finer evidence
        cell = "|".join(parts)
        if MODE == "pooled":
            cell = parts[0] + "|all"
        elif shuffle and KEY == "dimension_objective" and len(parts) == 3 and objectives:
            cell = f"{parts[0]}|{parts[1]}|{objectives[rnd.randrange(len(objectives))]}"
        elif shuffle:
            cell = f"{parts[0]}|{BANDS[rnd.randrange(len(BANDS))][1]}"
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


def shadow_due(cell: str | None, incumbent_unmet_in_cell: int, shadows_in_cell: int, fired: bool = False) -> bool:
    """A shadow trial is due when the incumbent has at least one settled VERIFIED_UNMET outcome in this cell, the
    cell's shadow ceiling is not spent, and the cell has not already decided (a fired preference needs no more
    shadows)."""
    return (MODE != "off" and cell is not None and not fired and incumbent_unmet_in_cell >= 1
            and shadows_in_cell < SHADOW_CEILING_PER_CELL)


def output_adapter(native_output: dict, certificate: dict) -> dict:
    """The multistart genome's answer -> the black-box request's answer shape, an exact rename: x -> candidate,
    value -> fitness, evaluations_used -> evaluations. The genome's own receipt keeps its native output."""
    return {"candidate": list(native_output["x"]), "fitness": native_output["value"],
            "evaluations": int(certificate["evaluations_used"])}


def shadow_trial(data: dict) -> dict:
    """Run the alternative on the same request through the adapter, inert: its answer is recorded, never returned.
    The genome gets exactly the request's own evaluation budget. Its own independent verifier checks the answer; a
    refused, unverified or failed trial records no fitness (and so cannot pass any predicate)."""
    import time
    from .genomes import library
    started = time.monotonic()
    record = {"policy": POLICY, "method": ALTERNATIVE, "family": ALTERNATIVE_FAMILY, "version": ALTERNATIVE_VERSION,
              "inert": True, "authority_created": False, "fitness": None, "evaluations": 0, "verified": False}
    try:
        native = adapter(data)
        out = library.run(ALTERNATIVE_FAMILY, native, {"latency_limit": 3600, "compute_limit": native["evaluations"]})
        checks = library.check(ALTERNATIVE_FAMILY, native, out["output"], out["proof"]) if out["output"] else {}
        record["evaluations"] = int((out["proof"].get("certificate") or {}).get("evaluations_used") or 0)
        record["verified"] = out["status"] == "ANSWER" and bool(checks) and all(checks.values())
        if record["verified"]:
            record["fitness"] = out["output"]["value"]
        record["checks"] = checks
    except Exception as exc:                       # a refused or failed trial is recorded, never raised
        record["error"] = f"{type(exc).__name__}: {exc}"[:300]
    record["seconds"] = round(time.monotonic() - started, 3)
    return record


def pair(check: dict, incumbent_passed: bool, shadow: dict, cell: str, claim: str) -> dict:
    """One paired observation: the shadow judged by the same signed check predicate as the incumbent's answer."""
    from greg.missions import evaluate_predicate
    alt_ok = False
    if shadow.get("verified") and shadow.get("fitness") is not None:
        alt_ok, _ = evaluate_predicate(check["predicate"], {"result": {"fitness": shadow["fitness"]}})
    return {"cell": cell, "claim": claim, "incumbent_pass": bool(incumbent_passed), "alternative_pass": bool(alt_ok),
            "shadow_evaluations": shadow.get("evaluations", 0), "shadow_seconds": shadow.get("seconds", 0.0)}


def pairs_from(journal) -> list[dict]:
    """Every settled paired observation on this body, one per signed claim (settlement deduplicates claims)."""
    from . import settlement
    return [{**o["condition_pair"], "claim": settlement._outcome_identity(o)}
            for o in settlement.measured_outcomes(journal) if o.get("condition_pair")]


def evidence_from(journal) -> dict:
    """The cell evidence this arm reads: none under CONTROL ("off"), shuffled under ablation S."""
    if MODE == "off" or journal is None:
        return {}
    return cell_evidence(pairs_from(journal), shuffle=MODE == "shuffled")


def incumbent_unmet(journal, cell: str, exclude_problem: str | None = None) -> int:
    """Settled VERIFIED_UNMET outcomes of the incumbent in this cell (true dimension, whatever the arm), from
    problems other than ``exclude_problem``: a request is never shadowed because of its own failure, so the failure
    that triggers shadowing never enters the paired evidence (its re-observation would be a known discordant pair)."""
    from . import settlement
    return sum(1 for o in settlement.measured_outcomes(journal)
               if o.get("condition_cell") == cell and o["method"] == INCUMBENT and not o["correct"]
               and o.get("problem_id") != exclude_problem)


ADMITTED_STATUSES = ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY")


def _admitted() -> bool:
    """The alternative's frozen admission verdict, read (never written) from the evidence index at its version."""
    import json
    from .compiler import EVIDENCE_INDEX
    try:
        row = json.loads(EVIDENCE_INDEX.read_text())["genomes"][ALTERNATIVE_FAMILY]
    except (OSError, ValueError, KeyError):
        return False
    return row.get("status") in ADMITTED_STATUSES and row.get("version") == ALTERNATIVE_VERSION


def _attached(registry) -> bool:
    try:
        return ALTERNATIVE in registry.manifests and bool(registry.usable(ALTERNATIVE)[0])
    except Exception:
        return False


def compile_hook(geometry, data: dict, runnable: list, registry, journal, receipt: dict, pid=None) -> list:
    """The compiler's one call site, after the runnable fits are known. It records the request's cell; when the
    incumbent serves a cell with settled failures, it runs one inert shadow of the alternative (recorded, never
    returned); when the cell preference has fired and the alternative is founder-attached and admitted, it puts the
    alternative first, through the adapter, with the preference record as its basis. It never attaches, admits or
    reads another cell. Returns the (possibly reordered) runnable list."""
    cell = condition_key(geometry, data)
    if cell is None or not runnable:
        return runnable
    receipt["condition"] = {"policy": POLICY, "cell": cell, "mode": MODE}
    if MODE == "off" or runnable[0]["method"] != INCUMBENT:
        return runnable
    evidence = evidence_from(journal)
    pref = preference(cell, evidence)
    fired = bool(pref and pref["fired"])
    if pref:
        receipt["condition"]["preference"] = pref
    if fired and _attached(registry) and _admitted():
        try:
            adapted = adapter(data)
        except ValueError as exc:
            receipt["condition"]["not_switched"] = str(exc)
            return runnable
        from .genomes import library
        row = {"method": ALTERNATIVE, "kind": "operation", "operation": library.genome(ALTERNATIVE_FAMILY).operation,
               "usable": True, "usable_why": "founder-attached", "adapted_data": adapted,
               "condition_preferred": pref}
        receipt["dissent"].append(pref["basis"])
        return [row] + runnable
    if not fired and journal is not None:
        shadows = sum(1 for p in pairs_from(journal) if p["cell"] == cell)
        if shadow_due(cell, incumbent_unmet(journal, cell, exclude_problem=pid), shadows) and _attached(registry):
            from .contracts import digest
            request = digest(data)
            prior = _prior_shadow(journal, request)
            receipt["condition_shadow"] = ({**prior, "reused": True} if prior else
                                           {**shadow_trial(data), "cell": cell, "request_digest": request})
    return runnable


def answer(chosen: dict, inner: dict):
    """The compile result: the executed method's output, renamed exactly when it ran through the adapter."""
    if chosen.get("adapted_data") is None:
        return inner["output"]
    return output_adapter(inner["output"], (inner.get("proof_artifact") or {}).get("certificate")
                          or inner.get("certificate") or {"evaluations_used": 0})


def settlement_fields(compiled, check: dict, passed: bool) -> dict:
    """The settlement call site: the compile receipt's cell and, when it carried a shadow, the paired observation
    under the same signed check (the claim identity is attached by ``pairs_from``)."""
    condition = (compiled or {}).get("condition") or {}
    if not condition.get("cell"):
        return {}
    out = {"condition_cell": condition["cell"]}
    shadow = compiled.get("condition_shadow")
    if shadow:
        out["condition_pair"] = pair(check, passed, shadow, condition["cell"], None)
    return out


def _prior_shadow(journal, request: str) -> dict | None:
    """A shadow already run on this exact request (a re-observation of the same claim). The trial is seeded and
    deterministic, so its record is reused rather than re-run; a reused record costs nothing again."""
    for record in journal.ledger.by_type("receipt"):
        output = (record.payload.get("result") or {}).get("output")
        shadow = output.get("condition_shadow") if isinstance(output, dict) else None
        if shadow and shadow.get("request_digest") == request and not shadow.get("reused"):
            return {k: v for k, v in shadow.items() if k != "reused"}
    return None


def shadow_cost(journal) -> dict:
    """Every shadow trial this body ran, re-observations included, read from its retained compile receipts: the
    repair cost the experiment counts (pairs_from keeps one pair per claim, which would under-count)."""
    trials = evaluations = 0
    seconds = 0.0
    for record in journal.ledger.by_type("receipt"):
        output = (record.payload.get("result") or {}).get("output")
        shadow = output.get("condition_shadow") if isinstance(output, dict) else None
        if shadow and not shadow.get("reused"):
            trials += 1
            evaluations += int(shadow.get("evaluations") or 0)
            seconds += float(shadow.get("seconds") or 0.0)
    return {"trials": trials, "evaluations": evaluations, "seconds": round(seconds, 3)}
