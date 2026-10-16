"""Signal -> venture decision memo: RailScout evidence, WealthMachine engine, one binding verdict.

CI uses two small stand-in organs written into tmp_path with the real organs' entry
points (``railscout.appraise.appraise`` and ``src.services.opportunity_intake``). They
exercise GREG's side of the bridge: process isolation, the evidence cap, write-once
delivery and the appraiser's re-run. The stand-in engine, like the real one, says "go"
with nondeterministic ids. ``test_real_organs`` runs the actual RailScout and
WealthMachine checkouts when GREG_TEST_RAILSCOUT and GREG_TEST_WMI point at them.
"""
import hashlib
import json
import os
from pathlib import Path
import textwrap

import pytest

from greg import ventures
from types import SimpleNamespace

from greg.body import Body, Layout
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, SecretBroker
from greg.templates import venture_assessment
from tests.greg_fixtures import Clock, drop, make_body, signed

RAILSCOUT_STUB = '''
import hashlib, json, os
from pathlib import Path

def appraise(manifest, source_root):
    assert not [k for k in os.environ if "GREG" in k or "TOKEN" in k], "organ received GREG environment"
    sources = []
    for s in manifest["sources"]:
        data = (Path(source_root) / s["path"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != s["sha256"]:
            raise SystemExit("source bytes do not match the manifest")
        sources.append(dict(s))
    market = manifest.get("market", {})
    missing = [k for k in ("buyer", "budget_owner") if not (market.get(k) and market.get("evidence", {}).get(k))]
    claims = [dict(c, byte_start=0, byte_end=len(c["excerpt"])) for c in manifest["claims"]]
    appraisal = {"question": manifest["question"], "transaction": manifest["transaction"],
                 "status": "NEEDS_EVIDENCE" if missing else "READY_FOR_HUMAN_REVIEW",
                 "missing": missing, "sources": sources, "claims": claims, "market": market,
                 "failure": {"layer": "proof", "description": "proof gap"},
                 "candidate": {"current_form": "a verifier service"},
                 "next_action": "Find independent evidence for buyer" if missing else "Ask the named buyer",
                 "strongest_counterexample": None}
    body = json.dumps(appraisal, sort_keys=True).encode()
    return {"appraisal": appraisal, "receipt_sha256": hashlib.sha256(body).hexdigest()}
'''

WMI_STUB = '''
import uuid, datetime

class OpportunityIntakeService:
    def evaluate_packet(self, packet):
        return {"id": str(uuid.uuid4()), "schema_version": "1.1", "opportunity_packet_id": packet["id"],
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "go_no_go": "go", "opportunity_score": 0.72, "market_alignment": 0.49, "risk_level": "low",
                "reasons": ["score meets threshold", f"{len(packet['evidence'])} evidence item(s)"],
                "cases": [{"case": "bull", "stance": "for", "severity": "medium", "argument": "score clears threshold"},
                          {"case": "bear", "stance": "against", "severity": "medium",
                           "argument": "demand asserted, not shown"},
                          {"case": "do_nothing", "stance": "against", "severity": "low",
                           "argument": "preserve attention for a stronger signal"}],
                "validation_plan": [packet["smallest_validation_action"]],
                "recommended_next_action": "validate", "requires_human_approval": True}
'''


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text))
    return path


def _manifest(signal: Path, *, buyer_evidenced=False) -> Path:
    text = "Operators lose a week reconciling delivery proof before invoices are paid.\n"
    _write(signal / "01-signal.txt", text)
    market = {"buyer": "regional freight brokers" if buyer_evidenced else "",
              "budget_owner": "broker finance lead" if buyer_evidenced else "",
              "evidence": {"buyer": ["C1"], "budget_owner": ["C1"]} if buyer_evidenced else {}}
    manifest = {"question": "Is delivery-proof reconciliation a venture?",
                "transaction": "a broker releases payment after proof of delivery",
                "sources": [{"id": "s1", "path": "01-signal.txt", "sha256": hashlib.sha256(text.encode()).hexdigest(),
                             "collected_at": "2026-09-26T11:00:00Z", "origin": "test", "rights": "test"}],
                "claims": [{"id": "C1", "source_id": "s1", "topic": "pain", "assertion": "reconciliation takes a week",
                            "excerpt": text.strip(), "stance": "supports", "kind": "observation"}],
                "market": market}
    return _write(signal / "manifest.json", json.dumps(manifest, indent=1))


