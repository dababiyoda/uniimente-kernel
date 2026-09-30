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


# -- increment 4: composition, command surface, discovery, observability, security, twin, promotion

from foundry.systems import discovery, linking, observability, promotion, registry, shell, siem, twin


def _journal(body):
    return [{"type": e.type, "event_id": e.event_id, "payload": e.payload, "at": e.payload.get("at") or e.occurred_at}
            for e in body.journal.replay("")]


def test_registry_lifecycle_refuses_unsafe_moves_and_is_reachable_from_greg(tmp_path):
    result = registry.exercise(tmp_path / "ex")
    assert all(isinstance(v, str) for v in result["refusals"].values()), result["refusals"]
    assert "GenomeError" in result["refusals"]["invalid_genome"], "the Kernel's genome validator is the one owner"
    assert result["migrated"] == {"name": "buyer-scoring", "active": "2.0", "rollback_to": "1.0"}
    assert result["detached_keeps_versions"] == ["1.0", "2.0"]
    spec = registry.spec("notes", "1.0", ["text"])
    foundry_bridge.apply({"system": 12, "op": "install", "args": {"spec": spec, "code": "x", "tests_pass": True}},
                         _ctx(tmp_path, "foundry.apply"))
    report = foundry_bridge.query({"system": 12, "op": "report", "args": {"now": "2026-09-27T00:00:00Z"}},
                                  _ctx(tmp_path, "foundry.query"))
    assert report["result"]["genomes"]["notes"]["state"] == "INSTALLED"
    with pytest.raises(CapabilityError, match="has no query op 'install'"):
        foundry_bridge.query({"system": 12, "op": "install", "args": {}}, _ctx(tmp_path, "foundry.query"))


def test_linker_types_compositions_caps_authority_and_runs_through_greg(tmp_path):
    result = linking.exercise(tmp_path)
    assert result["price"] > 300 and 0 < result["trust"] < 1
    assert result["plan_authority"] == "read_only" and result["write_plan_authority"] == "internal_write"
    assert "needs trust:list, earlier stage provides trust:float" in result["refusals"]["type_mismatch"]
    assert all(result["refusals"].values())
    out = foundry_bridge.query({"system": 13, "op": "run_read_only", "args": {"stages": linking.demo_stages()}},
                               _ctx(tmp_path, "foundry.query"))
    assert [t["stage"] for t in out["result"]["trace"]] == ["rate", "price"]
    with pytest.raises(CapabilityError, match="exceeds granted ceiling read_only"):
        foundry_bridge.query({"system": 13, "op": "run_read_only", "args": {"stages": linking.demo_stages(post=True)}},
                             _ctx(tmp_path, "foundry.query"))
    lying = linking.demo_stages()
    lying[0]["provides"]["trust"]["type"] = "str"
    lying[1]["needs"]["trust"] = "str"
    with pytest.raises(linking.LinkError, match="contract says str"):
        linking.run(linking.link(lying), tmp_path / "lie", ceiling="read_only")


def test_shell_needs_signed_authority_for_writes_and_its_audit_detects_tampering(tmp_path):
    result = shell.exercise(tmp_path)
    assert result["executed"] == "EXECUTED" and result["reconciled"] and result["drift_detected"]
    assert set(result["refused"]) == {"execute_unauthorized_write", "intruder_signature", "wrong_hash", "replayed_nonce",
                                      "execute_revoked", "promote_without_evidence", "after_terminate"}
    assert all(result["refused"].values())
    assert result["audit"]["valid"] and ("propose", "refused") in [tuple(x) for x in result["audit_outcomes"]]
    assert result["promoted"] == [1, 2] and result["regressed_to"] == 3
    sh = shell.Shell(tmp_path / "shell", body_id="body-a", enrolled={})
    lines = (tmp_path / "shell" / "audit.jsonl").read_text().splitlines()
    forged = json.loads(lines[2]); forged["outcome"] = "ok"
    lines[2] = json.dumps(forged, sort_keys=True)
    (tmp_path / "shell" / "audit.jsonl").write_text("\n".join(lines) + "\n")
    assert sh.verify_audit() == {"valid": False, "broken_at": 2}, "rewriting a refusal into success is detected"


