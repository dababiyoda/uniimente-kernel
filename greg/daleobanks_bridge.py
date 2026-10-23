"""DALEOBANKS as a governed work surface for GREG missions (no social machinery rebuilt here).

GREG never posts. It asks DALEOBANKS, through DALEOBANKS's own code running in DALEOBANKS's
own interpreter, to (a) verify a draft with its EthicsGuard/Critic/PromptFirewall and (b)
attempt a publish through its existing ``SocialMultiplexer`` -> ``BaseSocialClient.publish``
gate (decision ledger, LIVE kill switch, rate governor, dry-run fallback). Two independent
authorities therefore stand between a draft and a platform:

    GREG mission -> Kernel Consequence Gate (external_contact: founder approval required)
                 -> DALEOBANKS KillSwitch (LIVE arming) + RateGovernor + platform credentials

Either may block. A block is returned truthfully with DALEOBANKS's own hash-chained ledger
entries as evidence; a dry-run identifier is never reported as a post.

On a body with confined egress (#26) DALEOBANKS's interpreter runs in a bubblewrap network
namespace whose only way out is the body relay's door: ``daleobanks.verify`` may reach
nothing, ``daleobanks.publish`` only the platform API hosts its manifest declares (the X API,
through tweepy). Every attempt is decided and journaled at the relay; without namespaces
nothing runs.

Capabilities:
  ``daleobanks.verify``   read_only sensor: DALEOBANKS content checks + GREG claim/source binding. Given
                          ``cognition`` (claim name -> problem id), every sentence of the draft must be a claim
                          that GREG's evidence family answered as written: bound to a supporting span and showing
                          none of the six detected kinds of change (directive section 16, the media case).
  ``daleobanks.publish``  external_contact: one publish request through DALEOBANKS's gate
  ``daleobanks.outcome``  read_only sensor: projection of this mission's canonical publish receipts
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from greg.capabilities import CapabilityError, InvocationContext, _inside
# The sentence-by-sentence rule is shared with the Task Fabric's evaluator (worker.appraise).
from greg.cognition.restatement import coverage as truth_preservation

SCRIPT = r'''
import asyncio, json, sys
from services.ethics_guard import EthicsGuard
from services.critic import Critic
from services.prompt_firewall import PromptFirewall
request = json.loads(sys.stdin.read())
draft = open(request["draft"], encoding="utf-8").read()
out = {"draft_chars": len(draft)}
ethics = EthicsGuard().validate_text(draft)
critic = Critic().analyze_quality(draft, content_type=request.get("content_type", "reply"))
out["ethics"] = {"approved": ethics.approved, "reasons": ethics.reasons, "uncertainty": ethics.uncertainty_score}
out["critic"] = {"blocking_issues": critic.blocking_issues, "quality_score": critic.quality_score}
out["firewall"] = PromptFirewall().scan(draft)
if request["action"] == "publish":
    from services.ledger import DecisionLedger, get_kill_switch
    from services.multiplexer import SocialMultiplexer
    out["kill_switch_armed"] = bool(get_kill_switch().armed)
    mux = SocialMultiplexer()
    out["platforms"] = sorted(mux.enabled_platforms())
    ledger = DecisionLedger()
    before = len(ledger.replay())
    metadata = {"greg_mission": request["mission_id"], "greg_grant": request["grant_id"]}
    if request.get("daleobanks_grant"):
        metadata.update(capability_grant_id=request["daleobanks_grant"], draft_id=request["draft_id"])
    results = asyncio.run(mux.publish(draft, kind="post", metadata=metadata))
    out["results"] = {k: {"post_id": v.post_id, "dry_run": v.dry_run} for k, v in results.items()}
    out["publish_gated"] = [{"platform": (e.get("payload") or {}).get("platform"),
                             "reason": (e.get("payload") or {}).get("reason"),
                             "capability_grant_id": (e.get("payload") or {}).get("capability_grant_id")}
                            for e in ledger.replay()[before:] if e.get("event") == "publish_gated"]
    ok = ledger.verify_chain()
    out["ledger"] = {"path": ledger.path, "chain_ok": ok if isinstance(ok, bool) else ok[0],
                     "tail": [{k: e.get(k) for k in ("seq", "event", "payload", "hash")} for e in ledger.replay()[-6:]]}
print(json.dumps(out, default=str))
'''


_GRANT_REF = re.compile(r"[A-Za-z0-9_.:-]{1,128}")


def _daleobanks_grant(params: dict) -> dict:
    """The DALEOBANKS CapabilityGrant a human approved in DALEOBANKS, and the draft it names, as the founder signed
    them in the mission's params. GREG forwards the reference only; DALEOBANKS validates and consumes it at its own
    gate. GREG never mints, widens or stores a DALEOBANKS grant. Both or neither."""
    grant, draft = params.get("daleobanks_grant"), params.get("draft_id")
    if grant is None and draft is None:
        return {}
    if not (isinstance(grant, str) and isinstance(draft, str) and _GRANT_REF.fullmatch(grant)
            and _GRANT_REF.fullmatch(draft)):
        raise CapabilityError("daleobanks_grant and draft_id go together, as DALEOBANKS identifiers "
                              "(letters, digits and . _ : -, at most 128)")
    return {"daleobanks_grant": grant, "draft_id": draft}


def _draft(params: dict, ctx: InvocationContext) -> Path:
    path = Path(params["draft"])
    return _inside(path if path.is_absolute() else ctx.workspace / path, ctx.read_roots + (ctx.workspace,))


def _run(params: dict, ctx: InvocationContext, action: str) -> dict:
    root = _inside(Path(params["daleobanks_root"]), ctx.read_roots)
    python = Path(params.get("python") or root / ".venv/bin/python")
    if not os.access(python, os.X_OK):
        raise CapabilityError(f"DALEOBANKS interpreter {python} is not installed")
    draft = _draft(params, ctx)
    ledger = _inside(ctx.workspace / "daleobanks" / "decision_ledger.jsonl", (ctx.workspace,))
    ledger.parent.mkdir(parents=True, exist_ok=True)
    env = {"PATH": f"{python.parent}:/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(ledger.parent),
           "LEDGER_PATH": str(ledger), "PYTHONPATH": str(root)}
    # LIVE and platform credentials are DALEOBANKS's own arming; GREG never sets or forwards them.
    request = {"draft": str(draft), "action": action, "mission_id": ctx.mission_id, "grant_id": ctx.grant_id,
               "content_type": params.get("content_type", "reply"), **_daleobanks_grant(params)}
    argv = [str(python), "-c", SCRIPT]
    if ctx.egress is None:
        proc = subprocess.run(argv, input=json.dumps(request), capture_output=True, text=True, cwd=root, env=env,
                              timeout=120)
    else:
        proc = _behind_door(argv, request, env, ctx, root=root, ledger_dir=ledger.parent, draft=draft)
    if proc.returncode:
        raise CapabilityError("DALEOBANKS refused or failed: " + (proc.stderr or proc.stdout)[-400:])
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise CapabilityError("DALEOBANKS produced unreadable output") from exc


def _behind_door(argv: list, request: dict, env: dict, ctx: InvocationContext, *, root: Path, ledger_dir: Path,
                 draft: Path):
    """DALEOBANKS's interpreter in a network namespace whose only way out is the relay, allowlisted for exactly the
    hosts this capability's manifest declares (none for verify). Its ledger directory is the one writable place."""
    import sys
    from foundry.systems.relay_door import Door, door_argv, namespace_argv
    from foundry.systems.segmentation import Relay
    from greg.worker_isolation import WorkerIsolationError, _backend
    try:
        _backend(require_bubblewrap=True)
    except WorkerIsolationError as exc:
        raise CapabilityError(f"confined egress needs bubblewrap network namespaces here: {exc}") from None
    identity, hosts = ctx.manifest.capability_id, tuple(ctx.manifest.egress_allowlist or ())
    scoped = Relay({identity: {"allow": [[h, 443] for h in hosts], "external": bool(hosts)}}, ctx.egress.journal,
                   connect=ctx.egress.connect, proxy=ctx.egress.proxy)
    # The interpreter's own venv (its packages) and the base Python it resolves to may both live under the hidden
    # $HOME (a CI runner keeps both there), so both are shown again, read-only, as foundry/systems/mcp_gateway does.
    venv = str(Path(argv[0]).parent.parent)
    interpreter = str(Path(argv[0]).resolve().parent.parent)
    namespace = namespace_argv(writable=[ledger_dir], readonly=[root, draft, venv, interpreter], chdir=root)
    with Door(scoped, identity) as door:
        return subprocess.run(namespace + door_argv(sys.executable, door.fd, argv), pass_fds=[door.fd],
                              input=json.dumps(request), capture_output=True, text=True, env=env, timeout=120)


