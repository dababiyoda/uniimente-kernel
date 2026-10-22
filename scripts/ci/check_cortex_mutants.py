"""Mutation check for the cortex and GREG-path authority, evidence and budget invariants.

    python scripts/ci/check_cortex_mutants.py

Each mutant removes one safeguard the build prompt requires (a failed gate
cannot be outranked, predictions cannot settle competence, victim protection is
human-led, ...). The cortex tests must fail for every mutant. Mutants are
applied to a scratch copy of the repository, never to the working tree.
Exit status 1 if any mutant survives or no longer applies.
"""
from __future__ import annotations

import os
import queue
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS = ["tests/unit/test_cortex_gates_genome.py", "tests/unit/test_cortex_routes.py",
         "tests/unit/test_cortex_pipeline.py"]
MUTANTS = [
    ("receipt claims authority", "cortex/routing.py",
     '"authority_created": False,\n            "execution_authority": "none",\n        }\n        body["receipt_id"]',
     '"authority_created": True,\n            "execution_authority": "none",\n        }\n        body["receipt_id"]'),
    ("rank ignores failed gates", "cortex/gates.py",
     "eligible = [o for o in options if reports[o.option_id].all_pass]", "eligible = list(options)"),
    ("prediction settles competence", "cortex/memory.py",
     "if kind in REFUSED_PROVENANCE and outcome_status in SETTLING:", "if False:"),
    ("financial recommended", "cortex/routing.py",
     'if not ceiling_ok or consequence_rank(geometry.consequence_class) >= consequence_rank("financial"):',
     "if False:"),
    ("model-generated DAG identifies", "cortex/organs/evidence_causal.py",
     'if basis == "model_generated":', "if False:"),
    ("witness check skipped", "cortex/organs/formal.py",
     'if not ok:\n                    discrepancies.append(f"{kind} witness',
     'if False:\n                    discrepancies.append(f"{kind} witness'),
    ("undecided witness counts as agreement", "cortex/organs/formal.py",
     "if res not in (z3.sat, z3.unsat):", "if False:"),
    ("exhausted timeout reported as inconclusive", "cortex/organs/formal.py",
     'return "TIMEOUT" if "timeout" in reason or "canceled" in reason else "INCONCLUSIVE"',
     'return "TIMEOUT" if "timeout" in reason else "INCONCLUSIVE"'),
    ("exit ignores geometry", "cortex/evaluation/scoring.py",
     "reasons.extend(_geometry_reasons(routed, arm, name))", "pass"),
    ("exit ignores cost and latency", "cortex/evaluation/scoring.py",
     "reasons.extend(_resource_reasons(routed, arm, name))", "pass"),
    ("optimality certificate skipped", "cortex/organs/formal.py",
     "certifier, res = check(domain + list(exprs.values()) + [better])", "certifier, res = None, z3.unsat"),
    ("protection gaps ignored", "cortex/routing.py",
     "set(HUMAN_LED_PROTECTION) or protection.gaps):", "set(HUMAN_LED_PROTECTION)):"),
    ("unknown harm treated as safe", "cortex/contracts.py",
     'if lvl in ("high", "medium", "unknown")]', 'if lvl in ("high", "medium")]'),
    ("receipt hides the strongest counterargument", "cortex/routing.py",
     "strongest = ({", "strongest = None and ({"),
    ("coercive intervention accepted", "cortex/organs/deterrence.py",
     "            if kind in PROHIBITED_KINDS:", "            if False:"),
    ("hard-harm intervention accepted", "cortex/organs/deterrence.py",
     "            if hard:\n", "            if False:\n"),
    ("severity mislabelled as certainty", "cortex/organs/deterrence.py",
     '"sanction_usd": "severity",', '"sanction_usd": "certainty",'),
    ("external deterrence not handed off", "cortex/routing.py",
     "        if deterrent is not None:\n", "        if False:\n"),
    ("quote check skipped", "cortex/organs/semantic.py",
     "if not isinstance(q, str) or not q.strip() or not any(", "if False and not any("),
    ("disabled family eligible", "cortex/genome.py",
     "if not profile.enabled:\n                reasons.append", "if False:\n                reasons.append"),
    ("non-permission record grants", "cortex/gates.py",
     "return self.origin in PERMISSION_BEARING.get(self.kind, ())", "return True"),
    ("stale evidence accepted", "cortex/organs/evidence_causal.py",
     "(today - observed).days > max_age:", "(today - observed).days > 10**9:"),
    ("protection not handed off", "cortex/routing.py",
     "if protection.relevant and (set(protection.required_actions) & set(HUMAN_LED_PROTECTION) or protection.gaps):",
     "if False:"),
    ("verifier ignores protection", "cortex/organs/adversarial.py",
     'if protection is not None and getattr(protection, "relevant", False) and proposed_disposition == "recommend"',
     "if False"),
    ("preserved evidence open access", "cortex/contracts.py",
     'and "evidence_preservation" in actions and access in ("unknown", "internal"):', "and False:"),
    ("receipt drops protection", "cortex/routing.py",
     '"protection": None if protection is None or not protection.relevant else {',
     '"protection": None if True else {'),
]

# GREG path (directive section 15): "deliberately remove a permission check, drop a constraint,
# relabel UNKNOWN, replace evidence, duplicate settlement, or enable a paid fallback. The
# corresponding tests must fail."
GREG_TESTS = ["tests/unit/test_greg_cortex_bridge.py", "tests/unit/test_cortex_formal_engines.py",
              "tests/unit/test_cortex_schedule_composition.py", "tests/integration/test_greg_cortex_mission.py"]
