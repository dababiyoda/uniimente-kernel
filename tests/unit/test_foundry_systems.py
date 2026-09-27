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


# -- increment 2 -------------------------------------------------------------------------

from foundry.systems import distributed, dsl, emulator, mechanism, next_test, queue, seed, snapshots


def test_emulator_is_deterministic_and_exposes_the_naive_double_charge():
    result = emulator.exercise(None)
    assert result["deterministic"] and result["naive_client_double_charged"] and result["unknown_fault_refused"]
    lazy = emulator.ProviderEmulator(["duplicate_delivery"], honours_idempotency=False)
    lazy.charge("k", 1)
    assert lazy.truth()["charges"] == 2, "a provider that ignores idempotency is reproduced faithfully"


def test_distributed_controls_charge_exactly_once_resume_and_compensate(tmp_path):
    result = distributed.exercise(tmp_path)
    assert result["exactly_once"] and result["resumed_without_duplicate"] and result["compensated"]
    assert result["retry_schedule"] == [0.5, 2.0], "exponential backoff raised to the provider's retry-after"
    provider = emulator.ProviderEmulator(["timeout"] * 5)
    out = distributed.run_saga("s", [{"name": "only", "amount": 5}], provider, distributed.Journal(tmp_path / "j.jsonl"))
    assert out["status"] == "compensated" and provider.truth()["charges"] == 0, "unknown and absent: nothing assumed"
    with pytest.raises(emulator.ProviderError):
        distributed.with_retries(lambda: (_ for _ in ()).throw(emulator.ProviderError(400)))


def test_queue_redelivers_dead_letters_and_survives_restart(tmp_path):
    result = queue.exercise(tmp_path)
    assert all(result.values()), result
    q = queue.Queue(tmp_path / "q2", "t", visibility=5)
    q.publish({"n": 1}, message_id="a")
    assert q.receive(now=0)["id"] == "a" and q.receive(now=1) is None, "a leased message is invisible"


def test_snapshots_fork_without_touching_production(tmp_path):
    result = snapshots.exercise(tmp_path)
    assert result["production_untouched"] and result["overwrite_refused"] and result["snapshot_reproducible"]
    assert result["diff"] == {"only_a": [], "only_b": ["experiment.txt"], "changed": ["policy/pricing.json"]}


def test_seed_restores_a_real_greg_body_that_verifies_and_reboots(tmp_path):
    from provenance.ledger import EvidenceLedger
    home, key, body_id, _ = make_body(tmp_path)
    with Body(home) as body:
        body.boot()
        head = body.ledger.head
        constitution = body.compiled.constitution_hash
    made = seed.make_seed(home, tmp_path / "seed-store")
    assert any(e.endswith("_ed25519.pem") for e in made["excluded"]), "private keys are never packed"
    target = tmp_path / "new-mac" / "body"
    restored = seed.restore(tmp_path / "seed-store", made["seed"], target)
    ledger = EvidenceLedger(constitution, str(Layout(target).ledger), read_only=True)
    try:
        ok, why = ledger.verify_chain()
        assert ok, why
        assert ledger.head == head, "the restored institution holds exactly the pre-failure history"
    finally:
        ledger.close()
    assert restored["needs_from_founder"], "recovery names what only the founder can supply"
    with pytest.raises(FileExistsError):
        seed.restore(tmp_path / "seed-store", made["seed"], target)


def test_seed_cli_refuses_a_store_inside_the_body(tmp_path):
    from greg import cli
    home, *_ = make_body(tmp_path)
    assert cli.main(["--home", str(home), "foundry", "seed", "--out", str(Path(home) / "seed")]) != 0
    assert cli.main(["--home", str(home), "foundry", "seed", "--out", str(tmp_path / "offsite")]) == 0


def test_next_best_test_ignores_near_certain_beliefs_and_prefers_information_per_cost():
    assert next_test.value_of_information(99, 1, 0.9) < 0.01
    result = next_test.exercise(None)
    assert result["near_certain_belief_worth_little"] and result["one_lucky_transition_not_first"]


def test_mechanisms_make_truth_the_best_response():
    result = mechanism.exercise(None)
    assert result["brier_truthful"] and result["vickrey_max_deviation_gain"] <= 0
    assert result["procurement"] == {"winner": "b", "paid": 120}


def test_dsl_runs_narrow_rules_and_rejects_code():
    result = dsl.exercise(None)
    assert result["price"] == 392.0 and result["budget"] == 800 and all(result["refused"].values())
    for src in ("2 ** 10 ** 10", "[x for x in range(9)]", "units[0]", "open('/etc/passwd')"):
        with pytest.raises(dsl.RuleError):
            dsl.parse("pricing", src)


