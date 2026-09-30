"""Assembly boundary tests plus opt-in real source-consumer composition."""
import copy
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import threading

import pytest

from adapters.contract_validation import validate_contract
from egregore.local_model import LocalModelClient, LocalModelConfig
from events.spine import EventSpine, WorkflowKilled
from foundry.research_consumers import SourceConsumer
from foundry.research_line import ResearchLine, job_spec, validate_analysis
from foundry.research_report import report
from foundry.research_sources import MAX_JSON, SearxSearch, normalize_results, source_record
from loom.ratify import Ratifier
from loom.weaver import LoomRefused
from provenance.ledger import EvidenceLedger, ReconciliationRequired

RESULTS = [{"title": "Synthetic observation", "url": "https://example.org/observation",
            "content": "Synthetic fixture: intake questions repeat; buyer demand is unverified."}]
JOB = {"query": "Could an intake checklist reduce repeated manual questions?",
       "audience": "Small business operators", "risk_flags": ["operator_review"]}
ANCHOR = "sandbox:research-test"


class Consumer:
    def __init__(self, role):
        self.role, self.calls, self.fail = role, [], False

    def binding(self):
        return {"role": self.role, "path": "/synthetic/" + self.role, "commit": "synthetic"}

    def assess(self, packet):
        self.calls.append(packet["id"])
        if self.fail:
            raise ValueError("synthetic failure")
        result = {"id": "synthetic-assessment", "schema_version": "1.1",
                  "created_at": datetime.now(timezone.utc).isoformat(),
                  "opportunity_packet_id": packet["id"], "go_no_go": "needs_more_evidence",
                  "requires_human_approval": True, "cases": []}
        validate_contract(result, "wire-venture-assessment")
        return result

    def draft(self, packet, analysis):
        self.calls.append(packet["id"])
        return {"drafts": [{"approval_status": "pending",
                           "source_opportunity_packet_id": packet["id"],
                           "draft_text": analysis["thesis"]}], "consumer_decisions": []}


def make_line(**kwargs):
    return ResearchLine(JOB, wmi=Consumer("wmi"), dale=Consumer("dale"),
                        fixture_results=RESULTS, fixture_analysis="template-preview", **kwargs)


def stack(line, *, path=None, workflow_id="test"):
    ledger = EvidenceLedger(ANCHOR, path=path)
    spine, ratifier = EventSpine(ledger), Ratifier(ledger)
    pattern = line.pattern(actor="synthetic-author", legal_principal="synthetic-operator")
    ratifier.decide(ratifier.submit(pattern), ratified=True,
                    ratifier="synthetic-operator", reason="test only")
    workflow = line.workflow(spine, ratifier, pattern, workflow_id=workflow_id)
    return ledger, spine, ratifier, pattern, workflow


def test_connected_bundle_preserves_evidence_and_pending_review():
    line = make_line()
    ledger, _, _, _, workflow = stack(line)
    workflow.execute()
    bundle = workflow.state["review_bundle"]
    assert bundle["activation_eligible"] is False
    assert bundle["status"] == "pending_review"
    assert bundle["market_validation"] == "unproven"
    assert bundle["opportunity_packet"]["confidence"] == 0
    assert bundle["opportunity_packet"]["buyer_type"] == ""
    assert bundle["opportunity_packet"]["risk_flags"] == JOB["risk_flags"]
    assert bundle["sources"][0]["evidence_tier"] == "observation"
    assert bundle["sources"][0]["verified_buyer_demand"] is False
    assert bundle["assessment"]["requires_human_approval"] is True
    assert line.wmi.calls == line.dale.calls
    assert ledger.verify_chain()[0]
    ledger.close()


def test_unratified_line_cannot_call_providers():
    line = make_line()
    ledger = EvidenceLedger(ANCHOR)
    pattern = line.pattern(actor="author", legal_principal="operator")
    with pytest.raises(LoomRefused, match="not ratified"):
        line.workflow(EventSpine(ledger), Ratifier(ledger), pattern, workflow_id="no")
    assert not line.wmi.calls and not line.dale.calls


def test_changed_query_invalidates_ratification():
    line = make_line()
    ledger, spine, ratifier, pattern, _ = stack(line)
    line.job["query"] = "A different operator request"
    with pytest.raises(LoomRefused, match="differs"):
        line.workflow(spine, ratifier, pattern, workflow_id="new")
    ledger.close()


def test_change_after_weaving_stops_before_execution():
    line = make_line()
    ledger, _, _, _, workflow = stack(line)
    line.job["risk_flags"] = []
    with pytest.raises(ReconciliationRequired):
        workflow.execute()
    assert not line.wmi.calls and not line.dale.calls
    ledger.close()


def test_failure_is_not_blindly_retried():
    line = make_line()
    line.wmi.fail = True
    ledger, _, _, _, workflow = stack(line)
    with pytest.raises(ReconciliationRequired):
        workflow.execute()
    assert workflow.status == "reconciliation_required"
    assert len(line.wmi.calls) == 1 and not line.dale.calls
    ledger.close()


