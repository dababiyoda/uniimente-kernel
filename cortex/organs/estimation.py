"""Fermi / Estimation organ (build prompt item 5).

Executes an explicit decomposition. Every input carries a unit and a range;
dimensions are checked before any number is produced; dependencies between
uncertain inputs are preserved through a Gaussian copula instead of being
silently assumed independent; sensitivity names the dominant uncertainty; a
reference class, when supplied, anchors the result from the outside view.

Standard library only. Deterministic for a given seed.
"""
from __future__ import annotations

import math
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Mapping

from ..contracts import Expenditure, OrganResult

ORGAN_ID = "cortex.estimation.fermi@0.1.0"
VERSION = "0.1.0"
Z90 = 1.6448536269514722  # standard normal 95th percentile

# Scaled aliases normalise to a canonical symbol. Everything else is its own dimension.
_ALIASES = {
    "year": ("day", 365.25), "yr": ("day", 365.25), "month": ("day", 30.4375), "week": ("day", 7.0),
    "day": ("day", 1.0), "hour": ("day", 1 / 24), "h": ("day", 1 / 24), "minute": ("day", 1 / 1440),
    "second": ("day", 1 / 86400), "s": ("day", 1 / 86400),
    "kUSD": ("USD", 1e3), "MUSD": ("USD", 1e6), "USD": ("USD", 1.0),
    "%": ("1", 0.01), "1": ("1", 1.0),
}
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class EstimationError(ValueError):
    pass


class DimensionError(EstimationError):
    """Quantities with incompatible units were combined."""


@dataclass(frozen=True)
class Unit:
    dims: tuple[tuple[str, int], ...]
    scale: float

    @staticmethod
    def parse(text: str) -> "Unit":
        if not isinstance(text, str) or not text.strip():
            raise EstimationError("unit must be a non-empty string")
        dims: dict[str, int] = {}
        scale = 1.0
        # tokens like  a*b/c^2   ; leading '/' allowed via '1/…'
        parts = re.split(r"([*/])", text.replace(" ", ""))
        sign = 1
        for part in parts:
            if part == "*":
                sign = 1
                continue
            if part == "/":
                sign = -1
                continue
            if not part:
                continue
            base, _, exp = part.partition("^")
            power = int(exp) if exp else 1
            symbol, factor = _ALIASES.get(base, (base, 1.0))
            if symbol != "1" and not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", symbol):
                raise EstimationError(f"bad unit symbol {base!r}")
            scale *= factor ** (sign * power)
            if symbol != "1":
                dims[symbol] = dims.get(symbol, 0) + sign * power
        return Unit(tuple(sorted((k, v) for k, v in dims.items() if v)), scale)

    def mul(self, other: "Unit", sign: int = 1) -> "Unit":
        dims = dict(self.dims)
        for k, v in other.dims:
            dims[k] = dims.get(k, 0) + sign * v
        return Unit(tuple(sorted((k, v) for k, v in dims.items() if v)), 1.0)

    def pow(self, n: int) -> "Unit":
        return Unit(tuple((k, v * n) for k, v in self.dims), 1.0)

    def render(self) -> str:
        if not self.dims:
            return "1"
        num = [f"{k}^{v}" if v != 1 else k for k, v in self.dims if v > 0]
        den = [f"{k}^{-v}" if v != -1 else k for k, v in self.dims if v < 0]
        return ("*".join(num) or "1") + ("/" + "/".join(den) if den else "")


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _cholesky(m: list[list[float]]) -> list[list[float]]:
    n = len(m)
    low = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = sum(low[i][k] * low[j][k] for k in range(j))
            if i == j:
                v = m[i][i] - s
                if v <= 1e-12:
                    raise EstimationError("dependency matrix is not positive definite")
                low[i][j] = math.sqrt(v)
            else:
                low[i][j] = (m[i][j] - s) / low[j][j]
    return low


def _ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=xs.__getitem__)
    ranks = [0.0] * len(xs)
    for r, i in enumerate(order):
        ranks[i] = float(r)
    return ranks


def _pearson(a: list[float], b: list[float]) -> float:
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    return 0.0 if va == 0 or vb == 0 else cov / math.sqrt(va * vb)


def _quantile(sorted_xs: list[float], q: float) -> float:
    if not sorted_xs:
        raise EstimationError("no samples")
    pos = q * (len(sorted_xs) - 1)
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_xs[lo] + (sorted_xs[hi] - sorted_xs[lo]) * (pos - lo)


