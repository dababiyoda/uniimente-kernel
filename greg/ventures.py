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
The binding verdict is the WealthMachine verdict capped by the RailScout status and
by canonical fields the packet leaves unevidenced. ``governing_bottleneck`` is one of
those fields: it is mapped only from a source-bound failure the appraisal cites, never
from the engine's score or from the cheapest test. A "go" that outruns either gap is
delivered as ``needs_more_evidence``, with both verdicts shown.

Second rule, from the Mind (directive section 16): **a revenue figure may not outrun its
causal support.** When the signal carries an economics block, the mission first asks
GREG's own cognition (``cognition.solve``, read-only) for a revenue range (the estimation
family: factors, units, dominant uncertainty) and for causal support (the causal family,
identification-gated). The memo's revenue section is rendered only from those receipts:
no identified causal effect means an estimate is shown and no revenue conclusion is drawn.
The appraiser re-derives the section and checks every receipt against the ledger.

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

from adapters.daleobanks_opportunity import VERDICT_RANK as VERDICT_RANK
from adapters.daleobanks_opportunity import justified_verdict
from greg.capabilities import CapabilityError, InvocationContext, _inside

KERNEL_ROOT = Path(__file__).resolve().parents[1]
RENDERER = "greg.ventures/one-greg-1"
ORGAN_TIMEOUT_SECONDS = 60
NAMESPACE = uuid.UUID("2f0c6f86-3f1d-4b4e-9f2c-7a1e4c0d5b21")
_GOVERNING_LAYERS = frozenset({"proof", "trust", "eligibility", "routing", "settlement", "coordination"})

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


def _organ(script: str, stdin: dict, *args: str, cwd: Path, confined: bool = False) -> dict:
    """Run one organ in its own process: no GREG secrets, keys or ledger reach it.

    ``confined`` (a body with confined egress, #26): an appraisal needs no network, so the organ runs in a bubblewrap
    network namespace with no door at all, its checkouts read-only. Without namespaces nothing runs (fail closed)."""
    # A fresh bytecode cache per run: a stale .pyc (same size, same mtime second) must
    # never let a re-run execute code other than the organ's current source.
    with tempfile.TemporaryDirectory(prefix="greg-organ-pyc-") as pycache:
        env = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PYTHONHASHSEED": "0",
               "HOME": str(cwd), "LANG": "C.UTF-8", "PYTHONPYCACHEPREFIX": pycache}
        argv = [sys.executable, "-s", "-c", script, *args]
        if confined:
            from foundry.systems.relay_door import namespace_argv
            from greg.worker_isolation import WorkerIsolationError, _backend
            try:
                _backend(require_bubblewrap=True)
            except WorkerIsolationError as exc:
                raise CapabilityError(f"confined egress needs bubblewrap network namespaces here: {exc}") from None
            argv = namespace_argv(writable=[pycache], readonly=[cwd, *(a for a in args if Path(a).is_absolute())],
                                  chdir=cwd) + argv
        try:
            done = subprocess.run(argv, input=json.dumps(stdin), capture_output=True, text=True,
                                  timeout=ORGAN_TIMEOUT_SECONDS, cwd=cwd, env=env)
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
    challenging = [c for c in appraisal["claims"] if c["stance"] == "challenges"]
    sources = {s["id"]: s for s in appraisal["sources"]}
    cite = lambda c: (f"[source {sources[c['source_id']]['path']} sha256:{sources[c['source_id']]['sha256']} "
                      f"bytes {c['byte_start']}-{c['byte_end']}]")
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
        "evidence": [f"{c['assertion']} {cite(c)}" for c in supporting],
        "possible_offer": appraisal["candidate"]["current_form"],
        "monetization_paths": [],
        # Sourced counterevidence travels on the wire; the engine is not allowed to be
        # handed a packet from which the adverse case was silently removed.
        "risk_flags": [f"counterevidence: {c['assertion']} {cite(c)}" for c in challenging],
        "smallest_validation_action": appraisal["next_action"],
    }


