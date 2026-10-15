"""Organ exchange on the mission path: DALEOBANKS -> WealthMachine over the signed bridge.

Until now the signed organ exchange ran only from a script (``scripts/organ_bridge_live.py``,
#171). A mission could not use it, so no mission's authority, receipts, appraisal or
Mission Control trace ever included an organ. This module puts the same mechanism behind
two governed capabilities; it adds no transport, no ledger and no authority:

``organ.exchange`` (internal_write, target ``organ:daleobanks-wealthmachine``)
    1. DALEOBANKS runs its own ``IdeaRefinery`` on the seed text, in its own checkout and
       interpreter, and signs the resulting OpportunityPacket (``adapters/bridge_transport``).
    2. WealthMachine, in its own checkout and interpreter, verifies that message and
       answers with a signed VentureAssessment bound to the request digest.
    3. GREG verifies both messages at the kernel, retains each body as untrusted content
       and binds both to this mission's one trace (``greg.organ_bridge``).
    4. A second WealthMachine process re-derives the assessment from the same packet;
       agreement is recorded as ``organ.appraised: REPRODUCED``, never VERIFIED.

    Each organ runs from a snapshot of its committed HEAD (``git archive``), so the recorded
    head is the code that ran; uncommitted edits in a founder checkout are reported, never used.
    The organ processes share the body's UID and filesystem (no OS confinement beyond network
    denial), so DALEOBANKS could rewrite WealthMachine's code: the WealthMachine snapshot's
    digest is taken before DALEOBANKS runs and re-checked before each WealthMachine stage. The
    re-derivation is a separate process, not an independent organization or machine.

    Both organ processes run with a scrubbed environment and the OS network denial used for
    every other GREG subprocess (``run_isolated``); their stores live in the mission
    workspace. A per-invocation signing key is generated, passed only through the child
    environment and never written. The organs pin ``uniimente-kernel-boundaries`` at 4999acff,
    whose transport has one shared key, so ``sender_identity_isolated`` is reported false:
    the exchange authenticates a key holder, not a specific organ (#174 explains the upgrade).

``organ.status`` (read_only sensor, retry-safe)
    Re-reads this mission's organ facts from the journal: which organs were observed, whether
    every message was transport-verified, and the latest organ appraisal verdict. Only facts a
    DONE ``organ.exchange`` receipt (or a founder reconciliation) stands behind count
    (``organ_bridge.bound_facts``); facts left by a dispatch that never completed do not.

Nothing here contacts anyone, publishes, spends or decides. A signed organ message is
evidence about an organ's computation; it is not a Kernel consequence and grants nothing.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import secrets as _secrets
import subprocess
import tempfile
import time

from adapters import bridge_transport as bt
from greg import isolation, organ_bridge
from adapters.contract_validation import validate_contract
from greg.capabilities import CapabilityError, InvocationContext, _inside, run_isolated
from events.spine import EventError
from greg.workers import WorkerInterrupted, _tree_digest

PAIR = "daleobanks-wealthmachine"
TARGET = "organ:" + PAIR
MAX_SEED = 2000

DALEOBANKS_STAGE = r'''
import asyncio, json, sys
from adapters import bridge_transport as bt
from db.session import get_db_session, init_db
from services.idea_refinery import IdeaRefinery
from services.venture_protocol import packet_to_wire
init_db()
refinery = IdeaRefinery()
with get_db_session() as session:
    idea = refinery.intake(session, sys.argv[1])
    result = asyncio.run(refinery.refine(session, idea))
if result.get("opportunity") is None:   # the organ's own judgment: nothing to evaluate
    print(json.dumps({"no_opportunity": True, "refined": {k: str(v)[:300] for k, v in result.items()
                                                          if k != "opportunity"}}))
    raise SystemExit(0)
wire = packet_to_wire(result["opportunity"])
body = json.dumps(wire, sort_keys=True).encode()
headers = bt.build_headers(body, identity="daleobanks", schema_version=wire.get("schema_version", "1.1"),
                           idempotency_key=wire["id"], trace_id=sys.argv[2])
print(json.dumps({"body": body.decode(), "headers": headers}))
'''

WEALTHMACHINE_STAGE = r'''
import json, sys
from adapters import bridge_transport as bt
from src.services.opportunity_intake import OpportunityIntakeService
msg = json.loads(sys.stdin.read())
body = msg["body"].encode()
bt.verify_headers(msg["headers"], body, nonce_cache=bt.NonceCache(), expected_sender="daleobanks",
                  expected_recipient="wealthmachine", expected_operation="opportunity.evaluate")
assessment = OpportunityIntakeService().evaluate_packet(json.loads(body))
out = json.dumps(assessment, sort_keys=True).encode()
headers = bt.build_headers(out, identity="wealthmachine", schema_version=assessment["schema_version"],
                           idempotency_key=assessment["id"], recipient="kernel", operation="assessment.report",
                           trace_id=msg["headers"]["X-Trace-Id"], request_digest=bt.body_digest(body))
print(json.dumps({"body": out.decode(), "headers": headers}))
'''

# The assessment fields a second, independent WealthMachine run must reproduce exactly.
REPRODUCIBLE = ("go_no_go", "opportunity_score", "market_alignment", "risk_level", "legal_readiness",
                "requires_human_approval", "validation_plan", "reasons")
SUMMARY = ("go_no_go", "opportunity_score", "risk_level", "legal_readiness", "requires_human_approval")


def trace_for(mission_id: str, seed: str) -> str:
    """One trace per mission and seed, stable across retries, so a retry binds to the same trace."""
    return "trace-" + hashlib.sha256(json.dumps([mission_id, seed]).encode()).hexdigest()[:16]


def _interpreter(path, ctx: InvocationContext, name: str) -> Path:
    if not isinstance(path, str) or not path:
        raise CapabilityError(f"{name} must name the organ's own interpreter (founder-declared)")
    p = Path(path)
    if not p.is_absolute():
        raise CapabilityError(f"{name} must be an absolute path")
    # The venv entry is often a symlink to the system interpreter: confine the declared path,
    # not its target, and require it to be an executable file.
    parent = _inside(p.parent, ctx.read_roots)
    candidate = parent / p.name
    if not (candidate.is_file() and os.access(candidate, os.X_OK)):
        raise CapabilityError(f"{name} {path} is not an executable interpreter")
    return candidate


def _roots(params: dict, ctx: InvocationContext) -> dict:
    try:
        dale = _inside(Path(params["daleobanks_root"]), ctx.read_roots)
        wmi = _inside(Path(params["wealthmachine_root"]), ctx.read_roots)
    except KeyError as exc:
        raise CapabilityError(f"missing {exc.args[0]}") from None
    if not (dale / "services" / "idea_refinery.py").is_file():
        raise CapabilityError("daleobanks_root is not a DALEOBANKS checkout")
    if not (wmi / "src" / "services" / "opportunity_intake.py").is_file():
        raise CapabilityError("wealthmachine_root is not a WealthMachineIntelligence checkout")
    return {"daleobanks": dale, "wealthmachine": wmi,
            "daleobanks_python": _interpreter(params.get("daleobanks_python"), ctx, "daleobanks_python"),
            "wealthmachine_python": _interpreter(params.get("wealthmachine_python"), ctx, "wealthmachine_python")}


def _head(path: Path) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True,
                             timeout=10, env={"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1"})
        return out.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _snapshot(root: Path, dest: Path) -> dict:
    """The organ's committed HEAD extracted to ``dest``: what runs is exactly what is recorded."""
    git_env = {"PATH": "/usr/bin:/bin", "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(dest.parent)}
    head = _head(root)
    if head is None:
        raise CapabilityError(f"{root.name} is not a git checkout with a commit; its code cannot be pinned")
    dest.mkdir(parents=True)
    archive = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C", str(root), "archive", "--format=tar",
                              head], capture_output=True, timeout=120, env=git_env)
    if archive.returncode:
        raise CapabilityError(f"could not snapshot {root.name}: " + archive.stderr.decode("utf-8", "replace")[-300:])
    untar = subprocess.run(["tar", "-x", "-f", "-", "-C", str(dest)], input=archive.stdout, capture_output=True,
                           timeout=120, env={"PATH": "/usr/bin:/bin"})
    if untar.returncode:
        raise CapabilityError(f"could not extract the {root.name} snapshot")
    dirty = subprocess.run(["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
                           capture_output=True, text=True, timeout=60, env=git_env).stdout.strip()
    return {"path": dest, "head": head, "tree_sha256": _tree_digest(dest),
            "uncommitted_changes_ignored": bool(dirty)}


def _unchanged(snapshot: dict, why: str) -> None:
    if _tree_digest(snapshot["path"]) != snapshot["tree_sha256"]:
        raise CapabilityError(f"the {snapshot['path'].name} snapshot changed {why}; the exchange was refused")


def _confinement(python: Path, code_dir: Path, store: Path) -> dict | None:
    """Landlock grants for one organ stage: its own code snapshot and interpreter read-only, the
    system runtime read-only, writes only to the mission's organ store. Another organ's code, the
    Kernel's sources and the body's home are unreachable. None where Landlock is unavailable."""
    if not isolation.available().get("available"):
        return None
    runtime = Path(os.path.realpath(python)).parents[1]          # e.g. /usr for /usr/bin/python3.13
    return {"read": [code_dir, "/etc", "/dev/urandom"],
            "read_exec": [python.parent.parent, runtime, "/usr", "/lib", "/lib64", "/bin"],
            "write": [store, "/dev/null"]}


def _stage(python: Path, cwd: Path, code: str, *args, stdin=None, env: dict, timeout: float,
           confine: dict | None = None, stop_check=None) -> dict:
    if timeout <= 0:
        raise CapabilityError("the organ exchange exceeded its time bound")
    try:
        proc = run_isolated([str(python), "-s", "-c", code, *args], cwd=cwd, isolate_network=True,
                            timeout=timeout, extra_env=env, confine=confine,
                            stop_check=stop_check or (lambda: False),
                            input_bytes=json.dumps(stdin).encode() if stdin is not None else None)
    except WorkerInterrupted:
        # Nothing an interrupted exchange recorded counts without a receipt (organ_bridge.bound_facts).
        raise CapabilityError("founder STOP ended the organ exchange; its organ processes were killed") from None
    except subprocess.TimeoutExpired:
        raise CapabilityError(f"organ stage in {cwd.name} exceeded the exchange's time bound") from None
    if proc.returncode:
        raise CapabilityError(f"organ stage in {cwd.name} failed: "
                              + proc.stderr.decode("utf-8", "replace")[-600:])
    try:
        return json.loads(proc.stdout.decode("utf-8").strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise CapabilityError(f"organ stage in {cwd.name} returned no message") from None


def exchange(params: dict, ctx: InvocationContext) -> dict:
    seed = params.get("seed")
    if not isinstance(seed, str) or not 1 <= len(seed) <= MAX_SEED or "\0" in seed:
        raise CapabilityError(f"seed must be 1..{MAX_SEED} characters of text")
    if not ctx.mission_id:
        raise CapabilityError("an organ exchange belongs to exactly one mission")
    roots = _roots(params, ctx)
    timeout = params.get("timeout_seconds", 300)
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 30 <= timeout <= 900:
        raise CapabilityError("timeout_seconds must be an integer in [30, 900] (the whole exchange's bound)")
    store = ctx.workspace / "organs" / PAIR
    (store / "tmp").mkdir(parents=True, exist_ok=True)
    key = _secrets.token_hex(32)          # per invocation, only in the children's environment, never written
    env = {bt.SIGNING_KEY_ENV: key, "HOME": str(store), "TMPDIR": str(store / "tmp"), "PERSIST_STORE": "false",
           "LEDGER_PATH": str(store / "daleobanks-decision-ledger.jsonl"),
           "DB_SNAPSHOT_PATH": str(store / "daleobanks-store.jsonl"), "PYTHONDONTWRITEBYTECODE": "1"}
    # One trace per mission: a mission already bound to a trace (an earlier seed or an older ledger)
    # keeps it, so a second exchange never runs both organs only to fail the binding afterwards.
    bound = [e.payload["trace_id"] for e in (ctx.journal.replay("organ.observed") if ctx.journal else [])
             if e.payload.get("mission_id") == ctx.mission_id and e.payload.get("trace_id")]
    trace = bound[0] if bound else trace_for(ctx.mission_id, seed)
    # Code snapshots live beside the writable store, never inside it.
    (ctx.workspace / "organs" / "code").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=PAIR + "-", dir=ctx.workspace / "organs" / "code") as tmp:
        code = {organ: _snapshot(roots[organ], Path(tmp) / organ) for organ in ("daleobanks", "wealthmachine")}
        for organ, snap in code.items():
            snap["confine"] = _confinement(roots[organ + "_python"], snap["path"], store)
            snap["interpreter"] = _interpreter_record(roots[organ + "_python"])
        deadline = time.monotonic() + timeout
        try:
            return _exchange(ctx, roots, code, env, seed, trace, deadline)
        except (bt.BridgeSecurityError, organ_bridge.MissionBindingError, EventError, KeyError, ValueError,
                TypeError) as exc:
            # A forged, misbound or malformed exchange is a receipted refusal, never an "uncertain
            # external effect" for the founder to reconcile: nothing here touches the outside world.
            raise CapabilityError(f"organ exchange refused: {type(exc).__name__}: {str(exc)[:300]}") from None


def _interpreter_record(python: Path) -> dict:
    """What actually runs for an organ: the declared path, its resolved target and that file's digest."""
    real = Path(os.path.realpath(python))
    return {"declared": str(python), "realpath": str(real), "sha256": hashlib.sha256(real.read_bytes()).hexdigest()}


def _wire(payload: dict, contract: str, who: str) -> dict:
    try:
        return validate_contract(payload, contract)
    except ValueError as exc:
        raise CapabilityError(f"{who} broke its wire contract ({contract}): {str(exc)[:200]}") from None


def _assigned(message: dict, trace: str, who: str) -> None:
    """The organs sign the trace they were given. One that names another trace is refused before
    anything is recorded, so the receipt and the journal never disagree about the binding."""
    signed = (message.get("headers") or {}).get(bt.H_TRACE)
    if signed != trace:
        raise CapabilityError(f"{who} signed trace {signed!r}, not the assigned {trace}")


def _exchange(ctx, roots, code, env, seed, trace, deadline) -> dict:
    dale, wmi = code["daleobanks"], code["wealthmachine"]
    left = lambda: deadline - time.monotonic()                                      # noqa: E731
    d = _stage(roots["daleobanks_python"], dale["path"], DALEOBANKS_STAGE, seed, trace, env=env, timeout=left(),
               confine=dale["confine"], stop_check=ctx.stop_check)
    if d.get("no_opportunity"):
        # DALEOBANKS's own judgment: nothing to evaluate. A correct organ answer, not a capability
        # fault, so it completes (no message exists and none is recorded); the mission's check
        # stays failing, truthfully.
        return {"state": "NO_OPPORTUNITY", "pair": PAIR, "trace_id": trace, "refined": d.get("refined"),
                "appraisal_verdict": None, "transport_verified": False,
                "organ_heads": {organ: snap["head"] for organ, snap in code.items()},
                "recorded_in_journal": False, "external_effects": None, "spend_usd": 0.0, "authority_created": False}
    _unchanged(wmi, "while DALEOBANKS ran")
    _assigned(d, trace, "DALEOBANKS")
    _wire(json.loads(d["body"]), "wire-opportunity-packet", "DALEOBANKS")
    w = _stage(roots["wealthmachine_python"], wmi["path"], WEALTHMACHINE_STAGE, stdin=d, env=env, timeout=left(),
               confine=wmi["confine"], stop_check=ctx.stop_check)
    _assigned(w, trace, "WealthMachine")
    _wire(json.loads(w["body"]), "wire-venture-assessment", "WealthMachine")
    request_body, answer_body = d["body"].encode(), w["body"].encode()
    # Kernel-side verification under the same key; a forged or replayed message raises here.
    previous = os.environ.get(bt.SIGNING_KEY_ENV)
    os.environ[bt.SIGNING_KEY_ENV] = env[bt.SIGNING_KEY_ENV]
    try:
        cache = bt.NonceCache()
        if ctx.journal is not None:
            seen = [organ_bridge.record_exchange(
                        ctx.journal, mission_id=ctx.mission_id, headers=d["headers"], body=request_body,
                        nonce_cache=cache, expected_sender="daleobanks", expected_operation="opportunity.evaluate"),
                    organ_bridge.record_exchange(
                        ctx.journal, mission_id=ctx.mission_id, headers=w["headers"], body=answer_body,
                        nonce_cache=cache, expected_sender="wealthmachine", expected_recipient="kernel",
                        expected_operation="assessment.report", request_digest=bt.body_digest(request_body))]
        else:
            seen = [bt.verify_headers(d["headers"], request_body, nonce_cache=cache, expected_sender="daleobanks",
                                      expected_operation="opportunity.evaluate"),
                    bt.verify_headers(w["headers"], answer_body, nonce_cache=cache, expected_sender="wealthmachine",
                                      expected_recipient="kernel", expected_operation="assessment.report",
                                      request_digest=bt.body_digest(request_body))]
    finally:
        if previous is None:
            os.environ.pop(bt.SIGNING_KEY_ENV, None)
        else:
            os.environ[bt.SIGNING_KEY_ENV] = previous
    _unchanged(wmi, "between the WealthMachine runs")
    # The re-derivation: a fresh WealthMachine process given DALEOBANKS's own signed message (its
    # replay cache is its own). The Kernel never signs as an organ: with per-organ keys configured
    # in the body, building headers here would forge DALEOBANKS's isolated identity.
    redo = _stage(roots["wealthmachine_python"], wmi["path"], WEALTHMACHINE_STAGE, stdin=d,
                  env=env, timeout=left(), confine=wmi["confine"], stop_check=ctx.stop_check)
    packet, original = json.loads(d["body"]), json.loads(w["body"])
    again = _wire(json.loads(redo["body"]), "wire-venture-assessment", "WealthMachine (re-derivation)")
    # A field both runs omit is not "reproduced": absence on both sides proves nothing.
    reproduced = {k: original.get(k) is not None and again.get(k) == original.get(k) for k in REPRODUCIBLE}
    invariants = {"human_approval_required": original.get("requires_human_approval") is True,
                  "answers_this_packet": original.get("opportunity_packet_id") == packet.get("id"),
                  "redo_answers_this_packet": again.get("opportunity_packet_id") == packet.get("id"),
                  "finance_flag_forces_review": "finance_education_only" not in packet.get("risk_flags", [])
                                                or original.get("legal_readiness") == "review_required"}
    judged = {"trace_id": trace, "packet_sha256": hashlib.sha256(request_body).hexdigest(),
              "assessment_sha256": hashlib.sha256(answer_body).hexdigest(),
              "redo_sha256": hashlib.sha256(redo["body"].encode()).hexdigest()}
    if ctx.journal is not None:
        appraisal = organ_bridge.record_appraisal(ctx.journal, mission_id=ctx.mission_id,
                                                  appraiser="kernel-organ-appraiser", reproduced=reproduced,
                                                  invariants=invariants, exchange=judged)
    else:
        passed = all(reproduced.values()) and all(invariants.values())
        appraisal = {"verdict": organ_bridge.APPRAISAL_VERDICT if passed else "REFUTED",
                     "checks": {**reproduced, **invariants}}
    return {"pair": PAIR, "trace_id": trace, "packet_id": packet.get("id"),
            "packet_sha256": judged["packet_sha256"], "assessment_sha256": judged["assessment_sha256"],
            "redo_sha256": judged["redo_sha256"],
            "assessment": {k: original.get(k) for k in SUMMARY},
            "appraisal_verdict": appraisal["verdict"], "transport_verified": True,
            "sender_identity_isolated": all(bool(s.get("identity_isolated") in (True, "true")) or
                                            bool(s.get("sender_identity_isolated")) for s in seen),
            "organ_heads": {organ: snap["head"] for organ, snap in code.items()},
            "organ_code": {organ: {**{k: snap[k] for k in ("head", "tree_sha256", "uncommitted_changes_ignored",
                                                           "interpreter")},
                                   "filesystem_confined": snap["confine"] is not None}
                           for organ, snap in code.items()},
            "independence": ("separate processes from committed snapshots, each confined (Landlock) to its own "
                             "code, its interpreter and the mission's organ store; same host and UID"
                             if all(snap["confine"] for snap in code.values()) else
                             "separate processes from committed snapshots, NOT filesystem-confined on this host "
                             "(same UID and filesystem); the WealthMachine snapshot digest was re-checked before "
                             "each WealthMachine run")
                            + "; the re-derivation shows same-code determinism, not an independent party",
            "recorded_in_journal": ctx.journal is not None, "external_effects": None, "spend_usd": 0.0,
            "authority_created": False}


def status(params: dict, ctx: InvocationContext) -> dict:
    """Read-only: this mission's organ facts as retained in the journal."""
    if ctx.journal is None or not ctx.mission_id:
        raise CapabilityError("organ.status reads one mission's journal facts")
    facts = organ_bridge.bound_facts(ctx.journal, ctx.mission_id)
    observed, appraisals = facts["observed"], facts["appraisals"]
    traces = sorted({o.get("trace_id") for o in observed if o.get("trace_id")})
    return {"organs_observed": sorted({o["organ"] for o in observed}),
            "messages": len(observed), "transport_verified": bool(observed) and all(o.get("transport_verified")
                                                                                    for o in observed),
            "trace_ids": traces, "verdict": appraisals[-1]["verdict"] if appraisals else None,
            "appraisals": len(appraisals), "bound_to_receipts": facts["receipts"],
            "founder_reconciled": facts["founder_reconciled"], "unbound_facts_ignored": facts["unbound"]}


__all__ = ["DALEOBANKS_STAGE", "PAIR", "REPRODUCIBLE", "TARGET", "WEALTHMACHINE_STAGE", "exchange", "status",
           "trace_for"]
