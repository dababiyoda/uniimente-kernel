"""P6 v6 runner (cortex/evaluation/composition_lift/run_v6.py): the held-out gate, the clean room, the freeze, the
pre-registered rule, the independent rescoring, the integrity checks and a development smoke run.

No test here runs any arm on a held-out item. Every refusal test replaces ``run_items`` and ``suite_items`` with
functions that fail the test if they are ever called (or that serve synthetic items and record the partition asked
for), so a gate that stopped refusing would fail the test before any held-out item could run; the smoke run and the
rescoring tests read development items only.
"""
from __future__ import annotations

import copy
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

import pytest

pytest.importorskip("ortools")
pytest.importorskip("networkx")
pytest.importorskip("scipy")

from cortex.evaluation.composition_lift import run_v6 as V6  # noqa: E402
from cortex.evaluation.composition_lift.vpl_metrics import validate_preregistration  # noqa: E402
from greg.cognition import compiler  # noqa: E402
from greg.cognition.genomes import admission, library  # noqa: E402

GIT = ["git", "-c", "user.email=test@example.invalid", "-c", "user.name=test", "-c", "commit.gpgsign=false"]
PLAN = {"increments": {"a->b": 1}, "flow_value": 50}


def _never(*args, **kwargs):
    raise AssertionError("a refused held-out run must not read or run any item")


@pytest.fixture
def guarded(monkeypatch):
    monkeypatch.setattr(V6, "run_items", _never)
    monkeypatch.setattr(V6, "suite_items", _never)


def _repo(root: Path, files: dict) -> Path:
    root.mkdir()
    subprocess.run([*GIT, "init", "-q"], cwd=root, check=True)
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "base"], cwd=root, check=True)
    return root


def _row(genome="optimal", routed="optimal", genome_s=0.4, routed_s=1.2, network="n", genome_state=None,
         routed_state="ANSWERED", genome_agrees=True, routed_agrees=True, truth_agrees=True, item_id="F7-n-0"):
    """A rule row: the genome's state defaults to NONE for a plan and ABSTAIN for no_decision."""
    state = genome_state or ("ABSTAIN" if genome == "no_decision" else "NONE")
    return {"item_id": item_id, "network": network,
            "arms": {V6.GENOME: {"result": genome, "seconds": genome_s, "state": state},
                     V6.ROUTED: {"result": routed, "seconds": routed_s, "state": routed_state}},
            "independent": {"truth_agrees": truth_agrees, "optimum": 50, "status": "OPTIMAL",
                            "arms": {V6.GENOME: {"agrees": genome_agrees}, V6.ROUTED: {"agrees": routed_agrees}}}}


def _full_row(i, partition="heldout", **genome):
    """A complete synthetic result row (all four arms), for the summary and the integrity checks."""
    arms = {V6.GENOME: {"result": "optimal", "plan_score": "optimal", "throughput": 50, "seconds": 0.3, "state": "NONE",
                        "method": V6.GENOME_CAPABILITY, "method_version": "0.2.0",
                        "proof_intelligence_id": V6.GENOME_INTELLIGENCE, "proof_version": V6.GENOME_VERSION,
                        "verifier": "STRUCTURALLY_VERIFIED", "answer": PLAN},
            V6.ROUTED: {"result": "optimal", "throughput": 50, "seconds": 1.2, "state": "ANSWERED",
                        "recipe": V6.RECIPE, "answer": PLAN},
            V6.COMPILED: {"result": "optimal", "throughput": 50, "seconds": 0.3, "state": "ANSWERED",
                          "selected": V6.GENOME_CAPABILITY, "answer": PLAN},
            V6.PMCF: {"result": "optimal", "throughput": 50, "seconds": 0.01, "state": "practitioner_in_process",
                      "answer": PLAN}}
    arms[V6.GENOME].update(genome)
    return {"item_id": f"F7-synthetic-{i}", "network": "synthetic", "partition": partition, "truth": {"optimum": 50},
            "arms": arms, "independent": {"optimum": 50, "status": "OPTIMAL", "truth_agrees": True, "arms": {
                a: {"result": "optimal", "throughput": 50, "spent_claim_true": None, "agrees": True} for a in V6.ARMS}}}


def _ran(rows, loaded=("a.py",), executed=None, distributions=None):
    return {"rows": rows, "loaded": list(loaded),
            "executed": {p: "sha256:a" for p in loaded} if executed is None else executed,
            "distributions": distributions or {"numpy": "1"}}


def _clean_gate(monkeypatch, tmp_path, frozen):
    """The gate's inputs, tree, clean room and preconditions stubbed to pass, with a freeze file on disk."""
    manifest = tmp_path / "freeze-v6.json"
    manifest.write_text(json.dumps({"inputs": frozen}))
    monkeypatch.setattr(V6, "MANIFEST", manifest)
    monkeypatch.setattr(V6, "inputs", lambda: copy.deepcopy(frozen))
    monkeypatch.setattr(V6, "tree_dirty", lambda paths, root=V6.ROOT: [])
    monkeypatch.setattr(V6, "clean_room_violations", lambda code, root=V6.ROOT: [])
    monkeypatch.setattr(V6, "preconditions", lambda index=None: [])
    monkeypatch.setattr(V6, "bytecode_files", lambda root=V6.ROOT: [])
    return manifest


# ------------------------------------------------------------------ the held-out gate and the freeze
def test_a_heldout_run_without_a_freeze_is_refused_before_any_item(guarded, tmp_path, monkeypatch):
    monkeypatch.setattr(V6, "MANIFEST", tmp_path / "freeze-v6.json")
    out = tmp_path / "results.json"
    with pytest.raises(SystemExit, match="NO_FREEZE"):
        V6.main(["--out", str(out)])
    with pytest.raises(SystemExit, match="NO_FREEZE"):
        V6.main(["--check-gate"])
    assert not out.exists()
    with pytest.raises(SystemExit, match="--out required"):
        V6.main([])
    with pytest.raises(SystemExit, match="development runs only"):            # a held-out run is never truncated
        V6.main(["--limit", "2", "--out", str(out)])


def test_an_existing_out_is_refused_before_the_gate(guarded, tmp_path, monkeypatch):
    out = tmp_path / "results.json"
    out.write_text("{}")
    monkeypatch.setattr(V6, "heldout_gate", _never)
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        V6.main(["--out", str(out)])
    assert out.read_text() == "{}"


def test_a_tampered_frozen_input_is_refused_and_named(guarded, tmp_path, monkeypatch):
    original = V6.PREREG.read_bytes()
    prereg = tmp_path / "prereg-v6.json"
    prereg.write_bytes(original)
    manifest = tmp_path / "freeze-v6.json"
    monkeypatch.setattr(V6, "PREREG", prereg)
    monkeypatch.setattr(V6, "MANIFEST", manifest)
    monkeypatch.setattr(V6, "tree_dirty", lambda paths, root=V6.ROOT: [])     # isolates the input comparison
    monkeypatch.setattr(V6, "clean_room_violations", lambda code, root=V6.ROOT: [])
    monkeypatch.setattr(V6, "preconditions", lambda index=None: [])
    frozen = V6.inputs()
    manifest.write_text(json.dumps({"inputs": frozen}))
    gate = V6.heldout_gate()
    assert gate["inputs"] == frozen and gate["token"] in V6._ISSUED          # untouched: the gate passes
    V6._ISSUED.discard(gate["token"])
    out = tmp_path / "results.json"
    prereg.write_bytes(original.replace(b"EXPECTED TIE", b"EXPECTED WIN", 1))  # the pre-registration edited
    with pytest.raises(SystemExit, match="FROZEN_INPUT_CHANGED") as refused:
        V6.main(["--out", str(out)])
    assert "'prereg'" in str(refused.value)
    prereg.write_bytes(original)
    tampered = copy.deepcopy(frozen)
    tampered["code"]["cortex/evaluation/composition_lift/run_v4.py"] = "sha256:" + "0" * 64
    manifest.write_text(json.dumps({"inputs": tampered}))                    # a frozen file whose bytes differ
    with pytest.raises(SystemExit, match="code:cortex/evaluation/composition_lift/run_v4.py"):
        V6.main(["--out", str(out)])
    manifest.write_text(json.dumps({"inputs": frozen}))
    monkeypatch.setattr(V6, "LATENCY_RATIO", 2.0)                             # a threshold changed after the freeze
    with pytest.raises(SystemExit, match="latency_ratio"):
        V6.main(["--out", str(out)])
    monkeypatch.setattr(V6, "LATENCY_RATIO", 1.25)
    rule = V6.F7_RULE
    monkeypatch.setattr(V6, "F7_RULE", rule.replace("p < 0.05", "p < 0.10"))  # the secondary rule edited
    with pytest.raises(SystemExit, match="FROZEN_INPUT_CHANGED.*'f7_secondary'"):
        V6.main(["--out", str(out)])
    monkeypatch.setattr(V6, "F7_RULE", rule)
    monkeypatch.setattr(V6.platform, "python_version", lambda: "3.0.0")       # another interpreter version
    with pytest.raises(SystemExit, match="FROZEN_INPUT_CHANGED.*'python'"):
        V6.main(["--out", str(out)])
    assert not out.exists()


