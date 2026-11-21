"""Mutation check for the cortex and GREG-path authority, evidence and budget invariants.

    python scripts/ci/check_cortex_mutants.py

Each mutant removes one safeguard the build prompt requires (a failed gate
cannot be outranked, predictions cannot settle competence, victim protection is
human-led, ...). The cortex tests must fail for every mutant. Mutants are
applied to a scratch copy of the repository, never to the working tree.
Exit status 1 if any mutant survives or no longer applies.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
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
             "tests/unit/test_greg_cognition.py"]
OSS_MUTANTS = [
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
     "(formation only).\n        if self._form_only:", "(formation only).\n        if False:"),
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
    ("a goal's request attaches a construction's engine that fell back to VERIFIED", "greg/genesis.py",
     "or ask.\"\"\"\n        if self._form_only:\n            return False",
     "or ask.\"\"\"\n        if False:\n            return False"),
    ("a second request awaiting one formed capability faults the journal", "greg/genesis.py",
     '        if self.journal.retained("deficit.awaiting_attach", key) is None:', "        if True:"),
    ("a host outage during a goal's formation stops the body's tick", "greg/goal_gravity.py",
     "            except CapabilityError as exc:", "            except ZeroDivisionError as exc:"),
    ("a stopped goal still asks for formation", "greg/goal_gravity.py",
     "        if gid not in facts.admitted or facts.stopped(gid) is not None:\n            continue\n        state",
     "        if gid not in facts.admitted:\n            continue\n        state"),
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
    ("a signed pre-approval admits every strategy of its capability and class", "greg/missions.py",
     '        p["action_id"] == strategy["action_id"] and p["capability"] == manifest.capability_id\n'
     '        and p["target"] == strategy["target"] and p["consequence_class"] == manifest.consequence_class\n',
     '        p["capability"] == manifest.capability_id\n'
     '        and p["consequence_class"] == manifest.consequence_class\n'),
    ("the appraiser counts an answer the founder fold does not", "greg/appraisal.py",
     "        answers = {rid: answer for rid, answer in answers.items() if rid in counted}",
     "        answers = dict(answers)"),
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

# 2026-10-21: #173's interruption guards (appraiser retry bound, Genesis build reservation), pinned by the review of
# the PR #184 port branch (f63f218), carried onto #173's code. Each survived the suites that existed before.
INTERRUPTION_TESTS = ["tests/unit/test_greg_genesis_build_reservation.py", "tests/unit/test_greg_appraisal_retry_bound.py"]
INTERRUPTION_MUTANTS = [
    ("an interrupted call by a builder with no ceiling is charged nothing", "greg/genesis.py",
     '"reserved_usd": min(self.builder_cap, remaining) if self.builder_cap is not None else remaining,',
     '"reserved_usd": min(self.builder_cap, remaining) if self.builder_cap is not None else 0.0,'),
    ("the appraiser's read-only restore completes an unresolved auto-attach", "greg/genesis.py",
     "        if record:\n            self._finish_attaches()", "        self._finish_attaches()"),
    ("the third unavailable appraisal waits a tick for its final verdict", "greg/body.py",
     '        if attempt >= APPRAISAL_ATTEMPTS:\n            self.journal.record("mission.appraised"',
     '        if False:\n            self.journal.record("mission.appraised"'),
    ("a build budget left only by binary rounding is not used up", "greg/genesis.py",
     'round(contract["build_budget_usd"] - spent, 6) <= 0', 'contract["build_budget_usd"] - spent <= 0'),
    ("a cone left only by binary rounding buys another call", "greg/genesis.py",
     'remaining = round(min(contract["build_budget_usd"] - spent, cone_left - (spent - spent_at_entry)), 6)',
     'remaining = min(contract["build_budget_usd"] - spent, cone_left - (spent - spent_at_entry))'),
]

# 2026-10-22: the review of the merge of #178 e410977 into PR #184 (conv-m178e). Each mutant reverts one fix; on the
# merge tip the pinning test failed (acceptance soundness, the console's H.G7 half, signal scoping, the timed-out
# acceptance record, a receipted overspend, the appraiser's H.G4 re-derivation, a billed failure across a kill).
ACCEPTANCE_READER_TESTS = ["tests/unit/test_acceptance_harness.py::test_the_manifest_and_contract_are_sound_against_this_tree"]
ACCEPTANCE_READER_MUTANTS = [
    ("a python -c Body.run driver is not seen as a real Body process", "acceptance/__init__.py",
     'script = 2 if const[1:2] == ["-c"] else 1', "script = 1"),
]
CONSOLE_LINK_TESTS = ["tests/integration/test_greg_inbox_writer_kill_process.py::"
                      "test_a_service_killed_while_writing_a_decision_leaves_no_partial_command_and_it_applies_once"
                      "[console-after-rename]"]
CONSOLE_LINK_MUTANTS = [
    ("the console's private link works more than once", "greg/console.py",
     "            self._bootstrap = None\n            return True", "            return True"),
]
_CONTAIN = "tests/unit/test_greg_worker_containment.py::"
SIGNAL_SCOPE_TESTS = [_CONTAIN + "test_a_supervised_confined_worker_cannot_signal_the_body",
                      _CONTAIN + "test_gregs_supervised_acceptance_run_cannot_signal_the_body",
                      _CONTAIN + "test_a_timed_out_supervised_acceptance_run_is_never_recorded_as_the_envelope"]
SIGNAL_SCOPE_MUTANTS = [
    ("a supervised Landlock worker may signal the body", "greg/workers.py",
     "isolation.restrict(grants, libc, scope=scope)", "isolation.restrict(grants, libc)"),
    ("GREG's confined acceptance run may signal the body", "greg/capabilities.py",
     "restrict(grants, libc, scope=scope)   # precomputed", "restrict(grants, libc)   # precomputed"),
    ("a timed-out supervised acceptance run keeps an unconfined record", "greg/workers.py",
     "                    mode, evidence = _supervised_acceptance(landlock), {\"mode\": \"supervised\", \"landlock\": landlock}\n"
     "                    raise",
     "                    raise"),
]
_RECON = "tests/unit/test_greg_mission_reconciliation.py::"
RECONCILED_MONEY_TESTS = [_RECON + "test_a_receipted_interrupt_that_reported_spending_over_its_cap_books_what_it_reported",
                          _RECON + "test_the_appraiser_refutes_a_closure_that_released_a_metered_not_executed_cap_and_retried",
                          _RECON + "test_the_appraiser_verifies_a_closure_that_kept_the_metered_cap_booked"]
RECONCILED_MONEY_MUTANTS = [
    ("a receipted interrupt's report over its cap is settled at the cap", "greg/missions.py",
     "if booked and reported is not None and reported > worst + 1e-9:", "if False:"),
    ("the appraiser takes a reconciliation's booking from the engine", "greg/appraisal.py",
     '                if cost < required - 1e-9:\n                    approvals_ok = False',
     '                if False:\n                    approvals_ok = False'),
    ("the appraiser leaves a booked reconciliation out of spend so far", "greg/appraisal.py",
     'if action.get("route") == "founder_reconciliation":', "if False:"),
]
BILLED_FAILURE_TESTS = ["tests/unit/test_greg_genesis_build_reservation.py::"
                        "test_a_billed_failure_survives_a_kill_between_its_two_records_and_the_budget_bounds_the_next_call"]
BILLED_FAILURE_MUTANTS = [
    ("a billed failure's bill does not settle its call", "greg/genesis.py",
     'SETTLES_BUILD = ("genesis.built", "genesis.unbuilt", "genesis.build_failed")',
     'SETTLES_BUILD = ("genesis.built", "genesis.build_failed")'),
    ("a billed failure's bill is never recorded", "greg/genesis.py",
     "                    if cost:   # billed although no candidate came back",
     "                    if False:   # billed although no candidate came back"),
]

GROUPS = [("cortex", TESTS, MUTANTS), ("greg path", GREG_TESTS, GREG_MUTANTS),
          ("open-source genesis", OSS_TESTS, OSS_MUTANTS), ("recombine", RECOMBINE_TESTS, RECOMBINE_MUTANTS),
          ("mind construction", MIND_CONSTRUCTION_TESTS, MIND_CONSTRUCTION_MUTANTS),
          ("recovery", RECOVERY_TESTS, RECOVERY_MUTANTS),
          ("capability perception", CAPABILITY_PERCEPTION_TESTS, CAPABILITY_PERCEPTION_MUTANTS),
          ("goal-requested formation", GOAL_FORMATION_TESTS, GOAL_FORMATION_MUTANTS),
          ("evidence chain at commit", COMMIT_CHAIN_TESTS, COMMIT_CHAIN_MUTANTS),
          ("founder tier", FOUNDER_TIER_TESTS, FOUNDER_TIER_MUTANTS),
          ("founder tier (body)", FOUNDER_TIER_BODY_TESTS, FOUNDER_TIER_BODY_MUTANTS),
          ("closure integrity", CLOSURE_INTEGRITY_TESTS, CLOSURE_INTEGRITY_MUTANTS),
          ("interruption", INTERRUPTION_TESTS, INTERRUPTION_MUTANTS),
          ("acceptance reader", ACCEPTANCE_READER_TESTS, ACCEPTANCE_READER_MUTANTS),
          ("console private link", CONSOLE_LINK_TESTS, CONSOLE_LINK_MUTANTS),
          ("signal scoping", SIGNAL_SCOPE_TESTS, SIGNAL_SCOPE_MUTANTS),
          ("reconciled money", RECONCILED_MONEY_TESTS, RECONCILED_MONEY_MUTANTS),
          ("billed failure", BILLED_FAILURE_TESTS, BILLED_FAILURE_MUTANTS)]


def main() -> int:
    bad = total = 0
    with tempfile.TemporaryDirectory(prefix="cortex-mutants-") as tmp:
        work = Path(tmp) / "repo"
        shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        for group, tests, name, rel, old, new in [(g, t, *m) for g, t, ms in GROUPS for m in ms]:
            total += 1
            path = work / rel
            source = path.read_text(encoding="utf-8")
            if source.count(old) != 1:
                print(f"STALE    [{group}] {name}: pattern not found exactly once in {rel}")
                bad += 1
                continue
            path.write_text(source.replace(old, new), encoding="utf-8")
            try:
                run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
                                     cwd=work, capture_output=True, text=True)
            finally:
                path.write_text(source, encoding="utf-8")
            caught = run.returncode != 0
            tail = (run.stdout.strip().splitlines() or ["(no output)"])[-1]
            print(f"{'CAUGHT ' if caught else 'SURVIVED'} [{group}] {name}: {tail}")
            bad += not caught
    print(f"{total} mutants, {bad} survived or stale")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