def test_discovery_is_signed_typed_fresh_and_grants_nothing(tmp_path):
    result = discovery.exercise(tmp_path)
    assert result["ranked"] == [["dale.assess_fast", 200], ["wmi.assess", 900]] or \
        result["ranked"] == [("dale.assess_fast", 200), ("wmi.assess", 900)]
    assert result["down_excluded"] and result["stale_after_ttl"] == 0 and not result["grants_access"]
    assert set(result["refusals"]) == {"unenrolled_organ", "forged_signature", "replayed_sequence", "untyped_contract",
                                       "rekey_without_founder"}
    assert len(result["static_seeded"]) == 3 and result["use_without_grant"] == "refused"


def test_observability_explains_a_real_greg_mission_and_why_a_metric_moved(tmp_path, capsys):
    result = observability.exercise(None)
    why = result["why_closures_fell"]
    assert why["direction"] == "down" and why["drivers"][0]["capability"] == "wmi.assess"
    assert any(a["kind"] == "mission.blocked" for a in why["drivers"][0]["after_window_anomalies"])
    assert result["why_latency_rose"][0]["delta"] == 1500.0
    # a real GREG body: one signed mission that needs founder approval
    home, key, body_id, _ = make_body(tmp_path)
    strategy = {"action_id": "store", "capability": "foundry.apply", "target": "foundry:cas",
                "params": {"system": 36, "op": "put", "args": {"text": "note"}}, "advances": ["stored"], "rationale": "r"}
    check = {"check_id": "stored", "description": "stored", "sensor": {"capability": "foundry.query",
             "params": {"system": 36, "op": "verify"}, "target": "foundry:cas"},
             "predicate": {"op": "gte", "field": "result.objects", "value": 1}}
    drop(home, signed(key, body_id, "MISSION", mission("m:obs", checks=[check], strategies=[strategy],
                                                        capabilities=["foundry.query"], targets=("foundry:*",),
                                                        ceiling="read_only")))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot(); clock.advance(30); body.tick()
        body.engine.book.rebuild()
        rid = body.engine.book.open_requests()[0]["request_id"]
    drop(home, signed(key, body_id, "DECISION", {"request_id": rid, "answer": "approve"}))
    with Body(home, clock=clock) as body:
        for _ in range(3):
            clock.advance(30); body.tick()
        events = _journal(body)
    spans = observability.correlate(events, "m:obs")["missions"]["m:obs"]["spans"]
    kinds = [s["kind"] for s in spans]
    assert kinds.index("decision.requested") < kinds.index("decision.answered") < kinds.index("mission.action")
    answered = next(s for s in spans if s["kind"] == "decision.answered")
    assert answered["latency_s"] is not None and answered["latency_s"] >= 0
    assert observability.metrics(events)["closures"] >= 1
    from greg import cli
    assert cli.main(["--home", str(home), "foundry", "trace", "--mission", "m:obs"]) == 0
    assert "m:obs" in json.loads(capsys.readouterr().out)["missions"]


def test_siem_learns_a_rule_from_a_confirmed_incident_on_a_real_body(tmp_path):
    result = siem.exercise(tmp_path / "ex")
    assert {c for c, _ in result["week1_alerts"]} == {"identity", "network", "credential", "spend", "outcome"}
    assert result["week2_single_forgery_before_learning"] == []
    assert result["week2_single_forgery_after_learning"] == [["derived.identity.1", ["e250"]]] or \
        result["week2_single_forgery_after_learning"] == [("derived.identity.1", ["e250"])]
    assert result["duplicate_rule_refused"]
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    (tmp_path / "real").mkdir()
    home, key, body_id, _ = make_body(tmp_path / "real")
    intruder = Ed25519PrivateKey.generate()
    for n in range(3):
        drop(home, signed(intruder, body_id, "BODY_STOP", {"reason": f"forged {n}"}))
    with Body(home) as body:
        body.boot()
        body.ingest_inbox()
        events = _journal(body)
    alerts = siem.detect(events, siem.rules(tmp_path / "siem"))
    assert [a["rule"] for a in alerts] == ["identity.burst"], "three forged founder commands are an identity incident"
    siem.confirm(tmp_path / "siem", alerts[0], events, note="intruder key")
    drop(home, signed(intruder, body_id, "BODY_STOP", {"reason": "forged again"}))
    with Body(home) as body:
        body.ingest_inbox()
        later = [e for e in _journal(body) if e["event_id"] not in {x["event_id"] for x in events}]
    assert any(a["rule"].startswith("derived.identity") for a in siem.detect(later, siem.rules(tmp_path / "siem")))


