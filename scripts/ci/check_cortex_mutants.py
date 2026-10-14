"""Mutation check for the cortex authority and protection invariants.

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
         "tests/unit/test_cortex_pipeline.py", "tests/unit/test_cortex_defect_fixes.py",
         "tests/unit/test_cortex_finality_deficit.py", "tests/unit/test_cortex_proposer.py",
         "tests/unit/test_cortex_replay.py"]
# A mutant must be caught by a behavioural test. The freeze-hash checks fail for any edit to a frozen file,
# so they are deselected here; otherwise every mutant of frozen code would count as caught (0.1.6).
DESELECT = ["tests/unit/test_cortex_pipeline.py::TestEvaluationIntegrity::test_heldout_matches_its_freeze",
            "tests/unit/test_cortex_replay.py::test_replay_does_not_touch_the_freeze"]
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
    # ---- 0.1.6 safeguards
    ("settlement accepts the wrong method version", "cortex/memory.py",
     "if key not in selected:", "if False:"),
    ("settlement ignores the content address", "cortex/memory.py",
     'if unsigned.pop("receipt_id", None) != digest(unsigned):', 'if False:'),
    ("settlement counts a route that never ran", "cortex/memory.py",
     "if outcome_status in SETTLING and key not in ran:", "if False:"),
    ("one observation settles twice", "cortex/memory.py",
     "if outcome_status in SETTLING and any(", "if False and any("),
    ("composed part settles under the receipt's class", "cortex/memory.py",
     "geometry = part_geometries.get(key) or geometry", "geometry = geometry"),
    ("expiring mandate passes without an instant", "cortex/gates.py",
     "        if not as_of:\n", "        if False:\n"),
    ("harm cannot raise the consequence class", "cortex/routing.py",
     'implied = "financial" if (harm.levels["financial"] in ("high", "critical") or harm.hard_violations()) else None',
     "implied = None"),
    ("unanswered part recommended around", "cortex/routing.py",
     'if unanswered and disposition == "recommend":', "if False:"),
    ("missing input called a capability gap", "cortex/routing.py",
     "            if eligible:\n                # A capability exists", "            if False:\n                # A capability exists"),
    ("deficit emitted on a handoff", "cortex/routing.py",
     'if disposition == "abstain" else None))', "if True else None))"),
    ("options parsed after organs spend", "cortex/routing.py",
     '        if problem.payload.get("options"):\n            try:\n                recs = ',
     '        if False:\n            try:\n                recs = '),
    ("context authority records trusted", "egregore/cortex_proposer.py",
     'if "authority_records" in request:', "if False:"),
    ("context instant trusted", "egregore/cortex_proposer.py",
     'if "as_of" in payload:', "if False:"),
    ("receipt guard skips the content address", "egregore/cortex_proposer.py",
     "if identity != cortex_digest(body):", "if False:"),
    ("receipt guard skips the model-call ceiling", "egregore/cortex_proposer.py",
     "if not isinstance(calls, int) or isinstance(calls, bool) or calls > self.max_model_calls:", "if False:"),
    ("missing replay reply counts as a baseline failure", "cortex/evaluation/replay.py",
     "    if client.misses:\n        for arm in replayed:", "    if False:\n        for arm in replayed:"),
    ("replay accepts repeated arms", "cortex/evaluation/replay.py",
     "if len(arm_names) != len(set(arm_names)):", "if False:"),
]


def main() -> int:
    bad = 0
    with tempfile.TemporaryDirectory(prefix="cortex-mutants-") as tmp:
        work = Path(tmp) / "repo"
        shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
        for name, rel, old, new in MUTANTS:
            path = work / rel
            source = path.read_text(encoding="utf-8")
            if source.count(old) != 1:
                print(f"STALE    {name}: pattern not found exactly once in {rel}")
                bad += 1
                continue
            path.write_text(source.replace(old, new), encoding="utf-8")
            try:
                run = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *TESTS,
                                      *[f"--deselect={d}" for d in DESELECT]],
                                     cwd=work, capture_output=True, text=True)
            finally:
                path.write_text(source, encoding="utf-8")
            caught = run.returncode != 0
            tail = (run.stdout.strip().splitlines() or ["(no output)"])[-1]
            print(f"{'CAUGHT ' if caught else 'SURVIVED'} {name}: {tail}")
            bad += not caught
    print(f"{len(MUTANTS)} mutants, {bad} survived or stale")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
