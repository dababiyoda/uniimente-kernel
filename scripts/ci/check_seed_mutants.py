"""Deliberate critical-gate defects in disposable copies; never mutate live source."""
from pathlib import Path
import ast, json, shutil, subprocess, sys, tempfile, time
ROOT=Path(__file__).resolve().parents[2]
MUTANTS=[
 ('eligibility','greg/cognition/cortex.py','eligible, reason = registry.usable(cid)','eligible, reason = True, "mutant ignores detach"','tests/integration/test_greg_cognition_mission.py::test_detachment_survives_restart_and_solver_cannot_bypass_it'),
 ('constraint','greg/cognition/verification.py','checks["constraint_substitution"] = bool(valid)','checks["constraint_substitution"] = True','tests/unit/test_cognition_seed_gates.py::test_verifier_refutes_integer_violation'),
 ('unknown','greg/cognition/solvers.py','str(status).upper()','"SAT" if str(status) == "unknown" else str(status).upper()','tests/unit/test_cognition_seed_gates.py::test_real_solver_unknown_not_sat_or_optimal'),
 ('evidence','greg/cognition/evidence.py','if s.get("digest") != digest(s["text"]):','if False:','tests/unit/test_cognition_seed_gates.py::test_forged_or_stale_evidence_abstains'),
 ('duplicate_settlement','greg/cognition/settlement.py','if prior is None or digest({k:v for k,v in prior.payload.items() if k != "supersedes"}) != digest(outcome):','if True:','tests/integration/test_greg_cognition_mission.py::test_cognition_is_durable_receipted_and_reobserved_on_the_existing_body'),
 ('paid_fallback','greg/cognition/cortex.py','raise CognitionError("CAPABILITY_UNAVAILABLE: no founder-selected local model")','from greg.models import OpenAIRoute\n        OpenAIRoute("mutation-test-blocked")\n        raise CognitionError("paid fallback enabled")','tests/unit/test_cognition_seed_gates.py::test_catalog_not_eligibility_and_no_paid_fallback'),
 ('protected_party','greg/cognition/cortex.py','elif consequences.prohibited:','elif False:','tests/unit/test_cognition_seed_gates.py::test_score_improvement_cannot_harm_protected_party'),
]

def main(output):
 rows=[]
 for name,path,before,after,test in MUTANTS:
  with tempfile.TemporaryDirectory(prefix='greg-seed-mutant-') as directory:
   copy=Path(directory)/'repo';shutil.copytree(ROOT,copy,ignore=shutil.ignore_patterns('.git','__pycache__','evidence','.pytest_cache'))
   f=copy/path;s=f.read_text()
   if s.count(before)!=1:raise RuntimeError(f'{name}: mutation anchor not unique')
   f.write_text(s.replace(before,after));ast.parse(f.read_text())
   if name=='evidence':
    vf=copy/'greg/cognition/verification.py';vs=vf.read_text();vs=vs.replace('checks["custody_digests"] = all(s["digest"] == digest(s["text"]) for s in sources.values())','checks["custody_digests"] = True');vf.write_text(vs);ast.parse(vs)
   start=time.monotonic();run=subprocess.run([sys.executable,'-m','pytest','-q',test],cwd=copy,capture_output=True,text=True,timeout=60)
   detected=run.returncode==1 and 'FAILED' in run.stdout
   rows.append({'mutant':name,'detected':detected,'exit_code':run.returncode,'seconds':time.monotonic()-start,'test':test,'stdout':run.stdout,'stderr':run.stderr,
                'limit':'paid fallback mutant changes the refusal disposition; no real paid request is made'})
   print(name,detected,flush=True)
 Path(output).write_text(json.dumps({'schema':'seed-mutation-results/1','results':rows,'all_detected':all(r['detected'] for r in rows)},indent=2))
 return all(r['detected'] for r in rows)
if __name__=='__main__':raise SystemExit(0 if main(sys.argv[1]) else 1)
