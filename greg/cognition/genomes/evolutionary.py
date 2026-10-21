"""Layer 3 evolutionary intelligences: a genetic algorithm on additively decomposed pseudo-Boolean landscapes and
MAP-Elites quality-diversity on a redundant planar arm.

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.json``) lists ``L3.evo.ga`` and
``L3.evo.quality_diversity`` as ABSENT. No GA or QD library is installed (no DEAP, pymoo, pyribs or qdpy), so the
residual code is built here on NumPy, and each genome is measured against the simplest baseline and the strongest
deployable method installed:

* ``evo_ga_factored`` (``maximize_factored_binary``): a generational genetic algorithm (tournament selection,
  crossover, bit-flip mutation, one elite) under a hard evaluation budget, on a pseudo-Boolean objective given as
  a sum of factor tables (NK landscapes with random or adjacent neighbourhoods, and concatenated deceptive traps
  with tight or loose linkage). Baseline: random-restart first-improvement bit-flip hill climbing on the same
  budget. Competitor: OR-Tools CP-SAT on the exact factor model (one worker, fixed deterministic time), the
  strongest installed exact engine on dev seeds (SciPy HiGHS on the marginal-polytope MILP was weaker within the
  same time on 7 of 10 dev seeds). Verified by an independent pure-Python recomputation of the fitness and the
  upper bound; global optimality is never claimed.
* ``evo_map_elites`` (``quality_diversity_archive``): MAP-Elites with iso+line (Vassiliades and Mouret 2018)
  variation on the redundant planar arm benchmark (Cully et al. 2015): genotype = joint angles, behaviour = end
  effector position on a grid, quality = smoothness of the posture. The answer is the archive; the score is the
  QD-score (summed quality of filled cells over the reachable cells, i.e. coverage x mean quality). Baseline:
  uniform random search archived by the same insertion rule. Competitor: a single-objective optimiser (SciPy
  differential evolution on the quality) whose every evaluation is archived by the same rule - the conventional
  QD comparator; no QD library is installed. Verified by recomputing every elite's behaviour cell and quality and
  the QD-score from the genotypes.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output of any
method here creates authority. Development seeds 0-9 only.
"""
from __future__ import annotations

import math
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4 (restore the full five-layer scope)",
           "docs/collaboration/MIND-COVERAGE-2026-10-21.json (L3.evo.ga, L3.evo.quality_diversity ABSENT)")


def _common(**kw):
    return dict(buildability="BUILDABLE_NOW", memory_model="stateless",
                learning_rule="none (competence settles per geometry through GREG outcomes)", lineage=LINEAGE, **kw)


