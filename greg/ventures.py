"""Signal -> venture assessment through the real organs (Bridge A, as a GREG capability).

    RailScout (evidence organ)   source-bound appraisal of real source bytes; unknown
                                 buyer/budget/verifier stay NEEDS_EVIDENCE
      -> wire OpportunityPacket  built by the Kernel side from the appraisal; fields
                                 RailScout did not evidence stay empty, never invented
      -> WealthMachine           the organ's own venture engine (opportunity_intake)
      -> Kernel adapters         canonical packet/assessment; untranslatable fields are
                                 reported as unresolved
      -> one decision memo       delivered to Alfonso; nothing is executed

Emergent rule no organ applies alone: **a score may not outrun missing evidence.**
The binding verdict is the WealthMachine verdict capped by the RailScout status, so
a "go" from the venture engine on a packet with no evidenced buyer is delivered as
``needs_more_evidence``, with both verdicts shown.

Each organ runs from its own checkout (inside the body's read roots) in a separate
Python process that receives no GREG secrets, keys or ledger. The appraiser
re-renders the memo from the receipt and re-runs both organs to confirm the
receipted appraisal and assessment were produced by them, not written by GREG.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

from greg.capabilities import CapabilityError, InvocationContext, _inside

KERNEL_ROOT = Path(__file__).resolve().parents[1]
RENDERER = "greg.ventures/1"
ORGAN_TIMEOUT_SECONDS = 60
NAMESPACE = uuid.UUID("2f0c6f86-3f1d-4b4e-9f2c-7a1e4c0d5b21")
VERDICT_RANK = {"kill": 0, "needs_more_evidence": 1, "defer": 2, "go": 3}

_RAILSCOUT = """
import json, sys
sys.path.insert(0, sys.argv[1])
from railscout.appraise import appraise
print(json.dumps(appraise(json.load(sys.stdin), sys.argv[2]), sort_keys=True))
"""
_WEALTHMACHINE = """
import json, logging, sys
logging.disable(logging.CRITICAL)
sys.path.insert(0, sys.argv[1]); sys.path.append(sys.argv[2])
from src.services.opportunity_intake import OpportunityIntakeService
print(json.dumps(OpportunityIntakeService().evaluate_packet(json.load(sys.stdin)), sort_keys=True))
"""


def _organ(script: str, stdin: dict, *args: str, cwd: Path) -> dict:
    """Run one organ in its own process: no GREG secrets, keys or ledger reach it."""
    # A fresh bytecode cache per run: a stale .pyc (same size, same mtime second) must
    # never let a re-run execute code other than the organ's current source.
    with tempfile.TemporaryDirectory(prefix="greg-organ-pyc-") as pycache:
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONHASHSEED": "0",
               "HOME": str(cwd), "LANG": "C.UTF-8", "PYTHONPYCACHEPREFIX": pycache}
        try:
            done = subprocess.run([sys.executable, "-s", "-c", script, *args], input=json.dumps(stdin),
                                  capture_output=True, text=True, timeout=ORGAN_TIMEOUT_SECONDS, cwd=cwd, env=env)
        except subprocess.TimeoutExpired:
            raise CapabilityError(f"organ timed out after {ORGAN_TIMEOUT_SECONDS}s") from None
    if done.returncode != 0:
        raise CapabilityError(f"organ refused: {done.stderr.strip().splitlines()[-1] if done.stderr.strip() else done.returncode}")
    return json.loads(done.stdout)


def _git_head(path: Path) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=10)
        return out.stdout.strip() or None
    except (OSError, subprocess.TimeoutExpired):
        return None


def packet_from_appraisal(receipt: dict) -> dict:
    """Wire OpportunityPacket from a RailScout receipt. Unevidenced fields stay empty."""
    appraisal = receipt["appraisal"]
    market, evidence = appraisal.get("market", {}), (appraisal.get("market") or {}).get("evidence", {})
    evidenced = lambda key: market.get(key, "").strip() if market.get(key, "").strip() and evidence.get(key) else ""
    supporting = [c for c in appraisal["claims"] if c["stance"] == "supports"]
    sources = {s["id"]: s for s in appraisal["sources"]}
    collected = max(s["collected_at"] for s in appraisal["sources"])
    return {
        "id": str(uuid.uuid5(NAMESPACE, receipt["receipt_sha256"])),
        "schema_version": "1.1",
        "created_at": collected,
        "source": "railscout",
        "source_ref": receipt["receipt_sha256"],
        "signal_type": "product_opportunity",
        "observed_pain": appraisal["failure"]["description"],
        "core_thesis": appraisal["question"],
        "audience": evidenced("buyer"),
        "buyer_type": evidenced("budget_owner"),
        "urgency": "medium",
        "evidence": [f"{c['assertion']} [source {sources[c['source_id']]['path']} sha256:"
                     f"{sources[c['source_id']]['sha256']} bytes {c['byte_start']}-{c['byte_end']}]"
                     for c in supporting],
        "possible_offer": appraisal["candidate"]["current_form"],
        "monetization_paths": [],
        "risk_flags": [],
        "smallest_validation_action": appraisal["next_action"],
    }


def binding_verdict(railscout_status: str, wmi_verdict: str) -> tuple[str, str]:
    """A score may not outrun missing evidence."""
    if railscout_status == "READY_FOR_HUMAN_REVIEW":
        return wmi_verdict, "evidence complete for review; the venture engine verdict stands"
    capped = min(wmi_verdict, "needs_more_evidence", key=lambda v: VERDICT_RANK.get(v, 1))
    if capped != wmi_verdict:
        return capped, f"RailScout status {railscout_status} caps the engine's '{wmi_verdict}'"
    return capped, f"RailScout status {railscout_status}; engine verdict already no higher"


def _canonical(packet: dict, assessment: dict) -> dict:
    sys.path.insert(0, str(KERNEL_ROOT)) if str(KERNEL_ROOT) not in sys.path else None
    from adapters import daleobanks_opportunity, wealthmachine_assessment
    try:
        packet_result = daleobanks_opportunity.adapt(packet, transport_identity="kernel")
        canonical_assessment = wealthmachine_assessment.adapt(assessment, transport_identity="wealthmachine")
    except daleobanks_opportunity.AdapterError as exc:
        raise CapabilityError(f"organ output violates the kernel contract: {exc}") from None
    return {"packet_unresolved": packet_result.unresolved, "packet_resolved": packet_result.resolved,
            "assessment_verdict": canonical_assessment["verdict"],
            "assessment_execution_authority": canonical_assessment["execution_authority"],
            "assessment_requires_human_approval": canonical_assessment["requires_human_approval"]}


STABLE_ASSESSMENT = ("go_no_go", "opportunity_score", "market_alignment", "risk_level", "reasons", "cases",
                     "validation_plan", "recommended_next_action", "requires_human_approval")


def render(inputs: dict) -> str:
    appraisal, assessment = inputs["railscout"]["appraisal"], inputs["assessment"]
    v = inputs["binding"]
    lines = [f"# Venture assessment — {appraisal['question']}", "",
             f"**Binding verdict: {v['verdict']}** — {v['why']}.", "",
             f"- RailScout (evidence): **{appraisal['status']}**; next action: {appraisal['next_action']}",
             f"- WealthMachine (venture engine): **{assessment['go_no_go']}**, opportunity score "
             f"{assessment['opportunity_score']}, market alignment {assessment['market_alignment']}, risk "
             f"{assessment['risk_level']}",
             f"- Requires your approval: yes. GREG executed nothing beyond reading sources and running both organs.",
             "", "## Governing transaction", "", appraisal["transaction"], "",
             f"Failure layer: {appraisal['failure']['layer']} — {appraisal['failure']['description']}", "",
             "## Evidence (source bytes verified; assertions not independently verified)", ""]
    for c in appraisal["claims"]:
        lines.append(f"- {c['stance']} [{c['id']}, {c['kind']}] {c['assertion']} "
                     f"(`{c['source_id']}` bytes {c['byte_start']}-{c['byte_end']})")
    lines += ["", "## What is not evidenced", ""]
    lines += [f"- {m}" for m in appraisal["missing"]] or ["- nothing listed"]
    lines += [f"- canonical packet fields unresolved: {', '.join(inputs['canonical']['packet_unresolved']) or 'none'}"]
    if appraisal.get("strongest_counterexample"):
        c = appraisal["strongest_counterexample"]
        lines += ["", "## Strongest counterexample", "", f"{c['assertion']} — \"{c['excerpt']}\""]
    lines += ["", "## Venture engine reasoning", ""] + [f"- {r}" for r in assessment["reasons"]]
    lines += ["", "## Adversarial committee", ""] + [f"- {c['case']} ({c['stance']}, {c['severity']}): {c['argument']}"
                                                  for c in assessment["cases"]]
    lines += ["", "## Validation plan (proposed, not executed)", ""] + [f"1. {s}" for s in assessment["validation_plan"]]
    lines += ["", "## Provenance", "",
              f"- RailScout receipt `{inputs['railscout']['receipt_sha256']}` at `{inputs['organs']['railscout_head']}`",
              f"- WealthMachine engine at `{inputs['organs']['wmi_head']}`",
              f"- Wire packet `{inputs['packet']['id']}` sent under the kernel identity; assessment adapted under "
              f"the wealthmachine identity; execution authority {inputs['canonical']['assessment_execution_authority']}",
              f"- Signal: manifest {inputs['manifest_sha256']}",
              f"- Renderer {RENDERER}", ""]
    return "\n".join(lines)


def inputs_digest(inputs: dict) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _deliver(text: str, ctx: InvocationContext, name: str) -> Path:
    if ctx.deliver_root is None:
        raise CapabilityError("this body has no delivery root configured")
    folder = Path(ctx.deliver_root).resolve() / "ventures"
    folder.mkdir(parents=True, exist_ok=True)
    target, data = folder / f"{name}.md", text.encode("utf-8")
    if target.exists():
        if target.read_bytes() == data:
            return target
        raise CapabilityError(f"a different assessment already exists at {target.name}; nothing overwritten")
    temporary = folder / f".{target.name}.{os.getpid()}.tmp"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.link(temporary, target)
    temporary.unlink()
    return target


def _paths(params, ctx: InvocationContext) -> dict:
    try:
        roots = {k: _inside(Path(params[k]), ctx.read_roots) for k in ("railscout_root", "wmi_root", "manifest",
                                                                         "source_root")}
    except KeyError as exc:
        raise CapabilityError(f"missing parameter {exc}") from None
    if not (roots["railscout_root"] / "railscout" / "appraise.py").is_file():
        raise CapabilityError("railscout_root is not a RailScout checkout with the appraiser")
    if not (roots["wmi_root"] / "src" / "services" / "opportunity_intake.py").is_file():
        raise CapabilityError("wmi_root is not a WealthMachineIntelligence checkout")
    return roots


def assess(params, ctx: InvocationContext) -> dict:
    if ctx.deliver_root is None:
        raise CapabilityError("this body has no delivery root configured")
    p = _paths(params, ctx)
    manifest_bytes = p["manifest"].read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    receipt = _organ(_RAILSCOUT, manifest, str(p["railscout_root"]), str(p["source_root"]), cwd=p["railscout_root"])
    packet = packet_from_appraisal(receipt)
    assessment = _organ(_WEALTHMACHINE, packet, str(p["wmi_root"]), str(KERNEL_ROOT), cwd=p["wmi_root"])
    verdict, why = binding_verdict(receipt["appraisal"]["status"], assessment["go_no_go"])
    inputs = {"renderer": RENDERER, "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(), "railscout": receipt, "packet": packet,
              "assessment": assessment, "canonical": _canonical(packet, assessment),
              "binding": {"verdict": verdict, "why": why},
              "organs": {"railscout_head": _git_head(p["railscout_root"]), "wmi_head": _git_head(p["wmi_root"])},
              "paths": {k: str(v) for k, v in p.items()}}
    text = render(inputs)
    path = _deliver(text, ctx, f"venture-{receipt['receipt_sha256'][:16]}")
    return {"path": str(path), "sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text.encode()),
            "inputs": inputs, "inputs_digest": inputs_digest(inputs), "verdict": verdict,
            "railscout_status": receipt["appraisal"]["status"], "engine_verdict": assessment["go_no_go"],
            "manifest_sha256": inputs["manifest_sha256"]}


def status(params, ctx: InvocationContext) -> dict:
    """Sensor: has an assessment been delivered for this manifest's current receipt?"""
    manifest = _inside(Path(params["manifest"]), ctx.read_roots)
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    folder = Path(ctx.deliver_root).resolve() / "ventures" if ctx.deliver_root else None
    found = sorted(folder.glob("venture-*.md")) if folder and folder.is_dir() else []
    marker = f"manifest {digest}"
    for path in found:
        text = path.read_text(encoding="utf-8")
        if marker in text:
            verdict = text.split("**Binding verdict: ", 1)[1].split("**", 1)[0]
            return {"assessed": True, "verdict": verdict, "path": path.name, "manifest_sha256": digest}
    return {"assessed": False, "verdict": None, "path": None, "manifest_sha256": digest}