NUMBER = re.compile(r"\d[\d,.]*%?")


def _unsupported_numbers(draft: str, source: str) -> list[str]:
    """Every figure in the draft must literally appear in the source it is bound to."""
    normalized = source.replace(",", "")
    return sorted({n for n in NUMBER.findall(draft) if n.rstrip(".,").replace(",", "") not in normalized})


def verify(params: dict, ctx: InvocationContext) -> dict:
    """``daleobanks.verify``: DALEOBANKS's content checks + claim/source binding, read-only."""
    draft = _draft(params, ctx)
    if not draft.is_file():
        return {"present": False, "verdict": "ABSENT"}
    text = draft.read_text(encoding="utf-8")
    source = _inside(Path(params["source"]), ctx.read_roots + (ctx.workspace,)).read_text(encoding="utf-8")
    checks = _run(params, ctx, "verify")
    findings = []
    limit = int(params.get("max_chars", 280))
    if len(text.strip()) > limit:
        findings.append(f"draft is {len(text.strip())} characters; limit {limit}")
    unsupported = _unsupported_numbers(text, source)
    if unsupported:
        findings.append(f"figures not found in the source: {unsupported}")
    if not checks["ethics"]["approved"]:
        findings.append("DALEOBANKS EthicsGuard: " + "; ".join(checks["ethics"]["reasons"])[:300])
    if checks["critic"]["blocking_issues"]:
        findings.append("DALEOBANKS Critic blocking: " + "; ".join(checks["critic"]["blocking_issues"])[:300])
    if float(checks["firewall"].get("risk", 0)) >= 0.5:
        findings.append(f"DALEOBANKS PromptFirewall risk {checks['firewall']['risk']}: {checks['firewall'].get('patterns')}")
    truth = {"checked": False, "limits": "figures against the source only: no sentence was checked as written"}
    if params.get("cognition"):
        from greg.ventures import cognition_receipts
        truth, problems = truth_preservation(text, cognition_receipts(ctx, params["cognition"]))
        findings += problems
    return {"present": True, "verdict": "VERIFIED" if not findings else "REJECTED", "findings": findings,
            "draft_sha256": "sha256:" + hashlib.sha256(text.encode()).hexdigest(), "chars": len(text.strip()),
            "daleobanks": checks, "truth_preservation": truth, "authority_created": False}


