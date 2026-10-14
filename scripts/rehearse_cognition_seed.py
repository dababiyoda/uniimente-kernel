"""CLI-process recovery rehearsal. Fresh synthetic authority, never a founder-device attestation."""
from pathlib import Path
import json, os, signal, subprocess, sys, time
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from greg.body import observe

def main(folder,model=None):
 p=Path(folder).resolve();p.mkdir(parents=True,exist_ok=False)
 home=p/'body';key=p/'test-key.pem';log=p/'commands.jsonl'
 def cli(*args):
  start=time.monotonic();r=subprocess.run([sys.executable,'-m','greg','--home',str(home),*args],cwd=ROOT,capture_output=True,text=True,timeout=60)
  with log.open('a') as f:f.write(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'args':args,'seconds':time.monotonic()-start,'exit':r.returncode,'stdout':r.stdout,'stderr':r.stderr})+'\n')
  if r.returncode:raise RuntimeError(r.stderr)
  return r.stdout
 cli('init','--read-root',str(p));pub=cli('founder','keygen','--key',str(key),'--no-passphrase').strip();cli('founder','enroll','--pubkey',pub)
 numeric_model={'variables':{'x':[0,20]},'constraints':[{'coefficients':{'x':1},'op':'>=','rhs':4}],'objective':{'coefficients':{'x':1},'sense':'min'}}
 requests=[('optimize',numeric_model),('estimate',{'factors':[{'name':'count','low':2,'central':3,'high':4},{'name':'rate','low':4,'central':5,'high':6}]}),('treatment_effect',{'design':'randomized','treated':[i%5+4 for i in range(40)],'control':[i%5 for i in range(40)],'synthetic':True})]
 for i,(op,data) in enumerate(requests):
  request=p/f'request-{i}.json';request.write_text(json.dumps({'problem_id':f'rehearsal:{i}','operation':op,'data':data}))
  cli('cognition','mission','--request',str(request),'--id',f'm:rehearsal-{i}','--key',str(key),'--no-passphrase')
 stream=(p/'interrupted.log').open('w');proc=subprocess.Popen([sys.executable,'-m','greg','--home',str(home),'run','--tick-seconds','0.1'],cwd=ROOT,stdout=stream,stderr=stream)
 deadline=time.monotonic()+45;seen=False
 try:
  while time.monotonic()<deadline:
   if home.joinpath('ledger.jsonl').exists():
    try:
     with observe(home) as journal:seen=any(r.payload.get('result',{}).get('output',{}).get('method')=='cognition.optimization' for r in journal.ledger.by_type('receipt'))
    except (ValueError,KeyError,TypeError):pass
   if seen:break
   time.sleep(.02)
  if not seen:raise RuntimeError('no durable solver receipt before recovery threshold')
 finally:proc.kill();proc.wait();stream.close()
 cli('detach','cognition.optimization','--key',str(key),'--no-passphrase')
 started=time.monotonic();cli('run','--max-ticks','2','--tick-seconds','0.1');rto=time.monotonic()-started
 inventory=json.loads(cli('cognition','inventory'));assert not next(x for x in inventory if x['capability_id']=='cognition.optimization')['attached']
 # A new explicit signed laboratory command restores capability attachment, never repair itself.
 cli('attach','cognition.optimization','--key',str(key),'--no-passphrase');cli('run','--max-ticks','3','--tick-seconds','0.1')
 before=json.loads(cli('cognition','knowledge'));cli('run','--max-ticks','2','--tick-seconds','0.1');after=json.loads(cli('cognition','knowledge'));assert before==after
 # Heterogeneous composition through the same signed mission seam; separate native receipts remain typed.
 request=p/'request-0.json'
 spec=json.loads(cli('cognition','mission','--request',str(request),'--id','m:composition','--print-only'))
 params={'requests':[json.loads((p/f'request-{i}.json').read_text()) for i in range(3)]}
 spec['success_checks'][0]['sensor']['capability']='cognition.compose';spec['success_checks'][0]['sensor']['params']=params
 spec['success_checks'][0]['predicate']={'op':'equals','field':'authority_created','value':False}
 spec['strategies']=[];spec['light_cone']['capabilities']=['cognition.compose']
 composed=p/'composition-mission.json';composed.write_text(json.dumps(spec));cli('mission','submit',str(composed),'--key',str(key),'--no-passphrase');cli('run','--max-ticks','2','--tick-seconds','0.1')
 if model:
  cli('model','set','--route','ollama','--local-model',model,'--key',str(key),'--no-passphrase')
  license_file=ROOT/'tests/evidence/cognition-seed-20261001/server-LICENSE.txt'
  request=p/'semantic.json';request.write_text(json.dumps({'problem_id':'rehearsal:semantic','operation':'interpret','geometry':{'latency_limit':30},'data':{'task':'Extract exactly the title MIT License; no proposals.','sources':[{'id':'ollama-license','text':license_file.read_text()}]}}))
  cli('cognition','mission','--request',str(request),'--id','m:semantic-live','--key',str(key),'--no-passphrase');cli('run','--max-ticks','2','--tick-seconds','0.1')
 with observe(home) as journal:
  compositions=[r.payload.get('result',{}).get('output') for r in journal.ledger.by_type('receipt')]
  compositions=[r for r in compositions if isinstance(r,dict) and 'metaconsensus' in r]
  assert compositions and len(compositions[-1]['receipts'])==3
  appraisals=[e.payload for e in journal.replay('mission.appraised')];settled=[e.payload for e in journal.replay('cognition.settled')]
 report={'environment':'Linux container; fresh laboratory key, not Alfonso authority','thresholds':{'recovery_seconds':30,'loss_of_completed_fsynced_receipts':0,'duplicate_external_effects':0,'revoked_attachment_on_restart':True},'observed_recovery_seconds':rto,'revocation_persisted':True,'knowledge_replay_idempotent':True,'appraisals':appraisals,'settlement_records':settled,'compositions':compositions,'local_model':model,'authority_created':False,'VEPMC_founder_device':0}
 assert rto<30;assert any(a.get('verdict')=='VERIFIED' for a in appraisals)
 (p/'report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else None)