@pytest.fixture
def organs(tmp_path):
    root = tmp_path / "data"
    rs, wmi = root / "railscout", root / "wmi"
    _write(rs / "railscout" / "__init__.py", "")
    _write(rs / "railscout" / "appraise.py", RAILSCOUT_STUB)
    _write(wmi / "src" / "services" / "opportunity_intake.py", WMI_STUB)
    signal = root / "signal"
    return {"railscout_root": str(rs), "wmi_root": str(wmi), "manifest": str(_manifest(signal)),
            "source_root": str(signal)}


def _ctx(tmp_path, read_roots, deliver=True):
    return InvocationContext(workspace=tmp_path / "ws", read_roots=tuple(Path(r) for r in read_roots),
                             secrets=SecretBroker(tmp_path / "vault.json"), manifest=BUILTINS["venture.assess"][0],
                             deliver_root=(tmp_path / "out") if deliver else None)


def test_binding_verdict_never_outruns_the_evidence():
    assert ventures.binding_verdict("NEEDS_EVIDENCE", "go")[0] == "needs_more_evidence"
    assert ventures.binding_verdict("NEEDS_EVIDENCE", "defer")[0] == "needs_more_evidence"
    assert ventures.binding_verdict("NEEDS_EVIDENCE", "kill")[0] == "kill", "a lower verdict is never raised"
    assert ventures.binding_verdict("READY_FOR_HUMAN_REVIEW", "go")[0] == "go"
    assert ventures.binding_verdict("SOMETHING_NEW", "go")[0] == "needs_more_evidence", "unknown status caps"


def test_packet_never_invents_an_unevidenced_buyer():
    base = {"receipt_sha256": "ab" * 32, "appraisal": {
        "question": "q", "failure": {"description": "d"}, "candidate": {"current_form": "c"}, "next_action": "n",
        "sources": [{"id": "s", "path": "p", "sha256": "0" * 64, "collected_at": "2026-09-26T00:00:00Z"}],
        "claims": [{"stance": "supports", "assertion": "a", "source_id": "s", "byte_start": 0, "byte_end": 1}],
        "market": {"buyer": "brokers", "budget_owner": "finance", "evidence": {}}}}
    packet = ventures.packet_from_appraisal(base)
    assert packet["audience"] == "" and packet["buyer_type"] == "", "named but unevidenced: left empty"
    assert packet == ventures.packet_from_appraisal(json.loads(json.dumps(base))), "deterministic"
    base["appraisal"]["market"]["evidence"] = {"buyer": ["C1"]}
    assert ventures.packet_from_appraisal(base)["audience"] == "brokers"


def test_assess_caps_the_engine_and_the_appraiser_reproduces_it(tmp_path, organs, monkeypatch):
    monkeypatch.setenv("GREG_TEST_SECRET", "must-not-reach-an-organ")
    ctx = _ctx(tmp_path, [tmp_path / "data"])
    out = ventures.assess(organs, ctx)
    assert (out["engine_verdict"], out["railscout_status"], out["verdict"]) == ("go", "NEEDS_EVIDENCE",
                                                                                 "needs_more_evidence")
    text = Path(out["path"]).read_text()
    assert "**Binding verdict: needs_more_evidence**" in text and "caps the engine's 'go'" in text
    assert "buyer" in text.split("## What is not evidenced")[1]
    assert ventures.status({"manifest": organs["manifest"]}, ctx)["verdict"] == "needs_more_evidence"
    ok, detail = ventures.verify_delivery(out, ctx.deliver_root)
    assert ok, detail
    assert ventures.assess(organs, ctx)["path"] == out["path"], "idempotent: same receipt, same file"


def test_evidenced_buyer_lets_the_engine_verdict_stand(tmp_path, organs):
    _manifest(Path(organs["source_root"]), buyer_evidenced=True)
    out = ventures.assess(organs, _ctx(tmp_path, [tmp_path / "data"]))
    assert out["verdict"] == "go" and out["inputs"]["packet"]["audience"] == "regional freight brokers"


