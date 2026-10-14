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
    # One reviewed first-party read-only recipe now reaches retained machine
    # state; unreviewed provider/source refusal is exercised separately.
    bounded = foundry_bridge.query({"system": 28, "op": "foundry_tool", "args": {
        "tool": "foundry_query", "args": {"system": 43, "op": "check_approval_boundary", "args_json": "{}"}}},
        _ctx(tmp_path, "foundry.query"))
    assert json.loads(bounded["result"]["value"])["holds"] is True
    assert bounded["execution"]["persistence"] == "discarded"
    assert bounded["execution"]["arbitrary_source"] == "refused"
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


# -- increment 6: owned web --------------------------------------------------------------

from foundry.systems import webserver


def test_owned_site_serves_provable_pages_and_guards_portals(tmp_path):
    result = webserver.exercise(tmp_path)
    assert result["served"] == 200 and result["version"] == "2" and result["etag_is_content_hash"]
    assert all(result["third_party_verification"].values()), "a stranger with the public key can verify the page"
    assert result["forged_body_verification"]["body_matches_leaf"] is False
    assert result["history"] == ["add outcome", "launch"]
    assert result["not_modified"] == 304 and result["traversal"] == 400 and result["tampered_page"] == 500
    assert result["portal"] == {"own": 200, "other_customer": 403, "no_token": 401, "expired": 403, "forged": 403}
    assert result["public_bind_refused"]
    site = webserver.Site(tmp_path / "s2", key_seed=bytes(32 * [5]))
    with pytest.raises(webserver.SiteError, match="reason and evidence"):
        site.publish("/x.html", "x", reason="", evidence=[])
    rendered = foundry_bridge.query({"system": 31, "op": "render", "args": {"path": "/missing", "now": 0}},
                                    _ctx(tmp_path, "foundry.query"))
    assert rendered["result"]["status"] == 404


# -- increment 8 (part): cognitive router -------------------------------------------------

from foundry.systems import cognitive_router


def test_cognitive_router_ranks_by_verified_evidence_and_keeps_governance(tmp_path):
    result = cognitive_router.exercise(tmp_path)
    assert result["by_quality"][0] == "anthropic:opus" and result["by_cost"][0] == "local:llama"
    assert result["local_only"] == ["local:llama"], "a local-only request never reaches a contracted vendor"
    assert result["after_provider_loss"] == ["openai:gpt", "local:llama"] and result["memory_kept_after_loss"]
    assert result["failover_answered_by"] == "openai:gpt" and result["failover_tried"] == ["failed", "ok"]
    assert result["refusals"]["refusal_is_terminal"] == "Refusal", "a declined request is never re-asked elsewhere"
    assert "nothing_fits_budget_and_privacy" in result["refusals"]
    # dominance: a route worse on every axis never leads the order even under its favourable priority
    r = tmp_path / "dom"
    cognitive_router.declare(r, "a", provider="p", privacy="public", price_per_call_usd=0.01)
    cognitive_router.declare(r, "b", provider="p", privacy="public", price_per_call_usd=0.02)
    now = "2026-10-13T00:00:00Z"
    for n in range(6):
        cognitive_router.observe(r, "a", task="t", verdict="VERIFIED", cost_usd=0.01, latency_s=1.0, at=now, evidence=f"a{n}")
        cognitive_router.observe(r, "b", task="t", verdict="VERIFIED" if n < 2 else "REFUTED", cost_usd=0.02, latency_s=3.0,
                                 at=now, evidence=f"b{n}")
    d = cognitive_router.choose(r, task="t", privacy="public", priority="cost", now=now)
    assert d["order"] == ["a", "b"] and d["dominated"] == ["b"]
    with pytest.raises(cognitive_router.RouterPolicyError):
        cognitive_router.declare(r, "c", provider="p", privacy="secret")
    out = foundry_bridge.query({"system": 25, "op": "routes", "args": {"now": now}}, _ctx(tmp_path, "foundry.query"))
    assert out["result"] == {}, "a fresh mission workspace has no routes until declared"


# -- increment 7 (part): rabbit hole engine and path attribution ----------------------------

from foundry.systems import attribution, rabbit_hole


