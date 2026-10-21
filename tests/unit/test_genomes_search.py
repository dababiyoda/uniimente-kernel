"""Layer 3 search genomes (IDA* on sliding puzzles, beam search on flow shops, UCT on Hex): contract, withheld
registration, canonical path, Competency Compiler reachability, independent verification, refutation of corrupted
answers and forged certificates, invalid input and scoring.

Development seeds 0-9 only; held-out admission seeds are never generated here.
"""
from __future__ import annotations

import copy
from functools import lru_cache
import json
import math
import random

import pytest

from greg.cognition import catalog
from greg.cognition.genomes import library, search
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

ITEMS = {x.genome.family: x for x in search.INTELLIGENCES}
FAMILIES = tuple(sorted(ITEMS))
SPEC = {  # family: (layer, operation, epistemic class, evidence type, dependency)
    "search_ida_star": (3, "sliding_puzzle_optimal", "optimization", "exact_calculation", None),
    "search_beam": (3, "flowshop_sequence", "optimization", "heuristic_trace", None),
    "search_mcts": (3, "hex_move_select", "strategic", "simulation", None),
}
# development seeds whose instances are cheap to build and solve (the 4x4 IDA* seeds with plans in the forties and
# the Hex positions that need many rejected draws are left to ``admission --dev``)
QUICK = {"search_ida_star": (0, 2, 3, 5, 6, 8), "search_beam": (0, 1, 2, 8), "search_mcts": (6, 8)}
BUDGET = {"latency_s": 8.0, "compute": 100000}
_CACHE: dict = {}


def dev(family, seed):
    assert 0 <= seed < 10                                      # never a held-out seed
    key = (family, seed)
    if key not in _CACHE:
        _CACHE[key] = ITEMS[family].instance(seed)
    data, truth = _CACHE[key]
    return copy.deepcopy(data), truth


def solved(family, seed):
    key = ("solved", family, seed)
    if key not in _CACHE:
        data, _ = dev(family, seed)
        _CACHE[key] = ITEMS[family].solve(data, BUDGET)
    data, truth = dev(family, seed)
    return data, truth, copy.deepcopy(_CACHE[key])


def _json_clean(value):
    if isinstance(value, float):
        assert math.isfinite(value)
    elif isinstance(value, dict):
        assert all(isinstance(k, str) for k in value)
        for v in value.values():
            _json_clean(v)
    elif isinstance(value, list):
        for v in value:
            _json_clean(v)
    else:
        assert value is None or isinstance(value, (str, int, bool))


def _all(family, data, output, cert):
    return all(ITEMS[family].verify(data, output, cert).values())


# ------------------------------------------------------------------ genome contract and registration
def test_genomes_validate_with_declared_identity():
    assert set(FAMILIES) == set(SPEC)
    for family, x in ITEMS.items():
        g = x.genome
        assert isinstance(g, IntelligenceGenome) and g.validate() is g
        assert (g.layer, g.operation, g.epistemic_class, g.evidence_type, g.dependency) == SPEC[family]
        assert g.buildability == "BUILDABLE_NOW" and g.standalone_decision and g.version == "1.0.0"
        assert g.authority_ceiling == g.consequence_limit == "read_only"
        assert "INTENT-20261007-POLYINTELLIGENCE-MIND-CONTINUATION" in g.lineage
        assert g.known_failure_modes and g.counterindications and g.abstention_conditions
        assert g.baseline and g.competitor and x.subregion is not None and x.competitor_deployable
        assert "seeds 0-9 dev" in g.benchmark_suite


def test_registered_in_the_one_catalog_and_withheld():
    families = library.executables()
    for family in FAMILIES:
        assert families[family] is ITEMS[family]
        g = ITEMS[family].genome
        assert catalog.FAMILIES[family] == (g.layer, (g.operation,), (g.epistemic_class,), "genome_certificate",
                                            g.dependency)
        assert catalog.initial_state(f"cognition.{family}") == "VERIFIED"      # registered, never auto-attached


def test_module_imports_no_heavy_package_at_top_level():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(search))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top for a in n.names} | {
        n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"numpy", "scipy", "networkx", "ortools", "z3"}


