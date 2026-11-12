"""Reviewer mutants of the changed lines (not in the branch's gate). Scratch copy of ra-head; never the worktree."""
import os, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
ONLY = sys.argv[2:]
A, B, M = "greg/appraisal.py", "greg/body.py", "greg/missions.py"
T_ATTACH = ["tests/unit/test_greg_appraiser_attach_state.py"]
T_BODY = T_ATTACH + ["tests/unit/test_greg_appraisal_retry_bound.py"]
T_ENGINE = ["tests/unit/test_greg_failure_closure.py", "tests/unit/test_greg_achievement_after_unmet.py",
            "tests/unit/test_greg_closure_scoped_claims.py", "tests/unit/test_greg_closure_scoped_settlement.py",
            "tests/unit/test_greg_unmeasured_not_failed.py"]
MUTANTS = [
 ("A1", A, "a check whose sensor was not run is not listed as unmeasured (world_reobserved stays true)",
  '                unmeasured.append(check["check_id"])\n', '                pass\n', T_ATTACH),
 ("A2", A, "a delivery that was not re-derived refutes the closure (NOT_RUN_CHECKS drops deliveries)",
  'NOT_RUN_CHECKS = ("world_reobserved", "deliveries_bound_to_evidence")', 'NOT_RUN_CHECKS = ("world_reobserved",)', T_ATTACH),
 ("A3", A, "the delivering capability that was not run is not named in not_run",
  '                not_run[action["capability"]] = withheld\n', '', T_ATTACH),
 ("A4", A, "a delivery that was not re-derived still passes deliveries_bound_to_evidence",
  '                underived.append(action["action_id"])\n', '', T_ATTACH),
 ("A5", A, "a sensor that is never re-run (not read-only) no longer fails world_reobserved",
  "                reobserved = False\n                findings.append(f\"{check['check_id']}: the world could not be re-measured ({never})\")",
  "                findings.append(f\"{check['check_id']}: the world could not be re-measured ({never})\")", T_ATTACH),
 ("A6", A, "a VERIFIED (never attached) sensor is re-run",
  '    if state != "ATTACHED":\n        return (f"{cid} is {state or',
  '    if state not in ("ATTACHED", "VERIFIED"):\n        return (f"{cid} is {state or', T_ATTACH),
 ("A7", A, "only brief.engineering is gated: a detached venture.assess or organs.exchange delivery is re-derived (organs re-run)",
  'withheld = _not_attached(registry, action["capability"])',
  'withheld = _not_attached(registry, action["capability"]) if action["capability"] == "brief.engineering" else None', T_ATTACH),
 ("B1", B, "the first appraisal of a closure, not the latest, decides whether it waits for an attach",
  '            latest[event.payload["mission_id"], event.payload.get("closure_event")] = event',
  '            latest.setdefault((event.payload["mission_id"], event.payload.get("closure_event")), event)', T_BODY),
 ("B4", B, "the final record written after a kill between the last unavailable run and its record reuses the first appraisal's identity",
  '                key=[mid, "appraised", closure_event or last["head"], *again])',
  '                key=[mid, "appraised", closure_event or last["head"]])', T_BODY),
 ("B8", B, "the first state change of a capability, not its latest, is compared with the appraisal",
  '        changed_at = {event.payload["capability_id"]: position.get(event.event_id, -1)\n'
  '                      for event in self.journal.replay("capability.state")}',
  '        changed_at = {}\n        for event in self.journal.replay("capability.state"):\n'
  '            changed_at.setdefault(event.payload["capability_id"], position.get(event.event_id, -1))', T_BODY),
 ("B10", B, "a closure is appraised again when what it waits on became VERIFIED, not ATTACHED",
  '            if all(self.registry.state.get(cid) == "ATTACHED" for cid in needed) \\\n',
  '            if all(self.registry.state.get(cid) in ("ATTACHED", "VERIFIED") for cid in needed) \\\n', T_BODY),
 ("B14", B, "the identity counter of a later appraisal counts every closure of the mission",
  '                      if e.payload["mission_id"] == mid and e.payload.get("closure_event") == closure_event)\n        again',
  '                      if e.payload["mission_id"] == mid)\n        again', T_BODY),
 ("E1", M, "one failure closure per mission ever (a later failure at a higher action count is never closed)",
  'closed = self.journal.retained("mission.unmet", [m.mission_id, "unmet", m.actions_done]) is not None',
  'closed = any(e.payload["mission_id"] == m.mission_id for e in self.journal.replay("mission.unmet"))', T_ENGINE),
 ("E2", M, "(the gate's own engine mutant) a failure closure is recorded again after a lifted blocker",
  'if not split and failing - unread and not closed:', 'if not split and failing - unread:', ["tests/unit/test_greg_failure_closure.py"]),
 ("B15", B, "a closure whose latest appraisal is the final UNAVAILABLE of exhausted runs (no not_run) is appraised again after any attach",
  '        waiting = {closure: event for closure, event in latest.items() if not_run_by_appraiser(event.payload)}',
  '        waiting = {closure: event for closure, event in latest.items() if event.payload.get("verdict") == "UNAVAILABLE"}', T_BODY),
 ("A8", A, "a failure closure whose sensor was not run is REFUTED, not UNAVAILABLE",
  '    if not_run:\n        judged["not_run"]', '    if not_run and not unmet:\n        judged["not_run"]', T_ATTACH),
]

def purge(repo):
    for top in ("greg", "tests"):
        for cache in (repo / top).rglob("__pycache__"):
            shutil.rmtree(cache, ignore_errors=True)

survived = 0
with tempfile.TemporaryDirectory(prefix="ra-mutants-") as temp:
    repo = Path(temp) / "repo"
    shutil.copytree(ROOT, repo, ignore=shutil.ignore_patterns(".git", "__pycache__", ".pytest_cache"))
    env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONDONTWRITEBYTECODE": "1"}
    for mid, target, name, old, new, tests in MUTANTS:
        if ONLY and mid not in ONLY:
            continue
        path = repo / target
        original = path.read_text()
        if original.count(old) != 1:
            print("STALE", mid, name, original.count(old), flush=True)
            continue
        path.write_text(original.replace(old, new))
        purge(repo)
        try:
            r = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", *tests],
                               cwd=repo, env=env, capture_output=True, text=True, timeout=1500)
        finally:
            path.write_text(original)
        failed = [l for l in r.stdout.splitlines() if l.startswith("FAILED ")]
        caught = r.returncode == 1 and failed and "ERROR collecting" not in r.stdout
        tail = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-200:]
        print("CAUGHT  " if caught else "SURVIVED", mid, "|", name, "|", (failed[0][:150] if failed else tail), flush=True)
        survived += not caught
print("survivors:", survived)
