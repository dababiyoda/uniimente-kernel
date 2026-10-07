"""Joined mission steps on a real signed body; sensor data never becomes authority."""
import pytest

from greg.body import Body
from greg.authority import AuthorityOffice
from greg.dataflow import BindingError, resolve_bindings
from greg.missions import MissionError, evaluate_predicate, validate_mission
from greg import workers
from greg.workflow_templates import browser_worker_document
from tests.greg_fixtures import Clock, drop, make_body, mission, note_check, signed, workspace, write_strategy


def copy_spec(home, source, *, preauthorize=True):
    dest = workspace(home, "m:compose") / "result.txt"
    strategy = write_strategy("copy", "result.txt", "", ["copied"], requires=["source"])
    strategy["param_bindings"] = [{"param": "content", "check_id": "source", "field": "text"}]
    spec = mission("m:compose", checks=[note_check("source", source, "payload"),
                                        note_check("copied", dest, "payload")], strategies=[strategy],
                   capabilities=["fs.read", "fs.write"] if preauthorize else ["fs.read"])
    return spec, dest


def ticks(home, clock, count=4):
    with Body(home, clock=clock) as body:
        for _ in range(count):
            body.tick()
            clock.advance(1)


def test_source_receipt_flows_to_next_step_after_restart_without_copying(tmp_path):
    home, key, bid, data = make_body(tmp_path)
    source = data / "source.txt"
    source.write_text("payload: evidence retained across restart")
    spec, dest = copy_spec(home, source, preauthorize=False)
    drop(home, signed(key, bid, "MISSION", spec))
    clock = Clock()
    ticks(home, clock, 1)
    with Body(home) as body:
        req = body.engine.book.open_requests()[0]
        assert req["authority_requested"]["params"]["content"] == source.read_text()
        assert req["authority_requested"]["bindings"][0]["receipt"]
    drop(home, signed(key, bid, "DECISION", {"request_id": req["request_id"], "answer": "approve"}))
    ticks(home, clock, 3)
    with Body(home) as body:
        assert body.engine.book.missions["m:compose"].status == "ACHIEVED"
        action = body.journal.replay("mission.action")[-1].payload
        binding = action["bindings"][0]
        assert body.journal.ledger.find(binding["receipt"]).record_type == "receipt"
        assert body.journal.event_hash(binding["observation_event"]) == binding["observation_hash"]
        assert len(body.journal.replay("decision.requested")) == 1
        assert len(body.journal.replay("mission.action")) == 1
    assert dest.read_text() == source.read_text()


def test_changed_source_invalidates_approved_resolved_params(tmp_path):
    home, key, bid, data = make_body(tmp_path)
    source = data / "source.txt"
    source.write_text("payload before approval")
    spec, dest = copy_spec(home, source, preauthorize=False)
    drop(home, signed(key, bid, "MISSION", spec))
    clock = Clock()
    ticks(home, clock, 1)
    with Body(home) as body:
        original = body.engine.book.open_requests()[0]
    source.write_text("payload changed after approval request")
    drop(home, signed(key, bid, "DECISION", {"request_id": original["request_id"], "answer": "approve"}))
    ticks(home, clock, 1)
    with Body(home) as body:
        fresh = body.engine.book.open_requests()[0]
        assert fresh["scope_digest"] != original["scope_digest"]
        assert fresh["authority_requested"]["params"]["content"] == source.read_text()
    assert not dest.exists()
    drop(home, signed(key, bid, "DECISION", {"request_id": fresh["request_id"], "answer": "approve"}))
    ticks(home, clock, 2)
    assert dest.read_text() == source.read_text()


@pytest.mark.parametrize("attack", ["target", "capability", "authority_ref", "provider", "allowed_paths",
                                  "acceptance", "tools", "max_budget_usd"])
def test_signed_data_binding_cannot_change_execution_or_authority(tmp_path, attack):
    home, key, bid, data = make_body(tmp_path)
    spec, _ = copy_spec(home, data / "source")
    spec["strategies"][0]["params"][attack] = "fixed"
    spec["strategies"][0]["param_bindings"][0]["param"] = attack
    with pytest.raises(MissionError):
        validate_mission(spec)