def test_the_freeze_binds_the_python_version_and_every_traced_distribution():
    frozen = V6.inputs()
    assert frozen["python"]["version"] == V6.platform.python_version()
    assert list(frozen["dependencies"]) == list(V6.DISTRIBUTIONS)
    assert {"pandas", "jsonschema", "scipy", "ortools", "networkx", "numpy"} <= set(V6.DISTRIBUTIONS)
    for name in ("pandas", "jsonschema"):
        assert frozen["dependencies"][name] == importlib.metadata.version(name)
    assert frozen["conditions"] == list(V6.CONDITIONS)
    assert frozen["deviations"] == [list(d) for d in V6.DEVIATIONS]
    assert frozen["genome"]["intelligence_id"] == V6.GENOME_INTELLIGENCE
    secondary = frozen["f7_secondary"]
    assert (secondary["rule"], secondary["conditions"], secondary["v4_rule"]) == (
        V6.F7_RULE, list(V6.F7_CONDITIONS), V6.V4.VERDICT_RULE)
    assert secondary["v4_constituents"]["counts"] == {"graph_alone_greedy": {"optimal": 108, "wrong": 0},
                                                      "optimize_flow_blind": {"optimal": 19, "wrong": 0}}
    assert set(V6.V4_EVIDENCE.values()) <= set(frozen["code"])              # v4's evidence files are hashed too


def test_a_dirty_tree_is_refused_for_a_heldout_run_and_for_a_freeze(guarded, tmp_path, monkeypatch):
    manifest = tmp_path / "freeze-v6.json"
    monkeypatch.setattr(V6, "MANIFEST", manifest)
    frozen = V6.inputs()
    manifest.write_text(json.dumps({"inputs": frozen}))
    seen = []

    def dirty(paths, root=V6.ROOT):
        seen.append(list(paths))
        return ["git status: ?? stray.py"]
    monkeypatch.setattr(V6, "tree_dirty", dirty)
    with pytest.raises(SystemExit, match="DIRTY_TREE"):
        V6.main(["--out", str(tmp_path / "results.json")])
    checked = set(seen[-1])
    assert set(frozen["code"]) <= checked                                     # every frozen file, and
    assert {"cortex/evaluation/composition_lift/suite-v4.json", "cortex/evaluation/composition_lift/prereg-v6.json",
            str(manifest.resolve())} <= checked                               # the suite, the prereg and the freeze
    fresh = tmp_path / "fresh.json"
    with pytest.raises(SystemExit, match="NOT_ISOLATED"):                     # pytest is not python -I
        V6.freeze(fresh)
    monkeypatch.setattr(V6, "_isolated", lambda: True)
    with pytest.raises(SystemExit, match="DIRTY_TREE"):
        V6.freeze(fresh)
    assert not fresh.exists()
    with pytest.raises(SystemExit, match="refusing to overwrite"):
        V6.freeze(manifest)
    monkeypatch.setattr(V6, "tree_dirty", lambda paths, root=V6.ROOT: [])
    monkeypatch.setattr(V6, "clean_room_violations", lambda code, root=V6.ROOT: [])
    monkeypatch.setattr(V6, "preconditions", lambda index=None: ["the evidence index records NICHE_CAPABILITY"])
    with pytest.raises(SystemExit, match="PRECONDITION"):
        V6.main(["--out", str(tmp_path / "results.json")])
    with pytest.raises(SystemExit, match="PRECONDITION"):
        V6.freeze(fresh)
    assert not fresh.exists()


def test_a_freeze_outside_the_repository_cannot_be_vouched_for(tmp_path):
    assert V6._rel(V6.SUITE) == "cortex/evaluation/composition_lift/suite-v4.json"
    assert V6._rel(tmp_path / "freeze-v6.json") == str((tmp_path / "freeze-v6.json").resolve())
    assert V6.tree_dirty([str(tmp_path / "freeze-v6.json")])                 # never an empty (clean) answer


def test_tree_dirty_compares_bytes_with_head_and_lists_every_status_line(tmp_path, monkeypatch):
    repo = _repo(tmp_path / "repo", {"a.py": "a = 1\n", "data.bin": "x"})
    assert V6.tree_dirty(["a.py", "data.bin"], root=repo) == []
    (repo / "a.py").write_text("a = 2\n")
    assert V6.tree_dirty(["a.py"], root=repo) == ["not committed as is: a.py", "git status:  M a.py"]
    (repo / "a.py").write_text("a = 1\n")
    (repo / "stray.py").write_text("s = 1\n")                                 # untracked anywhere is dirty
    assert V6.tree_dirty(["a.py"], root=repo) == ["git status: ?? stray.py"]
    (repo / "stray.py").unlink()
    subprocess.run([*GIT, "update-index", "--skip-worktree", "a.py"], cwd=repo, check=True)
    (repo / "a.py").write_text("a = 3\n")                                     # hidden from git status ...
    assert subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout == ""
    assert V6.tree_dirty(["a.py"], root=repo) == ["not committed as is: a.py"]   # ... but not from the bytes
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "a.py").write_text("a = 1\n")
    assert V6.tree_dirty(["a.py"], root=plain)[0].startswith("git cannot tell")
    assert V6.ignored_files(plain)[0].startswith("git cannot tell")


# ------------------------------------------------------------------ the clean room (bytecode, isolation, loader)
def _plant_stale_bytecode(source: Path, text: str) -> Path:
    """A timestamp .pyc compiled from ``text`` but stamped with the real source's mtime and size: Python's normal
    loader runs it instead of the source."""
    import importlib._bootstrap_external as external
    import importlib.util
    st = source.stat()
    pyc = Path(importlib.util.cache_from_source(str(source)))
    pyc.parent.mkdir(exist_ok=True)
    pyc.write_bytes(external._code_to_timestamp_pyc(compile(text, str(source), "exec"), int(st.st_mtime), st.st_size))
    return pyc


def test_planted_stale_bytecode_runs_under_the_normal_loader_but_never_under_the_source_only_loader(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("")
    source = tmp_path / "pkg" / "mod.py"
    source.write_text("VALUE = 'source'\n")
    _plant_stale_bytecode(source, "VALUE = 'stale'\n")
    plain = (f"import sys; sys.path.insert(0, {str(tmp_path)!r}); import pkg.mod; print(pkg.mod.VALUE)")
    proc = subprocess.run([sys.executable, "-I", "-B", "-c", plain], capture_output=True, text=True, check=True)
    assert proc.stdout.strip() == "stale"                     # what an isolated worker does with planted bytecode
    hooked = ("import sys, json, importlib.machinery; from pathlib import Path; "
              f"sys.path.insert(0, {str(V6.ROOT)!r}); "
              "from cortex.evaluation.composition_lift.run_v6 import _source_only_loader; "
              f"hook = _source_only_loader(Path({str(tmp_path)!r})); "
              "importlib.machinery.SourceFileLoader.get_data = hook; "
              f"sys.path.insert(0, {str(tmp_path)!r}); import pkg.mod; "
              "print(json.dumps([pkg.mod.VALUE, hook.executed]))")
    proc = subprocess.run([sys.executable, "-I", "-B", "-c", hooked], capture_output=True, text=True, check=True)
    value, executed = json.loads(proc.stdout.strip().splitlines()[-1])
    assert value == "source"
    assert executed["pkg/mod.py"] == V6.V1._sha(source)       # the digest of the bytes compiled
    with pytest.raises(OSError, match="never read"):
        V6._source_only_loader(tmp_path)(None, str(tmp_path / "x.cpython-313.pyc"))


def test_bytecode_and_ignored_files_in_the_checkout_are_found(tmp_path):
    repo = _repo(tmp_path / "repo", {".gitignore": "__pycache__/\n*.pyc\nbuild/\n", "pkg/__init__.py": "",
                                     "pkg/m.py": "x = 1\n"})
    assert V6.bytecode_files(repo) == [] and V6.ignored_files(repo) == []
    _plant_stale_bytecode(repo / "pkg" / "m.py", "x = 2\n")
    (repo / "stray.pyc").write_bytes(b"")
    (repo / "build").mkdir()
    (repo / "build" / "x.txt").write_text("x")
    assert V6.bytecode_files(repo) == ["pkg/__pycache__/", f"pkg/__pycache__/m.{sys.implementation.cache_tag}.pyc",
                                       "stray.pyc"]
    assert set(V6.ignored_files(repo)) == {"build/x.txt", f"pkg/__pycache__/m.{sys.implementation.cache_tag}.pyc",
                                           "stray.pyc"}
    assert subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=repo, capture_output=True,
                          text=True).stdout == ""                           # invisible to the tree check alone