def evidenced_governing_bottleneck(appraisal: dict) -> str:
    """The failure RailScout bound to source claims. No claim ids means the bottleneck is unstated."""
    failure = appraisal.get("failure") if isinstance(appraisal.get("failure"), dict) else {}
    layer, description, claim_ids = failure.get("layer"), failure.get("description"), failure.get("claim_ids")
    claims = appraisal.get("claims") if isinstance(appraisal.get("claims"), list) else []
    known = {claim.get("id") for claim in claims if isinstance(claim, dict)}
    if (isinstance(layer, str) and layer in _GOVERNING_LAYERS
            and isinstance(description, str) and description.strip()
            and isinstance(claim_ids, list) and claim_ids
            and all(isinstance(claim_id, str) and claim_id in known for claim_id in claim_ids)):
        return f"{layer}: {description.strip()}"
    return ""


def binding_verdict(railscout_status: str, wmi_verdict: str,
                    unresolved: list[str] | None = None,
                    evidence: list | None = None) -> tuple[str, str]:
    """A score may not outrun missing evidence, including an unmapped governing bottleneck.

    ``unresolved is None`` means the canonical gaps were not checked, so the bottleneck
    counts as unevidenced. Pass the adapter's list, including ``[]``, only after reading it.
    An empty evidence list is a gap, the same rule the organ-exchange verdict uses.
    """
    gaps = ["governing_bottleneck"] if unresolved is None else list(unresolved)
    if railscout_status != "READY_FOR_HUMAN_REVIEW":
        gaps.append(f"railscout:{railscout_status}")
    return justified_verdict(wmi_verdict, gaps, evidence)


class LedgerReader:
    """The canonical ledger, readable by record type and nothing else. The organ bridge reads the Mind's receipts;
    it is handed no ``record``, no ``append`` and no ledger object it could write through."""

    def __init__(self, journal):
        self.ledger = _Records(journal.ledger)


class _Records:
    __slots__ = ("_by_type",)

    def __init__(self, ledger):
        self._by_type = ledger.by_type

    def by_type(self, record_type: str):
        return self._by_type(record_type)


def cognition_receipts(ctx: InvocationContext, ids: dict) -> dict:
    """The latest valid CognitiveReceipt on the canonical ledger for each named problem; never fabricated."""
    from greg.cognition.settlement import _valid_receipt
    if ctx.journal is None:
        raise CapabilityError(f"{ctx.manifest.capability_id} needs the canonical ledger to read its cognition receipts")
    found = {}
    for record in ctx.journal.ledger.by_type("receipt"):
        output = (record.payload.get("result") or {}).get("output")
        if _valid_receipt(output) and output["problem_id"] in ids.values():
            found[output["problem_id"]] = output           # ledger order: the latest receipt wins
    receipts = {role: found.get(pid) for role, pid in ids.items()}
    missing = [role for role, r in receipts.items() if r is None]
    if missing:
        raise CapabilityError(f"no cognition receipt yet for {', '.join(missing)}; the cognition steps run first")
    return receipts


def revenue_conclusion(revenue: dict | None, causal: dict | None) -> dict:
    """A revenue figure may not outrun its causal support (the Mind's rule, applied by the organ bridge)."""
    if revenue is None or revenue.get("abstention_state") != "NONE":
        return {"kind": "none", "why": "no revenue figure is stated: the signal carries no estimate GREG could certify"}
    identified = bool(causal and causal.get("abstention_state") == "NONE"
                      and (causal.get("output") or {}).get("identified_conditionally") is True)
    if not identified:
        return {"kind": "conditional",
                "why": "an estimate is shown; no causal support for the offer producing it is identified, so no "
                       "revenue conclusion is drawn"}
    return {"kind": "stated", "why": "the estimate is supported by an identified (randomized) effect; it remains "
                                     "conditional on the stated identification assumptions"}


