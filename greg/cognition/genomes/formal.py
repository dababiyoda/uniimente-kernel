"""Layer 3 formal intelligence: property-based testing (search for a counterexample to a declared property).

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.json``, ``L3.formal.property_based``)
lists property-based testing as ABSENT. Effect, not metaphor: given a function under test and a property it must
satisfy, find an input on which the property fails, quickly and without a model of the function's semantics; a
found counterexample is a fact anyone can re-execute. "No counterexample found" is never a proof and is never
reported as one: the genome then answers UNKNOWN.

Acquire before inventing: Hypothesis (the standard Python property-based testing library) is not installed in this
container (``pip list``, 2026-10-21), so its core mechanisms are reproduced in a few dozen lines rather than taken as
a dependency: boundary-biased generation, small-value bias, value reuse across arguments, a dictionary of constants
mined from the code under test (the fuzzing literature's "magic number" dictionaries, AFL/libFuzzer), and greedy
shrinking of a failing input toward zero. The function and the property are written in the typed JSON expression
language of ``verify_modelcheck`` (``solvers_c``: linear integer arithmetic, ``mod`` by a literal, ``min``/``max``,
``ite``, comparisons and connectives; no code is ever evaluated). Its closure compiler runs the search, its
independent recursive interpreter (``_mc_eval``) checks answers, and its Z3 translation is the competitor.

* ``formal_property_search`` (``find_property_counterexample``): seeded generation within a fixed budget of 2,000
  evaluations, then shrinking. Verified by re-execution of the function and the property on the claimed input with
  the independent interpreter.

Native geometry: generated integer functions with a planted bug (a guard that changes the result on a region of
known size: a literal point, a literal pair, a linear relation, a residue class, a corner of the domain, an
off-by-one comparison, a clamp bound, a wide region), plus bug-free decoys; the property is equality with the
reference specification, so the truth (a witness, or "no counterexample exists") is known by construction.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output of any
method here creates authority. Development seeds 0-9 only.
"""
from __future__ import annotations

import hashlib
import json
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int
from .solvers_c import MC_MAX_VALUE, _RESERVED, _mc_compile, _mc_eval, _mc_mag, _mc_type, _mc_z3

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4 (restore the full five-layer scope)",
           "docs/collaboration/MIND-COVERAGE-2026-10-21.json (L3.formal.property_based ABSENT)",
           "greg/cognition/genomes/solvers_c.py verify_modelcheck (expression language, interpreter, Z3 encoding)")
PB_MAX_PARAMS = 6
PB_EVALUATIONS = 2000            # evaluations of the function and property per request (search and shrinking)
PB_SHRINK_MAX = 200              # at most this many of them are spent shrinking a found counterexample
PB_Z3_SECONDS = 4.0
RESULT = "result"                # the property's name for the function's return value
VERDICT = "COUNTEREXAMPLE"
PROVEN = "NO_COUNTEREXAMPLE_PROVEN"   # only the symbolic competitor may say this; the genome never does