GREG_MUTANTS = [
    ("permission check removed: signed target scope", "greg/cognition/cortex.py",
     'if not ctx.manifest.capability_id.startswith("cognition.") or not ctx.target.startswith("cognition:"):',
     "if False:"),
    ("permission check removed: founder detach not projected", "greg/cognition/bridge.py",
     "        ok, why = registry.usable(cid)\n        if not ok:\n            out[key]",
     "        ok, why = True, ''\n        if not ok:\n            out[key]"),
    ("constraint dropped: extracted deadline", "cortex/organs/schedule_extraction.py",
     'if jobs[j].get("deadline") is not None:', "if False:"),
    ("constraint dropped: CP-SAT encoding", "cortex/organs/cpsat.py",
     "for c in spec.constraints if constraints is None else constraints:",
     "for c in (spec.constraints[1:] if constraints is None else constraints):"),
    ("UNKNOWN relabelled: unknown harm as none", "greg/cognition/bridge.py",
     '"critical": 1.0, "unknown": None}', '"critical": 1.0, "unknown": 0.0}'),
    ("UNKNOWN relabelled: FEASIBLE as OPTIMAL", "cortex/organs/cpsat.py",
     'optimal = name == "OPTIMAL"', "optimal = True"),
    ("UNKNOWN relabelled: exhausted latency budget ignored", "cortex/organs/formal.py",
     's.set("timeout", max(1, ms_left(until)))', 's.set("timeout", spec.timeout_ms)'),
    ("evidence replaced: receipt content address unchecked", "greg/cognition/bridge.py",
     "if identity != cortex_digest(body):", "if False:"),
    ("evidence replaced: verifier re-check of returned assignments removed", "cortex/organs/adversarial.py",
     "    _recheck_formal_answers(payload, results, add)\n", "    pass\n"),
    ("authority claim accepted from the worker", "greg/cognition/bridge.py",
     'if receipt["authority_created"] is not False or receipt["execution_authority"] != "none":', "if False:"),
    # Converged #145 settlement: a revision is appended only when the claim's outcome changed.
    ("duplicate settlement", "greg/cognition/settlement.py",
     'if prior is None or digest({k:v for k,v in prior.payload.items() if k != "supersedes"}) != digest(outcome):',
     "if True:"),
    ("paid fallback enabled: purchased inference accepted", "greg/cognition/bridge.py",
     'if receipt["expenditure"]["usd"] != 0:', "if False:"),
    ("paid fallback enabled: non-founder provider order selects a model", "greg/cognition/bridge.py",
     'if not model_config or "ollama" not in model_config.get("order", []) or not model_config.get("ollama_model"):',
     'if not model_config or not model_config.get("ollama_model"):'),
    ("misclassified consequence: declared harm cannot raise the class", "cortex/routing.py",
     'implied = "financial" if (harm.levels["financial"] in ("high", "critical") or harm.hard_violations()) else None',
     "implied = None"),
    ("zero solver budget still solves", "cortex/routing.py",
     "elif set(FORMAL_ENGINES) & set(selected) and limits.max_solver_calls < 1:", "elif False:"),
]
# Founder correction 2026-10-01 (#144): open-source engines are supply, GREG's certificate is the control.
OSS_TESTS = ["tests/unit/test_greg_open_source_genesis.py", "tests/unit/test_greg_linear_genesis.py",
             "tests/unit/test_greg_cognition.py", "tests/unit/test_greg_license_qualification.py",
             "tests/unit/test_greg_document_text.py"]