def _render_revenue(inputs: dict) -> list[str]:
    if "revenue" not in inputs:
        return []   # a memo receipted before the revenue section existed renders exactly as it was receipted
    receipts, conclusion = inputs.get("cognition") or {}, inputs["revenue"]
    lines = ["## Revenue (GREG's own cognition; read-only)", "", f"**{conclusion['kind']}** — {conclusion['why']}."]
    revenue, causal = receipts.get("revenue"), receipts.get("causal")
    if revenue and revenue.get("abstention_state") == "NONE":
        out, proof = revenue["output"], revenue.get("proof_artifact") or {}
        units = " ".join(f"{u}^{e}" if e != 1 else u for u, e in sorted((out.get("units") or {}).items())) or "units unstated"
        lines += ["", f"- Estimate: {out['low']:g} to {out['high']:g} {units} (central {out['central']:g}); an interval "
                      f"enclosure of the stated factors, not a probability",
                  f"- Dominant uncertainty: {proof.get('dominant_variable')}; cheapest evidence: {proof.get('cheapest_evidence')}",
                  f"- Receipt `{revenue['receipt_id']}` ({revenue['method']} {revenue['method_version']})"]
    elif revenue:
        lines += ["", f"- Estimate: abstained ({revenue.get('abstention_state')}): "
                      f"{'; '.join(revenue.get('missing_information') or [])}"]
    if causal:
        out = causal.get("output") or {}
        if causal.get("abstention_state") == "NONE" and out.get("identified_conditionally"):
            lines += [f"- Causal support: randomized difference in means {out['effect']:g}, identified conditionally on "
                      f"{', '.join((causal.get('proof_artifact') or {}).get('identification_assumptions', []))}",
                      f"- Receipt `{causal['receipt_id']}` ({causal['method']} {causal['method_version']})"]
        else:
            lines += [f"- Causal support: not identified ({causal.get('abstention_state')}); missing: "
                      f"{'; '.join(causal.get('missing_information') or []) or 'a verified identification design'}",
                      f"- Receipt `{causal['receipt_id']}`"]
    return lines + [""]


def _canonical_view(packet: dict, appraisal: dict, assessment: dict) -> dict:
    """Adapt the organ packet. A claim-bound failure is stated as governing_bottleneck for that
    adaptation only; the packet sent to the venture engine is left unchanged."""
    stated = evidenced_governing_bottleneck(appraisal)
    subject = dict(packet)
    if stated:
        subject["governing_bottleneck"] = stated
    canonical = _canonical(subject, assessment)
    if stated and "governing_bottleneck" not in canonical["packet_unresolved"]:
        canonical = {**canonical, "governing_bottleneck": stated}
    return canonical


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


