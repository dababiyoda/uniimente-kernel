"""Layer 3 intelligences, batch C: mechanism design, verification, control, synthesis, causal, experiment design.

Six executables on GREG's one cognition path (``greg.cognition.cortex.reason`` -> isolated worker ->
independent verifier -> CognitiveReceipt). Each is an ordinary, well-understood method; the genome records
where it is natively competent, what it is compared against and how its output is checked.

* ``mech_vcg`` (``vcg_allocate_units``): Vickrey-Clarke-Groves allocation of k identical units with
  Clarke-pivot payments. Truthful reporting is a dominant strategy under private values, so participants
  need not out-guess one another; the score is allocative efficiency (welfare), never revenue taken from
  people. Verified by an independent NumPy dynamic program (optimality, externalities, IR).
* ``verify_modelcheck`` (``model_check_safety``): explicit-state breadth-first model checking of a bounded,
  typed JSON guarded-command language (no code is ever evaluated). SAFE with the reachable-state count and
  digest, or the shortest counterexample. Verified by trace replay (an independent interpreter) or an
  independent NumPy level-synchronous recount of the reachable set.
* ``control_mpc`` (``mpc_track``): linear model-predictive control of a double integrator with input
  bounds: one small box-constrained QP per step, solved exactly as bounded least squares (SciPy BVLS), with
  the discrete-ARE cost-to-go as terminal cost. Verified by independent re-simulation of the inputs.
* ``synth_cegis`` (``cegis_synthesize``): counterexample-guided inductive synthesis of a bounded integer
  linear threshold rule that must hold on every point of a finite Boolean domain. Z3 synthesises from a
  growing counterexample set; an exhaustive NumPy check over all 2^n points is the oracle. Verified by an
  independent exhaustive check (or an independent MILP infeasibility proof for UNREALIZABLE).
* ``causal_backdoor`` (``backdoor_ate``): average treatment effect by backdoor adjustment (stratification
  for discrete covariates, regression adjustment with interactions otherwise) after checking the declared
  adjustment set against the backdoor criterion (d-separation on the declared DAG); it abstains when the
  set fails. Verified by an independent Bayes-ball d-separation and an independent recomputation.
* ``info_experiment`` (``design_test_sequence``): adaptive experiment selection by greedy expected
  information gain over a discrete hypothesis prior with known likelihood tables, returned as a policy
  tree. Verified by recomputing every node's posterior and information gain in log space.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output
of any method here creates authority.
"""
from __future__ import annotations

from collections import deque
import hashlib
from itertools import product
import math
import operator
import random
import statistics
import time

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int, finite

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "greg/cognition/solvers.py (GREG's existing bounded solvers)")


def _common(**kw):
    return dict(buildability="BUILDABLE_NOW", memory_model="stateless",
                learning_rule="none (competence settles per geometry through GREG outcomes)", lineage=LINEAGE, **kw)


def _abstain(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="ABSTAIN", missing=[reason])


def _unknown(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="UNKNOWN", missing=[reason])


