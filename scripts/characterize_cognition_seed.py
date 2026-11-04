"""Characterize measured native behavior; no consciousness or universal competence score."""
import json, statistics, sys
from pathlib import Path

def characterize(evidence):
 p=Path(evidence);benchmark=json.loads((p/'heldout.json').read_text());recovery=json.loads((p/'cli-rehearsal/report.json').read_text());mutations=json.loads((p/'mutations-final.json').read_text())
 # Native workloads and qualification boundaries are explicit for each dimension.
 results=benchmark['results'];times=[r['routed']['latency'] for r in results] if results and 'routed' in results[0] else []
 dimensions={
 'responsiveness':{'measurement':'bounded held-out wall-clock latency by stratum','workload':'320 native held-out cases','evidence':benchmark['strata']},
 'memory_depth':{'measurement':'last 32 observation references per projected cell; durable journal has retention controls','workload':'CLI cognition knowledge across process restart','evidence':{'replay_unchanged':recovery['knowledge_replay_idempotent'],'limit':'not a measured semantic context-memory horizon'}},
 'prediction_horizon':{'state':'not_applicable','reason':'seed makes no qualified forecasting/control prediction'},
 'adaptability':{'state':'not_applicable','reason':'static routing is frozen; learning does not alter permitted choices'},
 'persistence':{'measurement':'recovery wall-clock seconds after process kill; no loss of completed fsynced receipts','workload':'canonical CLI kill/restart with revoked attachment','evidence':{'seconds':recovery['observed_recovery_seconds'],'revocation':recovery['revocation_persisted']}},
 'error_correction':{'measurement':'critical removed gates detected by tests; later refutation removes current competence','workload':'seven disposable-source mutations and native appraisal correction test','evidence':{'detected':sum(r['detected'] for r in mutations['results']),'denominator':len(mutations['results'])}},
 'supported_problem_space_size':{'measurement':'declared finite input ceilings, not general domain coverage','workload':'bounded linear-real SMT, bounded integer CP-SAT, product ranges and randomized complete two-arm data','evidence':'See greg/cognition/solvers.py input validators; no broad field solved claim'},
 'cooperation':{'measurement':'three separately typed method receipts in signed composition','workload':'optimization, estimation and synthetic causal first passes','evidence':{'receipt_count':len(recovery['compositions'][-1]['receipts']),'gain':'unproven; shared source/runtime specification dependencies'}},
 'generalization':{'measurement':'exact evaluator success per stratum with template correlation disclosed','workload':'20 held-out cases per stratum, native transformations','evidence':{'correct':benchmark['correct'],'denominator':benchmark['receipted_denominator'],'limits':'64 correlated groups; insufficient broad generalization evidence'}},
 'higher_scale_coherence':{'measurement':'claim/proof jurisdiction preserved by metaconsensus; no voting empirical truth','workload':'signed heterogeneous composition','evidence':recovery['compositions'][-1]['metaconsensus']}}
 return {'schema':'seed-characterization/1','dimensions':dimensions,'calibration':'real-world confidence/calibration unmeasured; geometry-specific local predicate counts only','correlated_failure':'shared Python, source requirements, declarative translation and deployment; separate numerical checks do not remove these dependencies','authority_created':False}
if __name__=='__main__':
 p=Path(sys.argv[1]);(p/'characterization.json').write_text(json.dumps(characterize(p),indent=2)+'\n')
