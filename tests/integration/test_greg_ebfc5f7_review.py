"""Fifth review of PR #184: #169's ebfc5f7 merged (Foundry #52 source repair, #26 acceptance from the relay journal).

* R52-1: code from the copied tree leaving a FIFO (or a socket) in its run's tree no longer hangs the repair's
  tamper scan forever with the store locked, or aborts it with a raw OSError: the run is rejected as tampering.
* R52-2: a diagnosis report whose rows have the wrong shape is a refusal (RepairError), not a crash.
* M1: the recorded Foundry #52 evidence no longer counts the frozen import closure, which moved with every unrelated
  import, and no evidence record claims a CI re-run its row does not get.
* F2: a page on another tenant of a shared suffix, a sibling host or another address is never labelled a
  read-after-write through the service's own host.
* F3: network_confined says what it counts (a connection any part of GREG made) and names who made them.
* F4: undeclared_destination_denied counts only refusals of a destination, not a request limit or malformed request.
* F5: a relay journal whose last line a crash cut short no longer crashes `greg acceptance`, and the next append
  keeps the chain intact.
* L1: every runbook step the acceptance report names exists in the runbook.

A second round, on those fixes (separate attackers; each confirmed finding reproduced by a skeptic):

* F1, F4: a run's report is read one name at a time without following a link or blocking, so a sandbox still
  running after a timeout cannot point it at a host file or swap in a FIFO; the tree walks never stat through a link.
* F2: a run's tree is compared with an early exit and a size check before hashing, so a flood of sparse files does
  not set the parent's cost.
* F3: a report nested deep enough to exhaust the decoder is a refusal, not a RecursionError.
* SEG-1: two torn tails at the same offset keep both sidecars, and each move is chained.
* SEG-3: a committed row that does not parse is a broken chain on every surface, not a crash.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import threading
import time
from pathlib import Path

import pytest

from foundry import completion
from foundry.systems import repair
from foundry.systems.segmentation import Journal
from greg import acceptance
from greg.acceptance import report
from greg.templates import remote_evidence
from tests.integration.test_greg_confined_egress import body_with_confined_egress
from tests.unit.test_foundry_repair_source import make_tree, run_repair


def status_of(result):
    return {p["property"]: p["status"] for p in result["properties"]}


# -- R52-1 ---------------------------------------------------------------------------------------------------

def manifest_within(tree: Path, seconds: float = 10.0) -> dict:
    out: dict = {}
    worker = threading.Thread(target=lambda: out.update(m=repair._manifest(tree)), daemon=True)
    worker.start()
    worker.join(seconds)
    assert not worker.is_alive(), "the tamper scan blocked on a special file the tree code left behind"
    return out["m"]


def test_a_fifo_or_socket_left_in_the_tree_is_tampering_and_never_blocks_the_scan(tmp_path):
    tree = make_tree(tmp_path / "t")
    clean = repair._manifest(tree)
    os.mkfifo(tree / "trap")                       # its writer died with the namespace: opening it would wait forever
    here = os.getcwd()
    os.chdir(tree)                                 # a short relative path keeps the socket under the 108-byte limit
    try:
        sock = socket.socket(socket.AF_UNIX)
        sock.bind("sock")
    finally:
        os.chdir(here)
    try:
        seen = manifest_within(tree)
    finally:
        sock.close()
    assert seen["trap"] == "special:fifo" and seen["sock"] == "special:socket"
    assert {"trap", "sock"} <= set(repair.tampered(clean, seen))


# -- R52-2 ---------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("rows", [[1, 2, 3], [{"lines": [[1]]}] * 3, [{"lines": ["x"]}] * 3,
                                  [{"lines": [True]}] * 3, [{"lines": [1], "observed": 5}] * 3,
                                  [{"lines": [1], "equals_expected": "yes"}] * 3, "deep"])
def test_a_malformed_diagnosis_report_is_a_refusal_not_a_crash(tmp_path, monkeypatch, rows):
    # The tracer runs in the same interpreter as the code under repair, which can rewrite its report.
    def traced(self, argv_for, target_source=None):
        report = b"[" * 100000 if rows == "deep" else json.dumps(rows).encode()
        return {"status": "exited", "code": 0, "tail": "", "report": report, "tampered": []}
    monkeypatch.setattr(repair._Runner, "run", traced)
    with pytest.raises(repair.RepairError, match="diagnosis could not run the target"):
        run_repair(tmp_path, make_tree(tmp_path / "t"))


# -- M1 ------------------------------------------------------------------------------------------------------

def test_the_foundry_52_evidence_does_not_count_the_frozen_import_closure():
    recorded = json.loads((completion.ROOT / "foundry/evidence/system-52.json").read_text())
    assert "frozen_files" not in recorded["result"]["source_repair"], \
        "the closure size moves with any unrelated import, so the evidence stops reproducing"


def test_every_evidence_record_says_truly_whether_the_ci_audit_re_runs_it():
    # Both ways: a PARTIAL row's record claims no CI re-run, and a row promoted to COMPLETE must be re-recorded
    # before its record stops saying it is not re-run (second round, R5B-6).
    rows = completion.contract()
    for path in sorted((completion.ROOT / "foundry" / "evidence").glob("system-*.json")):
        record = json.loads(path.read_text())
        state = rows.get(record["system"], {}).get("state")
        assert record["note"] == completion.evidence_note(record["system"], state), (path.name, state)


# -- F2 ------------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("service, page", [
    ("https://notes-mcp.vercel.app/mcp", "https://someone-else.vercel.app/board"),
    ("https://alice.github.io/mcp", "https://mallory.github.io/board"),
    ("https://mcp.notes.co.uk/mcp", "https://evil.co.uk/board"),
    ("https://10.0.0.5/mcp", "https://192.168.0.5/board"),
    ("https://1.2.3.4/mcp", "https://9.9.3.4/board"),
    ("https://notes.example.com/mcp", "https://com/board"),
    ("https://mcp.notes.example/mcp", "https://notes.example/board"),         # a parent name is not the service's
])
def test_a_page_on_another_tenant_or_address_is_never_labelled_the_services_own(service, page):
    assert remote_evidence(service, page) == "separate_host"


@pytest.mark.parametrize("service, page", [
    ("https://notes.example/mcp", "https://notes.example/board"),
    ("https://notes.example/mcp", "https://board.notes.example/x"),
    ("https://NOTES.example./mcp", "https://notes.example/board"),
    ("https://10.0.0.5/mcp", "https://10.0.0.5:8443/board"),
])
def test_the_services_own_host_or_a_name_under_it_is_a_read_after_write(service, page):
    assert remote_evidence(service, page) == "same_service"


# -- F3, F4, F5 ----------------------------------------------------------------------------------------------

def test_network_confined_names_who_made_the_connections_it_counts(tmp_path):
    home, _, _ = body_with_confined_egress(tmp_path)
    Journal(home / "egress-journal.jsonl").append(
        {"identity": "model.anthropic", "host": "api.anthropic.com", "port": 443, "verdict": "ALLOWED"})
    result = report(home)
    prop = next(p for p in result["properties"] if p["property"] == "network_confined")
    assert prop["status"] == "PASS" and "a mission's connection" not in prop["means"]
    assert result["egress"]["allowed_identities"] == ["model.anthropic"]


@pytest.mark.parametrize("row", [
    {"identity": "browser.render", "verdict": "DENIED", "why": "request limit"},
    {"identity": "browser.render", "verdict": "DENIED", "why": "oversized request"},
    {"identity": "browser.render", "verdict": "DENIED", "why": "malformed request", "request": "GARBAGE"},
])
def test_a_refused_request_that_named_no_destination_is_not_a_destination_refusal(tmp_path, row):
    home, _, _ = body_with_confined_egress(tmp_path)
    Journal(home / "egress-journal.jsonl").append(row)
    result = report(home)
    assert status_of(result)["undeclared_destination_denied"] == "NOT_YET"
    assert result["egress"]["denied"] == 0 and result["egress"]["denied_other"] == 1


def test_a_torn_final_journal_line_neither_crashes_the_report_nor_breaks_the_next_append(tmp_path):
    home, _, _ = body_with_confined_egress(tmp_path)
    path = home / "egress-journal.jsonl"
    journal = Journal(path)
    journal.append({"identity": "http.get", "host": "service.test", "port": 443, "verdict": "ALLOWED"})
    with open(path, "a") as fh:
        fh.write('{"identity": "http.get", "host": "serv')                  # power lost mid-append
    result = report(home)                                                    # before: JSONDecodeError
    assert result["egress"]["torn_tail"] is True and result["egress"]["chain_intact"] is True
    assert status_of(result)["network_confined"] == "PASS"
    assert journal.verify()["torn_tail_bytes"] > 0
    journal.append({"identity": "browser.render", "host": "beacon.example.com", "port": 443, "verdict": "DENIED",
                    "why": "host and port are not on this identity's allowlist"})
    check = journal.verify()
    assert check["intact"] and check["entries"] == 3 and "torn_tail_bytes" not in check
    assert check["quarantined_tails"] == 1
    moved = [r for r in journal.read() if r["verdict"] == "TORN_TAIL_QUARANTINED"]
    assert len(moved) == 1 and (home / moved[0]["sidecar"]).read_bytes() == b'{"identity": "http.get", "host": "serv'
    result = report(home)
    assert status_of(result)["undeclared_destination_denied"] == "PASS" and result["egress"]["quarantined_tails"] == 1


def test_a_complete_final_row_that_lost_its_newline_is_kept_and_not_glued_to_the_next(tmp_path):
    path = tmp_path / "egress-journal.jsonl"
    journal = Journal(path)
    journal.append({"identity": "http.get", "host": "a.test", "port": 443, "verdict": "ALLOWED"})
    path.write_bytes(path.read_bytes().rstrip(b"\n"))
    assert len(journal.read()) == 1 and "torn_tail_bytes" not in journal.verify()
    journal.append({"identity": "http.get", "host": "b.test", "port": 443, "verdict": "ALLOWED"})
    assert journal.verify() == {"intact": True, "entries": 2, "head": journal.read()[-1]["hash"]}


def test_damage_in_the_middle_of_the_journal_is_still_an_error():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "j.jsonl"
        journal = Journal(path)
        journal.append({"identity": "x", "verdict": "ALLOWED"})
        journal.append({"identity": "y", "verdict": "ALLOWED"})
        lines = path.read_text().splitlines()
        path.write_text("\n".join([lines[0][:-5], lines[1]]) + "\n")
        with pytest.raises(ValueError):
            journal.read()


# -- L1 ------------------------------------------------------------------------------------------------------

def test_every_runbook_step_the_report_names_exists_in_the_runbook():
    book = (completion.ROOT / acceptance.RUNBOOK).read_text()
    sections = {m.group(1): (m.group(2) + "\n" + m.group(3)).lower()
                for m in re.finditer(r"^## (\d+[a-z]?)\. (.*?)$(.*?)(?=^## |\Z)", book, re.M | re.S)}
    source = Path(acceptance.__file__).read_text()
    named = re.findall(r'"((?:\d+[a-z]?)\. [^"]*)"', source)
    assert named, "the report names runbook steps"
    for step in named:
        for number, label in re.findall(r"(\d+[a-z]?)\. ([^(:,]+)", step):
            label = label.strip().rstrip(".").lower().removesuffix(" then")
            assert number in sections, step
            assert label in sections[number], (step, "is not what runbook section " + number + " says")


# -- second round: F1, F2, F4 (the run's report and tree, read by the parent after the sandbox) -------------

def stub_envelope(monkeypatch, sabotage):
    """The worker envelope replaced by a stand-in whose "run" is ``sabotage(tree)``: what a sandbox can leave behind,
    or keep changing after a timeout, without needing bubblewrap."""
    from greg import worker_isolation, workers

    def prepare(argv, cwd, timeout_seconds, provider, reviewed=False, config_files=None, *, source_env=None,
                network=True, file_bytes=0, door=None):
        runtime = Path(cwd).parent / ".worker-runtime" / provider
        (runtime / "tmp").mkdir(parents=True, exist_ok=True)
        return {"argv": list(argv), "env": {}, "preexec_fn": None, "runtime_root": str(runtime),
                "evidence": {"network_isolated": True, "mechanism": "bubblewrap", "network": "none",
                             "process_isolation": "stand-in", "limits": {"cpu_seconds": 1, "file_bytes": file_bytes}}}

    def run(argv, *, cwd, **_):
        sabotage(Path(cwd))
        return subprocess.CompletedProcess(argv, 0, b"", b"")
    monkeypatch.setattr(worker_isolation, "prepare_worker", prepare)
    monkeypatch.setattr(workers, "supervised_run", run)


def a_runner(tmp_path) -> "repair._Runner":
    pristine = make_tree(tmp_path / "pristine")
    (tmp_path / "scratch").mkdir()
    return repair._Runner(tmp_path / "scratch", pristine, repair._manifest(pristine), "pkg/util.py", 5.0)


def runtime_tmp(tree: Path) -> Path:
    return tree.parent / ".worker-runtime" / repair._RUN_PROVIDER / "tmp"


def test_a_run_cannot_point_its_report_at_a_host_file(tmp_path, monkeypatch):
    host = tmp_path / "host"
    host.mkdir()
    (host / "report").write_text("HOST SECRET")

    def sabotage(tree):                  # the sandbox renames its tmp and leaves a link to a host directory
        runtime_tmp(tree).rename(runtime_tmp(tree).with_name("tmp-old"))
        runtime_tmp(tree).symlink_to(host, target_is_directory=True)
    stub_envelope(monkeypatch, sabotage)
    assert a_runner(tmp_path).run(lambda report: ["true"])["report"] is None


def test_a_report_swapped_for_a_fifo_is_no_report_and_never_blocks(tmp_path, monkeypatch):
    stub_envelope(monkeypatch, lambda tree: os.mkfifo(runtime_tmp(tree) / "report"))
    out: dict = {}
    worker = threading.Thread(target=lambda: out.update(r=a_runner(tmp_path).run(lambda report: ["true"])),
                              daemon=True)
    worker.start()
    worker.join(20)
    assert not worker.is_alive() and out["r"]["report"] is None


def test_a_flood_of_sparse_files_does_not_set_the_parents_cost(tmp_path, monkeypatch):
    def sabotage(tree):                  # each file costs the sandbox an ftruncate and the old scan 8 MiB of hashing
        for i in range(600):
            with open(tree / f"flood-{i:04d}", "wb") as fh:
                fh.truncate(8 * 1024 * 1024)
        with open(tree / "pkg" / "calc.py", "r+b") as fh:
            fh.truncate(8 * 1024 * 1024)
    stub_envelope(monkeypatch, sabotage)
    started = time.monotonic()
    out = a_runner(tmp_path).run(lambda report: ["true"])
    assert out["tampered"] and time.monotonic() - started < 5, "the tamper scan read what the tree code planted"


def test_the_tree_walks_never_stat_through_a_link(tmp_path, monkeypatch):
    tree = make_tree(tmp_path / "t")
    outside = tmp_path / "outside"
    outside.mkdir()
    expected, sizes = repair._manifest(tree), {}
    (tree / "pkg" / "link").symlink_to(outside, target_is_directory=True)
    followed, real = [], os.scandir

    class Entry:
        def __init__(self, entry):
            self._e, self.name, self.path = entry, entry.name, entry.path

        def __fspath__(self):
            return self.path

        def is_symlink(self):
            return self._e.is_symlink()

        def inode(self):
            return self._e.inode()

        def _note(self, follow):
            if follow and self._e.is_symlink():
                followed.append(self.name)

        def is_dir(self, *, follow_symlinks=True):
            self._note(follow_symlinks)
            return self._e.is_dir(follow_symlinks=follow_symlinks)

        def is_file(self, *, follow_symlinks=True):
            self._note(follow_symlinks)
            return self._e.is_file(follow_symlinks=follow_symlinks)

        def stat(self, *, follow_symlinks=True):
            self._note(follow_symlinks)
            return self._e.stat(follow_symlinks=follow_symlinks)

    class Scan:
        def __init__(self, *args):
            self._it = real(*args)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            self._it.close()

        def __iter__(self):
            return self

        def __next__(self):
            return Entry(next(self._it))

        def close(self):
            self._it.close()
    monkeypatch.setattr(os, "scandir", Scan)
    seen = repair._manifest(tree)
    repair._changed(tree, expected, sizes)
    assert seen["pkg/link"] == "symlink:" + str(outside) and followed == [], followed


# -- second round: SEG-1, SEG-3 ------------------------------------------------------------------------------

def test_two_torn_tails_at_the_same_offset_keep_both_sidecars(tmp_path):
    path = tmp_path / "egress-journal.jsonl"
    journal = Journal(path)
    journal.append({"identity": "http.get", "host": "a.test", "port": 443, "verdict": "ALLOWED"})
    with open(path, "ab") as fh:
        fh.write(b'{"identity": "http.get", "ho')
    journal._repair_tail()               # the append after this repair is killed too, at the same offset
    with open(path, "ab") as fh:
        fh.write(b'{"identity": "browser.render", "host": "b')
    journal.append({"identity": "http.get", "host": "c.test", "port": 443, "verdict": "ALLOWED"})
    sidecars = sorted(p.read_bytes() for p in tmp_path.glob("egress-journal.jsonl.torn-*"))
    assert sidecars == [b'{"identity": "browser.render", "host": "b', b'{"identity": "http.get", "ho']
    assert journal.verify()["intact"] and journal.verify()["quarantined_tails"] == 1


def test_a_committed_row_that_does_not_parse_is_a_broken_chain_on_every_surface(tmp_path):
    from greg.body import status
    home, _, _ = body_with_confined_egress(tmp_path)
    path = home / "egress-journal.jsonl"
    journal = Journal(path)
    journal.append({"identity": "http.get", "host": "service.test", "port": 443, "verdict": "ALLOWED"})
    journal.append({"identity": "browser.render", "host": "b.test", "port": 443, "verdict": "DENIED",
                    "why": "host and port are not on this identity's allowlist"})
    first, second = path.read_text().splitlines()
    path.write_text("\n".join(["X" + first[1:], second]) + "\n")       # one byte of damage on a structural char
    assert journal.verify() == {"intact": False, "broken_at": 0, "malformed": True}
    assert status(home)["egress"]["chain_intact"] is False                # before: JSONDecodeError
    result = report(home)
    assert result["egress"]["chain_intact"] is False and result["egress"]["broken_at"] == 0
    assert status_of(result)["network_confined"] == "NOT_YET"
    with pytest.raises(ValueError):
        journal.append({"identity": "http.get", "host": "x.test", "port": 443, "verdict": "ALLOWED"})