def test_the_gate_refuses_a_checkout_or_process_that_is_not_a_clean_room(guarded, tmp_path, monkeypatch):
    manifest = tmp_path / "freeze-v6.json"
    frozen = {"code": {"a.py": "sha256:a"}}
    manifest.write_text(json.dumps({"inputs": frozen}))
    monkeypatch.setattr(V6, "MANIFEST", manifest)
    monkeypatch.setattr(V6, "inputs", lambda: copy.deepcopy(frozen))
    monkeypatch.setattr(V6, "tree_dirty", lambda paths, root=V6.ROOT: [])
    monkeypatch.setattr(V6, "preconditions", lambda index=None: [])
    monkeypatch.setattr(V6, "bytecode_files", lambda root=V6.ROOT: ["greg/cognition/genomes/__pycache__/"])
    monkeypatch.setattr(V6, "ignored_files", lambda root=V6.ROOT: ["build/x.txt"])
    with pytest.raises(SystemExit, match="CLEAN_ROOM_REQUIRED") as refused:   # this pytest process, as it is
        V6.main(["--check-gate"])
    text = str(refused.value)
    for why in ("bytecode in the checkout", "ignored files", "not started with python -I",
                "source-only loader is not installed"):
        assert why in text, why
    monkeypatch.setattr(V6, "bytecode_files", lambda root=V6.ROOT: [])
    monkeypatch.setattr(V6, "ignored_files", lambda root=V6.ROOT: [])
    monkeypatch.setattr(V6, "_isolated", lambda: True)
    monkeypatch.setattr(sys, "dont_write_bytecode", True)

    class Hook:
        executed = {"a.py": "sha256:a"}
    monkeypatch.setattr(V6, "_hook", lambda: Hook)
    record = {"loaded": ["a.py"], "executed": dict(Hook.executed), "distributions": {"numpy": "2"}}
    monkeypatch.setattr(V6, "_process_record", lambda: copy.deepcopy(record))
    gate = V6.heldout_gate()                                                  # a clean room passes
    assert gate["inputs"] == frozen
    V6._ISSUED.discard(gate["token"])
    monkeypatch.setattr(sys, "dont_write_bytecode", False)
    with pytest.raises(SystemExit, match="bytecode writing is on"):
        V6.heldout_gate()
    monkeypatch.setattr(sys, "dont_write_bytecode", True)
    for change, why in ((lambda r: r["executed"].update({"a.py": "sha256:b"}), "unlike the freeze"),
                        (lambda r: r["executed"].update({"b.py": "sha256:b"}), "outside the freeze"),
                        (lambda r: r["loaded"].append("c.py"), "without the source-only loader"),
                        (lambda r: r["distributions"].update({"leftpad": "1"}), "does not bind")):
        changed = copy.deepcopy(record)
        change(changed)
        monkeypatch.setattr(V6, "_process_record", lambda changed=changed: copy.deepcopy(changed))
        with pytest.raises(SystemExit, match="CLEAN_ROOM_REQUIRED") as refused:
            V6.heldout_gate()
        assert why in str(refused.value), why


def test_integrity_names_unfrozen_unlike_and_unhashed_code_and_unbound_distributions():
    code = {"a.py": "sha256:a"}
    assert V6.integrity(code, _ran([], loaded=["a.py"], executed={"a.py": "sha256:a"})) == []
    problems = V6.integrity(code, _ran([], loaded=["a.py", "b.py", "c.py"],
                                       executed={"a.py": "sha256:z", "b.py": "sha256:b"},
                                       distributions={"numpy": "2", "leftpad": "1"}))
    assert any("without the source-only loader: ['c.py']" in p for p in problems)
    assert any("outside the freeze: ['b.py']" in p for p in problems)
    assert any("unlike the freeze: ['a.py']" in p for p in problems)
    assert any("['leftpad']" in p for p in problems)
    assert V6.integrity(code, _ran([], executed=None) | {"executed": None}) == [
        "no source-only record of the code executed (the loader was not installed)"]
    merged = V6._merge([{"loaded": ["a.py"], "executed": {"a.py": "sha256:a"}, "distributions": {}},
                        {"loaded": ["a.py"], "executed": {"a.py": "sha256:z"}, "distributions": {}}])
    assert merged["executed"]["a.py"].startswith("conflict:")               # two processes compiled two sources
    assert V6.integrity(code, merged)


def test_merge_keeps_a_process_without_a_source_only_record_visible():
    good = {"loaded": ["a.py"], "executed": {"a.py": "sha256:a"}, "distributions": {"numpy": "1"}}
    bare = {"loaded": ["a.py"], "executed": None, "distributions": {}}       # a process the loader did not cover
    assert V6._merge([copy.deepcopy(good), copy.deepcopy(good)])["executed"] == {"a.py": "sha256:a"}
    for records in ([good, bare], [bare, good], [good, bare, good]):
        merged = V6._merge(copy.deepcopy(records))
        assert merged["executed"] is None, records
        assert V6.integrity({"a.py": "sha256:a"}, merged) == [
            "no source-only record of the code executed (the loader was not installed)"]


def test_loaded_distributions_are_attributed_by_file_including_extension_modules():
    import scipy.sparse.csgraph  # noqa: F401
    found = V6._loaded_distributions()
    assert found["scipy"] == importlib.metadata.version("scipy")
    assert found["networkx"] == importlib.metadata.version("networkx")
    assert not any(k.startswith("<unowned:_cs") for k in found)              # scipy's own extensions are scipy's


# ------------------------------------------------------------------ the one-use held-out token
def test_heldout_items_run_only_with_the_token_the_gate_issued_once(tmp_path, monkeypatch):
    monkeypatch.setattr(V6, "RUNNERS", {arm: _never for arm in V6.ARMS})
    heldout = [{"item_id": "F7-synthetic-0", "partition": "heldout"}]
    with pytest.raises(SystemExit, match="HELDOUT_TOKEN"):
        V6.run_items(heldout, "heldout")
    with pytest.raises(SystemExit, match="HELDOUT_TOKEN"):
        V6.run_items(heldout, "heldout", token=V6._HeldoutToken())          # a token the gate did not issue
    _clean_gate(monkeypatch, tmp_path, {"code": {}})
    gate = V6.heldout_gate()
    monkeypatch.setattr(V6, "_run_item", lambda index, item: _full_row(index))
    assert len(V6.run_items(heldout, "heldout", token=gate["token"])["rows"]) == 1
    with pytest.raises(SystemExit, match="HELDOUT_TOKEN"):
        V6.run_items(heldout, "heldout", token=gate["token"])                # used once


def test_run_items_refuses_an_item_outside_its_partition_before_running_it(monkeypatch):
    monkeypatch.setattr(V6, "RUNNERS", {arm: _never for arm in V6.ARMS})
    with pytest.raises(SystemExit, match="outside the dev partition"):
        V6.run_items([{"item_id": "F7-x-0", "partition": "dev"}, {"item_id": "F7-y-0", "partition": "heldout"}], "dev")


# ------------------------------------------------------------------ warm-up refusal, INVALID_RUN, receipts
def _stub_heldout_run(monkeypatch, tmp_path, warmup, heldout, after=None):
    """main()'s held-out path with the gate passed and every item synthetic. Records the partitions read and run."""
    frozen = {"code": {"a.py": "sha256:a"}}
    _clean_gate(monkeypatch, tmp_path, frozen)
    calls = []
    gate = {"inputs": frozen, "token": V6._HeldoutToken()}
    monkeypatch.setattr(V6, "heldout_gate", lambda manifest=None: gate)

    def items(partition):
        calls.append(("read", partition))
        return [{"item_id": f"F7-synthetic-{partition}-{i}", "partition": partition} for i in range(3)]

    def run(items_, partition, workers=1, cores=None, token=None):
        calls.append(("run", partition))
        if partition == "heldout":
            assert token is gate["token"]
            if after:
                after()
            return heldout
        return warmup
    monkeypatch.setattr(V6, "suite_items", items)
    monkeypatch.setattr(V6, "run_items", run)
    return calls


def test_the_warmup_refuses_unfrozen_code_before_any_heldout_item_is_read(tmp_path, monkeypatch):
    out = tmp_path / "results.json"
    cases = ((_ran([_full_row(0, "dev")], loaded=["a.py", "stray.py"]), "stray.py"),
             (_ran([_full_row(0, "dev")], executed={"a.py": "sha256:z"}), "unlike the freeze"),
             (_ran([_full_row(0, "dev")], distributions={"leftpad": "1"}), "leftpad"),
             (_ran([_full_row(0, "dev", proof_version="1.0.1")]), "proof artifact"))
    for warmup, why in cases:
        calls = _stub_heldout_run(monkeypatch, tmp_path, warmup, heldout=None)
        with pytest.raises(SystemExit, match="UNFROZEN_CODE") as refused:
            V6.main(["--out", str(out)])
        assert why in str(refused.value), why
        assert calls == [("read", "dev"), ("run", "dev")]                     # no held-out item read or run
        assert not out.exists()


def test_a_run_whose_integrity_fails_is_marked_invalid_with_the_measured_rule_kept(tmp_path, monkeypatch):
    clean = [_full_row(i) for i in range(3)]
    variants = {
        "clean": (_ran(clean), None, None),
        "unfrozen": (_ran(clean, loaded=["a.py", "greg/stray.py"]), "greg/stray.py", None),
        "version": (_ran([*clean[:2], _full_row(2, proof_version="1.0.1")]), "1.0.1", None),
        "method": (_ran([*clean[:2], _full_row(2, method="cognition.other")]), "cognition.other", None),
        "bytecode": (_ran(clean), "bytecode appeared",
                     lambda: monkeypatch.setattr(V6, "bytecode_files", lambda root=V6.ROOT: ["greg/__pycache__/"])),
        "inputs": (_ran(clean), "frozen inputs changed during the run",
                   lambda: monkeypatch.setattr(V6, "inputs", lambda: {"code": {"a.py": "sha256:edited"}})),
    }
    for name, (heldout, why, after) in variants.items():
        out = tmp_path / f"results-{name}.json"
        calls = _stub_heldout_run(monkeypatch, tmp_path, _ran([_full_row(0, "dev")]), heldout, after)
        V6.main(["--out", str(out)])
        assert calls == [("read", "dev"), ("run", "dev"), ("read", "heldout"), ("run", "heldout")]
        report = json.loads(out.read_text())
        rule = report["summary"]["rule"]
        assert set(report["machine_load_start"]) >= {"loadavg_1_5_15_min", "cpu_count", "other_python_processes"}
        assert set(report["machine_load_end"]) >= {"loadavg_1_5_15_min", "cpu_count", "other_python_processes"}
        secondary = report["summary"]["f7_lift_with_genome"]
        if why is None:
            assert rule["outcome"] == "MATCH" and report["integrity"] == []
            assert secondary["outcome"] == "INCONCLUSIVE" and secondary["why"][0].startswith("ITEMS_DIFFER")
        else:
            assert rule["outcome"] == "INVALID_RUN", name
            assert any(why in w for w in rule["why"]), (name, rule["why"])
            assert rule["as_measured"]["outcome"] == "MATCH"
            assert secondary["outcome"] == "INVALID_RUN" and secondary["why"] == rule["why"]
            assert secondary["as_measured"]["outcome"] == "INCONCLUSIVE"