def test_rabbit_hole_routes_by_observed_doors_and_never_offers_weak_or_dark_nodes(tmp_path):
    result = rabbit_hole.exercise(tmp_path)
    assert result["territory_valid"] and "dark_pattern" in result["refusals"]
    assert result["routed_from_entry"] == "pod-basics", "the door visitors actually completed and bought through leads"
    assert result["alternatives"] == ["disputes"], "the other door is still offered, not hidden"
    assert result["weak_node_never_offered"] and result["from_disputes"] == "audit-kit"
    assert result["owned_ground"].startswith("portal:") and result["exit_ramp_always_present"] and result["depth_cap_stops"]
    stats = result["door_stats"]["why-proof->pod-basics"]
    assert stats["good"] <= stats["taken"], "a visitor counts once however well the visit went"
    assert 0 < rabbit_hole.door_value(stats) <= 1.0
    r2 = tmp_path / "t2"
    rabbit_hole.demo_territory(r2)
    rabbit_hole.observe(r2, session="s", kind="consume", node_id="why-proof", at="t")
    rabbit_hole.observe(r2, session="s", kind="leave", node_id="why-proof", at="t")
    with pytest.raises(rabbit_hole.RabbitHoleError, match="already left"):
        rabbit_hole.observe(r2, session="s", kind="consume", node_id="pod-basics", at="t")
    rec = foundry_bridge.query({"system": 50, "op": "recommend", "args": {"session": "nobody", "now": "t"}},
                               _ctx(tmp_path, "foundry.query"))
    assert rec["result"]["node"] is None and "exit_ramp" in rec["result"], "an empty territory routes nowhere, honestly"


def test_attribution_measures_paths_and_refuses_small_sample_stories(tmp_path):
    result = attribution.exercise(tmp_path)
    assert result["sessions"] == 24 and result["conversions"] == 10
    assert result["top_path"] == ["why-proof", "pod-basics", "audit-kit", "offer"]
    assert result["top_path_lower_bound"] < result["top_path_rate"], "reported with its uncertainty"
    assert result["single_session_path_lower_bound"] < 0.25, "one converting session is not a 100% path"
    assert result["attribution_sums_to_conversions"] and result["disputes_attracts_but_does_not_convert"]
    assert result["by_source"]["owned-newsletter"]["rate_lower_bound"] > result["by_source"]["platform-x"]["rate_lower_bound"]
    # the #34 engine measures the #50 engine's own log through the bridge (sibling store)
    ws = tmp_path / "ws" / "foundry"
    rabbit_hole.demo_territory(ws / "system-50")
    for i in range(3):
        rabbit_hole.observe(ws / "system-50", session=f"s{i}", kind="consume", node_id="why-proof", at="t")
        rabbit_hole.observe(ws / "system-50", session=f"s{i}", kind="consume", node_id="pod-basics", at="t")
        rabbit_hole.observe(ws / "system-50", session=f"s{i}", kind="buy" if i else "leave", node_id="pod-basics", at="t")
    measured = foundry_bridge.query({"system": 34, "op": "report_territory", "args": {}}, _ctx(tmp_path, "foundry.query"))
    assert measured["result"]["sessions"] == 3 and measured["result"]["conversions"] == 2
    assert attribution.wilson_lower(0, 0) == 0.0 and attribution.report([])["removal"]["attribution"] == {}


# -- increment 8 (part): payments on the rail's own SDK -----------------------------------------

from foundry.systems import payments


def test_payments_trace_every_charge_to_delivery_and_grant_and_reconcile_to_the_cent(tmp_path):
    result = payments.exercise(tmp_path)
    assert result["settled"] == "settled" and result["idempotent_retry_same_intent"]
    assert result["declined"]["status"] == "declined" and result["metered_settled"] == "settled" and result["usage_billed"]
    assert result["reconciled_to_processor"] and result["books_balance"]
    assert result["reserve_after_refund_cents"] < result["reserve_cents"] + 7000, "a refund draws the dispute reserve first"
    assert set(result["refusals"]) == {"live_key", "no_delivery_receipt", "no_grant", "grant_for_other_case",
                                       "double_charge_same_case", "metered_mismatch", "refund_over_charge", "refund_without_reason"}
    assert all(result["refusals"].values())
    # the emulator itself refuses a non-test key and an idempotency key reused for a different request
    server, emu = payments.start_emulator()
    try:
        status, body = emu.handle("POST", "/v1/payment_intents", {"amount": "100", "confirm": "true"}, "k1")
        assert status == 200
        assert emu.handle("POST", "/v1/refunds", {"payment_intent": body["id"]}, "k1")[0] == 400
        assert emu.handle("POST", "/v1/payment_intents", {"amount": "0"}, None)[0] == 400
    finally:
        server.shutdown(); server.server_close()
    books = foundry_bridge.query({"system": 38, "op": "books", "args": {}}, _ctx(tmp_path, "foundry.query"))
    assert books["result"]["balances"] == {}, "a fresh workspace has empty books; charging is never a free op"


