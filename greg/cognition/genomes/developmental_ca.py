"""Layer 4 developmental intelligence: cellular-automaton regeneration of a damaged rule-generated pattern.

The 2026-10-21 coverage record (``docs/collaboration/MIND-COVERAGE-2026-10-21.json``, ``L4.now.cellular_automata``)
lists cellular automata as ABSENT (``develop_repair``'s lattice rules repair a routing field, not a pattern). Effect,
not metaphor: restore the lost part of a structure from its own generative rule and the intact remainder, by purely
local rules, and restore only what is determined: never fill a gap with a plausible guess.

Native geometry: the space-time pattern of an elementary cellular automaton (Wolfram rule numbering, periodic rows;
row t+1 is the rule applied to row t), with holes erased (cells set to '?'). The rule is declared in the request: it
is the structure's "genome"; the original pattern is hidden.

* ``develop_ca_repair`` (``regenerate_rule_pattern``): a synchronous cellular automaton of radius 1 in space and 1 in
  time. Each erased cell reads only the up to four rule windows it belongs to (as the child of three cells above, and
  as one of the three parents of the cells below); in each round a cell takes a value when every other value is
  inconsistent with some window given its neighbours' current states. Rounds repeat until nothing changes; cells
  never determined stay '?'. Forward regeneration (from parents), backward inference (from children, for permutive
  rules) and lateral inference all fall out of the one local rule.
  Verified by an independent replay of the recorded rounds: for every restored cell, at its round, the other value
  must be refuted by a window containing it (exhaustive enumeration of that window's unknown members), so every
  restored value is entailed by the rule and the intact cells; the output must be exactly the replayed grid.

Honest expectation, stated before any held-out run: a central global solver over all the constraints at once (Z3,
the competitor) determines every entailed cell, a superset of what local propagation can reach, so the local rule can
tie it but never beat it on what is restored; where both restore the same cells the question is cost.

Everything is read-only computation: no files, network, subprocesses or environment access, and no output of any
method here creates authority. Development seeds 0-9 only.
"""
from __future__ import annotations

from itertools import product
import random
import time

from .contract import Executable, GenomeError, IntelligenceGenome, answer, bounded_int

LINEAGE = ("INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION", "INTENT-20261007-VERIFIED-POLYINTELLIGENCE-LIFT",
           "INTENT-20261021-MIND-MAXIMUM-CONTINUATION section 4 (restore the full five-layer scope)",
           "docs/collaboration/MIND-COVERAGE-2026-10-21.json (L4.now.cellular_automata ABSENT; precursor "
           "develop_repair)")
CA_MAX_ROWS, CA_MAX_COLS = 64, 64
CA_Z3_SECONDS = 10.0
UNKNOWN = "?"


def _input(data):
    if not isinstance(data, dict):
        raise GenomeError("data must be a JSON object")
    rule = bounded_int(data.get("eca_rule"), low=0, high=255, name="eca_rule")
    grid = data.get("damaged_grid")
    if not isinstance(grid, list) or not 2 <= len(grid) <= CA_MAX_ROWS:
        raise GenomeError(f"damaged_grid: 2-{CA_MAX_ROWS} rows")
    width = len(grid[0]) if isinstance(grid[0], str) else 0
    if not 3 <= width <= CA_MAX_COLS:
        raise GenomeError(f"rows: 3-{CA_MAX_COLS} cells")
    cells = []
    for row in grid:
        if not isinstance(row, str) or len(row) != width or set(row) - {"0", "1", UNKNOWN}:
            raise GenomeError("rows: strings of '0', '1' and '?' of one length")
        cells.append([None if ch == UNKNOWN else int(ch) for ch in row])
    return rule, cells


def _bit(rule, left, centre, right):
    return (rule >> (4 * left + 2 * centre + right)) & 1


def _windows(t, i, height, width):
    """The rule windows containing cell (t, i): child coordinates (t', i') of each window (parents at t'-1)."""
    out = []
    if t >= 1:
        out.append((t, i))
    if t + 1 < height:
        out.extend((t + 1, (i + d) % width) for d in (-1, 0, 1))
    return out


def _members(window, width):
    t, i = window
    return ((t - 1, (i - 1) % width), (t - 1, i), (t - 1, (i + 1) % width), (t, i))


def _consistent(rule, values):
    left, centre, right, child = values
    return _bit(rule, left, centre, right) == child


