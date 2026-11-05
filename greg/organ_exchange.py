"""Kernel-led authenticated exchange between two organ processes: DALEOBANKS -> WealthMachine -> DALEOBANKS.

    DALEOBANKS (public-voice organ)    turns one signal into a wire OpportunityPacket with its own
                                       sensing code and signs the envelope with the bridge transport
                                       (HMAC v2, identity daleobanks -> recipient wealthmachine)
      -> GREG relays                   checks the signature on the way through (an observation, not
                                       an authority), then hands the envelope to the second organ
      -> WealthMachine (venture organ) verifies the signature, validates the Kernel contract, claims
                                       the operation in its durable bridge state, runs its venture
                                       engine and signs the assessment back, bound to the request digest
      -> GREG relays                   checks the response signature on the way back
      -> DALEOBANKS                    verifies the response, validates the assessment contract and
                                       records the exchange in its own hash-chained decision ledger
      -> Kernel adapters               canonical packet and assessment; fields no organ evidenced stay
                                       unresolved, never invented
      -> one memo                      delivered to Alfonso; nothing is executed, sent or published

Each organ runs from its own checkout in a separate interpreter with no GREG key, ledger or secret.
The one shared material is a bridge key GREG mints for this exchange alone and hands to both organs
through their own protocol's configuration (``WEALTHMACHINE_SIGNING_KEY``); the ledger retains its
fingerprint, never the key. HMAC proves possession of that key, not identity or authority
(``adapters/bridge_transport.py``); a fresh key per exchange means an envelope from one exchange cannot
verify in another. The authority boundary stays the Kernel's: the assessment is a recommendation
(``requires_human_approval`` is non-negotiable on both organ sides), the evidence rule of
``greg.ventures`` applies (a score may not outrun missing evidence), and delivery stops at the founder's
approval unless signed into the cone.

Capabilities:
  ``organs.exchange``         internal_write (deliver:): one signed exchange, one memo
  ``organs.exchange_status``  read_only sensor: has a memo been delivered for this signal
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

from greg.capabilities import CapabilityError, InvocationContext, _inside
from greg.ventures import _git_head

KERNEL_ROOT = Path(__file__).resolve().parents[1]
RENDERER = "greg.organ_exchange/one-greg-1"
OPERATION = "opportunity.evaluate"
ORGAN_TIMEOUT_SECONDS = 90
DEFAULT_LEGAL_PRINCIPAL = "alfonso_lopez"       # authority/legal-principals.yaml: organ effects attach here
VOLATILE_PACKET_FIELDS = ("id", "created_at", "source_ref")   # fresh on every DALEOBANKS run (uuid, clock, vault id)
STABLE_ASSESSMENT = ("go_no_go", "opportunity_score", "market_alignment", "risk_level", "reasons", "cases",
                     "validation_plan", "recommended_next_action", "requires_human_approval")

# --- organ scripts: each runs inside the organ's own interpreter, on the organ's own modules -------------

_PRODUCER = r'''
import hashlib, json, logging, sys
logging.disable(logging.CRITICAL)
sys.path.insert(0, sys.argv[1]); sys.path.append(sys.argv[2])
from services.context_packet import build_packet
from db.models import OpportunityPacket
from services.venture_protocol import ALLOWED_SIGNAL_TYPES, SCHEMA_VERSION, packet_to_wire
from services.bridge_security import build_headers
from services.ledger import get_ledger
req = json.load(sys.stdin)
sig = req["signal"]
cp = build_packet(source=str(sig.get("source") or "operator"), raw_ref=str(sig.get("raw_ref", "")),
                  text=str(sig["text"]), topic=sig.get("topic"), trust="untrusted")
claims = [str(c) for c in cp.claims]
signal_type = str(sig.get("signal_type") or "operator_thought")
if signal_type not in ALLOWED_SIGNAL_TYPES:
    raise SystemExit(f"signal_type {signal_type!r} is not allowed by DALEOBANKS")
flags = []
if cp.risk >= 0.5:
    flags.append(f"injection_risk:{cp.risk}")
if cp.evidence_needed:
    flags.append("evidence_needed: claims without a cited source")
packet = OpportunityPacket(
    source="daleobanks", source_ref=str(cp.provenance.get("vault_id") or hashlib.sha256(cp.text.encode()).hexdigest()),
    signal_type=signal_type, observed_pain=str(cp.human_cost or cp.system_failure or cp.text)[:600],
    core_thesis=(claims[0] if claims else cp.text)[:600],
    audience=str(sig.get("audience", "")), buyer_type=str(sig.get("buyer_type", "")),
    urgency={"high": "high", "medium": "medium"}.get(cp.stakes, "low"), evidence=claims,
    possible_offer=str(sig.get("possible_offer", "")), monetization_paths=[], risk_flags=flags,
    smallest_validation_action=(("Find one independent source for: " + claims[0][:160]) if claims
                                else "Ask one named buyer whether this pain is real"),
    confidence=float(cp.confidence))
wire = packet_to_wire(packet)   # DALEOBANKS validates against the Kernel contract before anything leaves
body = json.dumps(wire, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")
headers = build_headers(body, identity="daleobanks", schema_version=SCHEMA_VERSION, idempotency_key=packet.id,
                        trace_id=req["mission_id"], recipient="wealthmachine", operation="opportunity.evaluate")
entry = get_ledger().record("venture_packet_signed", {"packet_id": packet.id, "trace_id": req["mission_id"],
                                                     "recipient": "wealthmachine",
                                                     "body_sha256": hashlib.sha256(body).hexdigest()})
print(json.dumps({"body": body.decode("ascii"), "headers": headers, "packet_id": packet.id,
                  "sensing": {"stakes": cp.stakes, "risk": cp.risk, "claims": claims,
                              "evidence_needed": bool(cp.evidence_needed),
                              "injection_patterns": list(cp.provenance.get("injection_patterns", []))},
                  "ledger_entry": {"seq": entry["seq"], "hash": entry["hash"]}}, sort_keys=True))
'''

_RECEIVER = r'''
import json, logging, sys
logging.disable(logging.CRITICAL)
sys.path.insert(0, sys.argv[1]); sys.path.append(sys.argv[2])
from adapters.bridge_transport import BridgeSecurityError, body_digest, build_headers, verify_headers
from adapters.contract_validation import strict_json, validate_contract
from events.bridge_state import BridgeState
from src.services.opportunity_intake import OpportunityIntakeService
req = json.load(sys.stdin)
raw = req["body"].encode("ascii")
state = BridgeState(req["bridge_state"], req["anchor"], owner="wealthmachine", legal_principal=req["legal_principal"])
try:
    transport = verify_headers(req["headers"], raw, nonce_cache=state, require_signature=True,
                               expected_sender="daleobanks", expected_recipient="wealthmachine",
                               expected_operation="opportunity.evaluate")
except BridgeSecurityError as exc:
    raise SystemExit("wealthmachine refused the envelope: " + str(exc))
payload = strict_json(raw)
validate_contract(payload, "wire-opportunity-packet")
if payload["schema_version"] != transport["schema_version"]:
    raise SystemExit("body/header contract version mismatch")
identity, claim = state.begin(caller="daleobanks", operation="opportunity.evaluate",
                              key=transport["idempotency_key"], body_digest=body_digest(raw))
if claim["state"] == "completed":
    assessment = claim["result"]
elif claim["state"] != "claimed":
    raise SystemExit("operation state " + str(claim["state"]))
else:
    try:
        assessment = OpportunityIntakeService().evaluate_packet(payload)
        assessment["schema_version"] = payload["schema_version"]
        validate_contract(assessment, "wire-venture-assessment")
        state.finish(identity, assessment)
    except Exception as exc:
        state.abandon(identity)
        raise SystemExit("engine failed; claim abandoned, no blind retry: " + type(exc).__name__)
body = json.dumps(assessment, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("ascii")
headers = build_headers(body, identity="wealthmachine", schema_version=assessment["schema_version"],
                        idempotency_key=transport["idempotency_key"], recipient="daleobanks",
                        operation="opportunity.evaluate", direction="response", status="200",
                        request_digest=body_digest(raw), trace_id=transport.get("trace_id", ""))
state.close()
print(json.dumps({"body": body.decode("ascii"), "headers": headers,
                  "transport": {k: transport[k] for k in ("identity", "recipient", "operation", "idempotency_key",
                                                           "schema_version", "body_digest")}}, sort_keys=True))
'''

_ACCEPTOR = r'''
import json, logging, sys
logging.disable(logging.CRITICAL)
sys.path.insert(0, sys.argv[1]); sys.path.append(sys.argv[2])
from services.bridge_security import BridgeSecurityError, body_digest, verify_headers
from services.venture_protocol import SCHEMA_VERSION, validate_assessment_wire
from services.ledger import DecisionLedger, get_ledger
from adapters.contract_validation import strict_json
from events.bridge_state import BridgeState
req = json.load(sys.stdin)
raw, request_raw = req["response_body"].encode("ascii"), req["request_body"].encode("ascii")
state = BridgeState(req["bridge_state"], req["anchor"], owner="daleobanks", legal_principal=req["legal_principal"])
try:
    transport = verify_headers(req["response_headers"], raw, nonce_cache=state, expected_sender="wealthmachine",
                               expected_recipient="daleobanks", expected_operation="opportunity.evaluate",
                               request_digest=body_digest(request_raw), direction="response", status="200")
except BridgeSecurityError as exc:
    raise SystemExit("daleobanks refused the response: " + str(exc))
finally:
    state.close()
if transport["idempotency_key"] != req["packet_id"] or transport["schema_version"] != SCHEMA_VERSION:
    raise SystemExit("response logical key or version mismatch")
payload = strict_json(raw)
validate_assessment_wire(payload)
if payload["opportunity_packet_id"] != req["packet_id"] or payload["schema_version"] != SCHEMA_VERSION:
    raise SystemExit("response refers to another packet/version")
ledger = get_ledger()
entry = ledger.record("venture_assessment", {"packet_id": req["packet_id"], "go_no_go": payload["go_no_go"],
                                             "score": payload.get("opportunity_score"), "mode": "kernel-relay"})
ok = DecisionLedger(ledger.path).verify_chain()
print(json.dumps({"accepted": True, "go_no_go": payload["go_no_go"], "requires_human_approval": True,
                  "ledger_entry": {"seq": entry["seq"], "hash": entry["hash"]},
                  "ledger_chain_ok": ok if isinstance(ok, bool) else bool(ok[0])}, sort_keys=True))
'''

_ENGINE_ONLY = r'''
import json, logging, sys
logging.disable(logging.CRITICAL)
sys.path.insert(0, sys.argv[1]); sys.path.append(sys.argv[2])
from src.services.opportunity_intake import OpportunityIntakeService
print(json.dumps(OpportunityIntakeService().evaluate_packet(json.load(sys.stdin)), sort_keys=True, default=str))
'''


def _organ(script: str, stdin: dict, *args: str, cwd: Path, env: dict, confined: bool = False) -> dict:
    """Run one organ in its own process; stderr's last line is the organ's own reason for refusing.

    ``confined`` (a body with confined egress, #26, as ``greg.ventures`` does): the exchange needs no network, so
    the organ runs in a bubblewrap network namespace with no door at all. Its checkouts are read-only; its working
    directory, where it keeps its own ledger and bridge state, stays writable. Without namespaces nothing runs."""
    cwd.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="greg-organ-pyc-") as pycache:
        full = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONHASHSEED": "0", "LANG": "C.UTF-8",
                "HOME": str(cwd), "PYTHONPYCACHEPREFIX": pycache, **env}
        argv = [sys.executable, "-s", "-c", script, *args]
        if confined:
            from foundry.systems.relay_door import namespace_argv
            from greg.worker_isolation import WorkerIsolationError, _backend
            try:
                _backend(require_bubblewrap=True)
            except WorkerIsolationError as exc:
                raise CapabilityError(f"confined egress needs bubblewrap network namespaces here: {exc}") from None
            argv = namespace_argv(writable=[pycache, cwd], readonly=[a for a in args if Path(a).is_absolute()],
                                  chdir=cwd) + argv
        try:
            done = subprocess.run(argv, input=json.dumps(stdin),
                                  capture_output=True, text=True, timeout=ORGAN_TIMEOUT_SECONDS, cwd=cwd, env=full)
        except subprocess.TimeoutExpired:
            raise CapabilityError(f"organ timed out after {ORGAN_TIMEOUT_SECONDS}s") from None
    if done.returncode != 0:
        tail = done.stderr.strip().splitlines()
        raise CapabilityError("organ refused: " + (tail[-1] if tail else str(done.returncode)))
    return json.loads(done.stdout)


def _relay_check(key: str, headers: dict, body: bytes, *, direction: str, status: str, request_digest: str,
                 sender: str, recipient: str) -> dict:
    """GREG's observation of a leg it carries: the envelope is signed under this exchange's key and names the
    parties it claims. Non-authoritative; each organ verifies for itself with its own replay state."""
    from adapters import bridge_transport as bt
    lower = {k.lower(): v for k, v in headers.items()}
    get = lambda name: lower.get(name.lower(), "")
    expected = bt.sign(key, get(bt.H_IDENTITY), get(bt.H_TIMESTAMP), get(bt.H_NONCE), get(bt.H_IDEMPOTENCY),
                       get(bt.H_SCHEMA), body, recipient=get(bt.H_RECIPIENT), operation=get(bt.H_OPERATION),
                       request_digest=get(bt.H_REQUEST), direction=get(bt.H_DIRECTION), status=get(bt.H_STATUS),
                       trace_id=get(bt.H_TRACE))
    signature = get(bt.H_SIGNATURE)
    verdict = {"signature_under_exchange_key": bool(signature) and hmac.compare_digest(signature, expected),
               "sender": get(bt.H_IDENTITY) == sender, "recipient": get(bt.H_RECIPIENT) == recipient,
               "operation": get(bt.H_OPERATION) == OPERATION, "direction": get(bt.H_DIRECTION) == direction,
               "status": get(bt.H_STATUS) == status, "request_digest": get(bt.H_REQUEST) == request_digest,
               "body_digest_matches": True}
    verdict["passed"] = all(verdict.values())
    return verdict


def _paths(params: dict, ctx: InvocationContext) -> dict:
    try:
        roots = {k: _inside(Path(params[k]), ctx.read_roots) for k in ("daleobanks_root", "wmi_root", "signal")}
    except KeyError as exc:
        raise CapabilityError(f"missing parameter {exc}") from None
    if not (roots["daleobanks_root"] / "services" / "venture_protocol.py").is_file():
        raise CapabilityError("daleobanks_root is not a DALEOBANKS checkout with the venture protocol")
    if not (roots["wmi_root"] / "src" / "services" / "opportunity_intake.py").is_file():
        raise CapabilityError("wmi_root is not a WealthMachineIntelligence checkout")
    if not roots["signal"].is_file():
        raise CapabilityError("signal must be a JSON file inside a read root")
    return roots


def _signal(path: Path) -> tuple[dict, str]:
    raw = path.read_bytes()
    try:
        signal = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CapabilityError(f"signal is not JSON: {exc}") from None
    if not isinstance(signal, dict) or not isinstance(signal.get("text"), str) or not signal["text"].strip():
        raise CapabilityError("signal needs a non-empty 'text'")
    if len(signal["text"]) > 8000:
        raise CapabilityError("signal text exceeds 8000 characters")
    return signal, hashlib.sha256(raw).hexdigest()


def _anchor(mission_id: str) -> str:
    """Anchor for the organs' per-exchange bridge state: this exchange's identity, not the constitution hash.
    The state is disposable with the mission workspace and never admits anything to the Kernel ledger."""
    return hashlib.sha256(("greg.organ_exchange:" + mission_id).encode()).hexdigest()


def binding_verdict(engine_verdict: str, unresolved: list[str], evidence: list[str]) -> tuple[str, str]:
    """A score may not outrun missing evidence (the same rule the venture memo applies)."""
    from adapters.daleobanks_opportunity import justified_verdict
    return justified_verdict(engine_verdict, unresolved, evidence)


def _canonical(packet: dict, assessment: dict) -> dict:
    from adapters import daleobanks_opportunity, wealthmachine_assessment
    try:
        packet_result = daleobanks_opportunity.adapt(packet, transport_identity="daleobanks")
        canonical_assessment = wealthmachine_assessment.adapt(assessment, transport_identity="wealthmachine")
    except daleobanks_opportunity.AdapterError as exc:
        raise CapabilityError(f"organ output violates the kernel contract: {exc}") from None
    return {"packet_unresolved": list(packet_result.unresolved), "packet_resolved": packet_result.resolved,
            "assessment_verdict": canonical_assessment["verdict"],
            "assessment_execution_authority": canonical_assessment["execution_authority"],
            "assessment_requires_human_approval": canonical_assessment["requires_human_approval"]}


def normalized_packet(packet: dict) -> dict:
    return {k: v for k, v in packet.items() if k not in VOLATILE_PACKET_FIELDS}


def render(inputs: dict) -> str:
    packet, assessment = json.loads(inputs["request"]["body"]), json.loads(inputs["response"]["body"])
    v, relay = inputs["binding"], inputs["relay_checks"]
    lines = [f"# Organ exchange — {inputs['signal'].get('topic') or packet['core_thesis'][:80]}", "",
             f"**Binding verdict: {v['verdict']}** — {v['why']}.", "",
             f"- DALEOBANKS (sensing): stakes {inputs['sensing']['stakes']}, injection risk {inputs['sensing']['risk']}, "
             f"{len(inputs['sensing']['claims'])} claim(s) extracted, evidence needed: {inputs['sensing']['evidence_needed']}",
             f"- WealthMachine (venture engine): **{assessment['go_no_go']}**, opportunity score "
             f"{assessment.get('opportunity_score')}, market alignment {assessment.get('market_alignment')}, risk "
             f"{assessment.get('risk_level')}",
             "- Requires your approval: yes. GREG executed nothing beyond reading the signal and running both organs.",
             "", "## Authenticated exchange (HMAC v2 bridge transport, one key minted for this exchange)", "",
             "| leg | sender -> recipient | operation | logical key | body sha256 | verified by |", "|---|---|---|---|---|---|",
             f"| request | daleobanks -> wealthmachine | {OPERATION} | `{packet['id']}` | `{inputs['request']['body_sha256'][:16]}…` | "
             f"wealthmachine (own bridge state); GREG relay check {'passed' if relay['request']['passed'] else 'FAILED'} |",
             f"| response | wealthmachine -> daleobanks | {OPERATION} | `{packet['id']}` | `{inputs['response']['body_sha256'][:16]}…` | "
             f"daleobanks (own bridge state, ledger seq {inputs['acceptance']['ledger_entry']['seq']}); GREG relay check "
             f"{'passed' if relay['response']['passed'] else 'FAILED'} |",
             "", f"Key fingerprint `{inputs['key_fingerprint'][:16]}…` (the key itself is not retained). HMAC proves possession "
             "of this exchange's key, not identity or authority.", "",
             "## What is not evidenced", ""]
    lines += [f"- canonical packet fields unresolved: {', '.join(inputs['canonical']['packet_unresolved']) or 'none'}"]
    lines += [f"- {f}" for f in packet.get("risk_flags", [])] or ["- no risk flags from DALEOBANKS sensing"]
    lines += ["", "## Evidence DALEOBANKS extracted (claims, not independently verified)", ""]
    lines += [f"- {c}" for c in packet.get("evidence", [])] or ["- none"]
    lines += ["", "## Venture engine reasoning", ""] + [f"- {r}" for r in assessment.get("reasons", [])]
    lines += ["", "## Adversarial committee", ""] + [f"- {c.get('case')} ({c.get('stance')}, {c.get('severity')}): {c.get('argument')}"
                                                  for c in assessment.get("cases", [])]
    lines += ["", "## Validation plan (proposed, not executed)", ""] + [f"1. {s}" for s in assessment.get("validation_plan", [])]
    lines += ["", f"Smallest validation action named by DALEOBANKS: {packet.get('smallest_validation_action')}", "",
              "## Provenance", "",
              f"- Signal sha256 `{inputs['signal_sha256']}`; mission `{inputs['mission_id']}`",
              f"- DALEOBANKS at `{inputs['organs']['daleobanks_head']}` (decision ledger entries "
              f"{inputs['producer_ledger_entry']['seq']} and {inputs['acceptance']['ledger_entry']['seq']}, chain "
              f"{'intact' if inputs['acceptance']['ledger_chain_ok'] else 'BROKEN'})",
              f"- WealthMachine at `{inputs['organs']['wmi_head']}`",
              f"- Canonical adapters: packet under the daleobanks identity, assessment under the wealthmachine identity; "
              f"execution authority {inputs['canonical']['assessment_execution_authority']}",
              f"- Renderer {RENDERER}", ""]
    return "\n".join(lines)


def inputs_digest(inputs: dict) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _deliver(text: str, ctx: InvocationContext, name: str) -> Path:
    if ctx.deliver_root is None:
        raise CapabilityError("this body has no delivery root configured")
    folder = Path(ctx.deliver_root).resolve() / "organs"
    folder.mkdir(parents=True, exist_ok=True)
    target, data = folder / f"{name}.md", text.encode("utf-8")
    if target.exists():
        if target.read_bytes() == data:
            return target
        raise CapabilityError(f"a different memo already exists at {target.name}; nothing overwritten")
    temporary = folder / f".{target.name}.{os.getpid()}.tmp"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.link(temporary, target)
    temporary.unlink()
    return target


def _organ_env(key: str, *, extra: dict | None = None) -> dict:
    return {"WEALTHMACHINE_SIGNING_KEY": key, **(extra or {})}


def exchange(params: dict, ctx: InvocationContext) -> dict:
    if ctx.deliver_root is None:
        raise CapabilityError("this body has no delivery root configured")
    p = _paths(params, ctx)
    signal, signal_sha256 = _signal(p["signal"])
    principal = str(params.get("legal_principal") or DEFAULT_LEGAL_PRINCIPAL)
    if principal == "UNIIMENTE" or not principal.strip():
        raise CapabilityError("an accountable legal principal is required; never UNIIMENTE")
    mission_id = ctx.mission_id or "m:organ-exchange"
    anchor = _anchor(mission_id)
    key = secrets.token_hex(32)                       # minted for this exchange; retained only as a fingerprint
    fingerprint = hashlib.sha256(key.encode()).hexdigest()
    base = ctx.workspace / "organs"
    d_home, w_home = base / "daleobanks", base / "wealthmachine"
    confined = ctx.egress is not None                 # #26: on a confined body the organs get no network at all
    d_env = _organ_env(key, extra={"LEDGER_PATH": str(d_home / "decision_ledger.jsonl"),
                                   "RAW_VAULT_PATH": str(d_home / "raw_vault.jsonl")})
    produced = _organ(_PRODUCER, {"signal": signal, "mission_id": mission_id}, str(p["daleobanks_root"]),
                      str(KERNEL_ROOT), cwd=d_home, env=d_env, confined=confined)
    request_body = produced["body"].encode("ascii")
    request_check = _relay_check(key, produced["headers"], request_body, direction="request", status="",
                                 request_digest="", sender="daleobanks", recipient="wealthmachine")
    if not request_check["passed"]:
        raise CapabilityError(f"DALEOBANKS envelope failed the relay check: {request_check}")
    received = _organ(_RECEIVER, {"body": produced["body"], "headers": produced["headers"],
                                  "bridge_state": str(w_home / "bridge-state.jsonl"), "anchor": anchor,
                                  "legal_principal": principal},
                      str(p["wmi_root"]), str(KERNEL_ROOT), cwd=w_home, env=_organ_env(key), confined=confined)
    response_body = received["body"].encode("ascii")
    response_check = _relay_check(key, received["headers"], response_body, direction="response", status="200",
                                  request_digest=hashlib.sha256(request_body).hexdigest(),
                                  sender="wealthmachine", recipient="daleobanks")
    if not response_check["passed"]:
        raise CapabilityError(f"WealthMachine envelope failed the relay check: {response_check}")
    accepted = _organ(_ACCEPTOR, {"request_body": produced["body"], "response_body": received["body"],
                                  "response_headers": received["headers"], "packet_id": produced["packet_id"],
                                  "bridge_state": str(d_home / "bridge-state.jsonl"), "anchor": anchor,
                                  "legal_principal": principal},
                      str(p["daleobanks_root"]), str(KERNEL_ROOT), cwd=d_home, env=d_env, confined=confined)
    packet, assessment = json.loads(produced["body"]), json.loads(received["body"])
    canonical = _canonical(packet, assessment)
    verdict, why = binding_verdict(assessment["go_no_go"], canonical["packet_unresolved"], packet.get("evidence", []))
    inputs = {"renderer": RENDERER, "mission_id": mission_id, "signal": signal, "signal_sha256": signal_sha256,
              "key_fingerprint": fingerprint, "legal_principal": principal,
              "request": {"body": produced["body"], "headers": produced["headers"],
                          "body_sha256": hashlib.sha256(request_body).hexdigest()},
              "response": {"body": received["body"], "headers": received["headers"],
                           "body_sha256": hashlib.sha256(response_body).hexdigest(),
                           "transport_as_verified_by_wealthmachine": received["transport"]},
              "relay_checks": {"request": request_check, "response": response_check},
              "sensing": produced["sensing"], "producer_ledger_entry": produced["ledger_entry"],
              "acceptance": accepted, "canonical": canonical, "binding": {"verdict": verdict, "why": why},
              "organs": {"daleobanks_head": _git_head(p["daleobanks_root"]), "wmi_head": _git_head(p["wmi_root"])},
              "paths": {k: str(v) for k, v in p.items()}}
    text = render(inputs)
    # One memo per exchange that actually happened: a re-run after an uncertain attempt is a second exchange with
    # its own packet id, nonces and key, never an overwrite of the first (write-once stays in _deliver).
    path = _deliver(text, ctx, f"exchange-{signal_sha256[:16]}-{produced['packet_id'][:8]}")
    return {"path": str(path), "sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text.encode()),
            "inputs": inputs, "inputs_digest": inputs_digest(inputs), "verdict": verdict,
            "engine_verdict": assessment["go_no_go"], "packet_id": produced["packet_id"],
            "signal_sha256": signal_sha256, "legs_verified": {"wealthmachine_verified_request": True,
                                                              "daleobanks_verified_response": bool(accepted["accepted"])},
            "authority_created": False, "money_moved": False, "external_contact": False}


def status(params: dict, ctx: InvocationContext) -> dict:
    """Sensor: has a memo been delivered for this exact signal file?"""
    signal = _inside(Path(params["signal"]), ctx.read_roots)
    digest = hashlib.sha256(signal.read_bytes()).hexdigest()
    folder = Path(ctx.deliver_root).resolve() / "organs" if ctx.deliver_root else None
    found = sorted(folder.glob("exchange-*.md")) if folder and folder.is_dir() else []
    marker = f"Signal sha256 `{digest}`"
    for path in found:
        text = path.read_text(encoding="utf-8")
        if marker in text:
            verdict = text.split("**Binding verdict: ", 1)[1].split("**", 1)[0]
            return {"exchanged": True, "verdict": verdict, "path": path.name, "signal_sha256": digest}
    return {"exchanged": False, "verdict": None, "path": None, "signal_sha256": digest}


def verify_delivery(output: dict, deliver_root: Path | None, ledger=None, *, confined: bool = False) -> tuple[bool, str]:
    """Appraiser (separate process, no key): the memo is the render of its receipt; both bodies satisfy the
    Kernel contracts; the envelopes name the parties and digests they claim; the venture engine reproduces the
    assessment; DALEOBANKS reproduces the packet's content from the same signal. On a confined body (#26) the
    organ re-runs are as confined as the exchange was."""
    if not isinstance(output, dict) or "inputs" not in output:
        return False, "receipt does not retain the exchange inputs"
    inputs = output["inputs"]
    if inputs.get("renderer") != RENDERER:
        return False, f"exchanged by {inputs.get('renderer')}; this appraiser re-derives {RENDERER} only"
    if inputs_digest(inputs) != output.get("inputs_digest"):
        return False, "retained inputs do not match their digest"
    expected = render(inputs).encode("utf-8")
    path = Path(output["path"])
    if hashlib.sha256(expected).hexdigest() != output.get("sha256"):
        return False, "receipt digest is not the render of its inputs"
    if deliver_root is None or Path(deliver_root).resolve() not in path.resolve().parents:
        return False, "delivered memo is outside the delivery root"
    if not path.is_file() or path.read_bytes() != expected:
        return False, "delivered memo differs from the render of the receipted inputs"
    try:
        from adapters import bridge_transport as bt
        from adapters.contract_validation import validate_contract
        request_body, response_body = inputs["request"]["body"].encode("ascii"), inputs["response"]["body"].encode("ascii")
        if hashlib.sha256(request_body).hexdigest() != inputs["request"]["body_sha256"] or \
                hashlib.sha256(response_body).hexdigest() != inputs["response"]["body_sha256"]:
            return False, "retained envelope bodies do not match their digests"
        packet, assessment = json.loads(request_body), json.loads(response_body)
        validate_contract(packet, "wire-opportunity-packet")
        validate_contract(assessment, "wire-venture-assessment")
        rq, rs = inputs["request"]["headers"], inputs["response"]["headers"]
        lower = lambda h: {k.lower(): v for k, v in h.items()}
        rql, rsl = lower(rq), lower(rs)
        g = lambda h, n: h.get(n.lower(), "")
        if not (g(rql, bt.H_IDENTITY) == "daleobanks" and g(rql, bt.H_RECIPIENT) == "wealthmachine"
                and g(rql, bt.H_OPERATION) == OPERATION and g(rql, bt.H_IDEMPOTENCY) == packet["id"]
                and g(rql, bt.H_DIRECTION) == "request" and len(g(rql, bt.H_SIGNATURE)) == 64):
            return False, "request envelope does not name daleobanks -> wealthmachine for this packet"
        if not (g(rsl, bt.H_IDENTITY) == "wealthmachine" and g(rsl, bt.H_RECIPIENT) == "daleobanks"
                and g(rsl, bt.H_DIRECTION) == "response" and g(rsl, bt.H_STATUS) == "200"
                and g(rsl, bt.H_REQUEST) == inputs["request"]["body_sha256"]
                and g(rsl, bt.H_IDEMPOTENCY) == packet["id"] and len(g(rsl, bt.H_SIGNATURE)) == 64):
            return False, "response envelope is not bound to the request it answers"
        if assessment["opportunity_packet_id"] != packet["id"] or not assessment["requires_human_approval"]:
            return False, "assessment does not answer this packet or drops human approval"
        if not all(inputs["relay_checks"][leg]["passed"] for leg in ("request", "response")):
            return False, "a relay check recorded as failed"
        if not inputs["acceptance"].get("accepted") or not inputs["acceptance"].get("ledger_chain_ok"):
            return False, "DALEOBANKS did not accept the response or its ledger chain is broken"
        canonical = _canonical(packet, assessment)
        if canonical["packet_unresolved"] != inputs["canonical"]["packet_unresolved"]:
            return False, "canonical unresolved fields are not the adapters' result"
        if binding_verdict(assessment["go_no_go"], canonical["packet_unresolved"], packet.get("evidence", []))[0] \
                != inputs["binding"]["verdict"]:
            return False, "binding verdict is not the evidence rule applied to the organ outputs"
        paths = {k: Path(v) for k, v in inputs["paths"].items()}
        signal_raw = paths["signal"].read_bytes()
        if hashlib.sha256(signal_raw).hexdigest() != inputs["signal_sha256"]:
            return False, "the signal changed since the exchange"
        with tempfile.TemporaryDirectory(prefix="greg-organ-appraisal-") as scratch:
            scratch = Path(scratch)
            again = _organ(_PRODUCER, {"signal": json.loads(signal_raw.decode("utf-8")), "mission_id": inputs["mission_id"]},
                           str(paths["daleobanks_root"]), str(KERNEL_ROOT), cwd=scratch / "daleobanks",
                           env=_organ_env(secrets.token_hex(32), extra={"LEDGER_PATH": str(scratch / "d.jsonl"),
                                                                        "RAW_VAULT_PATH": str(scratch / "v.jsonl")}),
                           confined=confined)
            if normalized_packet(json.loads(again["body"])) != normalized_packet(packet):
                return False, "DALEOBANKS does not reproduce the receipted packet from the same signal"
            engine = _organ(_ENGINE_ONLY, packet, str(paths["wmi_root"]), str(KERNEL_ROOT), cwd=scratch / "wealthmachine",
                            env={}, confined=confined)
    except (CapabilityError, OSError, ValueError, KeyError) as exc:
        return False, f"organ re-run failed: {type(exc).__name__}: {exc}"
    if any(engine.get(k) != assessment.get(k) for k in STABLE_ASSESSMENT):
        return False, "WealthMachine does not reproduce the receipted assessment"
    return True, "memo equals the render of the receipt; both envelopes bound and verified; both organs reproduce it"