def test_twin_detects_drift_recalibrates_and_records_its_negative_result(tmp_path):
    result = twin.exercise(tmp_path)
    assert result["drift_alerts"] and result["drift_alerts"][0]["index"] >= result["regime_change_at"]
    assert result["recalibration_helps_under_drift"]
    assert result["brier_after_drift"]["adaptive"] < result["brier_after_drift"]["static"] - 0.05
    assert 0 <= result["cost_without_drift"] < 0.02, "recalibration's price when nothing drifts stays small"
    assert result["prediction_after_restart"]["observations"] == 60
    events = observability.sample_events()
    replayed = foundry_bridge.apply({"system": 42, "op": "replay_greg", "args": {"events": events}},
                                    _ctx(tmp_path, "foundry.apply"))
    assert replayed["result"]["observed"] == 4


def test_promotion_blocks_at_the_first_failed_stage_and_needs_ratified_evidence(tmp_path):
    result = promotion.exercise(tmp_path)
    assert {k: tuple(v) for k, v in result["blocked"].items()} == {
        "wrong_test": ("BLOCKED", "tests"), "replay_regression": ("BLOCKED", "replay"),
        "adversarial": ("BLOCKED", "adversarial"), "margin_floor": ("BLOCKED", "simulation"),
        "canary_inelastic_market": ("BLOCKED", "canary")}
    assert tuple(result["without_ratification"]) == ("BLOCKED", "ratification")
    assert tuple(result["wrong_ratification"]) == ("BLOCKED", "ratification")
    assert result["promoted"] == "PROMOTED" and result["stages_passed"] == list(promotion.STAGES)
    assert result["stage_results"]["canary"]["market"] == "emulated"
    good = promotion.candidate(result["committed"]["source"])
    hacked = dict(good, source="base_price * units")
    assert promotion.evidence_hash(hacked, []) != promotion.evidence_hash(good, [])


# -- increment 5: compilers, data model, portable components, MCP, teams, repair, owned build

from foundry.systems import build as owned_build
from foundry.systems import business_compiler, compiler, datamodel, mcp_gateway, repair, teams, wasm


def test_compiler_compiles_six_kinds_deterministically_and_locates_errors(tmp_path):
    result = compiler.exercise(tmp_path)
    assert result["kinds"] == ["business", "experiment", "organ_charter", "policy", "swarm_contract", "workflow"]
    assert result["deterministic"] and result["compiled_workflow_ran"] == "completed" and result["workflow_verified"]
    for name, errors in result["located_errors"].items():
        assert errors and all(e.startswith(f"{name}:") and e.split(":")[1].isdigit() for e in errors), (name, errors)
    assert "6:12" in result["located_errors"]["business-bad.yaml"][0], "the error points at price_usd"
    checked = foundry_bridge.query({"system": 1, "op": "compile", "args": {"source": "kind: nonsense\n"}},
                                   _ctx(tmp_path, "foundry.query"))
    assert checked["result"]["ok"] is False and "unknown kind" in checked["result"]["errors"][0]


def test_datamodel_joins_intent_authority_action_outcome_money_and_migrates_losslessly(tmp_path):
    result = datamodel.exercise(tmp_path)
    assert result["rows_second_ingest"] == 0, "re-ingesting the journal changes nothing"
    assert result["lossless_round_trip"] and result["backup_written"]
    research = next(m for m in result["mission_ledger"] if m["mission_id"] == "m:research")
    assert research["revenue_cents"] == 90000 and research["last_verdict"] == "VERIFIED"
    assert all(result["refusals"].values())
    with pytest.raises(datamodel.ModelError, match="unknown schema version"):
        datamodel.migrate(tmp_path / "x", 9)
    datamodel.migrate(tmp_path / "y", 1)
    import sqlite3
    db = sqlite3.connect(tmp_path / "y" / "institution.sqlite")
    db.execute("UPDATE schema_migrations SET checksum = 'edited' WHERE version = 1"); db.commit(); db.close()
    with pytest.raises(datamodel.ModelError, match="changed after it was applied"):
        datamodel.migrate(tmp_path / "y", 3)


