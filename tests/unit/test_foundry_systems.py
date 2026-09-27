"""Foundry systems: behavior, GREG integration and the 55-system completion contract.

Each system is tested beyond its exercise (edge cases and refusals), then reached
through GREG's Authority Office, then the contract auditor is attacked: a claim
that does not reproduce, a missing id or a COMPLETE row without tests must fail.
"""
import json
from pathlib import Path

import pytest

from foundry import completion
from foundry.systems import accounting, cas, graph, model_check, reputation, search, versions
from greg.body import Body, Layout
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, SecretBroker
from greg import foundry_bridge
from tests.greg_fixtures import Clock, drop, make_body, mission, signed


# -- #36 content-addressed storage -------------------------------------------------------

def test_cas_dedups_refuses_substitution_and_rejects_bad_addresses(tmp_path):
    a = cas.put(tmp_path, b"x")
    assert cas.put(tmp_path, b"x") == a and cas.get(tmp_path, a) == b"x"
    other = cas.put(tmp_path, b"y")
    cas._path(tmp_path, a).write_bytes(b"y")          # substitute a different (valid) object's bytes
    with pytest.raises(cas.IntegrityError):
        cas.get(tmp_path, a)
    assert cas.verify_all(tmp_path)["corrupt"] == [a] and cas.get(tmp_path, other) == b"y"
    for bad in ("sha256:xyz", "md5:" + "0" * 64, "sha256:" + "G" * 64):
        with pytest.raises(ValueError):
            cas.get(tmp_path, bad)


# -- #3 versioned institutional objects --------------------------------------------------

def test_versions_keep_lineage_and_never_rewrite(tmp_path):
    v1 = versions.commit(tmp_path, "charter", {"scope": "brief"}, reason="first", evidence=["intent:1"])
    versions.commit(tmp_path, "charter", {"scope": "brief+venture"}, reason="widen")
    with pytest.raises(versions.VersionError):
        versions.commit(tmp_path, "charter", {"scope": "x"}, reason="stale", expected_parent=v1["address"])
    with pytest.raises(versions.VersionError):
        versions.commit(tmp_path, "../escape", {"a": 1}, reason="path")
    versions.rollback(tmp_path, "charter", 1, reason="widening failed")
    history = versions.history(tmp_path, "charter")
    assert [v["n"] for v in history] == [3, 2, 1] and history[0]["reason"].startswith("rollback to v1")
    assert versions.content(tmp_path, "charter") == {"scope": "brief"}
    # a tampered version record breaks retrieval (it is a CAS object)
    cas._path(tmp_path, history[1]["address"]).write_text("{}")
    with pytest.raises(cas.IntegrityError):
        versions.history(tmp_path, "charter")


# -- #39 double-entry accounting ---------------------------------------------------------

def test_accounting_balances_reverses_and_detects_tampering(tmp_path):
    result = accounting.exercise(tmp_path)
    assert result["equation_holds"] and all(result["refusals"].values())
    assert result["totals"]["revenue"] == 90000 and result["totals"]["asset"] == 187500
    assert result["double_reversal_refused"] and result["tamper_detected"]


def test_accounting_refuses_a_one_line_entry_and_a_currency_switch(tmp_path):
    accounting.open_account(tmp_path, "cash", "asset", "USD")
    with pytest.raises(accounting.AccountingError):
        accounting.open_account(tmp_path, "eur_cash", "asset", "EUR")
    with pytest.raises(accounting.AccountingError):
        accounting.post(tmp_path, date="d", memo="m", currency="USD", lines=[{"account": "cash", "debit": 1}])


# -- #43 formal methods ------------------------------------------------------------------

