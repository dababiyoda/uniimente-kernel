"""P4 in shadow: the competence ledger's would-be cortex routes, replayed without hindsight.

Nothing here changes a live route. The tests show that the shadow (1) needs five weighted outcomes
in every compared cell before it proposes anything, (2) learns only from outcomes settled before the
receipt it judges, (3) can learn about the second engine only from founder-pinned missions, and
(4) writes nothing.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("z3")
pytest.importorskip("ortools")

from greg.cognition import shadow  # noqa: E402
from greg.cognition.cortex import reason, registry_view  # noqa: E402
from tests.integration.test_greg_cortex_mission import cortex_mission, cortex_params  # noqa: E402
from tests.greg_fixtures import drop, make_body, signed  # noqa: E402
from greg.body import Body  # noqa: E402


@pytest.fixture(scope="module")
def receipts():
    registry = registry_view()
    default = reason(cortex_params(), registry=registry)
    pinned = reason(cortex_params(), registry=registry, forced_family="cognition.cortex.formal.z3")
    assert default["method"] == "cognition.cortex.optimization.cpsat"
    assert pinned["method"] == "cognition.cortex.formal.z3"
    return default, pinned


def ledger_of(*rows):
    records = [SimpleNamespace(hash=f"h{i}", record_type="receipt", payload={"result": {"output": r}})
               for i, r in enumerate(rows)]
    return SimpleNamespace(records=records)


def run(monkeypatch, rows, correct):
    ledger = ledger_of(*rows)
    monkeypatch.setattr(shadow, "measured_outcomes",
                        lambda journal: [{"receipt": f"h{i}", "correct": c} for i, c in correct.items()])
    return shadow.shadow(None, ledger)


def test_one_default_receipt_is_a_decision_point_with_no_evidence_and_no_proposal(monkeypatch, receipts):
    default, _ = receipts
    report = run(monkeypatch, [default], {0: True})
    [d] = report["decisions"]
    assert d["point"] == "formal_engine_order"
    assert d["live"] == ["cortex.optimization.cpsat@0.2.0", "cortex.formal.z3@0.2.0"]
    assert d["shadow"] == d["live"] and not d["differs"] and not d["ready"]
    assert d["live_outcome"] is True and d["estimates"][0]["basis"] == "prior"
    assert report["summary"]["cells"] == [] and report["authority_created"] is False


def test_ordinary_missions_never_explore_the_second_engine_so_the_shadow_never_moves(monkeypatch, receipts):
    default, _ = receipts
    rows = [default] * 12
    report = run(monkeypatch, rows, {i: False for i in range(11)})      # the default keeps failing
    last = report["decisions"][-1]
    assert not last["differs"] and not last["ready"], "Z3 has no cell: failing CP-SAT alone cannot move the order"
    [cell] = report["summary"]["cells"]
    assert cell["method"] == "cortex.optimization.cpsat" and cell["enough_to_reorder"]


def test_founder_pinned_outcomes_let_the_shadow_propose_a_reorder_after_enough_evidence(monkeypatch, receipts):
    default, pinned = receipts
    rows = [pinned] * 9 + [default] * 9 + [default]
    correct = {**{i: True for i in range(9)}, **{i: False for i in range(9, 18)}}
    report = run(monkeypatch, rows, correct)
    judged = [d for d in report["decisions"]]
    assert all(d["point"] == "formal_engine_order" for d in judged), "pinned receipts have one engine: no point"
    assert len(judged) == 10
    assert [d["differs"] for d in judged[:-2]] == [False] * 8, "not ready until both cells hold five outcomes"
    final = judged[-1]
    assert final["ready"] and final["differs"]
    assert final["shadow"] == ["cortex.formal.z3@0.2.0", "cortex.optimization.cpsat@0.2.0"]
    z3, cpsat = sorted(final["estimates"], key=lambda e: e["method"])
    assert z3["estimate"] > cpsat["estimate"] + 0.10
    assert report["summary"]["shadow_differs"] >= 1 and report["promotion"].startswith("founder decision")


def test_the_shadow_judges_each_receipt_only_from_earlier_outcomes(monkeypatch, receipts):
    default, pinned = receipts
    rows = [default] + [pinned] * 9 + [default] * 9
    correct = {**{i: True for i in range(1, 10)}, **{i: False for i in range(10, 19)}, 0: False}
    report = run(monkeypatch, rows, correct)
    first = report["decisions"][0]
    assert first["receipt"] == "h0" and not first["differs"] and first["ledger_head"].endswith("0" * 64)


def test_an_invalid_or_non_cortex_receipt_is_ignored(monkeypatch, receipts):
    default, _ = receipts
    forged = {**default, "output": {"answer": "forged"}}                 # content address no longer matches
    report = run(monkeypatch, [forged, {"not": "a receipt"}], {0: True, 1: True})
    assert report["decisions"] == []


def test_on_a_real_body_the_shadow_reads_the_settled_mission_and_writes_nothing(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", cortex_mission()))
    with Body(home) as body:
        body.boot()
        assert body.tick()["missions"][0]["state"] == "ACHIEVED"
        before = len(body.ledger.records)
        report = shadow.shadow(body.journal, body.ledger)
        assert len(body.ledger.records) == before, "the shadow is a projection: no write"
        [d] = report["decisions"]
        assert d["live_outcome"] is True and not d["differs"] and not d["ready"]
        assert report["summary"]["live_scored"] == report["summary"]["live_correct"] == 1


def test_the_founder_reads_the_shadow_from_the_cli(tmp_path, capsys):
    import json
    from greg import cli
    home, key, body_id, _ = make_body(tmp_path)
    drop(home, signed(key, body_id, "MISSION", cortex_mission()))
    with Body(home) as body:
        body.boot()
        body.tick()
    try:
        cli.main(["--home", str(home), "cognition", "shadow"])
    except SystemExit as exit_:
        assert not exit_.code
    data = json.loads(capsys.readouterr().out)
    assert data["summary"]["decision_points"] == 1 and data["authority_created"] is False
