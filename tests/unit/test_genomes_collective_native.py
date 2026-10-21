"""Native-geometry benchmark regimes of the Layer 2 collective genomes (collective.BENCHMARK_REVISION, 2026-10-14).

The admission generators of collective_quorum, collective_physarum, collective_immune and collective_flock became
seeded mixtures of regimes: ``REGIMES[family][seed % k]``; regime 0 is the generator before the revision, kept
byte-identical for its seeds. Subregions are read from the data, never from the seed, because the Competency Compiler
places live requests with them: each native regime is one subregion marked by what its data declare, and regime 0
keeps its pre-revision bands (so a request without a native marker is placed against the v1 verdicts exactly as
before). These tests pin all of that and prove that no solve or verify function changed (so no genome version
changed). Development seeds 0-9 and review seeds 3000-3999 only: no held-out (1000-1029, 1100-1129, 1200-1299) or
protected-evolution (7000-8059) seed is generated here.
"""
import ast
import copy
import hashlib
import json
import math

import pytest

from greg.cognition.genomes import collective as c
from greg.cognition.genomes import library
from greg.cognition.genomes.contract import CATEGORIES

BUDGET = {"latency_s": 5.0, "compute": 100000}
DEV = range(10)
FAMILIES = ("collective_quorum", "collective_physarum", "collective_immune", "collective_flock")
REGIMES = {
    "collective_quorum": ("mixed_panel", "wrong_faction_early_decision", "wrong_faction_late_decision"),
    "collective_physarum": ("static_design", "edge_failure_mid_run"),
    "collective_immune": ("gaussian_ellipsoid", "multimodal_self", "annular_self", "nonconvex_self"),
    "collective_flock": ("ring_swap", "agent_dropout", "limited_radius"),
}
SUBREGIONS = {
    "collective_quorum": ("dominant_faction", "spread_factions", "wrong_faction_early_decision",
                          "wrong_faction_late_decision"),
    "collective_physarum": ("high_fault_weight", "low_fault_weight", "edge_failure_mid_run"),
    "collective_immune": ("low_dim_2_3", "mid_dim_4_6", "multimodal_self", "annular_self", "nonconvex_self"),
    "collective_flock": ("four_to_five_agents", "six_to_eight_agents", "agent_dropout", "limited_radius"),
}
# the pre-revision subregion function of each family, kept under a band name
BANDS = {"collective_quorum": c.quorum_faction_band, "collective_physarum": c.physarum_fault_band,
         "collective_immune": c.immune_dimension_band, "collective_flock": c.flock_size_band}
OLD = {"collective_quorum": c.quorum_mixed_panel_instance, "collective_physarum": c.physarum_static_instance,
       "collective_immune": c.immune_gaussian_instance, "collective_flock": c.flock_ring_swap_instance}
VERSIONS = {"collective_quorum": "1.0.1", "collective_physarum": "1.0.1", "collective_immune": "1.0.2",
            "collective_flock": "1.0.2"}