def test_genome_receipts_must_name_the_frozen_genome_unless_they_carry_no_output():
    assert V6.receipt_problems([_full_row(0)]) == []
    assert V6.receipt_problems([_full_row(0, proof_intelligence_id="solver.other")])
    abstained = _full_row(0, result="no_decision", plan_score="no_decision", throughput=None, state="UNKNOWN",
                          answer=None, proof_intelligence_id=None, proof_version=None)
    assert V6.receipt_problems([abstained]) == []                              # a GENOME_DECIDES failure instead
    assert V6.receipt_problems([_full_row(0, method="none", answer=None)])


# ------------------------------------------------------------------ the pre-registered rule
def test_the_rule_decides_a_tie_a_quality_loss_a_latency_failure_and_a_wrong_answer():
    tie = [_row() for _ in range(200)]
    d = V6.decide(tie)
    assert d["outcome"] == "MATCH" and d["failed"] == [] and d["informative"] is False
    assert "uninformative beyond replication" in d["reading"]
    assert (d["wins"], d["losses"], d["p_worse_one_sided"], d["latency_ratio"]) == (0, 0, 1.0, round(0.4 / 1.2, 4))

    d = V6.decide(tie[:195] + [_row(genome="suboptimal") for _ in range(5)])  # 0-5: p = 1/32 < 0.05
    assert d["outcome"] == "NO_MATCH" and d["failed"] == ["NOT_SIGNIFICANTLY_WORSE"]
    assert (d["losses"], d["p_worse_one_sided"]) == (5, 0.03125) and d["informative"] is True
    d = V6.decide(tie[:196] + [_row(genome="suboptimal") for _ in range(4)])  # 0-4: p = 1/16, not significant
    assert d["outcome"] == "MATCH" and d["losses"] == 4 and d["informative"] is True
    assert "informative" in d["reading"] and "uninformative" not in d["reading"]

    d = V6.decide([_row(genome_s=1.26, routed_s=1.0) for _ in range(200)])    # 1.26x
    assert d["outcome"] == "NO_MATCH" and d["failed"] == ["LATENCY_WITHIN_RATIO"] and d["latency_ratio"] == 1.26
    assert V6.decide([_row(genome_s=1.25, routed_s=1.0) for _ in range(200)])["outcome"] == "MATCH"   # inclusive

    d = V6.decide(tie[:199] + [_row(genome="wrong")])                         # one wrong answer is enough
    assert d["outcome"] == "NO_MATCH" and d["failed"] == ["NO_WRONG_ANSWER"] and d["genome_wrong"] == 1
    d = V6.decide([_row(genome="wrong", genome_s=5.0) for _ in range(10)])   # every failed condition is named
    assert d["failed"] == ["NO_WRONG_ANSWER", "NOT_SIGNIFICANTLY_WORSE", "LATENCY_WITHIN_RATIO"]
    with pytest.raises(ValueError):
        V6.decide([])


def test_degenerate_arms_never_satisfy_the_rule():
    """The critique's cases: neither arm deciding, both suboptimal, an abstaining genome against routed plans, and
    a fast abstaining genome on a few items; none of them is a MATCH or uninformative."""
    d = V6.decide([_row("no_decision", "no_decision", 0.01, 60.0) for _ in range(200)])               # case 1
    assert d["outcome"] == "NO_MATCH" and d["failed"] == ["GENOME_DECIDES_EVERY_ITEM"] and d["informative"]
    assert (d["genome_no_decision"], d["comparator_replicated"]) == (200, False)

    d = V6.decide([_row("suboptimal", "suboptimal") for _ in range(200)])                             # case 2
    assert d["outcome"] == "INCONCLUSIVE" and d["failed"] == [] and d["informative"]
    assert any(w.startswith("COMPARATOR_NOT_REPLICATED: routed optimal on 0 of 200") for w in d["why"])

    d = V6.decide([_row("no_decision", "suboptimal", 0.01) for _ in range(200)])                     # case 3
    assert d["outcome"] == "NO_MATCH" and (d["wins"], d["losses"]) == (0, 200)
    assert d["failed"] == ["GENOME_DECIDES_EVERY_ITEM", "NOT_SIGNIFICANTLY_WORSE"]

    d = V6.decide([_row() for _ in range(196)] + [_row("no_decision", "optimal", 0.001) for _ in range(4)])  # 4
    assert d["outcome"] == "NO_MATCH" and d["failed"] == ["GENOME_DECIDES_EVERY_ITEM"] and d["losses"] == 4

    d = V6.decide([_row() for _ in range(199)] + [_row("no_decision", "wrong")])   # any routed plan, even wrong
    assert d["losses"] == 1
    d = V6.decide([_row() for _ in range(199)] + [_row("suboptimal", "no_decision")])   # not a genome win
    assert (d["wins"], d["losses"]) == (0, 0) and d["outcome"] == "INCONCLUSIVE"


def test_a_comparator_that_does_not_replicate_never_yields_a_match():
    d = V6.decide([_row() for _ in range(199)] + [_row("optimal", "no_decision")])
    assert d["outcome"] == "INCONCLUSIVE" and d["wins"] == 1 and d["failed"] == []
    # a latency failure alone against a failing comparator is not the composition's serving latency
    d = V6.decide([_row(genome_s=2.0, routed_s=1.0) for _ in range(199)] + [_row("optimal", "no_decision")])
    assert d["outcome"] == "INCONCLUSIVE" and d["failed"] == ["LATENCY_WITHIN_RATIO"]
    # a genome failure stands whatever the comparator did
    d = V6.decide([_row() for _ in range(198)] + [_row("optimal", "no_decision"), _row("wrong", "optimal")])
    assert d["outcome"] == "NO_MATCH" and d["failed"] == ["NO_WRONG_ANSWER"]


def test_an_independent_rescoring_disagreement_makes_any_outcome_inconclusive():
    tie = [_row() for _ in range(200)]
    for row in ([_row(genome_agrees=False)], [_row(routed_agrees=False)], [_row(truth_agrees=False)],
                [{**_row(), "independent": None}]):
        d = V6.decide(tie[:199] + row)
        assert d["outcome"] == "INCONCLUSIVE" and d["informative"], row
        assert d["why"][0].startswith("INDEPENDENT_RESCORING_DISAGREES")
    d = V6.decide(tie[:199] + [_row(genome="wrong", genome_agrees=False)])   # it outranks a NO_MATCH
    assert d["outcome"] == "INCONCLUSIVE" and d["failed"] == ["NO_WRONG_ANSWER"]
    row = _row()
    row["independent"]["arms"][V6.COMPILED] = {"agrees": False}            # a secondary arm: reported only, but
    d = V6.decide(tie[:199] + [row])
    assert d["outcome"] == "MATCH" and d["failed"] == [] and d["informative"] is True   # a disagreement is information
    assert d["rescoring_disagreements_on_secondary_arms"] == {V6.COMPILED: 1}
    assert "SECONDARY_RESCORING_DISAGREES" in d["reading"] and "uninformative" not in d["reading"]


def test_the_reading_claims_agreement_only_for_what_the_rule_checks():
    rows = [_full_row(i) for i in range(200)]
    d = V6.decide(rows)
    assert d["outcome"] == "MATCH" and d["informative"] is False
    assert ("agrees with the primary scoring on the genome's and the routed composition's plans and on every item's "
            "truth, and no secondary arm's rescoring disagrees") in d["reading"]
    for row in rows:                                    # the re-check's case: every compiled rescoring disagrees
        row["independent"]["arms"][V6.COMPILED]["agrees"] = False
    d = V6.decide(rows)
    assert (d["outcome"], d["failed"], d["informative"]) == ("MATCH", [], True)
    assert d["rescoring_disagreements_on_secondary_arms"] == {V6.COMPILED: 200}
    assert "SECONDARY_RESCORING_DISAGREES" in d["reading"] and "uninformative" not in d["reading"]
    rows = [_full_row(i) for i in range(200)]
    del rows[5]["independent"]["arms"][V6.PMCF]          # a recorded secondary arm the rescoring did not cover
    d = V6.decide(rows)
    assert d["rescoring_disagreements_on_secondary_arms"] == {V6.PMCF: 1} and d["informative"] is True
    assert V6.summarize(rows)["independent_rescoring"]["secondary_inconclusive"] == [V6.PMCF]