def _obj(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be an object")
    return data


def _is_num(x):
    return type(x) in (int, float) and math.isfinite(x)


# =================================================================== 1. VCG allocation of identical units
VCG_MAX_BIDDERS, VCG_MAX_UNITS, VCG_MAX_DEMAND, VCG_MAX_VALUE = 50, 200, 20, 1e6
VCG_DP_OPS = 3_000_000                     # (n + 1) welfare DPs of n * k * demand steps for general valuations
VCG_CLASSES = ("strong", "weak")


def _vcg(data):
    _obj(data)
    k = bounded_int(data.get("units"), low=1, high=VCG_MAX_UNITS, name="units")
    bidders = data.get("bidders")
    if not isinstance(bidders, list) or not 1 <= len(bidders) <= VCG_MAX_BIDDERS:
        raise GenomeError(f"bidders: a list of 1-{VCG_MAX_BIDDERS} bidders")
    values = []
    for b in bidders:
        v = b.get("values") if isinstance(b, dict) else None
        if not isinstance(v, list) or not 1 <= len(v) <= VCG_MAX_DEMAND:
            raise GenomeError(f"each bidder reports 1-{VCG_MAX_DEMAND} marginal values")
        values.append([finite(x, low=0.0, high=VCG_MAX_VALUE, name="marginal value") for x in v])
    return k, values


def _cum(v):
    out = [0.0]
    for x in v:
        out.append(out[-1] + x)
    return out


def _vcg_greedy(values, k, skip=None):
    """Diminishing marginal values: the welfare optimum takes the k highest positive marginals."""
    pool = sorted((-x, i, j) for i, v in enumerate(values) if i != skip for j, x in enumerate(v) if x > 0)
    q = [0] * len(values)
    welfare = 0.0
    for neg, i, _ in pool[:k]:
        q[i] += 1
        welfare -= neg
    return welfare, q, pool


def _vcg_dp(values, k, skip=None):
    """General valuations V_i(q) = sum of the first q marginals: exact DP over bidders and units."""
    best = [0.0] * (k + 1)
    choices = []
    for i, v in enumerate(values):
        if i == skip:
            choices.append(None)
            continue
        cum = _cum(v)
        new, ch = best[:], [0] * (k + 1)
        for u in range(1, k + 1):
            for q in range(1, min(u, len(v)) + 1):
                c = best[u - q] + cum[q]
                if c > new[u] + 1e-12:
                    new[u], ch[u] = c, q
        best = new
        choices.append(ch)
    q, u = [0] * len(values), k
    for i in range(len(values) - 1, -1, -1):
        if choices[i] is not None:
            q[i] = choices[i][u]
            u -= q[i]
    return best[k], q


def vcg_solve(data, budget):
    k, values = _vcg(data)
    if data.get("budgets") is not None:
        return _abstain("bidder budget constraints break VCG's dominant-strategy truthfulness")
    if data.get("value_model", "private") != "private":
        return _abstain("interdependent or common values: VCG is neither truthful nor efficient there")
    n = len(values)
    concave = all(v[j] >= v[j + 1] for v in values for j in range(len(v) - 1))
    if concave:
        welfare, q, pool = _vcg_greedy(values, k)
        without = [_vcg_greedy(values, k, skip=i)[0] for i in range(n)]
        method = "Clarke-pivot VCG; welfare optimum = k highest pooled marginals (diminishing marginal values)"
        clearing = -pool[min(k, len(pool)) - 1][0] if pool else 0.0
        rejected = -pool[k][0] if len(pool) > k else 0.0
    else:
        if (n + 1) * n * k * max(len(v) for v in values) > VCG_DP_OPS:
            return _abstain("non-diminishing valuations exceed the bounded DP size", bidders=n, units=k)
        welfare, q = _vcg_dp(values, k)
        without = [_vcg_dp(values, k, skip=i)[0] for i in range(n)]
        method = "Clarke-pivot VCG; welfare optimum by exact DP over bidders (general quantity valuations)"
        clearing = rejected = None
    own = [_cum(values[i])[q[i]] for i in range(n)]
    pay = []
    for i in range(n):
        p = without[i] - (welfare - own[i])           # the externality bidder i imposes on the others
        pay.append(0.0 if abs(p) < 1e-9 else p)
    return answer({"mechanism": "vcg", "allocation": q, "payments": pay, "welfare": welfare,
                   "revenue": sum(pay), "efficient": True},
                  {"method": method, "reports": "truthful: a dominant strategy under private values, quasi-linear "
                   "utility and no budgets", "welfare_without_bidder": without, "clearing_value": clearing,
                   "highest_rejected_value": rejected, "units_allocated": sum(q), "objective": "allocative "
                   "efficiency (sum of values), not revenue"})


def _np_welfare(values, k, skip=None):
    """Independent optimum: vectorised DP best[u] = max over q of best_prev[u - q] + V_i(q)."""
    import numpy as np
    best = np.zeros(k + 1)
    for i, v in enumerate(values):
        if i == skip:
            continue
        cum = np.concatenate(([0.0], np.cumsum(np.asarray(v, dtype=float))))
        new = best.copy()
        for q in range(1, min(k, len(v)) + 1):
            np.maximum(new[q:], best[:k + 1 - q] + cum[q], out=new[q:])
        best = new
    return float(best[k])


def _vcg_shape(values, k, output):
    if not isinstance(output, dict):
        return None
    q, pay = output.get("allocation"), output.get("payments")
    n = len(values)
    if (not isinstance(q, list) or len(q) != n or not isinstance(pay, list) or len(pay) != n
            or any(type(x) is not int or not 0 <= x <= len(values[i]) for i, x in enumerate(q))
            or sum(q) > k or not all(_is_num(p) for p in pay)):
        return None
    return q, pay


def vcg_verify(data, output, certificate):
    k, values = _vcg(data)
    shape = _vcg_shape(values, k, output)
    if shape is None:
        return {"allocation_and_payments_well_formed": False}
    q, pay = shape
    own = [math.fsum(values[i][:q[i]]) for i in range(len(values))]
    opt = _np_welfare(values, k)
    tol = 1e-6 * max(1.0, opt)
    welfare = math.fsum(own)
    claimed = output.get("welfare")
    ext = [_np_welfare(values, k, skip=i) - (opt - own[i]) for i in range(len(values))]
    return {"allocation_and_payments_well_formed": True,
            "welfare_recomputed": _is_num(claimed) and abs(claimed - welfare) <= tol,
            "allocatively_optimal_by_independent_dp": welfare >= opt - tol,
            "payments_equal_clarke_externalities": all(abs(p - e) <= tol for p, e in zip(pay, ext)),
            "individually_rational": all(p <= o + tol for p, o in zip(pay, own)),
            "no_subsidy": all(p >= -tol for p in pay)}


def _vcg_draw(r, spec):
    m = r.randint(1, spec["max_units"])
    v = [round(r.uniform(0.0, spec["high"]), 2)]
    for _ in range(m - 1):
        v.append(round(v[-1] * r.uniform(*spec["decay"]), 2))
    return v


def _pab_shading(prior, counts, k, seed):
    """Class-symmetric linear bid shading in a pay-as-bid auction: damped iterated best response, simulated.

    Each class best-responds (grid 0.30..1.00, step 0.025) to the current shading of everyone else on 300
    seeded draws of the whole profile; 12 damped rounds. A model of strategic bidders, not observed people.
    """
    import numpy as np
    rng = np.random.default_rng(seed)
    reps, width = 300, max(prior[c]["max_units"] for c in VCG_CLASSES)
    draws = {}
    for c in VCG_CLASSES:
        nc, spec = counts[c], prior[c]
        if nc == 0:
            continue
        m = rng.integers(1, spec["max_units"] + 1, size=(reps, nc))
        v = np.zeros((reps, nc, width))
        v[:, :, 0] = rng.uniform(0.0, spec["high"], size=(reps, nc))
        for j in range(1, width):
            v[:, :, j] = v[:, :, j - 1] * rng.uniform(*spec["decay"], size=(reps, nc))
        draws[c] = v * (np.arange(width)[None, None, :] < m[:, :, None])
    grid = np.round(np.arange(0.30, 1.0 + 1e-9, 0.025), 4)
    shade = {c: 0.8 for c in draws}
    for _ in range(12):
        new = {}
        for c in draws:
            others = np.concatenate([shade[c2] * (draws[c2][:, 1:, :] if c2 == c else draws[c2]).reshape(reps, -1)
                                     for c2 in draws], axis=1)
            padded = np.zeros((reps, max(k, others.shape[1])))
            padded[:, :others.shape[1]] = others
            top = -np.sort(-padded, axis=1)[:, :k]            # the k highest competing bids, descending
            dv = draws[c][:, 0, :]
            utility = []
            for x in grid:
                win = np.zeros((reps, width), dtype=bool)
                for qq in range(1, min(width, k) + 1):        # q-th own unit beats the (k - q + 1)-th rival bid
                    win[:, qq - 1] = x * dv[:, qq - 1] > top[:, k - qq]
                win = np.cumprod(win, axis=1).astype(bool)
                utility.append(float(((1.0 - x) * dv * win).sum(axis=1).mean()))
            new[c] = float(grid[int(np.argmax(utility))])
        shade = {c: round(0.5 * shade[c] + 0.5 * new[c], 4) for c in draws}
    return shade


def vcg_instance(seed):
    r = random.Random(1_700_000 + seed)
    prior = {"strong": {"high": 100.0, "decay": [0.55, 0.95], "max_units": 3},
             "weak": {"high": r.choice([45.0, 60.0]), "decay": [0.6, 1.0], "max_units": 2}}
    counts = {"strong": r.randint(2, 4), "weak": r.randint(2, 6)}
    bidders = [{"class": c, "values": _vcg_draw(r, prior[c])} for c in VCG_CLASSES for _ in range(counts[c])]
    r.shuffle(bidders)
    demand = sum(len(b["values"]) for b in bidders)
    k = max(1, round(demand * r.uniform(0.35, 0.65)))
    shading = _pab_shading(prior, counts, k, 900_000 + seed)
    data = {"units": k, "bidders": bidders, "value_model": "private",
            "prior": {**prior, "counts": counts},
            "behavior": {"pay_as_bid_shading": shading,
                         "pay_as_bid_model": "class-symmetric linear shading, simulated damped iterated best "
                                             "response (300 draws, grid 0.025, 12 rounds)",
                         "vcg_model": "truthful (dominant strategy)",
                         "posted_price_model": "each bidder buys its utility-maximising quantity at the price"},
            "seed": 17_000 + seed}
    values = [b["values"] for b in bidders]
    return data, {"optimal_welfare": _vcg_dp(values, k)[0]}


def vcg_subregion(data):
    demand = sum(len(b["values"]) for b in data["bidders"])
    return "scarce" if data["units"] <= 0.45 * demand else "moderate"


def vcg_score(data, truth, output):
    if output is None:
        return {"quality": 0.0, "category": "abstain"}
    k, values = _vcg(data)
    shape = _vcg_shape(values, k, output)
    if shape is None:
        return {"quality": -1.0, "category": "wrong"}          # infeasible or malformed allocation
    q, pay = shape
    own = [math.fsum(values[i][:q[i]]) for i in range(len(values))]
    if any(p > o + 1e-6 or p < -1e-6 for p, o in zip(pay, own)):
        return {"quality": -1.0, "category": "wrong"}          # charges a participant more than its value
    opt = truth["optimal_welfare"]
    eff = math.fsum(own) / opt if opt > 0 else 1.0
    if output.get("efficient") is True and eff < 1.0 - 1e-9:
        return {"quality": -1.0, "category": "wrong"}          # a false efficiency claim
    return {"quality": eff, "category": "correct"}


def vcg_pay_as_bid(data):
    """Baseline: discriminatory (pay-as-bid) auction; bidders shade by their class's simulated factor."""
    k, values = _vcg(data)
    shade = (data.get("behavior") or {}).get("pay_as_bid_shading")
    classes = [b.get("class") for b in data["bidders"]]
    if not isinstance(shade, dict) or any(not _is_num(shade.get(c)) or not 0 < shade[c] <= 1 for c in classes):
        raise GenomeError("pay-as-bid behaviour model missing")
    bids = sorted((-(shade[classes[i]] * x), i, j) for i, v in enumerate(values) for j, x in enumerate(v) if x > 0)
    q, pay = [0] * len(values), [0.0] * len(values)
    for neg, i, _ in bids[:k]:
        q[i] += 1
        pay[i] -= neg
    return {"mechanism": "pay_as_bid", "allocation": q, "payments": pay}


def vcg_posted_price(data):
    """Competitor: posted price at the median of the seeded value prior; random-arrival rationing."""
    k, values = _vcg(data)
    prior = data.get("prior")
    if not isinstance(prior, dict) or not isinstance(prior.get("counts"), dict):
        raise GenomeError("value prior missing")
    r = random.Random(bounded_int(data.get("seed"), low=0, high=10**9, name="seed"))
    sample = []
    while len(sample) < 4000:
        for c in VCG_CLASSES:
            for _ in range(prior["counts"].get(c, 0)):
                sample.extend(x for x in _vcg_draw(r, prior[c]) if x > 0)
    price = statistics.median(sample)
    order = list(range(len(values)))
    r.shuffle(order)
    left, q = k, [0] * len(values)
    for i in order:
        cum = _cum(values[i])
        want = max(range(len(cum)), key=lambda m: (cum[m] - m * price, -m))
        q[i] = min(want, left)
        left -= q[i]
    return {"mechanism": "posted_price", "price": price, "allocation": q, "payments": [x * price for x in q]}


# =================================================================== 2. explicit-state safety model checking
MC_MAX_VARS, MC_MAX_CMDS, MC_MAX_NODES, MC_MAX_VALUE, MC_MAX_INIT = 16, 64, 4000, 100_000, 4096
MC_NATIVE_STATES = 50_000
MC_MAX_TRACE = 1000
MC_BMC_DEPTH, MC_Z3_SECONDS = 15, 4.0       # one total wall-clock budget across every Z3 check
MC_MAX_MAGNITUDE = 2 ** 62                   # every intermediate value fits int64 (the NumPy verifier's type)
MC_WALK_STEPS, MC_WALK_LENGTH = 10_000, 250
_CMP = {"==": operator.eq, "!=": operator.ne, "<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge}
_RESERVED = {"+", "-", "*", "mod", "min", "max", "and", "or", "not", "implies", "ite", "true", "false"} | set(_CMP)


def _mc_type(expr, names, counter, depth=0):
    """Type-check one expression of the guarded-command language: 'int' or 'bool'. Nothing is evaluated."""
    counter[0] += 1
    if counter[0] > MC_MAX_NODES or depth > 64:
        raise GenomeError(f"expressions exceed {MC_MAX_NODES} nodes or depth 64")
    if type(expr) is bool:
        return "bool"
    if type(expr) is int:
        bounded_int(expr, low=-MC_MAX_VALUE, high=MC_MAX_VALUE, name="integer literal")
        return "int"
    if isinstance(expr, str):
        if expr not in names:
            raise GenomeError(f"unknown variable {expr!r}")
        return "int"
    if not isinstance(expr, list) or not expr or not isinstance(expr[0], str):
        raise GenomeError("expression: integer, true/false, variable name or [operator, argument, ...]")
    op, args = expr[0], expr[1:]
    kinds = [_mc_type(a, names, counter, depth + 1) for a in args]
    ints, bools = all(k == "int" for k in kinds), all(k == "bool" for k in kinds)
    if op in ("+", "min", "max") and len(args) >= 2 and ints:
        return "int"
    if op == "-" and len(args) in (1, 2) and ints:
        return "int"
    if op == "*" and len(args) == 2 and ints and (type(args[0]) is int or type(args[1]) is int):
        return "int"                                    # linear: one factor is a literal
    if op == "mod" and len(args) == 2 and ints and type(args[1]) is int and args[1] >= 1:
        return "int"                                    # modulus is a positive literal
    if op in _CMP and len(args) == 2 and ints:
        return "bool"
    if op in ("and", "or") and len(args) >= 1 and bools:
        return "bool"
    if op == "not" and len(args) == 1 and bools:
        return "bool"
    if op == "implies" and len(args) == 2 and bools:
        return "bool"
    if op == "ite" and len(args) == 3 and kinds[0] == "bool" and kinds[1] == kinds[2]:
        return kinds[1]
    raise GenomeError(f"ill-typed or unknown operator {op!r} with {len(args)} arguments")


def _mc_mag(expr, mags):
    """Static bound on |value| of a type-checked expression; refuses one that could leave int64.

    The solver evaluates with Python integers and the verifier with NumPy int64, so the two semantics
    agree only when every intermediate value is provably in range.
    """
    t = type(expr)
    if t is bool:
        return 1
    if t is int:
        return abs(expr)
    if t is str:
        return mags[expr]
    op, sub = expr[0], [_mc_mag(a, mags) for a in expr[1:]]
    if op in ("+", "-"):
        out = sum(sub)
    elif op == "*":
        out = sub[0] * sub[1]
    elif op == "mod":
        out = abs(expr[2]) - 1
    elif op in ("min", "max"):
        out = max(sub)
    elif op == "ite":
        out = max(sub[1], sub[2])
    else:
        out = 1                                          # comparison or connective: a boolean
    if out > MC_MAX_MAGNITUDE:
        raise GenomeError("an expression can exceed 2^62 in magnitude; rescale the model")
    return out


def _mc_system(data):
    _obj(data)
    sysd = data.get("system")
    if not isinstance(sysd, dict):
        raise GenomeError("system: {variables, commands, invariant}")
    variables = sysd.get("variables")
    if not isinstance(variables, list) or not 1 <= len(variables) <= MC_MAX_VARS:
        raise GenomeError(f"system.variables: 1-{MC_MAX_VARS} bounded integer variables")
    names, lo, hi, inits = [], [], [], []
    for v in variables:
        name = v.get("name") if isinstance(v, dict) else None
        if (not isinstance(name, str) or not name.isidentifier() or len(name) > 32 or name in _RESERVED
                or name in names):
            raise GenomeError("variable names: unique identifiers of <= 32 characters, not operator names")
        a = bounded_int(v.get("min"), low=-MC_MAX_VALUE, high=MC_MAX_VALUE, name=f"{name}.min")
        b = bounded_int(v.get("max"), low=a, high=MC_MAX_VALUE, name=f"{name}.max")
        init = v.get("init")
        init = [init] if type(init) is int else init
        if not isinstance(init, list) or not 1 <= len(init) <= 64:
            raise GenomeError(f"{name}.init: an integer or a list of 1-64 integers")
        names.append(name)
        lo.append(a)
        hi.append(b)
        inits.append(sorted({bounded_int(x, low=a, high=b, name=f"{name}.init") for x in init}))
    if math.prod(len(i) for i in inits) > MC_MAX_INIT:
        raise GenomeError(f"more than {MC_MAX_INIT} initial states")
    index = {n: i for i, n in enumerate(names)}
    counter = [0]
    commands = sysd.get("commands")
    if not isinstance(commands, list) or not 1 <= len(commands) <= MC_MAX_CMDS:
        raise GenomeError(f"system.commands: 1-{MC_MAX_CMDS} guarded commands")
    cmds, seen = [], set()
    for c in commands:
        cname = c.get("name") if isinstance(c, dict) else None
        if not isinstance(cname, str) or not 1 <= len(cname) <= 64 or cname in seen:
            raise GenomeError("command names: unique strings of 1-64 characters")
        seen.add(cname)
        guard = c.get("guard", True)
        if _mc_type(guard, index, counter) != "bool":
            raise GenomeError(f"{cname}: guard must be boolean")
        update = c.get("update")
        if not isinstance(update, dict):
            raise GenomeError(f"{cname}: update is an object variable -> integer expression")
        ups = []
        for var, e in update.items():
            if var not in index or _mc_type(e, index, counter) != "int":
                raise GenomeError(f"{cname}: update of {var!r} must assign an integer expression to a variable")
            ups.append((index[var], e))
        cmds.append((cname, guard, tuple(sorted(ups, key=lambda u: u[0]))))
    inv = sysd.get("invariant")
    if _mc_type(inv, index, counter) != "bool":
        raise GenomeError("invariant must be boolean")
    mags = {n: max(abs(a), abs(b)) for n, a, b in zip(names, lo, hi)}
    for _, guard, ups in cmds:
        _mc_mag(guard, mags)
        for _, e in ups:
            _mc_mag(e, mags)
    _mc_mag(inv, mags)
    return {"names": names, "index": index, "lo": lo, "hi": hi, "inits": inits, "commands": cmds, "invariant": inv}


def _mc_compile(expr, index):
    """Expression -> closure over a state tuple (a fixed operator table; no code evaluation)."""
    if type(expr) in (bool, int):
        const = expr
        return lambda s: const
    if isinstance(expr, str):
        i = index[expr]
        return lambda s: s[i]
    op, fs = expr[0], [_mc_compile(a, index) for a in expr[1:]]
    if op == "+":
        if len(fs) == 2:
            a, b = fs
            return lambda s: a(s) + b(s)
        return lambda s: sum(f(s) for f in fs)
    if op == "-":
        if len(fs) == 1:
            a = fs[0]
            return lambda s: -a(s)
        a, b = fs
        return lambda s: a(s) - b(s)
    if op in ("*", "mod") or op in _CMP or op == "implies":
        a, b = fs
        fn = {"*": operator.mul, "mod": operator.mod, "implies": lambda x, y: (not x) or y}.get(op) or _CMP[op]
        return lambda s: fn(a(s), b(s))
    if op == "min":
        return lambda s: min(f(s) for f in fs)
    if op == "max":
        return lambda s: max(f(s) for f in fs)
    if op == "and":
        if len(fs) == 2:
            a, b = fs
            return lambda s: a(s) and b(s)
        return lambda s: all(f(s) for f in fs)
    if op == "or":
        if len(fs) == 2:
            a, b = fs
            return lambda s: a(s) or b(s)
        return lambda s: any(f(s) for f in fs)
    if op == "not":
        a = fs[0]
        return lambda s: not a(s)
    c, a, b = fs                                                   # ite
    return lambda s: a(s) if c(s) else b(s)


def _mc_compiled(sysm):
    idx = sysm["index"]
    cmds = [(name, _mc_compile(g, idx), tuple((i, _mc_compile(e, idx)) for i, e in ups))
            for name, g, ups in sysm["commands"]]
    return cmds, _mc_compile(sysm["invariant"], idx)


def _mc_step(cmds, lo, hi, s):
    out = []
    for ci, (_, g, ups) in enumerate(cmds):
        if not g(s):
            continue
        t = list(s)
        for i, f in ups:
            v = f(s)
            if v < lo[i] or v > hi[i]:
                break                                   # an update leaving a range disables the command
            t[i] = v
        else:
            out.append((ci, tuple(t)))
    return out


def _mc_digest(states):
    h = hashlib.sha256()
    for s in sorted(states):
        h.update((",".join(map(str, s)) + ";").encode())
    return "sha256:" + h.hexdigest()


def mc_solve(data, budget):
    sysm = _mc_system(data)
    if data.get("property", "safety") != "safety":
        return _abstain("only safety invariants are in this checker's competence (no liveness or LTL)")
    cmds, inv = _mc_compiled(sysm)
    lo, hi = sysm["lo"], sysm["hi"]
    deadline = time.perf_counter() + max(0.5, float((budget or {}).get("latency_s", 5.0)))
    parent = {}
    level, depth = [], 0

    def trace(t):
        steps, s = [], t
        while parent[s] is not None:
            s, ci = parent[s]
            steps.append(cmds[ci][0])
        steps.reverse()
        if len(steps) > MC_MAX_TRACE:
            return _unknown(f"shortest counterexample longer than {MC_MAX_TRACE} steps")
        return answer({"verdict": "UNSAFE", "initial": list(s), "commands": steps, "violating_state": list(t),
                       "depth": len(steps)},
                      {"method": "breadth-first explicit-state search; the first violation found is a shortest "
                                 "counterexample", "states_explored": len(parent), "state_order": sysm["names"]})

    for s0 in product(*sysm["inits"]):
        if s0 not in parent:
            parent[s0] = None
            if not inv(s0):
                return trace(s0)
            level.append(s0)
    while level:
        nxt = []
        for s in level:
            for ci, t in _mc_step(cmds, lo, hi, s):
                if t in parent:
                    continue
                parent[t] = (s, ci)
                if not inv(t):
                    return trace(t)
                nxt.append(t)
            if len(parent) > MC_NATIVE_STATES:
                return _abstain(f"reachable state space exceeds {MC_NATIVE_STATES} states (state explosion)",
                                states_explored=len(parent), depth_completed=depth)
            if time.perf_counter() > deadline:
                return _unknown("latency budget exhausted", states_explored=len(parent))
        level = nxt
        depth += 1 if nxt else 0
    return answer({"verdict": "SAFE", "reachable_states": len(parent)},
                  {"method": "breadth-first explicit-state search to a fixed point (every reachable state checked)",
                   "reachable_states": len(parent), "max_depth": depth, "state_digest": _mc_digest(parent),
                   "state_order": sysm["names"]})


def _mc_eval(expr, env):
    """Independent recursive interpreter (truth, replay and scoring), separate from the closure compiler."""
    t = type(expr)
    if t is bool or t is int:
        return expr
    if t is str:
        return env[expr]
    op = expr[0]
    if op == "ite":
        return _mc_eval(expr[2] if _mc_eval(expr[1], env) else expr[3], env)
    if op == "and":
        return all(_mc_eval(a, env) for a in expr[1:])
    if op == "or":
        return any(_mc_eval(a, env) for a in expr[1:])
    if op == "not":
        return not _mc_eval(expr[1], env)
    if op == "implies":
        return (not _mc_eval(expr[1], env)) or _mc_eval(expr[2], env)
    vals = [_mc_eval(a, env) for a in expr[1:]]
    if op == "+":
        return sum(vals)
    if op == "-":
        return -vals[0] if len(vals) == 1 else vals[0] - vals[1]
    if op == "*":
        return vals[0] * vals[1]
    if op == "mod":
        return vals[0] % vals[1]
    if op == "min":
        return min(vals)
    if op == "max":
        return max(vals)
    return _CMP[op](vals[0], vals[1])


def _mc_succ_interp(sysm, state):
    env = dict(zip(sysm["names"], state))
    out = []
    for cname, guard, ups in sysm["commands"]:
        if not _mc_eval(guard, env):
            continue
        nxt, ok = list(state), True
        for i, e in ups:
            v = _mc_eval(e, env)
            if not sysm["lo"][i] <= v <= sysm["hi"][i]:
                ok = False
                break
            nxt[i] = v
        if ok:
            out.append((cname, tuple(nxt)))
    return out


def _mc_dfs_truth(sysm, cap):
    """Independent depth-first enumeration of every reachable state with the interpreter (no early exit)."""
    seen, stack = set(), []
    for s0 in product(*sysm["inits"]):
        if s0 not in seen:
            seen.add(s0)
            stack.append(s0)
    safe = True
    while stack:
        s = stack.pop()
        if not _mc_eval(sysm["invariant"], dict(zip(sysm["names"], s))):
            safe = False
        for _, t in _mc_succ_interp(sysm, s):
            if t not in seen:
                seen.add(t)
                if len(seen) > cap:
                    return None
                stack.append(t)
    return {"safe": safe, "reachable_states": len(seen), "digest": _mc_digest(seen)}


def _mc_replay(sysm, output):
    initial, commands, final = output.get("initial"), output.get("commands"), output.get("violating_state")
    n = len(sysm["names"])
    if (not isinstance(initial, list) or len(initial) != n or any(type(x) is not int for x in initial)
            or not isinstance(commands, list) or len(commands) > MC_MAX_TRACE):
        return {"trace_well_formed": False}
    allowed = all(x in init for x, init in zip(initial, sysm["inits"]))
    by_name = {c[0]: c for c in sysm["commands"]}
    s, replays = tuple(initial), True
    for name in commands:
        cmd = by_name.get(name) if isinstance(name, str) else None
        if cmd is None:
            replays = False
            break
        env = dict(zip(sysm["names"], s))
        if not _mc_eval(cmd[1], env):
            replays = False
            break
        nxt = list(s)
        for i, e in cmd[2]:
            v = _mc_eval(e, env)
            if not sysm["lo"][i] <= v <= sysm["hi"][i]:
                replays = False
                break
            nxt[i] = v
        if not replays:
            break
        s = tuple(nxt)
    return {"trace_well_formed": True, "initial_state_allowed": allowed, "trace_replays": replays,
            "final_state_matches": replays and isinstance(final, list) and list(s) == final,
            "ends_in_violation": replays and not _mc_eval(sysm["invariant"], dict(zip(sysm["names"], s)))}


def _mc_vec(expr, cols, size):
    """Vectorised NumPy evaluation over many states at once (the verifier's own semantics)."""
    import numpy as np
    t = type(expr)
    if t is bool:
        return np.full(size, expr, dtype=bool)
    if t is int:
        return np.full(size, expr, dtype=np.int64)
    if t is str:
        return cols[expr]
    op, args = expr[0], [_mc_vec(a, cols, size) for a in expr[1:]]
    if op == "+":
        out = args[0]
        for a in args[1:]:
            out = out + a
        return out
    if op == "-":
        return -args[0] if len(args) == 1 else args[0] - args[1]
    if op == "*":
        return args[0] * args[1]
    if op == "mod":
        return np.mod(args[0], args[1])
    if op == "min":
        return np.minimum.reduce(args)
    if op == "max":
        return np.maximum.reduce(args)
    if op == "and":
        return np.logical_and.reduce(args)
    if op == "or":
        return np.logical_or.reduce(args)
    if op == "not":
        return ~args[0]
    if op == "implies":
        return ~args[0] | args[1]
    if op == "ite":
        return np.where(args[0], args[1], args[2])
    return {"==": np.equal, "!=": np.not_equal, "<": np.less, "<=": np.less_equal, ">": np.greater,
            ">=": np.greater_equal}[op](args[0], args[1])


def _mc_np_reach(sysm, cap):
    """Independent level-synchronous reachability over arrays of states; None if beyond the cap."""
    import numpy as np
    names, lo, hi = sysm["names"], sysm["lo"], sysm["hi"]
    radix = [h - l + 1 for l, h in zip(lo, hi)]
    if math.prod(radix) >= 2 ** 62:
        return None
    mult = [math.prod(radix[i + 1:]) for i in range(len(radix))]
    lo_a, mult_a = np.array(lo, dtype=np.int64), np.array(mult, dtype=np.int64)

    def encode(arr):
        return ((arr - lo_a) * mult_a).sum(axis=1)

    frontier = np.array(list(product(*sysm["inits"])), dtype=np.int64).reshape(-1, len(names))
    seen, keep = np.unique(encode(frontier), return_index=True)
    frontier = frontier[keep]
    layers = [frontier]
    while len(frontier):
        cols = {n: frontier[:, i] for i, n in enumerate(names)}
        cand = []
        for _, guard, ups in sysm["commands"]:
            g = _mc_vec(guard, cols, len(frontier))
            if not g.any():
                continue
            sub = {n: c[g] for n, c in cols.items()}
            nxt, ok = frontier[g].copy(), np.ones(int(g.sum()), dtype=bool)
            for i, e in ups:
                val = _mc_vec(e, sub, len(nxt))
                ok &= (val >= lo[i]) & (val <= hi[i])
                nxt[:, i] = val
            cand.append(nxt[ok])
        if not cand:
            break
        cand = np.concatenate(cand)
        codes, first = np.unique(encode(cand), return_index=True)
        fresh = ~np.isin(codes, seen)
        frontier = cand[first[fresh]]
        seen = np.union1d(seen, codes[fresh])
        if len(seen) > cap:
            return None
        layers.append(frontier)
    states = np.concatenate(layers)
    cols = {n: states[:, i] for i, n in enumerate(names)}
    holds = bool(_mc_vec(sysm["invariant"], cols, len(states)).all())
    return {"count": len(states), "digest": _mc_digest(map(tuple, states.tolist())), "invariant_holds": holds}


def mc_verify(data, output, certificate):
    sysm = _mc_system(data)
    verdict = output.get("verdict") if isinstance(output, dict) else None
    if verdict == "UNSAFE":
        return _mc_replay(sysm, output)
    if verdict == "SAFE":
        reach = _mc_np_reach(sysm, 4 * MC_NATIVE_STATES)
        if reach is None:
            return {"independent_recount_feasible": False}
        return {"independent_recount_feasible": True,
                "reachable_count_matches": reach["count"] == output.get("reachable_states"),
                "reachable_set_digest_matches": reach["digest"] == (certificate or {}).get("state_digest"),
                "invariant_holds_on_every_reachable_state": reach["invariant_holds"]}
    return {"verdict_is_safe_or_unsafe": False}


def mc_score(data, truth, output):
    if output is None:
        return {"quality": 0.0, "category": "abstain"}
    verdict = output.get("verdict") if isinstance(output, dict) else None
    if verdict == "SAFE":
        ok = truth["safe"]
    elif verdict == "UNSAFE":
        ok = all(_mc_replay(_mc_system(data), output).values())     # a replayed counterexample is a proof
    else:
        return {"quality": -1.0, "category": "wrong"}
    return {"quality": 1.0, "category": "correct"} if ok else {"quality": -1.0, "category": "wrong"}


def mc_random_walk(data):
    """Baseline: random-walk testing with a 10,000-step budget; no violation seen is reported as SAFE."""
    sysm = _mc_system(data)
    if data.get("property", "safety") != "safety":
        return None
    cmds, inv = _mc_compiled(sysm)
    r = random.Random(bounded_int(data.get("seed", 0), low=0, high=10**9, name="seed") * 7919 + 13)
    inits = list(product(*sysm["inits"]))
    steps = 0
    while steps < MC_WALK_STEPS:
        s0 = s = r.choice(inits)
        names = []
        if not inv(s):
            return {"verdict": "UNSAFE", "initial": list(s0), "commands": [], "violating_state": list(s)}
        for _ in range(MC_WALK_LENGTH):
            succ = _mc_step(cmds, sysm["lo"], sysm["hi"], s)
            steps += 1
            if not succ or steps > MC_WALK_STEPS:
                break
            ci, s = r.choice(succ)
            names.append(cmds[ci][0])
            if not inv(s):
                return {"verdict": "UNSAFE", "initial": list(s0), "commands": names, "violating_state": list(s)}
    return {"verdict": "SAFE", "method": f"random testing: no violation in {MC_WALK_STEPS} steps"}


def _mc_z3(expr, xs, index):
    import z3
    t = type(expr)
    if t is bool:
        return z3.BoolVal(expr)
    if t is int:
        return z3.IntVal(expr)
    if t is str:
        return xs[index[expr]]
    op, a = expr[0], [_mc_z3(e, xs, index) for e in expr[1:]]
    if op == "+":
        return z3.Sum(a)
    if op == "-":
        return -a[0] if len(a) == 1 else a[0] - a[1]
    if op == "*":
        return a[0] * a[1]
    if op == "mod":
        return a[0] % a[1]
    if op in ("min", "max"):
        out = a[0]
        for b in a[1:]:
            out = z3.If(out <= b, out, b) if op == "min" else z3.If(out >= b, out, b)
        return out
    if op == "and":
        return z3.And(a)
    if op == "or":
        return z3.Or(a)
    if op == "not":
        return z3.Not(a[0])
    if op == "implies":
        return z3.Implies(a[0], a[1])
    if op == "ite":
        return z3.If(a[0], a[1], a[2])
    return _CMP[op](a[0], a[1])


def mc_bmc_kinduction(data):
    """Competitor: Z3 bounded model checking interleaved with k-induction, both to depth 15.

    One total budget of ``MC_Z3_SECONDS`` covers every check: each Z3 call gets only the time left, so the
    arm is bounded as a whole (inconclusive or out of time -> abstain, never a guess).
    """
    import z3
    sysm = _mc_system(data)
    if data.get("property", "safety") != "safety":
        return None
    names, index, lo, hi = sysm["names"], sysm["index"], sysm["lo"], sysm["hi"]
    n = len(names)
    deadline = time.perf_counter() + MC_Z3_SECONDS

    def timed_check(solver):
        left = deadline - time.perf_counter()
        if left <= 0.01:
            return z3.unknown
        solver.set("timeout", max(1, int(left * 1000)))
        return solver.check()

    def state(tag, k):
        return [z3.Int(f"{tag}{k}_{i}") for i in range(n)]

    def ranges(xs):
        return z3.And([z3.And(x >= l, x <= h) for x, l, h in zip(xs, lo, hi)])

    def trans(xs, ys):
        options = []
        for _, guard, ups in sysm["commands"]:
            upd = dict(ups)
            options.append(z3.And(_mc_z3(guard, xs, index),
                                  *[ys[i] == (_mc_z3(upd[i], xs, index) if i in upd else xs[i]) for i in range(n)]))
        return z3.And(z3.Or(options), ranges(ys))

    def inv(xs):
        return _mc_z3(sysm["invariant"], xs, index)

    base, step = z3.Solver(), z3.Solver()
    for s in (base, step):
        s.set("random_seed", 0)
    X, Y = [state("x", 0)], [state("y", 0)]
    base.add(ranges(X[0]), *[z3.Or([X[0][i] == v for v in sysm["inits"][i]]) for i in range(n)])
    step.add(ranges(Y[0]))
    for k in range(MC_BMC_DEPTH + 1):
        base.push()
        base.add(z3.Not(inv(X[k])))
        verdict = timed_check(base)
        if verdict == z3.sat:
            m = base.model()
            states = [tuple(m.eval(x, model_completion=True).as_long() for x in xs) for xs in X]
            base.pop()
            cmds, _ = _mc_compiled(sysm)
            path = []
            for s, t in zip(states, states[1:]):
                match = [cmds[ci][0] for ci, nt in _mc_step(cmds, lo, hi, s) if nt == t]
                if not match:
                    return None
                path.append(match[0])
            return {"verdict": "UNSAFE", "initial": list(states[0]), "commands": path,
                    "violating_state": list(states[-1]), "method": f"BMC counterexample at depth {k}"}
        base.pop()
        if verdict != z3.unsat:
            return None
        base.add(inv(X[k]))
        Y.append(state("y", k + 1))
        step.add(inv(Y[k]), trans(Y[k], Y[k + 1]))
        step.push()
        step.add(z3.Not(inv(Y[k + 1])))
        inductive = step.check()
        step.pop()
        if inductive == z3.unsat:
            return {"verdict": "SAFE", "method": f"{k + 1}-induction (base case by BMC to depth {k})"}
        if k < MC_BMC_DEPTH:
            X.append(state("x", k + 1))
            base.add(trans(X[k], X[k + 1]))
    return None                                         # inconclusive within the depth bound: abstain


def _mcv(name, lo, hi, init=0):
    return {"name": name, "min": lo, "max": hi, "init": init}


def _mc_tick(var, top):
    return {"name": f"tick_{var}", "guard": True, "update": {var: ["mod", ["+", var, 1], top + 1]}}


def _mc_peterson(r):
    bug = r.choice([None, "turn_before_flag", "wrong_turn_test"])
    m1, m2 = r.randint(5, 12), r.randint(5, 12)
    variables = [_mcv("pc0", 0, 3), _mcv("pc1", 0, 3), _mcv("f0", 0, 1), _mcv("f1", 0, 1),
                 _mcv("turn", 0, 1, [0, 1]), _mcv("c1", 0, m1), _mcv("c2", 0, m2)]
    commands = []
    for i, j in ((0, 1), (1, 0)):
        pc, f, fj = f"pc{i}", f"f{i}", f"f{j}"
        first, second = ({f: 1}, {"turn": j}) if bug != "turn_before_flag" else ({"turn": j}, {f: 1})
        wait_turn = i if bug != "wrong_turn_test" else j
        commands += [
            {"name": f"p{i}_step1", "guard": ["==", pc, 0], "update": {**first, pc: 1}},
            {"name": f"p{i}_step2", "guard": ["==", pc, 1], "update": {**second, pc: 2}},
            {"name": f"p{i}_enter", "guard": ["and", ["==", pc, 2], ["or", ["==", fj, 0], ["==", "turn", wait_turn]]],
             "update": {pc: 3}},
            {"name": f"p{i}_exit", "guard": ["==", pc, 3], "update": {f: 0, pc: 0}}]
    commands += [_mc_tick("c1", m1), _mc_tick("c2", m2)]
    system = {"variables": variables, "commands": commands,
              "invariant": ["not", ["and", ["==", "pc0", 3], ["==", "pc1", 3]]]}
    return system, bug is None, f"peterson_mutex{'' if bug is None else ':' + bug}"


def _mc_lock(r):
    digits, length = r.randint(4, 8), r.randint(6, 24)
    code = [r.randrange(digits) for _ in range(length)]
    bug = r.random() < 0.75
    if not bug:
        code[r.randrange(length)] = digits                 # a digit no command can press: never opens
    top = r.randint(8, 30)
    commands = []
    for v in range(digits):
        pos = [["==", "s", j] for j, c in enumerate(code) if c == v]
        commands.append({"name": f"press_{v}", "guard": ["<", "s", length],
                         "update": {"s": ["ite", ["or", *pos], ["+", "s", 1], 0] if pos else 0}})
    commands.append(_mc_tick("c", top))
    system = {"variables": [_mcv("s", 0, length), _mcv("c", 0, top)], "commands": commands,
              "invariant": ["!=", "s", length]}
    return system, not bug, f"combination_lock:L={length}"


def _mc_buffer(r):
    cap, bug, top = r.randint(4, 12), r.random() < 0.6, r.randint(6, 20)
    variables = [_mcv("count", 0, cap + 2), _mcv("p1", 0, 1), _mcv("p2", 0, 1), _mcv("n", 0, top)]
    commands = []
    for p in ("p1", "p2"):
        if bug:                                             # check-then-act race between two producers
            commands += [{"name": f"{p}_check", "guard": ["and", ["==", p, 0], ["<", "count", cap]],
                          "update": {p: 1}},
                         {"name": f"{p}_commit", "guard": ["==", p, 1], "update": {"count": ["+", "count", 1], p: 0}}]
        else:
            commands.append({"name": f"{p}_produce", "guard": ["<", "count", cap],
                             "update": {"count": ["+", "count", 1]}})
    commands += [{"name": "consume", "guard": [">", "count", 0], "update": {"count": ["-", "count", 1]}},
                 _mc_tick("n", top)]
    system = {"variables": variables, "commands": commands, "invariant": ["<=", "count", cap]}
    return system, not bug, f"bounded_buffer{':race' if bug else ''}"


def _mc_parity(r):
    half, top, bug = r.randint(16, 40), r.randint(5, 15), r.random() < 0.4
    end = 2 * half
    commands = [{"name": "step", "guard": ["<=", ["+", "x", 2], end], "update": {"x": ["+", "x", 2]}},
                {"name": "reset", "guard": ["==", "x", end], "update": {"x": 0}}, _mc_tick("y", top)]
    if bug:
        commands.append({"name": "glitch", "guard": ["and", ["==", "x", end], ["==", "y", top]],
                         "update": {"x": ["+", "x", 1]}})
    system = {"variables": [_mcv("x", 0, end + 1), _mcv("y", 0, top)], "commands": commands,
              "invariant": ["!=", "x", end + 1]}
    return system, not bug, f"parity_counter{':glitch' if bug else ''}"


def _bounded_sum_count(nvars, top, cap):
    ways = [1] + [0] * cap
    for _ in range(nvars):
        ways = [sum(ways[s - x] for x in range(min(top, s) + 1)) for s in range(cap + 1)]
    return sum(ways)


def _mc_resources(r):
    nvars, top = r.randint(6, 8), r.randint(8, 15)
    cap, bug = r.randint(3 * nvars, 4 * nvars), r.random() < 0.5
    xs = [f"x{i}" for i in range(nvars)]
    total = ["+", *xs]
    commands = []
    for x in xs:
        commands += [{"name": f"inc_{x}", "guard": ["<=" if bug else "<", total, cap], "update": {x: ["+", x, 1]}},
                     {"name": f"dec_{x}", "guard": [">", x, 0], "update": {x: ["-", x, 1]}}]
    system = {"variables": [_mcv(x, 0, top) for x in xs], "commands": commands, "invariant": ["<=", total, cap]}
    analytic = {"safe": not bug, "reachable_states": None if bug else _bounded_sum_count(nvars, top, cap),
                "basis": "invariant inductive by construction; count of x in [0,top]^n with sum <= cap"
                if not bug else f"violation reached by {cap + 1} increments"}
    return system, analytic, f"resource_pool:n={nvars}"


def mc_instance(seed):
    r = random.Random(2_200_000 + seed)
    kind = seed % 5
    gen = (_mc_peterson, _mc_lock, _mc_buffer, _mc_parity, _mc_resources)[kind]
    system, safe, label = gen(r)
    data = {"system": system, "property": "safety", "name": label, "seed": 29_000 + seed}
    if kind == 4:                     # beyond explicit enumeration: truth is analytic (see _mc_resources)
        return data, {**safe, "kind": "resource_pool"}
    truth = _mc_dfs_truth(_mc_system(data), 10 * MC_NATIVE_STATES)
    if truth is None or truth["safe"] != safe:
        raise GenomeError("model-checking generator disagrees with its independent DFS")
    return data, {**truth, "kind": label.split(":")[0]}


def mc_subregion(data):
    return data.get("name", "system").split(":")[0]


# =================================================================== 3. linear MPC for a double integrator
MPC_MAX_STEPS, MPC_MAX_HORIZON, MPC_MAX_ABS = 400, 60, 1e6


def _mpc(data):
    _obj(data)
    dt = finite(data.get("dt"), low=1e-3, high=10.0, name="dt")
    umax = finite(data.get("u_max"), low=1e-6, high=MPC_MAX_ABS, name="u_max")
    x0 = data.get("x0")
    if not isinstance(x0, list) or len(x0) != 2:
        raise GenomeError("x0: [position, velocity]")
    x0 = [finite(x, low=-MPC_MAX_ABS, high=MPC_MAX_ABS, name="x0") for x in x0]
    ref = data.get("reference")
    if not isinstance(ref, list) or not 2 <= len(ref) <= MPC_MAX_STEPS + 1:
        raise GenomeError(f"reference: positions for steps 0..T, 1 <= T <= {MPC_MAX_STEPS}")
    ref = [finite(x, low=-MPC_MAX_ABS, high=MPC_MAX_ABS, name="reference") for x in ref]
    dist = data.get("disturbance")
    if not isinstance(dist, list) or len(dist) != len(ref) - 1:
        raise GenomeError("disturbance: one velocity disturbance per step (length T)")
    dist = [finite(x, low=-1e3, high=1e3, name="disturbance") for x in dist]
    w = data.get("weights")
    if not isinstance(w, dict):
        raise GenomeError("weights: {q_pos, q_vel, r_u}")
    qp = finite(w.get("q_pos"), low=1e-9, high=1e6, name="q_pos")
    qv = finite(w.get("q_vel", 0.0), low=0.0, high=1e6, name="q_vel")
    ru = finite(w.get("r_u"), low=1e-9, high=1e6, name="r_u")
    horizon = bounded_int(data.get("horizon", 20), low=1, high=MPC_MAX_HORIZON, name="horizon")
    preview = data.get("preview", True)
    if type(preview) is not bool:
        raise GenomeError("preview: boolean")
    return dt, umax, x0, ref, dist, (qp, qv, ru), horizon, preview


def _mpc_cost(dt, x0, ref, dist, weights, inputs):
    """Plant p' = p + dt v + dt^2 u / 2, v' = v + dt u + w_t; stage cost on steps 1..T, input cost on 0..T-1."""
    qp, qv, ru = weights
    p, v = x0
    cost = 0.0
    for t, u in enumerate(inputs):
        p, v = p + dt * v + 0.5 * dt * dt * u, v + dt * u + dist[t]
        cost += qp * (p - ref[t + 1]) ** 2 + qv * v * v + ru * u * u
    return cost, [p, v]


def _mpc_out(dt, x0, ref, dist, weights, inputs, **extra):
    cost, final = _mpc_cost(dt, x0, ref, dist, weights, inputs)
    return {"inputs": inputs, "cost": cost, "final_state": final, **extra}


def _dare(dt, weights):
    import numpy as np
    from scipy.linalg import solve_discrete_are
    qp, qv, ru = weights
    A = np.array([[1.0, dt], [0.0, 1.0]])
    B = np.array([[0.5 * dt * dt], [dt]])
    P = solve_discrete_are(A, B, np.diag([qp, qv]), np.array([[ru]]))
    K = np.linalg.solve(np.array([[ru]]) + B.T @ P @ B, B.T @ P @ A)
    return A, B, P, K


def _digest_floats(xs):
    return "sha256:" + hashlib.sha256(",".join(f"{x:.12g}" for x in xs).encode()).hexdigest()


def mpc_solve(data, budget):
    dt, umax, x0, ref, dist, weights, horizon, preview = _mpc(data)
    if data.get("state_bounds") is not None:
        return _abstain("state constraints need a general QP; this method handles input bounds only")
    if data.get("measurement", "full_state") != "full_state":
        return _abstain("partial measurement needs an observer; this method assumes full-state feedback")
    import numpy as np
    from scipy.linalg import cholesky
    from scipy.optimize import lsq_linear
    qp, qv, ru = weights
    A, B, P, _ = _dare(dt, weights)
    N = horizon
    upper = cholesky(P + 1e-12 * np.eye(2), lower=False)          # P = U^T U: residual U e gives e' P e
    powers = [np.eye(2)]
    for _ in range(N):
        powers.append(A @ powers[-1])
    Phi, G, W = np.zeros((2 * N, 2)), np.zeros((2 * N, N)), np.zeros((2 * N, 2 * N))
    for k in range(1, N + 1):
        rows = slice(2 * (k - 1), 2 * k)
        Phi[rows] = powers[k]
        for j in range(k):
            G[rows, j] = (powers[k - 1 - j] @ B)[:, 0]
        W[rows, rows] = upper if k == N else np.diag([math.sqrt(qp), math.sqrt(qv)])
    M = np.vstack([W @ G, math.sqrt(ru) * np.eye(N)])
    T = len(ref) - 1
    x = np.array(x0, dtype=float)
    inputs, saturated = [], 0
    for t in range(T):
        target = np.zeros(2 * N)
        for k in range(1, N + 1):
            target[2 * (k - 1)] = ref[min(t + k, T)] if preview else ref[t + 1]
        rhs = np.concatenate([W @ (target - Phi @ x), np.zeros(N)])
        sol = lsq_linear(M, rhs, bounds=(-umax, umax), method="bvls")
        u = float(min(umax, max(-umax, sol.x[0])))
        saturated += abs(u) >= umax * (1 - 1e-9)
        inputs.append(u)
        x = A @ x + B[:, 0] * u + np.array([0.0, dist[t]])
    out = _mpc_out(dt, x0, ref, dist, weights, inputs)
    return answer(out, {"method": "receding-horizon QP: min ||M U - b||^2 subject to |u| <= u_max, solved exactly "
                        "as bounded least squares (SciPy BVLS); terminal cost from the discrete ARE",
                        "horizon": N, "steps": T, "reference_preview": preview, "saturated_steps": saturated,
                        "terminal_P": [[float(P[0, 0]), float(P[0, 1])], [float(P[1, 0]), float(P[1, 1])]],
                        "simulated_cost": out["cost"], "input_digest": _digest_floats(inputs),
                        "disturbance_use": "measured state only; future disturbances unknown to the controller"})


def mpc_verify(data, output, certificate):
    dt, umax, x0, ref, dist, weights, _, _ = _mpc(data)
    inputs = output.get("inputs") if isinstance(output, dict) else None
    T = len(ref) - 1
    if not isinstance(inputs, list) or len(inputs) != T or not all(_is_num(u) for u in inputs):
        return {"inputs_well_formed": False}
    qp, qv, ru = weights
    p, v, cost = x0[0], x0[1], 0.0                      # independent re-simulation, written out separately
    for t in range(T):
        u = inputs[t]
        p_next = p + v * dt + u * dt * dt / 2.0
        v = v + u * dt + dist[t]
        p = p_next
        cost += qp * (p - ref[t + 1]) * (p - ref[t + 1]) + qv * v * v + ru * u * u
    claimed, final = output.get("cost"), output.get("final_state")
    return {"inputs_well_formed": True,
            "inputs_within_bounds": all(abs(u) <= umax * (1 + 1e-12) for u in inputs),
            "cost_recomputed": _is_num(claimed) and abs(claimed - cost) <= 1e-6 * (1 + abs(cost)),
            "final_state_recomputed": isinstance(final, list) and len(final) == 2 and all(_is_num(x) for x in final)
            and abs(final[0] - p) <= 1e-6 * (1 + abs(p)) and abs(final[1] - v) <= 1e-6 * (1 + abs(v)),
            "certificate_binds_inputs": (certificate or {}).get("input_digest") in (None, _digest_floats(inputs))}


def _mpc_clairvoyant(dt, x0, ref, dist, weights, umax):
    """Hindsight lower bound: all T inputs chosen with the realised disturbances known (bounded LSQ)."""
    import numpy as np
    from scipy.optimize import lsq_linear
    qp, qv, ru = weights
    T = len(ref) - 1
    A = np.array([[1.0, dt], [0.0, 1.0]])
    Bv = np.array([0.5 * dt * dt, dt])
    free = np.zeros((T, 2))                              # state with zero input (initial state + disturbances)
    Gx = np.zeros((T, 2, T))                             # sensitivity of x_{t+1} to u_j
    x = np.array(x0, dtype=float)
    S = np.zeros((2, T))
    for t in range(T):
        x = A @ x + np.array([0.0, dist[t]])
        S = A @ S
        S[:, t] += Bv
        free[t], Gx[t] = x, S
    sq = np.array([math.sqrt(qp), math.sqrt(qv)])
    M = np.vstack([(Gx * sq[None, :, None]).reshape(2 * T, T), math.sqrt(ru) * np.eye(T)])
    target = np.stack([np.array(ref[1:]), np.zeros(T)], axis=1)
    rhs = np.concatenate([((target - free) * sq[None, :]).reshape(2 * T), np.zeros(T)])
    sol = lsq_linear(M, rhs, bounds=(-umax, umax), method="bvls")
    return _mpc_cost(dt, x0, ref, dist, weights, [float(u) for u in np.clip(sol.x, -umax, umax)])[0]


def mpc_instance(seed):
    r = random.Random(3_300_000 + seed)
    kind = ("steps", "big_steps", "sine", "mixed")[seed % 4]
    dt, T = 0.1, r.randint(80, 140)
    umax = round(r.uniform(1.0, 3.0) if kind in ("steps", "sine") else r.uniform(0.5, 1.5), 3)
    ref = [0.0] * (T + 1)
    if kind in ("steps", "big_steps", "mixed"):
        amp = (1.0, 4.0) if kind != "big_steps" else (4.0, 10.0)
        level, t = 0.0, r.randint(5, 20)
        changes = sorted(r.sample(range(10, T - 10), r.randint(2, 4)))
        for t in range(T + 1):
            if changes and t >= changes[0]:
                changes.pop(0)
                level = round(r.choice((-1, 1)) * r.uniform(*amp), 3)
            ref[t] = level
    if kind in ("sine", "mixed"):
        a, period, phase = r.uniform(1.0, 3.0), r.uniform(3.0, 8.0), r.uniform(0, 2 * math.pi)
        ref = [round(ref[t] + a * math.sin(2 * math.pi * t * dt / period + phase), 4) for t in range(T + 1)]
    sigma, bias = r.uniform(0.0, 0.03), r.uniform(-0.02, 0.02) if r.random() < 0.5 else 0.0
    start = r.randint(0, T // 2)
    dist = [round(r.gauss(0.0, sigma) + (bias if t >= start else 0.0), 5) for t in range(T)]
    weights = {"q_pos": 1.0, "q_vel": r.choice([0.0, 0.05]), "r_u": r.choice([0.01, 0.05])}
    data = {"dt": dt, "u_max": umax, "x0": [round(r.uniform(-0.5, 0.5), 3), 0.0], "reference": ref,
            "disturbance": dist, "weights": weights, "horizon": r.choice([15, 20, 25]),
            "preview": seed % 8 < 4, "profile": kind, "measurement": "full_state"}
    wt = (weights["q_pos"], weights["q_vel"], weights["r_u"])
    zero = _mpc_cost(dt, data["x0"], ref, dist, wt, [0.0] * T)[0]
    return data, {"zero_input_cost": max(zero, 1e-9),
                  "clairvoyant_cost": _mpc_clairvoyant(dt, data["x0"], ref, dist, wt, umax)}


def mpc_subregion(data):
    return f"{data.get('profile', 'reference')}:{'preview' if data.get('preview', True) else 'no_preview'}"


def mpc_score(data, truth, output):
    dt, umax, x0, ref, dist, weights, _, _ = _mpc(data)
    zero = truth["zero_input_cost"]
    if output is None:
        return {"quality": -1.0, "category": "abstain"}                  # no controller: zero input
    inputs = output.get("inputs") if isinstance(output, dict) else None
    T = len(ref) - 1
    if (not isinstance(inputs, list) or len(inputs) != T or not all(_is_num(u) for u in inputs)
            or any(abs(u) > umax * (1 + 1e-9) for u in inputs)):
        return {"quality": -2.0, "category": "wrong"}                    # an input-bound violation
    cost = _mpc_cost(dt, x0, ref, dist, weights, inputs)[0]
    claimed = output.get("cost")
    if claimed is not None and (not _is_num(claimed) or abs(claimed - cost) > 1e-6 * (1 + cost)):
        return {"quality": -2.0, "category": "wrong"}                    # a false cost claim
    return {"quality": -cost / zero, "category": "correct"}


def mpc_pd(data):
    """Baseline: saturated proportional state feedback (PD), critically damped at w = (q_pos / r_u)^(1/4)."""
    dt, umax, x0, ref, dist, weights, _, _ = _mpc(data)
    omega = (weights[0] / weights[2]) ** 0.25
    kp, kd = omega * omega, 2.0 * omega
    p, v = x0
    inputs = []
    for t in range(len(ref) - 1):
        u = min(umax, max(-umax, kp * (ref[t + 1] - p) - kd * v))
        inputs.append(u)
        p, v = p + dt * v + 0.5 * dt * dt * u, v + dt * u + dist[t]
    return _mpc_out(dt, x0, ref, dist, weights, inputs)


def mpc_lqr(data):
    """Competitor: infinite-horizon discrete LQR (SciPy DARE) on the next reference, with input clipping."""
    dt, umax, x0, ref, dist, weights, _, _ = _mpc(data)
    _, _, _, K = _dare(dt, weights)
    k1, k2 = float(K[0, 0]), float(K[0, 1])
    p, v = x0
    inputs = []
    for t in range(len(ref) - 1):
        u = min(umax, max(-umax, -(k1 * (p - ref[t + 1]) + k2 * v)))
        inputs.append(u)
        p, v = p + dt * v + 0.5 * dt * dt * u, v + dt * u + dist[t]
    return _mpc_out(dt, x0, ref, dist, weights, inputs)


# =================================================================== 4. CEGIS for bounded threshold rules
SY_MAX_N, SY_NATIVE_N, SY_MAX_BOUND = 16, 13, 64
SY_MAX_ITER, SY_SAMPLE, SY_Z3_MS = 400, 128, 20_000


def _sy(data):
    _obj(data)
    if data.get("spec", "threshold_gate") != "threshold_gate":
        raise GenomeError("spec: threshold_gate (sign(w.x + b) must equal the label on every point)")
    n = bounded_int(data.get("n"), low=1, high=SY_MAX_N, name="n")
    bound = bounded_int(data.get("weight_bound"), low=1, high=SY_MAX_BOUND, name="weight_bound")
    labels = data.get("labels")
    width = max(1, (2 ** n + 3) // 4)
    if not isinstance(labels, str) or len(labels) != width or any(c not in "0123456789abcdef" for c in labels):
        raise GenomeError(f"labels: {width} lowercase hex digits (bit i = label of point i)")
    value = int(labels, 16)
    if value >> (2 ** n):
        raise GenomeError("labels encode more than 2^n points")
    return n, bound, value


def _sy_domain(n, value):
    import numpy as np
    idx = np.arange(2 ** n, dtype=np.int64)
    X = ((idx[:, None] >> np.arange(n)) & 1).astype(np.int64)
    raw = np.frombuffer(value.to_bytes((2 ** n + 7) // 8, "little"), dtype=np.uint8)
    y = np.unpackbits(raw, bitorder="little")[:2 ** n].astype(bool)
    return X, y


def _sy_params(output, n, bound):
    w, b = output.get("weights"), output.get("bias")
    if (not isinstance(w, list) or len(w) != n or any(type(x) is not int or abs(x) > bound for x in w)
            or type(b) is not int or abs(b) > bound * n):
        return None
    return w, b


def _sy_constraint(z3, w, b, row, positive):
    terms = [w[j] for j, bit in enumerate(row) if bit]
    expr = z3.Sum(terms) + b if terms else b
    return expr >= 1 if positive else expr <= -1


def _sy_new_solver(z3, n, bound):
    s = z3.Solver()
    s.set("random_seed", 0)
    s.set("timeout", SY_Z3_MS)
    w = [z3.Int(f"w{j}") for j in range(n)]
    b = z3.Int("b")
    s.add(*[z3.And(x >= -bound, x <= bound) for x in w], b >= -bound * n, b <= bound * n)
    return s, w, b


def _sy_model(z3, s, w, b):
    m = s.model()
    return [m.eval(x, model_completion=True).as_long() for x in w], m.eval(b, model_completion=True).as_long()


def cegis_solve(data, budget):
    n, bound, value = _sy(data)
    if n > SY_NATIVE_N:
        return _abstain(f"domain 2^{n} beyond the exhaustive-verification size 2^{SY_NATIVE_N}", n=n)
    import numpy as np
    import z3
    X, y = _sy_domain(n, value)
    sign = np.where(y, 1, -1)
    s, w, b = _sy_new_solver(z3, n, bound)
    deadline = time.perf_counter() + max(0.5, float((budget or {}).get("latency_s", 5.0)))
    examples = []
    for it in range(1, SY_MAX_ITER + 1):
        verdict = s.check()
        if verdict == z3.unsat:
            return answer({"realizable": False},
                          {"method": "CEGIS: the counterexample set alone has no bounded integer solution (Z3 "
                                     "UNSAT), so the full specification has none", "iterations": it,
                           "unsat_witness": examples, "domain_size": 2 ** n})
        if verdict != z3.sat:
            return _unknown("synthesiser returned unknown", iterations=it)
        wv, bv = _sy_model(z3, s, w, b)
        margin = sign * (X @ np.array(wv, dtype=np.int64) + bv)
        bad = np.nonzero(margin < 1)[0]
        if bad.size == 0:
            return answer({"realizable": True, "weights": wv, "bias": bv},
                          {"method": "CEGIS: Z3 synthesiser on a growing counterexample set; exhaustive NumPy "
                                     "oracle over all 2^n points found no violation", "iterations": it,
                           "examples": examples, "domain_size": 2 ** n, "violations": 0})
        for mask in (y[bad], ~y[bad]):                          # worst positive and worst negative violation
            cand = bad[mask]
            if cand.size:
                i = int(cand[np.argmin(margin[cand])])
                examples.append(i)
                s.add(_sy_constraint(z3, w, b, X[i], bool(y[i])))
        if time.perf_counter() > deadline:
            return _unknown("latency budget exhausted", iterations=it)
    return _unknown(f"no convergence within {SY_MAX_ITER} iterations")


def cegis_verify(data, output, certificate):
    n, bound, value = _sy(data)
    flag = output.get("realizable") if isinstance(output, dict) else None
    if flag is True:
        params = _sy_params(output, n, bound)
        if params is None:
            return {"parameters_within_bounds": False}
        w, b = params
        holds = True
        for i in range(2 ** n):                                  # independent exhaustive check, pure Python
            total = b + sum(w[j] for j in range(n) if (i >> j) & 1)
            if (total < 1) if (value >> i) & 1 else (total > -1):
                holds = False
                break
        return {"parameters_within_bounds": True, "spec_holds_on_every_domain_point": holds}
    if flag is False:
        wit = (certificate or {}).get("unsat_witness")
        if (not isinstance(wit, list) or not wit or len(set(wit)) != len(wit)
                or any(type(i) is not int or not 0 <= i < 2 ** n for i in wit)):
            return {"witness_well_formed": False}
        import numpy as np
        from scipy.optimize import Bounds, LinearConstraint, milp
        rows = np.array([[(i >> j) & 1 for j in range(n)] + [1] for i in wit], dtype=float)
        sg = np.array([1.0 if (value >> i) & 1 else -1.0 for i in wit])
        res = milp(c=np.zeros(n + 1), constraints=LinearConstraint(rows * sg[:, None], lb=np.ones(len(wit))),
                   integrality=np.ones(n + 1), bounds=Bounds([-bound] * n + [-bound * n], [bound] * n + [bound * n]),
                   options={"time_limit": 20.0})
        return {"witness_well_formed": True, "witness_infeasible_by_independent_milp": res.status == 2}
    return {"realizable_flag_present": False}


def cegis_score(data, truth, output):
    if output is None:
        return {"quality": 0.0, "category": "abstain"}
    n, bound, value = _sy(data)
    flag = output.get("realizable") if isinstance(output, dict) else None
    if flag is True:
        params = _sy_params(output, n, bound)
        ok = False
        if params is not None:
            import numpy as np
            X, y = _sy_domain(n, value)
            margin = np.where(y, 1, -1) * (X @ np.array(params[0], dtype=np.int64) + params[1])
            ok = bool((margin >= 1).all())
    elif flag is False:
        ok = not truth["realizable"]
    else:
        ok = False
    return {"quality": 1.0, "category": "correct"} if ok else {"quality": -1.0, "category": "wrong"}


def _sy_hex(y):
    value = 0
    for i, bit in enumerate(y):
        if bit:
            value |= 1 << i
    return format(value, "x").zfill(max(1, (len(y) + 3) // 4))


def _sy_milp_realizable(n, bound, value):
    import numpy as np
    from scipy.optimize import Bounds, LinearConstraint, milp
    X, y = _sy_domain(n, value)
    sg = np.where(y, 1.0, -1.0)
    A = np.hstack([X, np.ones((len(X), 1))]).astype(float) * sg[:, None]
    res = milp(c=np.zeros(n + 1), constraints=LinearConstraint(A, lb=np.ones(len(X))), integrality=np.ones(n + 1),
               bounds=Bounds([-bound] * n + [-bound * n], [bound] * n + [bound * n]), options={"time_limit": 60.0})
    if res.status not in (0, 2):
        raise GenomeError("independent MILP could not decide realizability")
    return res.status == 0


def cegis_instance(seed):
    import numpy as np
    r = random.Random(4_400_000 + seed)
    kind = ("planted_small", "planted_wide", "xor_face", "comparator")[seed % 4]
    bound = r.choice([8, 10, 12])
    if kind == "comparator":
        half = r.choice([5, 6])
        n = 2 * half
        X, _ = _sy_domain(n, 0)
        y = X[:, :half] @ (2 ** np.arange(half)) > X[:, half:] @ (2 ** np.arange(half))
    else:
        n = r.randint(9, 12)
        X, _ = _sy_domain(n, 0)
        W = 2 if kind == "planted_small" else (bound - 1) // 2
        while True:
            w = np.array([r.randint(-W, W) for _ in range(n)])
            if w.any():
                break
        score = X @ w
        b = -int(np.round(np.median(score))) + r.randint(-W, W)
        y = score + b >= 0
        if y.all() or not y.any():
            y = score >= np.median(score)
        if kind == "xor_face":
            a, c, face = r.sample(range(n), 3)
            on_face = X[:, face] == 1
            y = np.where(on_face, (X[:, a] ^ X[:, c]).astype(bool), y)
    value = int(_sy_hex(y.tolist()), 16)
    data = {"spec": "threshold_gate", "n": n, "weight_bound": bound, "labels": _sy_hex(y.tolist()),
            "seed": 31_000 + seed, "description": kind}
    if kind.startswith("planted"):
        realizable, basis = True, "analytic: (2w*, 2b*+1) satisfies the margin within the bounds"
    elif kind == "xor_face":
        realizable, basis = False, "analytic: an XOR pattern on a 2-face is not linearly separable"
    else:
        realizable, basis = _sy_milp_realizable(n, bound, value), "independent HiGHS MILP on the full domain"
    if kind.startswith("planted") and not _sy_milp_realizable(n, bound, value):
        raise GenomeError("planted threshold instance not realizable: generator error")
    return data, {"realizable": realizable, "basis": basis}


def cegis_subregion(data):
    return data.get("description", "threshold")


def cegis_sample(data):
    """Baseline: one Z3 synthesis on a fixed random sample of 128 domain points (no feedback)."""
    n, bound, value = _sy(data)
    import z3
    r = random.Random(bounded_int(data.get("seed", 0), low=0, high=10**9, name="seed"))
    pts = r.sample(range(2 ** n), min(2 ** n, SY_SAMPLE))
    s, w, b = _sy_new_solver(z3, n, bound)
    for i in pts:
        s.add(_sy_constraint(z3, w, b, [(i >> j) & 1 for j in range(n)], bool((value >> i) & 1)))
    verdict = s.check()
    if verdict == z3.unsat:
        return {"realizable": False}
    if verdict != z3.sat:
        return None
    wv, bv = _sy_model(z3, s, w, b)
    return {"realizable": True, "weights": wv, "bias": bv}


def cegis_full_domain(data):
    """Competitor: Z3 on the whole specification at once (all 2^n constraints, SMT-LIB text encoding)."""
    n, bound, value = _sy(data)
    import z3
    lines = [f"(declare-const w{j} Int)" for j in range(n)] + ["(declare-const b Int)"]
    lines += [f"(assert (and (>= w{j} {-bound}) (<= w{j} {bound})))" for j in range(n)]
    lines.append(f"(assert (and (>= b {-bound * n}) (<= b {bound * n})))")
    for i in range(2 ** n):
        terms = " ".join(f"w{j}" for j in range(n) if (i >> j) & 1)
        expr = f"(+ b {terms})" if terms else "b"
        lines.append(f"(assert (>= {expr} 1))" if (value >> i) & 1 else f"(assert (<= {expr} (- 1)))")
    s = z3.Solver()
    s.set("random_seed", 0)
    s.set("timeout", SY_Z3_MS)
    s.from_string("\n".join(lines))
    verdict = s.check()
    if verdict == z3.unsat:
        return {"realizable": False}
    if verdict != z3.sat:
        return None
    m = s.model()
    get = {d.name(): m[d].as_long() for d in m.decls()}
    return {"realizable": True, "weights": [get.get(f"w{j}", 0) for j in range(n)], "bias": get.get("b", 0)}


# =================================================================== 5. backdoor adjustment for the ATE
CA_MAX_NODES, CA_MIN_ROWS, CA_MAX_ROWS, CA_MAX_LEVEL = 24, 20, 5000, 50
CA_TYPES = ("binary", "discrete", "continuous")


def _ca(data):
    _obj(data)
    nodes = data.get("nodes")
    if not isinstance(nodes, list) or not 2 <= len(nodes) <= CA_MAX_NODES:
        raise GenomeError(f"nodes: 2-{CA_MAX_NODES} declared variables")
    info = {}
    for nd in nodes:
        name = nd.get("name") if isinstance(nd, dict) else None
        if not isinstance(name, str) or not name.isidentifier() or len(name) > 32 or name in info:
            raise GenomeError("node names: unique identifiers")
        if type(nd.get("observed", True)) is not bool or nd.get("type", "continuous") not in CA_TYPES:
            raise GenomeError(f"{name}: observed is boolean; type is binary, discrete or continuous")
        info[name] = {"observed": nd.get("observed", True), "type": nd.get("type", "continuous")}
    edges = data.get("edges")
    if not isinstance(edges, list) or len(edges) > CA_MAX_NODES * CA_MAX_NODES:
        raise GenomeError("edges: a list of [parent, child]")
    parents = {v: [] for v in info}
    children = {v: [] for v in info}
    for e in edges:
        if (not isinstance(e, list) or len(e) != 2 or e[0] not in info or e[1] not in info or e[0] == e[1]
                or e[0] in parents[e[1]]):
            raise GenomeError("edge: [parent, child] between distinct declared nodes, no duplicates")
        parents[e[1]].append(e[0])
        children[e[0]].append(e[1])
    indeg = {v: len(parents[v]) for v in info}
    queue, seen = [v for v in info if indeg[v] == 0], 0
    while queue:
        v = queue.pop()
        seen += 1
        for c in children[v]:
            indeg[c] -= 1
            if indeg[c] == 0:
                queue.append(c)
    if seen != len(info):
        raise GenomeError("the declared graph has a directed cycle")
    t, y = data.get("treatment"), data.get("outcome")
    if t not in info or y not in info or t == y or not info[t]["observed"] or not info[y]["observed"]:
        raise GenomeError("treatment and outcome: distinct observed nodes")
    if info[t]["type"] != "binary" or info[y]["type"] != "continuous":
        raise GenomeError("treatment is binary and outcome is continuous")
    zset = data.get("adjustment_set")
    if not isinstance(zset, list) or len(set(zset)) != len(zset) or any(z not in info or z in (t, y) for z in zset):
        raise GenomeError("adjustment_set: distinct declared nodes other than treatment and outcome")
    samples = data.get("samples")
    if not isinstance(samples, dict):
        raise GenomeError("samples: observed column name -> values")
    cols, rows = {}, None
    for name, vals in samples.items():
        if name not in info or not info[name]["observed"]:
            raise GenomeError(f"samples: {name!r} is not an observed node")
        if not isinstance(vals, list) or not CA_MIN_ROWS <= len(vals) <= CA_MAX_ROWS:
            raise GenomeError(f"samples.{name}: {CA_MIN_ROWS}-{CA_MAX_ROWS} values")
        rows = len(vals) if rows is None else rows
        if len(vals) != rows:
            raise GenomeError("samples: columns of equal length")
        kind = info[name]["type"]
        if kind == "continuous":
            cols[name] = [finite(v, low=-1e9, high=1e9, name=name) for v in vals]
        else:
            top = 1 if kind == "binary" else CA_MAX_LEVEL
            cols[name] = [bounded_int(v, low=0, high=top, name=name) for v in vals]
    for need in (t, y):
        if need not in cols:
            raise GenomeError(f"samples: column {need!r} required")
    return {"info": info, "parents": parents, "children": children, "t": t, "y": y, "z": list(zset), "cols": cols}


def _descendants(children, root):
    out, stack = set(), list(children[root])
    while stack:
        v = stack.pop()
        if v not in out:
            out.add(v)
            stack.extend(children[v])
    return out


def _dsep_moral(parents, xs, ys, zs):
    """X and Y d-separated by Z: moralise the ancestral graph of X, Y, Z, delete Z, test connectivity."""
    anc, stack = set(), list(xs | ys | zs)
    while stack:
        v = stack.pop()
        if v not in anc:
            anc.add(v)
            stack.extend(parents[v])
    adj = {v: set() for v in anc}
    for v in anc:
        ps = parents[v]
        for p in ps:
            adj[v].add(p)
            adj[p].add(v)
        for a in ps:
            for b in ps:
                if a != b:
                    adj[a].add(b)
    seen, stack = set(xs), list(xs)
    while stack:
        v = stack.pop()
        for u in adj[v]:
            if u in zs or u in seen:
                continue
            if u in ys:
                return False
            seen.add(u)
            stack.append(u)
    return True


def _cut_treatment(g):
    t = g["t"]
    return {v: [p for p in ps if p != t] for v, ps in g["parents"].items()}


def _ca_backdoor(g, zset):
    z = set(zset)
    return {"adjustment_set_observed": all(g["info"][v]["observed"] for v in z),
            "no_descendant_of_treatment": not (z & _descendants(g["children"], g["t"])),
            "backdoor_paths_blocked": _dsep_moral(_cut_treatment(g), {g["t"]}, {g["y"]}, z)}


def _ca_stratify(t, y, zcols):
    import numpy as np
    keys = np.stack(zcols, axis=1) if zcols else np.zeros((len(t), 1), dtype=np.int64)
    _, inv = np.unique(keys, axis=0, return_inverse=True)
    inv = np.asarray(inv).reshape(-1)
    est, var, n = 0.0, 0.0, len(t)
    for s in range(int(inv.max()) + 1):
        m = inv == s
        y1, y0 = y[m & (t == 1)], y[m & (t == 0)]
        if len(y1) < 2 or len(y0) < 2:
            return None
        share = m.sum() / n
        est += share * (y1.mean() - y0.mean())
        var += share * share * (y1.var(ddof=1) / len(y1) + y0.var(ddof=1) / len(y0))
    return float(est), float(math.sqrt(var)), int(inv.max()) + 1


def _ca_design(g, zset):
    """Covariate matrix: one-hot (drop first level) for binary/discrete, raw values for continuous."""
    import numpy as np
    cols = []
    for z in zset:
        v = np.asarray(g["cols"][z], dtype=float)
        if g["info"][z]["type"] == "continuous":
            cols.append(v)
        else:
            for level in sorted(set(g["cols"][z]))[1:]:
                cols.append((v == level).astype(float))
    return np.column_stack(cols) if cols else np.zeros((len(g["cols"][g["t"]]), 0))


def _ca_regress(t, y, Z):
    import numpy as np
    Zc = Z - Z.mean(axis=0) if Z.shape[1] else Z
    X = np.column_stack([np.ones(len(t)), t, Zc, t[:, None] * Zc])
    coef, _, rank, _ = np.linalg.lstsq(X, y, rcond=None)
    if rank < X.shape[1] or len(t) <= X.shape[1] + 1:
        return None
    resid = y - X @ coef
    bread = np.linalg.inv(X.T @ X)
    meat = (X * resid[:, None] ** 2).T @ X
    se = math.sqrt(max(0.0, float((bread @ meat @ bread)[1, 1])))       # HC0 sandwich
    return float(coef[1]), se, X.shape[1]


def causal_solve(data, budget):
    import numpy as np
    g = _ca(data)
    z = sorted(g["z"])
    bd = _ca_backdoor(g, z)
    if not all(bd.values()):
        failed = [k for k, ok in bd.items() if not ok]
        return _abstain("non-identified: the declared adjustment set fails the backdoor criterion",
                        failed_conditions=failed, adjustment_set=z, dsep_algorithm="moralised ancestral graph")
    if any(v not in g["cols"] for v in z):
        return _abstain("an adjustment variable has no samples", adjustment_set=z)
    t = np.asarray(g["cols"][g["t"]], dtype=np.int64)
    y = np.asarray(g["cols"][g["y"]], dtype=float)
    if all(g["info"][v]["type"] != "continuous" for v in z):
        res = _ca_stratify(t, y, [np.asarray(g["cols"][v], dtype=np.int64) for v in z])
        estimator = "stratification"
    else:
        res = _ca_regress(t, y.astype(float), _ca_design(g, z))
        estimator = "regression_adjustment"
    if res is None:
        return _abstain("positivity or rank failure: some covariate stratum lacks treated or control units",
                        estimator=estimator)
    est, se, size = res
    return answer({"ate": est, "se": se, "adjustment_set": z, "estimator": estimator,
                   "identified_by": "backdoor criterion"},
                  {"method": f"backdoor adjustment ({estimator}) after a d-separation identification check",
                   "backdoor": bd, "dsep_algorithm": "moralised ancestral graph", "n": int(len(t)),
                   "strata_or_columns": size, "ci95": [est - 1.96 * se, est + 1.96 * se],
                   "assumptions": "declared DAG is correct; no unmeasured confounding beyond it; positivity; "
                                  "linear outcome model with interactions (regression adjustment)"})


def _dsep_ball(parents, children, x, ys, zs):
    """Bayes-ball reachability (Shachter 1998 / Koller-Friedman): an independent d-separation test."""
    anc, stack = set(), list(zs)
    while stack:
        v = stack.pop()
        if v not in anc:
            anc.add(v)
            stack.extend(parents[v])
    visited, reach, stack = set(), set(), [(x, "up")]
    while stack:
        v, d = stack.pop()
        if (v, d) in visited:
            continue
        visited.add((v, d))
        if v not in zs:
            reach.add(v)
        if d == "up" and v not in zs:
            stack.extend((p, "up") for p in parents[v])
            stack.extend((c, "down") for c in children[v])
        elif d == "down":
            if v not in zs:
                stack.extend((c, "down") for c in children[v])
            if v in anc:
                stack.extend((p, "up") for p in parents[v])
    return not (reach & set(ys))


def _ca_backdoor_ball(g, zset):
    z = set(zset)
    t = g["t"]
    cut_children = {v: [c for c in cs if v != t] for v, cs in g["children"].items()}
    return (all(g["info"][v]["observed"] for v in z) and not (z & _descendants(g["children"], t))
            and _dsep_ball(_cut_treatment(g), cut_children, t, {g["y"]}, z))


def causal_verify(data, output, certificate):
    g = _ca(data)
    if not isinstance(output, dict) or not _is_num(output.get("ate")):
        return {"estimate_well_formed": False}
    z = output.get("adjustment_set")
    declared = sorted(g["z"])
    checks = {"estimate_well_formed": True, "adjustment_set_is_declared": z == declared,
              "backdoor_criterion_by_independent_bayes_ball": isinstance(z, list) and _ca_backdoor_ball(g, declared)}
    t, y, n = g["cols"][g["t"]], g["cols"][g["y"]], len(g["cols"][g["t"]])
    discrete = all(g["info"][v]["type"] != "continuous" for v in declared)
    checks["estimator_matches_covariate_types"] = output.get("estimator") == (
        "stratification" if discrete else "regression_adjustment")
    if discrete:                                       # pure-Python stratum accumulation
        acc = {}
        for i in range(n):
            key = tuple(g["cols"][v][i] for v in declared)
            a = acc.setdefault(key, [0, 0.0, 0, 0.0])
            if t[i] == 1:
                a[0] += 1
                a[1] += y[i]
            else:
                a[2] += 1
                a[3] += y[i]
        if any(a[0] == 0 or a[2] == 0 for a in acc.values()):
            checks["estimate_recomputed"] = False
            return checks
        est = sum((a[0] + a[2]) / n * (a[1] / a[0] - a[3] / a[2]) for a in acc.values())
    else:                                              # normal equations instead of least squares
        import numpy as np
        Z = _ca_design(g, declared)
        Zc = Z - Z.mean(axis=0)
        tt = np.asarray(t, dtype=float)
        X = np.hstack([np.ones((n, 1)), tt[:, None], Zc, tt[:, None] * Zc])
        try:
            est = float(np.linalg.solve(X.T @ X, X.T @ np.asarray(y, dtype=float))[1])
        except np.linalg.LinAlgError:
            checks["estimate_recomputed"] = False
            return checks
    checks["estimate_recomputed"] = abs(est - output["ate"]) <= 1e-6 * (1 + abs(est))
    return checks


def causal_score(data, truth, output):
    g = _ca(data)
    if output is None:
        return {"quality": -1.0 if truth["identified"] else 0.0, "category": "abstain"}
    z = output.get("adjustment_set") if isinstance(output, dict) else None
    if (not isinstance(z, list) or not _is_num(output.get("ate")) or any(v not in g["info"] for v in z)
            or len(set(z)) != len(z) or g["t"] in z or g["y"] in z):
        return {"quality": -2.0, "category": "wrong"}
    if not _ca_backdoor_ball(g, z):
        return {"quality": -2.0, "category": "wrong"}       # a causal claim from a non-identifying adjustment
    err = abs(output["ate"] - truth["ate"]) / truth["scale"]
    return {"quality": -min(err, 1.0), "category": "correct"}


def causal_naive(data):
    """Baseline: difference in means, no adjustment and no identification check."""
    g = _ca(data)
    t, y = g["cols"][g["t"]], g["cols"][g["y"]]
    y1 = [v for v, a in zip(y, t) if a == 1]
    y0 = [v for v, a in zip(y, t) if a == 0]
    if not y1 or not y0:
        return None
    return {"ate": sum(y1) / len(y1) - sum(y0) / len(y0), "adjustment_set": [], "estimator": "difference_in_means"}


def causal_ipw(data):
    """Competitor: backdoor gate (NetworkX d-separation) + Hajek IPW with a logistic propensity (IRLS)."""
    import networkx as nx
    import numpy as np
    g = _ca(data)
    z = sorted(g["z"])
    if any(not g["info"][v]["observed"] or v not in g["cols"] for v in z):
        return None
    G = nx.DiGraph()
    G.add_nodes_from(g["info"])
    G.add_edges_from((p, c) for c, ps in g["parents"].items() for p in ps)
    if set(z) & nx.descendants(G, g["t"]):
        return None
    G.remove_edges_from(list(G.out_edges(g["t"])))
    if not nx.is_d_separator(G, {g["t"]}, {g["y"]}, set(z)):
        return None
    t = np.asarray(g["cols"][g["t"]], dtype=float)
    y = np.asarray(g["cols"][g["y"]], dtype=float)
    Z = _ca_design(g, z)
    if Z.shape[1]:
        sd = Z.std(axis=0)
        Z = (Z - Z.mean(axis=0)) / np.where(sd > 0, sd, 1.0)
    X = np.column_stack([np.ones(len(t)), Z])
    beta = np.zeros(X.shape[1])
    for _ in range(50):
        p = 1.0 / (1.0 + np.exp(-np.clip(X @ beta, -30, 30)))
        wts = p * (1 - p)
        H = X.T @ (X * wts[:, None]) + 1e-8 * np.eye(X.shape[1])
        step = np.linalg.solve(H, X.T @ (t - p))
        beta += step
        if np.abs(step).max() < 1e-10:
            break
    e = np.clip(1.0 / (1.0 + np.exp(-np.clip(X @ beta, -30, 30))), 0.01, 0.99)
    w1, w0 = t / e, (1 - t) / (1 - e)
    ate = float((w1 * y).sum() / w1.sum() - (w0 * y).sum() / w0.sum())
    return {"ate": ate, "adjustment_set": z, "estimator": "ipw_hajek_logistic"}


def _ca_round(xs, digits=3):
    return [round(float(x), digits) for x in xs]


def causal_instance(seed):
    import numpy as np
    r = random.Random(5_500_000 + seed)
    rng = np.random.default_rng(5_500_000 + seed)
    kind = ("discrete", "continuous_linear", "continuous_nonlinear", "m_bias", "mediator_or_latent")[seed % 5]
    n = r.randint(800, 1000)
    sig = lambda x: 1.0 / (1.0 + np.exp(-x))                                  # noqa: E731
    nodes = [{"name": "T", "type": "binary"}, {"name": "Y", "type": "continuous"}]
    edges = [["T", "Y"]]
    samples = {}
    if kind == "discrete":
        levels = r.randint(3, 4)
        pz = rng.dirichlet(np.full(levels, 4.0))
        pz = 0.1 + 0.9 * pz / pz.sum() * (1 - 0.1 * levels) / 0.9 if False else pz
        e = rng.uniform(0.15, 0.85, size=levels)
        mu, tau = rng.uniform(-2, 2, size=levels), r.uniform(-1.5, 1.5) + rng.uniform(-0.5, 0.5, size=levels)
        zv = rng.choice(levels, size=n, p=pz)
        tv = (rng.uniform(size=n) < e[zv]).astype(int)
        yv = mu[zv] + tau[zv] * tv + rng.normal(size=n)
        nodes.append({"name": "Z", "type": "discrete"})
        edges += [["Z", "T"], ["Z", "Y"]]
        samples["Z"] = [int(v) for v in zv]
        ate, zset = float((pz * tau).sum()), ["Z"]
    elif kind in ("continuous_linear", "continuous_nonlinear"):
        z1 = rng.normal(size=n)
        z2 = 0.3 * z1 + math.sqrt(1 - 0.09) * rng.normal(size=n)
        randomized = kind == "continuous_linear" and r.random() < 0.3
        a = np.array([r.uniform(-0.3, 0.3), r.uniform(-1.2, 1.2), r.uniform(-1.2, 1.2)])
        tv = (rng.uniform(size=n) < (0.5 if randomized else sig(a[0] + a[1] * z1 + a[2] * z2))).astype(int)
        tau0, tau1 = r.uniform(-1.5, 1.5), r.uniform(-0.8, 0.8)
        b1, b2 = r.uniform(-2, 2), r.uniform(-2, 2)
        curve = r.uniform(0.8, 1.6) * r.choice((-1, 1)) if kind == "continuous_nonlinear" else 0.0
        yv = tau0 * tv + tau1 * tv * z1 + b1 * z1 + b2 * z2 + curve * (z1 ** 2 - 1) + rng.normal(size=n)
        nodes += [{"name": "Z1", "type": "continuous"}, {"name": "Z2", "type": "continuous"}]
        edges += [["Z1", "Y"], ["Z2", "Y"], ["Z1", "Z2"]] + ([] if randomized else [["Z1", "T"], ["Z2", "T"]])
        samples["Z1"], samples["Z2"] = _ca_round(z1), _ca_round(z2)
        ate, zset = tau0, ["Z1", "Z2"]
    elif kind == "m_bias":
        u1, u2, zc = rng.normal(size=n), rng.normal(size=n), rng.normal(size=n)
        c = 0.9 * u1 + 0.9 * u2 + 0.5 * rng.normal(size=n)
        tv = (rng.uniform(size=n) < sig(1.2 * u1 + 0.8 * zc)).astype(int)
        tau = r.uniform(-1.5, 1.5)
        yv = tau * tv + 1.5 * u2 + 1.0 * zc + rng.normal(size=n)
        nodes += [{"name": "Z", "type": "continuous"}, {"name": "C", "type": "continuous"},
                  {"name": "U1", "type": "continuous", "observed": False},
                  {"name": "U2", "type": "continuous", "observed": False}]
        edges += [["U1", "T"], ["U1", "C"], ["U2", "C"], ["U2", "Y"], ["Z", "T"], ["Z", "Y"]]
        samples["Z"], samples["C"] = _ca_round(zc), _ca_round(c)
        ate, zset = tau, ["C", "Z"]
    else:
        zc = rng.normal(size=n)
        tau = r.uniform(-1.5, 1.5)
        nodes.append({"name": "Z", "type": "continuous"})
        edges += [["Z", "T"], ["Z", "Y"]]
        samples["Z"] = _ca_round(zc)
        if r.random() < 0.5:                              # a mediator wrongly placed in the adjustment set
            tv = (rng.uniform(size=n) < sig(0.9 * zc)).astype(int)
            gamma, delta = r.uniform(0.5, 1.5), r.uniform(0.5, 1.5)
            m = gamma * tv + 0.5 * zc + rng.normal(size=n)
            yv = tau * tv + delta * m + 1.0 * zc + rng.normal(size=n)
            nodes.append({"name": "M", "type": "continuous"})
            edges += [["T", "M"], ["M", "Y"], ["Z", "M"]]
            samples["M"] = _ca_round(m)
            ate, zset = tau + gamma * delta, ["M", "Z"]
        else:                                             # an unmeasured confounder
            u = rng.normal(size=n)
            tv = (rng.uniform(size=n) < sig(0.9 * zc + 1.2 * u)).astype(int)
            yv = tau * tv + 1.0 * zc + 1.5 * u + rng.normal(size=n)
            nodes.append({"name": "U", "type": "continuous", "observed": False})
            edges += [["U", "T"], ["U", "Y"]]
            ate, zset = tau, ["Z"]
    samples["T"], samples["Y"] = [int(v) for v in tv], _ca_round(yv)
    data = {"nodes": nodes, "edges": edges, "treatment": "T", "outcome": "Y", "adjustment_set": zset,
            "samples": samples}
    g = _ca(data)
    identified = _ca_backdoor_ball(g, zset)
    if identified != (kind not in ("m_bias", "mediator_or_latent")):
        raise GenomeError("causal generator: identification disagrees with its construction")
    return data, {"ate": ate, "scale": float(np.std(yv)), "identified": identified, "kind": kind}


def causal_subregion(data):
    g = _ca(data)
    if any(not i["observed"] for i in g["info"].values()):
        return "latent_nodes"
    if g["z"] and all(g["info"][v]["type"] != "continuous" for v in g["z"]):
        return "discrete_covariates"
    return "continuous_covariates"


# =================================================================== 6. adaptive experiment selection (EIG)
IE_MAX_H, IE_MAX_TESTS, IE_MAX_OUT, IE_MAX_LEN, IE_MAX_NODES = 64, 32, 4, 8, 1000
IE_SCENARIOS = 2000


def _ie(data):
    _obj(data)
    prior = data.get("prior")
    if not isinstance(prior, list) or not 2 <= len(prior) <= IE_MAX_H:
        raise GenomeError(f"prior: 2-{IE_MAX_H} hypothesis probabilities")
    prior = [finite(p, low=0.0, high=1.0, name="prior") for p in prior]
    if abs(sum(prior) - 1.0) > 1e-6:
        raise GenomeError("prior must sum to 1")
    m = len(prior)
    tests = data.get("tests")
    if not isinstance(tests, list) or not 1 <= len(tests) <= IE_MAX_TESTS:
        raise GenomeError(f"tests: 1-{IE_MAX_TESTS} likelihood tables")
    tables = []
    for test in tests:
        lik = test.get("likelihood") if isinstance(test, dict) else None
        if not isinstance(lik, list) or len(lik) != m:
            raise GenomeError("likelihood: one row per hypothesis")
        width = len(lik[0]) if isinstance(lik[0], list) else 0
        if not 2 <= width <= IE_MAX_OUT:
            raise GenomeError(f"each test has 2-{IE_MAX_OUT} outcomes")
        rows = []
        for row in lik:
            if not isinstance(row, list) or len(row) != width:
                raise GenomeError("likelihood rows: equal width")
            row = [finite(p, low=0.0, high=1.0, name="likelihood") for p in row]
            if abs(sum(row) - 1.0) > 1e-6:
                raise GenomeError("likelihood rows must sum to 1")
            rows.append(row)
        tables.append(rows)
    length = bounded_int(data.get("length"), low=1, high=IE_MAX_LEN, name="length")
    return prior, tables, length


def _ie_worst_nodes(tables, length):
    widest = max(len(t[0]) for t in tables)
    return sum(widest ** d for d in range(length))


def _eig(post, P):
    """Mutual information I(H; O) = H(O) - H(O | H) for one test under the current posterior."""
    import numpy as np
    pred = post @ P
    h_o = -float(np.sum(pred[pred > 0] * np.log(pred[pred > 0])))
    with np.errstate(divide="ignore", invalid="ignore"):
        cond = -np.nansum(np.where(P > 0, P * np.log(P), 0.0), axis=1)
    return h_o - float(post @ cond)


def _ie_build(prior, tables, length, chooser):
    import numpy as np
    P = [np.asarray(t, dtype=float) for t in tables]

    def build(post, depth):
        if depth == length:
            return None
        t = chooser(post, P, depth)
        pred = post @ P[t]
        kids = []
        for o in range(P[t].shape[1]):
            if pred[o] <= 1e-15:
                kids.append(None)                         # an impossible outcome: no further tests
                continue
            nxt = post * P[t][:, o]
            kids.append(build(nxt / nxt.sum(), depth + 1))
        return {"test": int(t), "next": kids}
    return build(np.asarray(prior, dtype=float), 0)


def _ie_value(tree, prior, tables):
    """Exact expected posterior mass on the true hypothesis: sum over leaves of sum_h joint_h^2 / sum_h joint_h."""
    import numpy as np
    P = [np.asarray(t, dtype=float) for t in tables]

    def rec(node, joint):
        s = float(joint.sum())
        if s <= 0:
            return 0.0
        if node is None:
            return float((joint ** 2).sum()) / s
        return sum(rec(child, joint * P[node["test"]][:, o]) for o, child in enumerate(node["next"]))
    return rec(tree, np.asarray(prior, dtype=float))


def _ie_count(tree):
    return 0 if tree is None else 1 + sum(_ie_count(c) for c in tree["next"])


def ie_solve(data, budget):
    import numpy as np
    prior, tables, length = _ie(data)
    if _ie_worst_nodes(tables, length) > IE_MAX_NODES:
        return _abstain(f"an adaptive policy tree could exceed {IE_MAX_NODES} nodes; use an open-loop design")
    if data.get("test_costs") is not None and len(set(data["test_costs"])) > 1:
        return _abstain("unequal test costs: greedy information gain ignores cost (needs a cost-aware design)")

    def greedy(post, P, depth):
        return int(np.argmax([_eig(post, p) for p in P]))
    tree = _ie_build(prior, tables, length, greedy)
    value = _ie_value(tree, prior, tables)
    return answer({"policy": tree, "expected_posterior_on_truth": value},
                  {"method": "adaptive greedy expected information gain (mutual information) per node; policy "
                             "tree over outcomes", "nodes": _ie_count(tree), "length": length,
                   "expected_posterior_on_truth": value,
                   "model": "declared prior and likelihood tables are taken as correct"})


def _ie_policy(output, tables, length):
    """Normalise an output to a policy tree (open-loop sequences become outcome-independent trees)."""
    if not isinstance(output, dict):
        return None
    if "sequence" in output and "policy" not in output:
        seq = output["sequence"]
        if not isinstance(seq, list) or not 1 <= len(seq) <= length:
            return None

        def chain(d):
            if d == len(seq):
                return None
            t = seq[d]
            if type(t) is not int or not 0 <= t < len(tables):
                raise GenomeError("bad test index")
            return {"test": t, "next": [chain(d + 1) for _ in range(len(tables[t][0]))]}
        try:
            return chain(0)
        except GenomeError:
            return None
    tree, count = output.get("policy"), [0]

    def ok(node, depth):
        if node is None:
            return True
        count[0] += 1
        if (not isinstance(node, dict) or depth >= length or count[0] > IE_MAX_NODES
                or type(node.get("test")) is not int or not 0 <= node["test"] < len(tables)):
            return False
        kids = node.get("next")
        return (isinstance(kids, list) and len(kids) == len(tables[node["test"]][0])
                and all(ok(c, depth + 1) for c in kids))
    return tree if isinstance(tree, dict) and ok(tree, 0) else None


def ie_verify(data, output, certificate):
    prior, tables, length = _ie(data)
    tree = _ie_policy(output, tables, length) if isinstance(output, dict) and "policy" in output else None
    if tree is None:
        return {"policy_well_formed": False}
    m = len(prior)
    checks = {"policy_well_formed": True, "every_node_maximises_information_gain": True,
              "reachable_outcomes_have_full_depth": True}

    def info_gain_kl(logpost, t):
        """Expected KL from predictive to likelihood rows (a different formula for the same gain)."""
        post = [math.exp(v) for v in logpost]
        z = sum(post)
        post = [p / z for p in post]
        width = len(tables[t][0])
        pred = [sum(post[h] * tables[t][h][o] for h in range(m)) for o in range(width)]
        return sum(post[h] * tables[t][h][o] * math.log(tables[t][h][o] / pred[o])
                   for h in range(m) for o in range(width) if tables[t][h][o] > 0 and post[h] > 0)

    total = [0.0]

    def walk(node, logpost, depth):
        joint = [math.exp(v) for v in logpost]
        if node is None:
            s = sum(joint)
            if depth < length and s > 1e-300:
                checks["reachable_outcomes_have_full_depth"] = False
            total[0] += sum(j * j for j in joint) / s if s > 0 else 0.0
            return
        gains = [info_gain_kl(logpost, t) for t in range(len(tables))]
        if gains[node["test"]] < max(gains) - 1e-9:
            checks["every_node_maximises_information_gain"] = False
        for o, child in enumerate(node["next"]):
            nxt = [lp + math.log(tables[node["test"]][h][o]) if tables[node["test"]][h][o] > 0 else -math.inf
                   for h, lp in enumerate(logpost)]
            if all(v == -math.inf for v in nxt):
                continue
            walk(child, nxt, depth + 1)

    walk(tree, [math.log(p) if p > 0 else -math.inf for p in prior], 0)
    claimed = output.get("expected_posterior_on_truth")
    checks["expected_value_recomputed"] = _is_num(claimed) and abs(claimed - total[0]) <= 1e-9 + 1e-7 * total[0]
    return checks


def ie_instance(seed):
    r = random.Random(6_600_000 + seed)
    m, K, length = r.randint(8, 24), r.randint(8, 14), r.randint(3, 5)
    raw = [r.expovariate(1.0) ** 1.5 + 1e-3 for _ in range(m)]
    prior = [round(x / sum(raw), 6) for x in raw]
    prior[-1] = round(1.0 - sum(prior[:-1]), 6)
    tests, traps = [], 0
    for k in range(K):
        width = r.choice((2, 2, 3))
        kind = r.random()
        rows = []
        if kind < 0.6:                                     # a partition test with symmetric noise
            acc, cls = r.uniform(0.6, 0.97), [r.randrange(width) for _ in range(m)]
            for h in range(m):
                rows.append([acc if o == cls[h] else (1 - acc) / (width - 1) for o in range(width)])
        elif kind < 0.85:                                  # a near-uniform trap: high outcome entropy, little information
            traps += 1
            for _ in range(m):
                row = [1.0 / width + r.uniform(-0.03, 0.03) for _ in range(width)]
                rows.append([x / sum(row) for x in row])
        else:                                              # a sharp test that isolates a small set
            members = set(r.sample(range(m), r.randint(1, 2)))
            for h in range(m):
                hit = 0.99 if h in members else 0.01
                rows.append([1 - hit, hit] + [0.0] * (width - 2) if width == 2 else
                            [(1 - hit) / 2, hit, (1 - hit) / 2])
        clean = []
        for row in rows:
            row = [round(x, 4) for x in row]
            row[-1] = round(1.0 - sum(row[:-1]), 4)
            clean.append(row)
        tests.append({"name": f"test_{k}", "likelihood": clean})
    data = {"prior": prior, "tests": tests, "length": length, "seed": 37_000 + seed}
    scenarios = []
    for _ in range(IE_SCENARIOS):
        h = r.choices(range(m), weights=prior)[0]
        scenarios.append((h, [r.random() for _ in range(length)]))
    return data, {"scenarios": scenarios, "trap_tests": traps}


def ie_subregion(data):
    return f"length_{data['length']}"


def ie_score(data, truth, output):
    prior, tables, length = _ie(data)
    scen = truth["scenarios"]
    base = sum(prior[h] for h, _ in scen) / len(scen)
    if output is None:
        return {"quality": base, "category": "abstain"}                   # no experiments: the prior
    tree = _ie_policy(output, tables, length)
    if tree is None:
        return {"quality": base - 1.0, "category": "wrong"}
    memo, total = {}, 0.0
    for h, us in scen:
        node, path, d = tree, [], 0
        while node is not None and d < length:
            row = tables[node["test"]][h]
            acc, o = 0.0, len(row) - 1
            for k, p in enumerate(row):
                acc += p
                if us[d] < acc:
                    o = k
                    break
            path.append((node["test"], o))
            node = node["next"][o]
            d += 1
        key = tuple(path)
        if key not in memo:
            joint = list(prior)
            for t, o in key:
                joint = [j * tables[t][g][o] for g, j in enumerate(joint)]
            s = sum(joint)
            memo[key] = [j / s for j in joint] if s > 0 else list(prior)
        total += memo[key][h]
    return {"quality": total / len(scen), "category": "correct"}


def ie_random(data):
    """Baseline: a random test order (open loop), seeded."""
    prior, tables, length = _ie(data)
    r = random.Random(bounded_int(data.get("seed", 0), low=0, high=10**9, name="seed"))
    K = len(tables)
    seq = r.sample(range(K), length) if length <= K else [r.randrange(K) for _ in range(length)]
    return {"sequence": seq}


def ie_competitor(data):
    """Competitor: the better (exact expected posterior on truth) of adaptive uncertainty sampling and a
    fixed expert order (tests ranked once by information gain under the prior, cycled)."""
    import numpy as np
    prior, tables, length = _ie(data)
    if _ie_worst_nodes(tables, length) > IE_MAX_NODES:
        return None

    def entropy_pick(post, P, depth):
        scores = []
        for p in P:
            pred = post @ p
            scores.append(-float(np.sum(pred[pred > 0] * np.log(pred[pred > 0]))))
        return int(np.argmax(scores))
    pr = np.asarray(prior, dtype=float)
    order = sorted(range(len(tables)), key=lambda t: (-_eig(pr, np.asarray(tables[t], dtype=float)), t))

    def expert_pick(post, P, depth):
        return order[depth % len(order)]
    best = None
    for name, chooser in (("uncertainty_sampling", entropy_pick), ("fixed_expert_order", expert_pick)):
        tree = _ie_build(prior, tables, length, chooser)
        value = _ie_value(tree, prior, tables)
        if best is None or value > best["expected_posterior_on_truth"] + 1e-12:
            best = {"policy": tree, "expected_posterior_on_truth": value, "rule": name}
    return best


# =================================================================== genomes
INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.mechanism.vcg_multiunit", version="1.0.0", family="mech_vcg", layer=3,
            operation="vcg_allocate_units", epistemic_class="strategic",
            subgeometry="identical-unit allocation; private values; quasi-linear bidders",
            source_provenance="Vickrey (1961), Clarke (1971), Groves (1973): Clarke-pivot VCG",
            native_representation="supply k; each participant's marginal values for 1..m units",
            required_inputs=("units", "bidders"),
            output_contract={"allocation": "[units per bidder]", "payments": "[Clarke-pivot payment]",
                             "welfare": "float", "efficient": "bool"},
            algorithm_or_runtime="pooled-marginal greedy (diminishing marginals) or exact DP (general); n + 1 "
                                 "welfare solves for externalities",
            parameters={"max_bidders": VCG_MAX_BIDDERS, "max_units": VCG_MAX_UNITS, "dp_ops": VCG_DP_OPS},
            composition_inputs=("participant reports", "supply"), composition_outputs=("allocation", "payments"),
            evidence_type="decision_analysis",
            verification_method="independent NumPy DP recomputes the optimal welfare with and without each "
                                "bidder: allocative optimality, Clarke externalities, individual rationality, "
                                "no subsidy",
            confidence_semantics="exact given the reports; truthful reporting is a dominant strategy only under "
                                 "private values, quasi-linear utility and no budgets",
            resource_profile="O(N log N) per welfare solve (N pooled marginals); n + 1 solves",
            latency_profile="milliseconds at benchmark size",
            known_strengths=("truthful reporting is a dominant strategy, so participants need not out-guess "
                             "each other", "allocatively efficient under the declared values",
                             "individually rational with no subsidies (Clarke pivot); scored on welfare, "
                             "never on revenue extracted from people"),
            known_failure_modes=("revenue can be low or zero: not revenue-optimal",
                                 "vulnerable to collusion and shill (false-name) bids",
                                 "the pay-as-bid shading benchmark is a simulated behavioural model, not "
                                 "observed people"),
            counterindications=("budget-constrained participants", "interdependent or common values",
                                "heterogeneous combinatorial goods (needs full winner determination)"),
            abstention_conditions=("budgets declared", "value_model other than private",
                                   "non-diminishing valuations beyond the bounded DP"),
            benchmark_suite="asymmetric strong/weak bidder classes with 1-3 unit diminishing demand and scarce "
                            "supply; efficiency against the optimum from an independent DP; seeds 0-9 dev / "
                            "1000-1029 held out",
            baseline="pay-as-bid auction; bidders shade by a class-symmetric factor from a simulated iterated "
                     "best response",
            competitor="posted price at the median of the seeded value prior with random-arrival rationing",
            **_common()),
        solve=vcg_solve, verify=vcg_verify, instance=vcg_instance, score=vcg_score, baseline=vcg_pay_as_bid,
        competitor=vcg_posted_price, subregion=vcg_subregion, tolerance=1e-9,
        notes={"purpose": "welfare-compatible truthful allocation rules; the score is allocative efficiency"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.verification.explicit_state_bfs", version="1.0.0", family="verify_modelcheck",
            layer=3, operation="model_check_safety", epistemic_class="deductive",
            subgeometry="finite guarded-command transition systems; safety invariants",
            source_provenance="explicit-state model checking (Clarke, Emerson, Sifakis; Holzmann's SPIN lineage)",
            native_representation="typed JSON guarded commands over bounded integer variables; no code evaluation",
            required_inputs=("system",),
            output_contract={"verdict": "SAFE | UNSAFE", "reachable_states": "int (SAFE)",
                             "initial/commands/violating_state": "shortest counterexample (UNSAFE)"},
            algorithm_or_runtime="breadth-first search over hashed states with closure-compiled expressions",
            parameters={"max_states": MC_NATIVE_STATES, "max_trace": MC_MAX_TRACE, "max_vars": MC_MAX_VARS},
            composition_inputs=("transition system", "invariant"), composition_outputs=("verdict", "trace"),
            evidence_type="exhaustive_check",
            verification_method="UNSAFE: counterexample replay by an independent interpreter; SAFE: independent "
                                "NumPy level-synchronous recount of the reachable set (count, digest, invariant)",
            confidence_semantics="exact for the declared model within the state cap; says nothing about code "
                                 "the model abstracts",
            resource_profile="memory and time linear in reachable states (<= 50,000)",
            latency_profile="milliseconds to ~1 s at the cap",
            known_strengths=("decides safety exactly when the reachable space fits",
                             "shortest counterexamples", "finds deep bugs that random testing misses"),
            known_failure_modes=("state explosion: abstains beyond 50,000 reachable states",
                                 "only as faithful as the model of the real system"),
            counterindications=("liveness or temporal-logic properties", "unbounded or very wide state spaces "
                                "(use symbolic or inductive methods)"),
            abstention_conditions=("property other than safety", "more than 50,000 reachable states"),
            benchmark_suite="Peterson mutex (correct and two planted bugs), combination locks, producer races, "
                            "non-inductive parity counters, wide resource pools; truth by an independent DFS or "
                            "construction; seeds 0-9 dev / 1000-1029 held out",
            baseline="random-walk testing, 10,000 steps in walks of 250; no violation seen is reported SAFE",
            competitor="Z3 bounded model checking interleaved with k-induction, both to depth 15",
            **_common()),
        solve=mc_solve, verify=mc_verify, instance=mc_instance, score=mc_score, baseline=mc_random_walk,
        competitor=mc_bmc_kinduction, subregion=mc_subregion, tolerance=1e-9),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.control.linear_mpc_box", version="1.0.0", family="control_mpc", layer=3,
            operation="mpc_track", epistemic_class="physical",
            subgeometry="linear time-invariant plant (double integrator), input bounds, reference tracking",
            source_provenance="receding-horizon control (Mayne et al. 2000); BVLS (Stark-Parker 1995) in SciPy",
            native_representation="dt, input bound, initial state, reference, disturbance, quadratic weights",
            required_inputs=("dt", "u_max", "x0", "reference", "disturbance", "weights"),
            output_contract={"inputs": "[u_t]", "cost": "float", "final_state": "[p, v]"},
            algorithm_or_runtime="per step: condensed box-constrained QP as bounded least squares (BVLS), DARE "
                                 "terminal cost, first input applied",
            parameters={"max_steps": MPC_MAX_STEPS, "max_horizon": MPC_MAX_HORIZON},
            composition_inputs=("plant model", "reference"), composition_outputs=("input trace", "cost"),
            evidence_type="control_trace",
            verification_method="independent re-simulation of the returned inputs: bounds, cost and final state",
            confidence_semantics="the trace is exact for the declared model and disturbance sequence; real "
                                 "plants differ from the model",
            resource_profile="one N-variable bounded least squares per step (N <= 60)",
            latency_profile="~3 ms per step; < 0.5 s for 150 steps",
            known_strengths=("respects input bounds by construction rather than clipping",
                             "anticipates reference changes when a preview is available",
                             "reduces to LQR when constraints are inactive"),
            known_failure_modes=("model mismatch and unmeasured disturbances degrade tracking (no integral action)",
                                 "a short horizon with a DARE terminal cost underestimates saturated cost-to-go"),
            counterindications=("state constraints", "partial measurement without an observer",
                                "nonlinear or unknown plants"),
            abstention_conditions=("state_bounds declared", "measurement other than full_state"),
            benchmark_suite="double integrator tracking steps, large saturating steps, sinusoids and mixtures, with "
                            "and without reference preview, noisy and biased velocity disturbances; cost relative "
                            "to zero input; seeds 0-9 dev / 1000-1029 held out",
            baseline="saturated PD (state-proportional) controller, critically damped at w = (q/r)^(1/4)",
            competitor="infinite-horizon discrete LQR (SciPy DARE) with input clipping",
            dependency="scipy", **_common()),
        solve=mpc_solve, verify=mpc_verify, instance=mpc_instance, score=mpc_score, baseline=mpc_pd,
        competitor=mpc_lqr, subregion=mpc_subregion, tolerance=1e-6),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.synthesis.cegis_threshold", version="1.0.0", family="synth_cegis", layer=3,
            operation="cegis_synthesize", epistemic_class="constraint_feasibility",
            subgeometry="bounded integer parameters that must satisfy a spec on every point of a finite domain",
            source_provenance="counterexample-guided inductive synthesis (Solar-Lezama 2006); Z3 (de Moura-Bjorner)",
            native_representation="n Boolean inputs, labels as a 2^n-bit hex string, weight bound B",
            required_inputs=("n", "labels", "weight_bound"),
            output_contract={"realizable": "bool", "weights": "[int] (realizable)", "bias": "int (realizable)"},
            algorithm_or_runtime="Z3 integer synthesis on a growing counterexample set; exhaustive NumPy oracle",
            parameters={"native_n": SY_NATIVE_N, "max_iterations": SY_MAX_ITER},
            composition_inputs=("finite specification",), composition_outputs=("parameters", "unsat witness"),
            evidence_type="exhaustive_check",
            verification_method="realizable: independent pure-Python check of every domain point; unrealizable: "
                                "independent HiGHS MILP proves the witness subset infeasible",
            confidence_semantics="exact over the declared finite domain and bounds",
            resource_profile="a few dozen small incremental SMT checks plus vectorised 2^n checks",
            latency_profile="tens to hundreds of milliseconds at n <= 12",
            known_strengths=("only a small subset of the domain reaches the solver",
                             "unrealizability is proved by a small witness set",
                             "the oracle is exhaustive, so returned parameters are never wrong"),
            known_failure_modes=("iteration count can grow when many points sit near the boundary",
                                 "exhaustive oracle is exponential in n"),
            counterindications=("infinite or very large domains (needs a symbolic verifier)",
                                "specifications that are not checkable pointwise"),
            abstention_conditions=("n above 13", "iteration or latency budget exhausted (UNKNOWN)"),
            benchmark_suite="planted threshold rules (small and near-bound weights), XOR-face non-separable "
                            "labellings, bit-comparators needing weights beyond the bound; seeds 0-9 dev / "
                            "1000-1029 held out",
            baseline="Z3 synthesis on a fixed random sample of 128 domain points (no counterexample feedback)",
            competitor="Z3 on the full-domain encoding (all 2^n constraints at once, SMT-LIB text)",
            dependency="z3-solver", **_common()),
        solve=cegis_solve, verify=cegis_verify, instance=cegis_instance, score=cegis_score, baseline=cegis_sample,
        competitor=cegis_full_domain, subregion=cegis_subregion, tolerance=1e-9),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.causal.backdoor_adjustment", version="1.0.0", family="causal_backdoor", layer=3,
            operation="backdoor_ate", epistemic_class="causal",
            subgeometry="average treatment effect of a binary treatment from observational data and a declared DAG",
            source_provenance="Pearl (1993, 2009) backdoor criterion; Robins g-formula; regression adjustment",
            native_representation="declared DAG (latent nodes marked), treatment, outcome, adjustment set, samples",
            required_inputs=("nodes", "edges", "treatment", "outcome", "adjustment_set", "samples"),
            output_contract={"ate": "float", "se": "float", "adjustment_set": "[node]", "estimator": "str"},
            algorithm_or_runtime="d-separation by moralised ancestral graph; stratification (discrete covariates) "
                                 "or OLS with treatment interactions (continuous)",
            parameters={"max_rows": CA_MAX_ROWS, "max_nodes": CA_MAX_NODES},
            composition_inputs=("causal graph", "observational data"), composition_outputs=("ate", "se"),
            evidence_type="statistical_estimate",
            verification_method="independent Bayes-ball d-separation re-check of the backdoor criterion and an "
                                "independent recomputation (dictionary strata or normal equations)",
            confidence_semantics="unbiased only if the declared DAG is right and the outcome model is adequate; "
                                 "se is a normal-approximation standard error",
            resource_profile="O(rows x covariates)", latency_profile="milliseconds",
            known_strengths=("refuses to answer when the declared adjustment set does not identify the effect",
                             "efficient when the outcome model is correctly specified",
                             "stratification is model-free for discrete covariates"),
            known_failure_modes=("regression adjustment is biased under outcome-model misspecification",
                                 "a wrong DAG makes the identification check meaningless",
                                 "positivity failures in small strata"),
            counterindications=("unmeasured confounding not represented in the DAG", "continuous treatments",
                                "strong outcome nonlinearity in continuous covariates (prefer doubly robust)"),
            abstention_conditions=("declared set fails the backdoor criterion (non-identified)",
                                   "adjustment variable latent or without samples",
                                   "positivity or rank failure"),
            benchmark_suite="discrete and continuous confounding, randomised trials with prognostic covariates, "
                            "nonlinear outcomes, M-bias colliders, mediators and latent confounders in the declared "
                            "set; truth from the generating structural model; seeds 0-9 dev / 1000-1029 held out",
            baseline="naive difference in means (no adjustment, no identification check)",
            competitor="backdoor gate (NetworkX d-separation) + Hajek IPW with a logistic propensity (IRLS)",
            **_common()),
        solve=causal_solve, verify=causal_verify, instance=causal_instance, score=causal_score,
        baseline=causal_naive, competitor=causal_ipw, subregion=causal_subregion, tolerance=1e-6),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.experiment.greedy_eig_policy", version="1.0.0", family="info_experiment",
            layer=3, operation="design_test_sequence", epistemic_class="strategic",
            subgeometry="sequential test selection over a discrete hypothesis space with known likelihoods",
            source_provenance="Lindley (1956) expected information; greedy adaptive Bayesian experimental design",
            native_representation="prior over hypotheses; per-test likelihood tables P(outcome | hypothesis)",
            required_inputs=("prior", "tests", "length"),
            output_contract={"policy": "tree {test, next[outcome]}", "expected_posterior_on_truth": "float"},
            algorithm_or_runtime="per node: argmax mutual information I(H; O_t) under the current posterior",
            parameters={"max_nodes": IE_MAX_NODES, "max_length": IE_MAX_LEN},
            composition_inputs=("hypotheses", "test catalogue"), composition_outputs=("test policy",),
            evidence_type="decision_analysis",
            verification_method="every node's posterior and information gain recomputed in log space with the KL "
                                "form; the expected posterior on truth recomputed by enumeration",
            confidence_semantics="optimal one step ahead under the declared model; not globally optimal",
            resource_profile="nodes x tests x hypotheses x outcomes", latency_profile="milliseconds",
            known_strengths=("adapts the next test to the outcomes so far",
                             "ignores high-entropy but uninformative tests that fool uncertainty sampling"),
            known_failure_modes=("greedy, not lookahead-optimal", "wrong likelihood tables mislead it",
                                 "Shannon gain is a proxy for the posterior-mass objective"),
            counterindications=("unequal test costs", "very long horizons with wide outcome alphabets"),
            abstention_conditions=("policy tree could exceed 1000 nodes", "unequal test costs declared"),
            benchmark_suite="8-24 hypotheses, 8-14 tests (partition, near-uniform trap and sharp tests), length "
                            "3-5; 2000 seeded truth scenarios per instance; seeds 0-9 dev / 1000-1029 held out",
            baseline="random test order (open loop)",
            competitor="better of adaptive uncertainty sampling (max outcome entropy) and a fixed expert order "
                       "(tests ranked once by prior information gain), chosen by exact expected value",
            **_common()),
        solve=ie_solve, verify=ie_verify, instance=ie_instance, score=ie_score, baseline=ie_random,
        competitor=ie_competitor, subregion=ie_subregion, tolerance=1e-9),
]