def _mapping(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    return data


def _cert(certificate):
    return certificate if isinstance(certificate, dict) else {}


# =================================================================== 1. genetic algorithm, factored landscapes
GA_MAX_BITS, GA_MAX_FACTORS, GA_MAX_ARITY = 2000, 4000, 10
GA_MAX_VALUE, GA_MAX_EVALS = 1_000_000, 1_000_000
GA_NATIVE_BITS = 400
GA_POPULATION, GA_TOURNAMENT, GA_CROSSOVER_RATE = 100, 2, 0.9
GA_CROSSOVER = "two_point"
CP_DETERMINISTIC_TIME = 2.0
GA_KINDS = ("nk_random", "trap_tight", "nk_adjacent", "trap_loose")


def _factored(data):
    """(num_bits, [(vars tuple, table tuple)], evaluations, seed) or GenomeError."""
    data = _mapping(data)
    n = bounded_int(data.get("num_bits"), low=1, high=GA_MAX_BITS, name="num_bits")
    factors = data.get("factors")
    if not isinstance(factors, list) or not 1 <= len(factors) <= GA_MAX_FACTORS:
        raise GenomeError(f"factors: 1-{GA_MAX_FACTORS} {{vars, table}} objects")
    out = []
    for f in factors:
        if not isinstance(f, dict) or set(f) != {"vars", "table"}:
            raise GenomeError("factor: {vars: [bit index], table: [int per assignment]}")
        v, t = f["vars"], f["table"]
        if (not isinstance(v, list) or not 1 <= len(v) <= GA_MAX_ARITY
                or not all(type(i) is int and 0 <= i < n for i in v) or len(set(v)) != len(v)):
            raise GenomeError(f"factor vars: 1-{GA_MAX_ARITY} distinct bit indices below num_bits")
        if (not isinstance(t, list) or len(t) != 2 ** len(v)
                or not all(type(x) is int and 0 <= x <= GA_MAX_VALUE for x in t)):
            raise GenomeError("factor table: 2^len(vars) integers in [0, 1000000]; the first var is the high bit")
        out.append((tuple(v), tuple(t)))
    evals = bounded_int(data.get("evaluations"), low=1, high=GA_MAX_EVALS, name="evaluations")
    seed = bounded_int(data.get("seed"), low=0, high=2**31 - 1, name="seed")
    return n, out, evals, seed


def _fitness(factors, bits):
    """Reference fitness, pure Python (verifier and score side)."""
    total = 0
    for v, t in factors:
        index = 0
        for i in v:
            index = (index << 1) | bits[i]
        total += t[index]
    return total


def _upper_bound(factors):
    return sum(max(t) for _, t in factors)


class _Budget:
    """Vectorised NumPy fitness of whole populations with an exact evaluation count (solver side)."""

    def __init__(self, n, factors, evals):
        import numpy as np
        self.np = np
        self.budget, self.used = evals, 0
        self.groups = {}
        for v, t in factors:
            self.groups.setdefault(len(v), ([], []))
            self.groups[len(v)][0].append(v)
            self.groups[len(v)][1].append(t)
        self.groups = {a: (np.array(v), np.array(t, dtype=np.int64), 1 << np.arange(a - 1, -1, -1))
                       for a, (v, t) in self.groups.items()}

    def __call__(self, pop):
        np = self.np
        pop = pop[:max(0, self.budget - self.used)]
        self.used += len(pop)
        total = np.zeros(len(pop), dtype=np.int64)
        for v, t, w in self.groups.values():
            index = (pop[:, v] * w).sum(-1)
            total += t[np.arange(len(t)), index].sum(-1)
        return pop, total


def ga_solve(data, budget):
    import numpy as np
    n, factors, evals, seed = _factored(data)
    if n > GA_NATIVE_BITS:
        return answer(None, {"reason": f"more than {GA_NATIVE_BITS} bits"}, status="ABSTAIN",
                      missing=[f"more than {GA_NATIVE_BITS} bits"])
    rng = np.random.default_rng(seed)
    f = _Budget(n, factors, evals)
    pop_size = min(GA_POPULATION, evals)
    pop, fit = f(rng.integers(0, 2, (pop_size, n), dtype=np.int64))
    best_i = int(fit.argmax())
    best, best_fit = pop[best_i].copy(), int(fit[best_i])
    generations = 0
    while f.used < evals and len(pop) >= 2:
        size = len(pop)
        draws = rng.integers(0, size, (size, GA_TOURNAMENT))
        parents = draws[np.arange(size), fit[draws].argmax(1)]
        a, b = pop[parents[0::2]], pop[parents[1::2]]
        m = min(len(a), len(b))
        a, b = a[:m], b[:m]
        if GA_CROSSOVER == "two_point":
            cuts = np.sort(rng.integers(0, n + 1, (m, 2)), axis=1)
            pos = np.arange(n)
            mask = (pos >= cuts[:, :1]) & (pos < cuts[:, 1:])
        else:
            mask = rng.random((m, n)) < 0.5
        mask &= (rng.random(m) < GA_CROSSOVER_RATE)[:, None]
        children = np.vstack([np.where(mask, b, a), np.where(mask, a, b)])[:size]
        children ^= (rng.random(children.shape) < 1.0 / n).astype(np.int64)
        children[0] = best                                  # one elite, re-evaluated (counted)
        children, cfit = f(children)
        if not len(children):
            break
        generations += 1
        pop, fit = children, cfit
        i = int(fit.argmax())
        if fit[i] > best_fit:
            best, best_fit = pop[i].copy(), int(fit[i])
    return answer({"bits": [int(x) for x in best], "fitness": best_fit},
                  {"method": f"generational GA: population {pop_size}, tournament {GA_TOURNAMENT}, "
                             f"{GA_CROSSOVER.replace('_', '-')} crossover p={GA_CROSSOVER_RATE}, bit-flip 1/n, "
                             "one elite",
                   "evaluations_used": f.used, "evaluation_budget": evals, "generations": generations,
                   "upper_bound": _upper_bound(factors), "global_optimality": "not claimed"})


def ga_verify(data, output, certificate):
    n, factors, evals, seed = _factored(data)
    if (not isinstance(output, dict) or set(output) != {"bits", "fitness"} or not isinstance(output["bits"], list)
            or type(output["fitness"]) is not int):
        return {"output_shape": False}
    bits = output["bits"]
    shape = len(bits) == n and all(type(b) is int and b in (0, 1) for b in bits)
    if not shape:
        return {"output_shape": True, "bits_are_a_full_assignment": False, "fitness_recomputed": False}
    used = _cert(certificate).get("evaluations_used")
    value = _fitness(factors, bits)
    return {"output_shape": True, "bits_are_a_full_assignment": True,
            "fitness_recomputed": value == output["fitness"],
            "not_above_the_factor_upper_bound": output["fitness"] <= _upper_bound(factors),
            "within_the_evaluation_budget": type(used) is int and 1 <= used <= evals}


def _trap_table(k):
    """Deceptive trap on k bits: 1000 when all ones, else 200 (k - 1 - ones)."""
    return [1000 if bin(a).count("1") == k else 200 * (k - 1 - bin(a).count("1")) for a in range(2 ** k)]


def _adjacent_optimum(n, factors):
    """Exact optimum of a cyclic adjacent-neighbourhood landscape by dynamic programming over the first K bits and
    a sliding window (independent of every search arm). Factor i reads bits i, i+1, ..., i+K (mod n)."""
    k = len(factors[0][0]) - 1
    tables = {v[0]: t for v, t in factors}
    best = -1
    mask = (1 << k) - 1
    for head in range(1 << k):                       # bits 0..k-1
        # state: last k bits (window ending at position j), value: best partial sum
        states = {head: 0}
        for j in range(k, n + k):
            nxt = {}
            for s, val in states.items():
                for b in (0, 1):
                    if j >= n and b != (head >> (k - 1 - (j - n))) & 1:
                        continue                    # wrap-around bits must equal the head
                    window = (s << 1) | b           # bits j-k..j
                    gain = tables[j - k][window]
                    ns = window & mask
                    if nxt.get(ns, -1) < val + gain:
                        nxt[ns] = val + gain
            states = nxt
        best = max(best, max(states.values()))
    return best


def ga_instance(seed):
    r = random.Random(f"genome:evo_ga_factored:{seed}")
    kind = GA_KINDS[seed % 4]
    n = r.choice((48, 64, 80, 96))
    factors, optimum = [], None
    if kind in ("nk_random", "nk_adjacent"):
        k = r.choice((2, 3, 4, 5, 6))
        for i in range(n):
            nbrs = [i] + (r.sample([j for j in range(n) if j != i], k) if kind == "nk_random"
                          else [(i + d) % n for d in range(1, k + 1)])
            factors.append({"vars": nbrs, "table": [r.randint(0, 1000) for _ in range(2 ** (k + 1))]})
        if kind == "nk_adjacent":
            optimum = _adjacent_optimum(n, [(tuple(f["vars"]), tuple(f["table"])) for f in factors])
    else:
        k = 5 if n % 5 == 0 else 4
        order = list(range(n))
        if kind == "trap_loose":
            r.shuffle(order)
        table = _trap_table(k)
        factors = [{"vars": order[i:i + k], "table": list(table)} for i in range(0, n - n % k, k)]
        optimum = 1000 * len(factors)
    data = {"num_bits": n, "factors": factors, "evaluations": 300 * n, "seed": r.randrange(2**31)}
    parsed = _factored(data)[1]
    return data, {"kind": kind, "optimum": optimum, "upper_bound": _upper_bound(parsed)}


def ga_subregion(data):
    n, factors, _, _ = _factored(data)
    adjacent = all(all((v[i] + 1) % n == v[i + 1] for i in range(len(v) - 1)) for v, _ in factors)
    deceptive = len({t for _, t in factors}) == 1
    return ("tight_linkage" if adjacent else "loose_linkage") + ("_deceptive" if deceptive else "_rugged")


def ga_score(data, truth, output):
    if not isinstance(output, dict) or not isinstance(output.get("bits"), list):
        return {"quality": 0.0, "category": "abstain"}
    n, factors, _, _ = _factored(data)
    bits = output["bits"]
    if len(bits) != n or not all(type(b) is int and b in (0, 1) for b in bits) \
            or _fitness(factors, bits) != output.get("fitness"):
        return {"quality": -1.0, "category": "wrong"}            # a false fitness claim
    reference = truth["optimum"] if truth.get("optimum") else truth["upper_bound"]
    return {"quality": output["fitness"] / reference, "category": "correct"}


def ga_hill_climb(data):
    """Baseline: random-restart first-improvement single-bit-flip hill climbing, random flip order, restarts on a
    local optimum; one evaluation per neighbour tried (incremental arithmetic, same count) within the budget."""
    n, factors, evals, seed = _factored(data)
    rng = random.Random(seed)
    touching = [[] for _ in range(n)]
    for fi, (v, _) in enumerate(factors):
        for i in v:
            touching[i].append(fi)

    def idx(fi, x):
        out = 0
        for i in factors[fi][0]:
            out = (out << 1) | x[i]
        return out
    used, best, best_fit = 0, None, -1
    while used < evals:
        x = [rng.randint(0, 1) for _ in range(n)]
        fit = _fitness(factors, x)
        used += 1
        if fit > best_fit:
            best, best_fit = list(x), fit
        improved = True
        while improved and used < evals:
            improved = False
            order = list(range(n))
            rng.shuffle(order)
            for i in order:
                if used >= evals:
                    break
                before = sum(factors[fi][1][idx(fi, x)] for fi in touching[i])
                x[i] ^= 1
                after = sum(factors[fi][1][idx(fi, x)] for fi in touching[i])
                used += 1
                if after > before:
                    fit += after - before
                    improved = True
                    if fit > best_fit:
                        best, best_fit = list(x), fit
                else:
                    x[i] ^= 1
    return {"bits": best, "fitness": best_fit}


def ga_cpsat(data):
    """Competitor: OR-Tools CP-SAT on the exact factor model (an element constraint per factor), one worker, fixed
    seed and a fixed deterministic time; its best incumbent, or None when it finds none."""
    from ortools.sat.python import cp_model
    n, factors, evals, seed = _factored(data)
    m = cp_model.CpModel()
    x = [m.NewBoolVar(f"x{i}") for i in range(n)]
    terms = []
    for fi, (v, t) in enumerate(factors):
        a = len(v)
        index = m.NewIntVar(0, 2 ** a - 1, f"i{fi}")
        m.Add(index == sum((1 << (a - 1 - p)) * x[i] for p, i in enumerate(v)))
        value = m.NewIntVar(min(t), max(t), f"v{fi}")
        m.AddElement(index, list(t), value)
        terms.append(value)
    m.Maximize(sum(terms))
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_deterministic_time = CP_DETERMINISTIC_TIME
    status = solver.Solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    bits = [int(solver.Value(b)) for b in x]
    return {"bits": bits, "fitness": _fitness(factors, bits)}


# =================================================================== 2. MAP-Elites quality-diversity
QD_MAX_JOINTS, QD_MAX_GRID, QD_MAX_EVALS = 24, 64, 200_000
QD_BATCH, QD_ISO_SIGMA, QD_LINE_SIGMA = 64, 0.01, 0.2
QD_DIGITS = 5
QD_NATIVE_SIZE = 16384                 # grid^2 x joints: keeps the archive answer under the worker's 256 KiB


def _arm(data):
    data = _mapping(data)
    links = data.get("link_lengths")
    if (not isinstance(links, list) or not 2 <= len(links) <= QD_MAX_JOINTS
            or not all(type(x) in (int, float) and math.isfinite(x) and 0.01 <= x <= 100 for x in links)):
        raise GenomeError(f"link_lengths: 2-{QD_MAX_JOINTS} positive lengths")
    grid = bounded_int(data.get("grid"), low=2, high=QD_MAX_GRID, name="grid")
    evals = bounded_int(data.get("evaluations"), low=1, high=QD_MAX_EVALS, name="evaluations")
    seed = bounded_int(data.get("seed"), low=0, high=2**31 - 1, name="seed")
    return [float(x) for x in links], grid, evals, seed


def _arm_eval(links, angles, grid):
    """Reference (verifier and score side, pure Python): (cell [i, j], quality in [0, 1]).

    Genotype ``angles`` in [0, 1]^d maps to joint angles (g - 0.5) * 2 pi; behaviour is the end effector scaled by
    the total length to [0, 1]^2 and binned on a grid x grid lattice; quality is 1 - std(joint angles) / pi."""
    total = sum(links)
    x = y = heading = 0.0
    thetas = []
    for length, g in zip(links, angles):
        a = (g - 0.5) * 2 * math.pi
        thetas.append(a)
        heading += a
        x += length * math.cos(heading)
        y += length * math.sin(heading)
    bx, by = (x / total + 1) / 2, (y / total + 1) / 2
    cell = [min(grid - 1, max(0, int(bx * grid))), min(grid - 1, max(0, int(by * grid)))]
    mean = sum(thetas) / len(thetas)
    std = math.sqrt(sum((t - mean) ** 2 for t in thetas) / len(thetas))
    return cell, 1.0 - std / math.pi


def _arm_eval_batch(np, links, genomes, grid):
    """Solver side, NumPy: (cells (B, 2), quality (B,))."""
    links = np.asarray(links)
    thetas = (genomes - 0.5) * 2 * np.pi
    heading = np.cumsum(thetas, axis=1)
    x = (links * np.cos(heading)).sum(1)
    y = (links * np.sin(heading)).sum(1)
    total = links.sum()
    cells = np.stack([np.clip(((x / total + 1) / 2 * grid).astype(int), 0, grid - 1),
                      np.clip(((y / total + 1) / 2 * grid).astype(int), 0, grid - 1)], axis=1)
    return cells, 1.0 - thetas.std(axis=1) / np.pi


def reachable_cells(links, grid):
    """Grid cells whose square meets the reachable annulus [max(0, 2 l_max - L), L] (the planar workspace of a
    revolute chain with unlimited joints), scaled like the behaviour descriptor. Exact geometry, no sampling."""
    total = sum(links)
    inner = max(0.0, 2 * max(links) - total) / total
    count = 0
    for i in range(grid):
        for j in range(grid):
            # cell square in the [-1, 1]^2 frame
            x0, x1 = 2 * i / grid - 1, 2 * (i + 1) / grid - 1
            y0, y1 = 2 * j / grid - 1, 2 * (j + 1) / grid - 1
            dx = max(x0 - 0, 0 - x1, 0.0)
            dy = max(y0 - 0, 0 - y1, 0.0)
            near = math.hypot(dx, dy)
            far = max(math.hypot(px, py) for px in (x0, x1) for py in (y0, y1))
            if near <= 1.0 and far >= inner:
                count += 1
    return count


class _Archive:
    def __init__(self, np, grid, d):
        self.np = np
        self.fit = np.full((grid, grid), -np.inf)
        self.gen = np.zeros((grid, grid, d))

    def insert(self, cells, quality, genomes):
        for (i, j), q, g in zip(cells, quality, genomes):
            if q > self.fit[i, j]:
                self.fit[i, j] = q
                self.gen[i, j] = g

    def output(self, links, grid):
        """The archive as a compact answer: genomes rounded to QD_DIGITS decimals, every elite's cell and quality
        recomputed by the reference kinematics from the rounded genome (rounding can move a genome across a cell
        border; on a collision the better elite is kept)."""
        np = self.np
        best = {}
        for i in range(grid):
            for j in range(grid):
                if np.isfinite(self.fit[i, j]):
                    genome = [round(float(v), QD_DIGITS) for v in self.gen[i, j]]
                    cell, q = _arm_eval(links, genome, grid)
                    if tuple(cell) not in best or q > best[tuple(cell)]["quality"]:
                        best[tuple(cell)] = {"cell": cell, "genome": genome, "quality": q}
        elites = [best[c] for c in sorted(best)]
        return {"elites": elites, "qd_score": math.fsum(e["quality"] for e in elites)}


def qd_solve(data, budget):
    import numpy as np
    links, grid, evals, seed = _arm(data)
    d = len(links)
    if grid * grid * d > QD_NATIVE_SIZE:
        return answer(None, {"reason": f"grid^2 x joints above {QD_NATIVE_SIZE}"}, status="ABSTAIN",
                      missing=[f"grid^2 x joints above {QD_NATIVE_SIZE} (archive answer too large)"])
    rng = np.random.default_rng(seed)
    archive = _Archive(np, grid, d)
    used = 0
    init = min(evals, max(QD_BATCH, evals // 10))
    while used < init:
        g = rng.random((min(QD_BATCH, init - used), d))
        archive.insert(*_arm_eval_batch(np, links, g, grid), g)
        used += len(g)
    while used < evals:
        filled = np.argwhere(np.isfinite(archive.fit))
        b = min(QD_BATCH, evals - used)
        pa = filled[rng.integers(0, len(filled), b)]
        pb = filled[rng.integers(0, len(filled), b)]
        xa, xb = archive.gen[pa[:, 0], pa[:, 1]], archive.gen[pb[:, 0], pb[:, 1]]
        g = xa + QD_ISO_SIGMA * rng.standard_normal((b, d)) + QD_LINE_SIGMA * rng.standard_normal((b, 1)) * (xb - xa)
        g = np.clip(g, 0.0, 1.0)
        archive.insert(*_arm_eval_batch(np, links, g, grid), g)
        used += b
    out = archive.output(links, grid)
    return answer(out, {"method": f"MAP-Elites, iso+line variation (sigma_iso {QD_ISO_SIGMA}, sigma_line "
                                  f"{QD_LINE_SIGMA}), batch {QD_BATCH}, {init} random initial evaluations",
                        "evaluations_used": used, "evaluation_budget": evals, "cells_filled": len(out["elites"]),
                        "reachable_cells": reachable_cells(links, grid)})


def qd_verify(data, output, certificate):
    links, grid, evals, seed = _arm(data)
    d = len(links)
    if (not isinstance(output, dict) or set(output) != {"elites", "qd_score"} or not isinstance(output["elites"], list)
            or type(output["qd_score"]) not in (int, float) or not math.isfinite(output["qd_score"])):
        return {"output_shape": False}
    ok_shape = all(isinstance(e, dict) and set(e) == {"cell", "genome", "quality"} and isinstance(e["cell"], list)
                   and len(e["cell"]) == 2 and all(type(c) is int and 0 <= c < grid for c in e["cell"])
                   and isinstance(e["genome"], list) and len(e["genome"]) == d
                   and all(type(v) in (int, float) and math.isfinite(v) and 0.0 <= v <= 1.0 for v in e["genome"])
                   and type(e["quality"]) in (int, float) and math.isfinite(e["quality"]) for e in output["elites"])
    if not ok_shape:
        return {"output_shape": True, "elites_well_formed": False, "cells_and_qualities_recomputed": False}
    cells = [tuple(e["cell"]) for e in output["elites"]]
    recomputed = [_arm_eval(links, e["genome"], grid) for e in output["elites"]]
    used = _cert(certificate).get("evaluations_used")
    return {"output_shape": True, "elites_well_formed": True,
            "one_elite_per_cell": len(set(cells)) == len(cells),
            "cells_and_qualities_recomputed": all(
                tuple(c) == tuple(e["cell"]) and abs(q - e["quality"]) <= 1e-12
                for (c, q), e in zip(recomputed, output["elites"])),
            "qd_score_recomputed": abs(math.fsum(q for _, q in recomputed) - output["qd_score"]) <= 1e-9,
            "no_more_elites_than_evaluations": type(used) is int and len(cells) <= used <= evals}


def qd_instance(seed):
    r = random.Random(f"genome:evo_map_elites:{seed}")
    d = r.choice((4, 6, 8, 12, 16))
    kind = ("uniform", "tapered", "random", "one_long")[seed % 4]
    if kind == "uniform":
        links = [1.0] * d
    elif kind == "tapered":
        links = [round(1.0 - 0.6 * i / d, 4) for i in range(d)]
    elif kind == "random":
        links = [round(r.uniform(0.3, 1.0), 4) for _ in range(d)]
    else:
        links = [round(r.uniform(0.3, 0.6), 4) for _ in range(d)]
        links[r.randrange(d)] = round(0.6 * sum(links), 4)       # an inner hole in the workspace
    grid = r.choice((16, 24, 32))
    data = {"link_lengths": links, "grid": grid, "evaluations": 500 * d * 4, "seed": r.randrange(2**31)}
    return data, {"reachable_cells": reachable_cells(links, grid), "kind": kind}


def qd_subregion(data):
    links, grid, evals, seed = _arm(data)
    return ("low_dim" if len(links) <= 6 else "high_dim") + ("_coarse" if grid <= 16 else "_fine")


def qd_score(data, truth, output):
    if not isinstance(output, dict) or not isinstance(output.get("elites"), list):
        return {"quality": 0.0, "category": "abstain"}
    checks = qd_verify(data, output, {"evaluations_used": _arm(data)[2]})
    if not all(checks.values()):
        return {"quality": -1.0, "category": "wrong"}
    return {"quality": output["qd_score"] / truth["reachable_cells"], "category": "correct"}


def _archived(links, grid, genomes_list):
    import numpy as np
    archive = _Archive(np, grid, len(links))
    g = np.clip(np.asarray(genomes_list, dtype=float), 0.0, 1.0)
    archive.insert(*_arm_eval_batch(np, links, g, grid), g)
    return archive.output(links, grid)


def qd_random(data):
    """Baseline: uniform random genotypes for the whole budget, archived by the same elitist insertion."""
    import numpy as np
    links, grid, evals, seed = _arm(data)
    rng = np.random.default_rng(seed)
    return _archived(links, grid, rng.random((evals, len(links))))


def qd_single_objective(data):
    """Competitor: SciPy differential evolution maximising the quality alone (the conventional single-objective
    comparator in QD work), every evaluation it makes archived by the same elitist insertion; same budget."""
    import numpy as np
    from scipy.optimize import differential_evolution
    links, grid, evals, seed = _arm(data)
    d = len(links)
    seen = []

    def f(x):
        x = np.atleast_2d(x.T if x.ndim == 2 else x)
        seen.extend(x[:max(0, evals - len(seen))].tolist())
        return -(1.0 - ((x - 0.5) * 2 * np.pi).std(axis=1) / np.pi)
    differential_evolution(f, [(0.0, 1.0)] * d, maxiter=max(1, evals // (15 * d) - 1), popsize=15, seed=seed,
                           polish=False, tol=0, atol=0, vectorized=True, updating="deferred")
    return _archived(links, grid, seen[:evals])


# =================================================================== registration
INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.evolutionary.genetic_algorithm", version="1.0.0", family="evo_ga_factored",
            layer=3, operation="maximize_factored_binary", epistemic_class="optimization",
            subgeometry="maximise an additively decomposed pseudo-Boolean function (a sum of factor tables over "
                        "small sets of bits: NK landscapes, deceptive traps) under a hard evaluation budget",
            source_provenance="Holland (1975); Goldberg (1989) deceptive traps and building blocks; Kauffman (1993) "
                              "NK landscapes; implemented on NumPy (no GA library is installed); OR-Tools CP-SAT "
                              "(Apache-2.0) as the competitor",
            native_representation="number of bits, factor list {vars: [bit index], table: [int]} (first var is "
                                  "the high bit of the table index), evaluation budget and seed",
            required_inputs=("num_bits", "factors", "evaluations", "seed"),
            output_contract={"bits": "[0|1 per bit]", "fitness": "int"},
            algorithm_or_runtime=f"generational GA: population {GA_POPULATION}, binary tournament, two-point "
                                 f"crossover p={GA_CROSSOVER_RATE}, bit-flip mutation 1/n, one re-evaluated elite; "
                                 "stops exactly at the evaluation budget",
            parameters={"population": GA_POPULATION, "tournament": GA_TOURNAMENT, "crossover": GA_CROSSOVER,
                        "crossover_rate": GA_CROSSOVER_RATE, "mutation": "1/n", "native_bits": GA_NATIVE_BITS},
            composition_inputs=("a decomposed binary objective",), composition_outputs=("best assignment", "fitness"),
            evidence_type="heuristic_trace",
            verification_method="the fitness recomputed from the factor tables by independent pure-Python code; the "
                                "assignment complete and binary; the fitness not above the sum of table maxima; the "
                                "evaluations within the budget",
            confidence_semantics="the returned assignment has exactly the stated fitness; no claim of global "
                                 "optimality",
            resource_profile="exactly the declared evaluation budget, vectorised in NumPy per generation",
            latency_profile="tens of milliseconds at benchmark size",
            known_strengths=("two-point crossover recombines adjacent building blocks: it escapes deceptive traps "
                             "with tight linkage that trap bit-flip hill climbing",
                             "needs no model of the structure, only evaluations"),
            known_failure_modes=("loose linkage (building blocks spread across the string) defeats the crossover; "
                                 "it then behaves like a noisy hill climber",
                                 "without local search it refines slowly: hill climbing is as good or better on "
                                 "random NK landscapes",
                                 "an exact solver wins wherever the structure is small enough to solve",
                                 "no global optimality guarantee"),
            counterindications=("small or low-epistasis models an exact solver proves quickly (use CP-SAT or MILP)",
                                "objectives with no decomposition the caller can state (use a black-box method)",
                                "continuous decisions (use blackbox_multistart_lbfgsb)"),
            abstention_conditions=(f"more than {GA_NATIVE_BITS} bits",),
            benchmark_suite="NK landscapes (random and cyclic-adjacent neighbourhoods, K 2-6) and concatenated "
                            "deceptive traps (k 4-5, tight or loose linkage), 48-96 bits, 300 evaluations per bit; "
                            "quality is fitness over the exact optimum (traps by construction, adjacent NK by "
                            "dynamic programming) or over the sum of table maxima (random NK); seeds 0-9 dev, "
                            "held-out seeds fixed by the admission freeze",
            baseline="random-restart first-improvement single-bit-flip hill climbing on the same evaluation budget",
            competitor=f"OR-Tools CP-SAT on the exact factor model (element constraints, one worker, deterministic "
                       f"time {CP_DETERMINISTIC_TIME}), its best incumbent", dependency=None, **_common()),
        solve=ga_solve, verify=ga_verify, instance=ga_instance, score=ga_score, baseline=ga_hill_climb,
        competitor=ga_cpsat, subregion=ga_subregion, tolerance=1e-12,
        notes={"competitor_choice": "CP-SAT (element model) beat SciPy HiGHS on the marginal-polytope MILP within "
                                    "2 s on 7 of 10 dev seeds; both measured on dev seeds 0-9 only"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.evolutionary.map_elites", version="1.0.0", family="evo_map_elites", layer=3,
            operation="quality_diversity_archive", epistemic_class="optimization",
            subgeometry="illuminate a behaviour space: return, for every reachable cell of a behaviour grid, the "
                        "highest-quality solution found (the redundant planar arm: postures per end-effector cell)",
            source_provenance="Mouret and Clune (2015) MAP-Elites; Vassiliades and Mouret (2018) iso+line "
                              "variation; Cully et al. (2015) arm benchmark; implemented on NumPy (no QD library is "
                              "installed); SciPy differential evolution as the competitor",
            native_representation="link lengths of a planar revolute chain, grid resolution, evaluation budget, "
                                  "seed",
            required_inputs=("link_lengths", "grid", "evaluations", "seed"),
            output_contract={"elites": "[{cell: [i, j], genome: [float in [0, 1], 5 decimals], quality: float}] sorted by cell",
                             "qd_score": "float (sum of elite qualities)"},
            algorithm_or_runtime=f"MAP-Elites: a tenth of the budget uniform random, then batches of {QD_BATCH} "
                                 "children of two uniformly drawn elites by iso+line variation, elitist insertion",
            parameters={"batch": QD_BATCH, "sigma_iso": QD_ISO_SIGMA, "sigma_line": QD_LINE_SIGMA},
            composition_inputs=("a parameterised design with a behaviour descriptor",),
            composition_outputs=("archive of diverse high-quality solutions", "QD-score"),
            evidence_type="heuristic_trace",
            verification_method="every elite's cell and quality recomputed from its genome by independent "
                                "pure-Python kinematics; one elite per cell; genomes in the unit box; the QD-score "
                                "re-summed; no more elites than evaluations used",
            confidence_semantics="each elite exists and has exactly the stated cell and quality; coverage and "
                                 "per-cell optimality are not claimed",
            resource_profile="exactly the declared evaluation budget; archive grid x grid",
            latency_profile="tens to hundreds of milliseconds at benchmark size",
            known_strengths=("covers the behaviour space a single-objective optimiser collapses",
                             "line variation exploits correlations between elites"),
            known_failure_modes=("quality inside a cell improves slowly: a per-cell optimiser can beat it on "
                                 "quality where it covers the cell", "the grid must be chosen by the caller",
                                 "measured only on the planar arm"),
            counterindications=("one best solution is wanted (use a single-objective optimiser)",
                                "behaviour spaces of more than two or three dimensions on a grid (use CVT "
                                "MAP-Elites)"),
            abstention_conditions=(f"grid^2 x joints above {QD_NATIVE_SIZE} (the archive answer would exceed the "
                                   "worker's 256 KiB output limit)",),
            benchmark_suite="redundant planar arms with 4-16 joints (uniform, tapered, random links, or one long "
                            "link that opens an inner hole), grids 16-32, 2000 evaluations per joint; quality is "
                            "QD-score over the exactly computed number of reachable cells; seeds 0-9 dev, held-out "
                            "seeds fixed by the admission freeze",
            baseline="uniform random search on the same budget, archived by the same insertion rule",
            competitor="SciPy differential evolution maximising quality alone, every evaluation archived by the "
                       "same insertion rule (the conventional single-objective comparator)", dependency=None,
            **_common()),
        solve=qd_solve, verify=qd_verify, instance=qd_instance, score=qd_score, baseline=qd_random,
        competitor=qd_single_objective, subregion=qd_subregion, tolerance=1e-9),
]
