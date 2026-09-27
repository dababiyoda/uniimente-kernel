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