def _possible(rule, grid, cell, window, width):
    """Values of ``cell`` consistent with ``window`` for some completion of the window's other unknown members."""
    members = _members(window, width)
    free = [m for m in members if grid[m[0]][m[1]] is None and m != cell]
    out = set()
    for v in (0, 1):
        for fill in product((0, 1), repeat=len(free)):
            assign = dict(zip(free, fill))
            assign[cell] = v
            vals = [assign[m] if m in assign else grid[m[0]][m[1]] for m in members]
            if _consistent(rule, vals):
                out.add(v)
                break
    return out


def _known_consistent(rule, grid):
    height, width = len(grid), len(grid[0])
    for t in range(1, height):
        for i in range(width):
            vals = [grid[a][b] for a, b in _members((t, i), width)]
            if None not in vals and not _consistent(rule, vals):
                return False
    return True


def _render(grid):
    return ["".join(UNKNOWN if v is None else str(v) for v in row) for row in grid]


def ca_solve(data, budget):
    rule, grid = _input(data)
    if not _known_consistent(rule, grid):
        return answer(None, {"reason": "inconsistent"}, status="UNKNOWN",
                      missing=["the intact cells contradict the declared rule: nothing can be regenerated"])
    height, width = len(grid), len(grid[0])
    unknown = {(t, i) for t in range(height) for i in range(width) if grid[t][i] is None}
    rounds = []
    while unknown:
        decided = []
        for cell in sorted(unknown):
            possible = {0, 1}
            for window in _windows(cell[0], cell[1], height, width):
                possible &= _possible(rule, grid, cell, window, width)
                if len(possible) <= 1:
                    break
            if not possible:
                return answer(None, {"reason": "inconsistent"}, status="UNKNOWN",
                              missing=["no value of an erased cell is consistent with the rule"])
            if len(possible) == 1:
                decided.append((cell, possible.pop()))
        if not decided:
            break
        for (t, i), v in decided:                           # synchronous: all decided from the same state
            grid[t][i] = v
            unknown.discard((t, i))
        rounds.append([[t, i, v] for (t, i), v in decided])
    restored = sum(len(r) for r in rounds)
    return answer({"grid": _render(grid), "restored": restored, "undetermined": len(unknown)},
                  {"method": "synchronous local-rule CA: a cell takes the only value consistent with its rule windows",
                   "rounds": rounds})


def _refuted(rule, grid, cell, value, width):
    """Independent check: some window containing ``cell`` has no completion with ``cell`` = ``value``."""
    height = len(grid)
    t, i = cell
    windows = []
    if t >= 1:
        windows.append((t, i))
    if t + 1 < height:
        windows += [(t + 1, (i - 1) % width), (t + 1, i), (t + 1, (i + 1) % width)]
    for (wt, wi) in windows:
        coords = [(wt - 1, (wi - 1) % width), (wt - 1, wi), (wt - 1, (wi + 1) % width), (wt, wi)]
        options = [[value] if c == cell else ([0, 1] if grid[c[0]][c[1]] is None else [grid[c[0]][c[1]]])
                   for c in coords]
        if not any(((rule >> (4 * a + 2 * b + c)) & 1) == d for a, b, c, d in product(*options)):
            return True
    return False


def ca_verify(data, output, certificate):
    rule, grid = _input(data)
    height, width = len(grid), len(grid[0])
    if (not isinstance(output, dict) or set(output) != {"grid", "restored", "undetermined"}
            or not isinstance(output["grid"], list) or len(output["grid"]) != height
            or not all(isinstance(row, str) and len(row) == width and not set(row) - {"0", "1", UNKNOWN}
                       for row in output["grid"])):
        return {"output_shape": False}
    rounds = certificate.get("rounds") if isinstance(certificate, dict) else None
    if not isinstance(rounds, list) or not all(
            isinstance(rd, list) and rd and all(isinstance(c, list) and len(c) == 3 and all(type(x) is int for x in c)
                                                and 0 <= c[0] < height and 0 <= c[1] < width and c[2] in (0, 1)
                                                for c in rd) for rd in rounds):
        return {"output_shape": True, "rounds_well_formed": False}
    entailed = True
    state = [row[:] for row in grid]
    for rd in rounds:
        for t, i, v in rd:
            if state[t][i] is not None or not _refuted(rule, state, (t, i), 1 - v, width):
                entailed = False
        if not entailed:
            break
        for t, i, v in rd:
            state[t][i] = v
    restored = sum(1 for t in range(height) for i in range(width) if grid[t][i] is None and state[t][i] is not None)
    return {"output_shape": True, "rounds_well_formed": True, "intact_cells_consistent": _known_consistent(rule, grid),
            "every_restored_cell_is_entailed": entailed,
            "output_is_the_replayed_grid": entailed and output["grid"] == _render(state),
            "counts_recomputed": entailed and output["restored"] == restored
            and output["undetermined"] == sum(row.count(None) for row in state)}