OSS_MUTANTS = [
    # license qualification (directive 2026-10-22, 5.3 and 6): legally qualified is a separate state
    ("an uncleared license still auto-attaches", "greg/genesis.py",
     "allowed = (not cognition and licensed", "allowed = (not cognition and True"),
    ("an engine dependency attaches whatever its license", "greg/genesis.py",
     "allowed = (licensed and mission.spec", "allowed = (True and mission.spec"),
    ("an unclassified or restricted license is cleared", "greg/licensing.py",
     "cleared = ORDER.index(worst) <= ORDER.index(CLEARED_UP_TO)", "cleared = True"),
    ("AND takes the most permissive term", "greg/licensing.py",
     "        return _worst(values)\n\n    def disjunction():", "        return _best(values)\n\n    def disjunction():"),
    ("a card without an assessment is cleared", "greg/licensing.py",
     'return False, "no license assessment on its Mechanism Card"', 'return True, ""'),
    ("a stricter License field beside a classifier is ignored", "greg/licensing.py",
     "ORDER.index(text_class) > ORDER.index(cls):", "False:"),
    # document.text (directive 2026-10-22): an acquired PDF reader qualified on GREG's own PDFs; binary licenses
    ("the frozen oracle accepts any extraction", "greg/genesis.py",
     'if got != case["expected"]:', "if False:"),
    ("a binary under a not-open license attaches itself", "greg/licensing.py",
     'assessment.get("class") in (NETWORK_COPYLEFT, NOT_OPEN)', "False"),
    ("DEP-5 'and' takes the most permissive license", "greg/licensing.py",
     "        best.append(_worst(classes))", "        best.append(_best(classes))"),
    ("a DEP-5 license definition paragraph is read as applying", "greg/licensing.py",
     'if "license" in fields and (index == 0 or "files" in fields):', 'if "license" in fields:'),
    ("a phrase is judged on the receipt's bounded prefix", "greg/genesis.py",
     '"derive": documents.find_phrase,', ""),
    ("a binary's output is unbounded", "greg/genesis.py",
     "if len(proc.stdout) > mechanisms.MAX_OUTPUT:", "if False:"),
    ("a network-copyleft term beside an unclassified one is not held", "greg/licensing.py",
     'return [t for t in terms if t["class"] in (NETWORK_COPYLEFT, NOT_OPEN)]', "return []"),
    ("certificate skips edge feasibility", "greg/cognition/network.py",
     "if exact[b] > exact[a] + w + tolerance(exact[a] + w):", "if False:"),
    ("certificate trusts claimed unreachability", "greg/cognition/network.py",
     "        if b not in reached:\n            raise CertificateError", "        if False:\n            raise CertificateError"),
    ("flow certificate skips the residual graph", "greg/cognition/network.py", "if sink in side:", "if False:"),
    ("negative weights reach the engine", "greg/cognition/network.py", "    if value < 0:", "    if False:"),
    ("changed package files survive restart", "greg/genesis.py",
     'if mechanisms.digest(dist, candidate.digest_paths)[0] != manifest.provenance.get("package_digest"):',
     "if False:"),
    ("repair re-admits the package that failed in service", "greg/genesis.py",
     '            if repair and repair.get("capability_id") == manifest.capability_id:',
     "            if False:"),
    ("engine imported from an unqualified location", "greg/mechanisms.py",
     "if root not in module_file.parents:", "if False:"),
    ("#140 graph verifier accepts a longer route", "greg/cognition/verification.py",
     'checks["path_optimal"] = data["goal"] in best and', 'checks["path_optimal"] = True or'),
    ("#140 graph verifier accepts a false no-route", "greg/cognition/verification.py",
     'checks["unreachable_confirmed"] = data["goal"] not in best', 'checks["unreachable_confirmed"] = True'),
    ("LP certificate skips the duality gap", "greg/cognition/linear.py",
     "    if not _close(primal, dual, primal):", "    if False:"),
    ("LP certificate ignores multiplier signs", "greg/cognition/linear.py",
     "if any(y > TOLERANCE for y in y_ub) or", "if False and any(y > TOLERANCE for y in y_ub) or"),
    ("LP certificate skips inequality feasibility", "greg/cognition/linear.py",
     "        if sum(a * v for a, v in zip(F(row), x)) > Fraction(b) + TOLERANCE * (1 + abs(Fraction(b))):",
     "        if False:"),
    ("an unproved engine status closes a mission", "greg/cognition/linear.py",
     '        return {"certified": False, "status": claim["status"],\n                "why": "the engine reports no optimum and gives',
     '        return {"certified": True, "status": claim["status"],\n                "why": "the engine reports no optimum and gives'),
    ("a plan that meets every limit is reported as no plan", "greg/cognition/linear.py",
     "    if least <= threshold:                                   # a plan meets every limit", "    if False:"),
    ("a bounded objective is reported as having no limit", "greg/cognition/linear.py",
     "    if rate >= -TOLERANCE * (1 + max(", "    if False and rate >= -TOLERANCE * (1 + max("),
    ("a direction may break a limit", "greg/cognition/linear.py",
     "        if sum(Fraction(a) * v for a, v in zip(row, d)) > TOLERANCE * scale:", "        if False:"),
    ("an engine's 'no plan exists' closes without the elastic proof", "greg/genesis.py",
     '            if answer.get("follow_up") and spec.get("follow_up"):\n                # The engine',
     '            if False:\n                # The engine'),
    ("console attaches a capability no ask names", "greg/console.py",
     "if capability_id not in {c[\"capability_id\"] for c in _attachable(open_asks.get(request_id, {}))} | waiting:",
     "if False:"),
]

# Frontier leap 2026-10-13 (RECOMBINE, #164): a construction is controlled by its own certificate and lifecycle.
RECOMBINE_TESTS = ["tests/unit/test_greg_recombine.py"]
RECOMBINE_MUTANTS = [
    ("a portfolio that skips a prerequisite is certified", "greg/recombine.py",
     "    if missing:\n        raise ReductionError(f\"the chosen set is not closed", "    if False:\n        raise ReductionError(f\"the chosen set is not closed"),
    ("a portfolio below the funding bound is certified", "greg/recombine.py",
     "    if profit != gain - funded:", "    if False:"),
    ("funding along a made-up edge is accepted", "greg/recombine.py",
     "        elif (u, v) not in requires:", "        elif False:"),
    ("repair re-admits the construction that failed in service", "greg/genesis.py",
     'if repair and repair.get("capability_id") == manifest.capability_id:\n            self._route(deficit_id, "constructed"',
     'if False:\n            self._route(deficit_id, "constructed"'),
    ("a founder-detached construction is re-attached", "greg/genesis.py",
     'if self.registry.state.get(manifest.capability_id) == "DETACHED":\n            self._route(deficit_id, "constructed"',
     'if False:\n            self._route(deficit_id, "constructed"'),
    ("a construction that fails its oracle is registered", "greg/genesis.py",
     'if not passed:\n            self._route(deficit_id, "constructed", "failed qualification"',
     'if False:\n            self._route(deficit_id, "constructed", "failed qualification"'),
    ("an engine fault through a construction leaves the engine attached", "greg/genesis.py",
     'and self.registry.state.get(engine_id) == "ATTACHED":', "and False:"),
    ("changed reduction code survives restart", "greg/genesis.py",
     'elif recombine.chain_digest(found[0]) != origin["chain_digest"]:', "elif False:"),
    ("a construction outlives its engine's attach", "greg/recombine.py",
     "            if not ok:\n                raise CapabilityError(f\"capability refused: composed capability's engine",
     "            if False:\n                raise CapabilityError(f\"capability refused: composed capability's engine"),
    ("staffing certificate skips the deficiency bound", "greg/recombine.py", "    if staffed != bound:", "    if False:"),
    ("matching certificate skips the deficiency bound", "greg/recombine.py",
     'if size != len(p["right"]) - (len(U) - len(N)):', "if False:"),
    ("crash plan cost is not checked against the certified optimum", "greg/recombine.py",
     "if abs(Fraction(cost) - target) > Fraction(1, 10**6) * max(1, abs(cost)):", "if False:"),
    ("an infeasibility chain is not checked", "greg/recombine.py",
     "if not chain or any([a, b] not in p[\"precedences\"] for a, b in zip(chain, chain[1:])):", "if False:"),
]