def test_model_checker_verifies_the_boundary_and_returns_the_shortest_counterexample():
    assert model_check.check(model_check.APPROVAL_BOUNDARY)["holds"] is True
    bad = model_check.check(model_check.buggy_approval_boundary())
    assert bad["holds"] is False and bad["trace"] == ["raise_request", "execute_on_pending"]
    assert bad["violated"] == "never_executed_without_approval"
    with pytest.raises(model_check.ModelError):
        model_check.check({"variables": {"x": [0]}, "initial": {"x": 0}, "transitions": [{"name": "t", "set": {"y": 1}}]})
    bounded = model_check.check({"variables": {"n": list(range(50))}, "initial": {"n": 0},
                                 "transitions": [{"name": f"to{i}", "set": {"n": i}} for i in range(50)]}, max_states=10)
    assert bounded["holds"] is None, "hitting the state bound is reported, never read as a proof"


# -- #18 knowledge graph -----------------------------------------------------------------

def test_graph_refuses_non_causal_edges_and_explains_capital(tmp_path):
    result = graph.exercise(tmp_path)
    assert result["why_capital_reaches_signal"] and result["bad_edge_refused"]
    assert result["shared_capabilities"][0]["node"] == "cap:proof-verifier"
    g = graph.Graph()
    with pytest.raises(graph.GraphError):
        g.add("x", "Rumor")
    g.add("a", "Action")
    with pytest.raises(graph.GraphError):
        g.link("a", "produced", "missing")


# -- #41 reputation ----------------------------------------------------------------------

def test_reputation_ignores_unevidenced_claims_and_ranks_by_lower_bound(tmp_path):
    result = reputation.exercise(tmp_path)
    assert result["steady_beats_lucky"] and result["recovery_beats_unrecovered"]
    assert result["stale_is_insufficient"] and result["sybil_ignored"]


# -- #17 causal search -------------------------------------------------------------------

def test_search_returns_worked_and_failed_precedents_side_by_side(tmp_path):
    result = search.exercise(tmp_path)
    assert (result["closest_worked"], result["closest_failed"]) == ("freight-pilot-worked", "freight-pilot-failed")
    assert result["unmeasured"] == ["freight-unmeasured"] and result["clinic_case_excluded"]
    assert search.search([{"id": "a", "text": "unrelated"}], "freight") == []


# -- GREG integration --------------------------------------------------------------------

def _ctx(tmp_path, capability):
    return InvocationContext(workspace=tmp_path / "ws", read_roots=(tmp_path,), secrets=SecretBroker(tmp_path / "v.json"),
                             manifest=BUILTINS[capability][0], deliver_root=None)


def test_bridge_keeps_read_and_write_apart_and_scopes_stores_to_the_workspace(tmp_path):
    put = foundry_bridge.apply({"system": 36, "op": "put", "args": {"text": "hello"}}, _ctx(tmp_path, "foundry.apply"))
    address = put["result"]["address"]
    assert (tmp_path / "ws" / "foundry" / "system-36" / "objects").is_dir()
    got = foundry_bridge.query({"system": 36, "op": "get", "args": {"address": address}}, _ctx(tmp_path, "foundry.query"))
    assert got["result"]["text"] == "hello"
    with pytest.raises(CapabilityError, match="has no query op 'put'"):
        foundry_bridge.query({"system": 36, "op": "put", "args": {"text": "x"}}, _ctx(tmp_path, "foundry.query"))
    with pytest.raises(CapabilityError, match="not implemented yet"):
        foundry_bridge.query({"system": 10, "op": "run"}, _ctx(tmp_path, "foundry.query"))
    with pytest.raises(CapabilityError, match="refused post"):
        foundry_bridge.apply({"system": 39, "op": "post", "args": {"date": "d", "memo": "m", "currency": "USD",
                                                                    "lines": []}}, _ctx(tmp_path, "foundry.apply"))
    assert BUILTINS["foundry.query"][0].consequence_class == "read_only"
    assert BUILTINS["foundry.apply"][0].consequence_class == "internal_write"