def publish(params: dict, ctx: InvocationContext) -> dict:
    """``daleobanks.publish``: one publish request through DALEOBANKS's own gate; truthful outcome."""
    result = _run(params, ctx, "publish")
    posted = {k: v for k, v in result.get("results", {}).items() if not v["dry_run"]}
    gated = [g for g in result.get("publish_gated", []) or [] if isinstance(g, dict)]
    if posted:
        status, why = "PUBLISHED", "DALEOBANKS reported live platform identifiers"
    elif not result.get("kill_switch_armed"):
        status, why = "BLOCKED_BY_DALEOBANKS", ("DALEOBANKS kill switch is disarmed (LIVE=false): the request "
                                                "was ledgered and dry-run; nothing was posted")
    elif gated:
        # DALEOBANKS's own publish authority (or its rate governor) refused, and ledgered why: report exactly that.
        reasons = sorted({str(g.get("reason")) for g in gated})
        why = "DALEOBANKS gated the publish (" + ", ".join(reasons) + "); it was dry-run and nothing was posted"
        if "no_capability_grant" in reasons:
            why += (": no DALEOBANKS grant reached its gate. A live post needs a grant a human approved in DALEOBANKS "
                    "for this exact draft, named in the founder-signed mission as daleobanks_grant and draft_id")
        status = "BLOCKED_BY_DALEOBANKS"
    else:
        status, why = "BLOCKED_BY_DALEOBANKS", ("armed and no gate recorded a refusal, yet every platform stayed in "
                                                "dry-run (no platform credentials or client): nothing was posted")
    return {"status": status, "why": why, "published": posted, "dry_run": result.get("results", {}),
            "publish_gated": gated,
            "platforms": result.get("platforms", []), "kill_switch_armed": result.get("kill_switch_armed"),
            "daleobanks_ledger": result.get("ledger"), "checks": {k: result[k] for k in ("ethics", "critic")},
            "authority_created": False}


