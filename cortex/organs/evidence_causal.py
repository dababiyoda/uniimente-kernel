"""Evidence/Causal route (build prompt item 6).

Distinguishes factual support, association, prediction and intervention claims.
Always produces an evidence assessment: available evidence, provenance,
freshness, contradictions, missing observations and the question that remains
unresolved. Produces a causal estimate only when an explicit estimand,
identification assumptions, suitable data, confounder treatment, method and
limitations are all present — and never when the identification basis is a
model-generated diagram or explanation.

A passing refutation check is reported as exactly that. It does not prove
causal truth, so an estimate stays empirically unverified until reality
settles it.

Predictions, model outputs and self-assessments are recorded but never count as
support: they cannot settle a claim.
"""
from __future__ import annotations

import math
import random
import time
from datetime import date
from typing import Any, Mapping

from memory.causal import VALIDATION_WEIGHT

from ..contracts import CLAIM_TYPES, Expenditure, OrganResult

ORGAN_ID = "cortex.evidence_causal@0.1.0"
VERSION = "0.1.0"
NON_SETTLING_KINDS = ("model_output", "prediction", "self_assessment")
EVIDENCE_KINDS = ("measurement", "document", "testimony", "experiment") + NON_SETTLING_KINDS
# Observation tags an evidence item may carry in its ``observation`` field.
REQUIRED_OBSERVATIONS = {
    "factual_support": ("direct_observation",),
    "association": ("paired_observations",),
    "prediction": ("track_record", "current_inputs"),
    "intervention": ("estimand", "identification_assumptions", "treatment_outcome_confounder_data"),
}
OBSERVATION_TEXT = {
    "direct_observation": "a direct observation or authoritative record of the stated fact",
    "paired_observations": "paired observations of both variables from one population",
    "track_record": "a held-out track record of the predictor",
    "current_inputs": "current values of the predictor's inputs",
    "estimand": "an explicit estimand",
    "identification_assumptions": "identification assumptions",
    "treatment_outcome_confounder_data": "treatment, outcome and confounder data (or an experiment)",
}
CAUSAL_REQUIRED = ("estimand", "treatment", "outcome", "adjustment_set", "identification_assumptions",
                   "identification_basis", "method", "limitations")
IDENTIFICATION_ORIGINS = ("randomized_experiment", "declared_by_domain_expert", "quasi_experiment")
MIN_PER_ARM = 30