def test_retained_checkpoint_resumes_without_repeating_completed_stages(tmp_path):
    path = str(tmp_path / "evidence.jsonl")
    line = make_line()
    ledger, _, _, _, workflow = stack(line, path=path)
    with pytest.raises(WorkflowKilled):
        workflow.execute(kill_at_step="drafts")
    assert len(line.wmi.calls) == 1
    sources = copy.deepcopy(workflow.state["sources"])
    ledger.close()
    reopened = EvidenceLedger(ANCHOR, path=path)
    replacement = make_line()
    pattern = replacement.pattern(actor="synthetic-author", legal_principal="synthetic-operator")
    resumed = replacement.workflow(EventSpine(reopened), Ratifier(reopened), pattern,
                                   workflow_id="test", resume=True)
    resumed.execute()
    assert resumed.state["sources"] == sources
    assert not replacement.wmi.calls and len(replacement.dale.calls) == 1
    assert reopened.verify_chain()[0]
    reopened.close()


def test_revoked_pattern_refuses_resume():
    line = make_line()
    ledger, spine, ratifier, pattern, workflow = stack(line)
    with pytest.raises(WorkflowKilled):
        workflow.execute(kill_at_step="hypothesis")
    ratifier.decide(pattern.hash(), ratified=False, reason="withdrawn", ratifier="synthetic-operator")
    with pytest.raises(LoomRefused, match="not ratified"):
        line.workflow(spine, ratifier, pattern, workflow_id="test", resume=True)
    ledger.close()


def test_workflow_identity_cannot_be_rebound():
    line = make_line()
    ledger, spine, ratifier, _, workflow = stack(line)
    with pytest.raises(WorkflowKilled):
        workflow.execute(kill_at_step="hypothesis")
    line.job["query"] = "Different request"
    pattern = line.pattern(actor="synthetic-author", legal_principal="synthetic-operator")
    ratifier.decide(ratifier.submit(pattern), ratified=True, reason="separate request")
    with pytest.raises(LoomRefused, match="another pattern"):
        line.workflow(spine, ratifier, pattern, workflow_id="test", resume=True)
    ledger.close()


@pytest.mark.parametrize("reply", [
    {"thesis": "x", "offer": "x", "validation_action": "x", "source_ids": ["invented"], "uncertainties": []},
    {"thesis": "x", "offer": "x", "validation_action": "x", "source_ids": [], "uncertainties": []},
    {"thesis": "x", "offer": "x", "validation_action": "x", "source_ids": [], "uncertainties": [], "grant": "publish"},
])
def test_hallucinated_citations_or_authority_fields_are_refused(reply):
    with pytest.raises(ValueError):
        validate_analysis(reply, normalize_results(RESULTS, 5))


@pytest.mark.parametrize("url", [
    "https://api.openai.com", "http://search.remote.example", "http://127.0.0.1:8080/path",
    "http://user:password@localhost:8080", "http://localhost:8080?target=cloud",
])
def test_hosted_search_and_ambiguous_local_urls_are_refused(url):
    with pytest.raises(ValueError):
        SearxSearch(url)


@pytest.mark.parametrize("job", [
    {"query": "x", "publish": True}, {"query": "x", "risk_flags": "none"},
    {"query": "x", "documents": [{"title": "x", "path": "/etc/passwd"}]},
    {"query": "x" * 1001},
])
def test_job_cannot_supply_actions_or_file_reads(job):
    with pytest.raises(ValueError):
        job_spec(job)


def test_duplicate_search_results_and_local_documents_remain_attributed():
    assert len(normalize_results(RESULTS + RESULTS, 5)) == 1
    line = ResearchLine({**JOB, "documents": [{"title": "Operator note", "text": "Demand unknown."}]},
                        wmi=Consumer("wmi"), dale=Consumer("dale"),
                        fixture_results=RESULTS, fixture_analysis="template-preview")
    ledger, _, _, _, workflow = stack(line)
    workflow.execute()
    sources = workflow.state["sources"]
    assert {s["kind"] for s in sources} == {"search_snippet", "local_document"}
    assert all(s["source_id"].startswith("sha256:") for s in sources)
    ledger.close()