# 2026-10-14: the Mind names constructible deficits, uses attached constructions, and repairs them.
MIND_CONSTRUCTION_TESTS = ["tests/integration/test_greg_mind_constructs_capability.py"]
MIND_CONSTRUCTION_MUTANTS = [
    ("the Mind uses a construction that is not attached", "greg/cognition/compiler.py",
     "and registry.usable(m.capability_id)[0]]", "]"),
    ("the deficit names an unbuildable geometry label", "greg/cognition/compiler.py",
     "        if buildable:\n", "        if False:\n"),
    ("a construction's fault is charged to cognition, not repaired", "greg/missions.py",
     'if is_capability_fault(formed, detail, failure_class):\n                        self.capability_faults',
     'if False:\n                        self.capability_faults'),
    ("attaching the engine never forms the construction", "greg/missions.py",
     'if self.genesis.construction_ready(b["function"]):', "if False:"),
    ("the construction awaiting attach is hidden behind the old ask", "greg/missions.py",
     "                                              awaiting=bool(waiting))",
     "                                              awaiting=False)"),
    ("a formed-capability fault waits on the founder while blocked", "greg/missions.py",
     'if failing and self.capability_faults and m.blocker["type"] != "human_work":', "if False:"),
    ("the appraiser cannot see formed capabilities", "greg/appraisal.py",
     'capability_registry=_formed_registry(journal, request["workspace"])', "capability_registry=None"),
    ("restore writes to the appraiser's read-only ledger", "greg/genesis.py",
     'if getattr(self, "_recording", True):', "if True:"),
]

# 2026-10-14: governed recovery (opossum half-open, mutated) and the re-escalation fixes it exposed.
RECOVERY_TESTS = ["tests/integration/test_greg_capability_recovery.py"]
RECOVERY_MUTANTS = [
    ("a quarantined capability is probed before its backoff", "greg/genesis.py",
     "            if now < since + wait:\n", "            if False:\n"),
    ("a passing probe does not restore eligibility", "greg/genesis.py",
     '            if passed:\n                self.registry.set_state(cid, "VERIFIED")',
     '            if False:\n                self.registry.set_state(cid, "VERIFIED")'),
    ("flapping never stops recovery", "greg/genesis.py",
     "if len(faults) > RECOVERY_MAX_QUARANTINES", "if False"),
    ("constructions are probed before their engines", "greg/genesis.py",
     'key=lambda m: (m.provider.startswith("composed:"), m.capability_id)',
     'key=lambda m: (not m.provider.startswith("composed:"), m.capability_id)'),
    ("a construction's probe cannot reach its recovered engine", "greg/genesis.py",
     'if capability_id == self._engine_id and self.state.get(capability_id) in ("ATTACHED", "VERIFIED"):',
     'if capability_id == self._engine_id and self.state.get(capability_id) == "ATTACHED":'),
    ("a recovered capability is never offered back to its mission", "greg/missions.py",
     "                if fresh:", "                if False:"),
    ("an identical re-block after an unblock is swallowed", "greg/missions.py",
     'key=[m.mission_id, blocker, self._generation(m, "mission.unblocked")])', "key=[m.mission_id, blocker])"),
    ("a recorded qualification is re-run on the same deficit", "greg/genesis.py",
     '            if prior is not None:\n                self._route(deficit_id, "installed_package"',
     '            if False:\n                self._route(deficit_id, "installed_package"'),
]

# 2026-10-14 installed-body merge: appends verify only new history (e2440a6); a Gate commit verifies all of it.
COMMIT_CHAIN_TESTS = ["tests/unit/test_consequence_gate.py", "tests/unit/test_ledger_incremental_verification.py"]
COMMIT_CHAIN_MUTANTS = [
    ("a Gate commit trusts the incremental check on altered history", "provenance/ledger.py",
     "ok, reason = self.verify_chain() if record_type in COMMIT_RECORD_TYPES else self.verify_incremental()",
     "ok, reason = self.verify_incremental()"),
]

# 2026-10-14 installed-body merge (#137 verifier): a test-key closure is structural evidence, never the founder's path.
FOUNDER_TIER_TESTS = ["tests/unit/test_greg_founder_tier.py", "tests/unit/test_greg_business_case.py",
                      "tests/unit/test_developmental_inheritance.py"]
FOUNDER_TIER_MUTANTS = [
    ("a structural closure moves the founder's path", "greg/path.py",
     "    met = bool(structural and passed)\n", "    met = bool(structural)\n"),
    ("an unattested key reaches the founder tier", "greg/metrics.py",
     "        elif key not in attested:\n            why = NOT_FOUNDER_TIER\n",
     "        elif False:\n            why = NOT_FOUNDER_TIER\n"),
    ("an attestation reaches back to earlier missions", "greg/metrics.py",
     "        elif attested[key] > seq[event.event_id]:", "        elif False:"),
    ("the CLI attests an unprotected key", "greg/cli.py",
     "    if passphrase is None and require:\n        raise BodyError(NO_FOUNDER_TIER)",
     "    if False:\n        raise BodyError(NO_FOUNDER_TIER)"),
    # #138 port (673726a, on the one rule): N1 and N2 move the path only at the founder tier.
    ("N1 counts a test-key VEPMC closure", "greg/path.py",
     "    passed, refused = _at_founder_tier(journal, {m: [m] for m in counted})\n",
     "    passed, refused = counted, {}\n"),
    ("N2 counts a test-key genesis closure", "greg/path.py",
     '    passed, refused = _at_founder_tier(journal, {c["mission_id"]: [c["mission_id"]] for c in closures})\n',
     '    passed, refused = [c["mission_id"] for c in closures], {}\n'),
]

# The VEPMC row's own label, through the real product path (a supervised body, both key kinds).
FOUNDER_TIER_BODY_TESTS = ["tests/integration/test_greg_vepmc_path.py"]
FOUNDER_TIER_BODY_MUTANTS = [
    ("a VEPMC row labels itself founder-tier without its signer's attestation", "greg/metrics.py",
     "FOUNDER_TIER if tier.get(\"tier\") == FOUNDER_TIER else STRUCTURAL_CANDIDATE",
     "FOUNDER_TIER"),
]