def flip_condition(appraisal: dict, engine_verdict: str, verdict: str,
                   unresolved: list[str] | None = None) -> str:
    """Value of information: which evidence stands between this signal and a different verdict."""
    if verdict != engine_verdict:
        named = list(appraisal.get("missing") or [])
        for field in unresolved or []:
            if field not in named:
                named.append(field)
        subject = ", ".join(named) if named else "the contested topics"
        return (f"Evidencing {subject} is what stands between "
                f"this signal and the engine's '{engine_verdict}'. Smallest next step: {appraisal['next_action']}.")
    if appraisal["status"] == "READY_FOR_HUMAN_REVIEW":
        return f"Evidence is complete enough for your review; the decision is yours: {appraisal['next_action']}."
    return (f"Even with complete evidence the engine says '{engine_verdict}'; more evidence alone will not make "
            f"this a go. Change the offer, buyer or transaction, or retire the signal.")


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
             "", "## What would change the verdict", "", inputs["flip"], ""]
    lines += _render_revenue(inputs)
    lines += ["## Governing transaction", "", appraisal["transaction"], "",
             f"Failure layer: {appraisal['failure']['layer']} — {appraisal['failure']['description']}", "",
             "## Evidence (source bytes verified; assertions not independently verified)", ""]
    for c in appraisal["claims"]:
        lines.append(f"- {c['stance']} [{c['id']}, {c['kind']}] {c['assertion']} "
                     f"(`{c['source_id']}` bytes {c['byte_start']}-{c['byte_end']})")
    lines += ["", "## What is not evidenced", ""]
    lines += [f"- {m}" for m in appraisal["missing"]] or ["- nothing listed"]
    lines += [f"- canonical packet fields unresolved: {', '.join(inputs['canonical']['packet_unresolved']) or 'none'}"]
    if inputs["canonical"].get("governing_bottleneck"):
        lines += [f"- governing bottleneck mapped from the source-bound failure: {inputs['canonical']['governing_bottleneck']}"]
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
              *([f"- Economics: {inputs['economics_sha256'] or 'none stated'}"] if "economics_sha256" in inputs else []),
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
    confined = ctx.egress is not None
    receipt = _organ(_RAILSCOUT, manifest, str(p["railscout_root"]), str(p["source_root"]), cwd=p["railscout_root"],
                     confined=confined)
    packet = packet_from_appraisal(receipt)
    assessment = _organ(_WEALTHMACHINE, packet, str(p["wmi_root"]), str(KERNEL_ROOT), cwd=p["wmi_root"],
                        confined=confined)
    canonical = _canonical_view(packet, receipt["appraisal"], assessment)
    verdict, why = binding_verdict(receipt["appraisal"]["status"], assessment["go_no_go"],
                                   canonical["packet_unresolved"], packet.get("evidence"))
    receipts = cognition_receipts(ctx, params["cognition"]) if params.get("cognition") else None
    inputs = {"renderer": RENDERER, "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
              "railscout": receipt, "packet": packet,
              "assessment": assessment, "canonical": canonical,
              "binding": {"verdict": verdict, "why": why},
              "cognition": receipts,
              "revenue": revenue_conclusion((receipts or {}).get("revenue"), (receipts or {}).get("causal")),
              "flip": flip_condition(receipt["appraisal"], assessment["go_no_go"], verdict,
                                     canonical["packet_unresolved"]),
              "organs": {"railscout_head": _git_head(p["railscout_root"]), "wmi_head": _git_head(p["wmi_root"])},
              "paths": {k: str(v) for k, v in p.items()}}
    if "economics_sha256" in params:
        # the economics the revenue section is computed from (None: none stated); a memo from other economics is
        # a different memo, delivered beside it, never in its place
        inputs["economics_sha256"] = params["economics_sha256"]
    text = render(inputs)
    basis = inputs.get("economics_sha256")
    path = _deliver(text, ctx, f"venture-{receipt['receipt_sha256'][:16]}" + (f"-{basis[7:15]}" if basis else ""))
    return {"path": str(path), "sha256": hashlib.sha256(text.encode()).hexdigest(), "bytes": len(text.encode()),
            "inputs": inputs, "inputs_digest": inputs_digest(inputs), "verdict": verdict,
            "railscout_status": receipt["appraisal"]["status"], "engine_verdict": assessment["go_no_go"],
            "manifest_sha256": inputs["manifest_sha256"]}


def _same_economics(text: str, params: dict) -> bool:
    """A memo answers this mission only if it was computed from the economics the mission was signed with. A
    mission signed before economics were bound (no ``economics_sha256``) keeps matching by manifest alone; a memo
    rendered before they were bound states none."""
    if "economics_sha256" not in params:
        return True
    basis = params["economics_sha256"]
    if basis is None:
        return "- Economics: " not in text or "- Economics: none stated" in text
    return f"- Economics: {basis}\n" in text


def status(params, ctx: InvocationContext) -> dict:
    """Sensor: has an assessment been delivered for this manifest's current receipt and the signed economics?"""
    manifest = _inside(Path(params["manifest"]), ctx.read_roots)
    digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
    folder = Path(ctx.deliver_root).resolve() / "ventures" if ctx.deliver_root else None
    found = sorted(folder.glob("venture-*.md")) if folder and folder.is_dir() else []
    marker = f"manifest {digest}"
    for path in found:
        text = path.read_text(encoding="utf-8")
        if marker in text and _same_economics(text, params):
            verdict = text.split("**Binding verdict: ", 1)[1].split("**", 1)[0]
            return {"assessed": True, "verdict": verdict, "path": path.name, "manifest_sha256": digest}
    return {"assessed": False, "verdict": None, "path": None, "manifest_sha256": digest}