def ca_score(data, truth, output):
    """Quality: (restored cells equal to the original - restored cells that differ) / erased cells. Wrong if any
    restored cell differs or any intact cell is changed; abstain when nothing is restored."""
    rule, grid = _input(data)
    erased = sum(row.count(None) for row in grid)
    if output is None:
        return {"quality": 0.0, "category": "abstain"}
    rows = output.get("grid") if isinstance(output, dict) else None
    if (not isinstance(rows, list) or len(rows) != len(grid)
            or not all(isinstance(r, str) and len(r) == len(grid[0]) for r in rows)):
        return {"quality": -1.0, "category": "wrong"}
    good = bad = 0
    for t, row in enumerate(grid):
        for i, v in enumerate(row):
            got = rows[t][i]
            if v is not None:
                if got != str(v):
                    return {"quality": -1.0, "category": "wrong"}
            elif got != UNKNOWN:
                if got == truth["grid"][t][i]:
                    good += 1
                else:
                    bad += 1
    quality = (good - bad) / max(1, erased)
    return {"quality": quality, "category": "wrong" if bad else ("correct" if good else "abstain")}


def ca_no_repair(data):
    """Baseline: no regeneration; the damaged grid is returned as it is."""
    rule, grid = _input(data)
    return {"grid": _render(grid), "restored": 0, "undetermined": sum(row.count(None) for row in grid)}


def ca_global_z3(data):
    """Competitor: the central global solver. Every rule window becomes one Z3 constraint over the erased cells; a
    model is found, and each erased cell is restored exactly when the opposite value is unsatisfiable (entailed by
    all the constraints together). One 10 s budget: cells not decided in time stay '?'."""
    import z3
    rule, grid = _input(data)
    height, width = len(grid), len(grid[0])
    ctx = z3.Context()
    var = {(t, i): z3.Bool(f"c{t}_{i}", ctx) for t in range(height) for i in range(width) if grid[t][i] is None}

    def term(t, i):
        return var.get((t, i), z3.BoolVal(bool(grid[t][i]), ctx))
    s = z3.Solver(ctx=ctx)
    s.set("random_seed", 0)
    for t in range(1, height):
        for i in range(width):
            members = _members((t, i), width)
            if not any(m in var for m in members):
                continue
            l, c, r, child = (term(*m) for m in members)
            table = [z3.And(l == bool(a), c == bool(b), r == bool(d))
                     for a, b, d in product((0, 1), repeat=3) if _bit(rule, a, b, d)]
            s.add(child == (z3.Or(table) if table else z3.BoolVal(False, ctx)))
    deadline = time.perf_counter() + CA_Z3_SECONDS
    s.set("timeout", int(CA_Z3_SECONDS * 1000))
    if s.check() != z3.sat:
        return None
    model = s.model()
    out = [row[:] for row in grid]
    for (t, i), x in sorted(var.items()):
        left = deadline - time.perf_counter()
        if left <= 0.01:
            break
        value = z3.is_true(model.eval(x, model_completion=True))
        s.push()
        s.set("timeout", max(1, int(left * 1000)))
        s.add(x != value)
        if s.check() == z3.unsat:
            out[t][i] = int(value)
        s.pop()
    restored = sum(1 for (t, i) in var if out[t][i] is not None)
    return {"grid": _render(out), "restored": restored, "undetermined": len(var) - restored}


CA_RULES = (18, 22, 30, 45, 54, 57, 60, 73, 90, 105, 110, 122, 126, 137, 146, 150, 184)


def ca_instance(seed):
    r = random.Random(f"genome:develop_ca_repair:{seed}")
    width, height = r.randint(16, 40), r.randint(12, 30)
    rule = r.choice(CA_RULES)
    rows = [[r.randint(0, 1) for _ in range(width)]]
    for _ in range(height - 1):
        prev = rows[-1]
        rows.append([_bit(rule, prev[(i - 1) % width], prev[i], prev[(i + 1) % width]) for i in range(width)])
    damaged = [row[:] for row in rows]
    for _ in range(r.randint(1, 4)):                       # rectangular holes, anywhere (row 0 included)
        h, w = r.randint(2, 8), r.randint(2, 8)
        top, left = r.randrange(height), r.randrange(width)
        for t in range(top, min(height, top + h)):
            for i in range(left, left + w):
                damaged[t][i % width] = None
    salt = r.uniform(0.0, 0.04)                            # scattered single-cell erasures
    for t in range(height):
        for i in range(width):
            if r.random() < salt:
                damaged[t][i] = None
    data = {"eca_rule": rule, "damaged_grid": _render(damaged)}
    return data, {"grid": _render(rows), "rule": rule, "top": any(v is None for v in damaged[0])}


