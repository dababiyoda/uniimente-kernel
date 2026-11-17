"""Search batch B: novelty search on deceptive mazes, a selection hyper-heuristic for large bin packing, and role
differentiation under local lateral-inhibition rules.

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.json``) lists ``L3.evo.novelty``,
``L3.evo.hyperheuristics`` and ``L4.differentiation`` as ABSENT. No novelty-search, hyper-heuristic or distributed
MIS library is installed, so the residual code is built here on NumPy and the standard library, and each genome is
measured against the simplest baseline and the strongest deployable mechanism installed:

* ``evo_novelty_search`` (``deceptive_maze_navigate``): find a fixed-length move program that drives an agent from a
  start cell to a goal cell of a grid maze, using only a simulator and the declared objective (Manhattan distance
  of the final cell to the goal). Some mazes are declared deceptive: their shortest path is much longer than the
  Manhattan distance, so the objective leads into a dead end. Method: novelty search (Lehman and Stanley 2011) with
  an archive over the behaviour descriptor (the final cell), then hill-climbing refinement on the objective.
  Baseline: objective-driven hill climbing with restarts. Competitor: MAP-Elites over the same behaviour (one elite
  per final cell), same budget and mutation. Truth: the exact maze distance field by NetworkX BFS. Verified by an
  independent pure-Python replay of the moves.
* ``hyper_select_lowlevel`` (``bin_packing_hyperheuristic``): one-dimensional bin packing of 120-1000 items under a
  budget of low-level heuristic applications. Method: a selection hyper-heuristic (UCB1 credit assignment over first
  fit and best fit bin draining, first-fit-decreasing ruin-and-recreate, swap and move local search, non-worsening
  acceptance). This differs from ``binpack_cpsat`` (``bin_packing_min_bins``), which proves the minimum with CP-SAT
  and abstains above 150 items: this genome is an anytime heuristic for the sizes where the exact model is not
  native, and claims no optimality. Baseline: first-fit decreasing. Competitor: the stronger on dev seeds 0-9 of a
  random-selection hyper-heuristic and the best single low-level heuristic, each on an equal budget (see
  ``HH_COMPETITOR``). Truth: planted instances with zero slack, whose optimum is the volume lower bound (exact).
  Verified by an independent recount of every item and load.
* ``develop_differentiate`` (``local_role_differentiation``): every node of a graph chooses a role (leader or
  member) using only its distance-d neighbours' states, so that leaders are more than d hops apart and every member
  is within d hops of a leader (a maximal independent set of the d-th power graph). Method: phases of random-
  priority lateral inhibition (a node whose priority beats every undecided neighbour's becomes a leader and
  inhibits its neighbourhood; Luby 1986, Metivier et al. 2011). Score: the pattern first, then message rounds in the
  LOCAL model. Baseline: random roles. Competitor: a centralised greedy MIS (NetworkX) whose information must be
  gathered at a graph centre and broadcast back (2 x radius rounds). Truth: CP-SAT minimum leader count and an
  independent pattern check. Verified by a vectorised NumPy recomputation of the declared rule and the pattern.
  "Differentiation" names the effect (role specialisation by local rules); nothing biological is claimed.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output of any
method here creates authority. Development seeds 0-9 only.
"""
from __future__ import annotations

from collections import deque
import hashlib
import math
import random

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4 (restore the full five-layer scope)",
           "docs/collaboration/MIND-COVERAGE-2026-10-21.json (L3.evo.novelty, L3.evo.hyperheuristics, "
           "L4.differentiation ABSENT)")


def _common(**kw):
    return dict(buildability="BUILDABLE_NOW", memory_model="stateless",
                learning_rule="none (competence settles per geometry through GREG outcomes)", lineage=LINEAGE, **kw)


def _mapping(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    return data


def _cert(certificate):
    return certificate if isinstance(certificate, dict) else {}


def _abstain(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="ABSTAIN", missing=[reason])


def _unknown(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="UNKNOWN", missing=[reason])


# =================================================================== 1. novelty search on deceptive mazes
MZ_MAX_SIDE, MZ_MAX_LENGTH, MZ_MAX_EVALS = 64, 400, 200_000
MOVES = "UDLR"
DELTA = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}
NS_POPULATION, NS_K, NS_MUTATION = 50, 15, 2.0          # mutation: expected genes resampled per child
NS_REFINE_SHARE = 0.2                                     # share of the budget kept for objective refinement
NS_RHO0, NS_ARCHIVE_MAX = 3.0, 2000
HC_PATIENCE = 200
MZ_EVALS_PER_STEP = 400                                   # benchmark budget: evaluations per program step
MZ_KINDS = ("cup", "scatter", "comb", "rooms")


def _maze(data):
    """(grid rows as tuple of str, start (r, c), goal (r, c), length, evaluations, seed) or GenomeError."""
    data = _mapping(data)
    rows = data.get("maze")
    if (not isinstance(rows, list) or not 3 <= len(rows) <= MZ_MAX_SIDE
            or not all(isinstance(r, str) and len(r) == len(rows[0]) and set(r) <= {"#", "."} for r in rows)
            or not 3 <= len(rows[0]) <= MZ_MAX_SIDE):
        raise GenomeError(f"maze: 3-{MZ_MAX_SIDE} equal-length rows of '#' (wall) and '.' (free)")

    def cell(name):
        v = data.get(name)
        if (not isinstance(v, list) or len(v) != 2 or not all(type(x) is int for x in v)
                or not 0 <= v[0] < len(rows) or not 0 <= v[1] < len(rows[0]) or rows[v[0]][v[1]] != "."):
            raise GenomeError(f"{name}: [row, col] of a free cell")
        return v[0], v[1]
    start, goal = cell("start"), cell("goal")
    if start == goal:
        raise GenomeError("start and goal must differ")
    length = bounded_int(data.get("genome_length"), low=1, high=MZ_MAX_LENGTH, name="genome_length")
    evals = bounded_int(data.get("evaluations"), low=1, high=MZ_MAX_EVALS, name="evaluations")
    seed = bounded_int(data.get("seed"), low=0, high=2**31 - 1, name="seed")
    return tuple(rows), start, goal, length, evals, seed


def _replay(rows, start, goal, moves):
    """Reference replay (verifier and score side, pure Python): (final cell, step at which the goal was first
    reached or -1). A move into a wall or off the grid leaves the agent in place; the episode ends at the goal."""
    r, c = start
    for t, m in enumerate(moves, 1):
        dr, dc = DELTA[m]
        nr, nc = r + dr, c + dc
        if 0 <= nr < len(rows) and 0 <= nc < len(rows[0]) and rows[nr][nc] == ".":
            r, c = nr, nc
        if (r, c) == goal:
            return [r, c], t
    return [r, c], -1


