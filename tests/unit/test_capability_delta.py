"""Directive ask S70.A1: "what can real GREG now do that it could not do before" is computed between two commits.

``python -m acceptance delta --since <ref>`` compares the directive map at the ref with this tree. An ask counts
as a gained capability only when it is met here, was not met there, and the evidence that proves it is new or
changed. Asks that are now met but whose evidence did not change are reported separately and never counted.
Regressions are listed and never netted against gains. Here the base is the head map with one ask's evidence
removed, so each case is decided by one controlled difference.
"""
from __future__ import annotations

import copy

import pytest

from acceptance import directive
from acceptance.__main__ import main

MET = "S1.A1"          # met at head with UNIT_VERIFIED test nodes
OPEN = "S37.A2"        # open at head, though its cited tests reach UNIT_VERIFIED


def _ask(doc: dict, aid: str) -> dict:
    return next(a for s in doc["sections"] for a in s["asks"] if a["id"] == aid)


def _without_evidence(triple, aid):
    doc = copy.deepcopy(triple[0])
    _ask(doc, aid)["evidence"] = []
    return (doc, *triple[1:])


def _files(triple, aid) -> set[str]:
    return {n.split("::")[0] for n in directive.evidence_nodes(_ask(triple[0], aid), *triple[1:])}


@pytest.fixture(scope="module")
def head():
    return directive.defaults()


@pytest.fixture(scope="module")
def read_head():
    return directive.read_tree()


def _absent(read, files):
    """A base reader in which ``files`` did not exist yet."""
    return lambda path: None if path in files else read(path)


def _ids(delta, key):
    return [r["id"] for r in delta[key]]


def test_no_change_is_no_delta(head, read_head):
    delta = directive.capability_delta(head, head, read_head, read_head)
    assert delta["gained"] == delta["rose"] == delta["lost"] == delta["unproven"] == []
    assert delta["measured"] == {"base": False, "head": False}


def test_a_newly_met_ask_with_new_evidence_is_gained(head, read_head):
    base = _without_evidence(head, MET)
    delta = directive.capability_delta(base, head, _absent(read_head, _files(head, MET)), read_head)
    assert _ids(delta, "gained") == [MET]
    row = delta["gained"][0]
    assert row["before"] == {"met": False, "tier": "INTENDED"} and row["after"]["met"]
    assert row["changed_evidence"] and set(row["changed_evidence"]) <= set(row["evidence"])
    assert _ids(delta, "unproven") == [] and _ids(delta, "lost") == []


def test_a_newly_met_ask_whose_evidence_did_not_change_is_not_counted(head, read_head):
    base = _without_evidence(head, MET)
    delta = directive.capability_delta(base, head, read_head, read_head)
    assert _ids(delta, "gained") == []
    assert _ids(delta, "unproven") == [MET]
    assert delta["unproven"][0]["changed_evidence"] == []


def test_a_lost_ask_is_listed_and_not_netted(head, read_head):
    gone = _without_evidence(head, MET)
    delta = directive.capability_delta(head, gone, read_head, read_head)
    assert _ids(delta, "lost") == [MET] and _ids(delta, "gained") == []
    assert delta["lost"][0]["after"] == {"met": False, "tier": "INTENDED"}


def test_an_open_ask_that_came_closer_is_not_a_capability(head, read_head):
    base = _without_evidence(head, OPEN)
    delta = directive.capability_delta(base, head, _absent(read_head, _files(head, OPEN)), read_head)
    assert _ids(delta, "rose") == [OPEN]
    assert _ids(delta, "gained") == []
    assert not delta["rose"][0]["after"]["met"]


def test_a_recorded_run_replaces_the_ceiling(head, read_head):
    doc, manifest, _ = head
    passed = {n: {"outcome": "passed", "reason": ""}
              for n in directive.cited_nodes(doc) + directive._manifest_nodes(manifest)}
    failing = {**passed, **{n: {"outcome": "failed", "reason": "assert"}
                            for n in directive.ask_nodes(_ask(doc, MET))}}
    delta = directive.capability_delta(head, head, read_head, read_head, head_outcomes=failing)
    assert delta["measured"] == {"base": False, "head": True}
    assert MET in _ids(delta, "lost")
    assert _ids(delta, "gained") == []


@pytest.mark.skipif(not (directive.ROOT / ".git").exists(), reason="needs the repository's git history")
def test_the_command_compares_with_a_git_ref(capsys, tmp_path):
    assert main(["delta", "--since", "no-such-ref-xyz"]) == 2
    assert "cannot read git ref" in capsys.readouterr().out
    out = tmp_path / "delta.json"
    assert main(["delta", "--since", "HEAD", "--out", str(out)]) == 0
    printed = capsys.readouterr().out
    assert "What GREG can do now that it could not do at HEAD" in printed
    assert out.read_text().startswith("{")
