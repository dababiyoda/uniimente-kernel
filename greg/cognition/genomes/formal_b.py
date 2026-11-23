"""Layer 3 formal and estimation intelligences, batch B: resolution theorem proving with checkable proofs, MDL
polynomial model selection, and convex quadratic programming with a duality certificate.

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.md``) lists theorem proving, MDL and
convex optimisation as ABSENT. Effect, not metaphor:

* ``prove_resolution`` (``prove_clausal_entailment``): decide whether propositional or ground first-order premises
  entail a goal, and when they do, hand back a proof object that anyone can check with a few dozen lines of code
  and no trust in the prover. A saturation prover (given-clause loop, forward and backward subsumption, tautology
  deletion) first refutes the negated goal under the set-of-support strategy, then, if that strategy ends without
  a refutation, saturates the whole set under ordered resolution. A refutation yields a resolution-proof DAG ending
  in the empty clause; a saturated set without the empty clause yields a countermodel (Bachmair-Ganzinger
  candidate-model construction), which is re-checked before it is reported. A budget exhausted first gives
  UNKNOWN. The verifier is an independent proof checker (its own literal parser and resolvent arithmetic) and an
  independent model evaluator. Z3 is the stronger decision engine and is the competitor; this genome's distinct
  value is the independently checkable proof object, and its score says so (see ``prove_score``).
* ``mdl_model_select`` (``select_polynomial_degree``): choose the degree (0-8) of a polynomial model of 1-D noisy
  data by minimum description length, using Rissanen's normalized maximum likelihood (NML) code length for Gaussian
  linear regression in its Stirling form (Rissanen 2000; Roos, Myllymaki and Rissanen 2009). The verifier
  recomputes every code length on a different basis (Chebyshev, QR projection) and checks the fit.
* ``convex_qp_dual`` (``solve_convex_qp``): minimise 1/2 x'Qx + c'x subject to Gx <= h with a dense positive
  definite Q by a primal-dual interior point method (Mehrotra predictor-corrector) written here. It returns x and
  the dual multipliers; the verifier checks primal feasibility, dual feasibility, complementary slackness,
  stationarity and the duality gap against the Lagrangian dual objective, computed independently by a SciPy
  Cholesky solve. A small gap with feasible x and non-negative multipliers certifies near-optimality by weak
  duality, whatever produced x.

Overlap: ``reconcile_qp`` (solvers_d) solves a diagonal-Hessian weighted least-squares QP with equality balances
and non-negativity. ``convex_qp_dual`` takes the distinct sub-geometry of dense, coupled (possibly ill-conditioned)
Hessians under general linear inequalities, where neither the diagonal closed form nor bound-only active sets apply.
``formal_property_search`` (formal.py) searches for counterexamples to integer properties and was SUPERSEDED by Z3;
``prove_resolution`` does not search for counterexamples to programs: it proves clausal entailment and emits proofs.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output of any
method here creates authority. Development seeds 0-9 only.
"""
from __future__ import annotations

import heapq
import math
import random
import time

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int, finite

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4 (restore the full five-layer scope)",
           "docs/collaboration/MIND-COVERAGE-2026-10-21.md (Layer 3 ABSENT families)")