# -- increment 8 (part): markets whose rules are code ---------------------------------------------

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from foundry.systems import agent_commerce, marketplace
from greg.founder import public_bytes


def test_marketplace_matches_by_sealed_second_price_and_settles_only_through_verification(tmp_path):
    result = marketplace.exercise(tmp_path)
    big = result["big"]
    assert big["winner"] == "party:alpha" and big["winning_bid_cents"] == 80000 and big["price_cents"] == 95000
    assert result["cheapest_bid_did_not_win"] and result["paid_second_price_not_own_bid"]
    assert "newcomer ceiling" in big["excluded"]["party:newcomer"] and "never revealed" in big["excluded"]["party:delta"]
    assert result["no_reveal_on_record"] and result["truthful_bidding_dominant"]
    assert result["strict"]["winner"] == "party:alpha" and result["sole_eligible_bidder_paid_ceiling"]
    assert "below the buyer's minimum" in result["strict"]["excluded"]["party:gamma"]
    assert result["standing"]["party:alpha"][0] == "rated" and result["standing"]["party:gamma"][2] == 1
    assert result["settlement"]["status"] == "settled" and result["settlement"]["take_cents"] == 4750
    assert result["settlement"]["supplier_payable_cents"] + result["settlement"]["take_cents"] == 95000
    assert result["refuted_never_charged"] and result["books"]["equation_holds"] and result["books"]["cash_plus_reserve_matches_processor"]
    assert set(result["refusals"]) >= {"self_dealing", "duplicate_commit", "reveal_before_close", "bid_after_close", "reveal_mismatch",
                                       "verify_by_supplier", "settle_before_verification", "settle_refuted", "forged_signature",
                                       "unenrolled_signer", "untyped_contract", "settle_grant_for_other_match", "settle_twice"}
    assert all(result["refusals"].values()), "every attack named is refused with a reason"
    # a sole unrated bidder cannot be paid more than the newcomer ceiling even when the buyer's ceiling is higher
    root = tmp_path / "fresh"
    buyer, seller = Ed25519PrivateKey.from_private_bytes(bytes(32 * [1])), Ed25519PrivateKey.from_private_bytes(bytes(32 * [2]))
    marketplace.enroll(root, "b", public_bytes(buyer.public_key()).hex())
    marketplace.enroll(root, "s", public_bytes(seller.public_key()).hex())
    marketplace.post_request(root, marketplace.sign(buyer, {"request_id": "r", "buyer": "b", "produces": "evidence", "ceiling_cents": 90000,
                                                            "closes_at": "2026-10-13T10:00:00Z", "verification_methods": ["human_review"],
                                                            "min_reputation": None}))
    marketplace.commit_bid(root, marketplace.sign(seller, {"request_id": "r", "supplier": "s",
                                                           "commitment": marketplace.commitment("r", "s", 30000, "x")}), now="2026-10-13T09:00:00Z")
    marketplace.reveal_bid(root, marketplace.sign(seller, {"request_id": "r", "supplier": "s", "amount_cents": 30000, "nonce": "x"}),
                           now="2026-10-13T10:00:00Z")
    awarded = marketplace.award(root, "r", now="2026-10-13T10:00:00Z")
    assert awarded["status"] == "unfilled" and "newcomer ceiling" in awarded["excluded"]["s"]
    board = foundry_bridge.query({"system": 37, "op": "board", "args": {}}, _ctx(tmp_path, "foundry.query"))
    assert board["result"]["requests"] == [] and board["result"]["rules"] == marketplace.DEFAULT_RULES
    with pytest.raises(CapabilityError, match="refused"):
        foundry_bridge.apply({"system": 37, "op": "award", "args": {"request_id": "nope", "now": "2026-10-13T10:00:00Z"}},
                             _ctx(tmp_path, "foundry.apply"))