# 2026-10-14 installed-body review: closure integrity. Each guard below was a reproduced defect.
CLOSURE_INTEGRITY_TESTS = ["tests/unit/test_greg_closure_integrity.py", "tests/unit/test_greg_human_work_latency.py",
                           "tests/unit/test_greg_capabilities.py"]
CLOSURE_INTEGRITY_MUTANTS = [
    ("the appraiser trusts the engine's asks instead of the signed cone", "greg/appraisal.py",
     "                if (outside or human) and not _approved_before(",
     "                if False and not _approved_before("),
    ("the appraiser accepts an approval no founder DECISION carries", "greg/appraisal.py",
     '                and _decision_signed(journal, ledger, seq, answer[0], answer[1], data["request_id"], at_seq)):',
     "                and True):"),
    ("the appraiser counts an answer row the mission fold does not", "greg/appraisal.py",
     '                if held is None or held.get("command_digest") != e.payload.get("command_digest"):',
     "                if False:"),
    ("a signed pre-approval admits every strategy of its capability and class", "greg/missions.py",
     '        p["action_id"] == strategy["action_id"] and p["capability"] == manifest.capability_id\n'
     '        and p["target"] == strategy["target"] and p["consequence_class"] == manifest.consequence_class\n',
     '        p["capability"] == manifest.capability_id\n'
     '        and p["consequence_class"] == manifest.consequence_class\n'),
    ("a handoff picks the file fs.write overwrites", "greg/capabilities.py",
     "    if ctx.target != named:", "    if False:"),
    ("N3 counts a statement GREG wrote", "greg/path.py",
     '        missing += [f"greg_wrote_human_evidence:{aid}" for aid in _greg_wrote_human_evidence(journal, mid, spec)]\n'
     '        human = [',
     "        human = ["),
    ("N3 counts a declined step as observed work", "greg/path.py",
     '        if [h["request_id"] for h in human if not withdrawn.get(h["request_id"], "").startswith(OBSERVED)]:',
     '        if [h["request_id"] for h in human if h["request_id"] not in withdrawn]:'),
    ("an external node passes on its ledger predicate alone", "greg/path.py",
     '            if node["evidence_source"] == "external" and passed and not measured.get("external_evidence"):',
     "            if False:"),
    ("a decision closes a scope renewal", "greg/missions.py",
     '        if request["kind"] in NOT_ANSWERABLE:\n            raise MissionError(NOT_ANSWERABLE[request["kind"]])',
     '        if False:\n            raise MissionError(NOT_ANSWERABLE[request["kind"]])'),
    ("only fs.read deliverables are noticed early", "greg/missions.py",
     '            if manifest is None or manifest.consequence_class != "read_only" or not isinstance(path, str):',
     '            if sensor.get("capability") != "fs.read" or not isinstance(path, str):'),
    ("an SOP run keeps the taught directory in its signed text", "greg/sop.py",
     '            if prefix and "/" in value and not _names_directory(prefix.group(1), value):',
     "            if False:"),
    ("a signing command without a key crashes", "greg/cli.py",
     '    if not getattr(args, "key", None):\n        raise BodyError(f"{what} needs your founder key',
     '    if False:\n        raise BodyError(f"{what} needs your founder key'),
]

# 2026-10-15: capability formation is perception for Goal Gravity (a blocked goal wakes when what it waits on changes).
CAPABILITY_PERCEPTION_TESTS = ["tests/integration/test_greg_capability_wakes_goal.py"]
CAPABILITY_PERCEPTION_MUTANTS = [
    ("a capability change is invisible to Goal Gravity", "greg/goal_gravity.py",
     'elif t in ("greg.capability.registered", "greg.capability.state"):', "elif False:"),
    ("a blocked construction does not perceive its engine", "greg/goal_gravity.py",
     "        if function in (waiting, engine):", "        if function == waiting:"),
    ("a capability state is flattened to available or not", "greg/goal_gravity.py",
     'rec.hash, p["state"], "attributed")', 'rec.hash, p["state"] != "QUARANTINED", "attributed")'),
]

GOAL_FORMATION_TESTS = ["tests/integration/test_greg_goal_requests_formation.py"]
GOAL_FORMATION_MUTANTS = [
    ("a goal's formation request rides the mission's auto_attach", "greg/genesis.py",
     "request.\n        if self._form_only:", "request.\n        if False:"),
    ("a goal's formation request commissions the builder", "greg/genesis.py",
     "        if self._form_only:\n            self._route(deficit_id, \"builder\"",
     "        if False:\n            self._route(deficit_id, \"builder\""),
    ("a goal does not perceive the formation it asked for", "greg/goal_gravity.py",
     "            out.add((p[\"mission_id\"], p[\"function\"]))\n    return sorted(out)",
     "            out.add((p[\"mission_id\"], p[\"function\"]))\n    return []"),
    ("an attached implementation never closes the goal's deficit", "greg/goal_gravity.py",
     "        serving = genesis.find_attached(p[\"function\"])\n        if serving is None:",
     "        serving = genesis.find_attached(p[\"function\"])\n        if True:"),
    ("a function requirement never reads present", "greg/goal_gravity.py",
     "        if version == FUNCTION_VERSION:", "        if False:"),
    ("a stopped goal still asks for formation", "greg/goal_gravity.py",
     "        if gid not in facts.admitted or facts.stopped(gid) is not None:\n            continue\n        state",
     "        if gid not in facts.admitted:\n            continue\n        state"),
]