def test_a_refuted_genome_row_decides_no_wrong_answer_whatever_the_scorers_say_about_its_plan(monkeypatch):
    tie = [_row() for _ in range(199)]
    d = V6.decide(tie + [_row("wrong", genome_state="REFUTED", genome_agrees=False)])
    assert d["outcome"] == "NO_MATCH" and d["failed"] == ["NO_WRONG_ANSWER"] and d["why"] == []
    assert (d["rescoring_disagreements_on_rule_arms"], d["refuted_plan_rescoring_disagreements"]) == (0, 1)
    assert "the refutation decides those rows" in d["reading"]
    for other in ({"truth_agrees": False}, {"routed_agrees": False}):     # only its own plan's score is outranked
        d = V6.decide(tie + [_row("wrong", genome_state="REFUTED", genome_agrees=False, **other)])
        assert d["outcome"] == "INCONCLUSIVE", other
    # the re-check's probe on a development item: a refuted plan carrying a key that names no arc, which
    # run_v4.f7_score ignores (optimal) and the independent scorer calls wrong
    item = V6.suite_items("dev")[0]
    pmcf = V6.V4.parametric_min_cost_flow(item["payload"]["capacity_network"])
    plan = {**pmcf, "increments": {**pmcf["increments"], "nowhere->else": 20}}
    receipt = {"abstention_state": "REFUTED", "output": plan, "method": V6.GENOME_CAPABILITY, "method_version": "0.2.0",
               "evaluator_result": {"verdict": "REFUTED"}, "missing_information": [],
               "proof_artifact": {"intelligence_id": V6.GENOME_INTELLIGENCE, "version": V6.GENOME_VERSION}}
    monkeypatch.setattr(V6, "registry", lambda: None)
    monkeypatch.setattr(V6.V4, "reason", lambda params: receipt)
    genome = V6.genome_arm(item)
    assert (genome["result"], genome["plan_score"]) == ("wrong", "optimal")
    result, throughput = V6.V4.f7_score(item, pmcf)
    arms = {V6.GENOME: genome, V6.ROUTED: {"result": result, "throughput": throughput, "seconds": 1.2,
                                          "state": "ANSWERED", "answer": pmcf}}
    row = {"item_id": item["item_id"], "network": item["network"], "truth": item["truth"], "arms": arms,
           "independent": V6.independent_rescoring(item, arms)}
    assert row["independent"]["arms"][V6.GENOME]["result"] == "wrong"
    assert not row["independent"]["arms"][V6.GENOME]["agrees"] and row["independent"]["arms"][V6.ROUTED]["agrees"]
    d = V6.decide(tie + [row])
    assert d["outcome"] == "NO_MATCH" and d["failed"] == ["NO_WRONG_ANSWER"] and d["genome_refuted"] == 1


def test_a_failing_composition_credits_no_quality_escape_from_the_latency_condition():
    """Admission's 'or significantly better' escape is not used: the latency condition is always required."""
    d = V6.decide([_row(routed="suboptimal", genome_s=2.0, routed_s=1.0) for _ in range(10)])
    assert d["wins"] == 10 and d["p_better_one_sided"] < V6.ALPHA
    assert d["failed"] == ["LATENCY_WITHIN_RATIO"] and d["outcome"] == "INCONCLUSIVE"


# ------------------------------------------------------------------ a refuted genome answer is wrong
def test_a_refuted_genome_receipt_is_scored_wrong_and_counted_by_state(monkeypatch):
    item = V6.suite_items("dev")[0]                                           # a development item only
    net = item["payload"]["capacity_network"]
    pmcf = V6.V4.parametric_min_cost_flow(net)
    over_budget = {"increments": {f"{u}->{v}": net["max_increment"] for u, v, _ in net["edges"]},
                   "flow_value": 10**6, "spent": 0}
    monkeypatch.setattr(V6, "registry", lambda: None)
    for plan, plan_score in ((over_budget, "wrong"), (pmcf, "optimal")):     # a false plan, and a refuted good one
        receipt = {"abstention_state": "REFUTED", "output": plan, "method": V6.GENOME_CAPABILITY,
                   "method_version": "0.2.0", "evaluator_result": {"verdict": "REFUTED"}, "missing_information": [],
                   "proof_artifact": {"intelligence_id": V6.GENOME_INTELLIGENCE, "version": V6.GENOME_VERSION}}
        monkeypatch.setattr(V6.V4, "reason", lambda params, receipt=receipt: receipt)
        arm = V6.genome_arm(item)
        assert (arm["result"], arm["plan_score"], arm["state"], arm["verifier"]) == (
            "wrong", plan_score, "REFUTED", "REFUTED")
        assert arm["answer"] == plan and arm["proof_version"] == V6.GENOME_VERSION
    abstain = {"abstention_state": "UNKNOWN", "output": pmcf, "method": V6.GENOME_CAPABILITY, "method_version": "0.2.0",
               "evaluator_result": {"verdict": "NOT_RUN"}, "missing_information": ["TIMEOUT"], "proof_artifact": None}
    monkeypatch.setattr(V6.V4, "reason", lambda params: abstain)
    arm = V6.genome_arm(item)
    assert (arm["result"], arm["answer"], arm["proof_version"]) == ("no_decision", None, None)

    rows = [_full_row(i) for i in range(3)]
    rows.append(_full_row(3, result="wrong", plan_score="optimal", state="REFUTED", verifier="REFUTED"))
    summary = V6.summarize(rows)
    assert summary["rule"]["outcome"] == "NO_MATCH" and summary["rule"]["failed"] == ["NO_WRONG_ANSWER"]
    assert summary["rule"]["genome_refuted"] == 1
    assert summary["genome_receipts"]["result_by_state"] == {"NONE": {"optimal": 3}, "REFUTED": {"wrong": 1}}


# ------------------------------------------------------------------ the independent rescoring
def test_the_independent_rescoring_reproduces_the_truth_and_f7_score_on_development_items():
    for item in V6.suite_items("dev")[:4]:                                    # development items only
        net = item["payload"]["capacity_network"]
        inst = V6.independent_instance(net)
        best = V6.independent_optimum(inst)
        assert best == {"status": "OPTIMAL", "value": item["truth"]["optimum"]}
        plan = V6.V4.parametric_min_cost_flow(net)
        assert V6.independent_max_flow(inst, {}) == item["truth"]["without_lease"]
        score = V6.independent_score(inst, plan, best["value"])
        assert (score["result"], score["throughput"]) == V6.V4.f7_score(item, plan) == ("optimal", best["value"])


def test_the_independent_scorer_refuses_every_malformed_or_false_plan():
    item = V6.suite_items("dev")[0]
    net = item["payload"]["capacity_network"]
    inst, optimum = V6.independent_instance(net), item["truth"]["optimum"]
    plan = V6.V4.parametric_min_cost_flow(net)
    first = f"{net['edges'][0][0]}->{net['edges'][0][1]}"

    def score(answer):
        s = V6.independent_score(inst, answer, optimum)
        return s["result"], s["throughput"]
    assert score(None) == score({"flow_value": 3}) == ("no_decision", None)
    everything = {f"{u}->{v}": net["max_increment"] for u, v, _ in net["edges"]}
    assert score({"increments": everything}) == ("wrong", None)                         # over budget
    assert score({"increments": {**plan["increments"], first: net["max_increment"] + 1}})[0] == "wrong"   # limit
    assert score({"increments": {**plan["increments"], first: -1}})[0] == "wrong"
    assert score({"increments": {**plan["increments"], "nowhere->else": 0}}) == ("wrong", None)   # no such arc
    assert score({"increments": {**plan["increments"], first: 1.5}}) == ("wrong", None)          # not integral
    assert score({"increments": {**plan["increments"], first: True}}) == ("wrong", None)
    as_floats = {k: float(v) for k, v in plan["increments"].items()}
    assert score({"increments": as_floats}) == ("optimal", optimum)                     # integral floats are units
    assert score({**plan, "flow_value": optimum + 1}) == ("wrong", optimum)             # a false flow claim
    assert score({"increments": {}}) == ("suboptimal", item["truth"]["without_lease"])
    false_spent = V6.independent_score(inst, {**plan, "spent": -1}, optimum)
    assert (false_spent["result"], false_spent["spent_claim_true"]) == ("optimal", False)   # reported, as f7_score
    assert V6.independent_score(inst, plan, None)["result"] == "unscored"


def test_independent_rescoring_records_agreement_and_never_hides_a_failure(monkeypatch):
    item = V6.suite_items("dev")[0]
    plan = V6.V4.parametric_min_cost_flow(item["payload"]["capacity_network"])
    good = {"result": "optimal", "throughput": item["truth"]["optimum"], "answer": plan}
    ind = V6.independent_rescoring(item, {V6.GENOME: {**good, "plan_score": "optimal", "result": "wrong"},
                                          V6.ROUTED: good,
                                          V6.PMCF: {**good, "result": "suboptimal"}})   # a primary scoring defect
    assert ind["truth_agrees"] and ind["arms"][V6.GENOME]["agrees"] and ind["arms"][V6.ROUTED]["agrees"]
    assert not ind["arms"][V6.PMCF]["agrees"]
    short = {**good, "throughput": item["truth"]["optimum"] - 1}            # same category, another throughput
    assert not V6.independent_rescoring(item, {V6.ROUTED: short})["arms"][V6.ROUTED]["agrees"]
    wrong_truth = {**item, "truth": {**item["truth"], "optimum": item["truth"]["optimum"] + 1}}
    assert not V6.independent_rescoring(wrong_truth, {V6.ROUTED: good})["truth_agrees"]
    inst = V6.independent_instance(item["payload"]["capacity_network"])
    real_max_flow = V6.independent_max_flow
    monkeypatch.setattr(V6, "independent_max_flow", lambda inst, units: real_max_flow(inst, units) - 1)
    assert V6.independent_optimum(inst)["status"].startswith("PLAN_RECHECK_FAILED")   # the MILP's plan re-checked
    monkeypatch.setattr(V6, "independent_max_flow", real_max_flow)
    monkeypatch.setattr(V6, "independent_optimum", lambda inst: 1 / 0)
    broken = V6.independent_rescoring(item, {V6.GENOME: good, V6.ROUTED: good})
    assert broken["status"].startswith("ERROR: ZeroDivisionError") and not broken["truth_agrees"]
    assert not any(a["agrees"] for a in broken["arms"].values())
    monkeypatch.undo()
    monkeypatch.setattr(V6, "independent_score", lambda inst, answer, optimum: 1 / 0)   # an arm's rescoring raises
    broken = V6.independent_rescoring(item, {V6.GENOME: good, V6.ROUTED: good})
    assert broken["status"].startswith("ERROR: ZeroDivisionError") and not broken["truth_agrees"]
    assert set(broken["arms"]) == {V6.GENOME, V6.ROUTED} and not any(a["agrees"] for a in broken["arms"].values())