def test_binding_requires_explicit_prerequisite_and_unique_destination(tmp_path):
    home, _, _, data = make_body(tmp_path)
    spec, _ = copy_spec(home, data / "source")
    spec["strategies"][0]["requires"] = []
    with pytest.raises(MissionError, match="required check"):
        validate_mission(spec)
    spec["strategies"][0]["requires"] = ["source"]
    spec["strategies"][0]["param_bindings"] *= 2
    with pytest.raises(MissionError, match="duplicate parameter"):
        validate_mission(spec)


@pytest.mark.parametrize("source_text,field", [("payload" + "x" * 18000, "text"), ("payload", "missing")])
def test_missing_or_truncated_source_waits_and_does_not_stop_independent_mission(tmp_path, source_text, field):
    home, key, bid, data = make_body(tmp_path)
    source = data / "source.txt"
    source.write_text(source_text)
    spec, dest = copy_spec(home, source)
    spec["strategies"][0]["param_bindings"][0]["field"] = field
    spec["priority"] = 100
    other = workspace(home, "m:independent") / "ok.txt"
    independent = mission("m:independent", checks=[note_check("ready", other, "finished")],
                          strategies=[write_strategy("finish", "ok.txt", "finished", ["ready"])],
                          capabilities=["fs.read", "fs.write"], priority=1)
    for item in (spec, independent):
        drop(home, signed(key, bid, "MISSION", item))
    clock = Clock()
    ticks(home, clock, 3)
    with Body(home) as body:
        assert body.engine.book.missions["m:independent"].status == "ACHIEVED"
        assert body.engine.book.missions["m:compose"].status == "ACTIVE"
        assert not [e for e in body.journal.replay("mission.action") if e.payload["mission_id"] == "m:compose"]
    assert not dest.exists()
    if field == "text":
        # A truncation is a transient data gap, not a permanent founder-only
        # blocker. The parent mission resumes automatically when data heals.
        source.write_text("payload complete after repair")
        clock.advance(31)
        ticks(home, clock, 2)
        assert dest.read_text() == source.read_text()


def test_receipt_substitution_and_stale_source_are_rejected(tmp_path):
    home, key, bid, data = make_body(tmp_path)
    source = data / "source.txt"
    source.write_text("payload")
    spec, _ = copy_spec(home, source, preauthorize=False)
    drop(home, signed(key, bid, "MISSION", spec))
    clock = Clock()
    ticks(home, clock, 1)
    with Body(home) as body:
        state = body.engine.book.missions["m:compose"]
        observed_at = state.observations["source"]["at"]
        kwargs = dict(mission=state, strategy=spec["strategies"][0], journal=body.journal,
                      observed_at=observed_at, evaluate_predicate=evaluate_predicate)
        with pytest.raises(BindingError, match="fresh"):
            resolve_bindings(**{**kwargs, "observed_at": "1900-01-01T00:00:00Z"})
        state.observations["source"]["receipt"] = state.observations["copied"]["receipt"]
        with pytest.raises(BindingError, match="sensor dispatch"):
            resolve_bindings(**kwargs)


def test_silently_capped_receipt_list_cannot_supply_an_apparently_complete_string(tmp_path):
    home, key, bid, data = make_body(tmp_path)
    source = data / "source.txt"
    source.write_text("payload")
    spec, dest = copy_spec(home, source)
    spec["strategies"][0]["param_bindings"][0]["field"] = "values.999"
    drop(home, signed(key, bid, "MISSION", spec))
    with Body(home, clock=Clock()) as body:
        original = body.registry.adapters["fs.read"]
        def sensor(params, ctx):
            if params["path"] == str(source):
                return {"text": "payload", "values": ["payload"] * 1001}
            return original(params, ctx)
        body.registry.adapters["fs.read"] = sensor
        body.tick()
        body.engine.book.rebuild()
        assert body.engine.book.missions["m:compose"].blocker["type"] == "dataflow"
        assert "truncated list" in str(body.engine.book.missions["m:compose"].blocker)
    assert not dest.exists()