# sha256 of json.dumps(instance(seed), sort_keys=True) at dbc0643 (before the revision), seeds 0-9
BASE_INSTANCES = {
    "collective_quorum": [
        "23cf64ee9c3cbf27acee5eeb9c002654f050f5a9e7f6961bc74dace877d87c33",
        "fd6a22c7816c731d0c665bc97faac95a15a95528b5bfd7188d059de23182689b",
        "4f434467d56fc212ab393dee4f5fab17f31dc99d6822e98ca83bc470a4489d24",
        "db319276d98e945d27a27bb8b97e2226a10008f164a89a9e19a98a350679ffee",
        "268937fffde0c87817b4d71a3ab50122f765898b14c9348a4a5cc1ebbd9b2713",
        "2c7130bcb4fe19a3d201a54e298b9d28710edf0e5d8beed5d50a56167ac47c2b",
        "31034a97228b7df55b1155b709294c4964a753b3d5901a606828be722aecb541",
        "a7518f0c7fec9df7b8268867e8efa6979cb772e8c6ca934a22c885cd215c802e",
        "3f7cd8a59ee020478b5eaab603ec8fbf7a5ccca59e5378e22645d0b2ab394ada",
        "492c33955a28edea7279aa0ac55b03ec68b49c4957d7f553a6a53859a25f1e84"],
    "collective_physarum": [
        "5cc7afbe52e2f75945ca0ce91414063e8b73a3c38413b49dabfb914156c9293e",
        "f0de010550d07367aa9a4849847fb73bdd8fdf5e1b92ab5e75f6e350ee39ae34",
        "e1c91ae56b66659a3999afe5f53cff43499f50c13b96c888dad5124c82388c5f",
        "bec601b55c9811ac3d6257047d099698a7dab8bc62e9703b4323a829b76cf41a",
        "13028bd783a6261ce170bf5bbd61dee34861a9fcfd40b4bb5906ad4cb1ee974d",
        "166854db17b5a4ba3178f8ff8056ce05da7a20b55df2aaf808ed60d743f173fb",
        "16afbdb75b5c32f01849d48b92fb96465ca169754749aab22355ceabcdf47c52",
        "e7e6977db0584ebd3f9b7c1d74c371363c94cde0ed7e4e0f7c1da87535c5a6d4",
        "22535b4ac63b8183a18b0fd68d6b5e9c7c62a2317c7b44a3ecb3b426a80bce70",
        "9897f04da48ec7926ffb82e1d2506bc98e972d3d275da84098d2f47dcc081121"],
    "collective_immune": [
        "935032691c8c249ba52649424cb86fa580b057d45208ee9ea598976391b1b20e",
        "ae9c4829dc2459f5fdbbeb22072be80a585e92b6262b80d3bd73950b4556f3d0",
        "d896b846764e9df36618718c250a2600c81d6f76f1a176f13da8fab68fd4e75f",
        "e8ff0b366e3eec40fc1a53d9c932d939c94ed6f86fea47c8fb99c63fba4c440a",
        "d59c144fd3b8e398c85761cce48d02b32b9667c9db3b57a996faa19eda173e2b",
        "558981e9928fd0c48c089b80e4e1c3248afa4843bb10c02ae7d59dcc2de9ab04",
        "ec76903b7bb981f68ecfa1dbecc8ac1ad851672052ea40c559637256107b3862",
        "5446fe70cd770013e1caa412575a2a5987294ce6c322b7ce6fd86b4d265f8765",
        "24703f0d3ce52c626cc61894feadba122438cf93ddc9bc2d0d14da42bd358a45",
        "a5877f0b6fe39cfdb2bdf6bb04c473927f4bb547009a015bff4129f837db354d"],
    "collective_flock": [
        "72feef4ce0f18fe28fe146e5c78cc5e3961ff380f32c6a7a6a8b845428f30978",
        "0b3afad8fd07189706ebe2815a0b1c8e03698dab6bb7289f3c160f85d546b5bb",
        "d06a09023863ecb9736761b2db841582cf032c85389cace0dc568907ef9c65fd",
        "15a500c1669b7a061f3aa2908cbc33936308dbb1cdd60c628ae53fb37062dd05",
        "433e1bfddfb83bb6d4ee2534e87c2f5ce54ed56f178fb9b644466a7edd48dc74",
        "cef0462f8eb255a56c8a883582742ef487b5a5418ba9f1e3d397d63272955b78",
        "894be6bb44ac502daa61e750c322eccbc9b69facdc8c57e2fa30e994d5fff279",
        "88bd9d3b8fb7870ee50e79f9360bcb120bc6e055683123bde2a51206e01d48b3",
        "953d638c16d4b83849936aa0888e3cb593717c1c408ba17b08fd9ff5bed2f6e3",
        "efac1d62a541882380cf9d4dcff4ef692504b78a16f082dfe95d2ca5c577ad5d"],
}
# sha256 of each function's source segment at dbc0643, per family: every solve and verify (with the helpers they
# call) and every pre-revision arm and score. A mechanism change must change the genome version, which releases
# that family's pins; this revision changes no version, so every pin must hold.
BASE_SOURCES = {
    "collective_quorum": {
        "_quorum_inputs": "ef1fa7f279497b5fc3a237b00e1a51ef098455b7bdcce5a7435c65da356d8844",
        "_groups_in_order": "aa9503e2e9a63d35280619f3b90c433a77fddb0278316d4a5d2884c3df4da677",
        "_logsumexp": "6314783a246e1fd19a1750da892d176947a12e6824e2a73dc919bb2c108e29f3",
        "_group_loglik": "d734730f8486cfabb1a12e5c09c7af83110b1767016d6983d3ee43fb125fe170",
        "quorum_solve": "77ea5e1be259a029efff803bbf0d8ce69b5318313d38a7ead7e3c549b91b6095",
        "quorum_verify": "2d99794de9fa92af18436906f0581ed8866ce2b205e3563f8b53dd2b7b554d7e",
        "quorum_majority": "4be2c82b33d01b24e149cf93c723166ea02367d06720295c95bbe6098368dc71",
        "quorum_group_majority": "0ab82634af1f7dec9b236b30b035a24235778cfdb1b67b9f2543f7e208033e23",
        "quorum_score": "35f316a59e72c44647ec54d42fefc73d8216dd32625dd4f57dc604378d3bfa8d",
    },
    "collective_physarum": {
        "_network_inputs": "09e2724b9fee1e9ec6e25f1b3f5639b119aaf24e0c9f16f1731555142857a6e7",
        "_adjacency": "ef06f5871ca417dcaec85b7c86dc6ca08efcc87949d9aa63f0227af36e1f0793",
        "_design_value": "8bcb49f3fad12749431f13df7e5875e5fc37e42e23d1db47c2879704ff03d25a",
        "_dijkstra": "6d396168d3f34407a3663fa3836a4a4c801a0f5fb9be854aa0b4bd5ce5575495",
        "_path_edges": "28460ddce1075a8d992dc70babe7c8ac0a6c3a7aa49b4075fac543d854c9948d",
        "_components": "c02db50c5c50f4424e28fd858659d240250abac2e9c832412e244394ab6ca0be",
        "_repair_and_prune": "b9be8de3fa9ec7b5ab00b8de3467dcdd09fc6c67ae32f6b4f23be4cb2ac5ff08",
        "_terminals_connected": "272e987a0b8bd4f7e28d6357cfde6724e01e4486fa4096ff563a86ab0b8816da",
        "physarum_solve": "342ca9e536f279f1bef8348c558c20a4236cbf5a837e7acf5123594fa5bbfff3",
        "_union_find_split": "6aae5c1fc8a04ed43fc45e050a0f3e0f219dfe50677e5c53c01825e326747513",
        "network_evaluate": "ae943b5eb840322d8f66c928129a438fbcf673ae54937dc4c790f44871c79143",
        "physarum_verify": "98af51e23dfc08f14553a5a2146702f71848378004076a40275f8e8eb03005bb",
        "_kmb_tree": "4db5022e86cf94c486ba1e9a8ae8854a176ea12ff25b2f6eab2e1b2cfc65ba6a",
        "_tm_tree": "82b1417e9f92ef42bf759aff99a5124b1a83add696f04a04978ed79b0e2008cd",
        "_objective_local_search": "e3834912ed7c5d7564bdaca7289e788047713a8bf75f1ba44677ac60b916ddc7",
        "_edges_out": "8f8cdbed443c8ad4ea6614b0c097e25679ea1ac069429e53a7499ec26926d929",
        "physarum_mst": "422208acb316e8699faa0210c0cc4972b5b1097469848c0079f2a873895d0020",
        "physarum_multistart_search": "ef3853c3a53c0b027adf6c7cbf798c99c8de73911213465117fb874ae1ee6ff7",
    },
    "collective_immune": {
        "_immune_config": "dda6d372adad17db5b00c47701c8756c503df7a778ea4d1d1f9af34a34f74e5c",
        "_immune_inputs": "bf29bd3c6828090e8c0e5da1e2999fef9498c70dc1fbb89820d6e352490f9a3d",
        "_standardiser": "0e59007afc564da0a6a20cefeaee566cb56f2d3f9b7caef7f34e33d3d7d6b4c6",
        "immune_solve": "eae58d607dc77886797eaa4380c9dc16281ee914b73cb70393d42a9999a47370",
        "immune_solve_with": "d842e49f38e9f75a25d90aaad46bebfa0d46788cf3ed983fafe7d13b9660acb3",
        "immune_verify": "777e5147beabb754b1bd6aecc87175af2cfc7dcd8f6485ec2fdc7efc2dae908e",
        "_verify_cholesky": "3d719f0642f32fb3d59b4e69ec448bb37f317fa47885dd3494931f8128fef9c1",
        "_binom_upper": "1dcce22d089fb1dba288c23804a42857ac1be3bd0c63cb29381c1eccb9bae02d",
        "immune_zscore": "66af5ddd6b0f7be4b657f1f5d22178629600bdbbbf483c129ab3f96419254531",
        "immune_prediction_region": "fa0fb7cfc8a7ff60c1acf27a42d583827487b1ef4219dbb498a3d9e4f4239f08",
        "immune_score": "5e9f2fe922534de9fe4a3d782840545c96c05495f62437958730d46683178db4",
    },
    "collective_flock": {
        "_flock_inputs": "9cbe4fe1271e648ca273ac59dd5ed19883076c9c21905351386c19ff18798ec5",
        "_flock_output": "c882ee42082d7d32161edd9de45ce5581f329a3430ab615d78383cb94f41e22a",
        "_local_step": "d21aa590ec5aa9f899a20bc40219fde5850195a361c7aae4f78f4d54369ac390",
        "flock_solve": "b4f9a226cd0870107a6ce4c71985dd3c9f4c1376e4980d2e47af625d60861159",
        "_closest_approach": "d138e216ab69f97795eedcb697bf14f08193df8b7013bbb6522cfb8537d21ca9",
        "flock_audit": "e92bd9602e16b3c4befd54165b1438c3089649fddf89ab3616f30e8137e46375",
        "flock_verify": "b8013e777a5ed9e92343bdbcf7a188fe1ec9e1282cac595267826d80d60f6ab6",
        "flock_straight": "9d96b5bf771a66d28c24c37c2480d6c307751fc2327f85d9ad652f63ce9f11b4",
        "flock_prioritized": "32a7b198a6e65654d5e6fedbf963a4629596a81b56b4fa1f163a669add53b567",
        "_space_time_astar": "051f88e9fbcbdb781762f1e3b55c092c1c4b9e8c7c22cd5e657215dd6ab9b32a",
        "flock_score": "dc88c4fc5a68f8f483296cc5f212bc329d75bd7d53ecad909e6a71b0176f3b9c",
    },
}
_CACHE = {}