@pytest.mark.parametrize("tamper, finding", [
    ("memo", "differs from the render"),
    ("source", "source bytes do not match the manifest"),
    ("manifest", "signal manifest changed"),
    ("engine", "WealthMachine does not reproduce"),
    ("receipt", "not the render of its inputs"),
])
def test_appraiser_refutes_every_substitution(tmp_path, organs, tamper, finding):
    ctx = _ctx(tmp_path, [tmp_path / "data"])
    out = ventures.assess(organs, ctx)
    if tamper == "memo":
        Path(out["path"]).write_text(Path(out["path"]).read_text().replace("needs_more_evidence", "go"))
    elif tamper == "source":
        (Path(organs["source_root"]) / "01-signal.txt").write_text("Operators are fine.\n")
    elif tamper == "manifest":
        _manifest(Path(organs["source_root"]), buyer_evidenced=True)
    elif tamper == "engine":
        stub = Path(organs["wmi_root"]) / "src" / "services" / "opportunity_intake.py"
        stub.write_text(stub.read_text().replace("0.72", "0.91"))
    else:
        out["inputs"]["binding"]["verdict"] = "go"
        out["inputs_digest"] = ventures.inputs_digest(out["inputs"])
    ok, detail = ventures.verify_delivery(out, ctx.deliver_root)
    assert not ok and finding in detail, detail


def test_refusals_outside_roots_without_delivery_and_on_organ_failure(tmp_path, organs):
    with pytest.raises(CapabilityError, match="outside permitted roots"):
        ventures.assess(organs, _ctx(tmp_path, [Path(organs["source_root"])]))
    with pytest.raises(CapabilityError, match="no delivery root"):
        ventures.assess(organs, _ctx(tmp_path, [tmp_path / "data"], deliver=False))
    (Path(organs["source_root"]) / "01-signal.txt").write_text("changed after the manifest was signed\n")
    with pytest.raises(CapabilityError, match="organ refused"):
        ventures.assess(organs, _ctx(tmp_path, [tmp_path / "data"]))
    assert not (tmp_path / "out" / "ventures").exists() or not list((tmp_path / "out" / "ventures").glob("*.md"))


def test_signed_mission_asks_first_delivers_one_memo_and_is_independently_verified(tmp_path, organs):
    home, key, body_id, _ = make_body(tmp_path)
    spec = venture_assessment(**organs)
    assert spec["light_cone"]["max_consequence_class"] == "read_only" and spec["light_cone"]["budget_usd"] == 0
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        clock.advance(30)
        assert body.tick()["missions"][0]["state"] == "WAITING", "delivery is outside the read-only cone"
        body.engine.book.rebuild()
        request = body.engine.book.open_requests()[0]
        assert request["authority_requested"]["capability"] == "venture.assess"
        assert not (Layout(home).home / "deliveries" / "ventures").exists(), "no organ ran before approval"
    drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"], "answer": "approve"}))
    with Body(home, clock=clock) as body:
        states = []
        for _ in range(3):
            clock.advance(30)
            states.append(body.tick()["missions"][0]["state"])
        assert states[:2] == ["ACTED", "ACHIEVED"]
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        assert appraisal["checks"]["deliveries_bound_to_evidence"] is True
        memo = next((Layout(home).home / "deliveries" / "ventures").glob("venture-*.md"))
        memo.write_text(memo.read_text().replace("**Binding verdict: needs_more_evidence**", "**Binding verdict: go**"))
        verdict = body.appraise(spec["mission_id"])
    assert verdict["verdict"] == "REFUTED" and any("differs from the render" in f for f in verdict["findings"])


@pytest.mark.skipif(not (os.environ.get("GREG_TEST_RAILSCOUT") and os.environ.get("GREG_TEST_WMI")),
                    reason="set GREG_TEST_RAILSCOUT and GREG_TEST_WMI to real organ checkouts")
def test_real_organs(tmp_path):
    rs, wmi = Path(os.environ["GREG_TEST_RAILSCOUT"]), Path(os.environ["GREG_TEST_WMI"])
    signal = rs / "examples" / "project-source-packet"
    params = {"railscout_root": str(rs), "wmi_root": str(wmi), "manifest": str(signal / "manifest.json"),
              "source_root": str(signal)}
    ctx = _ctx(tmp_path, [rs, wmi])
    out = ventures.assess(params, ctx)
    assert out["railscout_status"] == "NEEDS_EVIDENCE" and out["verdict"] == "needs_more_evidence"
    assert out["inputs"]["packet"]["audience"] == "" and "budget_owner" in out["inputs"]["canonical"]["packet_unresolved"]
    assert out["inputs"]["canonical"]["assessment_execution_authority"] is False
    ok, detail = ventures.verify_delivery(out, ctx.deliver_root)
    assert ok, detail


