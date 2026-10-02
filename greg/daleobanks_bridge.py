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

Capabilities:
  ``daleobanks.verify``   read_only sensor: DALEOBANKS content checks + GREG claim/source binding
  ``daleobanks.publish``  external_contact: one publish request through DALEOBANKS's gate
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from greg.capabilities import CapabilityError, InvocationContext, _inside

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
    results = asyncio.run(mux.publish(draft, kind="post", metadata={"greg_mission": request["mission_id"],
                                                                     "greg_grant": request["grant_id"]}))
    out["results"] = {k: {"post_id": v.post_id, "dry_run": v.dry_run} for k, v in results.items()}
    ledger = DecisionLedger()
    ok = ledger.verify_chain()
    out["ledger"] = {"path": ledger.path, "chain_ok": ok if isinstance(ok, bool) else ok[0],
                     "tail": [{k: e.get(k) for k in ("seq", "event", "payload", "hash")} for e in ledger.replay()[-6:]]}
print(json.dumps(out, default=str))
'''


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
               "content_type": params.get("content_type", "reply")}
    proc = subprocess.run([str(python), "-c", SCRIPT], input=json.dumps(request), capture_output=True, text=True,
                          cwd=root, env=env, timeout=120)
    if proc.returncode:
        raise CapabilityError("DALEOBANKS refused or failed: " + (proc.stderr or proc.stdout)[-400:])
    try:
        return json.loads(proc.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise CapabilityError("DALEOBANKS produced unreadable output") from exc


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
    source = _inside(Path(params["source"]), ctx.read_roots).read_text(encoding="utf-8")
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
    return {"present": True, "verdict": "VERIFIED" if not findings else "REJECTED", "findings": findings,
            "draft_sha256": "sha256:" + hashlib.sha256(text.encode()).hexdigest(), "chars": len(text.strip()),
            "daleobanks": checks, "authority_created": False}


def publish(params: dict, ctx: InvocationContext) -> dict:
    """``daleobanks.publish``: one publish request through DALEOBANKS's own gate; truthful outcome."""
    result = _run(params, ctx, "publish")
    posted = {k: v for k, v in result.get("results", {}).items() if not v["dry_run"]}
    if posted:
        status, why = "PUBLISHED", "DALEOBANKS reported live platform identifiers"
    elif not result.get("kill_switch_armed"):
        status, why = "BLOCKED_BY_DALEOBANKS", ("DALEOBANKS kill switch is disarmed (LIVE=false): the request "
                                                "was ledgered and dry-run; nothing was posted")
    else:
        status, why = "BLOCKED_BY_DALEOBANKS", "armed, but rate governor or credentials kept every platform in dry-run"
    return {"status": status, "why": why, "published": posted, "dry_run": result.get("results", {}),
            "platforms": result.get("platforms", []), "kill_switch_armed": result.get("kill_switch_armed"),
            "daleobanks_ledger": result.get("ledger"), "checks": {k: result[k] for k in ("ethics", "critic")},
            "authority_created": False}


def publish_status(params: dict, ctx: InvocationContext) -> dict:
    """``daleobanks.outcome`` (read-only sensor): read DALEOBANKS's ledger for this mission's request."""
    ledger = _inside(ctx.workspace / "daleobanks" / "decision_ledger.jsonl", (ctx.workspace,))
    if not ledger.is_file():
        return {"requested": False, "outcome": "NONE"}
    entries = [json.loads(line) for line in ledger.read_text().splitlines() if line.strip()]
    results = [e for e in entries if e.get("event") == "publish_result"]
    attempts = [e for e in entries if e.get("event") == "publish_attempt"]
    if not results:
        return {"requested": bool(attempts), "outcome": "UNKNOWN", "entries": len(entries)}
    live = [r for r in results if not r["payload"].get("dry_run")]
    return {"requested": True, "outcome": "PUBLISHED" if live else "BLOCKED_DRY_RUN", "attempts": len(attempts),
            "results": [r["payload"] for r in results], "entries": len(entries),
            "last_hash": entries[-1].get("hash")}