class _Sim:
    """Simulator on a cell transition table with an exact evaluation count (solver side): vectorised NumPy for
    populations, a plain loop for a single program. The goal cell is absorbing."""

    def __init__(self, rows, start, goal, length, evals):
        import numpy as np
        self.np = np
        h, w = len(rows), len(rows[0])
        self.w = w
        trans = []
        for r in range(h):
            for c in range(w):
                nxt = []
                for m in MOVES:
                    dr, dc = DELTA[m]
                    nr, nc = r + dr, c + dc
                    free = 0 <= nr < h and 0 <= nc < w and rows[nr][nc] == "."
                    nxt.append(nr * w + nc if free and (r, c) != goal else r * w + c)
                trans.append(nxt)
        self.trans_list = trans
        self.trans = np.array(trans)
        self.s, self.g = start[0] * w + start[1], goal[0] * w + goal[1]
        self.start, self.goal, self.length = start, goal, length
        self.budget, self.used = evals, 0

    def __call__(self, genomes):
        """genomes (B, L) ints in 0..3 -> (genomes kept, final cells (B, 2), reached step (B,) or -1)."""
        np = self.np
        genomes = genomes[:max(0, self.budget - self.used)]
        self.used += len(genomes)
        b = len(genomes)
        if b == 1:
            pos, step, trans, goal = self.s, -1, self.trans_list, self.g
            for t, m in enumerate(genomes[0].tolist(), 1):
                pos = trans[pos][m]
                if pos == goal:
                    step = t
                    break
            return genomes, np.array([[pos // self.w, pos % self.w]]), np.array([step])
        pos = np.full(b, self.s)
        reached = np.full(b, -1)
        for t in range(self.length):
            pos = self.trans[pos, genomes[:, t]]
            reached[(pos == self.g) & (reached < 0)] = t + 1
        return genomes, np.stack([pos // self.w, pos % self.w], axis=1), reached

    def objective(self, cells):
        return self.np.abs(cells - self.np.array(self.goal)).sum(1)


def _mutate(np, rng, parents, length):
    children = parents.copy()
    mask = rng.random(children.shape) < NS_MUTATION / length
    children[mask] = rng.integers(0, 4, int(mask.sum()))
    return children


def _maze_answer(rows, start, goal, genome):
    moves = "".join(MOVES[int(g)] for g in genome)
    final, step = _replay(rows, start, goal, moves)
    return {"moves": moves, "final": final, "reached_at": step}


def _hill_refine(np, rng, sim, genome, cell, reached):
    """(1+1) objective hill climbing from one genome on the remaining budget (accept equal or better)."""
    best, best_obj, best_reached = genome, int(sim.objective(cell[None])[0]), reached
    while sim.used < sim.budget and best_reached < 0:
        child = _mutate(np, rng, best[None], sim.length)
        kept, cells, hit = sim(child)
        if not len(kept):
            break
        obj = int(sim.objective(cells)[0])
        if hit[0] >= 0 or obj <= best_obj:
            best, best_obj, best_reached = kept[0], obj, int(hit[0])
    return best, best_reached


def ns_solve(data, budget):
    import numpy as np
    rows, start, goal, length, evals, seed = _maze(data)
    rng = np.random.default_rng(seed)
    sim = _Sim(rows, start, goal, length, evals)
    novelty_budget = max(1, int(evals * (1 - NS_REFINE_SHARE)))
    sim.budget = novelty_budget
    pop, cells, hit = sim(rng.integers(0, 4, (min(NS_POPULATION, novelty_budget), length)))
    archive = np.zeros((0, 2))
    rho, generations, added_total = NS_RHO0, 0, 0
    found = None
    best_i = int(sim.objective(cells).argmin())
    best = (pop[best_i], cells[best_i], int(hit[best_i]), int(sim.objective(cells)[best_i]))
    if (hit >= 0).any():
        i = int(np.flatnonzero(hit >= 0)[0])
        found = pop[i]
    stale = 0
    def novelty(points, ref):
        """Mean Euclidean distance of each point to its k nearest in ``ref`` (``points`` are rows of ``ref``)."""
        dist = np.sqrt(((points[:, None, :] - ref[None, :, :]) ** 2).sum(-1))
        k = min(NS_K, len(ref) - 1)
        return np.sort(dist, axis=1)[:, 1:k + 1].mean(1) if k > 0 else np.zeros(len(points))
    while found is None and sim.used < sim.budget and len(pop) >= 2:
        # (mu + lambda) on novelty: uniform parents, mutated children, the most novel mu of parents and children
        # (against both and the archive) survive; children above the adaptive threshold enter the archive
        parents = rng.integers(0, len(pop), len(pop))
        children, ccells, chit = sim(_mutate(np, rng, pop[parents], length))
        if not len(children):
            break
        generations += 1
        allg, allc, allh = np.vstack([pop, children]), np.vstack([cells, ccells]), np.concatenate([hit, chit])
        ref = np.vstack([allc, archive]) if len(archive) else allc
        nov = novelty(allc, ref)
        add = ccells[nov[len(pop):] > rho]
        if len(add):
            archive = np.vstack([archive, add])[-NS_ARCHIVE_MAX:]
            added_total += len(add)
            stale = 0
        else:
            stale += 1
        if len(add) > 4:
            rho *= 1.2
        elif stale >= 5:
            rho *= 0.95
        keep = np.argsort(-nov, kind="stable")[:NS_POPULATION]
        pop, cells, hit = allg[keep], allc[keep], allh[keep]
        obj = sim.objective(ccells)
        i = int(obj.argmin())
        if obj[i] < best[3]:
            best = (children[i], ccells[i], int(chit[i]), int(obj[i]))
        if (chit >= 0).any():
            found = children[int(np.flatnonzero(chit >= 0)[0])]
    novelty_used = sim.used
    sim.budget = evals
    if found is None:
        genome, reached = _hill_refine(np, rng, sim, best[0], best[1], best[2])
        found = genome
    out = _maze_answer(rows, start, goal, found)
    return answer(out, {"method": f"novelty search: (mu + lambda) on novelty, mu = lambda = {NS_POPULATION}, "
                                  f"k {NS_K}, mutation {NS_MUTATION}/L genes, adaptive archive threshold; then "
                                  f"(1+1) hill climbing on the objective with the remaining budget",
                        "behaviour_descriptor": "final cell", "objective": "Manhattan distance to the goal",
                        "evaluations_used": sim.used, "evaluation_budget": evals,
                        "novelty_evaluations": novelty_used, "generations": generations,
                        "archive_size": int(min(added_total, NS_ARCHIVE_MAX)), "optimality": "not claimed"})


def ns_verify(data, output, certificate):
    rows, start, goal, length, evals, seed = _maze(data)
    if (not isinstance(output, dict) or set(output) != {"moves", "final", "reached_at"}
            or not isinstance(output["moves"], str) or not isinstance(output["final"], list)
            or type(output["reached_at"]) is not int):
        return {"output_shape": False}
    moves = output["moves"]
    program = len(moves) == length and set(moves) <= set(MOVES)
    if not program:
        return {"output_shape": True, "moves_are_a_full_program": False, "replay_matches": False}
    final, step = _replay(rows, start, goal, moves)
    used = _cert(certificate).get("evaluations_used")
    return {"output_shape": True, "moves_are_a_full_program": True,
            "replay_matches": final == output["final"] and step == output["reached_at"],
            "within_the_evaluation_budget": type(used) is int and 1 <= used <= evals}


def _distance_field(rows, goal):
    """Exact maze distance of every free cell to the goal by NetworkX BFS (truth side, independent of every arm)."""
    import networkx as nx
    g = nx.grid_2d_graph(len(rows), len(rows[0]))
    g.remove_nodes_from([(r, c) for r in range(len(rows)) for c in range(len(rows[0])) if rows[r][c] == "#"])
    lengths = nx.single_source_shortest_path_length(g, goal)
    return [[lengths.get((r, c), -1) for c in range(len(rows[0]))] for r in range(len(rows))]


def _carve_maze(r, kind):
    """A grid maze of one declared kind; returns (rows, start, goal) or None when disconnected."""
    if kind == "cup":
        h, w = r.choice(((17, 17), (21, 21), (23, 27)))
        g = [["." for _ in range(w)] for _ in range(h)]
        gr, gc = h // 3, w // 2
        half = r.randint(4, 6)
        for c in range(gc - half, gc + half + 1):            # bottom of the cup, between start and goal
            g[gr + half][c] = "#"
        for rr in range(gr - half + 2, gr + half + 1):        # two walls; the cup opens upward, away from start
            g[rr][gc - half] = "#"
            g[rr][gc + half] = "#"
        start, goal = (h - 2, gc + r.randint(-2, 2)), (gr, gc)     # straight below: the objective leads into the cup
        density = 0.05
    elif kind == "comb":
        h, w = r.choice(((17, 17), (21, 21), (23, 27)))
        g = [["." for _ in range(w)] for _ in range(h)]
        wall = h // 2
        gap_left = r.random() < 0.5
        for c in range(w):                                   # one long wall with a gap at one far end
            if (gap_left and c <= 1) or (not gap_left and c >= w - 2):
                continue
            g[wall][c] = "#"
        gc = w // 2 + r.randint(-2, 2)
        for rr in range(wall + 1, wall + 5):                 # a dead-end pocket just under the goal
            g[rr][gc - 2] = "#"
            g[rr][gc + 2] = "#"
        start, goal = (h - 2, gc), (wall - 2, gc)
        density = 0.04
    elif kind == "rooms":
        h, w = r.choice(((17, 17), (21, 21), (25, 25)))
        g = [["." for _ in range(w)] for _ in range(h)]
        for k in range(4, h - 1, 4):
            for c in range(w):
                g[k][c] = "#"
            for door in r.sample(range(1, w - 1), 2):
                g[k][door] = "."
        start, goal = (h - 2, r.randint(1, w - 2)), (1, r.randint(1, w - 2))
        density = 0.03
    else:                                                    # scatter: random obstacles, no designed trap
        h, w = r.choice(((15, 15), (19, 19), (21, 25)))
        g = [["." for _ in range(w)] for _ in range(h)]
        start, goal = (h - 2, 1), (1, w - 2)
        density = 0.18
    for rr in range(h):
        for c in range(w):
            if g[rr][c] == "." and (rr, c) not in (start, goal) and r.random() < density:
                g[rr][c] = "#"
    rows = ["".join(row) for row in g]
    field = _distance_field(rows, goal)
    if field[start[0]][start[1]] < 0:
        return None
    return rows, start, goal


def ns_instance(seed):
    r = random.Random(f"genome:evo_novelty_search:{seed}")
    kind = MZ_KINDS[seed % 4]
    built = None
    while built is None:
        built = _carve_maze(r, kind)
    rows, start, goal = built
    field = _distance_field(rows, goal)
    shortest = field[start[0]][start[1]]
    length = min(MZ_MAX_LENGTH, int(math.ceil(1.5 * shortest)) + 4)
    data = {"maze": rows, "start": list(start), "goal": list(goal), "genome_length": length,
            "evaluations": MZ_EVALS_PER_STEP * length, "seed": r.randrange(2**31)}
    manhattan = abs(start[0] - goal[0]) + abs(start[1] - goal[1])
    return data, {"kind": kind, "shortest_path": shortest, "manhattan": manhattan, "distance_field": field}


def ns_subregion(data):
    """``deceptive`` when the shortest path is at least 1.5 x the Manhattan distance the objective follows (the
    declared deceptive geometry), else ``direct``; computed by an independent BFS on the input."""
    rows, start, goal, length, evals, seed = _maze(data)
    field = _distance_field(rows, goal)
    manhattan = abs(start[0] - goal[0]) + abs(start[1] - goal[1])
    return "deceptive" if field[start[0]][start[1]] >= 1.5 * manhattan else "direct"


def ns_score(data, truth, output):
    if not isinstance(output, dict) or not isinstance(output.get("moves"), str):
        return {"quality": 0.0, "category": "abstain"}
    rows, start, goal, length, evals, seed = _maze(data)
    moves = output["moves"]
    if len(moves) != length or not set(moves) <= set(MOVES):
        return {"quality": -1.0, "category": "wrong"}
    final, step = _replay(rows, start, goal, moves)
    if final != output.get("final") or step != output.get("reached_at"):
        return {"quality": -1.0, "category": "wrong"}       # a false claim about where the program ends
    if step >= 0:
        return {"quality": 1.0, "category": "correct"}
    remaining = truth["distance_field"][final[0]][final[1]]
    return {"quality": max(0.0, 1.0 - remaining / truth["shortest_path"]) * 0.999, "category": "correct"}


def ns_hill_climb(data):
    """Baseline: objective-driven (1+1) hill climbing on the Manhattan distance (accept equal or better), restarting
    from a random program after HC_PATIENCE evaluations without improvement; same mutation, same budget."""
    import numpy as np
    rows, start, goal, length, evals, seed = _maze(data)
    rng = np.random.default_rng(seed)
    sim = _Sim(rows, start, goal, length, evals)
    best_overall = None
    while sim.used < sim.budget:
        cur, cell, hit = sim(rng.integers(0, 4, (1, length)))
        if not len(cur):
            break
        cur, obj, reached, since = cur[0], int(sim.objective(cell)[0]), int(hit[0]), 0
        while reached < 0 and since < HC_PATIENCE and sim.used < sim.budget:
            child, ccell, chit = sim(_mutate(np, rng, cur[None], length))
            cobj = int(sim.objective(ccell)[0])
            since += 1
            if chit[0] >= 0 or cobj <= obj:
                if cobj < obj:
                    since = 0
                cur, obj, reached = child[0], cobj, int(chit[0])
        if best_overall is None or (reached >= 0) > (best_overall[2] >= 0) or (
                (reached >= 0) == (best_overall[2] >= 0) and obj < best_overall[1]):
            best_overall = (cur, obj, reached)
        if reached >= 0:
            break
    return _maze_answer(rows, start, goal, best_overall[0])


def ns_map_elites(data):
    """Competitor: MAP-Elites with the same behaviour descriptor (one elite per final cell, quality = minus the
    Manhattan objective), NS_POPULATION random programs first, then uniform elite selection with the same mutation,
    same budget; returns a goal-reaching elite, else the elite with the best objective."""
    import numpy as np
    rows, start, goal, length, evals, seed = _maze(data)
    rng = np.random.default_rng(seed)
    sim = _Sim(rows, start, goal, length, evals)
    elites = {}

    def insert(genomes, cells, hits):
        objs = sim.objective(cells)
        for g, cell, h, o in zip(genomes, cells, hits, objs):
            key = (int(cell[0]), int(cell[1]))
            if key not in elites or o < elites[key][1]:
                elites[key] = (g, int(o), int(h))
        return any(h >= 0 for h in hits)
    done = insert(*sim(rng.integers(0, 4, (min(NS_POPULATION, evals), length))))
    while not done and sim.used < sim.budget:
        keys = list(elites)
        picks = rng.integers(0, len(keys), NS_POPULATION)
        parents = np.stack([elites[keys[i]][0] for i in picks])
        kept, cells, hits = sim(_mutate(np, rng, parents, length))
        if not len(kept):
            break
        done = insert(kept, cells, hits)
    best = min(elites.values(), key=lambda e: (e[2] < 0, e[1]))
    return _maze_answer(rows, start, goal, best[0])


# =================================================================== 2. selection hyper-heuristic, bin packing
HH_MAX_ITEMS, HH_MAX_SIZE, HH_MAX_APPLICATIONS = 2000, 1_000_000, 50_000
HH_LLH = ("drain_first_fit", "drain_best_fit", "ruin_recreate_ffd", "swap_fill", "move_fill")
HH_UCB_C = math.sqrt(2.0)
HH_COMPETITOR = "random_selection"      # fixed from dev seeds 0-9 (notes): the stronger of the two declared rivals


def _packing(data):
    data = _mapping(data)
    cap = bounded_int(data.get("bin_capacity"), low=1, high=HH_MAX_SIZE, name="bin_capacity")
    sizes = data.get("item_sizes")
    if (not isinstance(sizes, list) or not 1 <= len(sizes) <= HH_MAX_ITEMS
            or not all(type(s) is int and 1 <= s <= cap for s in sizes)):
        raise GenomeError(f"item_sizes: 1-{HH_MAX_ITEMS} integers in [1, bin_capacity]")
    apps = bounded_int(data.get("heuristic_applications"), low=0, high=HH_MAX_APPLICATIONS,
                       name="heuristic_applications")
    seed = bounded_int(data.get("seed"), low=0, high=2**31 - 1, name="seed")
    return sizes, cap, apps, seed


def _ffd(sizes, cap):
    order = sorted(range(len(sizes)), key=lambda i: (-sizes[i], i))
    bins, loads = [], []
    for i in order:
        for b, load in enumerate(loads):
            if load + sizes[i] <= cap:
                bins[b].append(i)
                loads[b] += sizes[i]
                break
        else:
            bins.append([i])
            loads.append(sizes[i])
    return bins


def _canonical(bins):
    packed = sorted(sorted(b) for b in bins if b)
    return {"bins": len(packed), "packing": packed}


class _Packing:
    """A packing with its loads and lexicographic objective (fewer bins, then larger sum of squared loads)."""

    def __init__(self, sizes, cap, bins):
        self.sizes, self.cap = sizes, cap
        self.bins = [list(b) for b in bins]
        self.loads = [sum(sizes[i] for i in b) for b in self.bins]

    def copy(self):
        other = _Packing.__new__(_Packing)
        other.sizes, other.cap = self.sizes, self.cap
        other.bins = [list(b) for b in self.bins]
        other.loads = list(self.loads)
        return other

    def key(self):
        return (len(self.bins), -sum(x * x for x in self.loads))

    def drop_empty(self):
        keep = [k for k, b in enumerate(self.bins) if b]
        self.bins = [self.bins[k] for k in keep]
        self.loads = [self.loads[k] for k in keep]

    def insert(self, items, best_fit):
        for i in sorted(items, key=lambda j: (-self.sizes[j], j)):
            s, target = self.sizes[i], None
            for b, load in enumerate(self.loads):
                if load + s <= self.cap and (target is None or (best_fit and load > self.loads[target])):
                    target = b
                    if not best_fit:
                        break
            if target is None:
                self.bins.append([i])
                self.loads.append(s)
            else:
                self.bins[target].append(i)
                self.loads[target] += s


def _low_bins(p, rng, share=0.3):
    order = sorted(range(len(p.bins)), key=lambda b: (p.loads[b], b))
    return order[:max(1, int(len(order) * share))]


def _llh(name, p, rng):
    """Apply one low-level heuristic to a copy of ``p``; returns the new packing."""
    q = p.copy()
    if len(q.bins) < 2:
        return q
    if name in ("drain_first_fit", "drain_best_fit"):
        b = rng.choice(_low_bins(q, rng, 0.1) if len(q.bins) >= 10 else _low_bins(q, rng, 0.5))
        items = q.bins[b]
        q.bins[b], q.loads[b] = [], 0
        q.drop_empty()
        q.insert(items, best_fit=name == "drain_best_fit")
    elif name == "ruin_recreate_ffd":
        k = max(2, int(round(0.05 * len(q.bins))))
        pool = _low_bins(q, rng, 0.3)
        chosen = rng.sample(pool, min(k, len(pool))) if len(pool) >= 2 else rng.sample(range(len(q.bins)), 2)
        items = [i for b in chosen for i in q.bins[b]]
        for b in chosen:
            q.bins[b], q.loads[b] = [], 0
        q.drop_empty()
        q.insert(items, best_fit=True)
    elif name == "swap_fill":
        a, b = rng.sample(range(len(q.bins)), 2)
        full, low = (a, b) if q.loads[a] >= q.loads[b] else (b, a)
        best = None
        for x in q.bins[full]:
            for y in q.bins[low]:
                gain = q.sizes[y] - q.sizes[x]
                if gain > 0 and q.loads[full] + gain <= q.cap and (best is None or gain > best[0]):
                    best = (gain, x, y)
        if best is not None:
            gain, x, y = best
            q.bins[full].remove(x)
            q.bins[full].append(y)
            q.bins[low].remove(y)
            q.bins[low].append(x)
            q.loads[full] += gain
            q.loads[low] -= gain
    else:                                                   # move_fill
        src = rng.choice(_low_bins(q, rng, 0.5))
        item = rng.choice(q.bins[src])
        s, target = q.sizes[item], None
        for b, load in enumerate(q.loads):
            if b != src and load + s <= q.cap and load >= q.loads[src] and (target is None or load > q.loads[target]):
                target = b
        if target is not None:
            q.bins[src].remove(item)
            q.loads[src] -= s
            q.bins[target].append(item)
            q.loads[target] += s
            q.drop_empty()
    return q


def _hyper(sizes, cap, apps, seed, policy):
    """Run a selection policy ('ucb1', 'random' or one LLH name) from the FFD packing for ``apps`` applications with
    non-worsening acceptance. Returns (packing, per-heuristic statistics)."""
    rng = random.Random(seed)
    p = _Packing(sizes, cap, _ffd(sizes, cap))
    lower = -(-sum(sizes) // cap)
    counts, rewards = {h: 0 for h in HH_LLH}, {h: 0.0 for h in HH_LLH}
    for t in range(1, apps + 1):
        if len(p.bins) <= lower:
            break                                           # the volume bound is met: no heuristic can improve
        if policy == "ucb1":
            untried = [h for h in HH_LLH if counts[h] == 0]
            h = untried[0] if untried else max(
                HH_LLH, key=lambda x: rewards[x] / counts[x] + HH_UCB_C * math.sqrt(math.log(t) / counts[x]))
        elif policy == "random":
            h = rng.choice(HH_LLH)
        else:
            h = policy
        q = _llh(h, p, rng)
        counts[h] += 1
        if q.key() < p.key():
            rewards[h] += 1.0
        if q.key() <= p.key():
            p = q
    return p, counts, rewards


def hh_solve(data, budget):
    sizes, cap, apps, seed = _packing(data)
    p, counts, rewards = _hyper(sizes, cap, apps, seed, "ucb1")
    out = _canonical(p.bins)
    return answer(out, {"method": "selection hyper-heuristic: UCB1 (c = sqrt 2, reward 1 on strict improvement of "
                                  "(bins, -sum of squared loads)) over " + ", ".join(HH_LLH) +
                                  "; start from first-fit decreasing; accept non-worsening moves",
                        "applications_used": sum(counts.values()), "application_budget": apps,
                        "selections": counts, "improvements": {h: int(v) for h, v in rewards.items()},
                        "volume_lower_bound": -(-sum(sizes) // cap), "optimality": "not claimed"})


def hh_verify(data, output, certificate):
    sizes, cap, apps, seed = _packing(data)
    if (not isinstance(output, dict) or set(output) != {"bins", "packing"} or type(output["bins"]) is not int
            or not isinstance(output["packing"], list)
            or not all(isinstance(b, list) and b and all(type(i) is int for i in b) for b in output["packing"])):
        return {"output_shape": False}
    packing = output["packing"]
    seen = [0] * len(sizes)
    in_range = True
    for b in packing:
        for i in b:
            if 0 <= i < len(sizes):
                seen[i] += 1
            else:
                in_range = False
    loads = [math.fsum(sizes[i] for i in b if 0 <= i < len(sizes)) for b in packing]
    used = _cert(certificate).get("applications_used")
    return {"output_shape": True,
            "every_item_packed_exactly_once": in_range and all(c == 1 for c in seen),
            "loads_within_capacity": all(x <= cap for x in loads),
            "bin_count_recounted": output["bins"] == len(packing),
            "canonical_order": packing == sorted(sorted(b) for b in packing),
            "not_below_the_volume_bound": len(packing) * cap >= sum(sizes),
            "within_the_application_budget": type(used) is int and 0 <= used <= apps}


def _planted_bins(r, cap, kind):
    if kind == "triplet":
        a = r.randint(int(0.38 * cap), int(0.49 * cap))
        b = r.randint(int(0.25 * cap) + 1, cap - a - int(0.25 * cap) - 1)
        return [a, b, cap - a - b]
    pieces = r.randint(3, 7)
    cuts = sorted(r.sample(range(1, cap), pieces - 1))
    return [y - x for x, y in zip([0] + cuts, cuts + [cap])]


def hh_instance(seed):
    r = random.Random(f"genome:hyper_select_lowlevel:{seed}")
    kind = ("triplet", "cuts", "mixed", "triplet")[seed % 4]
    cap = r.choice((1000, 1000, 600))
    m = r.randint(40, 160) if kind != "triplet" else r.randint(60, 200)
    sizes = []
    for k in range(m):
        sizes += _planted_bins(r, cap, "triplet" if kind == "triplet" or (kind == "mixed" and k % 2) else "cuts")
    r.shuffle(sizes)
    sizes = sizes[:HH_MAX_ITEMS]
    data = {"item_sizes": sizes, "bin_capacity": cap, "heuristic_applications": 5 * len(sizes),
            "seed": r.randrange(2**31)}
    assert sum(sizes) == m * cap
    return data, {"kind": kind, "optimum": m, "volume_lower_bound": m}


def hh_subregion(data):
    sizes, cap, apps, seed = _packing(data)
    triplet = all(cap / 4 < s < cap / 2 for s in sizes)
    return ("triplet" if triplet else "mixed_sizes") + ("_large" if len(sizes) > 400 else "_medium")


def hh_score(data, truth, output):
    if not isinstance(output, dict) or "packing" not in output:
        return {"quality": 0.0, "category": "abstain"}
    sizes, cap, apps, seed = _packing(data)
    checks = hh_verify(data, output, {"applications_used": 0})
    if not all(checks.values()):
        return {"quality": -1.0, "category": "wrong"}
    return {"quality": truth["optimum"] / output["bins"], "category": "correct"}


def hh_ffd(data):
    """Baseline: first-fit decreasing alone."""
    sizes, cap, apps, seed = _packing(data)
    return _canonical(_ffd(sizes, cap))


def hh_random(data):
    """Random-selection hyper-heuristic: the same pool, start and acceptance, a uniformly random heuristic per
    application, the same budget."""
    sizes, cap, apps, seed = _packing(data)
    return _canonical(_hyper(sizes, cap, apps, seed, "random")[0].bins)


def hh_best_single(data):
    """The best single low-level heuristic on dev seeds 0-9 (ruin-and-recreate, see notes) for the whole budget."""
    sizes, cap, apps, seed = _packing(data)
    return _canonical(_hyper(sizes, cap, apps, seed, "ruin_recreate_ffd")[0].bins)


HH_COMPETITORS = {"random_selection": hh_random, "best_single_llh": hh_best_single}


def hh_competitor(data):
    return HH_COMPETITORS[HH_COMPETITOR](data)


# =================================================================== 3. role differentiation by local inhibition
DF_MAX_NODES, DF_MAX_EDGES, DF_MAX_RADIUS, DF_MAX_PHASES = 800, 20_000, 3, 200
ROLES = ("leader", "member")
DF_KINDS = ("geometric", "small_world", "grid_holes", "dense_random")


def _role_graph(data):
    data = _mapping(data)
    n = bounded_int(data.get("num_nodes"), low=1, high=DF_MAX_NODES, name="num_nodes")
    edges = data.get("edges")
    if not isinstance(edges, list) or len(edges) > DF_MAX_EDGES:
        raise GenomeError(f"edges: at most {DF_MAX_EDGES} [u, v] pairs")
    adj = [set() for _ in range(n)]
    for e in edges:
        if (not isinstance(e, list) or len(e) != 2 or not all(type(x) is int and 0 <= x < n for x in e)
                or e[0] == e[1]):
            raise GenomeError("edge: [u, v], distinct node indices below num_nodes")
        adj[e[0]].add(e[1])
        adj[e[1]].add(e[0])
    radius = bounded_int(data.get("radius"), low=1, high=DF_MAX_RADIUS, name="radius")
    phases = bounded_int(data.get("max_phases"), low=1, high=DF_MAX_PHASES, name="max_phases")
    seed = bounded_int(data.get("seed"), low=0, high=2**31 - 1, name="seed")
    return n, adj, radius, phases, seed


def _priority(seed, phase, node):
    """The declared priority rule: the first 64 bits of SHA-256 of 'seed:phase:node' (ties broken by node id)."""
    return int.from_bytes(hashlib.sha256(f"{seed}:{phase}:{node}".encode()).digest()[:8], "big")


def _ball(adj, v, radius):
    """Nodes within ``radius`` hops of v, v excluded (solver side: a relayed neighbourhood)."""
    seen, frontier = {v}, [v]
    for _ in range(radius):
        nxt = []
        for u in frontier:
            for w in adj[u]:
                if w not in seen:
                    seen.add(w)
                    nxt.append(w)
        frontier = nxt
    seen.discard(v)
    return seen


def df_solve(data, budget):
    """Local message passing: each phase is two exchanges with the radius-d neighbourhood (priorities, then
    inhibition), each exchange relayed over d hops, so a phase costs 2d rounds of the LOCAL model."""
    n, adj, radius, max_phases, seed = _role_graph(data)
    ball = [_ball(adj, v, radius) for v in range(n)]
    state = ["undecided"] * n
    phase = 0
    while "undecided" in state:
        if phase >= max_phases:
            return _unknown(f"no stable role pattern within {max_phases} phases", phases=phase)
        phase += 1
        inbox = {v: [] for v in range(n) if state[v] == "undecided"}
        for v in inbox:                                     # exchange 1: undecided nodes send their priority
            message = (_priority(seed, phase, v), v)
            for u in ball[v]:
                if u in inbox:
                    inbox[u].append(message)
        new_leaders = [v for v, msgs in inbox.items()
                       if all((_priority(seed, phase, v), v) > m for m in msgs)]
        for v in new_leaders:
            state[v] = "leader"
        for v in new_leaders:                               # exchange 2: new leaders inhibit their neighbourhood
            for u in ball[v]:
                if state[u] == "undecided":
                    state[u] = "member"
    out = {"roles": state, "phases": phase, "rounds": 2 * radius * phase}
    return answer(out, {"method": "phased lateral inhibition: an undecided node whose (priority, id) beats every "
                                  "undecided node within the radius becomes a leader and inhibits them to members",
                        "priority_rule": "SHA-256('seed:phase:node') first 64 bits, ties by node id",
                        "round_model": "LOCAL; one exchange over radius d costs d rounds; two exchanges per phase",
                        "leaders": state.count("leader"), "max_phases": max_phases})


def _within(np, n, adj, radius):
    """Boolean (n, n) reachability within ``radius`` hops, self included (verifier side, matrix powers)."""
    a = np.eye(n, dtype=bool)
    for v in range(n):
        for u in adj[v]:
            a[v, u] = True
    reach = a.copy()
    for _ in range(radius - 1):
        reach = (reach.astype(np.int32) @ a.astype(np.int32)) > 0
    return reach


def _replay_rule(np, n, reach, seed, max_phases):
    """Vectorised recomputation of the declared rule: (roles as 1 leader / 0 member, phases) or None."""
    near = reach & ~np.eye(n, dtype=bool)
    undecided = np.ones(n, dtype=bool)
    leader = np.zeros(n, dtype=bool)
    ids = np.arange(n)
    phase = 0
    while undecided.any():
        if phase >= max_phases:
            return None
        phase += 1
        prio = np.array([int.from_bytes(hashlib.sha256(("%d:%d:%d" % (seed, phase, v)).encode()).digest()[:8],
                                        "big") for v in range(n)], dtype=object)
        win = np.zeros(n, dtype=bool)
        for v in np.flatnonzero(undecided):
            rivals = np.flatnonzero(near[v] & undecided)
            win[v] = all((prio[v], v) > (prio[u], ids[u]) for u in rivals)
        leader |= win
        undecided &= ~win
        undecided &= ~(near[win].any(0) if win.any() else np.zeros(n, dtype=bool))
    return leader, phase


def df_verify(data, output, certificate):
    import numpy as np
    n, adj, radius, max_phases, seed = _role_graph(data)
    if (not isinstance(output, dict) or set(output) != {"roles", "phases", "rounds"}
            or not isinstance(output["roles"], list) or type(output["phases"]) is not int
            or type(output["rounds"]) is not int):
        return {"output_shape": False}
    roles = output["roles"]
    if len(roles) != n or not all(isinstance(x, str) and x in ROLES for x in roles):
        return {"output_shape": True, "one_role_per_node": False, "pattern_holds": False}
    reach = _within(np, n, adj, radius)
    lead = np.array([x == "leader" for x in roles])
    near = reach & ~np.eye(n, dtype=bool)
    replay = _replay_rule(np, n, reach, seed, max_phases)
    return {"output_shape": True, "one_role_per_node": True,
            "leaders_more_than_radius_apart": not (near[lead][:, lead]).any(),
            "every_member_within_radius_of_a_leader": bool(reach[:, lead].any(1).all()),
            "roles_follow_the_declared_local_rule": replay is not None and bool((replay[0] == lead).all()),
            "phases_recomputed": replay is not None and replay[1] == output["phases"],
            "rounds_recomputed": output["rounds"] == 2 * radius * output["phases"]}


def _pattern_ok(n, edges, radius, roles):
    """Independent pattern check by NetworkX bounded BFS (score side)."""
    import networkx as nx
    g = nx.Graph()
    g.add_nodes_from(range(n))
    g.add_edges_from(map(tuple, edges))
    leaders = {v for v, x in enumerate(roles) if x == "leader"}
    for v in range(n):
        near = set(nx.single_source_shortest_path_length(g, v, cutoff=radius)) - {v}
        if v in leaders and near & leaders:
            return False
        if v not in leaders and not near & leaders:
            return False
    return True


def _centre_rounds(n, edges):
    """Rounds a centralised method needs in the LOCAL model: gather the topology at a centre of each component
    (its radius in rounds) and broadcast the roles back (the same again)."""
    import networkx as nx
    g = nx.Graph()
    g.add_nodes_from(range(n))
    g.add_edges_from(map(tuple, edges))
    return 2 * max(nx.radius(g.subgraph(c)) for c in nx.connected_components(g))


def df_instance(seed):
    import networkx as nx
    r = random.Random(f"genome:develop_differentiate:{seed}")
    kind = DF_KINDS[seed % 4]
    gseed = r.randrange(2**31)
    if kind == "geometric":
        n = r.randint(120, 400)
        g = nx.random_geometric_graph(n, math.sqrt(8.0 / (math.pi * n)), seed=gseed)
    elif kind == "small_world":
        n = r.randint(120, 400)
        g = nx.connected_watts_strogatz_graph(n, 6, 0.2, seed=gseed)
    elif kind == "grid_holes":
        side = r.randint(10, 18)
        g = nx.convert_node_labels_to_integers(nx.grid_2d_graph(side, side))
        g.remove_nodes_from([v for v in list(g) if r.random() < 0.1])
        g = nx.convert_node_labels_to_integers(g)
        n = g.number_of_nodes()
    else:
        n = r.randint(100, 300)
        g = nx.gnp_random_graph(n, 12.0 / n, seed=gseed)
    edges = sorted([min(u, v), max(u, v)] for u, v in g.edges())
    radius = 1 if r.random() < 0.6 else 2
    data = {"num_nodes": n, "edges": edges, "radius": radius, "max_phases": 64, "seed": r.randrange(2**31)}
    return data, {"kind": kind, "min_leaders": _min_leaders(n, edges, radius),
                  "centralised_rounds": _centre_rounds(n, edges)}


def _min_leaders(n, edges, radius):
    """CP-SAT minimum number of leaders over all role assignments satisfying the pattern (a minimum independent
    dominating set of the radius-th power graph): a feasibility witness and reference optimum, or None if not proven
    within the time limit. Truth side only."""
    import networkx as nx
    from ortools.sat.python import cp_model
    g = nx.Graph()
    g.add_nodes_from(range(n))
    g.add_edges_from(map(tuple, edges))
    p = nx.power(g, radius) if radius > 1 else g
    m = cp_model.CpModel()
    x = [m.NewBoolVar(f"x{v}") for v in range(n)]
    for u, v in p.edges():
        m.AddBoolOr([x[u].Not(), x[v].Not()])
    for v in range(n):
        m.AddBoolOr([x[v]] + [x[u] for u in p[v]])
    m.Minimize(sum(x))
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = 5.0
    status = solver.Solve(m)
    if status == cp_model.OPTIMAL:
        return int(solver.ObjectiveValue())
    return None


def df_subregion(data):
    n, adj, radius, max_phases, seed = _role_graph(data)
    edges = [[u, v] for u in range(n) for v in adj[u] if u < v]
    high = _centre_rounds(n, edges) > 2 * radius * max(1, math.ceil(math.log2(max(2, n))))
    return ("high_diameter" if high else "low_diameter") + f"_r{radius}"


def df_score(data, truth, output):
    if not isinstance(output, dict) or not isinstance(output.get("roles"), list):
        return {"quality": 0.0, "category": "abstain"}
    n, adj, radius, max_phases, seed = _role_graph(data)
    roles, rounds = output["roles"], output.get("rounds")
    if (len(roles) != n or not all(isinstance(x, str) and x in ROLES for x in roles)
            or type(rounds) is not int or rounds < 0 or not _pattern_ok(n, data["edges"], radius, roles)):
        return {"quality": -1.0, "category": "wrong"}
    return {"quality": 1.0 / (1.0 + rounds), "category": "correct"}


def df_random(data):
    """Baseline: random roles with no communication (leader with probability 1 / (1 + mean radius-d degree))."""
    n, adj, radius, max_phases, seed = _role_graph(data)
    rng = random.Random(seed)
    mean = sum(len(_ball(adj, v, radius)) for v in range(n)) / n
    return {"roles": ["leader" if rng.random() < 1.0 / (1.0 + mean) else "member" for _ in range(n)],
            "phases": 0, "rounds": 0}


def df_centralised(data):
    """Competitor: a centralised greedy maximal independent set of the radius-th power graph (NetworkX), charged the
    LOCAL-model rounds to gather the topology at each component's centre and broadcast the roles back."""
    import networkx as nx
    n, adj, radius, max_phases, seed = _role_graph(data)
    g = nx.Graph()
    g.add_nodes_from(range(n))
    g.add_edges_from((u, v) for u in range(n) for v in adj[u] if u < v)
    p = nx.power(g, radius) if radius > 1 else g
    leaders = set(nx.maximal_independent_set(p, seed=seed))
    edges = [[u, v] for u, v in g.edges()]
    return {"roles": ["leader" if v in leaders else "member" for v in range(n)], "phases": 1,
            "rounds": _centre_rounds(n, edges)}


# =================================================================== registration
INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.evolutionary.novelty_search", version="1.0.0", family="evo_novelty_search",
            layer=3, operation="deceptive_maze_navigate", epistemic_class="optimization",
            subgeometry="find a fixed-length move program reaching a goal cell, using only a simulator and a declared "
                        "objective (Manhattan distance of the final cell to the goal) that is deceptive when the "
                        "shortest path is at least 1.5x the Manhattan distance (subregion 'deceptive')",
            source_provenance="Lehman and Stanley (2011) novelty search and the deceptive-maze benchmark; Gomes, "
                              "Mariano and Christensen (2015) (mu + lambda) novelty survival; Mouret and "
                              "Clune (2015) MAP-Elites as the competitor; implemented on NumPy (no novelty-search or "
                              "QD library is installed); NetworkX BFS for the truth",
            native_representation="grid maze rows of '#' and '.', start and goal cells, program length, evaluation "
                                  "budget, seed",
            required_inputs=("maze", "start", "goal", "genome_length", "evaluations", "seed"),
            output_contract={"moves": "str over UDLR, exactly genome_length", "final": "[row, col]",
                             "reached_at": "int step at which the goal was first reached, or -1"},
            algorithm_or_runtime=f"novelty search: (mu + lambda) survival on novelty, mu = lambda = {NS_POPULATION}, "
                                 f"novelty = mean distance of the final cell to its {NS_K} nearest among parents, "
                                 f"children and archive, uniform parents, mutation {NS_MUTATION}/L genes, adaptive "
                                 f"archive threshold, stop on the goal; the last {int(NS_REFINE_SHARE * 100)}% of the budget refines the best "
                                 "objective by (1+1) hill climbing",
            parameters={"population": NS_POPULATION, "k_nearest": NS_K, "mutation_genes": NS_MUTATION,
                        "refine_share": NS_REFINE_SHARE, "rho0": NS_RHO0, "archive_max": NS_ARCHIVE_MAX},
            composition_inputs=("a simulator with a behaviour descriptor", "a deceptive objective"),
            composition_outputs=("a program", "where it ends", "whether it reached the goal"),
            evidence_type="heuristic_trace",
            verification_method="the moves replayed from the start by independent pure-Python code (walls stop the "
                                "agent, the episode ends at the goal); the final cell and the goal step must match; "
                                "the program must have exactly the declared length; evaluations within the budget",
            confidence_semantics="the program ends exactly where it says and reaches the goal exactly when it says; "
                                 "no claim that a shorter or better program does not exist",
            resource_profile="exactly the declared evaluation budget (400 per program step on the benchmark); "
                             "novelty is O(population x (population + archive)) per generation",
            latency_profile="tens to hundreds of milliseconds at benchmark size",
            known_strengths=("ignores the objective while exploring, so a dead end that attracts the objective does "
                             "not trap it (deceptive geometry)",
                             "needs only a simulator and a behaviour descriptor"),
            known_failure_modes=("the map is in the input here: BFS on it solves every instance exactly and is used "
                                 "as the truth, not as an arm; this genome is for the black-box geometry, where only a "
                                 "simulator exists, and on an explicit map it is dominated by BFS",
                                 "MAP-Elites over the same behaviour descriptor keeps one elite per final cell, which "
                                 "is itself a complete novelty archive on a grid; it can tie or beat novelty search",
                                 "on direct (non-deceptive) mazes objective hill climbing is as good and cheaper",
                                 "the behaviour descriptor (final cell) is chosen by the caller; a poor descriptor "
                                 "makes novelty search a random walk",
                                 "no optimality guarantee"),
            counterindications=("an explicit map or graph is available (use BFS / Dijkstra / A*)",
                                "a non-deceptive objective (use hill climbing)",
                                "no meaningful behaviour descriptor"),
            abstention_conditions=("none beyond malformed input: an answer is always a replayable program",),
            benchmark_suite="grid mazes 15x15 to 25x27 of four declared kinds (cup trap and comb with dead-end pocket: "
                            "deceptive by design; rooms; scattered obstacles), program length 1.5x the shortest path "
                            "+ 4, 400 evaluations per program step; quality 1 when the goal is reached, else 0.999 x "
                            "(1 - remaining BFS distance / shortest path); seeds 0-9 dev, held-out seeds fixed by the "
                            "admission freeze",
            baseline="objective-driven (1+1) hill climbing on the Manhattan distance with restarts after 200 "
                     "evaluations without improvement; same mutation and budget",
            competitor="MAP-Elites with the same behaviour descriptor (one elite per final cell, quality minus the "
                       "Manhattan objective), uniform elite selection, same mutation and budget", dependency=None,
            **_common()),
        solve=ns_solve, verify=ns_verify, instance=ns_instance, score=ns_score, baseline=ns_hill_climb,
        competitor=ns_map_elites, subregion=ns_subregion, tolerance=1e-9,
        notes={"competitor_choice": "the brief allowed the factored GA or MAP-Elites; MAP-Elites over the same "
                                    "behaviour descriptor is the stronger rival here (the GA's objective-driven "
                                    "selection is trapped exactly as hill climbing is)",
               "variant_choice": "dev seeds 0-9 only: a generational variant (binary tournament on novelty, no "
                                 "survival of parents) lost its stepping stones and ended in the cup or comb trap on "
                                 "5 of 7 deceptive mazes; (mu + lambda) novelty survival (Gomes et al. 2015) replaced "
                                 "it before any held-out seed existed. Negative result kept here"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.hyperheuristic.selection_ucb_binpack", version="1.0.0",
            family="hyper_select_lowlevel", layer=3, operation="bin_packing_hyperheuristic",
            epistemic_class="optimization",
            subgeometry="anytime one-dimensional bin packing of more items than the exact model handles natively "
                        "(120-1000 here; binpack_cpsat abstains above 150), under a budget of low-level heuristic "
                        "applications; distinct from bin_packing_min_bins, which proves the minimum",
            source_provenance="Burke et al. (2013) hyper-heuristic survey; Auer et al. (2002) UCB1; Fialho et al. "
                              "(2010) bandit operator selection; Falkenauer (1996) triplets and the sum-of-squares "
                              "fill measure; Johnson (1973) first-fit decreasing; pure Python",
            native_representation="item sizes, one bin capacity (integers), heuristic-application budget, seed",
            required_inputs=("item_sizes", "bin_capacity", "heuristic_applications", "seed"),
            output_contract={"bins": "int", "packing": "[[item index]] canonical (sorted bins, sorted by first)"},
            algorithm_or_runtime="start from first-fit decreasing; per application choose a low-level heuristic by "
                                 "UCB1 (reward 1 on a strict improvement of (bins, -sum of squared loads)), apply it to "
                                 "a copy, accept if not worse; stop at the budget or the volume bound",
            parameters={"low_level_heuristics": list(HH_LLH), "ucb_c": HH_UCB_C, "acceptance": "non-worsening",
                        "start": "first-fit decreasing"},
            composition_inputs=("job or file sizes", "worker or container capacity"),
            composition_outputs=("a packing", "number of bins"),
            evidence_type="feasibility_witness",
            verification_method="every item packed exactly once, every load within capacity, the bin count recounted "
                                "and the canonical order by independent arithmetic; the count not below the volume "
                                "bound; applications within the budget",
            confidence_semantics="the packing is feasible with exactly the stated number of bins; no optimality claim "
                                 "(the certificate reports the volume lower bound for the gap)",
            resource_profile="the declared application budget (5 per item on the benchmark); each application "
                             "copies the packing, O(items)",
            latency_profile="tenths of a second to a few seconds at benchmark size (pure Python)",
            known_strengths=("never worse than first-fit decreasing (it starts there and accepts no worsening)",
                             "adapts which neighbourhood to use to the instance by online credit"),
            known_failure_modes=("a random choice among the same heuristics is a strong rival: the credit signal is "
                                 "sparse and UCB1 may add nothing over it",
                                 "a single strong heuristic run alone can match the mixture",
                                 "first-fit decreasing is already optimal on many instances, so most arms tie there",
                                 "up to 150 items the exact binpack_cpsat genome proves the minimum",
                                 "no optimality guarantee; non-worsening acceptance can stall on plateaus"),
            counterindications=("150 items or fewer (use binpack_cpsat, exact)",
                                "multi-dimensional or conflicting items (vector packing / graph colouring)",
                                "a proven minimum is required"),
            abstention_conditions=(f"none within {HH_MAX_ITEMS} items: the first-fit decreasing start is always a "
                                   "feasible answer",),
            benchmark_suite="planted zero-slack instances (Falkenauer-style triplets, random cuts of 3-7 pieces per "
                            "bin, and a mix), 40-200 planted bins of capacity 1000 or 600, 120-1000 items, 5 "
                            "applications per item; the optimum is the planted count, equal to the volume lower bound; "
                            "quality optimum / bins; seeds 0-9 dev, held-out seeds fixed by the admission freeze",
            baseline="first-fit decreasing",
            competitor="random-selection hyper-heuristic over the same five heuristics, same start, acceptance and "
                       "budget (chosen over the best single heuristic, ruin-and-recreate alone, as the stronger rival "
                       "on dev seeds 0-9)", dependency=None, **_common()),
        solve=hh_solve, verify=hh_verify, instance=hh_instance, score=hh_score, baseline=hh_ffd,
        competitor=hh_competitor, subregion=hh_subregion, tolerance=1e-12,
        notes={"layer": "Layer 3, not 5: the coverage record lists hyper-heuristics as L3.evo.hyperheuristics, and "
                        "this method selects among low-level moves inside one solve; selecting among GREG's own "
                        "genomes is the Layer 5 Competency Compiler",
               "competitor_choice": "two declared rivals (random selection, best single heuristic) were compared on "
                                    "dev seeds 0-9 and the stronger fixed as the competitor (HH_COMPETITOR)",
               "differs_from": "binpack_cpsat (bin_packing_min_bins): exact CP-SAT with a lower-bound certificate, "
                               "native up to 150 items"}),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="developmental.differentiation.lateral_inhibition", version="1.0.0",
            family="develop_differentiate", layer=4, operation="local_role_differentiation",
            epistemic_class="constraint_feasibility",
            subgeometry="every node of a graph picks a role from its radius-d neighbours' states alone so that "
                        "leaders are more than d hops apart and every member is within d hops of a leader (a maximal "
                        "independent set of the d-th power graph), scored by the pattern first and then by LOCAL-model "
                        "message rounds",
            source_provenance="Luby (1986) randomized MIS; Metivier, Robson, Saheb-Djahromi and Zemmari (2011) "
                              "optimal-bit MIS; Afek et al. (2011) MIS by local inhibition rules; Linial (1992) LOCAL "
                              "model; NetworkX for the centralised competitor, OR-Tools CP-SAT for the reference "
                              "optimum; pure Python solver",
            native_representation="number of nodes, undirected edge list, radius d, phase cap, seed",
            required_inputs=("num_nodes", "edges", "radius", "max_phases", "seed"),
            output_contract={"roles": "['leader'|'member'] per node", "phases": "int",
                             "rounds": "int = 2 x radius x phases (LOCAL model)"},
            algorithm_or_runtime="phases of two relayed exchanges: undecided nodes send a hashed per-phase priority "
                                 "over d hops; a node beating every undecided rival within d becomes a leader and "
                                 "inhibits every undecided node within d to a member; UNKNOWN past max_phases",
            parameters={"priority": "SHA-256('seed:phase:node') first 64 bits, ties by id",
                        "round_cost_per_phase": "2 x radius"},
            composition_inputs=("a communication graph", "a coverage radius"),
            composition_outputs=("a role per node", "message rounds used"),
            evidence_type="feasibility_witness",
            verification_method="the pattern checked on a reachability matrix built by boolean matrix powers "
                                "(leaders pairwise beyond d, every member within d of a leader); the roles and phase "
                                "count recomputed by a vectorised NumPy evaluation of the declared rule; rounds "
                                "recomputed from the phases",
            confidence_semantics="the role assignment satisfies the pattern exactly and was reached by the declared "
                                 "local rule in exactly the stated phases and rounds; no claim of the fewest leaders",
            resource_profile="O(phases x sum of radius-d neighbourhood sizes); expected O(log n) phases",
            latency_profile="tens of milliseconds at benchmark size",
            known_strengths=("rounds grow with log n, not with the graph's diameter: on long, sparse graphs it "
                             "finishes before a centre could even gather the topology",
                             "no node needs global information"),
            known_failure_modes=("on low-diameter graphs (small-world, dense random) gathering at a centre takes few "
                                 "rounds and the centralised method wins on rounds",
                                 "rounds are counted in the LOCAL model (unbounded messages), which favours the "
                                 "centralised gather; in a bandwidth-limited model the gather would cost more",
                                 "leader count is not minimised (the CP-SAT reference optimum is reported, not scored)",
                                 "randomised phases: an unlucky seed needs more phases; UNKNOWN past the cap"),
            counterindications=("the whole graph is already at one place (decide centrally, zero rounds)",
                                "a minimum number of leaders is required (use CP-SAT on the independent dominating set "
                                "model)"),
            abstention_conditions=("UNKNOWN when the pattern is not stable within max_phases",),
            benchmark_suite="random geometric (high diameter), connected Watts-Strogatz (k 6, p 0.2), 2-D grids with "
                            "10% holes, and G(n, 12/n); 64-400 nodes; radius 1 (60%) or 2; quality 1 / (1 + rounds) "
                            "when the pattern holds, wrong otherwise; seeds 0-9 dev, held-out seeds fixed by the "
                            "admission freeze",
            baseline="random roles with no communication (leader with probability 1 / (1 + mean radius-d degree))",
            competitor="centralised greedy maximal independent set of the radius-th power graph (NetworkX), charged "
                       "2 x the largest component radius rounds to gather at a centre and broadcast back",
            dependency=None, **_common()),
        solve=df_solve, verify=df_verify, instance=df_instance, score=df_score, baseline=df_random,
        competitor=df_centralised, subregion=df_subregion, tolerance=1e-12,
        notes={"effect_not_metaphor": "differentiation names the effect, role specialisation by local rules; "
                                      "nothing biological is claimed"}),
]
