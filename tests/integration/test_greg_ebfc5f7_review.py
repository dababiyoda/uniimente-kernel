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
"""
from __future__ import annotations

import json
import os
import re
import socket
import threading
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
                                  [{"lines": [1], "equals_expected": "yes"}] * 3])
def test_a_malformed_diagnosis_report_is_a_refusal_not_a_crash(tmp_path, monkeypatch, rows):
    # The tracer runs in the same interpreter as the code under repair, which can rewrite its report.
    def traced(self, argv_for, target_source=None):
        return {"status": "exited", "code": 0, "tail": "", "report": json.dumps(rows).encode(), "tampered": []}
    monkeypatch.setattr(repair._Runner, "run", traced)
    with pytest.raises(repair.RepairError, match="diagnosis could not run the target"):
        run_repair(tmp_path, make_tree(tmp_path / "t"))


# -- M1 ------------------------------------------------------------------------------------------------------

def test_the_foundry_52_evidence_does_not_count_the_frozen_import_closure():
    recorded = json.loads((completion.ROOT / "foundry/evidence/system-52.json").read_text())
    assert "frozen_files" not in recorded["result"]["source_repair"], \
        "the closure size moves with any unrelated import, so the evidence stops reproducing"


def test_no_evidence_record_claims_a_ci_re_run_its_row_does_not_get():
    rows = completion.contract()
    for path in sorted((completion.ROOT / "foundry" / "evidence").glob("system-*.json")):
        record = json.loads(path.read_text())
        state = rows.get(record["system"], {}).get("state")
        if state != "COMPLETE":
            assert record["note"] != completion.AUDITED_NOTE, (path.name, state)
            assert record["note"] == completion.evidence_note(record["system"], state), path.name


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
    assert check["intact"] and check["entries"] == 2 and "torn_tail_bytes" not in check
    assert [p.name for p in home.glob("egress-journal.jsonl.torn-*")], "the torn bytes are kept beside the journal"
    assert status_of(report(home))["undeclared_destination_denied"] == "PASS"


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
