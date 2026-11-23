"""`greg path` answers directive section 15 on the command line: where GREG stands and what clears the active node.

Section 15 asks, for the active node, for CURRENT POSITION, ACTIVE GATE, ACTIVE SINGLE BOTTLENECK METRIC, OBJECTIVE EXIT
EVIDENCE and SMALLEST REAL NEXT BUILD. The command reports each from greg/path.json and the body's ledger, with a body
and without one.
"""
from __future__ import annotations

import json

from greg import cli
from greg import path as devpath
from tests.greg_fixtures import make_body

FIELDS = ("gate", "sbm", "exit_evidence", "smallest_next_build")


def _path(home, capsys) -> dict:
    assert cli.main(["--home", str(home), "path"]) == 0
    return json.loads(capsys.readouterr().out)


def test_greg_path_reports_position_gate_metric_exit_evidence_and_next_build(tmp_path, capsys):
    home, *_ = make_body(tmp_path)
    where = _path(home, capsys)
    nodes = {n["id"]: n for n in devpath.load()["nodes"]}
    active = where["active"]
    assert where["achieved"] == ["N0"] and active["id"] == "N1" and where["next"]["id"] == "N2"     # position
    for field in FIELDS:
        assert active[field] and active[field] == nodes["N1"][field], field
    assert active["measurement"] == {**active["measurement"], "source": "ledger", "met": False}
    assert where["next"]["gate"] == nodes["N2"]["gate"]


def test_greg_path_without_a_body_still_names_the_gate_and_says_it_cannot_measure(tmp_path, capsys):
    where = _path(tmp_path / "no-body", capsys)
    active = where["active"]
    assert active["id"] == "N1" and all(active[field] for field in FIELDS)
    assert "not_yet_measurable" in active["measurement"]          # never counted as passed without a ledger
