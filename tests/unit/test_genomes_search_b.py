"""Search batch B genomes: novelty search on deceptive mazes (L3), a selection hyper-heuristic for large bin packing
(L3) and role differentiation by local lateral inhibition (L4). Contract, withheld registration, canonical path,
Competency Compiler reachability, independent verification, refutation of corrupted answers, references against
independent methods, invalid input and budgets.

Development seeds 0-9 only; held-out admission seeds are never generated here.
"""
from __future__ import annotations

from collections import deque
import copy
import itertools
import json

import pytest

from greg.cognition import catalog
from greg.cognition.genomes import library, search_b
from greg.cognition.genomes.contract import GenomeError, IntelligenceGenome

ITEMS = {x.genome.family: x for x in search_b.INTELLIGENCES}
FAMILIES = tuple(sorted(ITEMS))
SPEC = {  # family: (layer, operation, epistemic class, evidence type, dependency)
    "evo_novelty_search": (3, "deceptive_maze_navigate", "optimization", "heuristic_trace", None),
    "hyper_select_lowlevel": (3, "bin_packing_hyperheuristic", "optimization", "feasibility_witness", None),
    "develop_differentiate": (4, "local_role_differentiation", "constraint_feasibility", "feasibility_witness", None),
}
BUDGET = {"latency_s": 8.0, "compute": 100000}
_CACHE: dict = {}


def dev(family, seed=1):
    assert 0 <= seed < 10                                   # never a held-out seed
    key = (family, seed)
    if key not in _CACHE:
        _CACHE[key] = ITEMS[family].instance(seed)
    data, truth = _CACHE[key]
    return copy.deepcopy(data), truth


def solved(family, seed=1):
    key = ("solved", family, seed)
    if key not in _CACHE:
        data, _ = dev(family, seed)
        _CACHE[key] = ITEMS[family].solve(data, BUDGET)
    data, truth = dev(family, seed)
    return data, truth, copy.deepcopy(_CACHE[key])


def _ok(family, data, output, cert):
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


def test_hyperheuristic_is_distinct_from_the_exact_bin_packing_genome():
    exact = library.executables()["binpack_cpsat"].genome
    hh = ITEMS["hyper_select_lowlevel"].genome
    assert exact.operation != hh.operation and exact.family != hh.family
    assert "binpack_cpsat" in " ".join(hh.counterindications) + " ".join(hh.known_failure_modes)


def test_differentiation_claims_nothing_biological():
    g = ITEMS["develop_differentiate"].genome
    text = json.dumps(g.to_dict()).lower()
    for word in ("cell", "tissue", "embryo", "notch", "organism", "biolog"):
        assert word not in text


def test_module_imports_no_heavy_package_at_top_level():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(search_b))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name.split(".")[0] for n in top for a in n.names} | {
        n.module.split(".")[0] for n in top if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"numpy", "scipy", "networkx", "ortools", "z3"}


# ------------------------------------------------------------------ solve / verify on development seeds
@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("seed", range(10))
def test_solve_answers_and_its_answer_verifies(family, seed):
    data, truth, out = solved(family, seed)
    assert out["status"] == "ANSWER", out["missing"]
    assert len(json.dumps(out, allow_nan=False)) < 256 * 1024
    checks = ITEMS[family].verify(data, out["output"], out["certificate"])
    assert checks and all(checks.values()), checks
    score = ITEMS[family].score(data, truth, out["output"])
    assert score["category"] == "correct" and 0.0 <= score["quality"] <= 1.0 + 1e-12


@pytest.mark.parametrize("family", FAMILIES)
def test_solve_is_deterministic_given_the_seed(family):
    data, _, out = solved(family, 2)
    again = ITEMS[family].solve(data, BUDGET)
    assert again["output"] == out["output"]