def _organ_hashes(ctx: InvocationContext) -> set | None:
    """Entry hashes present in the workspace organ file; None when it is absent or unreadable."""
    ledger = _inside(ctx.workspace / "daleobanks" / "decision_ledger.jsonl", (ctx.workspace,))
    try:
        return {json.loads(line).get("hash") for line in ledger.read_text().splitlines() if line.strip()}
    except (OSError, ValueError, AttributeError):
        return None


def publish_status(params: dict, ctx: InvocationContext) -> dict:
    """``daleobanks.outcome`` (read-only sensor): a projection of this mission's canonical publish receipts.

    The outcome comes only from Gate receipts of ``daleobanks.publish`` actions of this mission. The
    workspace organ ledger is writable by any signed workspace write, so it can only lower
    ``organ_consistent`` (a witnessed entry missing or rewritten); it never adds a fact. No receipted
    publish -> no outcome. Limit: a bound receipt proves the Gate ran the publish step at the
    founder-signed checkout and interpreter and retained what that code printed. It does not prove the
    code there is DALEOBANKS's reviewed gate (the root and interpreter are signed parameters, not pinned
    code), nor that a post exists (no platform read-back exists).
    """
    if ctx.journal is None or not ctx.mission_id:
        raise CapabilityError("daleobanks.outcome projects one mission's canonical publish receipts; journal required")
    bound, unwitnessed = [], 0
    for event in ctx.journal.replay("mission.action"):
        p = event.payload
        if p.get("mission_id") != ctx.mission_id or p.get("capability") != "daleobanks.publish" \
                or p.get("status") != "DONE":
            continue
        record = ctx.journal.ledger.find(p["receipt"]) if p.get("receipt") else None
        result = record.payload.get("result", {}) if record is not None and record.record_type == "receipt" else {}
        if result.get("result_class") == "positive" and isinstance(result.get("output"), dict):
            bound.append((record.hash, result["output"]))
        else:
            unwitnessed += 1    # e.g. founder reconcile_executed: executed, but its outcome was never retained
    if not bound:
        return {"requested": False, "outcome": "NONE", "unwitnessed_actions": unwitnessed}
    witnessed, chains_ok = set(), True
    for _, output in bound:
        organ = output.get("daleobanks_ledger") or {}
        chains_ok = chains_ok and organ.get("chain_ok") is True
        witnessed |= {e["hash"] for e in organ.get("tail") or [] if isinstance(e, dict) and e.get("hash")}
    present = _organ_hashes(ctx)
    last = bound[-1][1]
    return {"requested": True, "outcome": "PUBLISHED" if last.get("status") == "PUBLISHED" else "BLOCKED_DRY_RUN",
            "statuses": [o.get("status") for _, o in bound], "bound_receipts": [h for h, _ in bound],
            "unwitnessed_actions": unwitnessed,
            "organ_consistent": chains_ok and present is not None and witnessed <= present,
            "basis": "canonical daleobanks.publish receipts of the code at the signed root and interpreter; "
                     "its self-report, no platform read-back"}