class Model:
    """A validated decomposition."""

    def __init__(self, spec: Mapping[str, Any]):
        if not isinstance(spec, Mapping):
            raise EstimationError("estimation_model must be an object")
        target = spec.get("target") or {}
        self.target_name = target.get("name", "target")
        self.target_unit = Unit.parse(target.get("unit", ""))
        self.target_unit_text = target.get("unit")
        self.variables: dict[str, dict] = {}
        for var in spec.get("variables", []):
            name = var.get("name")
            if not isinstance(name, str) or not _IDENT.match(name) or name in self.variables:
                raise EstimationError(f"bad or duplicate variable name {name!r}")
            low, high = var.get("low"), var.get("high")
            if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in (low, high)):
                raise EstimationError(f"{name}: low/high must be finite numbers")
            if low > high:
                raise EstimationError(f"{name}: low exceeds high")
            dist = var.get("dist") or ("lognormal" if low > 0 else "normal")
            if dist not in ("lognormal", "normal", "uniform"):
                raise EstimationError(f"{name}: unknown distribution {dist!r}")
            if dist == "lognormal" and low <= 0:
                raise EstimationError(f"{name}: lognormal requires positive range")
            self.variables[name] = {"unit": Unit.parse(var.get("unit", "")), "low": float(low),
                                    "high": float(high), "dist": dist, "note": var.get("note", "")}
        if not self.variables:
            raise EstimationError("decomposition requires at least one variable")
        self.names = list(self.variables)
        self.dependencies = []
        for dep in spec.get("dependencies", []):
            a, b, rho = dep.get("a"), dep.get("b"), dep.get("rho")
            if a not in self.variables or b not in self.variables or a == b:
                raise EstimationError(f"dependency names unknown variables: {a!r}, {b!r}")
            if isinstance(rho, bool) or not isinstance(rho, (int, float)) or not -1 < rho < 1:
                raise EstimationError("dependency rho must be in (-1, 1)")
            self.dependencies.append((a, b, float(rho), dep.get("reason", "")))
        self.expression = spec.get("expression")
        self.reference = spec.get("reference_class")
        self.interval = float(spec.get("interval", 0.9))
        if not 0.5 <= self.interval < 1.0:
            raise EstimationError("interval must be in [0.5, 1)")
        self.samples = int(spec.get("samples", 20000))
        if not 1000 <= self.samples <= 200000:
            raise EstimationError("samples must be in [1000, 200000]")
        self.seed = int(spec.get("seed", 7))
        self._k = -_inv_normal((1 - self.interval) / 2)
        self.result_unit = self._unit_of(self.expression)

    # ---- dimensional analysis
    def _unit_of(self, node) -> Unit:
        if isinstance(node, bool):
            raise EstimationError("booleans are not quantities")
        if isinstance(node, (int, float)):
            return Unit((), 1.0)
        if isinstance(node, str):
            if node not in self.variables:
                raise EstimationError(f"unknown variable {node!r}")
            return self.variables[node]["unit"]
        if isinstance(node, Mapping) and "const" in node:
            return Unit.parse(node.get("unit", "1"))
        if not isinstance(node, list) or not node:
            raise EstimationError(f"bad expression node {node!r}")
        op, args = node[0], node[1:]
        units = [self._unit_of(a) for a in args]
        if op in ("+", "-"):
            if len({u.dims for u in units}) != 1:
                raise DimensionError(f"cannot {op} quantities with units {[u.render() for u in units]}")
            return Unit(units[0].dims, 1.0)
        if op == "*":
            out = Unit((), 1.0)
            for u in units:
                out = out.mul(u)
            return out
        if op == "/":
            if len(units) != 2:
                raise EstimationError("'/' takes two arguments")
            return units[0].mul(units[1], -1)
        if op == "pow":
            if len(args) != 2 or not isinstance(args[1], int) or isinstance(args[1], bool):
                raise EstimationError("pow takes an expression and an integer exponent")
            return units[0].pow(args[1])
        raise EstimationError(f"unknown operator {op!r}")

    # ---- evaluation on canonical-scale values
    def _eval(self, node, env: Mapping[str, float]) -> float:
        if isinstance(node, (int, float)) and not isinstance(node, bool):
            return float(node)
        if isinstance(node, str):
            return env[node]
        if isinstance(node, Mapping):
            return float(node["const"]) * Unit.parse(node.get("unit", "1")).scale
        op, args = node[0], node[1:]
        if op == "pow":
            return self._eval(args[0], env) ** args[1]
        vals = [self._eval(a, env) for a in args]
        if op == "+":
            return sum(vals)
        if op == "-":
            return vals[0] - sum(vals[1:])
        if op == "*":
            out = 1.0
            for v in vals:
                out *= v
            return out
        if op == "/":
            return vals[0] / vals[1] if vals[1] != 0 else math.inf
        raise EstimationError(f"unknown operator {op!r}")

    def _marginal(self, name: str, z: float) -> float:
        v = self.variables[name]
        lo, hi = v["low"], v["high"]
        k = self._k
        if v["dist"] == "lognormal":
            mu = (math.log(lo) + math.log(hi)) / 2
            sd = (math.log(hi) - math.log(lo)) / (2 * k) if hi > lo else 0.0
            x = math.exp(mu + sd * z)
        elif v["dist"] == "normal":
            x = (lo + hi) / 2 + ((hi - lo) / (2 * k)) * z
        else:
            x = lo + (hi - lo) * _phi(z)
        return x * v["unit"].scale

    def sample(self, *, dependent: bool = True) -> list[float]:
        n = len(self.names)
        corr = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
        if dependent:
            for a, b, rho, _ in self.dependencies:
                i, j = self.names.index(a), self.names.index(b)
                corr[i][j] = corr[j][i] = rho
        low = _cholesky(corr)
        rng = random.Random(self.seed)
        out = []
        self._last_inputs = {name: [] for name in self.names}
        for _ in range(self.samples):
            e = [rng.gauss(0.0, 1.0) for _ in range(n)]
            z = [sum(low[i][k] * e[k] for k in range(i + 1)) for i in range(n)]
            env = {name: self._marginal(name, z[i]) for i, name in enumerate(self.names)}
            for name in self.names:
                self._last_inputs[name].append(env[name])
            out.append(self._eval(self.expression, env) / self.target_unit.scale)
        return out

    def at(self, overrides: Mapping[str, float]) -> float:
        env = {name: self._marginal(name, overrides.get(name, 0.0)) for name in self.names}
        return self._eval(self.expression, env) / self.target_unit.scale


