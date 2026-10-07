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
     'if repair and repair.get("capability_id") == manifest.capability_id:', "if False:"),
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
     "if capability_id not in {c[\"capability_id\"] for c in _attachable(open_asks.get(request_id, {}))}:",
     "if False:"),
]

GROUPS = [("cortex", TESTS, MUTANTS), ("greg path", GREG_TESTS, GREG_MUTANTS),
          ("open-source genesis", OSS_TESTS, OSS_MUTANTS)]


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