PORTFOLIO_WORDS_TESTS = ["tests/unit/test_greg_portfolio_words.py"]
PORTFOLIO_WORDS_MUTANTS = [
    ("a cost is read as earnings", "greg/templates.py",
     'value[m["name"]] = -amount if m["verb"].lower() == "costs" else amount', 'value[m["name"]] = amount'),
    ("an unread portfolio sentence is silently dropped", "greg/templates.py",
     "    if unread:\n        raise ValueError(\"GREG could not read: \" + \"; \".join(repr(u[:80]) for u in unread[:5])"
     "\n                         + \". Write 'Offer1",
     "    if False:\n        raise ValueError(\"GREG could not read: \" + \"; \".join(repr(u[:80]) for u in unread[:5])"
     "\n                         + \". Write 'Offer1"),
    ("a prerequisite with no value is accepted", "greg/templates.py",
     "    if unknown:\n        raise ValueError(f\"{', '.join(unknown)}", "    if False:\n        raise ValueError(f\"{', '.join(unknown)}"),
    ("the planner never reads a portfolio", "greg/planner.py",
     "if PORTFOLIO.search(text) and PORTFOLIO_NEEDS.search(text):", "if False:"),
]

BUDGETED_TESTS = ["tests/unit/test_greg_budgeted_selection.py"]
BUDGETED_MUTANTS = [
    ("a head that searches in rounds is run as a single call", "greg/recombine.py",
     "        if path[0].rounds:\n            return in_rounds(", "        if False:\n            return in_rounds("),
    ("the proof tree need not partition the plans", "greg/recombine.py",
     'if sorted(node.get("in", [])) != sorted(fix_in) or sorted(node.get("out", [])) != sorted(fix_out):',
     'if False:'),
    ("a branch closed by its bound is not checked against the answer", "greg/recombine.py",
     "            if bound > profit:\n                raise ReductionError(\"a branch closed by its bound",
     "            if False:\n                raise ReductionError(\"a branch closed by its bound"),
    ("a node's funding certificate is not re-proved", "greg/recombine.py",
     "node_answer = certify_selection(normalize_selection(sub), {",
     "node_answer = (lambda q, a: a)(normalize_selection(sub), {"),
    ("a rounds reduction may sit inside a chain", "greg/recombine.py",
     "    if any(r.rounds for r in path[1:]):", "    if False:"),
    ("a stated budget is ignored", "greg/templates.py",
     'function = "selection.budgeted" if "budget" in params else "selection.closure"', 'function = "selection.closure"'),
]