def _tick(body, clock, n=1):
    states = []
    for _ in range(n):
        clock.advance(30)
        states.append(body.tick()["missions"][0]["state"])
    return states


def test_standing_mission_reassesses_when_evidence_changes_and_each_hold_is_appraised(tmp_path, organs):
    home, key, body_id, _ = make_body(tmp_path)
    spec = venture_assessment(**organs, standing=True, cadence_seconds=60)
    assert spec["closure"]["kind"] == "infinite" and spec["mission_id"].startswith("m:venture-watch-")
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    folder = Layout(home).home / "deliveries" / "ventures"
    with Body(home, clock=clock) as body:
        body.boot()
        _tick(body, clock)
        body.engine.book.rebuild()
        request = body.engine.book.open_requests()[0]
    drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"], "answer": "approve"}))
    with Body(home, clock=clock) as body:
        assert _tick(body, clock, 2) == ["ACTED", "HOLDING"]
        first = next(folder.glob("venture-*.md")).read_text()
        assert "**Binding verdict: needs_more_evidence**" in first and "Evidencing buyer, budget_owner" in first
        _tick(body, clock, 4)                                            # cadence passes; evidence unchanged
        done = [e for e in body.journal.replay("mission.action") if e.payload["status"] == "DONE"]
        assert len(done) == 1 and len(list(folder.glob("*.md"))) == 1, "unchanged evidence: nothing re-runs"

        _manifest(Path(organs["source_root"]), buyer_evidenced=True)   # new evidenced buyer/budget
        assert "ACTED" in _tick(body, clock, 4)
        memos = sorted(p.read_text() for p in folder.glob("*.md"))
        assert len(memos) == 2 and any("**Binding verdict: go**" in m for m in memos), "nothing overwritten"
        assert len(list(body.journal.replay("decision.requested"))) == 1, "approved once, reused"
        judged = [e.payload for e in body.journal.replay("mission.appraised")]
        assert [j["verdict"] for j in judged] == ["VERIFIED", "VERIFIED"], [j["findings"] for j in judged]
        assert all(j["checks"]["deliveries_bound_to_evidence"] for j in judged)
        assert len({j["closure_event"] for j in judged}) == 2, "each hold after new action appraised once"


def test_flip_condition_names_the_gap_or_says_evidence_will_not_help():
    gap = {"missing": ["buyer"], "next_action": "Find independent evidence for buyer", "status": "NEEDS_EVIDENCE"}
    assert "stands between this signal and the engine's 'go'" in ventures.flip_condition(gap, "go", "needs_more_evidence")
    assert "more evidence alone will not make this a go" in ventures.flip_condition(gap, "kill", "kill")
    ready = {"missing": [], "next_action": "Ask the named buyer", "status": "READY_FOR_HUMAN_REVIEW"}
    assert "the decision is yours" in ventures.flip_condition(ready, "go", "go")


def test_standing_hold_is_refuted_when_its_new_delivery_was_altered(tmp_path, organs):
    home, key, body_id, _ = make_body(tmp_path)
    spec = venture_assessment(**organs, standing=True, cadence_seconds=60, preauthorize_delivery=True)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        assert _tick(body, clock) == ["ACTED"]
        memo = next((Layout(home).home / "deliveries" / "ventures").glob("*.md"))
        memo.write_text(memo.read_text().replace("needs_more_evidence", "go"))   # before the hold is judged
        assert _tick(body, clock) == ["HOLDING"]
        judged = [e.payload for e in body.journal.replay("mission.appraised")]
    assert judged[-1]["verdict"] == "REFUTED" and "differs from the render" in judged[-1]["findings"][0]