# ------------------------------------------------------------------ solve / verify on development seeds
@pytest.mark.parametrize("family,seed", [(f, s) for f in FAMILIES for s in QUICK[f]])
def test_solve_answers_compactly_and_its_answer_verifies(family, seed):
    data, truth, out = solved(family, seed)
    assert out["status"] == "ANSWER", out["missing"]
    _json_clean(out["output"])
    _json_clean(out["certificate"])
    assert len(json.dumps(out, allow_nan=False)) < 64 * 1024
    json.dumps(data, allow_nan=False)
    checks = ITEMS[family].verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    score = ITEMS[family].score(data, truth, out["output"])
    assert score["category"] == "correct"
    if family == "search_ida_star":
        assert score["quality"] == 1.0 and out["output"]["length"] == truth["optimum"]


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_path_withholds_until_attached_and_creates_no_authority(family):
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    data, truth = dev(family, QUICK[family][0])
    request = {"problem_id": f"search-{family}", "operation": SPEC[family][1], "data": data,
               "geometry": {"latency_limit": 30}}
    assert reason(request, registry=registry)["abstention_state"] == "CAPABILITY_DEFICIT"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["abstention_state"] == "NONE" and r["proof_type"] == "genome_certificate"
    assert r["proof_artifact"]["evidence_type"] == SPEC[family][3]
    assert r["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED" and r["authority_created"] is False
    assert ITEMS[family].score(data, truth, r["output"])["category"] == "correct"


@pytest.mark.parametrize("family", FAMILIES)
def test_the_competency_compiler_reaches_the_family_by_its_inputs(family, tmp_path, monkeypatch):
    """Evaluation only: an in-memory attach (no body, journal or founder pin) and an empty evidence index."""
    from greg.cognition import compiler
    from greg.cognition.cortex import reason, registry_view
    monkeypatch.setattr(compiler, "EVIDENCE_INDEX", tmp_path / "index.json")
    data, truth = dev(family, QUICK[family][0])
    cls = SPEC[family][2]
    request = {"problem_id": f"search-compile-{family}", "compile": {"geometry": {"geometry": cls}, "data": data}}
    registry = registry_view()
    withheld = reason(request, registry=registry)
    assert withheld["state"] == "CAPABILITY_DEFICIT"
    assert withheld["withheld_best_fit"]["method"] == f"cognition.{family}"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == f"cognition.{family}"
    assert r["methods_considered"] == [f"cognition.{family}"]
    assert r["derived_geometry"]["fits_by_inputs"] == [cls] and r["authority_created"] is False
    assert ITEMS[family].score(data, truth, r["result"])["category"] == "correct"


# ------------------------------------------------------------------ IDA*: independent verification
def test_ida_verifier_refutes_broken_plans_and_a_longer_valid_plan():
    data, truth, out = solved("search_ida_star", 6)                         # a 4x4 instance
    o, cert = out["output"], out["certificate"]
    assert data["puzzle_width"] == 4
    short = {**o, "moves": o["moves"][:-1], "length": o["length"] - 1}
    assert not search.ida_verify(data, short, dict(cert, witness=search._digest(short["moves"]),
                                                   peak_stored_nodes=short["length"] + 1))["moves_reach_the_goal"]
    assert not search.ida_verify(data, {**o, "length": o["length"] + 1}, cert)["length_recomputed"]
    # a valid detour: the blank steps away and back (two extra moves), a forger re-signs its witness
    w = data["puzzle_width"]
    blank = search._replay(w, tuple(data["puzzle_tiles"]), o["moves"]).index(0)
    step = "U" if blank // w > 0 else "D"
    longer = o["moves"] + step + search.OPPOSITE[step]
    forged = {"solvable": True, "moves": longer, "length": len(longer)}
    checks = search.ida_verify(data, forged, dict(cert, witness=search._digest(longer),
                                                  peak_stored_nodes=len(longer) + 1))
    assert checks["moves_reach_the_goal"] and checks["witness_is_the_certified_plan"]
    assert checks["no_shorter_plan"] is False
    assert ITEMS["search_ida_star"].score(data, truth, forged)["category"] == "wrong"


def test_ida_verifier_on_3x3_uses_the_exhaustive_table():
    data, truth, out = solved("search_ida_star", 0)
    assert data["puzzle_width"] == 3
    assert search._distance_table_3x3()[tuple(data["puzzle_tiles"])] == truth["optimum"] == out["output"]["length"]
    assert len(search._distance_table_3x3()) == 181440


def test_ida_unsolvable_claims_are_checked_by_an_independent_parity():
    data, _, out = solved("search_ida_star", 2)
    swapped = list(data["puzzle_tiles"])
    i, j = [k for k, t in enumerate(swapped) if t][:2]
    swapped[i], swapped[j] = swapped[j], swapped[i]                         # one transposition: unsolvable
    bad = {**data, "puzzle_tiles": swapped}
    claim = search.ida_solve(bad, BUDGET)
    assert claim["status"] == "ANSWER" and claim["output"]["solvable"] is False
    assert _all("search_ida_star", bad, claim["output"], claim["certificate"])
    assert not _all("search_ida_star", data, {"solvable": False, "moves": None, "length": None}, {})
    for w in (3, 4):                                                        # the two parity formulas agree
        for seed in range(10):
            tiles = list(range(w * w))
            random.Random(f"parity:{w}:{seed}").shuffle(tiles)
            assert search._solvable(w, tuple(tiles)) == search._parity_solvable(w, tuple(tiles))


def test_ida_memory_claim_and_witness_are_bound():
    data, _, out = solved("search_ida_star", 5)
    o, cert = out["output"], out["certificate"]
    assert not search.ida_verify(data, o, dict(cert, peak_stored_nodes=o["length"]))["within_the_memory_budget"]
    assert not search.ida_verify({**data, "memory_nodes": o["length"]}, o, cert)["within_the_memory_budget"]
    assert not search.ida_verify(data, o, dict(cert, witness="sha256:0"))["witness_is_the_certified_plan"]


def test_ida_memory_budget_binds_breadth_first_and_a_star_but_not_ida():
    data, truth = dev("search_ida_star", 6)
    tight = {**data, "memory_nodes": 200}
    assert search.ida_bfs(tight) is None and search.ida_astar(tight) is None
    out = search.ida_solve(tight, BUDGET)
    assert out["status"] == "ANSWER" and out["output"]["length"] == truth["optimum"]
    assert out["certificate"]["peak_stored_nodes"] == truth["optimum"] + 1


# ------------------------------------------------------------------ beam: independent verification
def test_beam_verifier_recomputes_the_makespan_and_the_bound():
    data, truth, out = solved("search_beam", 0)
    o, cert = out["output"], out["certificate"]
    assert not search.fs_verify(data, {**o, "makespan": o["makespan"] - 1}, cert)["makespan_recomputed"]
    dup = {"order": o["order"][:-1] + o["order"][:1], "makespan": o["makespan"]}
    assert not search.fs_verify(data, dup, cert)["order_is_a_permutation_of_the_jobs"]
    assert not search.fs_verify(data, o, dict(cert, lower_bound=cert["lower_bound"] + 1))["lower_bound_recomputed"]
    assert not search.fs_verify(data, o, dict(cert, witness="sha256:0"))["witness_is_the_certified_order"]
    p = data["flowshop_times"]
    assert search._independent_makespan(p, o["order"]) == search.fs_makespan(p, o["order"]) == o["makespan"]
    assert truth["lower_bound"] == search.fs_lower_bound(p) <= o["makespan"]


@pytest.mark.parametrize("seed", QUICK["search_beam"])
def test_beam_is_never_worse_than_neh_and_width_one_is_neh(seed):
    data, _, out = solved("search_beam", seed)
    p = data["flowshop_times"]
    neh = search.fs_neh(data)
    assert out["output"]["makespan"] <= neh["makespan"]
    order, span, _ = search.flowshop_beam(p, 1)
    assert span == neh["makespan"]


def test_taillard_acceleration_matches_direct_insertion():
    data, _ = dev("search_beam", 1)
    p = data["flowshop_times"]
    order = list(range(0, len(p), 2))
    for j in range(1, len(p), 2)[:3]:
        fast = search._insertion_spans(p, order, j)
        slow = [search.fs_makespan(p, order[:k] + [j] + order[k:]) for k in range(len(order) + 1)]
        assert fast == slow


# ------------------------------------------------------------------ MCTS: independent verification
def _plain_winning_moves(n, cells, mover):
    """A reference solver for tiny positions: plain negamax over full boards, no pruning (test code only)."""
    @lru_cache(maxsize=None)
    def wins(board, player):
        other = search._other(player)
        for i, v in enumerate(board):
            if v == ".":
                nxt = board[:i] + player + board[i + 1:]
                if search._connected(n, nxt, player) or ("." in nxt and not wins(nxt, other)):
                    return True
        return False
    board = "".join(cells)
    out = []
    for i, v in enumerate(board):
        if v == ".":
            nxt = board[:i] + mover + board[i + 1:]
            if search._connected(n, nxt, mover) or ("." in nxt and not wins(nxt, search._other(mover))):
                out.append(i)
    return out


@pytest.mark.parametrize("seed", QUICK["search_mcts"])
def test_exact_hex_solver_agrees_with_a_plain_reference_on_small_continuations(seed):
    data, truth = dev("search_mcts", seed)
    n, cells, mover, _ = search._hex(data)
    empties = [i for i, v in enumerate(cells) if v == "."]
    checked = 0
    for start in range(0, 8):                       # fill all but 9 empty cells in a fixed order, alternating
        board, player = list(cells), mover
        for i in (empties[start:] + empties[:start])[:len(empties) - 9]:
            board[i] = player
            player = search._other(player)
        board = tuple(board)
        if search._connected(n, board, "B") or search._connected(n, board, "W"):
            continue
        assert search.hex_exact(n, board, player) == _plain_winning_moves(n, board, player)
        checked += 1
    assert checked >= 2
    assert search.hex_exact(n, cells, mover) == truth["winning_moves"]


def test_mcts_verifier_refutes_inconsistent_statistics_and_illegal_moves():
    data, truth, out = solved("search_mcts", 6)
    o, cert = out["output"], out["certificate"]
    n = data["hex_size"]
    taken = next([i // n, i % n] for i, v in enumerate("".join(data["hex_stones"])) if v != ".")
    assert not search.mcts_verify(data, {**o, "move": taken}, cert)["move_is_legal"]
    assert not search.mcts_verify(data, {**o, "value": o["value"] + 0.01}, cert)["value_recomputed"]
    assert not search.mcts_verify(data, {**o, "visits": o["visits"] + 1}, cert)["move_is_a_most_visited_child"]
    over = dict(cert, iterations=cert["iterations"] + 1)
    assert not search.mcts_verify(data, o, over)["root_statistics_consistent_with_the_budget"]
    small = {**data, "simulation_budget": cert["placements"] - 1}
    assert not search.mcts_verify(small, o, cert)["root_statistics_consistent_with_the_budget"]
    assert cert["placements"] <= data["simulation_budget"]


def test_mcts_verifier_refutes_a_losing_move_with_forged_consistent_statistics():
    data, truth, out = solved("search_mcts", 8)
    o, cert = out["output"], out["certificate"]
    n, cells, _, _ = search._hex(data)
    losing = next(i for i, v in enumerate(cells) if v == "." and i not in truth["winning_moves"])
    children = [list(ch) for ch in cert["children"]]
    top = max(ch[2] for ch in children)
    leader = next(ch for ch in children if ch[2] == top)
    mine = next(ch for ch in children if ch[0] * n + ch[1] == losing)
    delta = top + 1 - mine[2]
    mine[2], mine[3] = top + 1, 0                                       # the forger makes it most visited
    leader[2] -= delta                                                  # and keeps the visit total
    leader[3] = min(leader[3], leader[2])
    assert leader[2] >= 1
    forged_cert = dict(cert, children=children)
    forged = {"move": [losing // n, losing % n], "visits": top + 1, "value": 0.0}
    checks = search.mcts_verify(data, forged, forged_cert)
    assert checks["root_statistics_consistent_with_the_budget"] and checks["move_is_a_most_visited_child"]
    assert checks["move_wins_when_a_win_exists_by_exact_solve"] is False
    assert ITEMS["search_mcts"].score(data, truth, forged)["category"] == "wrong"


def test_mcts_arms_respect_the_shared_placement_budget():
    data, _ = dev("search_mcts", 6)
    small = {**data, "simulation_budget": 2000}
    out = search.mcts_solve(small, BUDGET)
    assert out["certificate"]["placements"] <= 2000
    assert search.hex_flat_mc(small) is not None
    calls = []
    original = search._hex_eval

    def spy(n, cells, player):
        calls.append(1)
        return original(n, cells, player)
    try:
        search._hex_eval = spy
        search.hex_alphabeta({**data, "simulation_budget": 300})
    finally:
        search._hex_eval = original
    assert len(calls) <= 300


def test_resistance_evaluation_prefers_the_player_closer_to_joining():
    n = 4
    black_line = ("B...", "B...", "B...", "....")                 # Black one stone from joining
    cells = tuple("".join(black_line))
    assert search._resistance(n, cells, "B") < search._resistance(n, cells, "W")
    blocked = tuple("".join(("WWWW", "....", "....", "....")))
    assert search._resistance(n, blocked, "B") == float("inf")


# ------------------------------------------------------------------ invalid input is refused, never crashes
@pytest.mark.parametrize("family,bad", [
    ("search_ida_star", {"puzzle_width": 5, "puzzle_tiles": list(range(25)), "memory_nodes": 10}),
    ("search_ida_star", {"puzzle_width": 3, "puzzle_tiles": [0, 1, 2, 3, 4, 5, 6, 7, 7], "memory_nodes": 10}),
    ("search_ida_star", {"puzzle_width": 3, "puzzle_tiles": list(range(9)), "memory_nodes": 0}),
    ("search_beam", {"flowshop_times": [[1, 2], [3]]}),
    ("search_beam", {"flowshop_times": [[1, 0], [3, 4]]}),
    ("search_beam", {"flowshop_times": [[1, 2]]}),
    ("search_mcts", {"hex_size": 4, "hex_stones": ["....", "....", "....", "..."], "to_move": "B",
                     "simulation_budget": 100}),
    ("search_mcts", {"hex_size": 4, "hex_stones": ["....", "....", "....", "...."], "to_move": "W",
                     "simulation_budget": 100}),
    ("search_mcts", {"hex_size": 4, "hex_stones": ["BB..", "....", "....", "...."], "to_move": "B",
                     "simulation_budget": 100}),
    ("search_mcts", {"hex_size": 4, "hex_stones": ["X...", "....", "....", "...."], "to_move": "W",
                     "simulation_budget": 100}),
])
def test_invalid_input_raises_a_genome_error(family, bad):
    with pytest.raises(GenomeError):
        ITEMS[family].solve(bad, BUDGET)


@pytest.mark.parametrize("family", FAMILIES)
def test_malformed_outputs_are_refuted_not_raised(family):
    data, _ = dev(family, QUICK[family][0])
    for junk in (None, 3, [], {}, {"x": None}, "answer", {"move": ["a", 1], "visits": 1, "value": 0.5},
                 {"order": "abc", "makespan": 1}, {"solvable": True, "moves": 7, "length": 1}):
        checks = ITEMS[family].verify(data, junk, {})
        assert not all(checks.values())


def test_abstentions():
    big = {"flowshop_times": [[1] * 3 for _ in range(search.FS_NATIVE_JOBS + 1)]}
    assert search.fs_solve(big, BUDGET)["status"] == "ABSTAIN"
    data, _ = dev("search_mcts", 6)
    assert search.mcts_solve({**data, "simulation_budget": 3}, BUDGET)["status"] == "ABSTAIN"
    joined = {"hex_size": 4, "hex_stones": ["B...", "BW..", "BW..", "BW.."], "to_move": "W", "simulation_budget": 100}
    assert search.mcts_solve(joined, BUDGET)["status"] == "ABSTAIN"


def test_instances_are_deterministic_by_seed():
    for family in FAMILIES:
        seed = QUICK[family][0]
        assert json.dumps(ITEMS[family].instance(seed)[0], sort_keys=True) == json.dumps(
            ITEMS[family].instance(seed)[0], sort_keys=True)