def _sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def item(family):
    return library.executables()[family]


def inst(family, seed):
    if (family, seed) not in _CACHE:
        _CACHE[(family, seed)] = item(family).instance(seed)
    return copy.deepcopy(_CACHE[(family, seed)])


def first_seed(family, regime):
    k = len(REGIMES[family])
    return next(s for s in DEV if REGIMES[family][s % k] == regime)


# ------------------------------------------------------------------ regime and subregion names
def test_regime_and_subregion_names_are_stable():
    assert c.REGIMES == REGIMES and c.SUBREGIONS == SUBREGIONS
    for family in FAMILIES:
        x = item(family)
        k = len(REGIMES[family])
        assert x.subregion is not None and x.instance is getattr(c, x.instance.__name__)
        seen = set()
        for seed in DEV:
            data, _ = inst(family, seed)
            name = x.subregion(data)
            if seed % k == 0:                         # the old regime keeps its pre-revision bands
                assert name == BANDS[family](data) and name in SUBREGIONS[family][:2], (family, seed, name)
            else:                                     # each native regime is one subregion of the same name
                assert name == REGIMES[family][seed % k], (family, seed, name)
            seen.add(name)
        assert set(REGIMES[family][1:]) <= seen <= set(SUBREGIONS[family])     # every native regime from dev seeds


def test_subregions_are_read_from_the_data_never_from_the_seed():
    """The compiler places live requests with ``subregion``: a seed number must not move a request between
    regimes, and an unknown declaration is unplaced (the compiler then reports no subregion evidence)."""
    for family in FAMILIES:
        for seed in DEV:
            data, _ = inst(family, seed)
            moved = dict(data, seed=seed + 1)
            assert item(family).subregion(moved) == item(family).subregion(data), (family, seed)
    data, _ = inst("collective_immune", first_seed("collective_immune", "annular_self"))
    with pytest.raises(c.GenomeError):
        c.immune_subregion(dict(data, self_support="spherical"))
    plain = {k: v for k, v in data.items() if k != "self_support"}
    assert c.immune_subregion(plain) == c.immune_dimension_band(plain)
    # no arm reads the declaration: the candidate's answer is the same without it
    assert c.immune_solve(plain, BUDGET) == c.immune_solve(data, BUDGET)


def test_the_compiler_still_places_undeclared_requests_against_the_frozen_v1_verdicts():
    """Before the revision every request was placed in a v1 band; it still is, so the live evidence index keeps its
    effect (for instance immune mid_dim_4_6 and physarum low_fault_weight are DOMINATED there) until a
    re-admission replaces it. A native-regime request is placed under its own name: UNMEASURED until a
    re-admission measures it, then that verdict."""
    from pathlib import Path

    from greg.cognition.compiler import _subregion_evidence
    index = json.loads((Path(__file__).resolve().parents[2] / "docs" / "evidence" /
                        "greg-mind-evidence-index.json").read_text())
    for family in FAMILIES:
        record = index["genomes"][family]
        table = record["subregions_vs_competitor"]
        assert set(SUBREGIONS[family][:2]) <= set(table) <= set(SUBREGIONS[family])
        k = len(REGIMES[family])
        for seed in DEV:
            data, _ = inst(family, seed)
            placed = _subregion_evidence(item(family), data, record)
            name = SUBREGIONS[family][:2] if seed % k == 0 else (REGIMES[family][seed % k],)
            assert placed["name"] in name, (family, seed, placed)
            if placed["name"] in table:
                assert placed["verdict"] in ("FAVOURED", "NEUTRAL", "DOMINATED"), (family, seed, placed)
                assert placed["vs_competitor"] == table[placed["name"]]
            else:
                assert placed == {"name": placed["name"], "verdict": "UNMEASURED"}, (family, seed)


@pytest.mark.parametrize("family", FAMILIES)
def test_every_regime_generates_bounded_valid_instances_on_dev_seeds(family):
    for seed in DEV:
        data, truth = inst(family, seed)
        assert json.loads(json.dumps(data)) == data and json.loads(json.dumps(truth)) == truth
        assert len(json.dumps(data)) < 60 * 1024                 # fits a canonical cognitive request (64 KiB)
        again, _ = item(family).instance(seed)
        assert again == data                                     # deterministic per seed


# ------------------------------------------------------------------ the old regime is byte-identical
@pytest.mark.parametrize("family", FAMILIES)
def test_the_old_regime_is_byte_identical_to_the_generator_before_the_revision(family):
    k = len(REGIMES[family])
    for seed in DEV:
        assert _sha(OLD[family](seed)) == BASE_INSTANCES[family][seed], (family, seed)   # the kept generator
        if seed % k == 0:
            assert _sha(inst(family, seed)) == BASE_INSTANCES[family][seed]              # the benchmark mixture
    assert OLD[family].__name__.startswith(family.split("_")[1])