def ca_subregion(data):
    """Whether the first row (which only backward inference can restore) is damaged, from the data alone."""
    return "first_row_damaged" if UNKNOWN in data["damaged_grid"][0] else "first_row_intact"


INTELLIGENCES = [
    Executable(
        genome=IntelligenceGenome(
            intelligence_id="developmental.ca.local_rule_regeneration", version="1.0.0", family="develop_ca_repair",
            layer=4, operation="regenerate_rule_pattern", epistemic_class="deductive",
            subgeometry="regeneration of erased cells of an elementary cellular automaton's space-time pattern from "
                        "the declared rule and the intact cells",
            source_provenance="von Neumann and Ulam cellular automata; Wolfram (1983) elementary CA rule numbering; "
                              "local constraint propagation (arc consistency, Mackworth 1977) run as a synchronous CA",
            native_representation="eca_rule (0-255, Wolfram numbering) and damaged_grid: rows of '0'/'1'/'?', row "
                                  "t+1 the rule applied to row t, periodic in space",
            required_inputs=("eca_rule", "damaged_grid"),
            output_contract={"grid": "rows with every entailed cell restored; undetermined cells stay '?'",
                             "restored": "cells restored", "undetermined": "erased cells left '?'"},
            algorithm_or_runtime="synchronous rounds: each erased cell intersects the values its (at most four) rule "
                                 "windows allow given the neighbours' current states and takes the value when one "
                                 "remains; until a round decides nothing",
            parameters={"radius_space": 1, "radius_time": 1},
            memory_model="the grid itself (each cell's state); nothing persists across requests",
            learning_rule="none (the rule is declared)",
            composition_inputs=("a structure generated by a known local rule", "its damaged observation"),
            composition_outputs=("the regenerated structure", "the cells that cannot be determined"),
            evidence_type="developmental_trace",
            verification_method="independent replay of the rounds: each restored cell's other value refuted by "
                                "exhaustive enumeration of one of its windows at that round, intact cells consistent "
                                "with the rule, output equal to the replayed grid and counts recomputed",
            confidence_semantics="every restored cell is entailed by the rule and the intact cells (certain if the "
                                 "intact cells are correct); '?' means local propagation could not decide it, not "
                                 "that it is undetermined globally",
            resource_profile="O(rounds x erased cells x 4 windows x 8 completions)",
            latency_profile="milliseconds to ~0.1 s",
            known_strengths=("purely local: each cell reads its rule windows only, so it parallelises and survives "
                             "loss of any distant part", "restores only entailed values: never a wrong cell",
                             "regenerates interior holes completely in forward rounds"),
            known_failure_modes=("weaker than global inference: cells entailed only by long chains of constraints "
                                 "through other unknowns stay '?'; a global solver restores them",
                                 "a damaged first row can be restored only by backward inference, which works for "
                                 "permutive rules (30, 45, 90, 105, 150, ...) and largely fails for others",
                                 "intact cells that are themselves corrupted (not erased) make it refuse "
                                 "(inconsistent) rather than repair"),
            counterindications=("patterns not generated by a known local rule", "damage by corruption rather than "
                                "erasure", "requests needing every globally entailed cell (use the global solver)"),
            abstention_conditions=("UNKNOWN when the intact cells contradict the declared rule",),
            benchmark_suite="space-time patterns of 17 elementary rules (18, 22, 30, 45, 54, 57, 60, 73, 90, 105, 110, "
                            "122, 126, 137, 146, 150, 184), 16-40 cells by 12-30 rows from a random first row; 1-4 "
                            "rectangular holes of 2-8 by 2-8 placed anywhere (the first row included) plus 0-4% "
                            "scattered erasures; quality is (correctly restored - wrongly restored) / erased cells "
                            "against the hidden original; seeds 0-9 dev, held-out seeds fixed by the admission freeze",
            baseline="no repair: the damaged grid is returned as it is",
            competitor="central global solver: Z3 over every rule window at once, restoring each erased cell whose "
                       "opposite value is unsatisfiable (10 s)",
            dependency=None, buildability="BUILDABLE_NOW", lineage=LINEAGE),
        solve=ca_solve, verify=ca_verify, instance=ca_instance, score=ca_score, baseline=ca_no_repair,
        competitor=ca_global_z3, subregion=ca_subregion, tolerance=1e-9),
]