class LocalDocumentWorker:
    """Deterministic local provider, not a live AI or evidence of model ability."""
    def __init__(self, cost=0.1):
        self.cost, self.orders = cost, []

    def available(self):
        return True, ""

    def run(self, order, cwd):
        self.orders.append(order)
        (cwd / order.acceptance["output"]).write_text(order.context)
        return workers.WorkerReport("local-test", "local-test", 0, 0.01, self.cost)


def document_spec(source):
    return mission("m:worker-compose", checks=[note_check("source", source, "payload"),
        {"check_id": "accepted", "description": "independent worker appraisal accepted the document",
         "sensor": {"capability": "worker.appraise", "params": {"order": "compose"}, "target": "work:compose"},
         "predicate": {"op": "equals", "field": "verdict", "value": "ACCEPTED"}}],
        strategies=[{"action_id": "draft", "capability": "worker.commission", "target": "work:compose",
            "params": {"order": "compose", "mode": "document", "objective": "Quote this context accurately",
                       "context": "", "provider": "local-test", "inputs": [], "allowed_paths": ["draft.md"],
                       "max_budget_usd": 1.0, "timeout_seconds": 60, "acceptance": {"output": "draft.md"}},
            "param_bindings": [{"param": "context", "check_id": "source", "field": "text"}],
            "requires": ["source"], "advances": ["accepted"], "cost_usd": 1.0,
            "rationale": "bounded document from fresh evidence"}],
        capabilities=["fs.read", "worker.commission", "worker.appraise"], targets=["fs:*", "work:compose"], budget=1)


def test_real_body_composes_observed_text_into_worker_then_independently_appraises(tmp_path, monkeypatch):
    home, key, bid, data = make_body(tmp_path)
    source = data / "source.txt"
    source.write_text("payload to compose without manual copying")
    provider = LocalDocumentWorker()
    monkeypatch.setitem(workers.PROVIDERS, "local-test", provider)
    spec = document_spec(source)
    drop(home, signed(key, bid, "MISSION", spec))
    clock = Clock()
    ticks(home, clock, 3)
    with Body(home) as body:
        state = body.engine.book.missions["m:worker-compose"]
        assert state.status == "ACHIEVED" and state.spent_usd == 0.1
    assert len(provider.orders) == 1 and provider.orders[0].context == source.read_text()
    assert (workspace(home, "m:worker-compose") / "work-orders/compose/work/draft.md").read_text() == source.read_text()


def test_collected_but_uncertain_worker_receipt_reserves_cap_and_never_blindly_retries(tmp_path, monkeypatch):
    home, key, bid, data = make_body(tmp_path)
    source = data / "source.txt"
    source.write_text("payload")
    monkeypatch.setitem(workers.PROVIDERS, "local-test", LocalDocumentWorker())
    calls = []
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.apply(signed(key, bid, "MISSION", document_spec(source)))
        def interrupted(params, ctx):
            calls.append(ctx.grant_id)
            return {"status": "UNCERTAIN", "work_order": "compose",
                    "spend": workers.worker_spend(None, 1.0), "cost_usd": 1.0}
        body.registry.adapters["worker.commission"] = interrupted
        for _ in range(3):
            body.tick()
            clock.advance(1)
        body.engine.book.rebuild()
        state = body.engine.book.missions["m:worker-compose"]
        assert state.spent_usd == 1.0 and state.actions_done == 0
        assert state.blocker["type"] == "reconciliation"
        action = body.journal.replay("mission.action")[-1].payload
        assert action["status"] == "UNCERTAIN" and action["cost_reserved"] is True
        assert body.journal.ledger.find(action["receipt"]).record_type == "receipt"
        assert len(calls) == 1
    # Process replacement reconstructs the same reservation and wait state.
    ticks(home, clock, 2)
    with Body(home) as body:
        assert body.engine.book.missions["m:worker-compose"].spent_usd == 1.0
        assert len(body.journal.replay("mission.action")) == 1