def test_no_solve_verify_or_pre_revision_arm_changed():
    """The revision changed generators, subregions and the physarum score's failure branch only. Every solve and
    verify (and its helpers) and every pre-revision arm is byte-identical at its source, so no genome version moved;
    a later mechanism change must bump the version, which releases that family's pins."""
    with open(c.__file__) as handle:
        source = handle.read()
    segments = {node.name: ast.get_source_segment(source, node) for node in ast.parse(source).body
                if isinstance(node, ast.FunctionDef)}
    for family in FAMILIES:
        x = item(family)
        assert x.solve.__name__ in BASE_SOURCES[family] and x.verify.__name__ in BASE_SOURCES[family]
        assert x.notes["benchmark_revision"] == c.BENCHMARK_REVISION
        if x.genome.version != VERSIONS[family]:
            continue                                     # a re-versioned mechanism is pinned by its own tests
        changed = [n for n, digest in BASE_SOURCES[family].items()
                   if hashlib.sha256(segments[n].encode()).hexdigest() != digest]
        assert not changed, (family, changed)
    for phrase in ("2026-10-14", "2026-10-13-v1", "2026-10-14-v2", "old regime", "re-admission"):
        assert phrase in c.BENCHMARK_REVISION, phrase


def test_every_subregion_belongs_to_exactly_one_regime():
    """The old regime stays reachable as its own row: its pre-revision bands map back to regime 0."""
    for family in FAMILIES:
        assert len(set(SUBREGIONS[family])) == len(SUBREGIONS[family])
        mapped = {name: c.regime_of(family, name) for name in SUBREGIONS[family]}
        assert set(mapped.values()) == set(REGIMES[family])
        assert [n for n, r in mapped.items() if r == REGIMES[family][0]] == list(SUBREGIONS[family][:2])
        k = len(REGIMES[family])
        for seed in DEV:
            data, _ = inst(family, seed)
            assert c.regime_of(family, item(family).subregion(data)) == REGIMES[family][seed % k], (family, seed)
        with pytest.raises(c.GenomeError):
            c.regime_of(family, "not_a_subregion")


# ------------------------------------------------------------------ solve + verify on every regime
REVIEW = range(3000, 3012)          # review seeds: every regime of every family appears at least three times


@pytest.mark.parametrize("family,regime", [(f, r) for f in FAMILIES for r in REGIMES[f]])
def test_solve_and_verify_pass_on_every_regime(family, regime):
    """Every answer on every regime passes the unchanged independent verifier and is scored as an answer; every
    non-answer is an explained abstention. Dev seeds 0-9 plus review seeds 3000-3011 (the candidate abstains on all
    three early-decision dev seeds of the quorum, an honest outcome under that deadline)."""
    x = item(family)
    k = len(REGIMES[family])
    answered = 0
    for seed in (s for s in (*DEV, *REVIEW) if s % k == REGIMES[family].index(regime)):
        data, truth = inst(family, seed)
        out = x.solve(copy.deepcopy(data), BUDGET)
        assert set(out) == {"output", "certificate", "status", "missing"}
        if out["status"] != "ANSWER":
            assert out["status"] == "ABSTAIN" and out["missing"], (seed, out)    # an honest, explained abstention
            assert x.score(data, truth, None)["category"] == "abstain"
            continue
        answered += 1
        checks = x.verify(data, out["output"], out["certificate"])
        assert checks and all(checks.values()), (seed, checks)
        assert x.score(data, truth, out["output"])["category"] in ("correct", "wrong")
        for arm in (x.baseline, x.competitor):
            result = arm(copy.deepcopy(data))
            assert x.score(data, truth, result)["category"] in CATEGORIES
    assert answered >= 1, (family, regime)


def test_every_native_regime_runs_on_the_canonical_cognition_path():
    """The first answered instance of each native regime goes through greg.cognition.cortex.reason (isolated worker,
    independent verifier, receipt) with the family attached in an evaluation-only registry view."""
    from greg.cognition.cortex import reason, registry_view
    registry = registry_view()
    for family in FAMILIES:
        registry.set_state(f"cognition.{family}", "ATTACHED")
        k = len(REGIMES[family])
        for index, regime in enumerate(REGIMES[family][1:], 1):
            data = next(d for d, _ in (inst(family, s) for s in (*DEV, *REVIEW) if s % k == index)
                        if item(family).solve(copy.deepcopy(d), BUDGET)["status"] == "ANSWER")
            receipt = reason({"problem_id": f"native:{family}:{regime}", "operation": item(family).genome.operation,
                              "data": data, "geometry": {"latency_limit": 30}}, registry=registry)
            assert receipt["abstention_state"] == "NONE", (family, regime, receipt["missing_information"])
            assert receipt["evaluator_result"]["verdict"] == "STRUCTURALLY_VERIFIED", (family, regime)
            assert receipt["proof_type"] == "genome_certificate" and receipt["authority_created"] is False


# ------------------------------------------------------------------ quorum: a wrong dominant faction, a deadline
def test_quorum_wrong_faction_regimes_declare_their_deadline_and_the_faction_is_wrong():
    for regime, (low, high) in (("wrong_faction_early_decision", c.QUORUM_EARLY_DEADLINE),
                                ("wrong_faction_late_decision", c.QUORUM_LATE_DEADLINE)):
        for seed in (s for s in DEV if s % 3 == REGIMES["collective_quorum"].index(regime)):
            data, truth = inst("collective_quorum", seed)
            assert low <= data["decision_time"] <= high
            times = [o["arrived_at"] for o in data["observers"]]
            assert times == sorted(times) and max(times) <= data["decision_time"]          # arrival order, by then
            faction = [o for o in data["observers"] if o["group"] == "faction"]
            assert len(faction) >= 8 and {o["vote"] for o in faction} == {truth["faction_vote"]}
            assert c._one_dominant_faction(data)                       # the largest group by construction
            assert truth["faction_vote"] != truth["truth"] and truth["faction_share"] >= 0.3
            assert c.quorum_majority(data)["choice"] == truth["faction_vote"]               # majority is captured
            # the solver reads the order, never the arrival times
            stripped = dict(data, observers=[{k: v for k, v in o.items() if k != "arrived_at"}
                                             for o in data["observers"]])
            assert c.quorum_solve(stripped, BUDGET) == c.quorum_solve(data, BUDGET)


def test_quorum_native_placement_needs_a_deadline_and_one_dominant_faction():
    """Wrongness is not knowable from the data; a deadline and one dominant faction are. A deadline over a panel
    without one dominant faction is placed in the pre-revision band; a deadline outside the 0-1 window is unplaced."""
    def panel(sizes, due):
        observers = [{"observer_id": f"{g}_{j}", "group": g, "accuracy": 0.7, "vote": "A"}
                     for g, n in sizes.items() for j in range(n)]
        return {"alternatives": ["A", "B"], "observers": observers, "decision_time": due,
                "groups": {g: {"shared_noise": 0.6} for g, n in sizes.items() if n > 1}}
    tied = panel({"g1": 2, "g2": 2, "s1": 1}, 0.4)
    assert c.quorum_subregion(tied) == c.quorum_faction_band(tied) in SUBREGIONS["collective_quorum"][:2]
    assert c.quorum_subregion(panel({"g1": 3, "g2": 2, "s1": 1}, 0.4)) == "wrong_faction_early_decision"
    assert c.quorum_subregion(panel({"g1": 3, "g2": 2, "s1": 1}, 0.8)) == "wrong_faction_late_decision"
    assert c.quorum_subregion(panel({"s1": 1, "s2": 1, "s3": 1}, 0.4)) == "spread_factions"
    with pytest.raises(c.GenomeError):
        c.quorum_subregion(panel({"g1": 3, "s1": 1}, 30))


