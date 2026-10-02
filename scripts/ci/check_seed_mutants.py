"""Deliberate critical-gate defects in disposable copies; never mutate live source."""
from pathlib import Path
import ast, hashlib, json, shutil, subprocess, sys, tempfile, time
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[2]
MUTANTS=[
 ('eligibility','greg/cognition/cortex.py','eligible, reason = registry.usable(cid)','eligible, reason = True, "mutant ignores detach"','tests/integration/test_greg_cognition_mission.py::test_detachment_survives_restart_and_solver_cannot_bypass_it'),
 ('constraint','greg/cognition/verification.py','checks["constraint_substitution"] = bool(valid)','checks["constraint_substitution"] = True','tests/unit/test_cognition_seed_gates.py::test_verifier_refutes_integer_violation'),
 ('unknown','greg/cognition/solvers.py','str(status).upper()','"SAT" if str(status) == "unknown" else str(status).upper()','tests/unit/test_cognition_seed_gates.py::test_real_solver_unknown_not_sat_or_optimal'),
 ('evidence','greg/cognition/evidence.py','if s.get("digest") != digest(s["text"]):','if False:','tests/unit/test_cognition_seed_gates.py::test_forged_or_stale_evidence_abstains'),
 ('duplicate_settlement','greg/cognition/settlement.py','if prior is None or digest({k:v for k,v in prior.payload.items() if k != "supersedes"}) != digest(outcome):','if True:','tests/integration/test_greg_cognition_mission.py::test_cognition_is_durable_receipted_and_reobserved_on_the_existing_body'),
 ('paid_fallback','greg/cognition/cortex.py','raise CognitionError("CAPABILITY_UNAVAILABLE: no founder-selected local model")','from greg.models import OpenAIRoute\n        OpenAIRoute("mutation-test-blocked")\n        raise CognitionError("paid fallback enabled")','tests/unit/test_cognition_seed_gates.py::test_catalog_not_eligibility_and_no_paid_fallback'),
 ('protected_party','greg/cognition/cortex.py','elif consequences.prohibited:','elif False:','tests/unit/test_cognition_seed_gates.py::test_score_improvement_cannot_harm_protected_party'),
 ('original_artifact','greg/appraisal.py','if checked["verdict"] != "STRUCTURALLY_VERIFIED":\n        raise ValueError("retained source/proof/output checks refuted the result")','if False:\n        raise ValueError("retained source/proof/output checks refuted the result")','tests/integration/test_greg_native_artifact_appraisal.py::test_original_numeric_source_and_certificate_must_survive_independent_appraisal[cognition.exact-expression]'),
]

def _sha(path):
 return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_test(copy, test):
 command=[sys.executable,'-m','pytest','-q',test]
 start=time.monotonic()
 try:
  run=subprocess.run(command,cwd=copy,capture_output=True,text=True,timeout=60)
  return {'command':command,'exit_code':run.returncode,'seconds':time.monotonic()-start,
          'stdout':run.stdout,'stderr':run.stderr,'timed_out':False}
 except subprocess.TimeoutExpired as exc:
  # A resource interruption is evidence of an inconclusive check, not a gate kill.
  def decode(value):
   return value.decode(errors='replace') if isinstance(value,bytes) else (value or '')
  return {'command':command,'exit_code':None,'seconds':time.monotonic()-start,
          'stdout':decode(exc.stdout),'stderr':decode(exc.stderr),'timed_out':True}


def main(output):
 rows=[]
 output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
 started=datetime.now(timezone.utc).isoformat()
 metadata={'schema':'seed-mutation-results/2','started_at':started,
           'git_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
           'python':sys.version,'harness_sha256':_sha(Path(__file__)),
           'limits':'Disposable Linux laboratory copies and test signing keys. A paid-route sentinel prevents any real paid request; no live authority or deployment evidence.'}
 def preserve():
  # Retain every completed attempt even if a later process or mutation cannot run.
  payload={**metadata,'updated_at':datetime.now(timezone.utc).isoformat(),
           'results':rows,'completed_mutants':len(rows),'expected_mutants':len(MUTANTS),
           'all_detected':len(rows)==len(MUTANTS) and all(r['detected'] for r in rows)}
  pending=output.with_suffix(output.suffix+'.pending')
  pending.write_text(json.dumps(payload,indent=2)+'\n');pending.replace(output)
 preserve()
 for name,path,before,after,test in MUTANTS:
  row={'mutant':name,'path':path,'test':test,'detected':False}
  start=time.monotonic()
  try:
   with tempfile.TemporaryDirectory(prefix='greg-seed-mutant-') as directory:
    copy=Path(directory)/'repo'
    shutil.copytree(ROOT,copy,ignore=shutil.ignore_patterns('.git','__pycache__','evidence','.pytest_cache'))
    files=[p for p in copy.rglob('*') if p.is_file() and p.suffix in ('.py','.json','.yaml','.sh','.js','.txt')]
    row['source_sha256']={str(p.relative_to(copy)):_sha(p) for p in sorted(files)}
    row['source_aggregate_sha256']=hashlib.sha256(json.dumps(row['source_sha256'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    baseline=_run_test(copy,test);row['baseline']=baseline
    if baseline['exit_code']!=0:
     row['disposition']='INCONCLUSIVE_BASELINE_FAILED'
    else:
     f=copy/path;s=f.read_text()
     if s.count(before)!=1:raise RuntimeError(f'{name}: mutation anchor not unique')
     f.write_text(s.replace(before,after));ast.parse(f.read_text())
     row['mutated_sha256']={path:_sha(f)}
     if name=='evidence':
      vf=copy/'greg/cognition/verification.py';vs=vf.read_text()
      anchor='checks["custody_digests"] = all(s["digest"] == digest(s["text"]) for s in sources.values())'
      if vs.count(anchor)!=1:raise RuntimeError('evidence: verifier mutation anchor not unique')
      vf.write_text(vs.replace(anchor,'checks["custody_digests"] = True'));ast.parse(vf.read_text())
      row['mutated_sha256']['greg/cognition/verification.py']=_sha(vf)
     run=_run_test(copy,test);row.update(run)
     row['detected']=run['exit_code']==1 and 'FAILED' in run['stdout']
     row['disposition']='DETECTED' if row['detected'] else 'INCONCLUSIVE_TIMEOUT' if run['timed_out'] else 'SURVIVED_OR_SETUP_FAILED'
  except Exception as exc:
   row['disposition']='INCONCLUSIVE_HARNESS_ERROR';row['error']=f'{type(exc).__name__}: {exc}'
  row['total_seconds']=time.monotonic()-start
  rows.append(row);preserve()
  print(name,row['disposition'],flush=True)
 return len(rows)==len(MUTANTS) and all(r['detected'] for r in rows)
if __name__=='__main__':raise SystemExit(0 if main(sys.argv[1]) else 1)