@pytest.mark.parametrize("family", FAMILIES)
def test_canonical_path_withholds_until_attached_and_creates_no_authority(family):
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    data, truth = dev(family, 3)
    request = {"problem_id": f"search-b-{family}", "operation": SPEC[family][1], "data": data,
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
    data, truth = dev(family, 1)
    cls = SPEC[family][2]
    request = {"problem_id": f"search-b-compile-{family}", "compile": {"geometry": {"geometry": cls}, "data": data}}
    registry = registry_view()
    withheld = reason(request, registry=registry)
    assert withheld["state"] == "CAPABILITY_DEFICIT"
    assert f"cognition.{family}" in withheld["methods_considered"]
    if family == "hyper_select_lowlevel":
        # the admitted exact genome reads a subset of these inputs and outranks an unevaluated one by evidence
        assert withheld["withheld_best_fit"]["method"] == "cognition.binpack_cpsat"
    else:
        assert withheld["withheld_best_fit"]["method"] == f"cognition.{family}"
    registry.set_state(f"cognition.{family}", "ATTACHED")
    r = reason(request, registry=registry)
    assert r["state"] == "ANSWERED" and r["method_or_composition_selected"] == f"cognition.{family}"
    assert r["authority_created"] is False
    assert ITEMS[family].score(data, truth, r["result"])["category"] == "correct"


# ------------------------------------------------------------------ corruptions: at least six per genome
def _maze_corruptions(o):
    flip = {"U": "D", "D": "U", "L": "R", "R": "L"}
    yield "moves_extra_char", {**o, "moves": o["moves"] + "U"}
    yield "moves_short", {**o, "moves": o["moves"][:-1]}
    yield "moves_bad_symbol", {**o, "moves": "X" + o["moves"][1:]}
    yield "final_shifted", {**o, "final": [o["final"][0] + 1, o["final"][1]]}
    yield "final_short", {**o, "final": o["final"][:1]}
    yield "reached_false", {**o, "reached_at": -1 if o["reached_at"] >= 0 else 1}
    yield "reached_later", {**o, "reached_at": o["reached_at"] + 1}
    i = next(k for k in range(len(o["moves"]))
             if search_b._replay(*_maze_ctx(), o["moves"][:k] + flip[o["moves"][k]] + o["moves"][k + 1:]) !=
             (o["final"], o["reached_at"]))
    yield "one_move_flipped", {**o, "moves": o["moves"][:i] + flip[o["moves"][i]] + o["moves"][i + 1:]}
    yield "not_a_dict", [o["moves"]]


_MAZE = {}


def _maze_ctx():
    rows, start, goal, *_ = search_b._maze(_MAZE["data"])
    return rows, start, goal


def test_novelty_verifier_refutes_eight_corruptions_and_accepts_the_answer():
    data, _, out = solved("evo_novelty_search", 0)
    _MAZE["data"] = data
    o, c = out["output"], out["certificate"]
    assert _ok("evo_novelty_search", data, o, c)
    refuted = [name for name, forged in _maze_corruptions(o) if not _ok("evo_novelty_search", data, forged, c)]
    assert len(refuted) == 9, refuted
    assert not _ok("evo_novelty_search", data, o, {**c, "evaluations_used": data["evaluations"] + 1})


def _packing_corruptions(o):
    p = o["packing"]
    yield "bins_plus_one", {**o, "bins": o["bins"] + 1}
    yield "item_dropped", {**o, "packing": [p[0][:-1]] + p[1:]} if len(p[0]) > 1 else {**o, "packing": p[1:]}
    yield "item_duplicated", {**o, "packing": [p[0] + [p[1][0]]] + p[1:]}
    yield "item_out_of_range", {**o, "packing": [p[0] + [10**6]] + p[1:]}
    merged = sorted(p[0] + p[1])
    yield "two_bins_merged_overfull", {"bins": o["bins"] - 1, "packing": sorted([merged] + p[2:])}
    yield "unsorted_bin", {**o, "packing": [list(reversed(p[0]))] + p[1:]} if len(p[0]) > 1 else {
        **o, "packing": list(reversed(p))}
    yield "unsorted_bins", {**o, "packing": list(reversed(p))}
    yield "empty_bin", {"bins": o["bins"] + 1, "packing": [[]] + p}
    yield "non_int", {**o, "packing": [[float(i) for i in p[0]]] + p[1:]}


def test_hyperheuristic_verifier_refutes_nine_corruptions_and_accepts_the_answer():
    data, _, out = solved("hyper_select_lowlevel", 0)
    o, c = out["output"], out["certificate"]
    assert _ok("hyper_select_lowlevel", data, o, c)
    names = [name for name, forged in _packing_corruptions(o) if not _ok("hyper_select_lowlevel", data, forged, c)]
    assert len(names) == 9, names
    assert not _ok("hyper_select_lowlevel", data, o, {**c, "applications_used": data["heuristic_applications"] + 1})


def _role_corruptions(o, data):
    roles = o["roles"]
    leader = roles.index("leader")
    member = roles.index("member")
    yield "leader_demoted", {**o, "roles": roles[:leader] + ["member"] + roles[leader + 1:]}
    yield "member_promoted", {**o, "roles": roles[:member] + ["leader"] + roles[member + 1:]}
    yield "role_dropped", {**o, "roles": roles[:-1]}
    yield "unknown_role", {**o, "roles": ["chief"] + roles[1:]}
    yield "phases_plus_one", {**o, "phases": o["phases"] + 1, "rounds": o["rounds"] + 2 * data["radius"]}
    yield "rounds_understated", {**o, "rounds": o["rounds"] - 1}
    yield "phases_understated", {**o, "phases": o["phases"] - 1, "rounds": o["rounds"] - 2 * data["radius"]}
    # a different valid pattern (greedy MIS) that the declared local rule did not produce
    yield "other_valid_pattern", {**search_b.df_centralised(data), "phases": o["phases"], "rounds": o["rounds"]}


def test_differentiation_verifier_refutes_eight_corruptions_and_accepts_the_answer():
    data, truth, out = solved("develop_differentiate", 0)
    o, c = out["output"], out["certificate"]
    assert _ok("develop_differentiate", data, o, c)
    forged = dict(_role_corruptions(o, data))
    names = [name for name, f in forged.items() if not _ok("develop_differentiate", data, f, c)]
    assert len(names) == 8, names
    # the greedy pattern is itself valid: refuted only for not following the declared rule
    checks = ITEMS["develop_differentiate"].verify(data, forged["other_valid_pattern"], c)
    assert checks["leaders_more_than_radius_apart"] and checks["every_member_within_radius_of_a_leader"]
    assert not checks["roles_follow_the_declared_local_rule"]


# ------------------------------------------------------------------ novelty search: truth and geometry
def test_maze_distance_field_matches_an_independent_bfs():
    data, truth = dev("evo_novelty_search", 2)
    rows, goal = data["maze"], tuple(data["goal"])
    dist = {goal: 0}
    q = deque([goal])
    while q:
        r, c = q.popleft()
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nc = r + dr, c + dc
            if 0 <= nr < len(rows) and 0 <= nc < len(rows[0]) and rows[nr][nc] == "." and (nr, nc) not in dist:
                dist[(nr, nc)] = dist[(r, c)] + 1
                q.append((nr, nc))
    for r in range(len(rows)):
        for c in range(len(rows[0])):
            assert truth["distance_field"][r][c] == dist.get((r, c), -1)


def test_deceptive_mazes_are_declared_and_the_objective_misleads_there():
    kinds = {}
    for seed in range(10):
        data, truth = dev("evo_novelty_search", seed)
        kinds.setdefault(ITEMS["evo_novelty_search"].subregion(data), []).append(truth["kind"])
        if truth["kind"] in ("cup", "comb"):
            assert truth["shortest_path"] >= 1.5 * truth["manhattan"]
    assert set(kinds) == {"deceptive", "direct"}


@pytest.mark.parametrize("arm", ["baseline", "competitor"])
def test_maze_arms_answer_with_replayable_programs(arm):
    data, truth = dev("evo_novelty_search", 5)
    item = ITEMS["evo_novelty_search"]
    out = getattr(item, arm)(data)
    assert item.score(data, truth, out)["category"] == "correct"
    assert _ok("evo_novelty_search", data, out, {"evaluations_used": data["evaluations"]})


def test_simulator_population_and_single_paths_agree_with_the_reference_replay():
    import numpy as np
    data, _ = dev("evo_novelty_search", 3)
    rows, start, goal, length, evals, seed = search_b._maze(data)
    rng = np.random.default_rng(0)
    genomes = rng.integers(0, 4, (40, length))
    sim = search_b._Sim(rows, start, goal, length, 10**6)
    _, cells, hits = sim(genomes)
    for g, cell, hit in zip(genomes, cells.tolist(), hits.tolist()):
        moves = "".join(search_b.MOVES[int(x)] for x in g)
        assert search_b._replay(rows, start, goal, moves) == (cell, hit)
        _, one, onehit = sim(g[None])
        assert one.tolist()[0] == cell and int(onehit[0]) == hit


def test_novelty_search_spends_no_more_than_its_budget():
    data, _ = dev("evo_novelty_search", 0)
    data["evaluations"] = 120
    out = ITEMS["evo_novelty_search"].solve(data, BUDGET)
    assert out["status"] == "ANSWER" and out["certificate"]["evaluations_used"] <= 120
    assert _ok("evo_novelty_search", data, out["output"], out["certificate"])


# ------------------------------------------------------------------ hyper-heuristic: truth and budget
@pytest.mark.parametrize("seed", range(10))
def test_planted_optimum_is_the_volume_bound_and_no_arm_beats_it(seed):
    data, truth = dev("hyper_select_lowlevel", seed)
    assert sum(data["item_sizes"]) == truth["optimum"] * data["bin_capacity"]
    _, _, out = solved("hyper_select_lowlevel", seed)
    ffd = ITEMS["hyper_select_lowlevel"].baseline(data)
    assert truth["optimum"] <= out["output"]["bins"] <= ffd["bins"]          # never worse than its FFD start


def test_hyperheuristic_respects_its_application_budget():
    data, _ = dev("hyper_select_lowlevel", 0)
    data["heuristic_applications"] = 7
    out = ITEMS["hyper_select_lowlevel"].solve(data, BUDGET)
    assert out["certificate"]["applications_used"] <= 7
    data["heuristic_applications"] = 0
    out = ITEMS["hyper_select_lowlevel"].solve(data, BUDGET)
    assert out["output"] == ITEMS["hyper_select_lowlevel"].baseline(data)


def test_declared_competitor_is_the_random_selection_rival():
    assert search_b.HH_COMPETITOR == "random_selection"
    data, _ = dev("hyper_select_lowlevel", 9)
    assert ITEMS["hyper_select_lowlevel"].competitor(data) == search_b.hh_random(data)


# ------------------------------------------------------------------ differentiation: truth and rule
def test_pattern_check_matches_brute_force_on_small_graphs():
    import random
    r = random.Random("test:search_b:pattern")
    for _ in range(25):
        n = r.randint(1, 7)
        edges = sorted({tuple(sorted(r.sample(range(n), 2))) for _ in range(r.randint(0, 9))} if n > 1 else set())
        edges = [list(e) for e in edges]
        radius = r.choice((1, 2))
        adj = [set() for _ in range(n)]
        for u, v in edges:
            adj[u].add(v)
            adj[v].add(u)
        within = [search_b._ball(adj, v, radius) for v in range(n)]
        for bits in itertools.product((0, 1), repeat=n):
            roles = ["leader" if b else "member" for b in bits]
            expect = all((not bits[v] or not any(bits[u] for u in within[v])) and
                         (bits[v] or any(bits[u] for u in within[v])) for v in range(n))
            assert search_b._pattern_ok(n, edges, radius, roles) == expect


@pytest.mark.parametrize("seed", range(10))
def test_cp_sat_reference_bounds_the_leader_count(seed):
    data, truth, out = solved("develop_differentiate", seed)
    if truth["min_leaders"] is not None:
        assert truth["min_leaders"] <= out["output"]["roles"].count("leader")


def test_differentiation_reports_unknown_past_its_phase_cap():
    data, _ = dev("develop_differentiate", 0)
    data["max_phases"] = 1
    out = ITEMS["develop_differentiate"].solve(data, BUDGET)
    assert out["status"] == "UNKNOWN" and out["output"] is None


def test_isolated_nodes_lead_at_once_and_a_path_differentiates():
    out = ITEMS["develop_differentiate"].solve(
        {"num_nodes": 3, "edges": [], "radius": 1, "max_phases": 5, "seed": 1}, BUDGET)
    assert out["output"] == {"roles": ["leader"] * 3, "phases": 1, "rounds": 2}
    path = {"num_nodes": 6, "edges": [[i, i + 1] for i in range(5)], "radius": 2, "max_phases": 20, "seed": 4}
    out = ITEMS["develop_differentiate"].solve(path, BUDGET)
    assert _ok("develop_differentiate", path, out["output"], out["certificate"])
    assert out["output"]["rounds"] == 4 * out["output"]["phases"]


def test_random_roles_baseline_is_scored_wrong_when_the_pattern_fails():
    data, truth = dev("develop_differentiate", 1)
    base = ITEMS["develop_differentiate"].baseline(data)
    ok = search_b._pattern_ok(data["num_nodes"], data["edges"], data["radius"], base["roles"])
    assert ITEMS["develop_differentiate"].score(data, truth, base)["category"] == ("correct" if ok else "wrong")


# ------------------------------------------------------------------ invalid input
@pytest.mark.parametrize("family,patch", [
    ("evo_novelty_search", {"maze": ["##", "##"]}),
    ("evo_novelty_search", {"goal": [-1, 0]}),
    ("evo_novelty_search", {"moves": "x", "genome_length": 0}),
    ("evo_novelty_search", {"evaluations": 0}),
    ("hyper_select_lowlevel", {"item_sizes": [0]}),
    ("hyper_select_lowlevel", {"bin_capacity": 5, "item_sizes": [6]}),
    ("hyper_select_lowlevel", {"heuristic_applications": -1}),
    ("develop_differentiate", {"edges": [[0, 0]]}),
    ("develop_differentiate", {"radius": 9}),
    ("develop_differentiate", {"num_nodes": 0}),
])
def test_invalid_input_is_refused(family, patch):
    data, _ = dev(family, 1)
    data.update(patch)
    with pytest.raises(GenomeError):
        ITEMS[family].solve(data, BUDGET)