# ------------------------------------------------------------------ physarum: failures mid-run
def _failure_case(seed=None):
    seed = first_seed("collective_physarum", "edge_failure_mid_run") if seed is None else seed
    data, truth = inst("collective_physarum", seed)
    assert "failure" in data
    return data, truth


def test_physarum_failure_strikes_corridor_edges_at_the_declared_step_and_leaves_terminals_connectable():
    for seed in (s for s in DEV if s % 2):
        data, _ = _failure_case(seed)
        coords, pairs, _, terms, _ = c._network_inputs(data)
        failed = c._declared_failure(data)
        assert 1 <= len(failed) <= 3 and failed <= set(pairs)
        corridor = set(c._corridor_edges([tuple(p) for p in data["nodes"]], pairs, len(terms)))
        assert failed <= corridor
        assert data["steps"] == data["failure"]["after_step"] and 80 <= data["steps"] <= 250
        find = c._score_components(len(coords), [p for p in pairs if p not in failed])
        assert len({find(t) for t in terms}) == 1


def test_physarum_pre_failure_designs_never_read_the_failure():
    data, _ = _failure_case()
    blind = {k: v for k, v in data.items() if k != "failure"}
    assert c.physarum_mst(data) == c.physarum_mst(blind)
    assert c.physarum_solve(copy.deepcopy(data), BUDGET) == c.physarum_solve(copy.deepcopy(blind), BUDGET)
    replanned = c.physarum_replan_at_failure(data)
    coords, pairs, lengths, terms, _ = c._network_inputs(blind)
    shortest = c._best_steiner_tree(len(coords), pairs, lengths, terms, lengths)
    assert replanned["edges"] == c._edges_out(pairs, shortest)["edges"]
    failed = c._declared_failure(data)
    assert not {(min(e), max(e)) for e in replanned["after_failure"]["edges"]} & failed


def test_physarum_failure_cost_is_build_plus_rebuild_plus_disruption():
    data, truth = _failure_case()
    _, pairs, lengths, _, lam = c._network_inputs(data)
    failed = c._declared_failure(data)
    survivors = [list(p) for p in pairs if p not in failed]
    cost = c.physarum_failure_cost(data, {"edges": survivors})       # nothing it uses fails: no rebuild, no outage
    assert cost["rebuild"] == 0.0 and cost["disconnected_pairs"] == 0
    assert math.isclose(cost["total"], math.fsum(lengths[e] for e, p in enumerate(pairs) if p not in failed))
    tree = c.physarum_mst(data)
    hit = c.physarum_failure_cost(data, tree)
    built = {(min(e), max(e)) for e in tree["edges"]}
    if built & failed:                                              # a broken tree pays a rebuild or an outage
        assert hit["rebuild"] > 0 or hit["disconnected_pairs"] > 0
    assert math.isclose(hit["total"], hit["build"] + hit["rebuild"] + lam * hit["disconnected_pairs"])
    # an after-failure network may not use a failed edge or leave a terminal out
    bad = dict(tree, after_failure={"edges": [list(p) for p in sorted(failed)] + survivors})
    assert c.physarum_failure_cost(data, bad) is None and c.physarum_score(data, truth, bad)["category"] == "wrong"
    floor = c.physarum_score(data, truth, None)
    assert floor["category"] == "abstain" and floor["quality"] < c.physarum_score(data, truth, tree)["quality"]
    assert c.physarum_score(data, truth, {"edges": survivors})["quality"] > floor["quality"]


def test_physarum_static_regime_is_still_scored_on_the_declared_objective():
    seed = first_seed("collective_physarum", "static_design")
    data, truth = inst("collective_physarum", seed)
    tree = c.physarum_mst(data)
    assert c.physarum_score(data, truth, tree) == {
        "quality": -c.network_evaluate(data, tree)["objective"] / truth["scale"], "category": "correct"}
    assert c.physarum_competitor(data) == c.physarum_multistart_search(data)


def _independent_failure_cost(data, output):
    """The realized failure cost recomputed with networkx, sharing no code with ``physarum_failure_cost``: build
    length, terminal pairs the failure disconnects, and the rebuild (the arm's after-failure network when it replans,
    else greedy cheapest-path reconnection from terminal 0's component with standing built tubes free)."""
    import itertools

    import networkx as nx
    coords = [tuple(p) for p in data["nodes"]]
    terms, lam = data["terminals"], data["lambda"]

    def key(e):
        return (min(e), max(e))

    def length(e):
        return math.hypot(coords[e[0]][0] - coords[e[1]][0], coords[e[0]][1] - coords[e[1]][1])
    failed = {key(e) for e in data["failure"]["edges"]}
    design = {key(e) for e in output["edges"]}
    standing = design - failed
    up = nx.Graph()
    up.add_nodes_from(range(len(coords)))
    up.add_edges_from(standing)
    disconnected = sum(1 for a, b in itertools.combinations(terms, 2) if not nx.has_path(up, a, b))
    if "after_failure" in output:
        new = {key(e) for e in output["after_failure"]["edges"]} - standing
    else:
        weighted = nx.Graph()
        for e in {key(e) for e in data["edges"]} - failed:
            weighted.add_edge(*e, weight=0.0 if e in standing else length(e))
        new, current = set(), nx.Graph(up)
        while True:
            root = nx.node_connected_component(current, terms[0])
            loose = [t for t in terms if t not in root]
            if not loose:
                break
            dist, paths = nx.multi_source_dijkstra(weighted, root)
            path = paths[min(loose, key=lambda t: (dist[t], t))]
            for a, b in itertools.pairwise(path):
                if key((a, b)) not in standing:
                    new.add(key((a, b)))
                current.add_edge(a, b)
    build, rebuild = math.fsum(map(length, design)), math.fsum(map(length, new))
    return {"total": build + rebuild + lam * disconnected, "build": build, "rebuild": rebuild,
            "disconnected_pairs": disconnected}


BROKEN_TREE_SEED = 3      # a dev failure seed whose KMB tree uses a failed edge (dev seed 1's tree misses both)


