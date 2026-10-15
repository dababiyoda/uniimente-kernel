"""Two organ processes exchange authenticated messages through a Kernel-led mission (Bridge A, both organs real).

CI uses two small stand-in organs written into tmp_path with the real organs' entry points and the real Kernel
bridge transport (``adapters.bridge_transport``) and bridge state (``events.bridge_state``). They exercise GREG's
side: per-exchange key minting, process isolation, relay checks on both legs, the evidence cap, write-once
delivery and the appraiser's re-run. ``test_real_organs`` runs the actual DALEOBANKS and WealthMachineIntelligence
checkouts when GREG_TEST_DALEOBANKS and GREG_TEST_WMI point at them.
"""
import hashlib
import json
import os
from pathlib import Path
import textwrap

import pytest

from greg import organ_exchange as ox
from greg.body import Body
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, SecretBroker
from greg.templates import organ_exchange
from tests.greg_fixtures import Clock, drop, make_body, signed

CONTEXT_PACKET_STUB = '''
from dataclasses import dataclass, field

@dataclass
class ContextPacket:
    text: str
    claims: list
    stakes: str
    risk: float
    human_cost: object
    system_failure: object
    evidence_needed: bool
    confidence: float
    provenance: dict

def build_packet(*, source, raw_ref="", text="", actor=None, topic=None, trust="untrusted", firewall=None):
    import os
    assert not [k for k in os.environ if "GREG" in k or "TOKEN" in k], "organ received GREG environment"
    claims = [s.strip() + "." for s in text.split(".") if "according to" in s.lower()]
    return ContextPacket(text=text, claims=claims, stakes="medium" if claims else "low", risk=0.0,
                         human_cost=None, system_failure=None, evidence_needed=bool(claims), confidence=1.0,
                         provenance={"trust": trust, "injection_patterns": [], "vault_id": "stub-vault"})
'''

MODELS_STUB = '''
from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Any, Dict, List
import uuid

def _uuid():
    return str(uuid.uuid4())

def _utcnow():
    return datetime.now(UTC)

@dataclass
class OpportunityPacket:
    id: str = field(default_factory=_uuid)
    source: str = ""
    source_ref: str = ""
    signal_type: str = "operator_thought"
    observed_pain: str = ""
    core_thesis: str = ""
    audience: str = ""
    cultural_context: str = ""
    language: str = "en"
    customer_segment: str = ""
    buyer_type: str = ""
    urgency: str = "medium"
    evidence: List[str] = field(default_factory=list)
    possible_offer: str = ""
    monetization_paths: List[str] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    smallest_validation_action: str = ""
    confidence: float = 0.5
    created_at: datetime = field(default_factory=_utcnow)
    status: str = "pending"
'''

VENTURE_PROTOCOL_STUB = '''
from dataclasses import asdict
SCHEMA_VERSION = "1.1"
ALLOWED_SIGNAL_TYPES = frozenset({"operator_thought", "product_opportunity", "repeated_question"})

def packet_to_wire(packet):
    payload = asdict(packet)
    payload["schema_version"] = SCHEMA_VERSION
    payload["created_at"] = packet.created_at.isoformat()
    from adapters.contract_validation import validate_contract
    validate_contract(payload, "wire-opportunity-packet")
    return payload

def validate_assessment_wire(payload):
    from adapters.contract_validation import validate_contract
    validate_contract(payload, "wire-venture-assessment")
    if payload.get("go_no_go") not in {"go", "defer", "kill", "needs_more_evidence"}:
        raise ValueError("go_no_go")
    return payload
'''