def test_independent_optimum_refuses_a_non_integral_milp_value(monkeypatch):
    import scipy.optimize
    item = V6.suite_items("dev")[0]                                           # a development item only
    inst = V6.independent_instance(item["payload"]["capacity_network"])
    real = scipy.optimize.milp

    def fractional(*args, **kwargs):
        result = real(*args, **kwargs)
        result.fun = result.fun - 0.25              # the value is the optimum + 0.25; its plan still re-checks
        return result
    monkeypatch.setattr(scipy.optimize, "milp", fractional)
    best = V6.independent_optimum(inst)
    assert best["status"].startswith("NOT_INTEGRAL") and best["value"] is None
    monkeypatch.setattr(scipy.optimize, "milp", real)
    assert V6.independent_optimum(inst) == {"status": "OPTIMAL", "value": item["truth"]["optimum"]}


# ------------------------------------------------------------------ the pre-registration
def test_the_preregistration_states_the_runners_rule_conditions_deviations_and_thresholds():
    doc = json.loads(V6.PREREG.read_text())
    assert doc["rule"]["text"] == V6.RULE
    assert doc["rule"]["alpha"] == V6.ALPHA == admission.ALPHA
    assert doc["rule"]["latency_ratio"] == V6.LATENCY_RATIO == admission.COST_RATIO
    assert [c["id"] for c in doc["rule"]["conditions"]] == list(V6.CONDITIONS) == list(
        V6.decide([_row()])["conditions"])
    assert [o.split(" ")[0] for o in doc["rule"]["outcomes"]] == ["MATCH", "NO_MATCH", "INCONCLUSIVE", "INVALID_RUN"]
    assert [(d["id"], d["text"]) for d in doc["deviations_from_admission_rule"]] == list(V6.DEVIATIONS)
    assert {d[0] for d in V6.DEVIATIONS} >= {"ZERO_WRONG", "DECIDES_EVERY_ITEM", "OPTIMAL_VS_NOT_DISCORDANCE",
                                             "NO_SIGNIFICANCE_ESCAPE", "NO_BASELINE_CLAUSE"}
    assert not any(word in V6.RULE.lower() for word in (" two deviations", " three deviations", "stricter than"))
    assert doc["execution"]["distributions"]["frozen"] == list(V6.DISTRIBUTIONS)
    assert [a["name"] for a in doc["arms"]] == list(V6.ARMS)
    assert (doc["genome"]["version"], doc["genome"]["capability"], doc["genome"]["intelligence_id"]) == (
        V6.GENOME_VERSION, V6.GENOME_CAPABILITY, V6.GENOME_INTELLIGENCE)
    assert "sha256:" + doc["items"]["suite_sha256"] == V6.V1._sha(V6.SUITE)
    assert "sha256:" + doc["data_provenance"]["sha256"] == V6.V1._sha(V6.ROOT / doc["data_provenance"]["file"])
    disclosure = doc["disclosures"][0]
    assert "looked at twice" in disclosure.lower() and "49b2d58" in disclosure and "8bbd3b8" in disclosure
    # the VPL validator does not fit a single genome against a composition on re-used items; its report is recorded
    assert doc["vpl_validator"]["applies"] is False
    assert validate_preregistration(doc) == doc["vpl_validator"]["problems_reported"]
    # the tie definition is decide()'s: every pair of scored results, classified as the code classifies it
    table = doc["rule"]["discordance"]["by_outcome_pair"]
    assert len(table) == len(V6.OUTCOMES) ** 2
    for g in V6.OUTCOMES:
        for k in V6.OUTCOMES:
            a, b = {"result": g}, {"result": k}
            assert not (V6._win(a, b) and V6._loss(a, b))
            assert table[f"{g}/{k}"] == ("win" if V6._win(a, b) else "loss" if V6._loss(a, b) else "tie"), (g, k)
    tie = doc["rule"]["discordance"]["tie"]
    assert "both non-optimal whatever their throughputs" not in tie and "never a tie" in tie
    # 'informative' and the agreement wording name only what the rule checks; secondary disagreements are information
    assert "agreeing everywhere" not in doc["rule"]["informative"]
    assert "no secondary arm (compiled, PMCF) whose rescoring disagrees" in doc["rule"]["informative"]
    assert "makes the run informative" in doc["independent_rescoring"]["effect"]
    assert "REFUTED" in doc["rule"]["outcome_precedence"][0]
    # the command sets no PYTHON* variable (-I ignores them); --check-gate is not the whole pre-look check
    execution = doc["execution"]
    assert "python -I cortex/evaluation/composition_lift/run_v6.py --workers 2" in execution["command"]
    assert "PYTHONDONTWRITEBYTECODE=1 python" not in execution["command"]
    assert "gate time" in execution["check_gate"] and "the warm-up completes it" in execution["check_gate"]
    assert "ARM_EXCEPTION" in execution["arm_exceptions"] and "WARMUP_ARM_EXCEPTION" in execution["warmup"]
    # the secondary decision: v4's verbatim rule, v4's frozen counts, its status and its expectation
    secondary = doc["secondary_decision"]
    assert (secondary["id"], secondary["rule"], secondary["v4_rule_verbatim"]) == (
        "F7_LIFT_WITH_GENOME", V6.F7_RULE, V6.V4.VERDICT_RULE)
    assert [c["id"] for c in secondary["conditions"]] == list(V6.F7_CONDITIONS)
    assert {c["name"]: (c.get("heldout_optimal"), c.get("heldout_wrong")) for c in secondary["constituents"]} == {
        **{n: (c["optimal"], c["wrong"]) for n, c in V6.v4_constituents("heldout")["counts"].items()},
        V6.GENOME: (None, None)}
    assert "does not change v4's frozen verdict" in secondary["status"]
    assert secondary["expected"].startswith("NO_LIFT") and "expectation, not a result" in secondary["expected"]
    assert secondary["outcomes"] == ["LIFT", "NO_LIFT", "INCONCLUSIVE", "INVALID_RUN"]
    assert (secondary["latency_multiplier"], secondary["chain_budget_s"], secondary["alpha"]) == (
        V6.V4.LATENCY_MULTIPLIER, V6.V4.CHAIN_BUDGET_S, V6.ALPHA)
    closure = set(V6.code_closure())
    assert {"cortex/evaluation/composition_lift/run_v6.py", "cortex/evaluation/composition_lift/run_v4.py",
            "cortex/evaluation/composition_lift/run.py", "greg/cognition/worker.py", "greg/cognition/genomes/flow.py",
            "greg/cognition/compiler.py", "docs/evidence/greg-mind-evidence-index.json",
            "cortex/evaluation/composition_lift/prereg-v6.json", "cortex/evaluation/data/sndlib_networks.json.gz",
            "cortex/evaluation/data/build_sndlib_networks.py"} <= closure


def test_preconditions_name_a_stale_or_lower_verdict():
    if library.executables()[V6.GENOME].genome.version != V6.GENOME_VERSION:
        pytest.skip("the genome was re-versioned; v6's question names 1.0.0 and its held-out run would refuse")
    current = {"genomes": {V6.GENOME: {"status": "DEFAULT_FOR_GEOMETRY", "version": V6.GENOME_VERSION}},
               "recipes": {}, "routing": {}}
    assert V6.preconditions(current) == []
    for status, version in (("NICHE_CAPABILITY", V6.GENOME_VERSION), ("DEFAULT_FOR_GEOMETRY", "0.9.0")):
        index = copy.deepcopy(current)
        index["genomes"][V6.GENOME].update(status=status, version=version)
        problems = V6.preconditions(index)
        assert any("not DEFAULT_FOR_GEOMETRY at 1.0.0" in p for p in problems), problems
        assert any("does not match" in p for p in problems), problems
    assert V6.preconditions({"genomes": {}, "recipes": {}, "routing": {}}) != []
    assert V6.preconditions() == V6.preconditions(compiler.evidence_index())   # the default reads the index


def test_machine_load_is_recorded():
    load = V6.machine_load()
    assert len(load["loadavg_1_5_15_min"]) == 3 and load["cpu_count"] >= 1
    assert load["other_python_processes"] is None or load["other_python_processes"] >= 0
    assert V6._header(1, None)["machine_load_start"].keys() == load.keys()


def test_other_python_processes_counts_every_python_process_but_this_one_and_its_children(tmp_path):
    proc = tmp_path / "proc"

    def entry(pid, argv0, ppid, stat=True):
        (proc / str(pid)).mkdir(parents=True)
        (proc / str(pid) / "cmdline").write_bytes(argv0.encode() + b"\0-c\0pass\0")
        if stat:
            (proc / str(pid) / "stat").write_text(f"{pid} (a name with ) in it) S {ppid} 1 1 0\n")
    entry(10, "/usr/bin/python3", 1)                  # counted
    entry(11, "python3.13", 500)                      # counted
    entry(12, "/bin/bash", 1)                         # not python
    entry(13, "/usr/bin/python3", 77)                 # a child of this process (77): not counted
    entry(77, "/usr/local/bin/python3", 1)            # this process: not counted
    entry(14, "/usr/bin/python3", 1, stat=False)      # unreadable: skipped
    (proc / "self").mkdir()
    assert V6._other_python_processes(proc, me=77) == 2
    assert V6._other_python_processes(tmp_path / "absent", me=77) is None
    if not Path("/proc").is_dir():
        return
    # on this machine: a python grandchild (a child's child) is another python process
    import os
    import signal
    import time
    sleeper = subprocess.Popen(["sh", "-c", f"'{sys.executable}' -c 'import time; time.sleep(60)' & wait"],
                               start_new_session=True)
    try:
        deadline = time.monotonic() + 15
        while (V6._other_python_processes() or 0) < 1 and time.monotonic() < deadline:
            time.sleep(0.05)
        assert V6._other_python_processes() >= 1
    finally:
        os.killpg(sleeper.pid, signal.SIGKILL)
        sleeper.wait()