def test_physarum_failure_cost_matches_an_independent_recomputation_where_the_tree_breaks():
    """Every arm's realized cost (build + rebuild + lambda x disconnected pairs) and score, recomputed independently
    on a failure the KMB tree does not survive: 6 terminal pairs cut, 20.98 rebuilt by the shared repair rule."""
    data, truth = _failure_case(BROKEN_TREE_SEED)
    failed = c._declared_failure(data)
    tree = c.physarum_mst(data)
    assert {(min(e), max(e)) for e in tree["edges"]} & failed
    assert data["lambda"] > 0
    candidate = c.physarum_solve(copy.deepcopy(data), BUDGET)
    assert candidate["status"] == "ANSWER"
    arms = {"baseline": tree, "candidate": candidate["output"], "competitor": c.physarum_competitor(data)}
    for name, out in arms.items():
        mine = _independent_failure_cost(data, out)
        cost = c.physarum_failure_cost(data, out)
        assert cost["disconnected_pairs"] == mine["disconnected_pairs"], (name, cost, mine)
        for part in ("build", "rebuild", "total"):
            assert math.isclose(cost[part], mine[part], rel_tol=1e-9, abs_tol=1e-9), (name, part, cost, mine)
        assert math.isclose(c.physarum_score(data, truth, out)["quality"], -mine["total"] / truth["scale"],
                            rel_tol=1e-9), name
    broken = _independent_failure_cost(data, tree)
    assert broken["disconnected_pairs"] == 6 and math.isclose(broken["rebuild"], 20.982795643, abs_tol=1e-6)


def test_physarum_competitor_replans_at_every_declared_failure():
    for seed in (s for s in DEV if s % 2):
        data, _ = _failure_case(seed)
        out = item("collective_physarum").competitor(data)
        assert out == c.physarum_competitor(data) == c.physarum_replan_at_failure(data), seed
        assert out["after_failure"]["edges"], seed


def test_physarum_replan_reuses_standing_built_tubes_for_free():
    """Five nodes, terminals A (0) and B (1). Before the failure the shortest tree is A-M-B (20). M-B fails. Reusing the
    standing tube A-M and detouring M-N-B costs 2 sqrt(34) = 11.66 new; the all-new route A-S-B costs
    2 sqrt(101) = 20.10. A replanner that charged the standing tube A-M again (10 + 11.66 > 20.10) would rebuild
    A-S-B; the from-scratch recomputation must treat what still stands as free."""
    data = {"nodes": [[0, 0], [20, 0], [10, 0], [15, 3], [10, -1]],
            "edges": [[0, 2], [1, 2], [2, 3], [1, 3], [0, 4], [1, 4]], "terminals": [0, 1], "lambda": 5.0,
            "failure": {"after_step": 100, "edges": [[1, 2]]}}
    detour, all_new = 2 * math.sqrt(34), 2 * math.sqrt(101)
    assert detour < all_new < 10 + detour
    out = c.physarum_competitor(data)
    assert out == c.physarum_replan_at_failure(data)
    assert out["edges"] == [[0, 2], [1, 2]] and out["after_failure"]["edges"] == [[0, 2], [1, 3], [2, 3]]
    cost, mine = c.physarum_failure_cost(data, out), _independent_failure_cost(data, out)
    assert cost["disconnected_pairs"] == mine["disconnected_pairs"] == 1
    assert all(math.isclose(cost[part], mine[part]) for part in ("build", "rebuild", "total"))
    assert math.isclose(cost["rebuild"], detour)
    assert math.isclose(cost["total"], 20 + detour + 5.0)


def test_a_null_failure_declares_no_failure():
    """Dispatch reads the parsed declaration: ``"failure": null`` is the static regime for the subregion, the
    competitor and the score alike; a malformed declaration is refused."""
    data, truth = inst("collective_physarum", first_seed("collective_physarum", "static_design"))
    null = dict(data, failure=None)
    assert c.physarum_subregion(null) == c.physarum_subregion(data) == c.physarum_fault_band(data)
    assert item("collective_physarum").subregion(null) == c.physarum_fault_band(data)
    tree = c.physarum_mst(data)
    assert c.physarum_score(null, truth, tree) == c.physarum_score(data, truth, tree)
    assert c.physarum_competitor(null) == c.physarum_multistart_search(data)
    with pytest.raises(c.GenomeError):
        c.physarum_failure_cost(null, tree)
    for bad in ({"after_step": 100, "edges": []}, {"edges": [[0, 1]]}, [[0, 1]]):
        with pytest.raises(c.GenomeError):
            c.physarum_subregion(dict(data, failure=bad))


# ------------------------------------------------------------------ immune: non-elliptical self
def test_immune_native_regimes_put_anomalies_inside_the_hull_and_stay_low_dimensional():
    """Each native regime puts some anomalies where an ellipsoid fitted to self is dense: inside the convex hull of
    the self samples (between modes, in the ring's hole, in the union's concavity). ``kinds`` is aligned with the
    anomalies in test-point order."""
    import numpy as np
    from scipy.spatial import Delaunay
    expected = {"multimodal_self": {"between_modes", "outer"}, "annular_self": {"hole", "outer", "off_plane"},
                "nonconvex_self": {"concavity", "outer", "off_plane"}}
    hull_kind = {"multimodal_self": "between_modes", "annular_self": "hole", "nonconvex_self": "concavity"}
    for seed in (s for s in DEV if s % 4):
        data, truth = inst("collective_immune", seed)
        regime = c.immune_subregion(data)
        dim = len(data["self_samples"][0])
        assert c.IMMUNE_NATIVE_DIM[0] <= dim <= c.IMMUNE_NATIVE_DIM[1]
        assert set(truth["kinds"]) <= expected[regime] and len(truth["kinds"]) == sum(truth["labels"])
        assert 60 <= len(data["self_samples"]) and len(data["test_points"]) <= c.IMMUNE_MAX_TEST
        assert hull_kind[regime] in truth["kinds"]
        hull = Delaunay(np.array(data["self_samples"]))
        anomalies = [p for p, label in zip(data["test_points"], truth["labels"]) if label]
        inside = [hull.find_simplex(np.array(p)) >= 0 for p, kind in zip(anomalies, truth["kinds"])
                  if kind == hull_kind[regime]]
        assert inside and all(inside), (seed, regime, inside)


def test_immune_gaussian_mixture_anomalies_are_far_from_every_mode():
    import numpy as np
    seed = first_seed("collective_immune", "multimodal_self")
    data, truth = inst("collective_immune", seed)
    self_s = np.array(data["self_samples"])
    points = np.array(data["test_points"])
    anomalies = points[np.array(truth["labels"]) == 1]
    normal = points[np.array(truth["labels"]) == 0]
    def nearest(p):
        return np.sqrt(((self_s - p) ** 2).sum(1)).min()
    assert min(nearest(p) for p in anomalies) > np.median([nearest(p) for p in normal])