def test_agent_commerce_sells_by_card_402_and_processor_verified_receipts(tmp_path):
    result = agent_commerce.exercise(tmp_path)
    assert result["published"]["skills"] == 2 and result["discovered"][0]["grants_access"] is False
    assert result["card_served"] and all(result["card_proof"].values()), "the served card is provably the seller's"
    assert result["quote_cents"] == 39200 and result["buyer_recomputes_same_quote"]
    assert result["challenge_status"] == 402 and result["redeemed"] == 200
    assert result["receipt_signature_verifies"] and result["forged_receipt_rejected"] and result["delivery_in_cas"]
    assert result["confirmed"] == "confirmed" and result["undeliverable"] == {"status": 409, "refunded_cents": 108000}
    assert result["receipts_without_verification_earn_nothing"] and result["declined_card_yields_no_payment"]
    assert result["standing"]["report"]["incidents"] == 1 and result["standing"]["audit"]["effective_outcomes"] == 1.0
    assert result["stray_swept"] == {"swept_cents": 39300, "payments": 2}, "under- and mis-paid money goes back to the payer"
    assert result["reconciled_to_processor"] and result["books_balance"] and result["refunds_due_after_sweep"] == 0
    assert set(result["refusals"]) >= {"unpriced_skill", "untyped_contract", "buyer_overrides_constant", "no_grant", "grant_for_other_order",
                                       "replay_same_payment", "replay_under_new_order", "underpaid", "payment_bound_to_other_order",
                                       "unknown_payment", "expired_challenge", "confirm_by_seller", "confirm_before_delivery"}
    assert all(result["refusals"].values())
    assert "replay refused" in result["refusals"]["replay_under_new_order"]
    orders = foundry_bridge.query({"system": 54, "op": "orders", "args": {}}, _ctx(tmp_path, "foundry.query"))
    assert orders["result"]["orders"] == [], "a fresh workspace has sold nothing"
    with pytest.raises(CapabilityError, match="no apply op"):
        foundry_bridge.apply({"system": 54, "op": "redeem", "args": {}}, _ctx(tmp_path, "foundry.apply"))


# -- governed implementation pluralism (convergence of #132 foundry-55 with the #158 line) ---------

from foundry import systems as foundry_systems


def test_co_implementations_stay_reachable_and_ambiguous_ops_must_be_qualified(tmp_path):
    # both lineages answer through the same system number; the primary backs the evidence
    assert foundry_systems.implementations(34) == ("attribution", "journeys")
    assert foundry_systems.implementations(50) == ("rabbit_hole", "journeys")
    query = foundry_systems.operations(34, "QUERY_OPS")
    assert "report" not in query, "a bare op two implementations declare is never resolved silently"
    assert query["attribution.report"] == ("attribution", "report") and query["journeys.report"] == ("journeys", "report")
    assert query["report_territory"] == ("attribution", "report_territory") and query["route"] == ("journeys", "route")
    with pytest.raises(LookupError, match="ambiguous"):
        foundry_systems.operation(34, "QUERY_OPS", "report")
    with pytest.raises(CapabilityError, match="ambiguous"):
        foundry_bridge.query({"system": 34, "op": "report", "args": {}}, _ctx(tmp_path, "foundry.query"))
    with pytest.raises(LookupError, match="no apply op"):
        foundry_systems.operation(31, "APPLY_OPS", "inspect")   # a query op never answers on the write table
    # the qualified #158 journeys report reads the shared observed-event store through the bridge
    out = foundry_bridge.query({"system": 34, "op": "journeys.report", "args": {"tier": "observed"}},
                               _ctx(tmp_path, "foundry.query"))
    assert out["result"]["events"] == 0
    # the #132 primary and the #158 co-implementation of system 31 share one store without colliding names
    rendered = foundry_bridge.query({"system": 31, "op": "render", "args": {"path": "/missing", "now": 0}},
                                    _ctx(tmp_path, "foundry.query"))
    assert rendered["result"]["status"] == 404


def test_contract_rejects_undeclared_or_overclaimed_co_implementations():
    rows = completion.contract()
    hidden = {**rows, 31: {k: v for k, v in rows[31].items() if k != "co_implementations"}}
    assert any("system 31: co_implementations [] differ from the registry ['portal']" in p
               for p in completion.audit(hidden, rerun=False))
    overclaimed = {**rows, 37: {**rows[37], "co_implementations": [{**rows[37]["co_implementations"][0], "state": "COMPLETE"}]}}
    assert any("must be PARTIAL or OUTSTANDING" in p for p in completion.audit(overclaimed, rerun=False))
    bad_tier = {**rows, 25: {**rows[25], "evidence_tier": "PRODUCTION"}}
    assert any("not in the directive vocabulary" in p for p in completion.audit(bad_tier, rerun=False))


# -- increment 8 (part): the embassy on a wire -----------------------------------------------------

from foundry.systems import embassy_wire