def _parse_day(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


class EvidenceCausalOrgan:
    organ_id = ORGAN_ID
    version = VERSION

    def run(self, problem, geometry, budget) -> OrganResult:
        started = time.perf_counter()
        payload = problem.payload
        claim = payload.get("claim") or {}
        ctype = claim.get("type")
        if ctype not in CLAIM_TYPES:
            return self._out("MALFORMED_INPUT", None, {"proof_class": "evidence_assessment",
                             "failure": f"claim type must be one of {CLAIM_TYPES}"}, started)
        assessment = self._assess(claim, payload.get("evidence", []), payload.get("as_of"))
        if ctype == "intervention":
            return self._intervention(claim, payload.get("causal_spec"), assessment, started)
        return self._empirical(claim, ctype, assessment, started)

    # ------------------------------------------------------------ assessment
    def _assess(self, claim: Mapping[str, Any], evidence: list, as_of: str | None) -> dict:
        today = _parse_day(as_of)
        usable, stale, excluded, supports, contradicts = [], [], [], [], []
        for e in evidence:
            eid = e.get("id", "?")
            kind = e.get("kind")
            status = e.get("validation_status", "self_reported")
            if kind not in EVIDENCE_KINDS:
                excluded.append({"id": eid, "why": f"unknown kind {kind!r}"})
                continue
            if kind in NON_SETTLING_KINDS:
                excluded.append({"id": eid, "why": f"{kind} cannot settle a claim"})
                continue
            observed = _parse_day(e.get("observed_at"))
            if today and observed and observed > today:
                excluded.append({"id": eid, "why": "observation dated after as_of: not yet observed (delayed outcome)"})
                continue
            max_age = e.get("max_age_days")
            if today and observed and isinstance(max_age, (int, float)) and (today - observed).days > max_age:
                stale.append({"id": eid, "age_days": (today - observed).days, "max_age_days": max_age})
                continue
            if observed is None:
                excluded.append({"id": eid, "why": "no observation date; freshness unknown"})
                continue
            weight = VALIDATION_WEIGHT.get(status, 0.0)
            item = {"id": eid, "kind": kind, "validation_status": status, "weight": weight,
                    "source": e.get("source"), "observed_at": e.get("observed_at")}
            usable.append(item)
            if e.get("stance") == "supports":
                supports.append(item)
            elif e.get("stance") == "contradicts":
                contradicts.append(item)
        have = {e.get("observation") for e in evidence
                if e.get("observation") and any(u["id"] == e.get("id") for u in usable)}
        required = REQUIRED_OBSERVATIONS[claim.get("type")]
        if claim.get("type") == "factual_support":
            missing = [] if supports or contradicts else list(required)
        else:
            missing = [tag for tag in required if tag not in have]
        return {
            "claim": {"id": claim.get("id"), "type": claim.get("type"), "statement": claim.get("statement")},
            "available": usable, "stale": stale, "excluded": excluded,
            "support_weight": round(sum(i["weight"] for i in supports), 4),
            "contradiction_weight": round(sum(i["weight"] for i in contradicts), 4),
            "contradictions": [{"supports": [i["id"] for i in supports],
                                "contradicts": [i["id"] for i in contradicts]}] if supports and contradicts else [],
            "provenance": sorted({f"{i['kind']}:{i['validation_status']}" for i in usable}),
            "missing_observations": [{"tag": m, "description": OBSERVATION_TEXT[m]} for m in missing],
            "as_of": as_of,
        }

    def _empirical(self, claim, ctype, a, started) -> OrganResult:
        s, c = a["support_weight"], a["contradiction_weight"]
        if s == 0 and c == 0:
            a["unresolved_question"] = f"Is it true that {claim.get('statement')}? No fresh settling evidence."
            a["proposal"] = "authorized_acquisition"
            return self._out("INSUFFICIENT_EVIDENCE", None, {"proof_class": "evidence_assessment", **a}, started)
        if s > 0 and c > 0 and max(s, c) < 3 * min(s, c):
            a["unresolved_question"] = "Fresh evidence conflicts; which source is correct?"
            a["proposal"] = "domain_or_human_adjudication"
            return self._out("CONTESTED", {"verdict": "contested"},
                             {"proof_class": "evidence_assessment", **a}, started)
        verdict = "supported" if s > c else "contradicted"
        if max(s, c) < 0.6:
            a["unresolved_question"] = "Only weak (self-reported) evidence; needs verification."
            a["proposal"] = "authorized_acquisition"
            return self._out("INSUFFICIENT_EVIDENCE", None, {"proof_class": "evidence_assessment", **a}, started)
        if ctype in ("association", "prediction") and a["missing_observations"]:
            a["unresolved_question"] = f"{ctype} claim lacks {[m['tag'] for m in a['missing_observations']]}"
            a["proposal"] = "authorized_acquisition"
            return self._out("INSUFFICIENT_EVIDENCE", None, {"proof_class": "evidence_assessment", **a}, started)
        a["unresolved_question"] = None
        return self._out("OK", {"verdict": verdict, "claim_type": ctype},
                         {"proof_class": "evidence_assessment", **a}, started)

    # ------------------------------------------------------------ intervention
    def _intervention(self, claim, spec, a, started) -> OrganResult:
        note = "association evidence does not identify an intervention effect"
        if not spec:
            a.update(unresolved_question=f"What is the effect of the intervention in {claim.get('statement')!r}?",
                     proposal="bounded_experiment", identification="absent", note=note)
            return self._out("NOT_IDENTIFIED", None, {"proof_class": "evidence_assessment", **a}, started)
        missing = [k for k in CAUSAL_REQUIRED if not spec.get(k) and not (k == "adjustment_set" and spec.get(k) == [])]
        basis = (spec.get("identification_basis") or {}).get("origin")
        problems = []
        if missing:
            problems.append(f"missing {missing}")
        if basis == "model_generated":
            problems.append("identification basis is model-generated; generated diagrams do not identify effects")
        elif basis and basis not in IDENTIFICATION_ORIGINS:
            problems.append(f"unrecognized identification basis {basis!r}")
        if spec.get("unmeasured_confounders"):
            problems.append(f"declared unmeasured confounders {spec['unmeasured_confounders']}")
        rows = spec.get("data") or []
        t, y, adj = spec.get("treatment"), spec.get("outcome"), list(spec.get("adjustment_set") or [])
        if not problems:
            bad_rows = [r for r in rows if any(k not in r for k in [t, y] + adj)]
            if not rows or bad_rows:
                problems.append("data absent or rows missing treatment/outcome/adjustment columns")
            elif {r[t] for r in rows} - {0, 1}:
                problems.append("treatment must be binary 0/1")
            else:
                n1 = sum(1 for r in rows if r[t] == 1)
                if min(n1, len(rows) - n1) < MIN_PER_ARM:
                    problems.append(f"fewer than {MIN_PER_ARM} rows in an arm")
        if problems:
            a.update(unresolved_question="The causal effect is not identified from what is available.",
                     proposal="bounded_experiment" if basis != "model_generated" else "domain_or_human_adjudication",
                     identification="failed", identification_problems=problems, note=note)
            return self._out("NOT_IDENTIFIED", None, {"proof_class": "evidence_assessment", **a}, started)

        method = spec["method"]
        rng = random.Random(int(spec.get("seed", 11)))
        try:
            if method == "stratified":
                est, positivity = _stratified(rows, t, y, adj)
                if positivity["dropped_fraction"] > 0.2:
                    a.update(identification="failed", identification_problems=["positivity violated"],
                             proposal="bounded_experiment", unresolved_question="Overlap is insufficient.")
                    return self._out("NOT_IDENTIFIED", None, {"proof_class": "evidence_assessment", **a}, started)
                boot = [_stratified(_resample(rows, rng), t, y, adj)[0] for _ in range(200)]
            elif method == "linear":
                est, positivity = _linear(rows, t, y, adj), {"note": "linear adjustment extrapolates; overlap not enforced"}
                boot = [_linear(_resample(rows, rng), t, y, adj) for _ in range(200)]
            else:
                raise ValueError(f"unknown method {method!r}")
        except (ValueError, ZeroDivisionError) as exc:
            a.update(identification="failed", identification_problems=[str(exc)], proposal="bounded_experiment")
            return self._out("NOT_IDENTIFIED", None, {"proof_class": "evidence_assessment", **a}, started)
        boot = sorted(b for b in boot if math.isfinite(b))
        ci = [boot[int(0.025 * len(boot))], boot[int(0.975 * len(boot)) - 1]]
        naive = _mean([r[y] for r in rows if r[t] == 1]) - _mean([r[y] for r in rows if r[t] == 0])
        refutations = _refute(rows, t, y, adj, method, est, rng)
        proof = {
            "proof_class": "causal_estimate",
            "estimand": spec["estimand"], "treatment": t, "outcome": y, "adjustment_set": adj,
            "identification_assumptions": list(spec["identification_assumptions"]),
            "identification_basis": spec["identification_basis"],
            "method": method, "estimate": est, "ci95_bootstrap": ci, "n": len(rows),
            "naive_difference": naive, "positivity": positivity, "refutations": refutations,
            "limitations": list(spec["limitations"]),
            "truth_note": "refutation checks passing does not prove causal truth; estimate holds only under the "
                          "stated identification assumptions",
            "evidence_assessment": a,
        }
        return self._out("OK", {"effect": est, "ci95": ci, "estimand": spec["estimand"],
                                "naive_difference": naive},
                         proof, started, assumptions=tuple(spec["identification_assumptions"]),
                         uncertainty=f"95% bootstrap interval [{ci[0]:.3g}, {ci[1]:.3g}] under stated assumptions")

    def _out(self, state, answer, proof, started, *, assumptions=(), uncertainty=None) -> OrganResult:
        return OrganResult(
            organ_id=ORGAN_ID, organ_version=VERSION, state=state, answer=answer, proof=proof,
            assumptions=assumptions,
            uncertainty=uncertainty or {"OK": "evidence-weighted verdict", "CONTESTED": "sources conflict"}.get(
                state, "unresolved"),
            expenditure=Expenditure(seconds=time.perf_counter() - started),
            dependencies=("python-stdlib",), origin="deterministic")


# ---------------------------------------------------------------- estimators
def _mean(xs):
    xs = list(xs)
    if not xs:
        raise ValueError("empty group")
    return sum(xs) / len(xs)


def _resample(rows, rng):
    return [rows[rng.randrange(len(rows))] for _ in rows]


def _stratified(rows, t, y, adj):
    strata: dict[tuple, list] = {}
    for r in rows:
        strata.setdefault(tuple(r[k] for k in adj), []).append(r)
    total, kept, effect = len(rows), 0, 0.0
    for members in strata.values():
        treated = [r[y] for r in members if r[t] == 1]
        control = [r[y] for r in members if r[t] == 0]
        if not treated or not control:
            continue
        kept += len(members)
        effect += len(members) * (_mean(treated) - _mean(control))
    if kept == 0:
        raise ValueError("no stratum contains both arms")
    return effect / kept, {"strata": len(strata), "dropped_fraction": round(1 - kept / total, 4)}


def _solve(a, b):
    n = len(a)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[piv][col]) < 1e-12:
            raise ValueError("design matrix is singular (collinear adjustment set?)")
        m[col], m[piv] = m[piv], m[col]
        for r in range(n):
            if r != col:
                f = m[r][col] / m[col][col]
                m[r] = [x - f * yv for x, yv in zip(m[r], m[col])]
    return [m[i][n] / m[i][i] for i in range(n)]