# Cortex 0.2.2: the Seed Cortex 0.1.6 repairs ported onto this line (PR #167 -> #184). Each guard must be load-bearing.
PORT_TESTS = ["tests/unit/test_cortex_seed_ports.py", "tests/unit/test_greg_seed_port_paths.py"]
PORT_MUTANTS = [
    ("settlement matches the method name only", "cortex/memory.py",
     "        if key not in selected and key not in ran:\n",
     "        if method not in [k.split(\"@\")[0] for k in [*selected, *ran]]:\n"),
    ("a route that never ran settles", "cortex/memory.py",
     "if outcome_status in SETTLING and key not in ran:", "if False:"),
    ("a superseded lead is not counted as run", "cortex/memory.py",
     ' + list(receipt["route"].get("attempts") or [])', ""),
    ("a tampered receipt settles", "cortex/memory.py",
     'if unsigned.pop("receipt_id", None) != digest(unsigned):', "if False:"),
    ("one receipt settles a method many times", "cortex/memory.py",
     "        if outcome_status in SETTLING and any(\n", "        if False and any(\n"),
    ("a composed part settles under the whole-problem class", "cortex/memory.py",
     '        geometry = (receipt["route"].get("part_geometries") or {}).get(key) or geometry\n', ""),
    ("reorder reads the whole-problem cell", "cortex/memory.py",
     'cell = (part_geometries or {}).get(key) or geometry.epistemic_class or "unresolved"',
     'cell = geometry.epistemic_class or "unresolved"'),
    ("a cap-dropped route is called not required", "cortex/routing.py",
     "dropped_by_cap = eligible_parts[MAX_COMPOSITION:]", "dropped_by_cap = []"),
    ("an unanswered part is recommended around", "cortex/routing.py",
     'if unanswered and disposition in ("recommend", "bounded_test"):', "if False:"),
    ("missing input is called a capability gap", "cortex/routing.py",
     "            if eligible and not unanswered:", "            if False:"),
    ("a withheld reader is called missing input", "cortex/routing.py",
     "            if eligible and not unanswered:", "            if eligible:"),
    ("options are parsed after the organs spend", "cortex/routing.py",
     '        options, recs = [], []\n        if problem.payload.get("options"):',
     '        options, recs = [], []\n        if False:'),
    ("a late rejection reports no spend", "cortex/routing.py",
     "expenditure = (spent or Expenditure()).plus(", "expenditure = (Expenditure()).plus("),
    ("an expiring mandate passes without an instant", "cortex/gates.py",
     "        if not as_of:\n            # 0.2.2", "        if False:\n            # 0.2.2"),
    ("a single receipt verifies a deficit", "cortex/routing.py",
     '"why": reason,\n               "verified": False,', '"why": reason,\n               "verified": True,'),
    ("a worker may report more model calls than allowed", "greg/cognition/bridge.py",
     "if max_model_calls is not None and (type(calls) is not int or calls > max_model_calls):", "if False:"),
    ("the caller's instant decides a mandate's expiry", "greg/cognition/bridge.py",
     "    return str(declared) if parsed > now else stamp", "    return str(declared)"),
    ("an empty compile request becomes a Genesis deficit", "greg/cognition/compiler.py",
     "        if native and not data:", "        if False:"),
    ("every unread input is called missing", "greg/cognition/compiler.py",
     "        if native and not data:", "        if native:"),
    ("a cap-dropped part is recommended around", "cortex/routing.py",
     'elif dropped_by_cap and disposition in ("recommend", "bounded_test"):', "elif False:"),
    ("a malformed record raises instead of being rejected", "cortex/gates.py",
     "        if not isinstance(value, Mapping):\n            raise CortexError(f\"authority record must",
     "        if False:\n            raise CortexError(f\"authority record must"),
    ("any first-listed mandate's weights rank", "cortex/routing.py",
     "and r.body.get(\"weights\") and r.record_id in accepted)}", "and r.body.get(\"weights\"))}"),
    ("list order resolves conflicting founder weights", "cortex/routing.py",
     "return next(iter(found.values())) if len(found) == 1 else None", "return next(iter(found.values()), None)"),
    ("an option's own harm cannot raise its class", "cortex/gates.py",
     '            declared, cc = cc, "financial"', "            declared = None"),
    ("a cortex non-answer is labelled answered", "greg/cognition/bridge.py",
     'outcome=receipt["outcome"], outcome_state=outcome_state_for(state), routing=routing)',
     'outcome=receipt["outcome"], routing=routing)'),
    ("a high-consequence composition is answered", "greg/cognition/compiler.py",
     "        if high:\n            # as on the problem, operation", "        if False:\n            # as on the problem, operation"),
    ("the compiler's control flag reaches the cortex", "greg/cognition/compiler.py",
     "if k not in PART_FLAGS and k not in foreign}", "if k not in foreign}"),
    # retired 2026-10-21 as equivalent: the route-policy loop that follows ("a masked part routes another organ...")
    # withholds every part routing an unselected organ by itself, so dropping the first strip changes nothing
    ("a claim that never ran is credited", "greg/cognition/seed_path.py",
     "for c in receipt.payload['claims'] if claim_ran(c)],", "for c in receipt.payload['claims']],"),
    ("a schedule-optimize lead is keyed to the whole problem", "cortex/routing.py",
     "for k in executed if plan})", "for k in () if plan})"),
    ("a resolved class is called an unknown geometry", "cortex/routing.py",
     '            state = "NO_ELIGIBLE_METHOD"\n            withheld',
     '            state = "NO_ELIGIBLE_METHOD" if any(e.eligible for e in eligibility) else "UNSUPPORTED_GEOMETRY"'
     '\n            withheld'),
    ("an unreached model is a run baseline", "cortex/evaluation/crossgeo.py",
     'if name in ("always_llm", "tool_llm") and isinstance(exc, (Unreached, OSError)):', "if False:"),
    ("an unserved baseline books a model call", "greg/cognition/seed_evaluation.py",
     "compute_cost={'model_calls':int(provenance is not None)", "compute_cost={'model_calls':1"),
    ("an errored baseline counts as run", "cortex/evaluation/scoring.py",
     "        if errored:\n", "        if False:\n"),
    ("the freeze hashes only the hand list", "cortex/evaluation/run.py",
     "FROZEN_CODE = FROZEN_CODE + [p for p in FROZEN_SUPPORT if p not in FROZEN_CODE]", "FROZEN_CODE = FROZEN_CODE"),
    ("a signed mission decides at the caller's instant", "greg/cognition/cortex.py",
     "        with signed_path():\n            return reason(", "        if True:\n            return reason("),
    ("the wall clock reaches a frozen evaluation", "greg/cognition/bridge.py",
     "            if trusted_clock or _SIGNED_PATH.get() else None", "            if True else None"),
    ("the compile's consequence never reaches the organ", "greg/cognition/compiler.py",
     "        payload, forwarded = _forward_consequence(payload, g, vector)\n", "        forwarded = None\n"),
    ("a protection matter becomes a capability gap", "greg/cognition/compiler.py",
     "g.geometry in HUMAN_CLASSES or protection:", "g.geometry in HUMAN_CLASSES:"),
    ("nothing reads an affected party", "greg/cognition/compiler.py",
     '    "protection_review": ("affected_party",),\n', ""),
    ("a reported run that loaded unfrozen code reports a verdict", "cortex/evaluation/run.py",
     "    if manifest is not None and unfrozen:", "    if False:"),
    ("a repeated arm runs twice", "cortex/evaluation/run.py",
     "    if len(set(arm_names)) != len(arm_names):", "    if False:"),
    # adversarial review of the port (2026-10-21)
    ("a mandate's malformed weights reach the ranking", "cortex/gates.py",
     '        if "weights" in body and not (', '        if False and not ('),
    ("a record's malformed scope reaches the gates", "cortex/gates.py",
     '        if "scope" in body and not isinstance(body["scope"], Mapping):', "        if False:"),
    ("an unhashable record id reaches the ranking", "cortex/gates.py",
     '        if value.get("record_id") is not None and not (', "        if False and not ("),
    ("a dominated option under another authority drops the founder's weights", "cortex/routing.py",
     "_founder_weights(recs, gate_reports, pareto_front(options, gate_reports))",
     "_founder_weights(recs, gate_reports, [o.option_id for o in options])"),
    ("a schedule with no eligible formal engine is recommended", "cortex/routing.py",
     "                    if plan is not None and not executed:", "                    if False:"),
    ("a deficit names only the first part's families", "cortex/routing.py",
     "    classes = {epistemic_class, *dict(unanswered or {}).values()}", "    classes = {epistemic_class}"),
    ("the extractor's model call is not planned", "cortex/routing.py",
     "        if EXTRACT in selected and self._extraction_needs_model(problem.payload):", "        if False:"),
    ("the payload's as_of judges authority on a signed path", "cortex/routing.py",
     'as_of=authority_as_of or problem.payload.get("as_of"))', 'as_of=problem.payload.get("as_of"))'),
    ("the body clock overwrites the question's as_of", "greg/cognition/bridge.py",
     '        serving = {**problem, "payload": {**pinned_payload, "resources": resources}}',
     '        serving = {**problem, "payload": {**pinned_payload, "resources": resources,\n'
     '                                          **({"as_of": instant} if instant else {})}}'),
    ("a composition on a signed mission decides at the caller's instant", "greg/cognition/cortex.py",
     "            with signed_path():   # a signed mission decides now", "            if True:   # a signed mission decides now"),
    ("a masked part routes another organ once its mask is withheld", "greg/cognition/compiler.py",
     '        while extra := [key for key, _ in _route_parts(payload) if key != chosen.get("organ")]:',
     "        while extra := []:"),
    ("a lead with no answer settles a success", "cortex/memory.py",
     '        if outcome_status == "verified_success" and key not in _ran(receipt, answered=True):', "        if False:"),
    ("the engine that answered cannot settle", "cortex/memory.py",
     "        if key not in selected and key not in ran:\n", "        if key not in selected:\n"),
    ("a fallback engine is keyed to no part", "cortex/routing.py",
     "                part_geometries.setdefault(k, slot_class)", "                pass"),
    ("an engine that ran is called not required", "cortex/routing.py",
     '"why_not": (ran_as[e.key] if e.key in ran_as', '"why_not": (ran_as[e.key] if False'),
    ("an installed dependency in the checkout is called unfrozen code", "cortex/evaluation/run.py",
     '        if rel[:1] == ("tests",) or {"site-packages", "dist-packages"} & set(rel) \\',
     '        if rel[:1] == ("tests",) \\'),
    ("the unfrozen guard drops the real reasons", "cortex/evaluation/run.py",
     '                                       *before.get("reasons", [])],', "                                       ],"),
    ("a malformed reply is an unrun baseline", "cortex/evaluation/arms.py",
     "    out = _parse_or_malformed(reply)", "    out = _parse(reply)"),
    ("a model that dies inside the call is a scored failure", "cortex/evaluation/arms.py",
     '        raise Unreached(f"{type(exc).__name__}: {exc}"[:300]) from exc', "        raise"),
    ("the reported file drops the incomplete rows", "cortex/evaluation/crossgeo.py",
     '"incomplete_rows": heldout.get("incomplete_rows", {})}', '"incomplete_rows": {}}'),
    ("checks sharing one receipt settle it twice", "greg/cognition/learned_routing.py",
     '        key = (claim["receipt"]["receipt_id"], claim["lead"])', '        key = (claim["claim"],)'),
    ("a refused claim stops every later request", "greg/cognition/learned_routing.py",
     "        except CortexError:\n            # A claim the ledger refuses", "        except ImportError:\n            # A claim the ledger refuses"),
    ("a pinned organ's mission reports the other parts as a gap", "greg/cognition/bridge.py",
     '        pinned_payload, outside_pin = _pinned_payload(problem["payload"], forced)',
     '        pinned_payload, outside_pin = problem["payload"], []'),
    ("the compile's harm never reaches the organ", "greg/cognition/compiler.py",
     "    if raised:\n        declared[\"harm\"]", "    if False:\n        declared[\"harm\"]"),
]