def test_embassy_wire_admits_by_challenge_verifies_before_acceptance_and_exposes_no_interior(tmp_path):
    result = embassy_wire.exercise(tmp_path)
    assert result["card_served"] and all(result["card_proof"].values())
    assert set(result["methods_exposed"]) == set(embassy_wire.METHODS) and len(result["methods_exposed"]) == 7
    assert result["admitted_ceiling"] == "internal_write" and result["admitted_budget_usd"] == 0.0
    assert result["negotiation"] == {"countered": "countered", "counter_cents": 500, "then": "accepted"}
    assert result["accepted"] == {"status": "accepted", "verification": "VERIFIED", "method": "deterministic_invariant"}
    assert result["receipt_verifies"] and result["sort_accepted"] == "accepted" and result["classify_accepted"] == "accepted"
    assert result["undecidable"] == {"status": "claimed", "verdict": "UNDECIDABLE"} and result["undecidable_earned_no_verdict"]
    assert result["rejected"]["status"] == "rejected" and result["rejected"]["suspended"] and result["refuted_task_reopened"]
    assert result["standing"]["loki@embassy:factor"]["incidents"] == 1 and result["standing"]["atlas@embassy:factor"]["incidents"] == 0
    assert result["ledger"]["admitted"] == 3 and result["ledger"]["routed_through_gate"] >= 8, "every claim and submission crossed the gate"
    assert result["books"] == {"equation_holds": True, "payable_to_agents_cents": 950}
    assert set(result["refusals"]) >= {"interior_path", "foundry_op_over_the_wire", "unsigned_before_admission", "card_not_signed_by_its_key",
                                       "wrong_audience", "expired_nonce", "replayed_nonce", "replayed_sequence", "forged_request_signature",
                                       "unknown_method_signed", "claim_already_claimed_task", "submit_unclaimed", "submit_twice",
                                       "claim_while_suspended"}
    assert all(result["refusals"].values())
    # the acceptance checks are invariants, not trust: a plausible-looking wrong factorization is refuted
    assert embassy_wire.verify_result("factor", {"n": 221}, {"factors": [1, 221]})["verdict"] == "REFUTED"
    assert embassy_wire.verify_result("factor", {"n": 221}, {"factors": [17, 13]})["verdict"] == "REFUTED", "canonical order is part of the contract"
    assert embassy_wire.verify_result("sort", {"items": [2, 1]}, {"sorted": [1, 2, 2]})["verdict"] == "REFUTED"
    with pytest.raises(embassy_wire.RpcError):
        embassy_wire.verify_result("mine", {}, {})
    assert embassy_wire.Embassy.verify_receipt("00" * 32, {"task_id": "t", "signature": "00" * 64}) is False
    tasks = foundry_bridge.query({"system": 29, "op": "tasks", "args": {}}, _ctx(tmp_path, "foundry.query"))
    assert tasks["result"]["tasks"] == [], "a fresh workspace has no embassy work posted"
    with pytest.raises(CapabilityError, match="no apply op"):
        foundry_bridge.apply({"system": 29, "op": "post_task", "args": {}}, _ctx(tmp_path, "foundry.apply"))


# -- increment 8 (part): commissioning agents in isolated branches -----------------------------------

from foundry.systems import commissioning


def test_commissioning_freezes_contracts_isolates_branches_and_proposes_only_green_changes(tmp_path):
    result = commissioning.exercise(tmp_path)
    vat = result["vat"]
    assert vat["status"] == "proposed" and vat["rounds"][0][1] == "red" and vat["rounds"][1][1] == "green"
    assert vat["rounds"][0][2] == ["tests/held_out/test_vat_rounding.py::test_half_rounds_up",
                                   "tests/held_out/test_vat_rounding.py::test_negative_rate_refused"], "the public tests passed; the held-out ones decided"
    assert all(f.startswith("held-out or public test failed: test_") for f in vat["feedback_named_tests_not_bodies"])
    assert vat["proposal_files"] == ["README.md", "pkg/tax.py", "tests/test_vat.py"] and vat["held_out_not_in_proposal"]
    assert vat["held_out_matches_contract"] and vat["secret_scrubbed_from_ci"] and vat["body_from_repo_template"] and vat["merged"] is False
    assert result["cone_breach"]["status"] == "abandoned" and len(result["cone_breach"]["problems"]) == 2
    assert result["shell"]["problems"] == ["pkg/tax.py: names subprocess"]
    assert result["nodocs"]["status"] == "abandoned" and result["nodocs"]["tests_green"], "green tests without the required docs is not a proposal"
    assert result["branches_kept"] == ["commission/cone", "commission/nodocs", "commission/shell", "commission/vat"]
    assert result["main_untouched"] and result["main_tree_unchanged"]
    sdk = result["agent_sdk"]
    assert sdk["configured"] and "Bash" not in sdk["allowed_tools"] and sdk["permission_mode"] == "acceptEdits" and sdk["live_route_run"] is False
    assert all(result["refusals"].values()) and set(result["refusals"]) == {"refreeze", "contract_without_held_out", "run_unfrozen"}
    # the screen alone
    assert commissioning.screen({"../escape.py": ""}, ["x.py"]) and commissioning.screen({"x.py": "import os\nos.environ['A']"}, ["x.py"])
    assert commissioning.screen({"x.py": "def f():\n    return 1\n"}, ["x.py"]) == []
    with pytest.raises(commissioning.CommissionError, match="not a git repository"):
        commissioning.Commission(tmp_path / "e", tmp_path / "not-a-repo")
    # the SDK builder refuses to run without the CLI rather than pretending
    builder = commissioning.AgentSDKBuilder(cli_path=None)
    builder.available = lambda: False
    with pytest.raises(commissioning.CommissionError, match="cannot run here"):
        builder.build({"contract": {}, "worktree": str(tmp_path)}, None)
    listing = foundry_bridge.query({"system": 51, "op": "commissions", "args": {}}, _ctx(tmp_path, "foundry.query"))
    assert listing["result"]["commissions"] == []
    with pytest.raises(CapabilityError, match="no apply op"):
        foundry_bridge.apply({"system": 51, "op": "run", "args": {}}, _ctx(tmp_path, "foundry.apply"))