def _immune_offsets(data, truth):
    """Each test point's distance off the self support declared in ``truth['support']``, recomputed from that
    construction alone: (offset, plane). multimodal_self: the least Mahalanobis distance to any mode; annular_self:
    the larger of |radius - R| / w and the largest extra-axis coordinate / s; nonconvex_self: the largest extra-axis
    coordinate / s, with ``plane`` the in-plane distance to the union of arms (None for the other two)."""
    import numpy as np
    geometry = truth["support"]
    x = np.array(data["test_points"], dtype=float)
    if data["self_support"] == "multimodal_self":
        per_mode = [np.sqrt(np.einsum("ij,jk,ik->i", x - m, np.linalg.inv(cv), x - m))
                    for m, cv in zip(np.array(geometry["means"]), np.array(geometry["covariances"]))]
        return np.min(per_mode, axis=0), None
    z = (x - np.array(geometry["center"])) @ np.array(geometry["frame"])        # back into the generator's frame
    axial = np.abs(z[:, 2:]).max(axis=1) / geometry["axial_spread"] if z.shape[1] > 2 else np.zeros(len(z))
    if data["self_support"] == "annular_self":
        radial = np.abs(np.hypot(z[:, 0], z[:, 1]) - geometry["radius"]) / geometry["radial_spread"]
        return np.maximum(radial, axial), None
    px, py = z[:, 0] + geometry["span"][0] / 2, z[:, 1] + geometry["span"][1] / 2
    plane = np.min([np.hypot(np.maximum(np.maximum(x0 - px, px - x1), 0), np.maximum(np.maximum(y0 - py, py - y1), 0))
                    for x0, x1, y0, y1 in geometry["boxes"]], axis=0)
    return axial, plane


def test_immune_native_anomalies_sit_off_the_declared_self_support():
    """The labels are re-derived from the declared construction: every multimodal or annular anomaly is >= 6 noise
    units off the self support and farther off than every normal point; every union anomaly is off the union (>= 1
    unit in the plane for concavity and outer, <= 2.5 for outer; >= 6 spreads along an extra axis for off_plane)
    while every normal point lies on it. The declared construction describes the self samples (checked first)."""
    import numpy as np
    margin, tolerance = 6.0, 1e-3              # the declared margin; tolerance covers the data's 6-decimal rounding
    for seed in (s for s in DEV if s % 4):
        data, truth = inst("collective_immune", seed)
        labels = np.array(truth["labels"]) == 1
        kinds = np.array(truth["kinds"])
        offset, plane = _immune_offsets(data, truth)
        own, own_plane = _immune_offsets(dict(data, test_points=data["self_samples"]), truth)
        if plane is None:
            assert own.max() < margin, (seed, own.max())                          # self lies on the support
            assert offset[labels].min() >= margin - tolerance, (seed, offset[labels].min())
            assert offset[~labels].max() < offset[labels].min(), seed
            continue
        assert own_plane.max() <= tolerance and plane[~labels].max() <= tolerance, seed      # self is on the union
        in_plane = plane[labels][kinds != "off_plane"]
        assert in_plane.size and in_plane.min() >= 1.0 - tolerance, (seed, in_plane.min())
        assert plane[labels][kinds == "outer"].max(initial=0.0) <= 2.5 + tolerance, seed
        assert offset[labels][kinds == "off_plane"].min(initial=np.inf) >= margin - tolerance, seed


# sha256 of json.dumps(evolution.immune_split(), sort_keys=True) at dbc0643 with the P8 seeds replaced by these review
# seeds (3001 and 3005 are not regime 0 of the new mixture, so drawing the mixture would change the digest)
P8_STAND_IN = {"train": (3001, 3002, 3005), "heldout": (3003, 3006)}
P8_SPLIT_AT_BASE = "7c188ba9f06a906c51d3790e2a3364ec5df2df0a8a0d789bfd1a49f004b9bd29"


def test_the_p8_immune_split_is_byte_identical_to_the_base_commit(monkeypatch):
    """Protected evolution cycle 2 sampled the Gaussian generator with its dimension buckets; the split must be
    byte-identical to the one at dbc0643 (review seeds stand in for the reserved P8 seeds 7000-8059, which this test
    never generates)."""
    from greg.cognition import evolution
    # the stand-ins are outside P8's reserved range, so the named split's seed check is replaced, not the generation
    monkeypatch.setattr(evolution, "immune_split_seeds",
                        lambda name: (P8_STAND_IN["train"], P8_STAND_IN["heldout"], set()))
    split = evolution.immune_split("cycle-2")
    assert _sha(split) == P8_SPLIT_AT_BASE
    train, held, _ = split
    assert {v["category"] for v in (*train.values(), *held.values())} == {"low_dim_2_3", "mid_dim_4_6"}
    for key, value in (*train.items(), *held.items()):
        data, truth = c.immune_gaussian_instance(int(key[1:]))
        assert value["data"] == data and value["truth"] == truth and "self_support" not in data
        assert value["category"] == c.immune_dimension_band(data) == c.immune_subregion(data)


# ------------------------------------------------------------------ flock: dropout and limited communication
def test_flock_dropout_snapshot_has_static_discs_in_a_dense_but_unjammed_crowd():
    for seed in (s for s in DEV if s % 3 == 1):
        data, truth = inst("collective_flock", seed)
        stopped = [i for i, (a, b) in enumerate(zip(data["starts"], data["goals"])) if a == b]
        assert stopped == truth["dropped"] == data["stopped"]
        assert 1 <= len(stopped) <= 2 and 6 <= len(data["starts"]) <= 9
        assert min(math.dist(a, b) for k, a in enumerate(data["starts"])
                   for b in data["starts"][:k]) >= c.FLOCK_SNAPSHOT_SPACING
        out = c.flock_solve(copy.deepcopy(data), BUDGET)
        if out["status"] == "ANSWER":                       # stopped agents never move
            for i in stopped:
                assert out["output"]["trajectories"][i] == data["starts"][i]


def test_flock_limited_radius_never_undercuts_the_local_sensing_radius():
    for seed in (s for s in DEV if s % 3 == 2):
        data, _ = inst("collective_flock", seed)
        assert c.FLOCK_SENSE <= data["communication_radius"] <= c.FLOCK_COMM_RADIUS[1]
    with pytest.raises(c.GenomeError):
        c.flock_online_replan(dict(data, communication_radius=c.FLOCK_SENSE - 0.5))