# -- increment 3: the Kernel's own authority, events and proof under the contract -------

from foundry.systems import capsec, event_sourcing, gate, pki, proofs, scenarios, treasury, workflows


def test_event_sourcing_replays_after_restart_and_refuses_tampering(tmp_path):
    result = event_sourcing.exercise(tmp_path)
    assert result["replayed_history"][0] == "signal.observed" and result["replayed_history"][-1] == "outcome.measured"
    assert all(v for k, v in result.items() if k != "replayed_history")


def test_proofs_bind_membership_to_a_trusted_root_only(tmp_path):
    result = proofs.exercise(tmp_path)
    assert result["all_members_prove"] and result["tampered_sibling_fails"] and result["non_member_refused"]
    assert result["forged_proof_self_consistent"], "negative evidence: a forger's proof is internally consistent"
    assert result["forged_rejected_by_trusted_root"] and result["signed_root_substitution_detected"]


def test_pki_limits_devices_to_delegated_kinds_and_lifetimes(tmp_path):
    result = pki.exercise(tmp_path)
    assert result["founder_mission"] == result["device_decision"] == "accepted"
    for case in ("replayed_nonce", "other_body", "tampered_body", "device_mission", "device_after_expiry",
                 "device_after_revocation"):
        assert result[case].startswith("refused"), (case, result[case])
    assert result["long_lived_delegation_refused"]


def test_capability_grants_reach_nothing_but_their_own_proposal():
    result = capsec.exercise(None)
    assert result["first_use"] == "recorded"
    for case in ("other_target", "overspend", "replay", "revoked"):
        assert result[case] == "refused", case
    assert not (result["other_target_executed"] or result["replay_executed"] or result["revoked_executed"])


def test_consequence_gate_pipeline_witnesses_and_fails_closed():
    result = gate.exercise(None)
    assert result["pipeline"] == ["proposed", "evaluating", "granted", "executing", "committed", "recorded"]
    assert result["witnessed"] and result["chain_ok"] and result["explosion_evidence_kept"]
    assert result["explosion"] == "reconciliation_required", "an exploding executor never reads as success"
    assert result["weak_evidence"] == result["no_identity"] == "refused"


def test_workflows_resume_without_repeats_and_compensate_in_reverse(tmp_path):
    result = workflows.exercise(tmp_path)
    assert result["killed_mid_flight"] and result["resumed_status"] == "completed" and result["no_step_repeated"]
    assert result["approval_blocks_without_approver"] and result["failure_compensated"]
    assert result["compensation_order"] == ["draft", "research"]


def test_composed_workflow_runs_foundry_systems_through_greg_and_resumes(tmp_path):
    steps = [{"name": "store", "system": 36, "op": "put", "args": {"text": "evidence"}, "write": True},
             {"name": "verify", "system": 36, "op": "verify"},
             {"name": "boundary", "system": 43, "op": "check_approval_boundary"}]
    out = foundry_bridge.apply({"system": 15, "op": "run", "args": {"workflow_id": "wf-a", "steps": steps}},
                               _ctx(tmp_path, "foundry.apply"))
    outputs = out["result"]["outputs"]
    assert out["result"]["status"] == "completed" and outputs["verify"]["intact"] and outputs["boundary"]["holds"]
    with pytest.raises(CapabilityError, match="refused run"):
        foundry_bridge.apply({"system": 15, "op": "run", "args": {"workflow_id": "wf-b", "steps": [
            {"name": "sneak", "system": 36, "op": "put", "args": {"text": "x"}}]}}, _ctx(tmp_path, "foundry.apply"))


def test_scenario_tribunal_is_deterministic_and_writes_playbooks():
    result = scenarios.exercise(None)
    assert result["deterministic"] and result["dominance"] == [["owned_proof_rail", "rented_audience"]]
    assert result["platform_loss"]["rented_audience"]["survival"] < result["platform_loss"]["owned_proof_rail"]["survival"]
    assert "owned channels" in result["playbook_platform_loss"]["mitigations"][0]
    assert len(result["scenarios_covered"]) == 6


def test_treasury_reconciles_to_the_books_and_debt_blocks_expansion(tmp_path):
    result = treasury.exercise(tmp_path)
    assert result["reconciled_to_the_cent"] and result["books_balance"] and result["unallocated_cents"] == 0
    assert result["budget_expansion_blocked_by_debt"] and result["evidenceless_repayment_refused"]
    assert result["unblocked_after_evidenced_repair"] and result["unknown_tier_refused"]
    assert result["last_tier_starved_first"], "obligations are funded before the last tier"
