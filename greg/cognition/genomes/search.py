"""Layer 3 search intelligences: iterative-deepening A*, beam search and Monte Carlo tree search.

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.json``) lists beam search, Monte Carlo
tree search and iterative deepening as ABSENT from Layer 3 (a stated code search found no mechanism). Each executable
here is a textbook mechanism on the geometry where it is known to matter, on GREG's one cognition path
(``greg.cognition.cortex.reason`` -> isolated worker -> independent verifier -> CognitiveReceipt):

* ``search_ida_star`` (``sliding_puzzle_optimal``): optimal plans for sliding-tile puzzles (3x3 and 4x4) under a
  declared memory budget of stored search nodes, by IDA* (Korf 1985) with Manhattan distance plus linear conflicts.
  IDA* stores only its path, so the memory budget never binds it; a memory-hungry search (breadth-first, A*) under
  the same budget abstains when its frontier outgrows the budget. Verified by replaying the moves, an independent
  parity formula for unsolvability claims, and an independent optimality proof: on 3x3 a breadth-first distance
  table of all 181,440 solvable states, on 4x4 a depth-first search of the verifier's own (Manhattan only) proving
  that no plan two moves shorter exists (plans of one position all have the same length parity).
* ``search_beam`` (``flowshop_sequence``): permutation flow-shop sequencing (minimum makespan), by forward beam
  search over partial sequences guided by a bound-and-idle-time score. Verified by recomputing the makespan of the
  returned sequence from the processing times and the machine-based lower bound; no optimality is claimed.
* ``search_mcts`` (``hex_move_select``): move selection in Hex positions under a declared simulator budget (stone
  placements), by UCT Monte Carlo tree search (Kocsis and Szepesvari 2006) with uniform random playouts. Verified by
  legality, the consistency of the reported root statistics with the budget, and, for positions small enough to
  solve within the verifier's bound, an independent exact solve requiring the move to win when any move wins.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output of any
method here creates authority. Development seeds 0-9 only.
"""
from __future__ import annotations

from collections import deque
from functools import lru_cache
import hashlib
import heapq
import json
import math
import random
import time

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4 (restore the full five-layer scope)",
           "docs/collaboration/MIND-COVERAGE-2026-10-21.json (Layer 3 ABSENT: L3.search.beam, L3.search.mcts, "
           "L3.search.iterative_deepening)")


def _common(**kw):
    return dict(buildability="BUILDABLE_NOW", memory_model="stateless",
                learning_rule="none (competence settles per geometry through GREG outcomes)", lineage=LINEAGE, **kw)


def _abstain(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="ABSTAIN", missing=[reason])


def _unknown(reason, **certificate):
    return answer(None, {"reason": reason, **certificate}, status="UNKNOWN", missing=[reason])