def test_counterevidence_travels_on_the_wire():
    receipt = {"receipt_sha256": "cd" * 32, "appraisal": {
        "question": "q", "failure": {"description": "d"}, "candidate": {"current_form": "c"}, "next_action": "n",
        "sources": [{"id": "s", "path": "p", "sha256": "0" * 64, "collected_at": "2026-09-26T00:00:00Z"}],
        "claims": [{"stance": "supports", "assertion": "pain is real", "source_id": "s", "byte_start": 0, "byte_end": 4},
                   {"stance": "challenges", "assertion": "a cheaper tool exists", "source_id": "s",
                    "byte_start": 5, "byte_end": 9}],
        "market": {}}}
    packet = ventures.packet_from_appraisal(receipt)
    assert packet["risk_flags"] == ["counterevidence: a cheaper tool exists [source p sha256:" + "0" * 64 + " bytes 5-9]"]
    assert all("cheaper" not in e for e in packet["evidence"])


def _namespaces_or_skip():
    from greg.worker_isolation import WorkerIsolationError, _backend
    try:
        _backend(require_bubblewrap=True)
    except WorkerIsolationError as exc:
        pytest.skip(f"no bubblewrap network namespaces here: {exc}")


PROBE = r'''
import json, socket, sys
try:
    socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=2).close()
    out = "REACHED"
except OSError as exc:
    out = type(exc).__name__
print(json.dumps({"result": out, "interfaces": sorted(name for _, name in socket.if_nameindex())}))
'''


def test_a_confined_organ_has_no_network_at_all(tmp_path):
    """#26: an appraisal needs no network, so on a confined body an organ runs in a namespace with no door. The same
    probe that reaches a listener on the body's loopback unconfined reaches nothing confined, and sees only lo."""
    import socket
    _namespaces_or_skip()
    listener = socket.create_server(("127.0.0.1", 0))
    port = str(listener.getsockname()[1])
    try:
        free = ventures._organ(PROBE, {}, port, cwd=tmp_path)
        confined = ventures._organ(PROBE, {}, port, cwd=tmp_path, confined=True)
    finally:
        listener.close()
    assert free["result"] == "REACHED"
    assert confined["result"] in ("ConnectionRefusedError", "OSError") and confined["interfaces"] == ["lo"]


def test_a_confined_body_assesses_and_its_appraiser_re_derives_inside_the_same_confinement(tmp_path, organs):
    """The stand-in RailScout reports which network interfaces it sees. The signed mission's assessment and the
    separate appraiser's re-run must agree on it: an appraiser that re-ran the organ unconfined would see the body's
    interfaces, its receipt would differ, and the appraisal would be REFUTED."""
    from greg.body import init_body
    from greg.founder import generate_founder_key, load_founder_key
    _namespaces_or_skip()
    stub = Path(organs["railscout_root"]) / "railscout" / "appraise.py"
    stub.write_text(stub.read_text().replace(
        '    return {"appraisal": appraisal, "receipt_sha256": hashlib.sha256(body).hexdigest()}',
        '    import socket\n'
        '    seen = sorted(name for _, name in socket.if_nameindex())\n'
        '    return {"appraisal": appraisal, "receipt_sha256": hashlib.sha256(body).hexdigest(), "interfaces": seen}'))
    home = tmp_path / "body"
    config = init_body(home, read_roots=[str(tmp_path / "data")], confined_egress=True)
    public = generate_founder_key(tmp_path / "founder.pem", None)
    with Body(home) as body:
        body.enroll_founder(public)
    key, body_id = load_founder_key(tmp_path / "founder.pem", None), config["body_id"]
    spec = venture_assessment(**organs)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        clock.advance(30)
        assert body.tick()["missions"][0]["state"] == "WAITING"
        body.engine.book.rebuild()
        request = body.engine.book.open_requests()[0]
    drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"], "answer": "approve"}))
    with Body(home, clock=clock) as body:
        states = _tick(body, clock, 3)
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        receipts = [r.payload["result"].get("output") for r in body.ledger.by_type("receipt")]
    assert states[:2] == ["ACTED", "ACHIEVED"]
    assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
    assessed = next(r for r in receipts if isinstance(r, dict) and "inputs" in r and "railscout" in r["inputs"])
    assert assessed["inputs"]["railscout"]["interfaces"] == ["lo"]          # the organ ran with no network