def _linear(rows, t, y, adj):
    xs = [[1.0, float(r[t])] + [float(r[k]) for k in adj] for r in rows]
    k = len(xs[0])
    xtx = [[sum(x[i] * x[j] for x in xs) for j in range(k)] for i in range(k)]
    xty = [sum(x[i] * float(r[y]) for x, r in zip(xs, rows)) for i in range(k)]
    return _solve(xtx, xty)[1]


def _refute(rows, t, y, adj, method, est, rng):
    fit = _stratified if method == "stratified" else (lambda rr, tt, yy, aa: (_linear(rr, tt, yy, aa), None))
    permuted = [dict(r) for r in rows]
    flags = [r[t] for r in rows]
    rng.shuffle(flags)
    for r, f in zip(permuted, flags):
        r[t] = f
    try:
        placebo = fit(permuted, t, y, adj)[0]
        out = [{"name": "placebo_treatment", "estimate": placebo,
                "passed": abs(placebo) < max(abs(est) / 3, 1e-9)}]
    except (ValueError, ZeroDivisionError) as exc:
        out = [{"name": "placebo_treatment", "estimate": None, "passed": False, "error": str(exc)}]
    if method == "linear":
        noisy = [dict(r, __rcc=rng.gauss(0, 1)) for r in rows]
        with_rcc = _linear(noisy, t, y, adj + ["__rcc"])
        out.append({"name": "random_common_cause", "estimate": with_rcc,
                    "passed": abs(with_rcc - est) <= 0.1 * max(abs(est), 1e-9)})
    halves = []
    for _ in range(5):
        subset = rng.sample(rows, len(rows) // 2)
        try:
            halves.append(fit(subset, t, y, adj)[0])
        except (ValueError, ZeroDivisionError):
            continue
    if halves:
        spread = max(halves) - min(halves)
        out.append({"name": "data_subset_stability", "estimates": halves,
                    "passed": spread <= max(abs(est), 1e-9)})
    return out