def _mapping(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    return data


def _cert(certificate):
    return certificate if isinstance(certificate, dict) else {}


def _seconds(budget, cap=10.0):
    try:
        return max(0.5, min(cap, float((budget or {}).get("latency_s", cap))))
    except (TypeError, ValueError):
        return cap


def _digest(value) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class _OutOfBudget(Exception):
    pass


# =================================================================== 1. IDA* on sliding-tile puzzles
SP_WIDTHS = (3, 4)
SP_MAX_MEMORY = 10_000_000
SP_VERIFY_NODES = 20_000_000          # the verifier's 4x4 optimality search refuses beyond this many nodes
ARM_SECONDS = 10.0                    # wall-clock cap of the baseline and competitor arms (they get no budget)
SP_BENCH_MEMORY = 100_000             # the benchmark's memory budget (stored positions), shared by every arm
MOVES = {"U": (-1, 0), "D": (1, 0), "L": (0, -1), "R": (0, 1)}
OPPOSITE = {"U": "D", "D": "U", "L": "R", "R": "L"}


def _puzzle(data):
    """(width, tiles tuple, memory budget in stored nodes)."""
    data = _mapping(data)
    w = data.get("puzzle_width")
    if type(w) is not int or w not in SP_WIDTHS:
        raise GenomeError(f"puzzle_width: one of {SP_WIDTHS}")
    tiles = data.get("puzzle_tiles")
    if (not isinstance(tiles, list) or len(tiles) != w * w or not all(type(t) is int for t in tiles)
            or sorted(tiles) != list(range(w * w))):
        raise GenomeError("puzzle_tiles: a permutation of 0..width^2-1 in row-major order (0 is the blank)")
    memory = bounded_int(data.get("memory_nodes"), low=1, high=SP_MAX_MEMORY, name="memory_nodes")
    return w, tuple(tiles), memory


def _goal(w):
    return tuple(list(range(1, w * w)) + [0])


def _solvable(w, tiles):
    """Solver's test: inversion count (with the blank's row from the bottom for even widths)."""
    seq = [t for t in tiles if t]
    inv = sum(1 for i in range(len(seq)) for j in range(i + 1, len(seq)) if seq[i] > seq[j])
    if w % 2:
        return inv % 2 == 0
    row_from_bottom = w - tiles.index(0) // w
    return (inv + row_from_bottom) % 2 == 1


def _neighbours(w):
    """blank index -> [(direction, new blank index)] in a fixed order."""
    out = []
    for b in range(w * w):
        r, c = divmod(b, w)
        here = []
        for d, (dr, dc) in MOVES.items():
            if 0 <= r + dr < w and 0 <= c + dc < w:
                here.append((d, (r + dr) * w + c + dc))
        out.append(here)
    return out


def _manhattan_table(w):
    """tile -> position -> distance to the tile's goal position."""
    table = [[0] * (w * w) for _ in range(w * w)]
    for t in range(1, w * w):
        gr, gc = divmod(t - 1, w)
        for p in range(w * w):
            r, c = divmod(p, w)
            table[t][p] = abs(r - gr) + abs(c - gc)
    return table


def _line_conflict(w, tiles, line, by_row):
    """Hansson, Mayer and Yung (1992) linear conflicts of one row (``by_row``) or column: two extra moves per tile
    that must leave the line for the others in it to pass, counted as (tiles in their goal line here) - (longest
    increasing subsequence of their goal positions), which is admissible."""
    goals = []
    for k in range(w):
        t = tiles[line * w + k if by_row else k * w + line]
        if t == 0:
            continue
        gr, gc = divmod(t - 1, w)
        if (gr if by_row else gc) == line:
            goals.append(gc if by_row else gr)
    if len(goals) < 2:
        return 0
    best = [1] * len(goals)                              # longest increasing subsequence (lines of <= 4)
    for i in range(len(goals)):
        for j in range(i):
            if goals[j] < goals[i] and best[j] + 1 > best[i]:
                best[i] = best[j] + 1
    return 2 * (len(goals) - max(best))


def _linear_conflicts(w, tiles):
    return sum(_line_conflict(w, tiles, line, by_row) for line in range(w) for by_row in (True, False))


def _heuristic(w, tiles, table):
    return sum(table[t][p] for p, t in enumerate(tiles) if t) + _linear_conflicts(w, tiles)


def ida_star(w, start, deadline=None, node_cap=None):
    """IDA* with Manhattan distance plus linear conflicts, both updated incrementally (a move changes one tile's
    distance and the conflicts of the two lines it leaves and enters). Returns (moves string, nodes, thresholds);
    raises _OutOfBudget past the deadline or node cap. Memory: the current path only."""
    table, nbr, goal = _manhattan_table(w), _neighbours(w), _goal(w)
    tiles = list(start)
    path = []
    nodes = [0]
    thresholds = []
    memo = {}

    def conflict(line, by_row):
        cells = tuple(tiles[line * w:(line + 1) * w]) if by_row else tuple(tiles[line::w])
        key = (by_row, line, cells)
        value = memo.get(key)
        if value is None:
            value = memo[key] = _line_conflict(w, tiles, line, by_row)
        return value

    rows = [conflict(i, True) for i in range(w)]
    cols = [conflict(i, False) for i in range(w)]

    def search(blank, g, bound, last, md, lc):
        nodes[0] += 1
        if nodes[0] & 4095 == 0 and ((deadline is not None and time.perf_counter() > deadline)
                                     or (node_cap is not None and nodes[0] > node_cap)):
            raise _OutOfBudget
        f = g + md + lc
        if f > bound:
            return f
        if md == 0:
            return -1                                    # every tile on its goal cell: the goal
        least = 1 << 30
        br, bc = divmod(blank, w)
        for d, nb in nbr[blank]:
            if last is not None and d == OPPOSITE[last]:
                continue
            t = tiles[nb]
            delta = table[t][blank] - table[t][nb]
            tiles[blank], tiles[nb] = t, 0
            nr, nc = divmod(nb, w)
            if nr == br:                                 # horizontal move: the tile changes column
                old = cols[nc] + cols[bc]
                cols[nc], cols[bc] = conflict(nc, False), conflict(bc, False)
                dlc = cols[nc] + cols[bc] - old
            else:                                        # vertical move: the tile changes row
                old = rows[nr] + rows[br]
                rows[nr], rows[br] = conflict(nr, True), conflict(br, True)
                dlc = rows[nr] + rows[br] - old
            path.append(d)
            r = search(nb, g + 1, bound, d, md + delta, lc + dlc)
            if r == -1:
                return -1
            path.pop()
            tiles[nb], tiles[blank] = t, 0
            if nr == br:
                cols[nc], cols[bc] = conflict(nc, False), conflict(bc, False)
            else:
                rows[nr], rows[br] = conflict(nr, True), conflict(br, True)
            if r < least:
                least = r
        return least

    md0 = sum(table[t][p] for p, t in enumerate(tiles) if t)
    lc0 = sum(rows) + sum(cols)
    bound = md0 + lc0
    blank = tiles.index(0)
    while True:
        thresholds.append(bound)
        r = search(blank, 0, bound, None, md0, lc0)
        if r == -1:
            return "".join(path), nodes[0], thresholds
        if r >= 1 << 30:
            raise GenomeError("no plan exists although the parity test passed")
        bound = r


def ida_solve(data, budget):
    w, tiles, memory = _puzzle(data)
    cert = {"method": "IDA* (Manhattan distance + linear conflicts), stores only the current path", "width": w,
            "memory_budget": memory}
    if not _solvable(w, tiles):
        return answer({"solvable": False, "moves": None, "length": None},
                      {**cert, "proof": "inversion parity (with the blank row for even widths) differs from the goal"})
    if memory < w * w * 4:
        return _abstain("memory budget below the path IDA* needs", **cert)
    try:
        moves, nodes, thresholds = ida_star(w, tiles, deadline=time.perf_counter() + _seconds(budget))
    except _OutOfBudget:
        return _unknown("IDA* did not finish within the latency budget", **cert)
    if len(moves) + 1 > memory:
        return _abstain("the plan is longer than the memory budget", **cert)
    out = {"solvable": True, "moves": moves, "length": len(moves)}
    return answer(out, {**cert, "nodes_expanded": nodes, "thresholds": thresholds,
                        "peak_stored_nodes": len(moves) + 1, "witness": _digest(moves)})


def _replay(w, tiles, moves):
    """The position after ``moves`` (blank directions), or None when a move leaves the board."""
    tiles = list(tiles)
    b = tiles.index(0)
    for d in moves:
        if d not in MOVES:
            return None
        r, c = divmod(b, w)
        dr, dc = MOVES[d]
        if not (0 <= r + dr < w and 0 <= c + dc < w):
            return None
        nb = (r + dr) * w + c + dc
        tiles[b], tiles[nb] = tiles[nb], 0
        b = nb
    return tuple(tiles)


def _parity_solvable(w, tiles):
    """Verifier's own test, a different formula: the permutation parity of all w^2 cells (blank included, by cycle
    decomposition) must equal the parity of the blank's taxicab distance from its goal cell."""
    goal_pos = {t: (t - 1 if t else w * w - 1) for t in range(w * w)}
    seen, transpositions = [False] * (w * w), 0
    for i in range(w * w):
        if not seen[i]:
            j, length = i, 0
            while not seen[j]:
                seen[j] = True
                j = goal_pos[tiles[j]]
                length += 1
            transpositions += length - 1
    b = tiles.index(0)
    blank_distance = abs(b // w - (w - 1)) + abs(b % w - (w - 1))
    return transpositions % 2 == blank_distance % 2


@lru_cache(maxsize=1)
def _distance_table_3x3():
    """Verifier's own exhaustive table: breadth-first distance from the goal to every solvable 3x3 position."""
    goal = _goal(3)
    dist = {goal: 0}
    queue = deque([goal])
    nbr = _neighbours(3)
    while queue:
        s = queue.popleft()
        b = s.index(0)
        d = dist[s] + 1
        for _, nb in nbr[b]:
            t = list(s)
            t[b], t[nb] = t[nb], 0
            t = tuple(t)
            if t not in dist:
                dist[t] = d
                queue.append(t)
    return dist


def _no_plan_within(w, tiles, bound, node_cap=SP_VERIFY_NODES):
    """Verifier's own exhaustive check: True if no plan of length <= ``bound`` reaches the goal (depth-first,
    pruned by plain Manhattan distance, no linear conflicts, no transposition table), False if one does, None past
    the node cap."""
    if bound < 0:
        return True
    goal = _goal(w)
    gpos = {t: divmod(t - 1, w) for t in range(1, w * w)}
    s = list(tiles)
    md = sum(abs(p // w - gpos[t][0]) + abs(p % w - gpos[t][1]) for p, t in enumerate(s) if t)
    count = [0]

    def dfs(b, g, md, back):
        count[0] += 1
        if count[0] > node_cap:
            raise _OutOfBudget
        if g + md > bound:
            return False
        if md == 0 and tuple(s) == goal:
            return True
        r, c = divmod(b, w)
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if not (0 <= nr < w and 0 <= nc < w):
                continue
            nb = nr * w + nc
            if nb == back:
                continue
            t = s[nb]
            tr, tc = gpos[t]
            delta = (abs(r - tr) + abs(c - tc)) - (abs(nr - tr) + abs(nc - tc))
            s[b], s[nb] = t, 0
            found = dfs(nb, g + 1, md + delta, b)
            s[nb], s[b] = t, 0
            if found:
                return True
        return False
    try:
        return not dfs(s.index(0), 0, md, -1)
    except _OutOfBudget:
        return None


def ida_verify(data, output, certificate):
    w, tiles, memory = _puzzle(data)
    if (not isinstance(output, dict) or set(output) != {"solvable", "moves", "length"}
            or type(output["solvable"]) is not bool):
        return {"output_shape": False}
    certificate = _cert(certificate)
    if not output["solvable"]:
        if output["moves"] is not None or output["length"] is not None:
            return {"output_shape": False}
        return {"output_shape": True, "unsolvable_by_independent_parity": not _parity_solvable(w, tiles)}
    moves, length = output["moves"], output["length"]
    if not isinstance(moves, str) or type(length) is not int:
        return {"output_shape": False}
    checks = {"output_shape": True, "length_recomputed": length == len(moves),
              "moves_reach_the_goal": _replay(w, tiles, moves) == _goal(w),
              "witness_is_the_certified_plan": certificate.get("witness") == _digest(moves),
              "within_the_memory_budget": isinstance(certificate.get("peak_stored_nodes"), int)
              and certificate["peak_stored_nodes"] == length + 1 <= memory}
    if not all(checks.values()):
        checks["no_shorter_plan"] = False
        return checks
    if w == 3:
        checks["no_shorter_plan"] = _distance_table_3x3().get(tiles) == length
    else:
        checks["no_shorter_plan"] = _no_plan_within(w, tiles, length - 2) is True
    return checks


def ida_optimum(w, tiles):
    """Evaluation side only (``score``): the optimal plan length by the verifier's code, never the solver's (3x3: the
    breadth-first table; 4x4: increasing bounds of the plain-Manhattan exhaustive search)."""
    if not _parity_solvable(w, tiles):
        return None
    if w == 3:
        return _distance_table_3x3()[tiles]
    gpos = {t: divmod(t - 1, w) for t in range(1, w * w)}
    bound = sum(abs(p // w - gpos[t][0]) + abs(p % w - gpos[t][1]) for p, t in enumerate(tiles) if t)
    while True:
        result = _no_plan_within(w, tiles, bound, node_cap=10 ** 9)
        if result is False:
            return bound
        bound += 2


def ida_instance(seed):
    """3x3 positions uniformly at random among solvable ones; 4x4 positions by a seeded random walk from the goal
    (no immediate reversals) of 40-80 moves, so optimal plans run from the teens to the forties."""
    r = random.Random(f"genome:search_ida_star:{seed}")
    kind = ("3x3_uniform", "4x4_walk", "4x4_walk", "3x3_uniform", "4x4_walk")[seed % 5]
    if kind == "3x3_uniform":
        w = 3
        while True:
            tiles = list(range(9))
            r.shuffle(tiles)
            if _parity_solvable(3, tiles):
                break
    else:
        w = 4
        tiles = list(_goal(4))
        b, last = tiles.index(0), None
        nbr = _neighbours(4)
        for _ in range(r.randint(40, 80)):
            options = [(d, nb) for d, nb in nbr[b] if last is None or d != OPPOSITE[last]]
            d, nb = r.choice(options)
            tiles[b], tiles[nb] = tiles[nb], 0
            b, last = nb, d
    data = {"puzzle_width": w, "puzzle_tiles": list(tiles), "memory_nodes": SP_BENCH_MEMORY}
    return data, {"optimum": ida_optimum(w, tuple(tiles))}



def ida_subregion(data):
    w, tiles, _ = _puzzle(data)
    return f"{w}x{w}"


def ida_score(data, truth, output):
    if not isinstance(output, dict) or "solvable" not in output:
        return {"quality": 0.0, "category": "abstain"}
    w, tiles, _ = _puzzle(data)
    if truth["optimum"] is None:
        ok = output.get("solvable") is False
        return {"quality": 1.0 if ok else -1.0, "category": "correct" if ok else "wrong"}
    moves = output.get("moves")
    if (output.get("solvable") is not True or not isinstance(moves, str) or output.get("length") != len(moves)
            or _replay(w, tiles, moves) != _goal(w)):
        return {"quality": -1.0, "category": "wrong"}
    if not moves:
        return {"quality": 1.0, "category": "correct"}
    q = truth["optimum"] / len(moves)
    return {"quality": q, "category": "correct" if len(moves) == truth["optimum"] else "wrong"}


def _plan(parents, state):
    moves = []
    while parents[state] is not None:
        state, d = parents[state]
        moves.append(d)
    return "".join(reversed(moves))


def ida_bfs(data):
    """Baseline: breadth-first search from the start, storing every generated position; abstains when the stored
    positions would exceed the memory budget."""
    w, tiles, memory = _puzzle(data)
    if not _solvable(w, tiles):
        return {"solvable": False, "moves": None, "length": None}
    goal, nbr = _goal(w), _neighbours(w)
    parents = {tiles: None}
    queue = deque([tiles])
    deadline = time.perf_counter() + ARM_SECONDS
    while queue:
        s = queue.popleft()
        if s == goal:
            moves = _plan(parents, s)
            return {"solvable": True, "moves": moves, "length": len(moves)}
        if time.perf_counter() > deadline:
            return None
        b = s.index(0)
        for d, nb in nbr[b]:
            t = list(s)
            t[b], t[nb] = t[nb], 0
            t = tuple(t)
            if t not in parents:
                if len(parents) >= memory:
                    return None
                parents[t] = (s, d)
                queue.append(t)
    return None


def ida_astar(data):
    """Competitor: A* with the candidate's heuristic (Manhattan distance + linear conflicts) and a closed list,
    storing every generated position; abstains when the stored positions would exceed the memory budget."""
    w, tiles, memory = _puzzle(data)
    if not _solvable(w, tiles):
        return {"solvable": False, "moves": None, "length": None}
    goal, nbr, table = _goal(w), _neighbours(w), _manhattan_table(w)
    g = {tiles: 0}
    parents = {tiles: None}
    heap = [(_heuristic(w, tiles, table), 0, 0, tiles)]
    counter = 0
    deadline = time.perf_counter() + ARM_SECONDS
    closed = set()
    while heap:
        f, negg, _, s = heapq.heappop(heap)
        if s in closed:
            continue
        if s == goal:
            moves = _plan(parents, s)
            return {"solvable": True, "moves": moves, "length": len(moves)}
        closed.add(s)
        counter += 1
        if counter & 1023 == 0 and time.perf_counter() > deadline:
            return None
        b = s.index(0)
        gs = g[s] + 1
        for d, nb in nbr[b]:
            t = list(s)
            t[b], t[nb] = t[nb], 0
            t = tuple(t)
            if t not in g or gs < g[t]:
                if t not in g and len(g) >= memory:
                    return None
                g[t] = gs
                parents[t] = (s, d)
                heapq.heappush(heap, (gs + _heuristic(w, t, table), -gs, counter, t))
    return None


# =================================================================== 2. beam search for permutation flow-shop sequencing
FS_MAX_JOBS, FS_MAX_MACHINES, FS_MAX_TIME = 200, 50, 100_000
FS_NATIVE_JOBS, FS_NATIVE_MACHINES = 60, 20
FS_WORK = 2_000_000           # beam width = this / (jobs^2 x machines), clipped to [4, FS_MAX_WIDTH]
FS_MAX_WIDTH = 64
FS_CPSAT_SECONDS = 2.0


def _flowshop(data):
    """Processing times p[job][machine] (positive integers)."""
    data = _mapping(data)
    p = data.get("flowshop_times")
    if not isinstance(p, list) or not 2 <= len(p) <= FS_MAX_JOBS or not isinstance(p[0], list):
        raise GenomeError(f"flowshop_times: 2-{FS_MAX_JOBS} jobs, each a list of machine times")
    m = len(p[0])
    if not 1 <= m <= FS_MAX_MACHINES:
        raise GenomeError(f"1-{FS_MAX_MACHINES} machines")
    for row in p:
        if not isinstance(row, list) or len(row) != m:
            raise GenomeError("every job lists one time per machine")
        for t in row:
            bounded_int(t, low=1, high=FS_MAX_TIME, name="processing time")
    return p


def fs_makespan(p, order):
    """Completion time of the last job on the last machine for a job order (the textbook recurrence)."""
    front = [0] * len(p[0])
    for j in order:
        row, prev = p[j], 0
        for k, t in enumerate(row):
            prev = (front[k] if front[k] > prev else prev) + t
            front[k] = prev
    return front[-1]


def fs_lower_bound(p):
    """Taillard (1993) machine- and job-based lower bound on the optimal makespan."""
    n, m = len(p), len(p[0])
    bound = max(sum(row) for row in p)
    for k in range(m):
        head = min(sum(row[:k]) for row in p)
        tail = min(sum(row[k + 1:]) for row in p)
        bound = max(bound, head + sum(row[k] for row in p) + tail)
    return bound


def _beam_width(n, m):
    return max(4, min(FS_MAX_WIDTH, FS_WORK // (n * n * m)))


def _insertion_spans(p, order, j):
    """Taillard (1990) acceleration: the makespan of inserting job ``j`` at every position of ``order`` (0..len),
    in O(len x machines) from heads, tails and the inserted job's completion times."""
    m, k = len(p[0]), len(order)
    e = [[0] * (m + 1) for _ in range(k + 1)]          # e[i][r]: completion of the i-th job on machine r (1-based)
    for i in range(1, k + 1):
        row = p[order[i - 1]]
        for r in range(1, m + 1):
            e[i][r] = max(e[i - 1][r], e[i][r - 1]) + row[r - 1]
    q = [[0] * (m + 2) for _ in range(k + 2)]          # q[i][r]: tail from the i-th job on machine r to the end
    for i in range(k, 0, -1):
        row = p[order[i - 1]]
        for r in range(m, 0, -1):
            q[i][r] = max(q[i + 1][r], q[i][r + 1]) + row[r - 1]
    spans, row = [], p[j]
    for pos in range(k + 1):
        f, best = 0, 0
        for r in range(1, m + 1):
            f = max(f, e[pos][r]) + row[r - 1]
            if f + q[pos + 1][r] > best:
                best = f + q[pos + 1][r]
        spans.append(best)
    return spans


def flowshop_beam(p, width, deadline=None):
    """Beam search in NEH's insertion space: jobs are taken by decreasing total time, and at each step every
    surviving partial sequence receives the next job at every position; the ``width`` distinct partial sequences
    with the smallest partial makespan (ties: the smaller sum of machine fronts, then the sequence) survive. The
    greedy chain (each step's first best insertion into the previous greedy sequence, i.e. NEH) is anchored in the
    beam, so the answer is never worse than NEH; width 1 is NEH itself."""
    jobs = sorted(range(len(p)), key=lambda j: (-sum(p[j]), j))
    beam = [(jobs[0],)]
    anchor = (jobs[0],)
    scored = 0
    for step, j in enumerate(jobs[1:], start=1):
        children = {}
        for seq in beam:
            spans = _insertion_spans(p, list(seq), j)
            for pos, span in enumerate(spans):
                child = seq[:pos] + (j,) + seq[pos:]
                if child not in children:
                    children[child] = span
                scored += 1
            if seq == anchor:
                pos = spans.index(min(spans))
                anchor = seq[:pos] + (j,) + seq[pos:]
        if len(children) > width:
            ranked = sorted(children.items(), key=lambda c: c[1])
            cut = ranked[width - 1][1]
            tied = [c for c in ranked if c[1] <= cut]
            if len(tied) > width:
                tied = sorted(tied, key=lambda c: (c[1], _flow(p, c[0]), c[0]))
            beam = [c[0] for c in tied[:width]]
            if anchor not in beam:
                beam[-1] = anchor
        else:
            beam = list(children)
        if deadline is not None and time.perf_counter() > deadline and step < len(jobs) - 1:
            raise _OutOfBudget
    best = min(beam, key=lambda seq: (fs_makespan(p, seq), seq))
    return list(best), fs_makespan(p, best), scored


def _flow(p, seq):
    """Sum over machines of the completion times of the sequence's last job (a tie-break that prefers tight
    fronts)."""
    front = [0] * len(p[0])
    for j in seq:
        prev = 0
        for k, t in enumerate(p[j]):
            prev = (front[k] if front[k] > prev else prev) + t
            front[k] = prev
    return sum(front)


def fs_solve(data, budget):
    p = _flowshop(data)
    n, m = len(p), len(p[0])
    if n > FS_NATIVE_JOBS or m > FS_NATIVE_MACHINES:
        return _abstain(f"more than {FS_NATIVE_JOBS} jobs or {FS_NATIVE_MACHINES} machines exceeds the bounded "
                        "beam budget", jobs=n, machines=m)
    width = _beam_width(n, m)
    try:
        order, span, expanded = flowshop_beam(p, width, deadline=time.perf_counter() + _seconds(budget))
    except _OutOfBudget:
        return _unknown("beam search did not finish within the latency budget", width=width)
    out = {"order": order, "makespan": span}
    return answer(out, {"method": "beam search over NEH insertions (Taillard-accelerated)", "width": width,
                        "children_scored": expanded, "lower_bound": fs_lower_bound(p), "witness": _digest(order)})


def _independent_makespan(p, order):
    """Verifier's own computation: earliest start times by longest paths in the job-machine grid (a different
    traversal order from the solver's recurrence: machine by machine)."""
    m = len(p[0])
    previous = [0] * len(order)
    for k in range(m):
        current, finish = [], 0
        for pos, j in enumerate(order):
            finish = max(finish, previous[pos]) + p[j][k]
            current.append(finish)
        previous = current
    return previous[-1] if previous else 0


def fs_verify(data, output, certificate):
    p = _flowshop(data)
    if not isinstance(output, dict) or set(output) != {"order", "makespan"}:
        return {"output_shape": False}
    order, span = output["order"], output["makespan"]
    if not isinstance(order, list) or not all(type(j) is int for j in order) or type(span) is not int:
        return {"output_shape": False}
    certificate = _cert(certificate)
    checks = {"output_shape": True, "order_is_a_permutation_of_the_jobs": sorted(order) == list(range(len(p)))}
    if not checks["order_is_a_permutation_of_the_jobs"]:
        checks["makespan_recomputed"] = False
        return checks
    checks["makespan_recomputed"] = _independent_makespan(p, order) == span
    checks["witness_is_the_certified_order"] = certificate.get("witness") == _digest(order)
    bound = max([sum(row) for row in p] + [min(sum(row[:k]) for row in p) + sum(row[k] for row in p)
                                          + min(sum(row[k + 1:]) for row in p) for k in range(len(p[0]))])
    checks["lower_bound_recomputed"] = certificate.get("lower_bound") == bound and bound <= span
    return checks


def fs_instance(seed):
    """Taillard-style random times U[1, 99], job-correlated times (a job's times share a level) and machine-
    correlated times (a machine's times share a level, bottleneck machines); 15-50 jobs on 5-20 machines."""
    r = random.Random(f"genome:search_beam:{seed}")
    kind = ("taillard", "job_correlated", "machine_correlated", "taillard", "job_correlated")[seed % 5]
    n = r.choice((15, 20, 30, 50))
    m = r.choice((5, 10, 20))
    if kind == "taillard":
        p = [[r.randint(1, 99) for _ in range(m)] for _ in range(n)]
    elif kind == "job_correlated":
        p = []
        for _ in range(n):
            level = r.randint(10, 90)
            p.append([max(1, min(99, level + r.randint(-10, 10))) for _ in range(m)])
    else:
        levels = [r.randint(10, 90) for _ in range(m)]
        p = [[max(1, min(99, levels[k] + r.randint(-10, 10))) for k in range(m)] for _ in range(n)]
    return {"flowshop_times": p}, {"lower_bound": fs_lower_bound(p)}


def fs_subregion(data):
    p = _flowshop(data)
    n = len(p)
    return "small (<= 20 jobs)" if n <= 20 else ("medium (30 jobs)" if n <= 30 else "large (50 jobs)")


def fs_score(data, truth, output):
    if not isinstance(output, dict) or "order" not in output:
        return {"quality": 0.0, "category": "abstain"}
    p = _flowshop(data)
    order = output.get("order")
    if (not isinstance(order, list) or sorted(order) != list(range(len(p)))
            or output.get("makespan") != fs_makespan(p, order)):
        return {"quality": -1.0, "category": "wrong"}
    return {"quality": truth["lower_bound"] / output["makespan"], "category": "correct"}


def fs_neh(data):
    """Baseline: NEH (Nawaz, Enscore and Ham 1983): jobs by decreasing total time, each inserted at the position that
    minimises the partial makespan (first such position)."""
    p = _flowshop(data)
    jobs = sorted(range(len(p)), key=lambda j: (-sum(p[j]), j))
    order = [jobs[0]]
    for j in jobs[1:]:
        best = None
        for pos in range(len(order) + 1):
            trial = order[:pos] + [j] + order[pos:]
            span = fs_makespan(p, trial)
            if best is None or span < best[0]:
                best = (span, trial)
        order = best[1]
    return {"order": order, "makespan": fs_makespan(p, order)}


def fs_cpsat(data):
    """Competitor: OR-Tools CP-SAT on the permutation flow-shop model (one interval per operation, no overlap per
    machine, one shared order literal per job pair), warm-started from the NEH sequence, one worker, 2 s limit; the
    better of the best sequence found and the warm start is returned."""
    from ortools.sat.python import cp_model
    p = _flowshop(data)
    n, m = len(p), len(p[0])
    horizon = sum(sum(row) for row in p)
    model = cp_model.CpModel()
    start = [[model.new_int_var(0, horizon, f"s{j}_{k}") for k in range(m)] for j in range(n)]
    for j in range(n):
        for k in range(1, m):
            model.add(start[j][k] >= start[j][k - 1] + p[j][k - 1])
    for a in range(n):
        for b in range(a + 1, n):
            before = model.new_bool_var(f"o{a}_{b}")
            for k in range(m):
                model.add(start[b][k] >= start[a][k] + p[a][k]).only_enforce_if(before)
                model.add(start[a][k] >= start[b][k] + p[b][k]).only_enforce_if(before.Not())
    span = model.new_int_var(0, horizon, "makespan")
    for j in range(n):
        model.add(span >= start[j][m - 1] + p[j][m - 1])
    model.minimize(span)
    hint = fs_neh(data)["order"]
    position = {j: i for i, j in enumerate(hint)}
    front = [0] * m
    for j in hint:
        prev = 0
        for k in range(m):
            s = max(front[k], prev)
            model.add_hint(start[j][k], s)
            prev = s + p[j][k]
            front[k] = prev
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    solver.parameters.max_time_in_seconds = FS_CPSAT_SECONDS
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {"order": hint, "makespan": fs_makespan(p, hint)}      # nothing found: the warm start stands
    order = sorted(range(n), key=lambda j: (solver.value(start[j][0]), position[j]))
    if fs_makespan(p, order) > fs_makespan(p, hint):
        order = hint
    return {"order": order, "makespan": fs_makespan(p, order)}


# =================================================================== 3. Monte Carlo tree search for Hex move selection
HX_SIZES = (4, 5, 6, 7, 8, 9)
HX_MAX_BUDGET = 2_000_000
HX_VERIFY_EMPTIES = 20            # the verifier solves positions with at most this many empty cells exactly
HX_SOLVE_NODES = 3_000_000        # node cap of an exact solve (verifier and evaluation)
HX_UCT_C = 1.0
HX_BENCH_BUDGET = 60_000


def _hex(data):
    """(size, cells tuple of '.', 'B', 'W' in row-major order, player to move, placement budget). Black joins the
    top and bottom rows, White the left and right columns; Black moves first, so the counts fix the mover."""
    data = _mapping(data)
    n = data.get("hex_size")
    if type(n) is not int or n not in HX_SIZES:
        raise GenomeError(f"hex_size: one of {HX_SIZES}")
    rows = data.get("hex_stones")
    if (not isinstance(rows, list) or len(rows) != n
            or not all(isinstance(row, str) and len(row) == n and set(row) <= set(".BW") for row in rows)):
        raise GenomeError("hex_stones: one string of '.', 'B' and 'W' per row")
    cells = tuple("".join(rows))
    black, white = cells.count("B"), cells.count("W")
    mover = data.get("to_move")
    if mover not in ("B", "W") or mover != ("B" if black == white else "W") or black - white not in (0, 1):
        raise GenomeError("to_move: 'B' or 'W', consistent with the stone counts (Black moves first)")
    budget = bounded_int(data.get("simulation_budget"), low=1, high=HX_MAX_BUDGET, name="simulation_budget")
    if "." not in cells:
        raise GenomeError("the board is full")
    return n, cells, mover, budget


@lru_cache(maxsize=None)
def _hex_adjacency(n):
    out = []
    for i in range(n * n):
        r, c = divmod(i, n)
        out.append(tuple((r + dr) * n + c + dc for dr, dc in ((-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0))
                         if 0 <= r + dr < n and 0 <= c + dc < n))
    return tuple(out)


def _connected(n, cells, player):
    """True if ``player`` joins its two edges (Black: top and bottom rows; White: left and right columns)."""
    adj = _hex_adjacency(n)
    if player == "B":
        stack = [c for c in range(n) if cells[c] == "B"]
        done = lambda i: i >= n * (n - 1)                                  # noqa: E731
    else:
        stack = [r * n for r in range(n) if cells[r * n] == "W"]
        done = lambda i: i % n == n - 1                                    # noqa: E731
    seen = set(stack)
    while stack:
        i = stack.pop()
        if done(i):
            return True
        for j in adj[i]:
            if j not in seen and cells[j] == player:
                seen.add(j)
                stack.append(j)
    return False


def _other(player):
    return "W" if player == "B" else "B"


def _rollout(n, cells, mover, rng):
    """Uniform random playout to a full board; returns the winner (exactly one player joins on a full board)."""
    empties = [i for i, v in enumerate(cells) if v == "."]
    rng.shuffle(empties)
    board = list(cells)
    player = mover
    for i in empties:
        board[i] = player
        player = _other(player)
    return "B" if _connected(n, board, "B") else "W"


class _Node:
    __slots__ = ("move", "parent", "children", "untried", "visits", "wins", "player")

    def __init__(self, move, parent, untried, player):
        self.move, self.parent, self.children, self.untried = move, parent, [], untried
        self.visits, self.wins, self.player = 0, 0, player          # player: who made ``move``


def uct(n, cells, mover, budget, seed=0, c=HX_UCT_C, deadline=None):
    """UCT: UCB1 selection (exploration constant ``c``), one expansion per iteration, a uniform random playout to a
    full board, backed-up wins. Every iteration places exactly as many stones as the root has empty cells (tree
    moves plus playout moves), and iterations stop when the next would exceed the placement budget."""
    rng = random.Random(f"uct:{seed}")
    root = _Node(None, None, [i for i, v in enumerate(cells) if v == "."], _other(mover))
    rng.shuffle(root.untried)
    empties = len(root.untried)
    used = iterations = 0
    while used + empties <= budget:
        if deadline is not None and iterations & 63 == 0 and time.perf_counter() > deadline:
            raise _OutOfBudget
        node, board = root, list(cells)
        while not node.untried and node.children:                      # selection
            log_n = math.log(node.visits)
            node = max(node.children, key=lambda ch: ch.wins / ch.visits + c * math.sqrt(log_n / ch.visits))
            board[node.move] = node.player
        if node.untried:                                               # expansion
            move = node.untried.pop()
            player = _other(node.player)
            board[move] = player
            child = _Node(move, node, [i for i, v in enumerate(board) if v == "."], player)
            rng.shuffle(child.untried)
            node.children.append(child)
            node = child
        if "." in board:                                               # playout
            winner = _rollout(n, board, _other(node.player), rng)
        else:
            winner = "B" if _connected(n, board, "B") else "W"
        used += empties
        iterations += 1
        while node is not None:                                        # backup
            node.visits += 1
            if winner == node.player:
                node.wins += 1
            node = node.parent
    return root, used, iterations


def _root_output(n, root, used, iterations, method):
    if not root.children:
        return None, None
    best = max(root.children, key=lambda ch: (ch.visits, ch.wins, -ch.move))
    stats = sorted([[ch.move // n, ch.move % n, ch.visits, ch.wins] for ch in root.children])
    out = {"move": [best.move // n, best.move % n], "visits": best.visits,
           "value": round(best.wins / best.visits, 12)}
    return out, {"method": method, "children": stats, "iterations": iterations, "placements": used}


def mcts_solve(data, budget):
    n, cells, mover, sims = _hex(data)
    empties = cells.count(".")
    if _connected(n, cells, "B") or _connected(n, cells, "W"):
        return _abstain("the game is already decided: a player has joined")
    if sims < empties:
        return _abstain("the simulation budget is below one playout", empties=empties)
    try:
        root, used, iterations = uct(n, cells, mover, sims, seed=_digest(list(cells)),
                                     deadline=time.perf_counter() + _seconds(budget))
    except _OutOfBudget:
        return _unknown("UCT did not spend its simulation budget within the latency budget")
    out, cert = _root_output(n, root, used, iterations, f"UCT (UCB1, c = {HX_UCT_C}), uniform random playouts")
    return answer(out, cert)


@lru_cache(maxsize=None)
def _hex_masks(n):
    """Bit masks of an n x n board (cell r * n + c is bit r * n + c): all cells, first and last column, Black's
    edges (top, bottom rows) and White's edges (left, right columns)."""
    full = (1 << (n * n)) - 1
    first_col = sum(1 << (r * n) for r in range(n))
    last_col = first_col << (n - 1)
    top, bottom = (1 << n) - 1, ((1 << n) - 1) << (n * (n - 1))
    return full, full & ~first_col, full & ~last_col, {"B": (top, bottom), "W": (first_col, last_col)}


def _grow(n, s):
    """``s`` with every hex neighbour of its cells added."""
    full, not_first, not_last, _ = _hex_masks(n)
    return full & (s | (s >> n) | ((s & not_last) >> (n - 1)) | ((s & not_first) >> 1) | ((s & not_last) << 1)
                   | ((s & not_first) << (n - 1)) | (s << n))


def _flood(n, seed, within):
    s = seed & within
    while True:
        t = _grow(n, s) & within
        if t == s:
            return s
        s = t


def _bit_threats(n, mine, empty, player):
    """Empty cells at which ``player`` (stones ``mine``) joins its edges at once."""
    first, last = _hex_masks(n)[3][player]
    reach_first, reach_last = _flood(n, mine & first, mine), _flood(n, mine & last, mine)
    return (_grow(n, reach_first) | first) & (_grow(n, reach_last) | last) & empty


def _bit_joined(n, mine, player):
    first, last = _hex_masks(n)[3][player]
    return bool(_flood(n, mine & first, mine) & last)


def hex_exact(n, cells, mover, node_cap=HX_SOLVE_NODES):
    """Exact solve (verifier and evaluation; never the solver): the set of the mover's winning moves, by negamax on
    bitboards with a transposition table, with two sound prunings: a player who can join at once wins, and a player
    facing two or more immediate joins by the opponent loses (only one can be blocked), and facing one must block
    it. None when the position is already decided or past the node cap."""
    full = _hex_masks(n)[0]
    black = sum(1 << i for i, v in enumerate(cells) if v == "B")
    white = sum(1 << i for i, v in enumerate(cells) if v == "W")
    if _bit_joined(n, black, "B") or _bit_joined(n, white, "W"):
        return None
    table = {}
    count = [0]
    centre = (n - 1) / 2
    order = [1 << i for i in sorted(range(n * n), key=lambda i: (abs(i // n - centre) + abs(i % n - centre), i))]

    def wins(mine, theirs, player):
        """True if ``player`` (stones ``mine``), to move with nobody joined, wins."""
        key = (mine, theirs)
        hit = table.get(key)
        if hit is not None:
            return hit
        count[0] += 1
        if count[0] > node_cap:
            raise _OutOfBudget
        empty = full & ~(mine | theirs)
        other = _other(player)
        if _bit_threats(n, mine, empty, player):
            result = True
        else:
            threats = _bit_threats(n, theirs, empty, other)
            if threats & (threats - 1):
                result = False
            else:
                options = threats or empty
                result = False
                for bit in order:                              # centre first: wins are found earlier
                    if bit & options and not wins(theirs, mine | bit, other):
                        result = True
                        break
        table[key] = result
        return result
    mine, theirs = (black, white) if mover == "B" else (white, black)
    try:
        out = []
        for i, v in enumerate(cells):
            if v == ".":
                bit = 1 << i
                after = mine | bit
                if _bit_joined(n, after, mover) or ((after | theirs) != full and not wins(theirs, after,
                                                                                          _other(mover))):
                    out.append(i)
        return out
    except _OutOfBudget:
        return None


def hex_flat_mc(data):
    """Baseline: flat Monte Carlo at the same placement budget: playouts are spread round-robin over the legal moves
    (no tree), and the move with the highest win rate is chosen (ties: more playouts, then the lower cell)."""
    n, cells, mover, sims = _hex(data)
    rng = random.Random(f"flat:{_digest(list(cells))}")
    moves = [i for i, v in enumerate(cells) if v == "."]
    empties = len(moves)
    stats = {i: [0, 0] for i in moves}
    used, k = 0, 0
    while used + empties <= sims:
        i = moves[k % empties]
        board = list(cells)
        board[i] = mover
        winner = (mover if _connected(n, board, mover) else _rollout(n, board, _other(mover), rng)) \
            if "." in board else ("B" if _connected(n, board, "B") else "W")
        stats[i][0] += 1
        stats[i][1] += winner == mover
        used += empties
        k += 1
    if not k:
        return None
    best = max(moves, key=lambda i: (stats[i][1] / stats[i][0] if stats[i][0] else -1.0, stats[i][0], -i))
    return {"move": [best // n, best % n], "visits": stats[best][0],
            "value": round(stats[best][1] / max(1, stats[best][0]), 12)}


def _resistance(n, cells, player):
    """Shannon-Anshelevich two-terminal resistance of ``player``'s network: own stones conduct (resistance ~0), empty
    cells cost 1, opponent stones are removed; adjacent cells join through the sum of their resistances; one
    terminal joins every cell of the player's first edge, the other every cell of its far edge. Smaller is
    better; infinite when the player cannot join."""
    import numpy as np
    cost = {player: 1e-3, ".": 1.0}
    nodes = [i for i, v in enumerate(cells) if v != _other(player)]
    index = {c: k for k, c in enumerate(nodes)}
    size = len(nodes) + 2
    source, sink = size - 2, size - 1
    lap = np.zeros((size, size))

    def link(a, b, r):
        g = 1.0 / r
        lap[a, a] += g
        lap[b, b] += g
        lap[a, b] -= g
        lap[b, a] -= g
    adj = _hex_adjacency(n)
    for c in nodes:
        for d in adj[c]:
            if d > c and d in index:
                link(index[c], index[d], cost[cells[c]] + cost[cells[d]])
        r, col = divmod(c, n)
        first, last = (r == 0, r == n - 1) if player == "B" else (col == 0, col == n - 1)
        if first:
            link(index[c], source, cost[cells[c]])
        if last:
            link(index[c], sink, cost[cells[c]])
    keep = [k for k in range(size) if k != sink]                       # ground the sink
    reduced = lap[np.ix_(keep, keep)]
    rhs = np.zeros(len(keep))
    rhs[keep.index(source)] = 1.0                                      # unit current into the source
    try:
        volts = np.linalg.solve(reduced, rhs)
    except np.linalg.LinAlgError:
        return float("inf")
    value = float(volts[keep.index(source)])
    return value if math.isfinite(value) and value < 1e9 else float("inf")


def _hex_eval(n, cells, player):
    """log(opponent resistance / own resistance), from ``player``'s side."""
    mine, theirs = _resistance(n, cells, player), _resistance(n, cells, _other(player))
    if mine == float("inf"):
        return -50.0
    if theirs == float("inf"):
        return 50.0
    return math.log(theirs / mine)


def hex_alphabeta(data):
    """Competitor: iterative-deepening negamax alpha-beta with the Shannon-Anshelevich resistance evaluation (the
    classical pre-MCTS Hex design, Anshelevich 2000 / Six), principal move searched first, at the same placement
    budget (every placement in the search counts one) and a 10 s wall-clock cap; the best move of the deepest
    completed iteration is chosen."""
    n, cells, mover, sims = _hex(data)
    moves = [i for i, v in enumerate(cells) if v == "."]
    used = [0]
    deadline = time.perf_counter() + ARM_SECONDS
    big = 1000.0

    def negamax(board, player, depth, alpha, beta):
        if depth == 0:
            return _hex_eval(n, board, player)
        best = -big
        for i, v in enumerate(board):
            if v != ".":
                continue
            used[0] += 1
            if used[0] > sims or time.perf_counter() > deadline:
                raise _OutOfBudget
            nxt = board[:i] + (player,) + board[i + 1:]
            if _connected(n, nxt, player):
                score = big - 1
            elif "." not in nxt:
                score = -(big - 1)
            else:
                score = -negamax(nxt, _other(player), depth - 1, -beta, -alpha)
            if score > best:
                best = score
            if best > alpha:
                alpha = best
            if alpha >= beta:
                break
        return best
    chosen, order = None, list(moves)
    for depth in range(1, len(moves) + 1):
        try:
            scores = {}
            alpha = -big
            for i in order:
                used[0] += 1
                if used[0] > sims or time.perf_counter() > deadline:
                    raise _OutOfBudget
                nxt = cells[:i] + (mover,) + cells[i + 1:]
                if _connected(n, nxt, mover):
                    scores[i] = big
                elif "." not in nxt:
                    scores[i] = -big
                else:
                    scores[i] = -negamax(nxt, _other(mover), depth - 1, -big, -alpha)
                alpha = max(alpha, scores[i])
        except _OutOfBudget:
            break
        order = sorted(scores, key=lambda i: (-scores[i], i))
        chosen = order[0]
        if scores[chosen] >= big - 1:
            break
    if chosen is None:
        return None
    return {"move": [chosen // n, chosen % n], "visits": 0, "value": 0.0}


def mcts_verify(data, output, certificate):
    n, cells, mover, sims = _hex(data)
    if (not isinstance(output, dict) or set(output) != {"move", "visits", "value"} or not isinstance(output["move"], list)
            or len(output["move"]) != 2 or not all(type(x) is int for x in output["move"])
            or type(output["visits"]) is not int or type(output["value"]) not in (int, float)):
        return {"output_shape": False}
    certificate = _cert(certificate)
    r, c = output["move"]
    move = r * n + c
    checks = {"output_shape": True, "move_is_legal": 0 <= r < n and 0 <= c < n and cells[move] == "."}
    empties = cells.count(".")
    children, iterations, placements = (certificate.get("children"), certificate.get("iterations"),
                                        certificate.get("placements"))
    stats_ok = (isinstance(children, list) and children and type(iterations) is int and type(placements) is int
                and all(isinstance(ch, list) and len(ch) == 4 and all(type(x) is int for x in ch) for ch in children))
    if stats_ok:
        cells_seen = [ch[0] * n + ch[1] for ch in children]
        stats_ok = (len(set(cells_seen)) == len(cells_seen)
                    and all(0 <= ch[0] < n and 0 <= ch[1] < n and cells[ch[0] * n + ch[1]] == "."
                            and 1 <= ch[2] and 0 <= ch[3] <= ch[2] for ch in children)
                    and sum(ch[2] for ch in children) == iterations
                    and placements == iterations * empties <= sims)
    checks["root_statistics_consistent_with_the_budget"] = bool(stats_ok)
    if stats_ok:
        top = max(ch[2] for ch in children)
        mine = [ch for ch in children if ch[0] * n + ch[1] == move]
        checks["move_is_a_most_visited_child"] = bool(mine) and mine[0][2] == top == output["visits"]
        checks["value_recomputed"] = bool(mine) and abs(output["value"] - mine[0][3] / mine[0][2]) <= 1e-9
    else:
        checks["move_is_a_most_visited_child"] = checks["value_recomputed"] = False
    if empties <= HX_VERIFY_EMPTIES and checks["move_is_legal"]:
        winning = hex_exact(n, cells, mover)
        checks["move_wins_when_a_win_exists_by_exact_solve"] = winning is not None and (not winning
                                                                                        or move in winning)
    return checks


def mcts_instance(seed):
    """Positions from seeded uniform random play on 6x6 and 7x7 boards, stopped with 17-20 empty cells. A position is
    kept only when nobody has joined, the mover cannot join at once and faces no immediate join (no one-move
    tactics), the mover has a winning move, and at most half of the mover's moves win (the choice matters). Truth
    is the exact set of winning moves (``hex_exact``)."""
    r = random.Random(f"genome:search_mcts:{seed}")
    n = (6, 7)[seed % 2]
    full = _hex_masks(n)[0]
    while True:
        empties = r.randint(17, 20)
        order = list(range(n * n))
        r.shuffle(order)
        cells, player = ["."] * (n * n), "B"
        for i in order[:n * n - empties]:
            cells[i] = player
            player = _other(player)
        cells = tuple(cells)
        mine = sum(1 << i for i, v in enumerate(cells) if v == player)
        theirs = sum(1 << i for i, v in enumerate(cells) if v == _other(player))
        empty = full & ~(mine | theirs)
        if (_bit_joined(n, mine, player) or _bit_joined(n, theirs, _other(player))
                or _bit_threats(n, mine, empty, player) or _bit_threats(n, theirs, empty, _other(player))):
            continue
        winning = hex_exact(n, cells, player)
        if winning is None or not winning or 2 * len(winning) > empties:
            continue
        rows = ["".join(cells[k * n:(k + 1) * n]) for k in range(n)]
        data = {"hex_size": n, "hex_stones": rows, "to_move": player, "simulation_budget": HX_BENCH_BUDGET}
        return data, {"winning_moves": winning}


def mcts_subregion(data):
    n, cells, _, _ = _hex(data)
    return f"{n}x{n}"


def mcts_score(data, truth, output):
    if not isinstance(output, dict) or "move" not in output:
        return {"quality": 0.0, "category": "abstain"}
    n, cells, _, _ = _hex(data)
    move = output.get("move")
    if (not isinstance(move, list) or len(move) != 2 or not all(type(x) is int and 0 <= x < n for x in move)
            or cells[move[0] * n + move[1]] != "."):
        return {"quality": -1.0, "category": "wrong"}
    ok = move[0] * n + move[1] in truth["winning_moves"]
    return {"quality": 1.0 if ok else 0.0, "category": "correct" if ok else "wrong"}


# =================================================================== registration
INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.search.ida_star_puzzle", version="1.0.0", family="search_ida_star", layer=3,
            operation="sliding_puzzle_optimal", epistemic_class="optimization",
            subgeometry="memory-bounded optimal state-space search: shortest plans for 3x3 and 4x4 sliding-tile "
                        "puzzles when the stored search nodes are capped (a deep implicit graph that no frontier-"
                        "storing search fits)",
            source_provenance="Korf (1985) iterative-deepening A*; Hansson, Mayer and Yung (1992) linear conflicts; "
                              "Johnson and Story (1879) parity; stdlib only",
            native_representation="board width, row-major tiles (0 = blank) and a memory budget in stored positions",
            required_inputs=("puzzle_width", "puzzle_tiles", "memory_nodes"),
            output_contract={"solvable": "bool", "moves": "blank moves U/D/L/R or null", "length": "int or null"},
            algorithm_or_runtime="IDA*: depth-first contours of f = g + h with h = Manhattan distance + linear "
                                 "conflicts (both updated incrementally); stores only the current path",
            parameters={"widths": list(SP_WIDTHS), "heuristic": "Manhattan + linear conflicts"},
            composition_inputs=("start and goal configurations of a permutation puzzle",),
            composition_outputs=("optimal move sequence", "plan length"),
            evidence_type="exact_calculation",
            verification_method="the moves replayed from the start must reach the goal with the stated length; an "
                                "unsolvability claim is checked by a different parity formula (cycle parity of the "
                                "permutation against the blank's taxicab parity); optimality is proved by the "
                                "verifier's own exhaustive search: on 3x3 a breadth-first distance table of all "
                                "181,440 solvable positions, on 4x4 a plain-Manhattan depth-first search showing no "
                                "plan two moves shorter exists (all plans of a position share a length parity); the "
                                "plan must be the certificate's witness and fit the memory budget",
            confidence_semantics="exact shortest plan, proved by an independent exhaustive search (fails closed when "
                                 "that search exceeds its node cap)",
            resource_profile="memory O(plan length); time exponential in the plan length (re-expands nodes "
                             "across contours)",
            latency_profile="milliseconds on 3x3; up to seconds on 4x4 plans in the forties (pure Python)",
            known_strengths=("optimal plans with memory linear in the plan length: never runs out of memory where A* "
                             "and breadth-first search do",
                             "independent optimality proof on every answer"),
            known_failure_modes=("re-expands nodes: on easy instances A* with the same heuristic is as good and "
                                 "faster when memory suffices",
                                 "pure-Python node rate (~0.5 M nodes/s): 4x4 plans above ~48 moves exceed a 5 s "
                                 "budget (UNKNOWN)",
                                 "no pattern databases: far weaker than state-of-the-art 15-puzzle solvers",
                                 "the 4x4 optimality proof is itself a search and can exceed its node cap (the check "
                                 "then fails)"),
            counterindications=("graphs that fit in memory with many transpositions (use A* or Dijkstra)",
                                "5x5 and larger puzzles (needs pattern databases or a suboptimal method)",
                                "real-valued edge costs with many distinct f-values (IDA* contours explode)"),
            abstention_conditions=("UNKNOWN when IDA* does not finish within the latency budget",
                                   "a memory budget below the plan length"),
            benchmark_suite="3x3 positions uniform among solvable ones and 4x4 positions by seeded random walks of "
                            "40-80 moves from the goal, memory budget 100,000 stored positions for every arm; truth "
                            "by the verifier's exhaustive search (3x3 breadth-first table, 4x4 plain-Manhattan "
                            "bounded depth-first search), never the solver's code; seeds 0-9 dev, held-out seeds "
                            "fixed by the admission freeze",
            baseline="breadth-first search from the start under the same memory budget (abstains when its stored "
                     "positions would exceed it)",
            competitor="A* with the candidate's own heuristic (Manhattan + linear conflicts) and a closed list under "
                       "the same memory budget (abstains when its stored positions would exceed it)",
            **_common()),
        solve=ida_solve, verify=ida_verify, instance=ida_instance, score=ida_score, baseline=ida_bfs,
        competitor=ida_astar, subregion=ida_subregion, tolerance=1e-9),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.search.beam_flowshop", version="1.0.0", family="search_beam", layer=3,
            operation="flowshop_sequence", epistemic_class="optimization",
            subgeometry="permutation flow-shop sequencing (minimum makespan, one job order on every machine): "
                        "sequencing work through a fixed pipeline of stages",
            source_provenance="Nawaz, Enscore and Ham (1983) insertion; Taillard (1990) insertion acceleration and "
                              "(1993) lower bound; beam search (Lowerre 1976; Ow and Morton 1988); stdlib only",
            native_representation="processing time of each job on each machine (positive integers)",
            required_inputs=("flowshop_times",),
            output_contract={"order": "[job index] (a permutation)", "makespan": "int"},
            algorithm_or_runtime="beam search in NEH's insertion space (jobs by decreasing total time; every "
                                 "surviving partial sequence receives the next job at every position, scored by "
                                 "Taillard-accelerated partial makespans), width = 2,000,000 / (jobs^2 x machines) "
                                 f"clipped to [4, {FS_MAX_WIDTH}], with the greedy (NEH) chain anchored in the beam",
            parameters={"work": FS_WORK, "max_width": FS_MAX_WIDTH, "native_jobs": FS_NATIVE_JOBS,
                        "native_machines": FS_NATIVE_MACHINES},
            composition_inputs=("job routings with stage times",), composition_outputs=("job order", "makespan"),
            evidence_type="heuristic_trace",
            verification_method="the order must be a permutation of the jobs; the makespan is recomputed by the "
                                "verifier's own machine-by-machine recurrence; Taillard's lower bound is recomputed "
                                "and must not exceed the makespan; the order must be the certificate's witness",
            confidence_semantics="a valid sequence with exactly the stated makespan, never worse than NEH by "
                                 "construction; no optimality claim (the gap to the lower bound is reported)",
            resource_profile="O(width x jobs^2 x machines) time, O(width x jobs) memory",
            latency_profile="tens of milliseconds to about two seconds at 15-50 jobs (pure Python)",
            known_strengths=("anytime-free and deterministic: never worse than NEH",
                             "widening the beam trades time for quality smoothly"),
            known_failure_modes=("on job-correlated instances the insertion space is flat and the beam ties NEH",
                                 "Iterated Greedy (Ruiz and Stuetzle 2007), the published state of the art for "
                                 "this objective, is neither installed nor in GREG and is not compared",
                                 "the lower bound is weak when machines are balanced, so the reported gap overstates "
                                 "the distance to the optimum"),
            counterindications=("flow shops where jobs may overtake (non-permutation) or with setup times",
                                "due-date objectives (tardiness: use develop_constraint_release)",
                                "small instances that CP-SAT proves optimal quickly"),
            abstention_conditions=(f"more than {FS_NATIVE_JOBS} jobs or {FS_NATIVE_MACHINES} machines",
                                   "UNKNOWN when the beam does not finish within the latency budget"),
            benchmark_suite="Taillard-style U[1, 99] times, job-correlated times and machine-correlated times, 15-50 "
                            "jobs on 5-20 machines; quality is Taillard's lower bound over the recomputed makespan; "
                            "seeds 0-9 dev, held-out seeds fixed by the admission freeze",
            baseline="NEH (the textbook constructive heuristic; the beam at width 1)",
            competitor="OR-Tools CP-SAT on the permutation flow-shop model (intervals, no overlap per machine, a "
                       "shared order literal per job pair), warm-started from NEH, one worker, 2 s; the better of "
                       "its best sequence and the warm start", dependency=None, **_common()),
        solve=fs_solve, verify=fs_verify, instance=fs_instance, score=fs_score, baseline=fs_neh,
        competitor=fs_cpsat, subregion=fs_subregion, tolerance=1e-9),
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="solver.search.mcts_hex", version="1.0.0", family="search_mcts", layer=3,
            operation="hex_move_select", epistemic_class="strategic",
            subgeometry="move selection in a two-player connection game (Hex) with a simulator and a placement "
                        "budget: a large branching factor and no reliable static evaluation",
            source_provenance="Kocsis and Szepesvari (2006) UCT; Auer, Cesa-Bianchi and Fischer (2002) UCB1; Hex "
                              "(Hein 1942, Nash 1948); stdlib only",
            native_representation="board size, rows of '.', 'B', 'W' (Black joins top and bottom, White left and "
                                  "right), the player to move and a budget of stone placements",
            required_inputs=("hex_size", "hex_stones", "to_move", "simulation_budget"),
            output_contract={"move": "[row, column]", "visits": "int (playouts through the move)",
                             "value": "float (the move's playout win rate)"},
            algorithm_or_runtime=f"UCT: UCB1 selection (c = {HX_UCT_C}), one expansion per iteration, uniform "
                                 "random playouts to a full board, most-visited root child; each iteration places "
                                 "as many stones as the root has empty cells",
            parameters={"exploration": HX_UCT_C, "verify_exact_empties": HX_VERIFY_EMPTIES},
            composition_inputs=("a game or sequential decision with a simulator",),
            composition_outputs=("move", "playout statistics"),
            evidence_type="simulation",
            verification_method="the move must be legal; the reported root statistics must be consistent (distinct "
                                "legal children, visits summing to the iterations, placements = iterations x empty "
                                "cells within the budget, the move a most-visited child with the stated visits and "
                                "win rate); for positions with at most 20 empty cells the verifier's own exact "
                                "negamax solve (bitboards, transposition table, sound immediate-win and forced-block "
                                "pruning; a node cap after which the check fails) requires the move to win whenever "
                                "some move wins",
            confidence_semantics="a sampled estimate: the win rate is of uniform random playouts, not of best play; "
                                 "the exact check, where it applies, is what certifies the move",
            resource_profile="the declared placement budget plus the tree (one node per iteration)",
            latency_profile="about 0.1 s at 60,000 placements on 6x6 and 7x7 (pure Python)",
            known_strengths=("needs only the rules (a simulator), no evaluation function",
                             "concentrates playouts on promising lines, so it reads replies that flat Monte Carlo "
                             "averages away"),
            known_failure_modes=("plain UCT without RAVE or priors: weak on large boards at small budgets",
                                 "random playouts misjudge positions decided by deep forcing sequences",
                                 "on the development positions flat Monte Carlo was almost as good (see the v7 "
                                 "draft): the edge over the simple baseline is not established"),
            counterindications=("games with a reliable static evaluation and shallow tactics (alpha-beta)",
                                "positions small enough to solve exactly within the budget (solve them)",
                                "one-player problems with a known model (dynamic programming)"),
            abstention_conditions=("a budget below one playout", "a decided game",
                                   "UNKNOWN when the budget is not spent within the latency budget"),
            benchmark_suite="positions from seeded uniform random play on 6x6 and 7x7 boards with 17-20 empty cells, "
                            "no immediate win or threat, a won position for the mover with at most half of its moves "
                            "winning; 60,000 placements for every arm; truth by the exact solve (evaluation and "
                            "verifier code, never the solver's); seeds 0-9 dev, held-out seeds fixed by the "
                            "admission freeze",
            baseline="flat Monte Carlo at the same placement budget (playouts spread round-robin over the moves, "
                     "best win rate)",
            competitor="iterative-deepening alpha-beta with the Shannon-Anshelevich resistance evaluation (the "
                       "classical pre-MCTS Hex design) at the same placement budget and a 10 s cap; no Hex engine is "
                       "installed", **_common()),
        solve=mcts_solve, verify=mcts_verify, instance=mcts_instance, score=mcts_score, baseline=hex_flat_mc,
        competitor=hex_alphabeta, subregion=mcts_subregion, tolerance=1e-9),
]