# ------------------------------------------------------------------ an arm that raises never aborts the look
def _stub_arms(raises=()):
    """Runners that answer with the in-process PMCF plan (scored by run_v4.f7_score) and raise RuntimeError for each
    (arm, item_id) in ``raises``. Nothing runs through cortex.reason."""
    def make(arm):
        def run(item):
            if (arm, item["item_id"]) in set(raises):
                raise RuntimeError(f"boom in {arm}")
            plan = V6.V4.parametric_min_cost_flow(item["payload"]["capacity_network"])
            result, throughput = V6.V4.f7_score(item, plan)
            record = {"result": result, "throughput": throughput, "seconds": 0.4 if arm == V6.GENOME else 1.2,
                      "stages": 1, "state": "NONE" if arm == V6.GENOME else "ANSWERED", "answer": plan}
            if arm == V6.GENOME:
                record.update(plan_score=result, method=V6.GENOME_CAPABILITY, method_version="0.2.0",
                              proof_intelligence_id=V6.GENOME_INTELLIGENCE, proof_version=V6.GENOME_VERSION,
                              verifier="STRUCTURALLY_VERIFIED")
            elif arm == V6.ROUTED:
                record["recipe"] = V6.RECIPE
            elif arm == V6.COMPILED:
                record["selected"] = V6.GENOME_CAPABILITY
            return record
        return run
    return {arm: make(arm) for arm in V6.ARMS}


def test_an_arm_that_raises_on_an_item_is_recorded_and_the_run_goes_on(tmp_path, monkeypatch):
    items = V6.suite_items("dev")[:3]                                         # development items only
    raises = {(V6.GENOME, items[1]["item_id"]), (V6.ROUTED, items[2]["item_id"])}
    monkeypatch.setattr(V6, "RUNNERS", _stub_arms(raises))
    rows = V6.run_items(items, "dev")["rows"]
    assert [r["item_id"] for r in rows] == [i["item_id"] for i in items]
    crashed = rows[1]["arms"][V6.GENOME]
    assert (crashed["result"], crashed["plan_score"], crashed["state"], crashed["answer"], crashed["throughput"]) == (
        "no_decision", "no_decision", V6.ARM_EXCEPTION, None, None)
    assert crashed["exception"] == f"RuntimeError: boom in {V6.GENOME}" and crashed["seconds"] >= 0
    assert rows[2]["arms"][V6.ROUTED]["state"] == V6.ARM_EXCEPTION and "plan_score" not in rows[2]["arms"][V6.ROUTED]
    assert rows[1]["arms"][V6.ROUTED]["result"] == rows[2]["arms"][V6.GENOME]["result"] == "optimal"   # others ran
    assert all(r["arms"][V6.PMCF]["result"] == "optimal" for r in rows)
    assert all(r["independent"]["truth_agrees"] and all(a["agrees"] for a in r["independent"]["arms"].values())
               for r in rows)
    assert V6.receipt_problems(rows) == []                                    # a runner that raised left no receipt
    d = V6.decide(rows)
    assert d["outcome"] == "NO_MATCH" and d["failed"] == ["GENOME_DECIDES_EVERY_ITEM"]
    assert d["comparator_replicated"] is False and d["states"][V6.GENOME][V6.ARM_EXCEPTION] == 1
    assert (d["wins"], d["losses"]) == (1, 1)
    out = tmp_path / "development.json"                                       # the development path writes its report
    monkeypatch.setattr(V6, "suite_items", lambda partition: items if partition == "dev" else _never())
    V6.main(["--development", "--out", str(out)])
    summary = json.loads(out.read_text())["summary"]
    assert summary["arm_exceptions"]["count"] == {V6.GENOME: 1, V6.ROUTED: 1}
    assert summary["rule"]["outcome"] == "NO_MATCH"


def test_a_heldout_run_survives_an_arm_exception_and_always_writes_its_report(tmp_path, monkeypatch):
    dev = V6.suite_items("dev")
    synthetic = [{**copy.deepcopy(item), "item_id": f"F7-synthetic-heldout-{i}", "partition": "heldout"}
                 for i, item in enumerate(dev[1:4])]          # development data relabelled: no held-out item is read
    frozen = {"code": {"a.py": "sha256:a"}}
    _clean_gate(monkeypatch, tmp_path, frozen)

    def gate(manifest=None):
        token = V6._HeldoutToken()
        V6._ISSUED.add(token)
        return {"inputs": frozen, "token": token}
    monkeypatch.setattr(V6, "heldout_gate", gate)
    monkeypatch.setattr(V6, "_process_record", lambda: {"loaded": ["a.py"], "executed": {"a.py": "sha256:a"},
                                                        "distributions": {"numpy": "1"}})
    read = []

    def items(partition):
        read.append(partition)
        return dev[:1] if partition == "dev" else synthetic
    monkeypatch.setattr(V6, "suite_items", items)
    monkeypatch.setattr(V6, "RUNNERS", _stub_arms({(V6.GENOME, synthetic[1]["item_id"])}))
    out = tmp_path / "results.json"
    V6.main(["--out", str(out)])
    report = json.loads(out.read_text())
    assert read == ["dev", "heldout"] and len(report["heldout"]) == 3 and report["integrity"] == []
    rule = report["summary"]["rule"]
    assert rule["outcome"] == "NO_MATCH" and rule["failed"] == ["GENOME_DECIDES_EVERY_ITEM"]
    assert report["summary"]["arm_exceptions"]["items"] == [
        {"item_id": synthetic[1]["item_id"], "arm": V6.GENOME, "exception": f"RuntimeError: boom in {V6.GENOME}"}]
    # the look reads v4's held-out constituent counts, never its development ones (final check, 2026-10-16)
    assert report["summary"]["f7_lift_with_genome"]["counts_source"] == V6.V4_EVIDENCE["heldout"]
    # a post-run step that raises still leaves a report: INVALID_RUN, the rows kept
    monkeypatch.setattr(V6, "summarize", lambda rows, v4=None: 1 / 0)
    out = tmp_path / "results-2.json"
    V6.main(["--out", str(out)])
    report = json.loads(out.read_text())
    assert len(report["heldout"]) == 3
    for key in ("rule", "f7_lift_with_genome"):
        assert report["summary"][key]["outcome"] == "INVALID_RUN"
        assert report["summary"][key]["why"][0].startswith("POST_RUN_EXCEPTION: ZeroDivisionError")
    # an arm that raises on the warm-up item stops the run before the look
    read.clear()
    monkeypatch.setattr(V6, "RUNNERS", _stub_arms({(V6.ROUTED, dev[0]["item_id"])}))
    out = tmp_path / "results-3.json"
    with pytest.raises(SystemExit, match="WARMUP_ARM_EXCEPTION"):
        V6.main(["--out", str(out)])
    assert read == ["dev"] and not out.exists()


# ------------------------------------------------------------------ the secondary decision F7_LIFT_WITH_GENOME
def _v4(n=200, greedy=(108, 0), blind=(19, 0)):
    return {"source": "synthetic", "partition": "heldout", "item_ids": [f"F7-n-{i}" for i in range(n)],
            "counts": {"graph_alone_greedy": {"optimal": greedy[0], "wrong": greedy[1]},
                       "optimize_flow_blind": {"optimal": blind[0], "wrong": blind[1]}}}


def _f7_rows(genome, routed=None, genome_s=0.4, routed_s=1.2):
    routed = routed or ["optimal"] * len(genome)
    return [_row(g, k, genome_s, routed_s, item_id=f"F7-n-{i}") for i, (g, k) in enumerate(zip(genome, routed))]