def test_flock_online_replanning_is_one_prioritized_plan_without_events_and_safe_with_them():
    for seed in (s for s in DEV if s % 3 == 0):                       # every ring_swap dev seed
        data, truth = inst("collective_flock", seed)
        planned = c.flock_prioritized(data)
        assert c.flock_online_replan(data)["trajectories"] == planned["trajectories"], seed
        assert c.flock_competitor(data) == planned
    for regime in ("agent_dropout", "limited_radius"):
        data, truth = inst("collective_flock", first_seed("collective_flock", regime))
        out = c.flock_competitor(data)
        assert out is None or c.flock_score(data, truth, out)["category"] == "correct", regime
        if out is not None:
            audit = c.flock_audit(data, out)
            assert audit["clear"] and audit["goals"] and audit["speed"] and audit["within_budget"]


def test_flock_competitor_is_online_replanning_in_the_native_regimes():
    """agent_dropout dev seed 1: the one-shot prioritized plan abstains, online replanning (the competitor) answers.
    limited_radius dev seed 2: the radius splits the coordinators at the start and costs a step (67 against 66 with
    every agent in reach)."""
    data, truth = inst("collective_flock", 1)
    assert c.flock_subregion(data) == "agent_dropout"
    assert c.flock_prioritized(data) is None
    out = item("collective_flock").competitor(data)
    assert out == c.flock_online_replan(data) and out["rule"] == "online_replanning"
    assert item("collective_flock").score(data, truth, out)["category"] == "correct"
    data, truth = inst("collective_flock", 2)
    assert c.flock_subregion(data) == "limited_radius"
    assert len(c._comm_groups([tuple(p) for p in data["starts"]], data["communication_radius"])) > 1
    out = item("collective_flock").competitor(data)
    assert out == c.flock_online_replan(data) and out["makespan"] == 67
    assert item("collective_flock").score(data, truth, out)["category"] == "correct"
    unlimited = c.flock_online_replan({k: v for k, v in data.items() if k != "communication_radius"})
    assert unlimited["makespan"] == 66 and unlimited["trajectories"] != out["trajectories"]


def test_the_immune_competitor_is_the_strongest_reasonable_one_per_regime():
    """Declared before the re-admission freeze: Hotelling (likelihood-optimal for Gaussian self data) on the Gaussian
    benchmark, the 5-NN split-conformal detector on the declared non-Gaussian supports; an unknown declaration is
    refused, never silently compared against the wrong competitor."""
    item_ = item("collective_immune")
    seen = set()
    for seed in range(10):
        data, _ = inst("collective_immune", seed)
        support = data.get("self_support")
        expected = c.immune_prediction_region(data) if support is None else c.immune_knn_conformal(data)
        assert item_.competitor(data) == expected, seed
        seen.add(support)
    assert None in seen and len(seen) >= 2
    native = next(d for d, _ in (inst("collective_immune", s) for s in range(10)) if d.get("self_support"))
    with pytest.raises(c.GenomeError):
        item_.competitor({**native, "self_support": "spherical_cow"})


def test_a_plan_that_moves_a_declared_stopped_agent_is_wrong():
    """A dropped-out agent is a static disc. A plan that steps it away and back passes the unchanged kinematic audit
    and ``flock_score``; the benchmark score (``flock_regime_score``) marks it wrong. Holding still is not movement,
    and without the ``stopped`` declaration an agent that starts at its goal may step aside, as before."""
    score = item("collective_flock").score
    for seed in (4, 7):                                              # agent_dropout dev seeds the candidate answers
        data, truth = inst("collective_flock", seed)
        solved = c.flock_solve(copy.deepcopy(data), BUDGET)
        assert solved["status"] == "ANSWER", seed
        assert score(data, truth, solved["output"])["category"] == "correct"
        for i in data["stopped"]:                                    # every stopped agent, not only the first
            x, y = data["starts"][i]
            for step in (0.25, 0.01):                                # a small step is movement too
                for k in range(16):
                    a = k * math.pi / 8
                    moved = copy.deepcopy(solved["output"])
                    moved["trajectories"][i] = [x, y, round(x + step * math.cos(a), 5),
                                                round(y + step * math.sin(a), 5), x, y]
                    moved["arrival_steps"][i] = 2
                    if all(c.flock_verify(data, moved, solved["certificate"]).values()):
                        break
                else:
                    pytest.fail(f"seed {seed} agent {i}: no heading clear of the crowd")
                assert c.flock_score(data, truth, moved)["category"] == "correct"   # kinematics alone cannot see it
                assert score(data, truth, moved) == {"quality": -1.0, "category": "wrong"}, (seed, i, step)
        i = data["stopped"][0]
        x, y = data["starts"][i]
        held = copy.deepcopy(solved["output"])
        held["trajectories"][i] = [x, y, x, y, x, y]
        held["arrival_steps"][i] = 2
        assert score(data, truth, held) == c.flock_score(data, truth, held)
        assert score(data, truth, held)["category"] == "correct"
        plain = {k: v for k, v in data.items() if k != "stopped"}
        assert score(plain, truth, moved) == c.flock_score(plain, truth, moved)


def test_flock_native_placement_reads_the_parsed_declarations():
    """An undeclared request is placed in its v1 size band even when an agent starts at its goal; ``stopped`` marks
    agent_dropout and ``communication_radius`` limited_radius only when they hold a value; malformed declarations
    are refused."""
    data, _ = inst("collective_flock", first_seed("collective_flock", "agent_dropout"))
    plain = {k: v for k, v in data.items() if k != "stopped"}
    band = c.flock_size_band(plain)
    assert any(a == b for a, b in zip(plain["starts"], plain["goals"]))
    for undeclared in (plain, dict(data, stopped=None), dict(data, stopped=[])):
        assert c.flock_subregion(undeclared) == band and c._flock_event(undeclared) is None
    assert c.flock_subregion(data) == item("collective_flock").subregion(data) == "agent_dropout"
    moving = next(i for i in range(len(data["starts"])) if i not in data["stopped"])
    for bad in ([moving], [data["stopped"][0]] * 2, [len(data["starts"])], ["0"], 0):
        with pytest.raises(c.GenomeError):
            c.flock_subregion(dict(data, stopped=bad))
    ring, _ = inst("collective_flock", first_seed("collective_flock", "ring_swap"))
    assert c.flock_subregion(dict(ring, communication_radius=None)) == c.flock_size_band(ring)
    assert c._flock_event(dict(ring, communication_radius=None)) is None
    assert c.flock_subregion(dict(ring, communication_radius=4.0)) == "limited_radius"
    for bad in (c.FLOCK_SENSE - 0.5, "far", math.inf):
        with pytest.raises(c.GenomeError):
            c.flock_subregion(dict(ring, communication_radius=bad))