def test_wasm_components_match_the_interpreter_and_the_host_grants_only_declared_imports(tmp_path):
    result = wasm.exercise(tmp_path)
    assert result["value"]["value"] == 270.0
    for key in ("pricing_differential", "budget_differential"):
        assert result[key]["disagree"] == 0 and result[key]["agree"] + result[key]["both_refused"] == 200
    assert set(result["refusals"]) == {"undeclared_wasi_import", "declared_but_host_forbids", "runaway_loop_out_of_fuel",
                                       "tampered_bytes"} and all(result["refusals"].values())
    assert result["declared_wasi_instantiates"]
    with pytest.raises(dsl.RuleError):
        wasm.compile_rule("pricing", "__import__('os')")


def test_mcp_tools_run_behind_kernel_identity_policy_and_gate(tmp_path):
    result = mcp_gateway.exercise(tmp_path)
    assert result["quote"] == 270.0 and result["failed_over_from"] == ["eco-a"]
    assert result["cross_checked_with"] == "uniimente-foundry", "two independent providers agree"
    assert result["provider_claims_send_is_read_only"] is True, "the provider lies; the policy decides"
    assert result["provider_calls_before_grant"] == 0 and result["provider_calls_after"] == 1
    assert set(result["refusals"]) == {"unknown_caller", "unlisted_tool", "send_without_grant", "grant_replayed"}
    assert all(result["refusals"].values()) and result["chain_ok"]
    out = foundry_bridge.query({"system": 28, "op": "foundry_tool", "args": {
        "tool": "foundry_query", "args": {"system": 43, "op": "check_approval_boundary", "args_json": "{}"}}},
        _ctx(tmp_path, "foundry.query"))
    assert json.loads(out["result"]["value"])["holds"] is True
    tools = {t["name"] for t in mcp_gateway.list_tools(mcp_gateway.FOUNDRY)}
    assert tools == {"foundry_query", "price_quote"}, "no write op is exposed over MCP"


def test_business_compiler_needs_admissible_verified_evidence_for_every_field(tmp_path):
    result = business_compiler.exercise(tmp_path)
    assert result["compiled_objects"] == ["business", "delivery", "experiment", "pricing"]
    assert result["economics"]["unit_margin_usd"] == 760.0, "price is the lowest evidenced acceptance, cost the worst"
    assert result["kill_rule"] == "fewer than 1 paid of 20 offers in 90 days"
    assert result["citations"]["price_usd"] == ["pay-1", "quote-1"]
    assert all(result["refusals"].values())
    assert "not admissible for price_usd" in result["refusals"]["interview_claims_price"][0]


def test_teams_intersect_authority_spend_nothing_extra_and_dissolve(tmp_path):
    result = teams.exercise(tmp_path)
    assert result["writer_wrote_and_dissolved"] == [True, "DISSOLVED"]
    assert result["narrow_grant_members"]["writer"]["max_consequence"] == "read_only"
    assert set(result["refusals"]) == {"competence_not_registered", "analyst_writes", "over_budget",
                                       "after_dissolution", "grant_caps_writer", "grant_without_role_capability"}
    assert all(result["refusals"].values())
    assert result["journal"][-1].startswith("refused: team offer-sprint is DISSOLVED")


def test_repair_writes_a_failing_test_finds_the_minimal_patch_and_records_the_procedure(tmp_path):
    result = repair.exercise(tmp_path)
    assert result["regression_before"] == "1 failed" and result["after_passed"]
    assert result["chosen"] == "line 7: drop '- 1'" and "range(remainder)" in result["diff"]
    assert result["tied"], "localization could not separate the lines; the tie was searched, not truncated"
    procedure = versions.content(tmp_path / "procedures", "recovery:split_invoice")
    assert procedure["fix"] == result["chosen"] and procedure["rejected"]
    with pytest.raises(repair.RepairError, match="does not reproduce"):
        repair.repair(tmp_path / "b", source=repair.TARGET, func="split_invoice",
                      failing={"id": "ok", "args": [90, 3], "expect": [30, 30, 30]}, passing=[{"args": [10, 1]}],
                      existing_tests=repair.EXISTING)


def test_owned_build_is_reproducible_and_runs_from_the_bundle(tmp_path):
    result = owned_build.exercise(tmp_path)
    assert result["identical_across_processes"] and result["verify"] and result["one_byte_changes_hash"]
    assert result["smoke"]["ran_from_bundle"], result["smoke"]
    assert result["toolchain_pins"] == ["PyYAML", "cryptography", "jsonschema", "pytest"]