@pytest.mark.skipif(not (os.environ.get("GREG_TEST_RAILSCOUT") and os.environ.get("GREG_TEST_WMI")),
                    reason="set GREG_TEST_RAILSCOUT and GREG_TEST_WMI to real organ checkouts")
def test_real_organs_assess_unchanged_with_no_network(tmp_path):
    """The real RailScout appraiser and WealthMachine intake run in a namespace with no network and give the same
    assessment; the appraiser's confined re-run reproduces it."""
    _namespaces_or_skip()
    rs, wmi = Path(os.environ["GREG_TEST_RAILSCOUT"]), Path(os.environ["GREG_TEST_WMI"])
    signal = rs / "examples" / "project-source-packet"
    params = {"railscout_root": str(rs), "wmi_root": str(wmi), "manifest": str(signal / "manifest.json"),
              "source_root": str(signal)}
    free = ventures.assess(params, _ctx(tmp_path / "free", [rs, wmi]))
    ctx = _ctx(tmp_path / "confined", [rs, wmi])
    ctx.egress = object()                                   # a confined body: organs get no network at all
    confined = ventures.assess(params, ctx)
    assert {k: confined[k] for k in ("verdict", "engine_verdict", "railscout_status")} == \
           {k: free[k] for k in ("verdict", "engine_verdict", "railscout_status")}
    assert confined["inputs"]["railscout"] == free["inputs"]["railscout"]
    ok, detail = ventures.verify_delivery(confined, ctx.deliver_root, confined=True)
    assert ok, detail


# -- the Mind inside the memo: a revenue figure may not outrun its causal support (directive section 16) ----

ECONOMICS = {"revenue": {"factors": [{"name": "brokers", "low": 20, "central": 60, "high": 150, "units": {"broker": 1}},
                                     {"name": "fee_per_broker_year", "low": 1200, "central": 2400, "high": 4800,
                                      "units": {"USD": 1, "broker": -1, "year": -1}}],
                         "expected_units": {"USD": 1, "year": -1},
                         "assumptions": ["one verifier seat per broker"], "next_measurement": "price three brokers"},
             "causal_support": {"design": "observational", "treated": [9, 11], "control": [4, 6]}}
RANDOMIZED = {**ECONOMICS, "causal_support": {"design": "randomized", "treated": [9, 11], "control": [4, 6],
                                              "dag": [["verifier", "paid_on_time"]]}}


def _tick_until(body, clock, state, limit=8):
    states = []
    for _ in range(limit):
        clock.advance(30)
        states.append(body.tick()["missions"][0]["state"])
        if states[-1] == state:
            return states
    raise AssertionError(f"never reached {state}: {states}")


def test_a_revenue_figure_never_outruns_its_causal_support():
    estimate = {"abstention_state": "NONE", "output": {"low": 1, "central": 2, "high": 3}}
    identified = {"abstention_state": "NONE", "output": {"identified_conditionally": True, "effect": 3}}
    unidentified = {"abstention_state": "UNIDENTIFIED", "output": {"identified_conditionally": False}}
    assert ventures.revenue_conclusion(None, identified)["kind"] == "none"
    assert ventures.revenue_conclusion({"abstention_state": "ABSTAIN"}, identified)["kind"] == "none"
    assert ventures.revenue_conclusion(estimate, None)["kind"] == "conditional"
    assert ventures.revenue_conclusion(estimate, unidentified)["kind"] == "conditional"
    assert ventures.revenue_conclusion(estimate, identified)["kind"] == "stated"
    assert ventures.revenue_conclusion(estimate, {"abstention_state": "NONE", "output": {}})["kind"] == "conditional"


def test_without_economics_the_memo_states_no_revenue_figure_and_the_mission_is_unchanged(organs):
    spec = venture_assessment(**organs)
    assert [s["action_id"] for s in spec["strategies"]] == ["assess-venture"]
    assert "cognition.solve" not in spec["light_cone"]["capabilities"] and "cognition" not in spec["strategies"][0]["params"]
    assert ventures.render({**_minimal_inputs(), "cognition": None,
                            "revenue": ventures.revenue_conclusion(None, None)}).count("no revenue figure is stated") == 1