def _inv_normal(p: float) -> float:
    """Acklam's rational approximation; |error| < 1.2e-9 on (0, 1)."""
    if not 0 < p < 1:
        raise EstimationError("probability out of range")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    plow = 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > 1 - plow:
        return -_inv_normal(1 - p)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
        (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def _render(node) -> str:
    if isinstance(node, (int, float)) and not isinstance(node, bool):
        return repr(node)
    if isinstance(node, str):
        return node
    if isinstance(node, Mapping):
        return f"{node['const']} {node.get('unit', '')}".strip()
    op, args = node[0], node[1:]
    if op == "pow":
        return f"({_render(args[0])})^{args[1]}"
    return "(" + f" {op} ".join(_render(a) for a in args) + ")"


class EstimationOrgan:
    organ_id = ORGAN_ID
    version = VERSION

    def run(self, problem, geometry, budget) -> OrganResult:
        started = time.perf_counter()
        spec = problem.payload.get("estimation_model")
        if spec is None:
            return self._fail("INSUFFICIENT_EVIDENCE", "no decomposition supplied", started)
        try:
            model = Model(spec)
        except DimensionError as exc:
            return self._fail("DIMENSION_MISMATCH", str(exc), started)
        except EstimationError as exc:
            return self._fail("MALFORMED_INPUT", str(exc), started)
        if model.result_unit.dims != model.target_unit.dims:
            return self._fail("DIMENSION_MISMATCH",
                              f"decomposition yields {model.result_unit.render()} but target is "
                              f"{model.target_unit.render()}", started)
        try:
            samples = model.sample(dependent=True)
            inputs = model._last_inputs
            independent = model.sample(dependent=False) if model.dependencies else samples
        except EstimationError as exc:
            return self._fail("MALFORMED_INPUT", str(exc), started)
        if any(not math.isfinite(x) for x in samples):
            return self._fail("MALFORMED_INPUT", "decomposition produced non-finite values (division by zero?)",
                              started)
        tail = (1 - model.interval) / 2
        s = sorted(samples)
        lo, mid, hi = _quantile(s, tail), _quantile(s, 0.5), _quantile(s, 1 - tail)
        si = sorted(independent)
        width_dep = hi - lo
        width_ind = _quantile(si, 1 - tail) - _quantile(si, tail)
        out_ranks = _ranks(samples)
        sensitivity = []
        for name in model.names:
            rank_corr = _pearson(_ranks(inputs[name]), out_ranks)
            z = _inv_normal(1 - tail)
            swing = abs(model.at({name: z}) - model.at({name: -z}))
            sensitivity.append({"variable": name, "rank_correlation": round(rank_corr, 4),
                                "swing": swing})
        sensitivity.sort(key=lambda r: -r["swing"])
        dominant = sensitivity[0]["variable"]
        reference = {"available": False, "note": "no reference class supplied"}
        notes = []
        if model.reference:
            ref = model.reference
            ref_unit = Unit.parse(ref.get("unit", ""))
            if ref_unit.dims != model.target_unit.dims:
                reference = {"available": True, "comparable": False,
                             "note": "reference class unit differs from target"}
            else:
                factor = ref_unit.scale / model.target_unit.scale
                rlo, rhi = ref["low"] * factor, ref["high"] * factor
                overlap = max(0.0, min(hi, rhi) - max(lo, rlo))
                frac = overlap / (hi - lo) if hi > lo else float(rlo <= mid <= rhi)
                reference = {"available": True, "comparable": True, "name": ref.get("name"),
                             "source": ref.get("source"), "low": rlo, "high": rhi,
                             "overlap_fraction": round(frac, 4), "outside": overlap == 0.0}
                if overlap == 0.0:
                    notes.append("inside-view interval does not overlap the reference class")
        assumptions = [f"{n}: {v['note']}" if v["note"] else f"{n}: range {v['low']}–{v['high']} is a "
                       f"{int(model.interval * 100)}% interval ({v['dist']})" for n, v in model.variables.items()]
        declared = {(a, b) for a, b, _, _ in model.dependencies}
        undeclared = [(a, b) for i, a in enumerate(model.names) for b in model.names[i + 1:]
                      if (a, b) not in declared and (b, a) not in declared]
        if undeclared:
            assumptions.append(f"assumed independent: {undeclared}")
        proof = {
            "proof_class": "estimation",
            "decomposition": f"{model.target_name} = {_render(model.expression)}",
            "units": {"target": model.target_unit_text, "canonical": model.target_unit.render(),
                      "result": model.result_unit.render(),
                      "dimension_check": "pass"},
            "inputs": [{"name": n, "unit": v["unit"].render(), "low": v["low"], "high": v["high"],
                        "dist": v["dist"]} for n, v in model.variables.items()],
            "dependencies": [{"a": a, "b": b, "rho": rho, "reason": r} for a, b, rho, r in model.dependencies],
            "dependency_effect": {"interval_width_dependent": width_dep,
                                  "interval_width_if_independent": width_ind,
                                  "ratio": (width_dep / width_ind) if width_ind else 1.0},
            "interval": model.interval, "samples": model.samples, "seed": model.seed,
            "low": lo, "median": mid, "high": hi,
            "sensitivity": sensitivity, "dominant_uncertainty": dominant,
            "reference_class": reference,
        }
        answer = {"low": lo, "median": mid, "high": hi, "unit": model.target_unit_text,
                  "interval": model.interval}
        # Inside view and outside view disagree outright: the estimate is contested,
        # not clean. The answer is kept for review; the route withholds a recommendation.
        state = "CONTESTED" if reference.get("outside") else "OK"
        return OrganResult(
            organ_id=ORGAN_ID, organ_version=VERSION, state=state, answer=answer, proof=proof,
            assumptions=tuple(assumptions),
            uncertainty=f"{int(model.interval * 100)}% interval [{lo:.4g}, {hi:.4g}] {model.target_unit_text}; "
                        f"dominant uncertainty: {dominant}",
            expenditure=Expenditure(seconds=time.perf_counter() - started),
            dependencies=("python-stdlib",), origin="deterministic", notes=tuple(notes))

    def _fail(self, state: str, why: str, started: float) -> OrganResult:
        return OrganResult(organ_id=ORGAN_ID, organ_version=VERSION, state=state, answer=None,
                           proof={"proof_class": "estimation", "failure": why},
                           uncertainty="not estimated",
                           expenditure=Expenditure(seconds=time.perf_counter() - started),
                           dependencies=("python-stdlib",), notes=(why,))