def test_signed_mission_uses_foundry_through_the_authority_office_and_is_appraised(tmp_path):
    home, key, body_id, _ = make_body(tmp_path)
    check = {"check_id": "stored", "description": "the evidence note is content-addressed and intact",
             "sensor": {"capability": "foundry.query", "params": {"system": 36, "op": "verify"}, "target": "foundry:cas"},
             "predicate": {"op": "gte", "field": "result.objects", "value": 1}}
    strategy = {"action_id": "store-note", "capability": "foundry.apply", "target": "foundry:cas",
                "params": {"system": 36, "op": "put", "args": {"text": "buyer interview 1: pays on proof"}},
                "advances": ["stored"], "rationale": "store the evidence note by content"}
    spec = mission("m:foundry-cas", checks=[check], strategies=[strategy],
                   capabilities=["foundry.query"], targets=("foundry:*",), ceiling="read_only")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        clock.advance(30)
        assert body.tick()["missions"][0]["state"] == "WAITING", "a write outside the read-only cone asks first"
        body.engine.book.rebuild()
        request = body.engine.book.open_requests()[0]
        assert request["authority_requested"]["capability"] == "foundry.apply"
    drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"], "answer": "approve"}))
    with Body(home, clock=clock) as body:
        states = []
        for _ in range(3):
            clock.advance(30)
            states.append(body.tick()["missions"][0]["state"])
        assert states[:2] == ["ACTED", "ACHIEVED"]
        verdict = body.journal.replay("mission.appraised")[-1].payload
        assert verdict["verdict"] == "VERIFIED", verdict["findings"]
        events = [{"type": e.type, "event_id": e.event_id, "payload": e.payload, "at": e.occurred_at}
                  for e in body.journal.replay("")]
    g = graph.from_greg(events)
    action = next(n for n, v in g.nodes.items() if v["kind"] == "Action")
    kinds = {row["kind"] for row in g.why(action)}
    assert {"Decision", "Authority"} <= kinds, "GREG can say why it acted: the mission and the founder approval"
    assert any(row["kind"] == "Outcome" for row in g.impact(action))
    rep = reputation.score(reputation.from_greg(events), now="2100-01-01T00:00:00Z", half_life_days=1e9)
    assert rep["subjects"][0]["subject"] == "foundry.apply" and rep["subjects"][0]["status"] == "insufficient"


def test_greg_foundry_cli_reports_status_and_runs_a_system(tmp_path, capsys):
    from greg import cli
    home, key, body_id, _ = make_body(tmp_path)
    assert cli.main(["--home", str(home), "foundry", "status"]) == 0
    status = json.loads(capsys.readouterr().out)
    assert status["complete"].endswith("/55") and len(status["open_obligations"]) + int(status["complete"].split("/")[0]) == 55
    assert cli.main(["--home", str(home), "foundry", "run", "43"]) == 0
    assert json.loads(capsys.readouterr().out)["result"]["bug_caught"] is True
    assert cli.main(["--home", str(home), "foundry", "reputation"]) == 0


# -- the completion contract -------------------------------------------------------------

def test_contract_is_audited_and_every_claim_reproduces():
    assert completion.audit() == []
    rows = completion.contract()
    assert set(rows) == set(range(1, 56))
    assert all(rows[i]["acceptance"] for i in rows)


def test_contract_rejects_missing_ids_unreproducible_evidence_and_untested_claims(tmp_path, monkeypatch):
    rows = completion.contract()
    del rows[10]
    assert any("missing [10]" in p for p in completion.audit(rows, rerun=False))

    rows = completion.contract()
    rows[43] = dict(rows[43], tests=[])
    assert any("system 43: COMPLETE requires tests" in p for p in completion.audit(rows, rerun=False))

    rows = completion.contract()
    rows[10] = dict(rows[10], state="COMPLETE")
    assert any("system 10" in p for p in completion.audit(rows, rerun=False)), "a claim with nothing behind it fails"

    forged = json.loads((completion.ROOT / "foundry/evidence/system-39.json").read_text())
    forged["result"]["equation_holds"] = False
    fake = tmp_path / "system-39.json"
    fake.write_text(json.dumps(forged))
    rows = completion.contract()
    rows[39] = dict(rows[39], evidence=str(fake))
    assert any("does not reproduce" in p for p in completion.audit({39: rows[39], **{i: r for i, r in completion.contract().items() if i != 39}}))