def _minimal_inputs():
    appraisal = {"question": "q", "status": "NEEDS_EVIDENCE", "next_action": "n", "transaction": "t",
                 "failure": {"layer": "proof", "description": "d"}, "claims": [], "missing": [], "sources": []}
    return {"renderer": ventures.RENDERER, "manifest_sha256": "0" * 64,
            "railscout": {"appraisal": appraisal, "receipt_sha256": "ab" * 32},
            "packet": {"id": "p"}, "assessment": {"go_no_go": "go", "opportunity_score": 0.5, "market_alignment": 0.5,
                                                  "risk_level": "low", "reasons": [], "cases": [], "validation_plan": []},
            "canonical": {"packet_unresolved": [], "assessment_execution_authority": False},
            "binding": {"verdict": "needs_more_evidence", "why": "w"}, "flip": "f",
            "organs": {"railscout_head": None, "wmi_head": None}}


def test_the_mission_asks_gregs_own_cognition_first_and_the_memo_draws_no_revenue_conclusion_without_identification(
        tmp_path, organs):
    _write(Path(organs["manifest"]).with_name("economics.json"), json.dumps(ECONOMICS))
    home, key, body_id, _ = make_body(tmp_path)
    spec = venture_assessment(**organs)
    assert [s["action_id"] for s in spec["strategies"]] == ["revenue-receipt", "causal-receipt", "assess-venture"]
    assert spec["strategies"][2]["requires"] == ["revenue_estimated", "causal_checked"]
    assert spec["light_cone"]["max_consequence_class"] == "read_only" and "cognition:*" in spec["light_cone"]["targets"]
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        _tick_until(body, clock, "WAITING")                      # cognition ran inside the cone; delivery waits
        receipts = [r.payload["result"]["output"] for r in body.ledger.by_type("receipt")
                    if isinstance(r.payload["result"].get("output"), dict)
                    and r.payload["result"]["output"].get("problem_id", "").startswith("venture-")]
        assert {r["problem_id"].split("-")[1] for r in receipts} == {"revenue", "causal"}
        assert all(r["authority_created"] is False for r in receipts)
        body.engine.book.rebuild()
        request = body.engine.book.open_requests()[0]
        assert request["authority_requested"]["capability"] == "venture.assess"
        assert not (Layout(home).home / "deliveries" / "ventures").exists(), "no organ ran before approval"
    drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"], "answer": "approve"}))
    with Body(home, clock=clock) as body:
        _tick_until(body, clock, "ACHIEVED")
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        memo = next((Layout(home).home / "deliveries" / "ventures").glob("venture-*.md"))
        text = memo.read_text()
        assert "**conditional**" in text and "no revenue conclusion is drawn" in text
        assert "Estimate: 24000 to 720000 USD year^-1 (central 144000)" in text
        assert "Dominant uncertainty: brokers" in text and "Causal support: not identified (UNIDENTIFIED)" in text
        memo.write_text(text.replace("**conditional**", "**stated**"))
        verdict = body.appraise(spec["mission_id"])
        assert verdict["verdict"] == "REFUTED" and any("differs from the render" in f for f in verdict["findings"])