LEDGER_STUB = '''
import hashlib, json, os

class DecisionLedger:
    def __init__(self, path=None):
        self.path = path or os.environ["LEDGER_PATH"]

    def _tail(self):
        if not os.path.exists(self.path):
            return 0, ""
        lines = [l for l in open(self.path).read().splitlines() if l]
        last = json.loads(lines[-1]) if lines else {"seq": 0, "hash": ""}
        return last["seq"], last["hash"]

    def record(self, event, payload=None):
        seq, prev = self._tail()
        entry = {"seq": seq + 1, "event": event, "payload": payload or {}, "prev_hash": prev}
        entry["hash"] = hashlib.sha256(json.dumps(entry, sort_keys=True).encode()).hexdigest()
        with open(self.path, "a") as fh:
            fh.write(json.dumps(entry) + "\\n")
        return entry

    def verify_chain(self):
        prev = ""
        for line in open(self.path).read().splitlines():
            entry = json.loads(line)
            material = {k: v for k, v in entry.items() if k != "hash"}
            if entry["prev_hash"] != prev or hashlib.sha256(json.dumps(material, sort_keys=True).encode()).hexdigest() != entry["hash"]:
                return False
            prev = entry["hash"]
        return True

def get_ledger():
    return DecisionLedger()
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

SIGNAL = {"topic": "delivery proof", "source": "operator",
          "text": "Small freight brokers lose invoices because proof of delivery arrives as photos nobody can verify. "
                  "According to the broker, chargebacks take 40 days."}


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text))
    return path


@pytest.fixture
def organs(tmp_path):
    root = tmp_path / "data"
    d, w = root / "daleobanks", root / "wmi"
    for name, text in (("services/__init__.py", ""), ("services/context_packet.py", CONTEXT_PACKET_STUB),
                       ("services/venture_protocol.py", VENTURE_PROTOCOL_STUB),
                       ("services/bridge_security.py", "from adapters.bridge_transport import *\n"),
                       ("services/ledger.py", LEDGER_STUB), ("db/__init__.py", ""), ("db/models.py", MODELS_STUB)):
        _write(d / name, text)
    for name, text in (("src/__init__.py", ""), ("src/services/__init__.py", ""),
                       ("src/services/opportunity_intake.py", WMI_STUB)):
        _write(w / name, text)
    signal = _write(root / "signals" / "pod.json", json.dumps(SIGNAL))
    return {"daleobanks_root": str(d), "wmi_root": str(w), "signal": str(signal)}


def _ctx(tmp_path, read_roots, deliver=True, mission_id="m:organs-test"):
    return InvocationContext(workspace=tmp_path / "ws", read_roots=tuple(Path(r) for r in read_roots),
                             secrets=SecretBroker(tmp_path / "vault.json"), manifest=BUILTINS["organs.exchange"][0],
                             deliver_root=(tmp_path / "out") if deliver else None, mission_id=mission_id)


def test_binding_verdict_never_outruns_unevidenced_canonical_fields():
    assert ox.binding_verdict("go", ["pain_owner"], ["a claim"])[0] == "needs_more_evidence"
    assert ox.binding_verdict("go", [], [])[0] == "needs_more_evidence", "no evidence at all caps a go"
    assert ox.binding_verdict("kill", ["pain_owner"], [])[0] == "kill", "a lower verdict is never raised"
    assert ox.binding_verdict("go", [], ["a claim"])[0] == "go"


def test_exchange_verifies_both_legs_caps_the_engine_and_the_appraiser_reproduces_it(tmp_path, organs, monkeypatch):
    monkeypatch.setenv("GREG_TEST_SECRET", "must-not-reach-an-organ")
    ctx = _ctx(tmp_path, [tmp_path / "data"])
    out = ox.exchange(organs, ctx)
    assert out["engine_verdict"] == "go" and out["verdict"] == "needs_more_evidence"
    assert out["legs_verified"] == {"wealthmachine_verified_request": True, "daleobanks_verified_response": True}
    assert all(out["inputs"]["relay_checks"][leg]["passed"] for leg in ("request", "response"))
    assert out["inputs"]["acceptance"]["ledger_chain_ok"] and out["inputs"]["acceptance"]["ledger_entry"]["seq"] == 2
    assert out["authority_created"] is False and out["money_moved"] is False and out["external_contact"] is False
    packet = json.loads(out["inputs"]["request"]["body"])
    assert packet["audience"] == "" and packet["evidence"] == ["According to the broker, chargebacks take 40 days."]
    assert "pain_owner" in out["inputs"]["canonical"]["packet_unresolved"]
    memo = Path(out["path"])
    assert memo.parent == (tmp_path / "out" / "organs") and "**Binding verdict: needs_more_evidence**" in memo.read_text()
    assert "daleobanks -> wealthmachine" in memo.read_text() and "wealthmachine -> daleobanks" in memo.read_text()
    assert "WEALTHMACHINE_SIGNING_KEY" not in json.dumps(out), "the exchange key never enters the receipt"
    # the two organs kept their own state inside the mission workspace, not in their checkouts
    assert (tmp_path / "ws" / "organs" / "daleobanks" / "decision_ledger.jsonl").is_file()
    assert (tmp_path / "ws" / "organs" / "wealthmachine" / "bridge-state.jsonl").is_file()
    assert not list((tmp_path / "data" / "daleobanks").rglob("*.jsonl"))
    assert ox.status({"signal": organs["signal"]}, ctx) == {"exchanged": True, "verdict": "needs_more_evidence",
                                                             "path": memo.name, "signal_sha256": out["signal_sha256"]}
    ok, why = ox.verify_delivery(out, ctx.deliver_root)
    assert ok, why
    # a second exchange is a second memo with its own packet id and key, never an overwrite of the first
    again = ox.exchange(organs, ctx)
    assert again["path"] != out["path"] and again["packet_id"] != out["packet_id"]
    assert memo.read_bytes() == ox.render(out["inputs"]).encode() and ox.verify_delivery(again, ctx.deliver_root)[0]


def test_a_confined_exchange_organ_has_no_network_at_all(tmp_path):
    """#26 on the alternate exchange, as #169 did for the venture organs: on a confined body an organ runs in a
    namespace with no door. The probe that reaches a listener on the body's loopback unconfined reaches nothing
    confined and sees only lo, while its working directory (its own ledger and bridge state) stays writable."""
    import socket
    from tests.unit.test_greg_ventures import PROBE, _namespaces_or_skip
    _namespaces_or_skip()
    probe = PROBE.replace("print(json.dumps(", "open('wrote.txt', 'w').write('ok')\nprint(json.dumps(")
    listener = socket.create_server(("127.0.0.1", 0))
    port = str(listener.getsockname()[1])
    try:
        free = ox._organ(probe, {}, port, cwd=tmp_path / "free", env={})
        confined = ox._organ(probe, {}, port, cwd=tmp_path / "confined", env={}, confined=True)
    finally:
        listener.close()
    assert free["result"] == "REACHED"
    assert confined["result"] in ("ConnectionRefusedError", "OSError") and confined["interfaces"] == ["lo"]
    assert (tmp_path / "confined" / "wrote.txt").read_text() == "ok"


def test_a_confined_body_exchanges_and_its_appraiser_re_derives_inside_the_same_confinement(tmp_path, organs):
    """The whole exchange runs with no network on a confined body, the organs still keep their own state in the
    mission workspace, and the appraiser's re-run, confined as the exchange was, reproduces it."""
    from tests.unit.test_greg_ventures import _namespaces_or_skip
    _namespaces_or_skip()
    ctx = _ctx(tmp_path, [tmp_path / "data"])
    ctx.egress = object()                                    # a confined body: organs get no network at all
    out = ox.exchange(organs, ctx)
    assert out["engine_verdict"] == "go" and out["verdict"] == "needs_more_evidence"
    assert out["inputs"]["acceptance"]["ledger_chain_ok"]
    assert (tmp_path / "ws" / "organs" / "daleobanks" / "decision_ledger.jsonl").is_file()
    assert (tmp_path / "ws" / "organs" / "wealthmachine" / "bridge-state.jsonl").is_file()
    ok, why = ox.verify_delivery(out, ctx.deliver_root, confined=True)
    assert ok, why


def test_every_delivery_the_appraiser_re_derives_accepts_the_confinement_it_passes():
    """The appraiser passes ``confined`` to every verifier in DELIVERING (#26). A verifier that does not take it
    fails every appraisal of that capability: the merge of #169 left this module's verifier without it, and only
    the ten-step proof's organ step found it."""
    import importlib
    import inspect
    from greg.appraisal import DELIVERING
    for capability, module in DELIVERING.items():
        parameters = inspect.signature(importlib.import_module(module).verify_delivery).parameters
        assert "confined" in parameters, capability
        assert parameters["confined"].kind is inspect.Parameter.KEYWORD_ONLY, capability
        assert parameters["confined"].default is False, capability


def test_a_tampered_memo_or_receipt_is_refuted(tmp_path, organs):
    ctx = _ctx(tmp_path, [tmp_path / "data"])
    out = ox.exchange(organs, ctx)
    memo = Path(out["path"])
    memo.write_text(memo.read_text().replace("needs_more_evidence", "go"))
    ok, why = ox.verify_delivery(out, ctx.deliver_root)
    assert not ok and "differs from the render" in why
    memo.write_text(ox.render(out["inputs"]))
    forged = json.loads(json.dumps(out))
    forged["inputs"]["response"]["body"] = forged["inputs"]["response"]["body"].replace('"go_no_go":"go"', '"go_no_go":"kill"')
    ok, why = ox.verify_delivery(forged, ctx.deliver_root)
    assert not ok and "do not match their digest" in why
    assert not ox.verify_delivery({"path": out["path"]}, ctx.deliver_root)[0]


def test_relay_check_refuses_another_key_or_a_renamed_party(tmp_path, organs, monkeypatch):
    from adapters import bridge_transport as bt
    monkeypatch.setenv(bt.SIGNING_KEY_ENV, "key-a")
    body = b'{"id":"p1","schema_version":"1.1","created_at":"2026-10-15T00:00:00+00:00"}'
    headers = bt.build_headers(body, identity="daleobanks", schema_version="1.1", idempotency_key="p1",
                               recipient="wealthmachine", operation=ox.OPERATION)
    good = ox._relay_check("key-a", headers, body, direction="request", status="", request_digest="",
                           sender="daleobanks", recipient="wealthmachine")
    assert good["passed"]
    bad_key = ox._relay_check("key-b", headers, body, direction="request", status="", request_digest="",
                              sender="daleobanks", recipient="wealthmachine")
    assert not bad_key["passed"] and not bad_key["signature_under_exchange_key"]
    renamed = dict(headers, **{bt.H_RECIPIENT: "kernel"})
    assert not ox._relay_check("key-a", renamed, body, direction="request", status="", request_digest="",
                               sender="daleobanks", recipient="wealthmachine")["passed"]


def test_wealthmachine_refuses_a_forged_signature_and_a_replayed_envelope(tmp_path, organs):
    d, w = Path(organs["daleobanks_root"]), Path(organs["wmi_root"])
    key, anchor = "k" * 64, ox._anchor("m:replay")
    produced = ox._organ(ox._PRODUCER, {"signal": SIGNAL, "mission_id": "m:replay"}, str(d), str(ox.KERNEL_ROOT),
                         cwd=tmp_path / "d", env=ox._organ_env(key, extra={"LEDGER_PATH": str(tmp_path / "d.jsonl"),
                                                                           "RAW_VAULT_PATH": str(tmp_path / "v.jsonl")}))
    envelope = {"body": produced["body"], "headers": produced["headers"], "bridge_state": str(tmp_path / "w.jsonl"),
                "anchor": anchor, "legal_principal": "alfonso_lopez"}
    forged = json.loads(json.dumps(envelope))
    forged["headers"]["X-Signature"] = "0" * 64
    with pytest.raises(CapabilityError, match="signature verification failed"):
        ox._organ(ox._RECEIVER, forged, str(w), str(ox.KERNEL_ROOT), cwd=tmp_path / "w", env=ox._organ_env(key))
    first = ox._organ(ox._RECEIVER, envelope, str(w), str(ox.KERNEL_ROOT), cwd=tmp_path / "w", env=ox._organ_env(key))
    assert json.loads(first["body"])["opportunity_packet_id"] == produced["packet_id"]
    with pytest.raises(CapabilityError, match="nonce replay refused"):
        ox._organ(ox._RECEIVER, envelope, str(w), str(ox.KERNEL_ROOT), cwd=tmp_path / "w", env=ox._organ_env(key))
    with pytest.raises(CapabilityError, match="refused the envelope"):
        ox._organ(ox._RECEIVER, dict(envelope, bridge_state=str(tmp_path / "w2.jsonl")), str(w), str(ox.KERNEL_ROOT),
                  cwd=tmp_path / "w", env=ox._organ_env("another-key"))


def test_signal_and_roots_are_validated(tmp_path, organs):
    ctx = _ctx(tmp_path, [tmp_path / "data"])
    with pytest.raises(CapabilityError, match="missing parameter"):
        ox.exchange({"daleobanks_root": organs["daleobanks_root"]}, ctx)
    with pytest.raises(CapabilityError, match="outside permitted roots"):
        ox.exchange(dict(organs, signal="/etc/hostname"), ctx)
    bad = Path(organs["signal"]).with_name("bad.json")
    bad.write_text(json.dumps({"text": ""}))
    with pytest.raises(CapabilityError, match="non-empty 'text'"):
        ox.exchange(dict(organs, signal=str(bad)), ctx)
    with pytest.raises(CapabilityError, match="never UNIIMENTE"):
        ox.exchange(dict(organs, legal_principal="UNIIMENTE"), ctx)
    with pytest.raises(CapabilityError, match="no delivery root"):
        ox.exchange(organs, _ctx(tmp_path, [tmp_path / "data"], deliver=False))


def test_signed_mission_stops_at_approval_then_delivers_once_and_is_independently_appraised(tmp_path, organs):
    home, key, body_id, _ = make_body(tmp_path, read_roots=[tmp_path / "data"])
    spec = organ_exchange(**organs)
    assert spec["light_cone"]["max_consequence_class"] == "read_only" and spec["light_cone"]["budget_usd"] == 0
    drop(home, signed(key, body_id, "MISSION", spec))
    clock = Clock()
    with Body(home, clock=clock) as body:
        body.boot()
        body.tick()
        body.engine.book.rebuild()
        request = body.engine.book.open_requests()[0]
        assert request["kind"] == "APPROVAL" and request["authority_requested"]["capability"] == "organs.exchange"
    folder = home / "deliveries" / "organs"
    assert not folder.exists() or not list(folder.glob("*.md"))
    drop(home, signed(key, body_id, "DECISION", {"request_id": request["request_id"], "answer": "approve"}))
    with Body(home, clock=clock) as body:
        states = []
        for _ in range(4):
            clock.advance(30)
            states.append(body.tick()["missions"][0]["state"])
            if states[-1] == "ACHIEVED":
                break
        assert states[-1] == "ACHIEVED", states
        done = [e.payload for e in body.journal.replay("mission.action") if e.payload["status"] == "DONE"]
        assert len(done) == 1 and done[0]["capability"] == "organs.exchange"
        verdict = body.appraise(spec["mission_id"])
        assert verdict["verdict"] == "VERIFIED", verdict["findings"]
        assert verdict["checks"]["deliveries_bound_to_evidence"] is True
    assert len(list(folder.glob("exchange-*.md"))) == 1


@pytest.mark.skipif(not (os.environ.get("GREG_TEST_DALEOBANKS") and os.environ.get("GREG_TEST_WMI")),
                    reason="set GREG_TEST_DALEOBANKS and GREG_TEST_WMI to real organ checkouts")
def test_real_organs(tmp_path):
    d, w = Path(os.environ["GREG_TEST_DALEOBANKS"]), Path(os.environ["GREG_TEST_WMI"])
    signal = _write(tmp_path / "signals" / "pod.json", json.dumps(SIGNAL))
    ctx = _ctx(tmp_path, [d, w, tmp_path / "signals"])
    out = ox.exchange({"daleobanks_root": str(d), "wmi_root": str(w), "signal": str(signal)}, ctx)
    assert out["verdict"] == "needs_more_evidence" and out["legs_verified"]["daleobanks_verified_response"]
    assert out["inputs"]["organs"]["daleobanks_head"] and out["inputs"]["organs"]["wmi_head"]
    ok, detail = ox.verify_delivery(out, ctx.deliver_root)
    assert ok, detail