@pytest.fixture
def local_server():
    context = {"search": {"results": RESULTS, "unresponsive_engines": [["synthetic", "test warning"]]},
               "redirect": False, "requests": []}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            context["requests"].append(("GET", self.path))
            if context["redirect"]:
                self.send_response(302)
                self.send_header("Location", "https://example.org/hosted")
                self.end_headers()
                return
            raw = context.get("raw", json.dumps(context["search"]).encode())
            self.send_response(200)
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            context["requests"].append(("POST", self.path))
            data = json.loads(request["messages"][1]["content"])
            sources = data["sources"]
            analysis = {"thesis": "An intake checklist could help. Buyer demand is unverified.",
                        "offer": "An intake checklist hypothesis",
                        "validation_action": "Review evidence before proposing any buyer contact",
                        "source_ids": [source["source_id"] for source in sources],
                        "uncertainties": ["Willingness to pay is unknown"]}
            reply = {"choices": [{"message": {"content": json.dumps(analysis)}}]}
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(reply).encode())
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    context["url"] = f"http://127.0.0.1:{server.server_port}"
    try:
        yield context
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_actual_search_protocol_bypasses_environment_proxy_and_retains_warnings(local_server, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    result = SearxSearch(local_server["url"]).search("operator query")
    assert len(result["sources"]) == 1
    assert result["search_warnings"]
    assert "format=json" in local_server["requests"][0][1]


def test_search_redirect_is_refused(local_server):
    local_server["redirect"] = True
    with pytest.raises(ValueError, match="redirect"):
        SearxSearch(local_server["url"]).search("x")
    assert len(local_server["requests"]) == 1


def test_search_response_is_bounded(local_server):
    local_server["raw"] = b"x" * (MAX_JSON + 1)
    with pytest.raises(ValueError, match="128 KiB"):
        SearxSearch(local_server["url"]).search("x")


def test_empty_search_preserves_missing_evidence():
    line = ResearchLine(JOB, wmi=Consumer("wmi"), dale=Consumer("dale"),
                        fixture_results=[], fixture_analysis="template-preview")
    ledger, _, _, _, workflow = stack(line)
    workflow.execute()
    assert workflow.state["opportunity_packet"]["evidence"] == []
    assert workflow.state["analysis"]["source_ids"] == []
    assert workflow.state["review_bundle"]["market_validation"] == "unproven"
    ledger.close()


def test_local_report_counts_review_outputs_without_claiming_success():
    pytest.importorskip("duckdb")
    ledger, _, _, _, workflow = stack(make_line())
    workflow.execute()
    result = report(ledger)
    assert result["verdict_counts"] == {"needs_more_evidence": 1}
    assert result["reviews"][0]["status"] == "pending_review"
    assert result["market_validation"] == "unproven"
    ledger.close()


def real_consumers():
    wmi, dale = os.getenv("WMI_SOURCE"), os.getenv("DALEOBANKS_SOURCE")
    if not wmi or not dale:
        pytest.skip("Real composition requires clean pinned consumer checkouts")
    return SourceConsumer(wmi, role="wmi"), SourceConsumer(dale, role="dale")


def test_real_consumer_composition_with_loopback_protocols(local_server, monkeypatch):
    wmi, dale = real_consumers()
    # Host/provider credentials must not enter the isolated consumer computation.
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-never-send")
    monkeypatch.setenv("DATABASE_URL", "postgresql://synthetic-should-not-connect")
    line = ResearchLine(JOB, wmi=wmi, dale=dale, search=SearxSearch(local_server["url"]),
                        model=LocalModelClient(LocalModelConfig(
                            base_url=local_server["url"] + "/v1")))
    ledger, _, _, _, workflow = stack(line)
    workflow.execute()
    bundle = workflow.state["review_bundle"]
    assert {method for method, path in local_server["requests"]} == {"GET", "POST"}
    assert bundle["inference_mode"] == "local_model" and bundle["search_mode"] == "searxng"
    validate_contract(bundle["opportunity_packet"], "wire-opportunity-packet")
    validate_contract(bundle["assessment"], "wire-venture-assessment")
    assert bundle["assessment"]["requires_human_approval"]
    assert bundle["assessment"]["cases"]
    assert bundle["drafts"] and all(d["approval_status"] == "pending" for d in bundle["drafts"])
    assert all(d["source_opportunity_packet_id"] == bundle["opportunity_packet"]["id"]
               for d in bundle["drafts"])
    assert ledger.verify_chain()[0]
    ledger.close()


def test_real_consumer_changes_after_planning_are_refused(monkeypatch):
    wmi, _ = real_consumers()
    original = wmi._git
    monkeypatch.setattr(wmi, "_git", lambda *args: "changed" if args[0] == "rev-parse" else original(*args))
    with pytest.raises(ValueError, match="changed after planning"):
        wmi.assess({"id": "p", "schema_version": "1.1", "created_at": "2026-09-30T00:00:00Z",
                    "core_thesis": "Synthetic hypothesis"})


def test_real_consumer_cannot_load_env_file(tmp_path):
    wmi, _ = real_consumers()
    path = tmp_path / "untrusted.env"
    path.write_text("UNEXPECTED_MODEL_KEY=synthetic-env-value\n")
    result = wmi._call(
        "import json, os, sys\n"
        "from dotenv import load_dotenv\n"
        "loaded = load_dotenv(json.load(sys.stdin)['path'])\n"
        "print(json.dumps({'loaded': loaded, 'unexpected': os.getenv('UNEXPECTED_MODEL_KEY')}))\n",
        {"path": str(path)})
    assert result == {"loaded": False, "unexpected": None}


def test_unsupported_env_loader_stops_before_consumer_execution(monkeypatch):
    import foundry.research_consumers as consumers
    monkeypatch.setattr(consumers, "version", lambda package: "1.1.1")
    consumer = object.__new__(SourceConsumer)
    with pytest.raises(ValueError, match="python-dotenv==1.2.3"):
        consumer._call("raise AssertionError('must never execute')", {})