GROUPS = [("cortex", TESTS, MUTANTS), ("greg path", GREG_TESTS, GREG_MUTANTS),
          ("open-source genesis", OSS_TESTS, OSS_MUTANTS), ("recombine", RECOMBINE_TESTS, RECOMBINE_MUTANTS),
          ("mind construction", MIND_CONSTRUCTION_TESTS, MIND_CONSTRUCTION_MUTANTS),
          ("recovery", RECOVERY_TESTS, RECOVERY_MUTANTS),
          ("evidence chain at commit", COMMIT_CHAIN_TESTS, COMMIT_CHAIN_MUTANTS),
          ("founder tier", FOUNDER_TIER_TESTS, FOUNDER_TIER_MUTANTS),
          ("founder tier (body)", FOUNDER_TIER_BODY_TESTS, FOUNDER_TIER_BODY_MUTANTS),
          ("closure integrity", CLOSURE_INTEGRITY_TESTS, CLOSURE_INTEGRITY_MUTANTS),
          ("capability perception", CAPABILITY_PERCEPTION_TESTS, CAPABILITY_PERCEPTION_MUTANTS),
          ("goal-requested formation", GOAL_FORMATION_TESTS, GOAL_FORMATION_MUTANTS),
          ("portfolio words", PORTFOLIO_WORDS_TESTS, PORTFOLIO_WORDS_MUTANTS),
          ("budgeted selection", BUDGETED_TESTS, BUDGETED_MUTANTS),
          ("seed ports", PORT_TESTS, PORT_MUTANTS)]


def _run_one(work: Path, group: str, tests: list, name: str, rel: str, old: str, new: str) -> tuple[bool, str]:
    """Apply one mutant in this worker's scratch copy, run its tests, restore the file."""
    path = work / rel
    source = path.read_text(encoding="utf-8")
    if source.count(old) != 1:
        return False, f"STALE    [{group}] {name}: pattern not found exactly once in {rel}"
    path.write_text(source.replace(old, new), encoding="utf-8")
    try:
        run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
                             cwd=work, capture_output=True, text=True)
    finally:
        path.write_text(source, encoding="utf-8")
    caught = run.returncode != 0
    tail = (run.stdout.strip().splitlines() or ["(no output)"])[-1]
    return caught, f"{'CAUGHT ' if caught else 'SURVIVED'} [{group}] {name}: {tail}"


def main() -> int:
    # Mutants run in parallel, one scratch copy of the repository per worker (a mutant never meets another's
    # edit); the report keeps the declared order. CORTEX_MUTANT_WORKERS overrides the worker count.
    mutants = [(g, t, *m) for g, t, ms in GROUPS for m in ms]
    workers = max(1, int(os.environ.get("CORTEX_MUTANT_WORKERS") or os.cpu_count() or 1))
    with tempfile.TemporaryDirectory(prefix="cortex-mutants-") as tmp:
        copies: queue.Queue = queue.Queue()
        for i in range(min(workers, len(mutants))):
            work = Path(tmp) / f"repo{i}"
            shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
            copies.put(work)

        def one(mutant):
            work = copies.get()
            try:
                return _run_one(work, *mutant)
            finally:
                copies.put(work)
        with ThreadPoolExecutor(max_workers=copies.qsize()) as pool:
            results = list(pool.map(one, mutants))
    for _, line in results:
        print(line)
    bad = sum(not caught for caught, _ in results)
    print(f"{len(results)} mutants, {bad} survived or stale")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