def verify_delivery(output: dict, deliver_root: Path | None, ledger=None, *, confined: bool = False) -> tuple[bool, str]:
    """Appraiser: the memo is the render of its receipt, and both organs reproduce the receipt."""
    if not isinstance(output, dict) or "inputs" not in output:
        return False, "receipt does not retain the assessment inputs"
    inputs = output["inputs"]
    if inputs.get("renderer") != RENDERER:
        return False, f"assessed by {inputs.get('renderer')}; this appraiser re-derives {RENDERER} only"
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
    if inputs["flip"] != flip_condition(inputs["railscout"]["appraisal"], inputs["assessment"]["go_no_go"],
                                        inputs["binding"]["verdict"],
                                        (inputs.get("canonical") or {}).get("packet_unresolved")):
        return False, "the stated verdict-change condition is not derived from the organ outputs"
    receipts = inputs.get("cognition") or {}
    # Every memo assessed since the revenue section carries a conclusion; one receipted before it carries neither a
    # conclusion nor cognition receipts, and states no revenue figure to hold to the rule.
    if (receipts or "revenue" in inputs) and \
            inputs.get("revenue") != revenue_conclusion(receipts.get("revenue"), receipts.get("causal")):
        return False, "the revenue conclusion is not the rule applied to the cognition receipts"
    from greg.cognition.settlement import _valid_receipt
    for role, receipt in receipts.items():
        if not _valid_receipt(receipt):
            return False, f"the {role} receipt is not a valid cognition receipt"
        if ledger is not None and not any(((r.payload.get("result") or {}).get("output") or {}).get("receipt_id")
                                          == receipt["receipt_id"] for r in ledger.by_type("receipt")):
            return False, f"the {role} receipt is not on the canonical ledger"
    paths = {k: Path(v) for k, v in inputs["paths"].items()}
    try:
        manifest_bytes = paths["manifest"].read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != inputs["manifest_sha256"]:
            return False, "the signal manifest changed since the assessment"
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        again = _organ(_RAILSCOUT, manifest, str(paths["railscout_root"]), str(paths["source_root"]),
                       cwd=paths["railscout_root"], confined=confined)
        if again != inputs["railscout"]:
            return False, "RailScout does not reproduce the receipted appraisal (sources or manifest changed)"
        if packet_from_appraisal(again) != inputs["packet"]:
            return False, "the packet is not the deterministic mapping of the appraisal"
        engine = _organ(_WEALTHMACHINE, inputs["packet"], str(paths["wmi_root"]), str(KERNEL_ROOT),
                        cwd=paths["wmi_root"], confined=confined)
        recomputed = _canonical_view(inputs["packet"], again["appraisal"], engine)
    except (CapabilityError, OSError, ValueError) as exc:
        return False, f"organ re-run failed: {exc}"
    if any(engine[k] != inputs["assessment"][k] for k in STABLE_ASSESSMENT):
        return False, "WealthMachine does not reproduce the receipted assessment"
    stored = inputs.get("canonical") or {}
    if recomputed["packet_unresolved"] != stored.get("packet_unresolved"):
        return False, "canonical unresolved fields are not the adapters' result"
    if recomputed.get("governing_bottleneck") != stored.get("governing_bottleneck"):
        return False, "governing bottleneck is not the evidenced mapping"
    if binding_verdict(again["appraisal"]["status"], engine["go_no_go"],
                       recomputed["packet_unresolved"], inputs["packet"].get("evidence"))[0] != inputs["binding"]["verdict"]:
        return False, "binding verdict is not the rule applied to the organ outputs"
    return True, "memo equals the render of the receipt; RailScout and WealthMachine reproduce it"