def test_identified_randomized_support_is_stated_with_its_assumptions_and_a_forged_receipt_is_refuted(tmp_path, organs):
    _write(Path(organs["manifest"]).with_name("economics.json"), json.dumps(RANDOMIZED))
    home, key, body_id, _ = make_body(tmp_path)
    spec = venture_assessment(**organs, preauthorize_delivery=True)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        _tick_until(body, clock, "ACHIEVED")
        memo = next((Layout(home).home / "deliveries" / "ventures").glob("venture-*.md"))
        text = memo.read_text()
        # the converged causal family names this identification assumption "random assignment"
        assert "**stated**" in text and "randomized difference in means 5" in text and "random assignment" in text
        receipt = [r for r in body.ledger.by_type("receipt")
                   if "inputs" in ((r.payload["result"].get("output") or {}) if isinstance(r.payload["result"].get("output"), dict) else {})][-1]
        output = json.loads(json.dumps(receipt.payload["result"]["output"]))
        ok, _ = ventures.verify_delivery(output, Layout(home).home / "deliveries", ledger=body.ledger)
        assert ok
        forged = json.loads(json.dumps(output))
        forged["inputs"]["cognition"]["causal"]["output"]["effect"] = 50       # digest no longer matches
        ok, why = ventures.verify_delivery(forged, Layout(home).home / "deliveries", ledger=body.ledger)
        assert not ok and "digest" in why
        offledger = json.loads(json.dumps(output))
        from greg.cognition.contracts import digest as receipt_digest
        causal = offledger["inputs"]["cognition"]["causal"]
        causal["output"]["effect"] = 50
        causal.pop("receipt_id")
        causal["receipt_id"] = receipt_digest(causal)
        # the converged receipt contract also binds the proof artifact to the output: this forgery is not even valid
        from greg.cognition.settlement import _valid_receipt
        assert not _valid_receipt(causal)
        causal.pop("receipt_id")
        causal["proof_artifact"]["estimate"] = 50
        causal["receipt_id"] = receipt_digest(causal)                           # self-consistent, never on the ledger
        assert _valid_receipt(causal)
        offledger["inputs"]["revenue"] = ventures.revenue_conclusion(offledger["inputs"]["cognition"]["revenue"], causal)
        offledger["inputs_digest"] = ventures.inputs_digest(offledger["inputs"])
        rendered = ventures.render(offledger["inputs"]).encode()
        memo.write_bytes(rendered)
        offledger["sha256"] = hashlib.sha256(rendered).hexdigest()
        ok, why = ventures.verify_delivery(offledger, Layout(home).home / "deliveries", ledger=body.ledger)
        assert not ok and "not on the canonical ledger" in why


def test_the_organ_bridge_reads_receipts_through_a_handle_with_no_write_method(tmp_path):
    # The bridge only reads the Mind's receipts. It is handed the ledger's by_type and nothing else: no journal
    # record, no replay, no append. In-process Python cannot be sandboxed, so this removes every write path from
    # the handle; it is not a security boundary against code that deliberately introspects.
    home, _, _, _ = make_body(tmp_path)
    with Body(home, clock=Clock()) as body:
        body.boot()
        ctx = body.engine._context(SimpleNamespace(mission_id="m:reader"), BUILTINS["venture.assess"][0])
        assert isinstance(ctx.journal, ventures.LedgerReader)
        assert [a for a in dir(ctx.journal) if not a.startswith("_")] == ["ledger"]
        assert [a for a in dir(ctx.journal.ledger) if not a.startswith("_")] == ["by_type"]
        assert list(ctx.journal.ledger.by_type("receipt")) == list(body.ledger.by_type("receipt"))
        with pytest.raises(AttributeError):
            ctx.journal.ledger.append = body.ledger.append
        cognition = body.engine._context(SimpleNamespace(mission_id="m:c"), BUILTINS["cognition.solve"][0])
        assert cognition.journal is body.journal            # other grants are unchanged


@pytest.mark.skipif(not (os.environ.get("GREG_TEST_RAILSCOUT") and os.environ.get("GREG_TEST_WMI")),
                    reason="set GREG_TEST_RAILSCOUT and GREG_TEST_WMI to real organ checkouts")
def test_real_organs_consume_the_minds_receipts_on_a_signed_mission(tmp_path):
    # Directive section 16 on the real organs: the RailScout and WealthMachine checkouts, one signed body mission,
    # and GREG's own revenue and causal receipts. Observational support yields an estimate and no revenue conclusion.
    rs, wmi = Path(os.environ["GREG_TEST_RAILSCOUT"]), Path(os.environ["GREG_TEST_WMI"])
    signal = rs / "examples" / "project-source-packet"
    home, key, body_id, _ = make_body(tmp_path, read_roots=[rs, wmi])
    spec = venture_assessment(railscout_root=str(rs), wmi_root=str(wmi), manifest=str(signal / "manifest.json"),
                              source_root=str(signal), economics=ECONOMICS, preauthorize_delivery=True)
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        _tick_until(body, clock, "ACHIEVED")
        appraisal = body.journal.replay("mission.appraised")[-1].payload
        assert appraisal["verdict"] == "VERIFIED", appraisal["findings"]
        memo = next((Layout(home).home / "deliveries" / "ventures").glob("venture-*.md")).read_text()
    assert "**Binding verdict: needs_more_evidence**" in memo
    assert "**conditional**" in memo and "no revenue conclusion is drawn" in memo
    assert "Causal support: not identified (UNIDENTIFIED)" in memo
