"""natops-2026-10-21: extractor determinism, independent truth recomputation, and freeze refusal."""
from __future__ import annotations

import copy
import random
import subprocess
from pathlib import Path

import pytest

from cortex.evaluation.natural_ops import arms as A, extract as E, run as R, split as S, truth as T

ROOT = Path(__file__).resolve().parents[2]


def _git(repo, *args):
    return subprocess.run(("git", *args), cwd=repo, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def toy_repo(tmp_path):
    """A tiny repository whose import graph is known by construction."""
    repo = tmp_path / "toy"
    (repo / "greg").mkdir(parents=True)
    (repo / "adapters").mkdir()
    (repo / "tests").mkdir()
    files = {
        "greg/__init__.py": "",
        "greg/missions.py": "from . import a\nimport greg.b\n",
        "greg/a.py": "from greg import hub\n",
        "greg/b.py": "def f():\n    from .hub import x\n",
        "greg/hub.py": "import adapters.organ\nx = 1\n",
        "adapters/__init__.py": "",
        "adapters/organ.py": "from greg.missing import nothing\n",
        "tests/test_x.py": "import greg.missions\n",
        "greg/broken.py": "def (:\n",
    }
    for path, text in files.items():
        (repo / path).write_text(text)
    _git(tmp_path, "init", "-q", str(repo))
    _git(repo, "add", "-A")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "toy")
    return repo


def test_import_graph_of_known_repository(toy_repo):
    adj, bad = E.import_graph(E.resolve("HEAD", toy_repo), toy_repo)
    assert bad == 1                                         # greg/broken.py is counted, not dropped silently
    assert "tests.test_x" not in adj                        # tests/ is excluded
    assert adj["greg.missions"] == ["greg.a", "greg.b"]     # relative and absolute imports
    assert adj["greg.a"] == ["greg.hub"]                    # from-package import of a module
    assert adj["greg.b"] == ["greg.hub"]                    # lazy, function-level relative import
    assert adj["greg.hub"] == ["adapters.organ"]
    assert adj["adapters.organ"] == ["greg"]                # unresolved submodule falls back to the package


def test_extractor_is_deterministic_and_selects_by_rule(toy_repo, monkeypatch):
    monkeypatch.setattr(E, "SOURCES", ("greg.missions",))
    base = E.resolve("HEAD", toy_repo)
    one, two = E.extract(base, toy_repo), E.extract(base, toy_repo)
    assert one == two
    targets = {i["target"]: i for i in one["instances"]}
    # direct imports (greg.a, greg.b) have no vertex cut and are excluded; greg/__init__ reached via organ
    assert set(targets) == {"greg.hub", "adapters.organ", "greg"}
    assert targets["adapters.organ"]["target_class"] == "organ_or_evidence"
    assert targets["greg.hub"]["target_class"] == "internal"
    for inst in one["instances"]:
        assert inst["instance_id"] == E.hashlib.sha256(
            f"{inst['source']}|{inst['target']}|{inst['subgraph_digest']}".encode()).hexdigest()[:16]


def test_extractor_on_this_repository_is_deterministic():
    head = E.resolve("HEAD")
    a, _ = E.import_graph(head)
    b, _ = E.import_graph(head)
    assert a == b and len(a) > 100


def _random_instance(seed):
    rng = random.Random(seed)
    n = rng.randint(4, 14)
    nodes = [f"m{i}" for i in range(n)]
    edges = {(u, v) for u in nodes for v in nodes if u != v and rng.random() < 0.3}
    edges.discard(("m0", f"m{n - 1}"))
    inst = {"source": "m0", "target": f"m{n - 1}", "edges": sorted([u, v] for u, v in edges)}
    if not inst["edges"] or T.separates(inst["edges"], "m0", inst["target"], []):
        return None
    return inst


def _brute_force_k(inst):
    from itertools import combinations
    mids = sorted({x for e in inst["edges"] for x in e} - {inst["source"], inst["target"]})
    for k in range(len(mids) + 1):
        if any(T.separates(inst["edges"], inst["source"], inst["target"], c) for c in combinations(mids, k)):
            return k
    raise AssertionError


def test_truth_recomputation_matches_brute_force():
    checked = 0
    for seed in range(200):
        inst = _random_instance(seed)
        if inst is None:
            continue
        tr = T.truth(inst)
        assert tr["k"] == _brute_force_k(inst)
        assert T.score(inst, tr["k"], tr["menger_cut"]) == "CORRECT"
        assert T.score(inst, tr["k"], tr["ilp_cut"]) == "CORRECT"
        checked += 1
    assert checked > 50