def test_f7_lift_with_genome_reads_v4s_rule_with_the_genome_as_a_constituent():
    v4 = _v4()
    tie = V6.f7_lift_with_genome(_f7_rows(["optimal"] * 200), v4)             # the genome ties routed: no lift
    assert (tie["outcome"], tie["best_constituent"]) == ("NO_LIFT", V6.GENOME)
    assert tie["failed"] == ["ROUTED_MORE_OPTIMAL", "SIGN_TEST_P_BELOW_ALPHA"]
    assert (tie["routed_wins"], tie["routed_losses"], tie["sign_test_p_one_sided"]) == (0, 0, 1.0)
    assert tie["constituents"][V6.GENOME] == {"optimal": 200, "wrong": 0, "from": "this run"}

    loses = ["optimal"] * 190 + ["suboptimal"] * 10                           # the genome loses 0-10
    d = V6.f7_lift_with_genome(_f7_rows(loses), v4)
    assert (d["outcome"], d["failed"], d["best_constituent"]) == ("LIFT", [], V6.GENOME)
    assert all(d["conditions"].values()) and list(d["conditions"]) == list(V6.F7_CONDITIONS)
    assert (d["routed_wins"], d["routed_losses"], d["sign_test_p_one_sided"]) == (10, 0, round(1 / 1024, 6))
    assert d["median_seconds"] == {V6.GENOME: 0.4, V6.ROUTED: 1.2} and d["latency_ratio_routed_over_best"] == 3.0
    assert V6.f7_lift_with_genome(_f7_rows(loses, genome_s=0.1, routed_s=1.0), v4)["outcome"] == "LIFT"   # 10x
    d = V6.f7_lift_with_genome(_f7_rows(loses, genome_s=0.09996, routed_s=1.0), v4)   # medians rounded as v4 rounds
    assert (d["outcome"], d["median_seconds"][V6.GENOME]) == ("LIFT", 0.1)            # (unrounded: 10.004x, fails)
    d = V6.f7_lift_with_genome(_f7_rows(loses, genome_s=0.1, routed_s=1.2), v4)
    assert (d["outcome"], d["failed"]) == ("NO_LIFT", ["ROUTED_MEDIAN_WITHIN_MULTIPLIER"])
    assert V6.f7_lift_with_genome(_f7_rows(loses, genome_s=6.0, routed_s=60.0), v4)["outcome"] == "LIFT"  # 60 s
    d = V6.f7_lift_with_genome(_f7_rows(loses, genome_s=7.0, routed_s=60.5), v4)
    assert d["failed"] == ["ROUTED_MEDIAN_WITHIN_CHAIN_BUDGET"]
    d = V6.f7_lift_with_genome(_f7_rows(["optimal"] * 196 + ["suboptimal"] * 4), v4)       # 0-4: p = 1/16
    assert d["failed"] == ["SIGN_TEST_P_BELOW_ALPHA"]
    assert V6.f7_lift_with_genome(_f7_rows(["optimal"] * 195 + ["suboptimal"] * 5), v4)["outcome"] == "LIFT"
    d = V6.f7_lift_with_genome(_f7_rows(["optimal"] * 150 + ["suboptimal"] * 50,
                                        routed=["optimal"] * 199 + ["wrong"]), v4)
    assert d["failed"] == ["ROUTED_NO_MORE_WRONG"]                           # a routed wrong answer the genome lacks
    assert "LIFT" in d["v4_verdict"] and d["expected"].startswith("NO_LIFT")


def test_f7_lift_with_genome_is_inconclusive_when_v4s_constituent_is_best_or_the_items_are_not_v4s():
    v4 = _v4()
    d = V6.f7_lift_with_genome(_f7_rows(["optimal"] * 100 + ["suboptimal"] * 100), v4)    # worse than greedy's 108
    assert (d["outcome"], d["best_constituent"], d["conditions"], d["failed"]) == (
        "INCONCLUSIVE", "graph_alone_greedy", None, None)
    assert d["why"][0].startswith("BEST_CONSTITUENT_IS_V4s: graph_alone_greedy (108 optimal, 0 wrong)")
    tied = V6.f7_lift_with_genome(_f7_rows(["optimal"] * 108 + ["suboptimal"] * 92), v4)  # a full tie keeps v4's
    assert (tied["outcome"], tied["best_constituent"]) == ("INCONCLUSIVE", "graph_alone_greedy")
    fewer_wrong = V6.f7_lift_with_genome(_f7_rows(["optimal"] * 108 + ["suboptimal"] * 92), _v4(greedy=(108, 1)))
    assert (fewer_wrong["outcome"], fewer_wrong["best_constituent"]) == ("LIFT", V6.GENOME)
    d = V6.f7_lift_with_genome(_f7_rows(["no_decision"] * 200), v4)          # an abstaining genome is never best
    assert (d["outcome"], d["best_constituent"]) == ("INCONCLUSIVE", "graph_alone_greedy")
    for rows in (_f7_rows(["optimal"] * 199), [{**r, "item_id": "F7-other-0"} if i == 0 else r
                                               for i, r in enumerate(_f7_rows(["optimal"] * 200))]):
        d = V6.f7_lift_with_genome(rows, v4)
        assert d["outcome"] == "INCONCLUSIVE" and d["why"][0].startswith("ITEMS_DIFFER"), d["why"]
    rows = _f7_rows(["optimal"] * 200)
    rows[3] = _row(routed_agrees=False, item_id="F7-n-3")
    d = V6.f7_lift_with_genome(rows, v4)
    assert d["outcome"] == "INCONCLUSIVE" and d["why"][0].startswith("INDEPENDENT_RESCORING_DISAGREES")
    rows[3] = _row("wrong", genome_state="REFUTED", genome_agrees=False, item_id="F7-n-3")   # the refutation decides
    d = V6.f7_lift_with_genome(rows, v4)
    assert (d["outcome"], d["failed"], d["constituents"][V6.GENOME]["wrong"]) == (
        "NO_LIFT", ["SIGN_TEST_P_BELOW_ALPHA"], 1)


def test_v4_constituent_counts_are_v4s_frozen_counts_on_the_same_items(tmp_path, monkeypatch):
    results = json.loads((V6.ROOT / V6.V4_EVIDENCE["heldout"]).read_text())
    held = V6.v4_constituents("heldout")
    assert held["counts"] == {n: {k: results["summary"]["F7"]["outcomes"][n][k] for k in ("optimal", "wrong")}
                              for n in V6.V4.CONSTITUENTS["F7"]}
    assert held["counts"] == {"graph_alone_greedy": {"optimal": 108, "wrong": 0},
                              "optimize_flow_blind": {"optimal": 19, "wrong": 0}}
    suite = json.loads(V6.SUITE.read_text())["items"]                        # item ids only; no arm runs on them
    assert held["item_ids"] == [i["item_id"] for i in suite if i["partition"] == "heldout"]
    dev = V6.v4_constituents("dev")
    assert dev["item_ids"] == [i["item_id"] for i in V6.suite_items("dev")]
    assert dev["counts"] == {"graph_alone_greedy": {"optimal": 23, "wrong": 0},
                             "optimize_flow_blind": {"optimal": 6, "wrong": 0}}
    assert V6.V4.VERDICT_RULE in V6.F7_RULE and results["summary"]["VPL_v4"]["rule"] == V6.V4.VERDICT_RULE
    for edit, why in ((lambda r: r["heldout"][0]["arms"]["graph_alone_greedy"].update(result="optimal"),
                       "do not reproduce its summary"),
                      (lambda r: r["summary"]["VPL_v4"].update(rule="another rule"), "not run_v4.VERDICT_RULE")):
        tampered = copy.deepcopy(results)
        edit(tampered)
        path = tmp_path / "results-v4.json"
        path.write_text(json.dumps(tampered))
        monkeypatch.setattr(V6, "V4_EVIDENCE", {**V6.V4_EVIDENCE, "heldout": str(path)})
        with pytest.raises(ValueError, match=why):
            V6.v4_constituents("heldout")


# ------------------------------------------------------------------ development smoke run
def test_a_development_smoke_run_on_two_items_reads_development_items_only(tmp_path, monkeypatch):
    # run_v6 attaches the genome on run_v4's cached evaluation view; a fresh view here, restored afterwards, keeps
    # that attachment out of every other test that uses run_v4's registry
    monkeypatch.setattr(V6.V4, "_REGISTRY", None)
    read, ran = [], []
    real_items, real_run = V6.suite_items, V6.run_items

    def items(partition):
        read.append(partition)
        return real_items(partition)

    def run(items_, partition, *args, **kwargs):
        ran.extend((i["item_id"], i["partition"]) for i in items_)
        return real_run(items_, partition, *args, **kwargs)
    monkeypatch.setattr(V6, "suite_items", items)
    monkeypatch.setattr(V6, "run_items", run)
    out = tmp_path / "development.json"
    V6.main(["--development", "--limit", "2", "--out", str(out)])
    assert read == ["dev"] and [p for _, p in ran] == ["dev", "dev"]
    report = json.loads(out.read_text())
    rows, summary = report["rows"], report["summary"]
    assert report["partition"] == "dev" and [r["partition"] for r in rows] == ["dev", "dev"]
    assert {r["network"] for r in rows} <= set(V6.V4.partition()[0])
    assert summary["n"] == 2 and set(rows[0]["arms"]) == set(V6.ARMS)
    for row in rows:
        genome = row["arms"][V6.GENOME]
        assert genome["method"] == V6.GENOME_CAPABILITY and genome["verifier"] == "STRUCTURALLY_VERIFIED"
        assert (genome["proof_intelligence_id"], genome["proof_version"]) == (V6.GENOME_INTELLIGENCE,
                                                                              V6.GENOME_VERSION)
        assert genome["result"] == genome["plan_score"] == "optimal"
        assert genome["throughput"] == row["truth"]["optimum"]
        assert row["arms"][V6.ROUTED]["recipe"] == V6.RECIPE
        assert row["arms"][V6.PMCF]["throughput"] == row["truth"]["optimum"]
        assert all(row["arms"][a]["result"] in V6.OUTCOMES for a in V6.ARMS)
        assert row["independent"]["truth_agrees"] and all(a["agrees"] for a in row["independent"]["arms"].values())
    assert report["receipt_problems"] == []
    assert summary["independent_rescoring"]["truth_agreement"] == 2
    assert report["preconditions"] == V6.preconditions()
    if not report["preconditions"]:                       # the DEFAULT verdict is current: the compiler serves it
        assert summary["compiler"]["selected_genome_on_every_item"] is True
    assert summary["rule"]["outcome"] in ("MATCH", "NO_MATCH", "INCONCLUSIVE") and summary["rule"]["n"] == 2
    assert set(report["machine_load_end"]) == set(report["machine_load_start"])
    secondary = summary["f7_lift_with_genome"]                # two development items are not v4's 50: no reading
    assert secondary["outcome"] == "INCONCLUSIVE" and secondary["why"][0].startswith("ITEMS_DIFFER")
    assert secondary["counts_source"] == V6.V4_EVIDENCE["dev"] and summary["arm_exceptions"]["count"] == {}