# -- increment 8 (part): an owned instance on the fediverse ------------------------------------------

from foundry.systems import federation


def test_federation_owns_actors_verifies_signatures_and_moves_accounts_with_followers(tmp_path):
    result = federation.exercise(tmp_path)
    assert result["webfinger"] == {"status": 200, "self_link_is_actor": True, "unknown": 404}
    assert result["follow"] == {"delivered": True, "alpha_followers": 1, "beta_following_confirmed": True}
    pub = result["publish"]
    assert pub["delivered_to_reader"] and pub["remote_outbox_items"] == 1 and pub["inbox_verified_signer"]
    assert pub["dead_inbox_dead_lettered"] and pub["dead_letters"] == 1, "a dead follower is dead-lettered, not dropped"
    assert result["refusals"] == {"unsigned": 401, "digest_mismatch": 401, "forged_key_claim": 401, "create_from_unfollowed_actor": 403,
                                  "replayed_after_window": 401, "unfetchable_key": 401}
    port = result["portability"]
    assert port["export_verifies"] and port["tampered_export_rejected"] and port["forged_import"].startswith("export bundle signature")
    assert port["move_without_alias"].startswith("the new actor does not name this one")
    assert port["new_actor_also_known_as_old"] and port["old_actor_moved_to_new"] and port["move_delivered_to_follower"]
    assert port["follower_now_follows_new"] and port["new_instance_followers"] == [True] and port["old_instance_lost_follower"]
    assert port["publish_after_move_refused"] and port["post_from_new_instance_reached_follower"]
    assert "dead_lettered" in result["alpha_journal_kinds"] and result["private_key_in_export"] is False
    # the digest and signature helpers stand alone
    assert federation._digest(b"x") == "SHA-256=" + __import__("base64").b64encode(__import__("hashlib").sha256(b"x").digest()).decode()
    inst = federation.Instance(tmp_path / "solo", clock=lambda: "2026-10-13T15:00:00Z")
    ok, why, _ = inst.verify_request("POST", "/users/a/inbox", {}, b"{}")
    assert not ok and why == "unsigned"
    ok, why, _ = inst.verify_request("POST", "/users/a/inbox", {"Signature": "garbage"}, b"{}")
    assert not ok and "malformed" in why
    actors = foundry_bridge.query({"system": 33, "op": "actors", "args": {}}, _ctx(tmp_path, "foundry.query"))
    assert actors["result"]["actors"] == []
    with pytest.raises(CapabilityError, match="no apply op"):
        foundry_bridge.apply({"system": 33, "op": "publish", "args": {}}, _ctx(tmp_path, "foundry.apply"))


# -- increment 8 (part): the owned community -----------------------------------------------------------

from foundry.systems import owned_community as community