def test_score_rejects_false_answers():
    inst = {"source": "s", "target": "t", "edges": [["s", "a"], ["s", "b"], ["a", "t"], ["b", "t"], ["a", "b"]]}
    assert T.truth(inst)["k"] == 2
    assert T.score(inst, 2, ["a", "b"]) == "CORRECT"
    assert T.score(inst, 2, ["a"]) == "WRONG"            # does not separate
    assert T.score(inst, 2, ["s", "a"]) == "WRONG"       # endpoint is not a control point
    assert T.score(inst, 2, ["a", "a"]) == "WRONG"       # duplicates
    assert T.score(inst, 2, ["a", "b", "x"]) == "WRONG"  # not a module of the instance
    assert T.score(inst, 2, None) == "ABSTAIN"
    with pytest.raises(T.TruthError):
        T.truth({"source": "s", "target": "t", "edges": [["s", "t"]]})


def test_baseline_and_translation_round_trip():
    inst = {"instance_id": "0" * 16, "source": "s", "target": "t",
            "edges": [["s", "a"], ["a", "h"], ["s", "b"], ["b", "h"], ["h", "t"]]}
    assert A._greedy(inst, A.degree_order(inst)) == ["h"]
    net = A.split_network(inst)
    assert net["source"] == "s#in" and net["sink"] == "t#out"
    assert A.back_translate({"cut_edges": [["h#in", "h#out", 1]]}) == ["h"]
    assert A.back_translate({"cut_edges": [["a#out", "h#in", 6]]}) is None   # not a unit split arc


def test_split_is_a_pure_function_of_the_id():
    ids = [f"{i:016x}" for i in range(0, 10_000, 37)]
    assert all(S.part(i) == S.part(i) for i in ids)
    dev, held = S.split([{"instance_id": i} for i in ids])
    assert len(dev) + len(held) == len(ids) and not {d["instance_id"] for d in dev} & {h["instance_id"] for h in held}


def _fake_pool():
    inst = []
    for seed in range(60):
        x = _random_instance(seed)
        if x is None:
            continue
        key = E.digest({"s": x["source"], "t": x["target"], "edges": x["edges"]})
        iid = E.hashlib.sha256(f"{x['source']}|{x['target']}|{key}".encode()).hexdigest()[:16]
        inst.append({**x, "instance_id": iid, "subgraph_digest": key, "commit": "c", "target_class": "internal",
                     "n_nodes": 0, "n_edges": len(x["edges"])})
    return {"instances": inst}


def test_freeze_holds_then_refuses_when_inputs_change():
    data = _fake_pool()
    frozen = R.make_freeze(data)
    held = R.check_freeze(frozen, data, require_clean=False)
    assert {i["instance_id"] for i in held} == {i for i, _ in frozen["heldout"]}

    changed = copy.deepcopy(data)                                  # an instance's input changes
    changed["instances"][0]["subgraph_digest"] = "0" * 64
    with pytest.raises(R.FreezeError):
        R.check_freeze(frozen, changed, require_clean=False)

    extra = copy.deepcopy(data)                                    # the pool grows
    extra["instances"].append({**data["instances"][0], "instance_id": "f" * 16})
    with pytest.raises(R.FreezeError):
        R.check_freeze(frozen, extra, require_clean=False)

    code = copy.deepcopy(frozen)                                   # code differs from the freeze
    code["code"][R.FROZEN_FILES[1]] = "0" * 64
    with pytest.raises(R.FreezeError, match="code changed"):
        R.check_freeze(code, data, require_clean=False)

    rule = copy.deepcopy(frozen)                                   # the decision thresholds differ
    rule["decision"]["alpha"] = 0.1
    with pytest.raises(R.FreezeError):
        R.check_freeze(rule, data, require_clean=False)

    ver = copy.deepcopy(frozen)
    ver["versions"]["networkx"] = "0.0"
    with pytest.raises(R.FreezeError, match="versions"):
        R.check_freeze(ver, data, require_clean=False)


def test_decision_rule_on_constructed_rows():
    def row(comp, flow, deg="WRONG", cs=0.01, fs=0.5):
        return {"instance_id": "x", "commit": "c", "target_class": "internal", "k": 1,
                "arms": {a: {"result": r, "seconds": s, "cpu_seconds": s} for a, r, s in
                         (("composition", comp, cs), ("flow_maxflow", flow, fs), ("degree_greedy", deg, 0.001),
                          ("betweenness_greedy", deg, 0.001), ("compiled", flow, fs), ("practitioner", "CORRECT", .001))}}
    tie_fast = [row("CORRECT", "CORRECT") for _ in range(30)]
    s = R.summarise(tie_fast)
    assert R.decide(tie_fast, s)["verdict"] == "EFFICIENCY_ONLY"
    lift = [row("CORRECT", "ABSTAIN") for _ in range(10)] + [row("CORRECT", "CORRECT") for _ in range(20)]
    assert R.decide(lift, R.summarise(lift))["verdict"] == "LIFT"
    worse = [row("WRONG", "CORRECT") for _ in range(2)] + [row("CORRECT", "CORRECT", cs=.5) for _ in range(20)]
    assert R.decide(worse, R.summarise(worse))["verdict"] == "REGRESSION"
    same = [row("CORRECT", "CORRECT", cs=.5) for _ in range(20)]
    assert R.decide(same, R.summarise(same))["verdict"] == "NO_LIFT"