def verify_delivery(output: dict, deliver_root: Path | None) -> tuple[bool, str]:
    """Appraiser: the memo is the render of its receipt, and both organs reproduce the receipt."""
    if not isinstance(output, dict) or "inputs" not in output:
        return False, "receipt does not retain the assessment inputs"
    inputs = output["inputs"]
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
    paths = {k: Path(v) for k, v in inputs["paths"].items()}
    try:
        manifest_bytes = paths["manifest"].read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != inputs["manifest_sha256"]:
            return False, "the signal manifest changed since the assessment"
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        again = _organ(_RAILSCOUT, manifest, str(paths["railscout_root"]), str(paths["source_root"]),
                       cwd=paths["railscout_root"])
        if again != inputs["railscout"]:
            return False, "RailScout does not reproduce the receipted appraisal (sources or manifest changed)"
        if packet_from_appraisal(again) != inputs["packet"]:
            return False, "the packet is not the deterministic mapping of the appraisal"
        engine = _organ(_WEALTHMACHINE, inputs["packet"], str(paths["wmi_root"]), str(KERNEL_ROOT),
                        cwd=paths["wmi_root"])
    except (CapabilityError, OSError, ValueError) as exc:
        return False, f"organ re-run failed: {exc}"
    if any(engine[k] != inputs["assessment"][k] for k in STABLE_ASSESSMENT):
        return False, "WealthMachine does not reproduce the receipted assessment"
    if binding_verdict(again["appraisal"]["status"], engine["go_no_go"])[0] != inputs["binding"]["verdict"]:
        return False, "binding verdict is not the rule applied to the organ outputs"
    return True, "memo equals the render of the receipt; RailScout and WealthMachine reproduce it"