def _input(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    fut, prop = data.get("function_under_test"), data.get("property")
    if not isinstance(fut, dict) or set(fut) != {"parameters", "body"}:
        raise GenomeError("function_under_test: {parameters: [{name, min, max}], body: integer expression}")
    params = fut["parameters"]
    if not isinstance(params, list) or not 1 <= len(params) <= PB_MAX_PARAMS:
        raise GenomeError(f"function_under_test.parameters: 1-{PB_MAX_PARAMS} bounded integer parameters")
    names, lo, hi = [], [], []
    for p in params:
        name = p.get("name") if isinstance(p, dict) else None
        if (not isinstance(name, str) or not name.isidentifier() or len(name) > 32 or name in _RESERVED
                or name == RESULT or name in names or set(p) != {"name", "min", "max"}):
            raise GenomeError("parameter: {name, min, max}; names unique identifiers, not operators or 'result'")
        a = bounded_int(p["min"], low=-MC_MAX_VALUE, high=MC_MAX_VALUE, name=f"{name}.min")
        b = bounded_int(p["max"], low=a, high=MC_MAX_VALUE, name=f"{name}.max")
        names.append(name)
        lo.append(a)
        hi.append(b)
    index = {n: i for i, n in enumerate(names)}
    counter = [0]
    if _mc_type(fut["body"], index, counter) != "int":
        raise GenomeError("function_under_test.body must be an integer expression")
    with_result = {**index, RESULT: len(names)}
    if _mc_type(prop, with_result, counter) != "bool":
        raise GenomeError("property must be a boolean expression over the parameters and 'result'")
    mags = {n: max(abs(a), abs(b)) for n, a, b in zip(names, lo, hi)}
    mags[RESULT] = _mc_mag(fut["body"], mags)
    _mc_mag(prop, mags)
    return {"names": names, "lo": lo, "hi": hi, "body": fut["body"], "property": prop, "index": index,
            "with_result": with_result}


def _literals(expr, out):
    if type(expr) is int:
        out.add(expr)
    elif isinstance(expr, list):
        for a in expr[1:]:
            _literals(a, out)
    return out


def _seed_of(data, tag):
    return int(hashlib.sha256((tag + json.dumps(data, sort_keys=True)).encode()).hexdigest()[:16], 16)


def _pools(spec):
    """Per parameter: boundary values and the dictionary of constants mined from the body and the property."""
    mined = set()
    for c in _literals(spec["body"], set()) | _literals(spec["property"], set()):
        mined |= {c, c - 1, c + 1, -c}
    out = []
    for a, b in zip(spec["lo"], spec["hi"]):
        edge = sorted({v for v in (a, b, a + 1, b - 1, 0, 1, -1) if a <= v <= b})
        out.append((edge, sorted(v for v in mined if a <= v <= b)))
    return out


def _search(spec, rng, budget, strategy):
    """Generate inputs until the property fails or the budget is spent; returns (failing input or None, used)."""
    body = _mc_compile(spec["body"], spec["index"])
    prop = _mc_compile(spec["property"], spec["with_result"])
    lo, hi = spec["lo"], spec["hi"]
    pools = _pools(spec) if strategy == "pbt" else None
    seen, used, attempts = set(), 0, 0
    while used < budget and attempts < 4 * budget:
        attempts += 1
        x = []
        for i, (a, b) in enumerate(zip(lo, hi)):
            if strategy == "uniform":
                x.append(rng.randint(a, b))
                continue
            edge, mined = pools[i]
            u = rng.random()
            if u < 0.30 and mined:
                v = rng.choice(mined)
            elif u < 0.45:
                v = rng.choice(edge)
            elif u < 0.55 and x:
                v = min(max(rng.choice(x), a), b)
            elif u < 0.65:
                v = min(max(rng.randint(-8, 8), a), b)
            else:
                v = rng.randint(a, b)
            x.append(v)
        x = tuple(x)
        if x in seen:
            continue
        seen.add(x)
        used += 1
        if not prop(x + (body(x),)):
            return x, used
    return None, used


def _shrink(spec, x, allowance):
    """Greedy shrinking toward zero (each parameter: 0 or its nearest bound, half, one step), keeping the failure."""
    body = _mc_compile(spec["body"], spec["index"])
    prop = _mc_compile(spec["property"], spec["with_result"])
    lo, hi = spec["lo"], spec["hi"]
    used, x, improved = 0, list(x), True

    def size(v):
        return sum(abs(t) for t in v)
    while improved and used < allowance:
        improved = False
        for i in range(len(x)):
            zero = min(max(0, lo[i]), hi[i])
            for v in (zero, zero + (x[i] - zero) // 2, x[i] - (1 if x[i] > zero else -1 if x[i] < zero else 0)):
                if used >= allowance or v == x[i] or not lo[i] <= v <= hi[i]:
                    continue
                y = x[:i] + [v] + x[i + 1:]
                used += 1
                if size(y) < size(x) and not prop(tuple(y) + (body(tuple(y)),)):
                    x, improved = y, True
                    break
    return tuple(x), used


def _counterexample(spec, x):
    env = dict(zip(spec["names"], x))
    return {"verdict": VERDICT, "counterexample": env, "result": _mc_eval(spec["body"], env)}


def property_search_solve(data, budget):
    spec = _input(data)
    rng = random.Random(_seed_of(data, "pbt:"))
    x, used = _search(spec, rng, PB_EVALUATIONS, "pbt")
    if x is None:
        return answer(None, {"evaluations": used, "reason": "no counterexample found within the budget"},
                      status="UNKNOWN",
                      missing=[f"no counterexample in {used} evaluations; this is not a proof that none exists"])
    found = used
    x, shrunk = _shrink(spec, x, min(PB_SHRINK_MAX, PB_EVALUATIONS - used))
    return answer(_counterexample(spec, x),
                  {"method": "boundary-biased generation, small-value bias, argument reuse, constants mined from "
                             "the body and property; greedy shrinking toward zero",
                   "evaluations": found + shrunk, "found_at_evaluation": found, "shrink_evaluations": shrunk,
                   "budget": PB_EVALUATIONS})


def _shape(output, spec):
    if not isinstance(output, dict) or set(output) != {"verdict", "counterexample", "result"}:
        return False
    cx = output["counterexample"]
    return (output["verdict"] == VERDICT and isinstance(cx, dict) and sorted(cx) == sorted(spec["names"])
            and all(type(v) is int for v in cx.values()) and type(output["result"]) is int)


def _refutes(spec, output) -> tuple[bool, bool, bool]:
    """Independent re-execution: (inputs in domain, result re-executed equal, property false on re-execution)."""
    cx = output["counterexample"]
    domain = all(a <= cx[n] <= b for n, a, b in zip(spec["names"], spec["lo"], spec["hi"]))
    if not domain:
        return False, False, False
    result = _mc_eval(spec["body"], dict(cx))
    holds = _mc_eval(spec["property"], {**cx, RESULT: result})
    return True, result == output["result"], not holds


def property_search_verify(data, output, certificate):
    spec = _input(data)
    if not _shape(output, spec):
        return {"output_shape": False}
    domain, result_ok, violated = _refutes(spec, output)
    evaluations = certificate.get("evaluations") if isinstance(certificate, dict) else None
    return {"output_shape": True, "inputs_in_declared_domain": domain, "result_reexecuted": result_ok,
            "property_violated_on_reexecution": violated,
            "within_declared_budget": type(evaluations) is int and 1 <= evaluations <= PB_EVALUATIONS}


def property_search_score(data, truth, output):
    """Found a valid counterexample: 1. A proof of absence where none exists: 1. Silence: 0 (abstain). A claimed
    counterexample that re-execution refutes, or a proof of absence where a bug exists: -1 (wrong)."""
    spec = _input(data)
    if output is None:
        return {"quality": 0.0, "category": "abstain"}
    if isinstance(output, dict) and output.get("verdict") == PROVEN and set(output) == {"verdict", "counterexample",
                                                                                         "result"}:
        return ({"quality": 1.0, "category": "correct"} if not truth["buggy"]
                else {"quality": -1.0, "category": "wrong"})
    if not _shape(output, spec) or not all(_refutes(spec, output)):
        return {"quality": -1.0, "category": "wrong"}
    return {"quality": 1.0, "category": "correct"}


def property_search_uniform(data):
    """Baseline: uniform random inputs over the declared domain, the same 2,000-evaluation budget, no shrinking."""
    spec = _input(data)
    x, _ = _search(spec, random.Random(_seed_of(data, "uniform:")), PB_EVALUATIONS, "uniform")
    return None if x is None else _counterexample(spec, x)


def property_search_z3(data):
    """Competitor: symbolic search. Z3 (linear integer arithmetic) is asked for a domain input whose result violates
    the property; sat gives a counterexample, unsat a proof that none exists, unknown or timeout (4 s) abstains."""
    import z3
    spec = _input(data)
    ctx = z3.Context()
    xs = [z3.Int(n, ctx) for n in spec["names"]] + [z3.Int(RESULT, ctx)]
    s = z3.Solver(ctx=ctx)
    s.set("random_seed", 0)
    s.set("timeout", int(PB_Z3_SECONDS * 1000))
    for x, a, b in zip(xs, spec["lo"], spec["hi"]):
        s.add(x >= a, x <= b)
    s.add(xs[-1] == _mc_z3(spec["body"], xs, spec["index"], ctx))
    s.add(z3.Not(_mc_z3(spec["property"], xs, spec["with_result"], ctx)))
    verdict = s.check()
    if verdict == z3.sat:
        m = s.model()
        return _counterexample(spec, tuple(m.eval(x, model_completion=True).as_long() for x in xs[:-1]))
    if verdict == z3.unsat:
        return {"verdict": PROVEN, "counterexample": None, "result": None}
    return None


# ------------------------------------------------------------------ native benchmark
PB_KINDS = ("point_literal", "pair_literal", "linear_relation", "residue", "corner", "off_by_one", "clamp_bound",
            "wide", "clean_decoy", "clean_rewrite")


def _spec_expr(r, names, lo, hi):
    a, b = r.sample(names, 2)
    c = names[-1]
    k1, k2 = r.randint(-9, 9) or 1, r.randint(-9, 9) or 2
    shape = r.choice(("linear", "maxdiff", "absdiff", "mod", "clamp"))
    if shape == "linear":
        return ["+", ["*", k1, a], ["*", k2, b], r.randint(-50, 50)]
    if shape == "maxdiff":
        return ["max", a, ["-", b, c]]
    if shape == "absdiff":
        return ["ite", ["<", a, b], ["-", b, a], ["-", a, b]]
    if shape == "mod":
        return ["+", ["mod", ["+", a, ["*", k2, b]], r.randint(7, 997)], c]
    low = r.randint(lo, (lo + hi) // 2)
    return ["min", ["max", a, low], r.randint(low, hi)]


def pb_instance(seed):
    r = random.Random(f"genome:formal_property_search:{seed}")
    nvars = r.randint(2, 4)
    width = r.choice((1000, 10_000, 50_000))
    lo, hi = (-width, width) if r.random() < 0.6 else (0, width)
    names = ["a", "b", "c", "d"][:nvars]
    spec = _spec_expr(r, names, lo, hi)
    kind = PB_KINDS[r.randrange(len(PB_KINDS))]
    x, y = names[0], names[1]
    delta = r.choice((-3, -2, -1, 1, 2, 3))
    mutant = ["+", spec, delta]
    witness = None
    if kind == "point_literal":
        cx = r.randint(lo, hi)
        trigger, witness = ["==", x, cx], {x: cx}
    elif kind == "pair_literal":
        cx, cy = r.randint(lo, hi), r.randint(lo, hi)
        trigger, witness = ["and", ["==", x, cx], ["==", y, cy]], {x: cx, y: cy}
    elif kind == "linear_relation":
        k, c = r.randint(2, 9), r.randint(-20, 20)
        vy = r.randint(-((c - lo) // k), (hi - c) // k)        # so that x = c + k*y lies in [lo, hi]
        trigger, witness = ["==", ["-", x, ["*", k, y]], c], {x: c + k * vy, y: vy}
    elif kind == "residue":
        m, k = r.randint(50, 400), r.randint(2, 9)
        res = r.randrange(m)
        vy = r.randint(lo, hi)
        vx = next(v for v in range(lo, hi + 1) if (v + k * vy) % m == res)
        trigger, witness = ["==", ["mod", ["+", x, ["*", k, y]], m], res], {x: vx, y: vy}
    elif kind == "corner":
        s = r.randint(0, 6)
        trigger, witness = [">=", ["+", x, y], 2 * hi - s], {x: hi, y: hi}
    elif kind == "off_by_one":
        mutant = ["ite", ["<=", x, y], ["+", x, 1], y]
        spec = ["ite", ["<", x, y], ["+", x, 1], y]
        trigger, witness = None, {x: (lo + hi) // 2, y: (lo + hi) // 2}
    elif kind == "clamp_bound":
        top = hi - r.randint(0, 3)
        spec = ["min", ["max", x, lo], top]
        mutant = ["min", ["max", x, lo], top + 1] if top < hi else ["min", ["max", x, lo], top - 1]
        trigger, witness = None, {x: hi}
    elif kind == "wide":
        trigger, witness = ["<", x, lo + (hi - lo) // 8], {x: lo}
    elif kind == "clean_decoy":
        cx = r.randint(lo, hi)
        trigger, c = ["==", x, cx], r.randint(1, 99)
        mutant = ["+", spec, ["-", c, c]]
    else:                                                  # clean_rewrite
        trigger, mutant = None, ["max", spec, spec]
    body = (mutant if trigger is None else ["ite", trigger, mutant, spec])
    params = [{"name": n, "min": lo, "max": hi} for n in names]
    data = {"function_under_test": {"parameters": params, "body": body}, "property": ["==", RESULT, spec]}
    buggy = not kind.startswith("clean")
    if buggy:
        env = {n: 0 if lo <= 0 <= hi else lo for n in names}
        env.update(witness)
        if _mc_eval(data["property"], {**env, RESULT: _mc_eval(body, env)}):
            # the planted change happens to coincide with the specification at this witness: search the
            # witness's neighbourhood in the other parameters (generation-time construction, never scoring)
            for v in range(lo, hi + 1):
                env2 = dict(env)
                for n in names:
                    if n not in witness:
                        env2[n] = v
                if not _mc_eval(data["property"], {**env2, RESULT: _mc_eval(body, env2)}):
                    env = env2
                    break
            else:
                raise GenomeError("generator: planted bug has no witness")   # never on dev seeds 0-9
        witness = env
    return data, {"buggy": buggy, "kind": kind, "witness": witness if buggy else None}


def pb_subregion(data):
    """From the data alone: the comparison operators the body adds beyond the property's (the planted guard)."""
    from collections import Counter

    def ops(e, out):
        if isinstance(e, list):
            out[e[0]] += 1
            for a in e[1:]:
                ops(a, out)
        return out
    prop = data["property"]
    within = Counter()
    for a in (prop[1:] if isinstance(prop, list) else ()):
        ops(a, within)
    extra = ops(data["function_under_test"]["body"], Counter()) - within
    if extra["=="]:
        return "equality_guard"
    if any(extra[o] for o in ("<", "<=", ">", ">=")):
        return "inequality_guard"
    return "no_added_guard"


INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.formal.property_based_search", version="1.0.0", family="formal_property_search",
            layer=3, operation="find_property_counterexample", epistemic_class="deductive",
            subgeometry="property-based testing: a bounded integer function and a declared property; find an input "
                        "that violates it within a fixed evaluation budget",
            source_provenance="QuickCheck (Claessen and Hughes 2000); Hypothesis (MacIver et al.) boundary bias and "
                              "shrinking; fuzzing dictionaries of magic constants (AFL, libFuzzer); the expression "
                              "language of verify_modelcheck",
            native_representation="function_under_test {parameters [{name, min, max}], body} and property, typed "
                                  "JSON integer expressions (linear arithmetic, mod by a literal, min, max, ite, "
                                  "comparisons, connectives); the property names the return value 'result'",
            required_inputs=("function_under_test", "property"),
            output_contract={"verdict": "COUNTEREXAMPLE (the only verdict this genome gives)",
                             "counterexample": "{parameter: int}", "result": "the function's value there"},
            algorithm_or_runtime="seeded generation (30% mined constants and neighbours, 15% domain edges and 0/±1, "
                                 "10% reuse of another argument, 10% small values, 35% uniform), duplicates skipped, "
                                 "closure-compiled evaluation; greedy shrinking toward zero",
            parameters={"evaluations": PB_EVALUATIONS, "shrink_max": PB_SHRINK_MAX},
            memory_model="stateless; the set of inputs tried in one request",
            learning_rule="none",
            composition_inputs=("a function and a property it must satisfy",),
            composition_outputs=("a re-executable counterexample, or nothing",),
            evidence_type="counterexample",
            verification_method="independent re-execution with the recursive interpreter (not the solver's closure "
                                "compiler): inputs within the declared domain, the result recomputed, the property "
                                "false on that result",
            confidence_semantics="a counterexample is certain (it re-executes); UNKNOWN after the budget says nothing "
                                 "about whether a counterexample exists",
            resource_profile="at most 2,000 evaluations of the body and the property",
            latency_profile="milliseconds to ~0.1 s",
            known_strengths=("needs no model of the function's semantics: works on whatever it can execute",
                             "finds guards on literal constants, domain edges and equal arguments quickly",
                             "shrunk counterexamples are small and readable"),
            known_failure_modes=("bugs on narrow regions with no literal or boundary hint (a conjunction of exact "
                                 "values not written in the code, a residue modulo a large number) are found only "
                                 "by luck",
                                 "never proves absence: a bug-free function always ends UNKNOWN",
                                 "a symbolic solver dominates it wherever the function is in a decidable theory "
                                 "(as on this benchmark): it finds every planted bug and proves the decoys clean"),
            counterindications=("questions that need a proof of correctness (use a model checker or SMT)",
                                "functions with huge inputs whose failures need structure (use a grammar or "
                                "symbolic execution)"),
            abstention_conditions=("UNKNOWN when no counterexample is found within 2,000 evaluations",),
            benchmark_suite="generated integer functions of 2-4 parameters on domains of width 1,000-100,000 with one "
                            "planted bug of ten kinds (literal point, literal pair, linear relation, residue class, "
                            "corner, off-by-one comparison, clamp bound, wide region) or a bug-free decoy (a guard "
                            "that changes nothing, a rewrite); the property is equality with the specification; "
                            "truth by construction (a witness re-executed at generation, or no bug); seeds 0-9 dev, "
                            "held-out seeds fixed by the admission freeze",
            baseline="uniform random inputs over the declared domain with the same 2,000-evaluation budget",
            competitor="Z3 symbolic search (linear integer arithmetic, 4 s): a counterexample, a proof of absence or "
                       "abstention",
            dependency=None, buildability="BUILDABLE_NOW", lineage=LINEAGE),
        solve=property_search_solve, verify=property_search_verify, instance=pb_instance, score=property_search_score,
        baseline=property_search_uniform, competitor=property_search_z3, subregion=pb_subregion, tolerance=1e-9),
]