def test_community_holds_identity_history_and_exports_under_signed_rules(tmp_path):
    result = community.exercise(tmp_path)
    assert result["members"] == 5 and result["linked_actor_verified"] and result["posts"] == 9 and result["rate_limit_resets"]
    assert result["reports"] == [1, 2, 3] and result["held_at_third_report"] and result["released_can_post"] and result["tombstone_keeps_hash"]
    assert result["alice_rated_by_four_helpful_marks"] and result["supporter_tier_from_settled_charge"] and result["feed_served_with_provenance"]
    assert result["member_export"] == {"verifies": True, "posts": 6, "received": 3, "reports_made": 1}, "exported before the fourth mark"
    full = result["full_export"]
    assert full["verifies"] and full["tampered_rejected"] and full["members"] == 4 and full["posts"] == 9 and full["private_keys_absent"]
    assert result["platform_import"] == {"invitations_added": 2, "invitations_total": 2, "invited_member_claimed": True}
    assert set(result["refusals"]) >= {"join_twice", "join_forged", "link_actor_without_alias", "rate_limit", "reply_to_unknown", "non_member_post",
                                       "forged_member_signature", "self_mark", "duplicate_reaction", "post_while_held", "moderate_without_role",
                                       "moderator_cannot_promote", "react_to_tombstone", "tier_on_declined_charge", "tier_on_claimed_charge"}
    assert all(result["refusals"].values())
    # a bad platform export is refused, and a fresh community has only its owner
    key = Ed25519PrivateKey.from_private_bytes(bytes(32 * [7]))
    c = community.Community(tmp_path / "fresh", name="x", key_seed=bytes(32 * [8]), owner_public_hex=public_bytes(key.public_key()).hex())
    with pytest.raises(community.CommunityError, match="Account address"):
        c.import_followers_csv("name,url\nx,y\n", source="other", now="2026-10-13T15:00:00Z")
    assert [m["role"] for m in c._state()["members"].values()] == ["owner"]
    members = foundry_bridge.query({"system": 32, "op": "members", "args": {}}, _ctx(tmp_path, "foundry.query"))
    assert members["result"]["members"] == []
    with pytest.raises(CapabilityError, match="no apply op"):
        foundry_bridge.apply({"system": 32, "op": "post", "args": {}}, _ctx(tmp_path, "foundry.apply"))


# -- increment 8 (part): the media engine -----------------------------------------------------------

from foundry.systems import media_engine as media


def test_media_engine_renders_from_canon_with_disclosure_and_signed_provenance(tmp_path):
    result = media.exercise(tmp_path)
    assert result["image"]["width"] == 640 and result["image"]["format"] == "PNG" and result["image_bg_is_canon_bg"] and result["image_mark_is_canon_accent"]
    assert result["audio"] == {"duration_s": 3.0, "sample_rate": 22050, "channels": 1, "peak": 19660}
    assert result["video"] == {"width": 320, "height": 180, "frames": 36, "has_audio": True, "video_codec": "h264"}, "decoded, not assumed"
    assert result["video_first_frame_near_canon_bg"]
    assert result["interactive"] == {"self_contained": True, "has_disclosure": True, "interactive_steps": 3}
    assert result["every_manifest_discloses"] and result["ingredients_trace_to_canon"] and result["assets_indexed"] == 4
    assert result["verify_image"] == {"hash_matches": True, "signature_ok": True, "disclosed": True}
    assert result["verify_substituted_bytes"]["hash_matches"] is False and result["verify_tampered_manifest"]["signature_ok"] is False
    assert set(result["refusals"]) == {"canon_without_disclosure_rule", "canon_without_palette", "brief_without_title", "brief_omitting_disclosure",
                                       "unknown_kind", "unknown_note", "odd_video_dimensions"} and all(result["refusals"].values())
    # the engine's own checks and the bridge
    engine = media.Engine(tmp_path / "ws" / "foundry" / "system-35" / "engine", key_seed=bytes(32 * [3]), clock=lambda: "t",
                          canon=media.canon_from_persona(media.demo_persona(), palette={"bg": "#000000", "fg": "#ffffff", "accent": "#ff0000"},
                                                         mark="X", editorial_rules=list(media.REQUIRED_EDITORIAL_RULES)))
    png = engine.render_image({"title": "t", "size": (64, 32)})
    assert engine.inspect("image", png)["bg_pixel"] == [0, 0, 0]
    produced = engine.produce("interactive", {"title": "t", "lines": ["a"]})
    verified = foundry_bridge.query({"system": 35, "op": "verify", "args": {"asset": produced["asset"], "manifest": produced["manifest_address"]}},
                                    _ctx(tmp_path, "foundry.query"))
    assert verified["result"] == {"hash_matches": True, "signature_ok": True, "disclosed": True}, "GREG can verify an asset through the bridge"
    assets = foundry_bridge.query({"system": 35, "op": "assets", "args": {}}, _ctx(tmp_path, "foundry.query"))
    assert [a["kind"] for a in assets["result"]["assets"]] == ["interactive"]
    # this engine renders only as an operator act under a ratified canon: it declares no write op, and its
    # qualified name is refused. The #158 co-implementation's deterministic local "produce" stays reachable
    # under a foundry.apply grant (the policy split is recorded for the founder in the convergence ADR).
    assert media.APPLY_OPS == {}
    with pytest.raises(CapabilityError, match="no apply op"):
        foundry_bridge.apply({"system": 35, "op": "media_engine.produce", "args": {}}, _ctx(tmp_path, "foundry.apply"))
    from foundry import systems as registry
    assert registry.operations(35, "APPLY_OPS")["produce"] == ("media", "produce")