def test_paid_approval_cannot_bypass_reserved_budget_after_not_executed_reconciliation(tmp_path, monkeypatch):
    home, key, bid, data = make_body(tmp_path)
    source = data / "source.txt"
    source.write_text("payload")
    monkeypatch.setitem(workers.PROVIDERS, "local-test", LocalDocumentWorker())
    spec = document_spec(source)
    spec["light_cone"]["capabilities"].remove("worker.commission")
    clock, calls = Clock(), []
    with Body(home, clock=clock) as body:
        body.apply(signed(key, bid, "MISSION", spec))
        def interrupted(params, ctx):
            calls.append(ctx.grant_id)
            return {"status": "UNCERTAIN", "spend": workers.worker_spend(None, 1.0), "cost_usd": 1.0}
        body.registry.adapters["worker.commission"] = interrupted
        body.tick()
        body.engine.book.rebuild()
        approval = body.engine.book.open_requests()[0]
        assert approval["kind"] == "APPROVAL" and not calls
        body.apply(signed(key, bid, "DECISION", {"request_id": approval["request_id"], "answer": "approve"}))
        clock.advance(1)
        body.tick()
        body.engine.book.rebuild()
        state = body.engine.book.missions[spec["mission_id"]]
        assert len(calls) == 1 and state.spent_usd == 1.0
        reconciliation = body.engine.book.open_requests()[0]
        assert reconciliation["kind"] == "RECONCILIATION"
        body.apply(signed(key, bid, "DECISION", {
            "request_id": reconciliation["request_id"], "answer": "reconcile_not_executed"}))
        clock.advance(1)
        body.tick()
        body.engine.book.rebuild()
        fresh = body.engine.book.open_requests()[0]
        assert fresh["kind"] == "APPROVAL" and fresh["scope_digest"] != approval["scope_digest"]
        assert fresh["evidence"]["budget"] == {"spent_usd": 1.0, "budget_usd": 1.0}
        assert len(calls) == 1  # old approval cannot authorize another paid dispatch
        body.apply(signed(key, bid, "DECISION", {"request_id": fresh["request_id"], "answer": "approve"}))
        clock.advance(1)
        body.tick()
        body.engine.book.rebuild()
        assert len(calls) == 2 and body.engine.book.missions[spec["mission_id"]].spent_usd == 2.0


@pytest.mark.parametrize("with_receipt", [True, False])
def test_paid_scope_upgrade_recovers_legacy_dispatch_without_repeating_it(tmp_path, monkeypatch, with_receipt):
    home, key, bid, data = make_body(tmp_path)
    source = data / "source.txt"
    source.write_text("payload")
    monkeypatch.setitem(workers.PROVIDERS, "local-test", LocalDocumentWorker())
    spec, calls = document_spec(source), []
    with Body(home) as body:
        body.apply(signed(key, bid, "MISSION", spec))
        state = body.engine.book.missions[spec["mission_id"]]
        manifest = body.registry.manifests["worker.commission"]
        def execute(params, ctx):
            calls.append(ctx.grant_id)
            if not with_receipt:
                raise RuntimeError("interrupted after the legacy dispatch claim")
            return {"status": "COMPLETED"}
        kwargs = dict(mission_id=state.mission_id, cone=state.cone, command_digest=state.command_digest,
                      manifest=manifest, adapter=execute, ctx=body.engine._context(state, manifest),
                      params=spec["strategies"][0]["params"], target="work:compose", cost_usd=1.0,
                      expected_outcome="worker collected", evidence_refs=[], attempt=0, spent_usd=0.0,
                      approved_scopes=set())
        with monkeypatch.context() as legacy:
            legacy.setattr(body.office, "scope_digest", lambda **scope: AuthorityOffice.scope_digest(
                **{k: v for k, v in scope.items() if k not in ("spent_usd", "budget_usd")}))
            original = body.office.act(**kwargs)
        recovered = body.office.act(**kwargs)
        assert len(calls) == 1 and recovered.proposal_id == original.proposal_id
        assert recovered.status == ("DONE" if with_receipt else "UNCERTAIN")
        assert recovered.receipt_hash == original.receipt_hash