def _mapping(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    return data


def _unknown(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="UNKNOWN", missing=[reason])


def _seconds(budget, cap=10.0):
    try:
        return max(0.5, min(cap, float((budget or {}).get("latency_s", cap))))
    except (TypeError, ValueError):
        return cap


def _abstain(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="ABSTAIN", missing=[reason])


# =================================================================== 1. resolution theorem proving
TP_MAX_CLAUSES, TP_MAX_ATOMS, TP_MAX_LEN, TP_MAX_GOALS = 3000, 600, 40, 8
TP_MAX_GENERATED = 40_000          # resolvents admitted to the passive queue, per goal clause (both phases)
TP_MAX_ACTIVE = 6_000              # active clauses, per phase
TP_TRUTH_TABLE_ATOMS = 18          # the baseline abstains above this
TP_Z3_SECONDS = 10.0
PROVED, NOT_PROVED = "PROVED", "NOT_PROVED"


def _tp_input(data):
    data = _mapping(data)
    premises, goals = data.get("premise_clauses"), data.get("goal_clauses")
    if not isinstance(premises, list) or len(premises) > TP_MAX_CLAUSES:
        raise GenomeError(f"premise_clauses: a list of at most {TP_MAX_CLAUSES} clauses")
    if not isinstance(goals, list) or not 1 <= len(goals) <= TP_MAX_GOALS:
        raise GenomeError(f"goal_clauses: 1-{TP_MAX_GOALS} clauses (the goal is their conjunction)")
    atoms = set()

    def clause(c, name):
        if not isinstance(c, list) or len(c) > TP_MAX_LEN:
            raise GenomeError(f"{name}: a list of at most {TP_MAX_LEN} literals")
        out = []
        for lit in c:
            if not isinstance(lit, str) or not 1 <= len(lit) <= 80:
                raise GenomeError(f"{name}: literals are strings, '~' marks negation")
            atom = lit[1:] if lit.startswith("~") else lit
            if not atom or atom.startswith("~") or any(ch.isspace() for ch in atom):
                raise GenomeError(f"{name}: literal {lit!r} is not an atom or its single negation")
            atoms.add(atom)
            out.append(lit)
        return out
    p = [clause(c, "premise clause") for c in premises]
    g = [clause(c, "goal clause") for c in goals]
    if len(atoms) > TP_MAX_ATOMS:
        raise GenomeError(f"at most {TP_MAX_ATOMS} distinct atoms")
    return p, g, sorted(atoms)


class _Prover:
    """Integer-literal saturation: atom of rank r is r+1, its negation -(r+1)."""

    def __init__(self, atoms, deadline=math.inf):
        self.atoms = atoms
        self.deadline = deadline
        self.rank = {a: i + 1 for i, a in enumerate(atoms)}

    def lit(self, s):
        return -self.rank[s[1:]] if s.startswith("~") else self.rank[s]

    def text(self, v):
        return ("~" if v < 0 else "") + self.atoms[abs(v) - 1]

    @staticmethod
    def key(v):                                     # literal order: atoms by rank, the negation above the atom
        return 2 * abs(v) + (1 if v < 0 else 0)

    def saturate(self, inputs, support, ordered, generated_left):
        """Given-clause loop. inputs/support: [(clause frozenset, origin)]. Returns (status, records, info) with
        status REFUTED (records[info] is the empty clause), SATURATED (info: active ids) or LIMIT."""
        records = []                                # (clause, parents or None, pivot atom rank, origin)
        passive, seen, used = [], set(), [0]

        def push(c, parents, pivot, origin):
            if any(-v in c for v in c) or c in seen:    # tautology or duplicate
                return None
            seen.add(c)
            records.append((c, parents, pivot, origin))
            heapq.heappush(passive, (len(c), len(records) - 1))
            return len(records) - 1
        active, index = [], {}

        def activate(i):
            active.append(i)
            for v in records[i][0]:
                index.setdefault(v, set()).add(i)

        def deactivate(i):
            active.remove(i)
            for v in records[i][0]:
                index[v].discard(i)
        if not ordered:                             # set of support: inputs are usable, never resolved together
            for c, origin in inputs:
                if any(-v in c for v in c) or c in seen:
                    continue
                seen.add(c)
                records.append((c, None, None, origin))
                if not c:
                    return "REFUTED", records, len(records) - 1
                activate(len(records) - 1)
            start = support
        else:
            start = list(inputs) + list(support)
        for c, origin in start:
            j = push(c, None, None, origin)
            if j is not None and not c:
                return "REFUTED", records, j
        pops = 0
        while passive:
            pops += 1
            if pops % 64 == 0 and time.monotonic() > self.deadline:
                return "LIMIT", records, "request latency budget"
            _, i = heapq.heappop(passive)
            c = records[i][0]
            if any(records[j][0] <= c for j in active):          # forward subsumption
                continue
            for j in [j for j in active if c < records[j][0]]:   # backward subsumption
                deactivate(j)
            if len(active) >= TP_MAX_ACTIVE:
                return "LIMIT", records, "active clause limit"
            activate(i)
            lits = [max(c, key=self.key)] if ordered else list(c)
            for v in lits:
                for j in list(index.get(-v, ())):
                    d = records[j][0]
                    if j == i or (ordered and max(d, key=self.key) != -v):
                        continue
                    r = (c - {v}) | (d - {-v})
                    if used[0] >= generated_left:
                        return "LIMIT", records, "generated clause limit"
                    k = push(r, (i, j), abs(v), "resolvent")
                    if k is not None:
                        used[0] += 1
                        if not r:
                            return "REFUTED", records, k
        return "SATURATED", records, list(active), used[0]

    def model(self, records, active):
        """Bachmair-Ganzinger candidate model of a set saturated under ordered resolution (clauses in ascending
        multiset order; a false clause whose maximal literal is positive produces that atom)."""
        true = set()
        for i in sorted(active, key=lambda i: sorted((self.key(v) for v in records[i][0]), reverse=True)):
            c = records[i][0]
            if any((v > 0) == (abs(v) in true) for v in c):
                continue
            top = max(c, key=self.key)
            if top > 0:
                true.add(top)
        return true

    def proof(self, records, last):
        order, stack, mark = [], [last], set()
        while stack:                                # iterative post-order over the parent DAG
            i = stack[-1]
            parents = records[i][1] or ()
            pending = [p for p in parents if p not in mark]
            if pending:
                stack.extend(pending)
                continue
            stack.pop()
            if i not in mark:
                mark.add(i)
                order.append(i)
        number = {i: n for n, i in enumerate(order)}
        steps = []
        for i in order:
            c, parents, pivot, origin = records[i]
            step = {"clause": sorted(self.text(v) for v in c)}
            if parents is None:
                step.update(origin)
            else:
                step.update({"rule": "resolve", "parents": [number[parents[0]], number[parents[1]]],
                             "pivot": self.atoms[pivot - 1]})
            steps.append(step)
        return steps


def prove_solve(data, budget):
    premises, goals, atoms = _tp_input(data)
    pr = _Prover(atoms, time.monotonic() + _seconds(budget))
    inputs = [(frozenset(pr.lit(s) for s in c), {"rule": "premise", "source": k}) for k, c in enumerate(premises)]
    proofs, stats = [], []
    for g, goal in enumerate(goals):
        support = [(frozenset([-pr.lit(s)]), {"rule": "negated_goal", "source": g}) for s in goal]
        left = TP_MAX_GENERATED
        phases = []
        result = None
        if support:
            status, records, info, *rest = pr.saturate(inputs, support, False, left // 2)
            phases.append(("set_of_support", status, len(records)))
            if status == "REFUTED":
                result = ("proof", records, info)
            left -= len(records)
        if result is None:
            status, records, info, *rest = pr.saturate(inputs, support, True, max(left, 1000))
            phases.append(("ordered", status, len(records)))
            if status == "REFUTED":
                result = ("proof", records, info)
            elif status == "SATURATED":
                result = ("model", records, info)
            else:
                return _unknown(f"goal clause {g}: resolution budget exhausted ({info}) before a refutation or "
                                f"saturation", goal_index=g, phases=[list(p) for p in phases])
        stats.append({"goal": g, "phases": [list(p) for p in phases]})
        if result[0] == "model":
            true = pr.model(result[1], result[2])
            cm = {a: (pr.rank[a] in true) for a in atoms}
            # re-check before reporting: every premise true, the goal clause false
            ok = all(any(cm[s.lstrip("~")] != s.startswith("~") for s in c) for c in premises) and not any(
                cm[s.lstrip("~")] != s.startswith("~") for s in goal)
            if not ok:
                return _unknown(f"goal clause {g}: saturated without refutation but the candidate model failed its "
                                f"re-check", goal_index=g)
            return answer({"verdict": NOT_PROVED, "proofs": None, "countermodel": cm, "failed_goal": g},
                          {"method": "set-of-support resolution, then ordered resolution saturation with subsumption; "
                                     "Bachmair-Ganzinger candidate model of the saturated set", "goals": stats})
        proofs.append(pr.proof(result[1], result[2]))
    return answer({"verdict": PROVED, "proofs": proofs, "countermodel": None, "failed_goal": None},
                  {"method": "refutation of each negated goal clause: set-of-support resolution, then ordered "
                             "resolution saturation; forward and backward subsumption, tautology deletion",
                   "goals": stats, "proof_steps": [len(p) for p in proofs]})


# ------------------------------------------------------------------ independent proof checker
def _parse(lit):
    """Checker's own literal reading: (atom, polarity)."""
    if not isinstance(lit, str):
        return None
    neg = lit[:1] == "~"
    atom = lit[1:] if neg else lit
    return (atom, not neg) if atom and atom[:1] != "~" else None


def _clause_set(lits):
    if not isinstance(lits, list):
        return None
    out = set()
    for s in lits:
        p = _parse(s)
        if p is None:
            return None
        out.add(p)
    return frozenset(out)


def check_proof(premises, goal, steps) -> dict:
    """Check one resolution refutation of premises plus the negation of one goal clause, step by step."""
    prem = {_clause_set(c) for c in premises}
    goal_lits = {_parse(s) for s in goal}
    out = {"steps_well_formed": True, "premise_steps_cite_premises": True, "negated_goal_steps_match_goal": True,
           "parents_precede_each_step": True, "every_resolvent_valid": True, "ends_in_empty_clause": False}
    if not isinstance(steps, list) or not steps:
        out["steps_well_formed"] = False
        return out
    clauses = []
    for n, step in enumerate(steps):
        if not isinstance(step, dict):
            out["steps_well_formed"] = False
            return out
        c = _clause_set(step.get("clause"))
        rule = step.get("rule")
        if c is None or len(c) != len(step["clause"]) or rule not in ("premise", "negated_goal", "resolve"):
            out["steps_well_formed"] = False
            return out
        if rule == "premise":
            src = step.get("source")
            if not (type(src) is int and 0 <= src < len(premises) and _clause_set(premises[src]) == c and c in prem):
                out["premise_steps_cite_premises"] = False
        elif rule == "negated_goal":
            if not (len(c) == 1 and next(iter(c)) and (next(iter(c))[0], not next(iter(c))[1]) in goal_lits):
                out["negated_goal_steps_match_goal"] = False
        else:
            parents, pivot = step.get("parents"), step.get("pivot")
            if (not isinstance(parents, list) or len(parents) != 2 or not all(type(p) is int for p in parents)
                    or not isinstance(pivot, str)):
                out["steps_well_formed"] = False
                return out
            if not all(0 <= p < n for p in parents):
                out["parents_precede_each_step"] = False
                return out
            a, b = clauses[parents[0]], clauses[parents[1]]
            pos, neg = (pivot, True), (pivot, False)
            if pos in a and neg in b:
                expect = (a - {pos}) | (b - {neg})
            elif neg in a and pos in b:
                expect = (a - {neg}) | (b - {pos})
            else:
                expect = None
            if expect != c:
                out["every_resolvent_valid"] = False
        clauses.append(c)
    out["ends_in_empty_clause"] = clauses[-1] == frozenset()
    return out


def _model_value(model, lit):
    atom, positive = _parse(lit)
    return model.get(atom) is positive


def prove_verify(data, output, certificate):
    premises, goals, atoms = _tp_input(data)
    if (not isinstance(output, dict) or set(output) != {"verdict", "proofs", "countermodel", "failed_goal"}
            or output["verdict"] not in (PROVED, NOT_PROVED)):
        return {"output_shape": False}
    if output["verdict"] == PROVED:
        proofs = output["proofs"]
        if (not isinstance(proofs, list) or len(proofs) != len(goals) or output["countermodel"] is not None
                or output["failed_goal"] is not None):
            return {"output_shape": False, "one_proof_per_goal_clause": False}
        checks = {"output_shape": True, "one_proof_per_goal_clause": True}
        for g, steps in enumerate(proofs):
            for name, ok in check_proof(premises, goals[g], steps).items():
                checks[name] = checks.get(name, True) and ok
        return checks
    cm, g = output["countermodel"], output["failed_goal"]
    if (not isinstance(cm, dict) or type(g) is not int or not 0 <= g < len(goals) or output["proofs"] is not None
            or not all(type(v) is bool for v in cm.values())):
        return {"output_shape": False}
    return {"output_shape": True, "countermodel_assigns_every_atom": set(cm) == set(atoms),
            "countermodel_satisfies_every_premise": all(any(_model_value(cm, s) for s in c) for c in premises),
            "countermodel_falsifies_the_goal_clause": not any(_model_value(cm, s) for s in goals[g])}


def prove_score(data, truth, output):
    """Declared scoring (this genome's distinct value is a checkable proof object):
    a correct verdict carried by an independently checked certificate (a resolution refutation per goal clause, or
    a countermodel that satisfies every premise and falsifies a goal clause) scores 1; a correct verdict with no
    checkable certificate (an entailment decided by an engine that emits no proof object here) scores 0.5; silence
    scores 0 (abstain); a wrong verdict, or a certificate that fails its check, scores -1 (wrong)."""
    premises, goals, atoms = _tp_input(data)
    if output is None:
        return {"quality": 0.0, "category": "abstain"}
    if not isinstance(output, dict) or output.get("verdict") not in (PROVED, NOT_PROVED):
        return {"quality": -1.0, "category": "wrong"}
    if (output["verdict"] == PROVED) != truth["entailed"]:
        return {"quality": -1.0, "category": "wrong"}
    if output["verdict"] == PROVED:
        if output.get("proofs") is None:
            return {"quality": 0.5, "category": "correct"}
    elif output.get("countermodel") is None:
        return {"quality": 0.5, "category": "correct"}
    try:
        ok = all(prove_verify(data, output, {}).values())
    except (GenomeError, TypeError, KeyError, AttributeError):
        ok = False
    return {"quality": 1.0, "category": "correct"} if ok else {"quality": -1.0, "category": "wrong"}


def prove_truth_table(data):
    """Baseline: truth-table enumeration (vectorised over all 2^n assignments) for at most 18 atoms; a verdict and,
    when the goal is not entailed, a countermodel. It emits no proof object; above 18 atoms it abstains."""
    import numpy as np
    premises, goals, atoms = _tp_input(data)
    n = len(atoms)
    if n > TP_TRUTH_TABLE_ATOMS:
        return None
    col = {a: i for i, a in enumerate(atoms)}
    rows = np.arange(2 ** n, dtype=np.int64)
    bits = ((rows[:, None] >> np.arange(n)) & 1).astype(bool) if n else np.zeros((1, 0), bool)

    def sat(c):
        v = np.zeros(len(bits), bool)
        for s in c:
            atom = s.lstrip("~")
            v |= bits[:, col[atom]] if not s.startswith("~") else ~bits[:, col[atom]]
        return v
    ok = np.ones(len(bits), bool)
    for c in premises:
        ok &= sat(c)
    for g, goal in enumerate(goals):
        bad = ok & ~sat(goal)
        if bad.any():
            row = bits[int(np.argmax(bad))]
            return {"verdict": NOT_PROVED, "proofs": None, "failed_goal": g,
                    "countermodel": {a: bool(row[col[a]]) for a in atoms}}
    return {"verdict": PROVED, "proofs": None, "countermodel": None, "failed_goal": None}


def _z3_entailment(premises, goals, atoms, seconds):
    """(entailed per goal clause, model dict of the first non-entailed goal or None); None entries are unknown."""
    import z3
    ctx = z3.Context()
    var = {a: z3.Bool(a, ctx) for a in atoms}

    def lit(s):
        return z3.Not(var[s[1:]]) if s.startswith("~") else var[s]
    verdicts, model = [], None
    for goal in goals:
        s = z3.Solver(ctx=ctx)
        s.set("timeout", int(seconds * 1000))
        for c in premises:
            s.add(z3.Or([lit(x) for x in c]) if c else z3.BoolVal(False, ctx))
        for x in goal:
            s.add(z3.Not(lit(x)))
        r = s.check()
        if r == z3.unsat:
            verdicts.append(True)
        elif r == z3.sat:
            verdicts.append(False)
            if model is None:
                m = s.model()
                model = {a: bool(z3.is_true(m.eval(var[a], model_completion=True))) for a in atoms}
        else:
            verdicts.append(None)
    return verdicts, model


def prove_z3(data):
    """Competitor: Z3 (CDCL SAT core). The stronger decision engine: it decides entailment and gives a model when
    the goal fails, but emits no proof object that this contract's checker can read, so an entailment from Z3 scores
    0.5 under the declared scoring; abstains on timeout."""
    premises, goals, atoms = _tp_input(data)
    verdicts, model = _z3_entailment(premises, goals, atoms, TP_Z3_SECONDS)
    for g, v in enumerate(verdicts):
        if v is None:
            return None
        if v is False:
            return {"verdict": NOT_PROVED, "proofs": None, "countermodel": model, "failed_goal": g}
    return {"verdict": PROVED, "proofs": None, "countermodel": None, "failed_goal": None}


# ------------------------------------------------------------------ native benchmark
TP_KINDS = ("random_3cnf_small", "horn_reachability", "pigeonhole", "implication_chain", "random_3cnf_medium",
            "ground_syllogism")


def _rand_clause(r, names, width):
    return [("~" if r.random() < 0.5 else "") + v for v in r.sample(names, width)]


def tp_instance(seed):
    r = random.Random(f"genome:prove_resolution:{seed}")
    kind = TP_KINDS[seed % len(TP_KINDS)] if seed < 10 else r.choice(TP_KINDS)
    if kind in ("random_3cnf_small", "random_3cnf_medium"):
        n = r.randint(8, 16) if kind == "random_3cnf_small" else r.randint(20, 32)
        names = [f"p{i}" for i in range(n)]
        m = int(round(n * r.uniform(2.5, 4.6)))
        premises = [_rand_clause(r, names, 3) for _ in range(m)]
        goals = [_rand_clause(r, names, r.randint(1, 2)) for _ in range(r.randint(1, 2))]
    elif kind == "horn_reachability":
        k = r.randint(4, 6)
        nodes = "abcdefgh"[:k]
        edges = {(u, v) for u in nodes for v in nodes if u != v and r.random() < 0.28}
        premises = [[f"Edge({u},{v})"] for u, v in sorted(edges)]
        premises += [[f"~Edge({u},{v})", f"Path({u},{v})"] for u in nodes for v in nodes if u != v]
        premises += [[f"~Path({u},{v})", f"~Edge({v},{w})", f"Path({u},{w})"]
                     for u in nodes for v in nodes for w in nodes if len({u, v, w}) == 3]
        u, v = r.sample(nodes, 2)
        goals = [[f"Path({u},{v})"]]
    elif kind == "pigeonhole":
        holes = r.randint(2, 4)
        pig = holes + (1 if r.random() < 0.7 else 0)
        premises = [[f"In({p},{h})" for h in range(holes)] for p in range(pig)]
        premises += [[f"~In({p},{h})", f"~In({q},{h})"] for h in range(holes) for p in range(pig)
                     for q in range(p + 1, pig)]
        goals = [[]]                                    # the empty goal clause: the premises are contradictory
    elif kind == "implication_chain":
        length = r.randint(10, 40)
        names = [f"q{i}" for i in range(length + 1)]
        premises = [[names[0]]] + [[f"~{names[i]}", names[i + 1]] for i in range(length)]
        if r.random() < 0.4:
            premises.pop(r.randint(1, length))          # one broken link
        extra = [f"d{i}" for i in range(r.randint(5, 20))]
        premises += [_rand_clause(r, extra + names, 3) for _ in range(len(extra))]
        goals = [[names[-1]]]
    else:                                               # ground_syllogism: unary predicates over constants
        consts = [f"c{i}" for i in range(r.randint(3, 6))]
        preds = ["Human", "Mortal", "Greek", "Wise", "Philosopher", "Teacher"]
        premises = []
        for _ in range(r.randint(4, 8)):                # ground rules A(x) -> B(x), sometimes A(x) & B(x) -> C(x)
            a, b, c = r.sample(preds, 3)
            for x in consts:
                premises.append([f"~{a}({x})", f"{b}({x})"] if r.random() < 0.6
                                else [f"~{a}({x})", f"~{b}({x})", f"{c}({x})"])
        for x in consts:
            for p in r.sample(preds, r.randint(1, 2)):
                premises.append([f"{p}({x})"])
        x, p = r.choice(consts), r.choice(preds)
        goals = [[f"{p}({x})"], [("~" if r.random() < 0.3 else "") + f"{r.choice(preds)}({r.choice(consts)})"]]
        goals = goals[:r.randint(1, 2)]
    data = {"premise_clauses": premises, "goal_clauses": goals}
    p, g, atoms = _tp_input(data)
    verdicts, _ = _z3_entailment(p, g, atoms, 60.0)
    if None in verdicts:
        raise GenomeError("generator: Z3 truth timed out")
    return data, {"entailed": all(verdicts), "per_goal": verdicts, "kind": kind, "atoms": len(atoms)}


def tp_subregion(data):
    premises, goals, atoms = _tp_input(data)
    if len(atoms) <= TP_TRUTH_TABLE_ATOMS:
        return "small_le_18_atoms"
    horn = all(sum(1 for s in c if not s.startswith("~")) <= 1 for c in premises)
    return "horn_large" if horn else "non_horn_large"


# =================================================================== 2. MDL polynomial model selection
MDL_MAX_POINTS, MDL_MAX_DEGREE = 5000, 8
MDL_FOLDS = 5


def _mdl_input(data):
    import numpy as np
    data = _mapping(data)
    xs, ys = data.get("observations_x"), data.get("observations_y")
    if (not isinstance(xs, list) or not isinstance(ys, list) or len(xs) != len(ys)
            or not 4 <= len(xs) <= MDL_MAX_POINTS):
        raise GenomeError(f"observations_x and observations_y: equal-length lists of 4-{MDL_MAX_POINTS} numbers")
    top = bounded_int(data.get("max_degree", MDL_MAX_DEGREE), low=0, high=MDL_MAX_DEGREE, name="max_degree")
    x = np.array([finite(v, low=-1e6, high=1e6, name="x") for v in xs])
    y = np.array([finite(v, low=-1e9, high=1e9, name="y") for v in ys])
    if x.max() - x.min() <= 1e-9 * (1 + abs(x).max()):
        raise GenomeError("observations_x must not all coincide")
    top = min(top, len(x) - 3)                      # k = degree + 1 parameters need n - k >= 2
    return x, y, top


def _mdl_frame(x):
    return (float(x.max()) + float(x.min())) / 2, (float(x.max()) - float(x.min())) / 2


def _nml_bits(n, k, rss, fit_sq):
    """Rissanen's NML code length (Stirling form) for Gaussian linear regression with k parameters, in bits:
    1/2 [ (n-k) ln(RSS/(n-k)) + k ln(|yhat|^2 / k) + ln(k (n-k)) ] / ln 2."""
    tiny = 1e-300
    return 0.5 * ((n - k) * math.log(max(rss, tiny) / (n - k)) + k * math.log(max(fit_sq, tiny) / k)
                  + math.log(k * (n - k))) / math.log(2)


def _mdl_fit(x, y, d):
    """Least squares on a Legendre basis of the abscissa rescaled to [-1, 1]: (Legendre coefficients, frame)."""
    import numpy as np
    from numpy.polynomial import legendre
    center, scale = _mdl_frame(x)
    coef, *_ = np.linalg.lstsq(legendre.legvander((x - center) / scale, d), y, rcond=None)
    return coef, center, scale


def _mdl_answer(x, y, d, lengths=None):
    import numpy as np
    from numpy.polynomial import legendre
    coef, center, scale = _mdl_fit(x, y, d)
    power = legendre.leg2poly(coef)
    return {"degree": d, "center": center, "scale": scale,
            "coefficients": [float(v) for v in np.pad(power, (0, d + 1 - len(power)))],
            "code_lengths_bits": lengths}


def mdl_solve(data, budget):
    import numpy as np
    from numpy.polynomial import legendre
    x, y, top = _mdl_input(data)
    n = len(x)
    lengths = []
    for d in range(top + 1):
        coef, center, scale = _mdl_fit(x, y, d)
        yhat = legendre.legval((x - center) / scale, coef)
        lengths.append(_nml_bits(n, d + 1, float(np.sum((y - yhat) ** 2)), float(np.dot(yhat, yhat))))
    best = int(np.argmin(lengths))
    return answer(_mdl_answer(x, y, best, [float(v) for v in lengths]),
                  {"method": "least squares on a Legendre basis of the rescaled abscissa; NML code length per degree "
                             "(Rissanen 2000, Stirling form); argmin", "degrees_considered": top + 1,
                   "selected_code_length_bits": float(lengths[best])})


def _mdl_recompute(x, y, top):
    """Verifier's own path: Chebyshev basis, QR projection, the code length written out again."""
    import numpy as np
    from numpy.polynomial import chebyshev
    n = len(x)
    lo, hi = float(np.min(x)), float(np.max(x))
    t = (2 * x - (hi + lo)) / (hi - lo)
    out, projections = [], []
    for d in range(top + 1):
        q, _ = np.linalg.qr(chebyshev.chebvander(t, d))
        yhat = q @ (q.T @ y)
        k = d + 1
        rss, fit_sq = float(((y - yhat) ** 2).sum()), float((yhat ** 2).sum())
        nats = ((n - k) * np.log(max(rss, 1e-300) / (n - k)) + k * np.log(max(fit_sq, 1e-300) / k)
                + np.log(k * (n - k))) / 2
        out.append(float(nats / np.log(2)))
        projections.append(yhat)
    return out, projections, ((hi + lo) / 2, (hi - lo) / 2)


def _poly_eval(coefficients, t):
    import numpy as np
    return np.polyval(np.array(coefficients[::-1], dtype=float), t)


def mdl_verify(data, output, certificate):
    import numpy as np
    x, y, top = _mdl_input(data)
    num = (int, float)
    if (not isinstance(output, dict)
            or set(output) != {"degree", "center", "scale", "coefficients", "code_lengths_bits"}
            or type(output["degree"]) is not int or not 0 <= output["degree"] <= top
            or not all(type(output[k]) in num and math.isfinite(output[k]) for k in ("center", "scale"))
            or not isinstance(output["coefficients"], list) or len(output["coefficients"]) != output["degree"] + 1
            or not isinstance(output["code_lengths_bits"], list) or len(output["code_lengths_bits"]) != top + 1
            or not all(type(v) in num and math.isfinite(v)
                       for v in output["coefficients"] + output["code_lengths_bits"])):
        return {"output_shape": False}
    lengths, projections, (center, scale) = _mdl_recompute(x, y, top)
    d = output["degree"]
    claimed = np.array(output["code_lengths_bits"], dtype=float)
    agree = bool(np.all(np.abs(claimed - lengths) <= 1e-6 * (1 + np.abs(lengths))))
    minimal = lengths[d] <= min(lengths) + 1e-7 * (1 + abs(min(lengths)))
    frame = (abs(output["center"] - center) <= 1e-9 * (1 + abs(center))
             and abs(output["scale"] - scale) <= 1e-9 * (1 + abs(scale)))
    fitted = _poly_eval(output["coefficients"], (x - output["center"]) / output["scale"]) if output["scale"] else None
    reproduces = bool(fitted is not None and np.all(np.isfinite(fitted))
                      and np.abs(fitted - projections[d]).max() <= 1e-6 * (1 + np.abs(y).max()))
    return {"output_shape": True, "code_lengths_recomputed": agree, "degree_minimises_code_length": bool(minimal),
            "frame_recomputed": bool(frame), "coefficients_are_the_least_squares_fit": reproduces}


def mdl_score(data, truth, output):
    """Degree recovery and out-of-sample error on the held-back split the instance supplies (never shown to any
    arm): quality = 0.5 [degree = generating degree] + 0.5 min(1, MSE of the generating-degree least-squares fit /
    MSE of the answer) on the held-back points. Category: correct when the degree is the generating degree."""
    import numpy as np
    from numpy.polynomial import legendre
    if output is None:
        return {"quality": 0.0, "category": "abstain"}
    x, y, top = _mdl_input(data)
    try:
        d = output["degree"]
        coefficients = [float(v) for v in output["coefficients"]]
        center, scale = float(output["center"]), float(output["scale"])
        if type(d) is not int or len(coefficients) != d + 1 or not scale:
            raise ValueError
    except (TypeError, KeyError, ValueError):
        return {"quality": -1.0, "category": "wrong"}
    hx, hy = np.array(truth["holdout_x"]), np.array(truth["holdout_y"])
    pred = _poly_eval(coefficients, (hx - center) / scale)
    if not np.all(np.isfinite(pred)):
        return {"quality": -1.0, "category": "wrong"}
    mse = float(np.mean((pred - hy) ** 2))
    coef, c0, s0 = _mdl_fit(x, y, truth["degree"])
    ref = float(np.mean((legendre.legval((hx - c0) / s0, coef) - hy) ** 2))
    hit = d == truth["degree"]
    return {"quality": 0.5 * hit + 0.5 * min(1.0, ref / max(mse, 1e-300)), "category": "correct" if hit else "wrong"}


def mdl_max_degree(data):
    """Baseline: always the largest admissible degree (the overfit)."""
    x, y, top = _mdl_input(data)
    return _mdl_answer(x, y, top)


def _rss(x, y, d, xq=None, yq=None):
    import numpy as np
    from numpy.polynomial import legendre
    coef, center, scale = _mdl_fit(x, y, d)
    if xq is None:
        xq, yq = x, y
    return float(np.sum((legendre.legval((xq - center) / scale, coef) - yq) ** 2))


def mdl_bic(data):
    """Competitor: the Bayesian information criterion, n ln(RSS/n) + (k + 1) ln n (k coefficients and the noise
    variance), minimised over the same degrees."""
    x, y, top = _mdl_input(data)
    n = len(x)
    scores = [n * math.log(max(_rss(x, y, d), 1e-300) / n) + (d + 2) * math.log(n) for d in range(top + 1)]
    return _mdl_answer(x, y, min(range(top + 1), key=lambda d: scores[d]))


def mdl_cv(data):
    """Second competitor: 5-fold cross-validated squared prediction error (folds by a fixed shuffle)."""
    import numpy as np
    x, y, top = _mdl_input(data)
    n = len(x)
    order = list(range(n))
    random.Random(n).shuffle(order)
    folds = [order[i::MDL_FOLDS] for i in range(MDL_FOLDS)]
    errors = []
    for d in range(top + 1):
        sse = 0.0
        for fold in folds:
            train = np.ones(n, bool)
            train[fold] = False
            if train.sum() < d + 2 or np.ptp(x[train]) <= 0:
                sse = math.inf
                break
            sse += _rss(x[train], y[train], d, x[fold], y[fold])
        errors.append(sse)
    return _mdl_answer(x, y, min(range(top + 1), key=lambda d: errors[d]))


def mdl_instance(seed):
    import numpy as np
    from numpy.polynomial import legendre
    r = random.Random(f"genome:mdl_model_select:{seed}")
    rng = np.random.default_rng(r.getrandbits(63))
    d = r.randint(0, 6)
    n = r.randint(15, 40) if r.random() < 0.5 else r.randint(40, 150)
    a, w = r.uniform(-50, 50), r.uniform(0.5, 20)
    layout = r.choice(("uniform", "uniform", "clustered"))
    sigma = r.uniform(0.1, 5.0)
    noise = "gaussian" if r.random() < 0.7 else "student_t3"
    # Legendre coefficients on the generating interval; the top one is 3-15 standard errors of its estimate
    coef = [r.gauss(0, 3 * sigma) for _ in range(d)] + [
        (1 if r.random() < 0.5 else -1) * r.uniform(3, 15) * sigma * math.sqrt((2 * d + 1) / n)]
    coef[0] += r.choice((0.0, r.uniform(-100, 100)))

    def draw(m):
        u = rng.uniform(0, 1, m) if layout == "uniform" else rng.beta(0.6, 0.6, m)
        xs = a + w * u
        e = rng.normal(0, sigma, m) if noise == "gaussian" else sigma * rng.standard_t(3, m) / math.sqrt(3)
        return xs, legendre.legval(2 * (xs - a) / w - 1, coef) + e
    x, y = draw(n)
    hx, hy = draw(400)
    keep = (hx >= x.min()) & (hx <= x.max())        # held-back points inside the observed range
    data = {"observations_x": [round(float(v), 9) for v in x], "observations_y": [round(float(v), 9) for v in y],
            "max_degree": MDL_MAX_DEGREE}
    return data, {"degree": d, "holdout_x": [float(v) for v in hx[keep]], "holdout_y": [float(v) for v in hy[keep]],
                  "noise": noise, "sigma": sigma, "layout": layout}


def mdl_subregion(data):
    x, y, top = _mdl_input(data)
    return "n_le_40" if len(x) <= 40 else "n_gt_40"


# =================================================================== 3. convex QP with a duality certificate
QP_MAX_VARS, QP_MAX_ROWS = 300, 600
QP_IPM_ITERATIONS = 100
QP_FEAS_TOL, QP_KKT_TOL, QP_GAP_TOL = 1e-7, 1e-6, 1e-7
QP_CORRECT_GAP = 1e-6              # relative suboptimality at or below which an answer is correct


def _cqp_input(data):
    import numpy as np
    data = _mapping(data)
    q, c, g, h = (data.get(k) for k in ("hessian", "linear_cost", "inequality_matrix", "inequality_rhs"))
    if not isinstance(c, list) or not 1 <= len(c) <= QP_MAX_VARS:
        raise GenomeError(f"linear_cost: a list of 1-{QP_MAX_VARS} numbers")
    n = len(c)
    if not isinstance(q, list) or len(q) != n or not all(isinstance(row, list) and len(row) == n for row in q):
        raise GenomeError("hessian: an n x n matrix (n = len(linear_cost))")
    if (not isinstance(g, list) or not 1 <= len(g) <= QP_MAX_ROWS or not isinstance(h, list) or len(h) != len(g)
            or not all(isinstance(row, list) and len(row) == n for row in g)):
        raise GenomeError(f"inequality_matrix: 1-{QP_MAX_ROWS} rows of n numbers; inequality_rhs: one per row")
    qv = np.array([[finite(v, low=-1e8, high=1e8, name="hessian") for v in row] for row in q])
    cv = np.array([finite(v, low=-1e8, high=1e8, name="cost") for v in c])
    gv = np.array([[finite(v, low=-1e6, high=1e6, name="coefficient") for v in row] for row in g])
    hv = np.array([finite(v, low=-1e9, high=1e9, name="rhs") for v in h])
    if np.abs(qv - qv.T).max() > 1e-9 * (1 + np.abs(qv).max()):
        raise GenomeError("hessian must be symmetric")
    qv = (qv + qv.T) / 2
    return qv, cv, gv, hv


def _cqp_objective(x, q, c):
    return float(0.5 * x @ q @ x + c @ x)


def cqp_solve(data, budget):
    """Primal-dual interior point (Mehrotra predictor-corrector) on min 1/2 x'Qx + c'x s.t. Gx + s = h, s >= 0."""
    import numpy as np
    q, c, g, h = _cqp_input(data)
    n, m = len(c), len(h)
    try:
        np.linalg.cholesky(q)
    except np.linalg.LinAlgError:
        return _abstain("hessian is not positive definite (this genome solves strictly convex QPs only)")
    x = np.zeros(n)
    s = np.maximum(h - g @ x, 1.0)
    lam = np.ones(m)
    scale = 1 + max(np.abs(c).max(), np.abs(h).max(), np.abs(q).max(), np.abs(g).max())
    for it in range(QP_IPM_ITERATIONS):
        rd = q @ x + c + g.T @ lam
        rp = g @ x + s - h
        mu = float(s @ lam) / m
        if (np.abs(rd).max() <= 1e-10 * scale and np.abs(rp).max() <= 1e-10 * scale and mu <= 1e-11 * scale):
            break
        w = lam / s
        normal = q + (g.T * w) @ g
        factor = None
        for shift in (0.0, 1e-14, 1e-12, 1e-10):          # near convergence w spans many decades: regularise
            try:
                factor = np.linalg.cholesky(normal + shift * np.abs(normal).max() * np.eye(n))
                break
            except np.linalg.LinAlgError:
                continue
        if factor is None:
            return _unknown("normal equations lost positive definiteness", iterations=it)

        def direction(rc):
            rhs = -rd - g.T @ (w * rp - rc / s)
            dx = np.linalg.solve(factor.T, np.linalg.solve(factor, rhs))
            dl = w * (g @ dx + rp) - rc / s
            ds = -rp - g @ dx
            return dx, ds, dl

        def step(v, dv):
            neg = dv < 0
            return min(1.0, float((-v[neg] / dv[neg]).min())) if neg.any() else 1.0
        dx, ds, dl = direction(s * lam)                       # affine-scaling predictor
        a = min(step(s, ds), step(lam, dl))
        sigma = (float((s + a * ds) @ (lam + a * dl)) / m / mu) ** 3 if mu > 0 else 0.0
        dx, ds, dl = direction(s * lam + ds * dl - sigma * mu)  # Mehrotra corrector
        a = 0.99 * min(step(s, ds), step(lam, dl))
        x, s, lam = x + a * dx, s + a * ds, lam + a * dl
    else:
        return _unknown(f"interior point did not converge in {QP_IPM_ITERATIONS} iterations")
    gap = float(s @ lam)
    return answer({"x": [float(v) for v in x], "objective": _cqp_objective(x, q, c)},
                  {"method": "primal-dual interior point, Mehrotra predictor-corrector, Cholesky normal equations",
                   "multipliers": [float(v) for v in lam], "iterations": it + 1, "complementarity_gap": gap})


def _dual_value(lam, q, c, g, h):
    """Verifier's own path: the Lagrangian dual g(lambda) = -1/2 r'Q^-1 r - h'lambda, r = c + G'lambda, by a SciPy
    Cholesky solve."""
    from scipy.linalg import cho_factor, cho_solve
    r = c + g.T @ lam
    return float(-0.5 * r @ cho_solve(cho_factor(q), r) - h @ lam)


def cqp_verify(data, output, certificate):
    import numpy as np
    q, c, g, h = _cqp_input(data)
    n, m = len(c), len(h)
    num = (int, float)
    if (not isinstance(output, dict) or set(output) != {"x", "objective"} or not isinstance(output["x"], list)
            or len(output["x"]) != n or not all(type(v) in num and math.isfinite(v) for v in output["x"])
            or type(output["objective"]) not in num or not math.isfinite(output["objective"])):
        return {"output_shape": False}
    lam = certificate.get("multipliers") if isinstance(certificate, dict) else None
    if (not isinstance(lam, list) or len(lam) != m
            or not all(type(v) in num and math.isfinite(v) for v in lam)):
        return {"output_shape": True, "dual_certificate_present": False}
    x, lam = np.array(output["x"], dtype=float), np.array(lam, dtype=float)
    primal = float(np.einsum("i,ij,j->", x, q, x) / 2 + np.dot(c, x))
    slack = h - g @ x
    feas = 1 + np.abs(h).max() + np.abs(g).max() * np.abs(x).max()
    grad = 1 + np.abs(q @ x).max() + np.abs(c).max() + np.abs(g.T @ lam).max()
    dual = _dual_value(lam, q, c, g, h)
    gap = primal - dual
    return {"output_shape": True, "dual_certificate_present": True,
            "primal_feasible": bool(slack.min() >= -QP_FEAS_TOL * feas),
            "dual_feasible": bool(lam.min() >= -QP_KKT_TOL * (1 + np.abs(lam).max())),
            "complementary_slackness": bool(np.abs(lam * slack).max() <= QP_KKT_TOL * grad * feas),
            "stationarity": bool(np.abs(q @ x + c + g.T @ lam).max() <= QP_KKT_TOL * grad),
            "duality_gap_closed": bool(-QP_GAP_TOL * (1 + abs(primal)) <= gap <= QP_GAP_TOL * (1 + abs(primal))),
            "objective_recomputed": abs(primal - output["objective"]) <= 1e-9 * (1 + abs(primal))}


def cqp_score(data, truth, output):
    """Feasibility within 1e-6 (scaled) is required (else wrong, -1). Quality 1 / (1 + max(0, rel_gap) / 1e-6), with
    rel_gap = (f(x) - f*) / (1 + |f*|) against the reference optimum: 1 at the optimum, 0.5 at a 1e-6 relative gap.
    Correct when rel_gap <= 1e-6."""
    import numpy as np
    if output is None:
        return {"quality": 0.0, "category": "abstain"}
    q, c, g, h = _cqp_input(data)
    try:
        x = np.array(output["x"], dtype=float)
    except (TypeError, KeyError, ValueError):
        return {"quality": -1.0, "category": "wrong"}
    if x.shape != c.shape or not np.isfinite(x).all():
        return {"quality": -1.0, "category": "wrong"}
    feas = 1 + np.abs(h).max() + np.abs(g).max() * np.abs(x).max()
    if (h - g @ x).min() < -1e-6 * feas:
        return {"quality": -1.0, "category": "wrong"}
    f_star = truth["optimum"]
    rel = (_cqp_objective(x, q, c) - f_star) / (1 + abs(f_star))
    return {"quality": 1.0 / (1.0 + max(0.0, rel) / QP_CORRECT_GAP),
            "category": "correct" if rel <= QP_CORRECT_GAP else "wrong"}


def cqp_dual_projected_gradient(data):
    """Baseline: projected gradient ascent on the dual (projection onto lambda >= 0 is a clip), step 1/L with
    L = ||G Q^-1 G'||_2, 3,000 iterations; x(lambda) = -Q^-1 (c + G'lambda). The primal point is not repaired, so a
    residual infeasibility counts against it."""
    import numpy as np
    q, c, g, h = _cqp_input(data)
    qi = np.linalg.inv(q)
    k = g @ qi @ g.T
    lip = float(np.linalg.eigvalsh(k).max())
    lam = np.zeros(len(h))
    for _ in range(3000):
        x = -qi @ (c + g.T @ lam)
        lam = np.maximum(0.0, lam + (g @ x - h) / lip)
    x = -qi @ (c + g.T @ lam)
    return {"x": [float(v) for v in x], "objective": _cqp_objective(x, q, c)}


def cqp_trust_constr(data):
    """Competitor: SciPy minimize(method='trust-constr') with the exact gradient and Hessian and the inequalities as
    a LinearConstraint (its interior-point barrier path), gtol 1e-10, xtol 1e-12, 3,000 iterations. OSQP is not
    installed in this container (checked 2026-10-22)."""
    import numpy as np
    from scipy.optimize import LinearConstraint, minimize
    q, c, g, h = _cqp_input(data)
    res = minimize(lambda x: _cqp_objective(x, q, c), np.zeros(len(c)), jac=lambda x: q @ x + c,
                   hess=lambda x: q, method="trust-constr",
                   constraints=[LinearConstraint(g, -np.inf, h)],
                   options={"gtol": 1e-10, "xtol": 1e-12, "maxiter": 3000, "verbose": 0})
    if not np.isfinite(res.x).all():
        return None
    return {"x": [float(v) for v in res.x], "objective": _cqp_objective(res.x, q, c)}


def cqp_reference(q, c, g, h):
    """Evaluation side only: a long SciPy SLSQP run (ftol 1e-15, 10,000 iterations) polished by an active-set
    iteration on exact equality-constrained KKT solves until every multiplier is non-negative and every inequality
    holds. Shares no code with the interior point; returns (optimum, x)."""
    import numpy as np
    from scipy.optimize import minimize
    res = minimize(lambda x: _cqp_objective(x, q, c), np.zeros(len(c)), jac=lambda x: q @ x + c, method="SLSQP",
                   constraints=[{"type": "ineq", "fun": lambda x: h - g @ x, "jac": lambda x: -g}],
                   options={"ftol": 1e-15, "maxiter": 10000})
    x = res.x
    scale = 1 + np.abs(h).max() + np.abs(g).max() * np.abs(x).max()
    active = set(np.flatnonzero(h - g @ x <= 1e-6 * scale).tolist())
    n = len(c)
    for _ in range(200):
        rows = sorted(active)
        ga = g[rows]
        kkt = np.block([[q, ga.T], [ga, np.zeros((len(rows), len(rows)))]])
        sol = np.linalg.lstsq(kkt, np.concatenate([-c, h[rows]]), rcond=None)[0]
        x, lam = sol[:n], sol[n:]
        viol = g @ x - h
        if len(rows) and lam.min() < -1e-10 * (1 + np.abs(lam).max()):
            active.discard(rows[int(np.argmin(lam))])
            continue
        if viol.max() > 1e-10 * scale:
            active.add(int(np.argmax(viol)))
            continue
        return _cqp_objective(x, q, c), x
    raise GenomeError("reference solve did not settle its active set")


def cqp_instance(seed):
    import numpy as np
    r = random.Random(f"genome:convex_qp_dual:{seed}")
    rng = np.random.default_rng(r.getrandbits(63))
    kind = ("well_conditioned", "ill_conditioned", "many_constraints")[seed % 3] if seed < 10 else r.choice(
        ("well_conditioned", "ill_conditioned", "many_constraints"))
    n = r.randint(8, 60)
    m = r.randint(max(2, n // 2), 2 * n) if kind != "many_constraints" else r.randint(3 * n, 6 * n)
    basis, _ = np.linalg.qr(rng.normal(size=(n, n)))
    spread = 1e4 if kind == "ill_conditioned" else 10.0
    eig = np.exp(rng.uniform(0, math.log(spread), n))
    q = (basis * eig) @ basis.T
    q = (q + q.T) / 2
    c = rng.normal(0, 10, n)
    g = rng.normal(size=(m, n))
    g /= np.linalg.norm(g, axis=1, keepdims=True)
    x0 = rng.normal(0, 1, n)
    h = g @ x0 + rng.uniform(0.0, 1.0, m)              # x0 is feasible, so the QP is feasible
    data = {"hessian": [[float(v) for v in row] for row in q], "linear_cost": [float(v) for v in c],
            "inequality_matrix": [[float(v) for v in row] for row in g], "inequality_rhs": [float(v) for v in h]}
    q, c, g, h = _cqp_input(data)
    optimum, xr = cqp_reference(q, c, g, h)
    return data, {"optimum": optimum, "active_constraints": int(np.sum(h - g @ xr <= 1e-8 * (1 + np.abs(h).max()))),
                  "kind": kind}


def cqp_subregion(data):
    import numpy as np
    q, c, g, h = _cqp_input(data)
    ev = np.linalg.eigvalsh(q)
    if ev.max() / max(ev.min(), 1e-300) > 1e3:
        return "ill_conditioned"
    return "many_constraints" if len(h) >= 3 * len(c) else "well_conditioned"


# =================================================================== genomes
def _common(**kw):
    return dict(buildability="BUILDABLE_NOW", memory_model="stateless",
                learning_rule="none (competence settles per geometry through GREG outcomes)", lineage=LINEAGE,
                dependency=None, **kw)


INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.logic.resolution_prover", version="1.0.0", family="prove_resolution", layer=3,
            operation="prove_clausal_entailment", epistemic_class="deductive",
            subgeometry="clausal entailment over propositional or ground first-order atoms: premises and a goal in "
                        "CNF; a checkable refutation per goal clause, or a countermodel",
            source_provenance="Robinson 1965 (resolution); Wos, Robinson and Carson 1965 (set of support); the "
                              "given-clause loop of Otter/E with forward and backward subsumption; Bachmair and "
                              "Ganzinger (ordered resolution, candidate-model construction)",
            native_representation="premise_clauses and goal_clauses: lists of clauses, each a list of literal "
                                  "strings; '~' marks negation; an atom is any string without whitespace (ground "
                                  "first-order atoms such as 'Path(a,b)' are atoms); the goal is the conjunction of "
                                  "its clauses; the empty goal clause asks whether the premises are contradictory",
            required_inputs=("premise_clauses", "goal_clauses"),
            output_contract={"verdict": "PROVED or NOT_PROVED",
                             "proofs": "per goal clause, a resolution refutation: steps {clause, rule premise | "
                                       "negated_goal | resolve, source or parents and pivot}, ending in []; or null",
                             "countermodel": "{atom: bool} satisfying every premise and falsifying the failed goal "
                                             "clause; or null",
                             "failed_goal": "index of the goal clause the countermodel falsifies; or null"},
            algorithm_or_runtime="per goal clause: set-of-support resolution from the negated goal (premises usable, "
                                 "never resolved together), then ordered resolution saturation of everything; "
                                 "shortest-clause-first given-clause loop, tautology deletion, forward and backward "
                                 "subsumption; proof DAG extracted from the empty clause; countermodel by candidate-"
                                 "model construction and re-checked",
            parameters={"max_generated_per_goal": TP_MAX_GENERATED, "max_active": TP_MAX_ACTIVE},
            composition_inputs=("a claim already compiled to clauses (premises and goal)",),
            composition_outputs=("a proof object any party can check without trusting the prover, or a countermodel",),
            evidence_type="exhaustive_check",
            verification_method="an independent proof checker with its own literal parser: every premise step is a "
                                "premise, every negated-goal step negates a literal of the goal clause, every "
                                "resolvent is recomputed from its cited earlier parents and pivot, and the proof ends "
                                "in the empty clause; a countermodel is evaluated on every premise and the goal clause",
            confidence_semantics="PROVED with checked proofs is certain (entailment by the soundness of resolution); "
                                 "NOT_PROVED with a checked countermodel is certain; UNKNOWN says nothing",
            resource_profile=f"at most {TP_MAX_GENERATED} resolvents and {TP_MAX_ACTIVE} active clauses per goal "
                             f"clause and phase; pure Python sets",
            latency_profile="milliseconds on Horn, chain and small random sets; seconds on pigeonhole 6-into-5",
            known_strengths=("emits a proof object a few dozen lines of independent code can check: trust moves from "
                             "the engine to the checker",
                             "set of support makes goal-directed Horn and chain entailments nearly instant",
                             "a saturated set yields a checked countermodel, so non-entailment is also certified"),
            known_failure_modes=("Z3 is the stronger decision engine: on large satisfiable random 3-CNF and hard "
                                 "combinatorial sets (pigeonhole beyond 6 into 5) saturation exceeds the budget and the "
                                 "genome answers UNKNOWN where Z3 decides",
                                 "resolution proofs are exponential on pigeonhole-like sets; the budget, not the proof "
                                 "system, ends those runs",
                                 "the declared scoring credits a checkable proof (1) over a bare verdict (0.5); under "
                                 "verdict-only scoring Z3 dominates this genome on every instance it decides",
                                 "first-order quantifiers are not handled: inputs must be ground (no unification)"),
            counterindications=("quantified first-order or higher-order goals (use a first-order prover or a proof "
                                "assistant)", "satisfiability at scale where no proof object is needed (use Z3 or a "
                                "CDCL solver)"),
            abstention_conditions=("UNKNOWN when the generated-clause or active-clause budget, or the request's "
                                   "latency budget, is exhausted before a refutation or saturation",
                                   "UNKNOWN when a saturated set's candidate model fails its re-check"),
            benchmark_suite="generated clause sets of six kinds: random 3-CNF with 8-16 atoms (truth-table range) and "
                            "20-32 atoms, ground Horn reachability over 4-6 constants, pigeonhole 2-4 holes "
                            "(contradictory or not), implication chains of 10-40 links with distractors and sometimes "
                            "one broken link, ground syllogisms over unary predicates; truth from Z3 (60 s); seeds 0-9 "
                            "dev, held-out seeds fixed by the admission freeze",
            baseline="truth-table enumeration (vectorised) for at most 18 atoms, abstaining above; a verdict and a "
                     "countermodel, no proof object",
            competitor="Z3 (CDCL SAT core, 10 s per goal clause): verdict and model; no proof object in this contract",
            **_common()),
        solve=prove_solve, verify=prove_verify, instance=tp_instance, score=prove_score,
        baseline=prove_truth_table, competitor=prove_z3, subregion=tp_subregion, tolerance=1e-9,
        notes={"scoring": "declared before any held-out run: checked certificate 1, bare correct verdict 0.5, "
                          "abstain 0, wrong or failed certificate -1",
               "truth": "Z3 on a separate path from the competitor call (own context, 60 s timeout)",
               "reserved": "no cortex reserved family names theorem proving; cortex.exact.symbolic is SymPy exact "
                           "calculation, not clausal entailment"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.stats.mdl_model_selection", version="1.0.0", family="mdl_model_select", layer=3,
            operation="select_polynomial_degree", epistemic_class="estimate",
            subgeometry="model-order selection for 1-D noisy data: the degree (0-8) of a polynomial regression",
            source_provenance="Rissanen 1978 (MDL); Rissanen 2000 (NML for linear regression, MDL denoising); Roos, "
                              "Myllymaki and Rissanen 2009 (the Stirling-form criterion); Schwarz 1978 (BIC, the "
                              "competitor)",
            native_representation="observations_x and observations_y (equal-length numeric lists) and max_degree (0-8)",
            required_inputs=("observations_x", "observations_y"),
            output_contract={"degree": "selected degree", "center": "x frame centre", "scale": "x frame half-width",
                             "coefficients": "power-basis coefficients in t = (x - center) / scale, ascending",
                             "code_lengths_bits": "NML code length of the data under every candidate degree"},
            algorithm_or_runtime="least squares on a Legendre basis of the rescaled abscissa for each degree; NML code "
                                 "length 1/2[(n-k) ln(RSS/(n-k)) + k ln(|yhat|^2/k) + ln(k(n-k))] in bits; argmin",
            parameters={"max_degree": MDL_MAX_DEGREE},
            composition_inputs=("a 1-D sample to be summarised by a smooth trend",),
            composition_outputs=("a polynomial trend of selected order with its code lengths",),
            evidence_type="exact_calculation",
            verification_method="every code length recomputed on a different basis (Chebyshev, QR projection) and "
                                "formula path; the selected degree must minimise them; the coefficients must "
                                "reproduce the least-squares projection at the selected degree; the frame recomputed",
            confidence_semantics="the code lengths and the argmin are exact calculations; that the selected degree is "
                                 "the generating one is an estimate, with no stated error rate",
            resource_profile="nine least-squares fits of at most 5,000 points", latency_profile="about 1-6 ms",
            known_strengths=("no tuning constant: the code length sets the complexity penalty",
                             "resists overfitting at small n where cross-validation is noisy"),
            known_failure_modes=("the k ln(|yhat|^2 / k) term is not invariant to an additive offset of the response: "
                                 "a large mean inflates the parameter cost and the criterion underfits (both dev misses "
                                 "had mean offsets of 4-10 noise standard deviations)",
                                 "Gaussian code: heavy-tailed noise is not modelled",
                                 "BIC is a strong competitor and agrees on most instances"),
            counterindications=("non-polynomial structure (periodic, piecewise) where no degree fits",
                                "extrapolation beyond the observed range"),
            abstention_conditions=("refuses input with fewer than 4 points or a degenerate abscissa",),
            benchmark_suite="generated polynomials of degree 0-6 in a Legendre basis on a random interval, the top "
                            "coefficient 3-15 standard errors of its estimate, n 15-150, uniform or clustered x, "
                            "Gaussian or Student-t(3) noise, sometimes a large offset; 400 held-back points inside the "
                            "observed range scored but never shown; truth is the generating degree; seeds 0-9 dev, "
                            "held-out seeds fixed by the admission freeze",
            baseline="the maximum admissible degree (overfit)",
            competitor="BIC (n ln(RSS/n) + (k+1) ln n) over the same degrees; 5-fold cross-validation was also run on "
                       "dev seeds and was weaker than BIC there (7.31 vs 8.34 total quality), so BIC is the competitor",
            **_common()),
        solve=mdl_solve, verify=mdl_verify, instance=mdl_instance, score=mdl_score,
        baseline=mdl_max_degree, competitor=mdl_bic, subregion=mdl_subregion, tolerance=1e-9,
        notes={"second_competitor": "greg.cognition.genomes.formal_b:mdl_cv (5-fold cross-validation), dev total "
                                    "quality 7.31 against BIC 8.34 on seeds 0-9",
               "scoring": "0.5 [degree = generating degree] + 0.5 min(1, reference holdout MSE / answer holdout MSE)"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.convex.qp_duality_certificate", version="1.0.0", family="convex_qp_dual", layer=3,
            operation="solve_convex_qp", epistemic_class="optimization",
            subgeometry="strictly convex quadratic programs with a dense coupled Hessian and general linear "
                        "inequalities (distinct from reconcile_qp: diagonal Hessian, equality balances, bounds)",
            source_provenance="Mehrotra 1992 (predictor-corrector); Nocedal and Wright, Numerical Optimization ch. 16 "
                              "(interior point for QP); Lagrangian duality (Boyd and Vandenberghe ch. 5)",
            native_representation="hessian (n x n, symmetric positive definite), linear_cost (n), inequality_matrix "
                                  "(m x n) and inequality_rhs (m): minimise 1/2 x'Qx + c'x subject to Gx <= h",
            required_inputs=("hessian", "linear_cost", "inequality_matrix", "inequality_rhs"),
            output_contract={"x": "the minimiser", "objective": "1/2 x'Qx + c'x at x"},
            algorithm_or_runtime="infeasible-start primal-dual interior point with Mehrotra's predictor-corrector, "
                                 "Cholesky-factored normal equations (tiny diagonal regularisation near convergence); "
                                 "the multipliers are returned in the certificate",
            parameters={"iterations": QP_IPM_ITERATIONS},
            composition_inputs=("a convex quadratic model already compiled to Q, c, G, h",),
            composition_outputs=("a minimiser with a dual certificate of optimality",),
            evidence_type="optimality_certificate",
            verification_method="primal feasibility, dual feasibility, complementary slackness and stationarity "
                                "recomputed in NumPy, and the duality gap between the primal objective and the "
                                "Lagrangian dual value computed independently by a SciPy Cholesky solve; a closed gap "
                                "with feasible x and non-negative multipliers proves near-optimality by weak duality",
            confidence_semantics="a verified certificate bounds suboptimality by the duality gap (relative 1e-7)",
            resource_profile="O((n^3 + m n^2) per iteration), at most 100 iterations",
            latency_profile="milliseconds at n <= 60, m <= 360",
            known_strengths=("a duality certificate anyone can check without trusting the solver",
                             "converges in 8-15 iterations regardless of conditioning on the benchmark",
                             "orders of magnitude faster than SciPy trust-constr on dense QPs"),
            known_failure_modes=("strictly convex only: a singular or indefinite Hessian is refused (abstain)",
                                 "infeasible or unbounded problems are not certified as such: the interior point "
                                 "returns UNKNOWN",
                                 "dense linear algebra: large sparse problems belong to a sparse QP solver (OSQP, "
                                 "not installed here)",
                                 "the dual projected-gradient baseline matches it to tolerance on well-conditioned "
                                 "instances; its edge there is only latency and the certificate"),
            counterindications=("nonconvex quadratic objectives", "large sparse problems", "integer variables"),
            abstention_conditions=("ABSTAIN when the Hessian has no Cholesky factor",
                                   "UNKNOWN when the interior point does not converge in 100 iterations or its normal "
                                   "equations lose positive definiteness"),
            benchmark_suite="generated dense QPs, n 8-60, Hessian eigenvalues spread 10 (well conditioned) or 1e4 "
                            "(ill conditioned), m from n/2 to 2n or 3n-6n (many constraints), unit-norm random rows, "
                            "feasible by construction; truth by a long SLSQP run polished by an exact active-set "
                            "KKT iteration; seeds 0-9 dev, held-out seeds fixed by the admission freeze",
            baseline="dual projected gradient (clip at zero), step 1/L, 3,000 iterations, primal not repaired",
            competitor="SciPy minimize(method='trust-constr') with exact gradient and Hessian, gtol 1e-10 (OSQP is not "
                       "installed)",
            **_common()),
        solve=cqp_solve, verify=cqp_verify, instance=cqp_instance, score=cqp_score,
        baseline=cqp_dual_projected_gradient, competitor=cqp_trust_constr, subregion=cqp_subregion, tolerance=1e-3,
        notes={"overlap": "reconcile_qp (solvers_d) covers diagonal-Hessian reconciliation with equality balances and "
                          "non-negativity; this genome covers dense coupled Hessians under general inequalities",
               "tolerance": "quality ties below 1e-3, i.e. relative suboptimality gaps below about 1e-9"}),
]