# -- increment 8 (part): the company loop end to end ------------------------------------------------

from foundry.systems import company_loop


def test_company_loop_runs_charter_to_kill_with_owned_distribution_products_finance_and_memory(tmp_path):
    result = company_loop.exercise(tmp_path)
    assert result["charter_ratified"] and result["followers_on_owned_actor"] == 2
    w1, w2, w3 = result["cycles"]
    assert w1["published"] == ["why-proof", "pod-basics", "audit-kit"] and result["weak_node_refused_at_publish"]
    assert w1["impressions"] == 6 and w1["owned_relationships"] == 3 and w1["useful_actions"] == {"completed_node": 4, "joined_community": 1, "purchased": 2}
    assert w1["informed_return"] == 1.75 and w1["closure"] == "CLOSED" and w1["revenue_cents"] == 18000 and w1["surplus_usd"] == 165.0
    assert w1["treasury_policy_version"] == 1 and w1["treasury_reconciled"] and w1["decision"] == "continue"
    assert w2["closure"] == "FALSELY_CLOSED" and w2["decision"] == "revise" and w2["treasury_policy_version"] is None, "no surplus, no allocation"
    assert w3["decision"] == "kill" and result["killed"] and result["memory_cycles"] == 3
    assert result["plan_after_cycle1"]["action"] == "continue" and result["plan_after_cycle1"]["least_attributed_node"] == "disputes"
    assert result["plan_after_kill"]["action"] == "stopped"
    assert result["owned_copies_in_outbox"] == 9 and result["reader_inbox_posts"] == 9 and result["every_post_discloses"]
    assert result["assets_with_provenance"] == 11 and result["community_members"] == 2 and result["community_export_verifies"]
    assert result["books"] == {"reconciled_to_processor": True, "equation_holds": True, "gross_cents": 18000}
    assert result["ledger"] == {"foundry.charter_submitted": 1, "foundry.charter_ratified": 1, "foundry.distribution_evaluated": 3}
    assert set(result["refusals"]) == {"publish_before_ratification", "off_topic_draft", "undisclosed_draft", "prohibited_pattern", "escalation_topic",
                                       "escalation_topic_even_if_allowed", "cycle_after_kill", "publish_after_kill"} and all(result["refusals"].values())
    assert company_loop.plan_from_memory({"cycles": [], "kill": None})["action"] == "start"
    plan = foundry_bridge.query({"system": 49, "op": "plan", "args": {}}, _ctx(tmp_path, "foundry.query"))
    assert plan["result"]["action"] == "start", "a fresh workspace has no company memory"
    with pytest.raises(CapabilityError, match="no apply op"):
        foundry_bridge.apply({"system": 49, "op": "cycle", "args": {}}, _ctx(tmp_path, "foundry.apply"))


def test_co_implementation_evidence_is_rederived_and_a_forged_record_fails(tmp_path, monkeypatch):
    rows = completion.contract()
    co = rows[35]["co_implementations"][0]
    assert co["module"] == "media" and co["evidence"] == "foundry/evidence/system-35-co-media.json"
    assert completion._co_implementation_problems(35, rows[35], "system 35") == []
    forged = json.loads((completion.ROOT / co["evidence"]).read_text())
    forged["result_sha256"] = "sha256:" + "0" * 64
    (tmp_path / "forged.json").write_text(json.dumps(forged))
    monkeypatch.setattr(completion, "ROOT", tmp_path)
    (tmp_path / "foundry" / "systems").mkdir(parents=True)
    for path in co.get("existing", []) + co.get("tests", []) + co.get("implementation", []):
        if ":" not in path:
            (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
            (tmp_path / path).write_text("")
    row = {**rows[35], "co_implementations": [{**co, "evidence": "forged.json"}]}
    assert any("does not reproduce" in p for p in completion._co_implementation_problems(35, row, "system 35"))
    with pytest.raises(KeyError, match="not registered"):
        completion.run(35, "portal")