def test_browser_worker_template_keeps_host_acceptance_and_prerequisite_signed():
    spec = browser_worker_document(url="https://example.invalid/", session="research", order="draft",
        extracted_field="findings", steps=[{"op": "extract", "selector": "main", "as": "findings"}],
        objective="write an evidence brief", provider="local-test")
    validate_mission(spec)
    strategy = spec["strategies"][-1]
    assert strategy["requires"] == ["retrieved"]
    assert strategy["param_bindings"] == [{"param": "context", "check_id": "retrieved", "field": "extracted.findings"}]
    assert spec["light_cone"]["targets"] == ["web:example.invalid", "work:draft"]
    assert strategy["params"]["acceptance"]["require_context_quote"] is True


def test_signed_body_browser_evidence_feeds_quoted_independently_appraised_document(tmp_path, monkeypatch):
    pytest.importorskip("playwright")
    from greg.capabilities import CapabilityError
    from greg.computer import chromium
    try:
        chromium()
    except CapabilityError:
        pytest.skip("real Chromium is not installed")
    import http.server
    import threading
    evidence_text = "payload from actual browser observation"
    class Page(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(f"<html><body><main>{evidence_text}</main></body></html>".encode())
        def log_message(self, *args):
            pass
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        home, key, bid, _ = make_body(tmp_path)
        provider = LocalDocumentWorker()
        monkeypatch.setitem(workers.PROVIDERS, "local-test", provider)
        spec = browser_worker_document(url=f"http://127.0.0.1:{server.server_address[1]}/",
            session="body-evidence", order="from-browser", extracted_field="findings",
            steps=[{"op": "extract", "selector": "main", "as": "findings"}],
            objective="Write a document quoting this evidence", provider="local-test")
        drop(home, signed(key, bid, "MISSION", spec))
        clock = Clock()
        ticks(home, clock, 4)
        with Body(home) as body:
            assert body.engine.book.missions[spec["mission_id"]].status == "ACHIEVED"
            assert body.journal.replay("mission.parameters_resolved")
            appraisal = body.appraise(spec["mission_id"])
            assert appraisal["verdict"] == "VERIFIED", appraisal
            assert appraisal["checks"]["world_reobserved"] is True
        assert len(provider.orders) == 1 and provider.orders[0].context == evidence_text
        assert provider.orders[0].acceptance["require_context_quote"] is True
        document = workspace(home, spec["mission_id"]) / "work-orders/from-browser/work/draft.md"
        assert document.read_text() == evidence_text
    finally:
        server.shutdown()
        server.server_close()


def test_signed_body_forms_cortex_dependency_and_automatically_resumes_original_problem(tmp_path):
    pytest.importorskip("networkx")
    pytest.importorskip("scipy")
    from tests.unit.test_greg_cortex_convergence import problem, spec as cortex_spec
    home, key, bid, _ = make_body(tmp_path)
    spec = cortex_spec(problem("graph.shortest_path"), "graph.shortest_path", True)
    drop(home, signed(key, bid, "MISSION", spec))
    clock = Clock()
    ticks(home, clock, 4)
    with Body(home) as body:
        state = body.engine.book.missions["m:typed-cortex"]
        assert state.status == "ACHIEVED"
        resolved = body.journal.replay("deficit.resolved")
        assert len(resolved) == 1 and resolved[0].payload["capability_id"].startswith("acquired.graph.shortest_path.")
        actions = body.journal.replay("mission.action")
        assert len(actions) == 1 and actions[0].payload["action_id"] == "compute"
        assert body.journal.replay("mission.strategy_retry")
        receipt = body.journal.replay("cognition.receipt")[-1].payload
        assert receipt["answered"] and receipt["problem_id"] == spec["strategies"][0]["params"]["problem"]["problem_id"]
        appraisal = body.appraise("m:typed-cortex")
        assert appraisal["verdict"] == "VERIFIED", appraisal
        assert appraisal["checks"]["cognition_attachment_authority_rederived"] is True
        assert appraisal["checks"]["world_reobserved"] is True
