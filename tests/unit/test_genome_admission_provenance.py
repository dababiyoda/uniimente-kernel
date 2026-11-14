"""What an admission run records about its own source (greg/cognition/genomes/admission.py), checked without
running ``--freeze`` or ``--run``: no held-out instance is generated here.

Found by the 2026-10-15 independent review (E9): the v3 results.json recorded ``source_commit`` but not whether the
frozen files were the committed ones, so its README's "clean worktree" rested on the operator's word. The freeze
digests bind the bytes a run executes; ``source_dirty`` binds them to the recorded commit, as P8's record does.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

from greg.cognition.genomes import admission, library

ROOT = Path(__file__).resolve().parents[2]
ADMISSION_RUNS = ROOT / "docs" / "evidence" / "greg-genome-admission"

GIT = ["git", "-c", "user.email=test@example.invalid", "-c", "user.name=test", "-c", "commit.gpgsign=false"]


def _repo(root: Path, files: dict) -> Path:
    root.mkdir()
    subprocess.run([*GIT, "init", "-q"], cwd=root, check=True)
    for name, text in files.items():
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_text(text)
    subprocess.run([*GIT, "add", "-A"], cwd=root, check=True)
    subprocess.run([*GIT, "commit", "-q", "-m", "base"], cwd=root, check=True)
    return root


def test_source_dirty_names_every_frozen_file_whose_bytes_are_not_its_commit(tmp_path):
    repo = _repo(tmp_path / "repo", {"a.py": "a = 1\n", "pkg/b.py": "b = 1\n", "data.bin": "x"})
    frozen = ["pkg/b.py", "a.py", "data.bin"]
    assert admission.source_dirty(frozen, root=repo) == []                       # a clean tree records nothing
    (repo / "a.py").write_text("a = 2\n")                                         # modified in the worktree
    (repo / "c.py").write_text("c = 1\n")                                         # untracked, never committed
    assert admission.source_dirty([*frozen, "c.py"], root=repo) == ["a.py", "c.py"]
    (repo / "pkg/b.py").write_text("b = 2\n")
    subprocess.run([*GIT, "add", "pkg/b.py"], cwd=repo, check=True)               # staged is still not committed
    assert admission.source_dirty([*frozen, "c.py"], root=repo) == ["a.py", "c.py", "pkg/b.py"]
    (repo / "a.py").write_text("a = 1\n")                                         # restored bytes are clean again
    assert admission.source_dirty(frozen, root=repo) == ["pkg/b.py"]


def test_source_dirty_names_every_path_when_git_cannot_tell(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))                # no repository above tmp_path
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "a.py").write_text("a = 1\n")
    assert admission.source_dirty(["a.py"], root=plain) == ["a.py"]              # not a repository
    repo = _repo(tmp_path / "repo", {"a.py": "a = 1\n"})
    assert admission.source_dirty(["a.py", "gone.py"], root=repo) == ["a.py", "gone.py"]   # an unreadable path


def test_the_results_header_records_the_dirty_state_of_the_frozen_files(tmp_path):
    frozen = {"inputs": {"code": {"greg/cognition/genomes/admission.py": "sha256:x",
                                  "tools/offline_test.py": "sha256:y"}}}
    (tmp_path / "freeze.json").write_text(json.dumps(frozen))
    header = admission.report_header(tmp_path, frozen)
    assert header["source_dirty"] == admission.source_dirty(frozen["inputs"]["code"])
    assert set(header["source_dirty"]) <= set(frozen["inputs"]["code"])
    assert header["rule"] == admission.RULE and header["genomes"] == {} and header["source_commit"]


# ------------------------------------------------------------------ diagnostics (2026-10-16): reported, never decide
# Review of grid_dijkstra 1.1.0: the same code read 1.22x its baseline in admission v3 and 1.7-4.0x on a loaded
# host, because load inflates the arms' wall-clock medians unevenly. The rule still decides on wall-clock medians;
# a run now also records each call's thread CPU time, the per-arm CPU medians and the host's load, so a reader can
# see how loaded the host was. Nothing here changes RULE, decide() or a threshold.
def _sleep(data):
    time.sleep(0.03)


def _spin(data):
    end = time.thread_time() + 0.03
    while time.thread_time() < end:
        pass


def _on_another_thread(data):
    worker = threading.Thread(target=_spin, args=(data,))
    worker.start()
    worker.join()


def test_the_cpu_clock_counts_the_calling_threads_work_and_encloses_the_unchanged_wall_clock_window():
    _, seconds, cpu, info = admission._arm(_sleep, {})
    assert seconds >= 0.03 and 0 <= cpu < 0.015 and info == {}                # waiting is wall time, not CPU
    _, seconds, cpu, _ = admission._arm(_spin, {})
    assert cpu >= 0.03 and seconds >= 0.029                                   # this thread's own work is both
    _, seconds, cpu, _ = admission._arm(_on_another_thread, {})
    assert seconds >= 0.03 and 0 <= cpu < 0.015          # another thread's work is not in it (the stated caveat)
    _, seconds, cpu, info = admission._arm(lambda data: 1 / 0, {})
    assert info["error"].startswith("ZeroDivisionError") and seconds >= 0 and cpu >= 0


def test_every_call_records_cpu_seconds_beside_seconds_and_the_decision_never_reads_them():
    item = library.executables()["flow_maxflow"]

    def waiting_solve(data, budget):                                          # waits, then answers as usual
        time.sleep(0.03)
        return item.solve(data, budget)
    slow = type(item)(**{**item.__dict__, "solve": waiting_solve, "baseline": _sleep})
    rows = admission.evaluate(slow, admission.DEV_SEEDS[:3])
    for row in rows:
        for arm in row["arms"].values():
            assert type(arm["cpu_seconds"]) is float and arm["cpu_seconds"] >= 0 and type(arm["seconds"]) is float
        for arm in ("candidate", "baseline"):                 # the 30 ms wait is wall time, never CPU time
            assert row["arms"][arm]["seconds"] - row["arms"][arm]["cpu_seconds"] >= 0.025, arm
        assert row["arms"]["candidate"]["category"] == "correct"
    decided = admission.decide(slow, rows)
    for change in (lambda arm: arm.pop("cpu_seconds"),
                   lambda arm: arm.update(cpu_seconds=arm["cpu_seconds"] * 1e3 + 9)):
        other = copy.deepcopy(rows)
        for row in other:
            for arm in row["arms"].values():
                change(arm)
        assert admission.decide(slow, other) == decided


def test_per_arm_median_cpu_seconds_are_reported_and_rows_from_before_read_as_none():
    rows = [{"arms": {arm: {"seconds": 1.0, "cpu_seconds": c * k} for arm, k in
                      (("candidate", 1), ("baseline", 2), ("competitor", 3))}} for c in (0.1, 0.3, 0.2)]
    reported = admission.diagnostics(rows)
    assert reported["median_cpu_seconds"] == {"candidate": 0.2, "baseline": 0.4, "competitor": 0.6}
    assert "never inputs to the admission decision" in reported["note"]
    del rows[0]["arms"]["baseline"]["cpu_seconds"]
    assert admission.diagnostics(rows)["median_cpu_seconds"]["baseline"] is None      # never a partial median
    # genome-admission runs only: the converged tree also holds PR #155's operation-family runs in this directory
    # (keyed "families", written by another harness), which carry no per-arm genome rows
    runs = [p for p in sorted(ADMISSION_RUNS.glob("*/results.json")) if "genomes" in json.loads(p.read_text())]
    before = [p for p in runs if p.parent.name < "2026-10-16"]           # v1-v3, written before diagnostics
    assert len(before) == 3
    for path in runs:
        for family, entry in json.loads(path.read_text())["genomes"].items():
            medians = admission.diagnostics(entry["heldout"])["median_cpu_seconds"]
            if path in before:
                assert medians == {"candidate": None, "baseline": None, "competitor": None}, (path, family)
            else:                                                             # v4 on: recorded, and what they record
                assert medians == entry["diagnostics"]["median_cpu_seconds"] and None not in medians.values(), \
                    (path, family)


def _stat(proc: Path, pid: int, comm: str, state: str, processor: int, cmdline: bytes) -> None:
    fields = [state] + ["0"] * 35 + [str(processor)] + ["0"] * 13             # stat fields 3-52; 39 is the CPU
    (proc / str(pid)).mkdir()
    (proc / str(pid) / "stat").write_text(f"{pid} ({comm}) {' '.join(fields)}\n")
    (proc / str(pid) / "cmdline").write_bytes(cmdline)


def test_host_load_reads_loadavg_affinity_and_the_other_python_processes(tmp_path):
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "loadavg").write_text("7.92 6.10 5.55 9/412 77777\n")
    ours = sorted(os.sched_getaffinity(0))
    mine, elsewhere = ours[0], max(ours) + 1
    _stat(proc, 101, "python3", "R", mine, b"/usr/bin/python3\0-m\0pytest\0")
    _stat(proc, 102, "python3.13", "R", elsewhere, b"python3.13\0x.py\0")
    _stat(proc, 103, "python3", "S", mine, b"/usr/bin/python3\0y.py\0")
    _stat(proc, 104, "python3", "Z", mine, b"")                              # a zombie: no command line
    _stat(proc, 105, "pytest", "R", mine, b"/usr/bin/python3\0/usr/bin/pytest\0")   # a script run by its #! line
    _stat(proc, 106, "bash", "R", mine, b"/bin/bash\0")
    _stat(proc, 107, "python3 (w) x", "S", mine, b"")                         # a name with spaces and parentheses
    _stat(proc, os.getpid(), "python3", "R", mine, b"python3\0")              # this process is not another
    (proc / "self").mkdir()
    (proc / "999").mkdir()                                                    # exited while being read: no stat
    load = admission.host_load(proc)
    assert load["loadavg"] == {"1m": 7.92, "5m": 6.10, "15m": 5.55, "runnable": 9, "entities": 412}
    assert load["cpu_affinity"] == ours and load["cpu_count"] == os.cpu_count() and load["at"]
    assert load["other_python_processes"] == {"count": 6, "by_state": {"R": 3, "S": 2, "Z": 1},
                                              "running_last_on_our_cpus": 2}
    absent = admission.host_load(tmp_path / "absent")
    assert absent["loadavg"] is None and absent["other_python_processes"] is None


def test_the_results_header_records_the_host_load_at_the_start_and_the_end_of_the_run(tmp_path):
    frozen = {"inputs": {"code": {"tools/offline_test.py": "sha256:y"}}}
    (tmp_path / "freeze.json").write_text(json.dumps(frozen))
    report = admission.report_header(tmp_path, frozen)
    assert list(report["host_load"]) == ["start"] and report["host_load"]["start"]["cpu_affinity"]
    assert report["diagnostics"] == admission.DIAGNOSTICS and "never inputs" in report["diagnostics"]
    assert admission.close_report(report) is report
    assert list(report["host_load"]) == ["start", "end"] and report["finished_at"]
    assert report["host_load"]["start"]["at"] <= report["host_load"]["end"]["at"]


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _old_shape(report: dict) -> dict:
    """The same results as admission v1-v3 wrote them: no diagnostics anywhere."""
    old = copy.deepcopy(report)
    del old["diagnostics"], old["host_load"]
    for entry in old["genomes"].values():
        del entry["diagnostics"]
        for row in entry["heldout"]:
            for arm in row["arms"].values():
                del arm["cpu_seconds"]
    return old


def test_every_reader_of_admission_results_reads_the_new_shape_as_it_reads_the_old(tmp_path, monkeypatch):
    """The index builder, admission v3's README table script, the reality ledger and the compiler give the same
    answers for a results file with the diagnostics and for the same file without them (the v1-v3 shape)."""
    frozen = {"inputs": {"code": {"tools/offline_test.py": "sha256:y"}}}
    (tmp_path / "freeze.json").write_text(json.dumps(frozen))
    report = admission.report_header(tmp_path, frozen)
    for family in ("grid_dijkstra", "flow_maxflow"):           # development seeds only, a stub canonical smoke
        item = library.executables()[family]
        rows = admission.evaluate(item, admission.DEV_SEEDS[:3])
        status, detail = admission.decide(item, rows)
        entry = admission.genome_entry(item, rows, status, detail, {"verifier": "STRUCTURALLY_VERIFIED"})
        assert entry["diagnostics"] == admission.diagnostics(rows) and entry["heldout"] == rows
        assert entry["status"] == status and entry["arms"] == detail["arms"]
        report["genomes"][family] = entry
    shapes = {"new": admission.close_report(report), "old": _old_shape(report)}
    builder = _module("_build_index_shapes", ROOT / "scripts" / "build_mind_evidence_index.py")
    indexes, tables = {}, {}
    prior = tmp_path / "prior.json"
    prior.write_text(json.dumps({"genomes": {}}))
    for shape, results in shapes.items():
        run = tmp_path / shape / builder.ADMISSION / "2026-10-16-dev"
        run.mkdir(parents=True)
        (run / "results.json").write_text(json.dumps(results, indent=1) + "\n")
        monkeypatch.setattr(builder, "ROOT", tmp_path / shape)
        indexes[shape] = builder.build()
        tables[shape] = subprocess.run(
            [sys.executable, "-I", str(ADMISSION_RUNS / "2026-10-15-v3" / "make_readme_tables.py"),
             str(run / "results.json"), str(prior)], capture_output=True, text=True, check=True).stdout
    assert indexes["new"]["genomes"] == indexes["old"]["genomes"]
    grid = indexes["new"]["genomes"]["grid_dijkstra"]
    assert grid["median_seconds"] == report["genomes"]["grid_dijkstra"]["arms"]["candidate"]["median_seconds"]
    assert not any("cpu" in key or "host" in key for record in indexes["new"]["genomes"].values() for key in record)
    assert tables["new"] == tables["old"] and "`grid_dijkstra`" in tables["new"]
    status = _module("_mind_status_shapes", ROOT / "scripts" / "mind_status.py")
    labels = {}
    for shape, index in indexes.items():
        path = tmp_path / shape / "index.json"
        path.write_text(json.dumps(index))
        labels[shape] = [(r["id"], r["label"], r["basis"])
                         for r in status.status(index_path=path, evidence_root=tmp_path / shape)["mechanisms"]]
    assert labels["new"] == labels["old"]
    from greg.cognition import compiler
    data, _ = library.executables()["grid_dijkstra"].instance(1)
    geometry = compiler.CompetencyGeometry.parse({"geometry": "optimization"})
    assert compiler.candidates(data, geometry, indexes["new"]) == compiler.candidates(data, geometry, indexes["old"])
