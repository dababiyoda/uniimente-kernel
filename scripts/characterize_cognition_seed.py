"""Describe selected native evidence; no consciousness or superiority score.

Explicit paths can select the final run after it exists. Missing evidence stays
missing; the harness never chooses a newer report by filename or assumes that
historical observations characterize the current source revision.
"""
import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path


def _read(path):
    path=Path(path)
    source={'path':str(path),'sha256':None,'state':'MISSING'}
    if not path.is_file():return None,source
    raw=path.read_bytes()
    value=json.loads(raw)
    if not isinstance(value,dict):raise ValueError(f'{path}: expected evidence object')
    source.update(sha256='sha256:'+hashlib.sha256(raw).hexdigest(),state='READ')
    return value,source


def _native_trials(benchmark):
    """Read v4 repeats and earlier rows without manufacturing lost receipts."""
    trials=[];planned=0
    for row in (benchmark or {}).get('results',[]):
        if isinstance(row.get('candidate'),dict):
            planned+=row['candidate']['planned']
            trials.extend(t for t in row['candidate']['trials'] if t.get('completed') and isinstance(t.get('receipt'),dict))
        else:
            planned+=1
            receipt=row.get('receipt',row.get('routed'))
            if isinstance(receipt,dict):trials.append({'receipt':receipt,'completed':True,'correct':row.get('correct')})
    # Earlier reports omitted uncompleted rows; a partial file likewise cannot
    # shrink the frozen repeated-trial workload to its surviving rows.
    if benchmark:
        declared=benchmark.get('planned_trials',{}).get('candidate')
        if declared is None:declared=benchmark.get('repetitions',{}).get('planned_trials_per_measured_arm')
        if declared is None and 'repetitions' not in benchmark:declared=benchmark.get('total',planned)
        if declared is not None:planned=max(planned,declared)
    return trials,planned


def _latency_summary(receipts):
    values=sorted(r['latency'] for r in receipts if isinstance(r.get('latency'),(int,float))
                  and not isinstance(r['latency'],bool) and math.isfinite(r['latency']) and r['latency']>=0)
    if not values:return {'observations':0,'seconds_mean':None,'seconds_p50':None,'seconds_p95':None,'seconds_max':None}
    return {'observations':len(values),'seconds_mean':statistics.mean(values),'seconds_p50':statistics.median(values),
            'seconds_p95':values[max(0,math.ceil(.95*len(values))-1)],'seconds_max':values[-1]}


def characterize(evidence,*,benchmark_path=None,recovery_path=None,mutation_path=None):
    base=Path(evidence)
    benchmark,b_source=_read(benchmark_path or base/'heldout.json')
    recovery,r_source=_read(recovery_path or base/'cli-rehearsal/report.json')
    mutations,m_source=_read(mutation_path or base/'mutations-final.json')
    trials,planned=_native_trials(benchmark);receipts=[t['receipt'] for t in trials]
    recovery=recovery or {};mutations=mutations or {}
    compositions=recovery.get('compositions',[])
    composition=compositions[-1] if compositions else None
    mutation_results=mutations.get('results',[])
    data_present=bool(benchmark)
    contaminated=bool(data_present and (benchmark.get('evaluation_state')=='CONTAMINATED_EVALUATION' or benchmark.get('source_unchanged_at_completion') is False))
    complete=bool(data_present and not contaminated and benchmark.get('completed')==benchmark.get('total') and len(trials)==planned)
    def measured(measurement,workload,evidence,*,present,limits):
        return {'state':'OBSERVED' if present else 'NEEDS_EVIDENCE','measurement':measurement,
                'native_workload':workload,'evidence':evidence,'limits':limits}
    dimensions={
        'responsiveness':measured('wall-clock seconds per executed native invocation, with observed tail latency',
            ['greg/cognition/seed_evaluation.py: automated selected held-out native trials'],
            {**_latency_summary(receipts),'planned_native_trials':planned,'receipted_native_trials':len(trials),
             'strata':(benchmark or {}).get('strata',{})},present=bool(receipts),
            limits='observed workload/environment only; missing trials retained; CPU, RAM, storage and energy consumption not inferred from latency'),
        'memory_depth':measured('retained knowledge projection unchanged across process restart/replay',
            ['scripts/rehearse_cognition_seed.py: canonical CLI kill/restart/reconcile','greg/cognition/cells.py: last 32 observation-reference projection'],
            {'replay_unchanged':recovery.get('knowledge_replay_idempotent'),'configured_projection_reference_ceiling':32,
             'measured_maximum_memory_horizon':None},present='knowledge_replay_idempotent' in recovery,
            limits='32 is a configured projection ceiling, not an experimentally measured memory capacity; semantic context depth not tested'),
        'prediction_horizon':{'state':'NOT_APPLICABLE','measurement':'maximum validated forecast/control horizon',
            'native_workload':[],'evidence':None,'limits':'selected seed suite makes no qualified forecast/control horizon claim; future family qualification must supply its own time-indexed workload'},
        'adaptability':{'state':'NOT_APPLICABLE','measurement':'held-out routing improvement after a protected update',
            'native_workload':[],'evidence':None,'limits':'retained policy is deterministic/static; bookkeeping updates do not establish learned routing or automatic promotion'},
        'persistence':measured('recovery seconds following process kill and retained revocation',
            ['scripts/rehearse_cognition_seed.py: actual signed CLI mission/interrupt/restart'],
            {'seconds':recovery.get('observed_recovery_seconds'),'predeclared_thresholds':recovery.get('thresholds'),
             'revocation':recovery.get('revocation_persisted'),'environment':recovery.get('environment'),
             'founder_device_verified':recovery.get('VEPMC_founder_device')},present='observed_recovery_seconds' in recovery,
            limits='scoped laboratory process interruption; no founder-device, multi-body failover, backup restoration or universal exactly-once guarantee'),
        'error_correction':measured('deliberately removed critical guards detected by their independent rejection tests',
            ['scripts/ci/check_seed_mutants.py: selected disposable-source mutation run',
             'tests/unit/test_greg_cognition.py: retained appraisal/settlement correction boundaries'],
            {'detected':sum(r.get('detected') is True for r in mutation_results),'denominator':len(mutation_results),
             'failures':[r.get('mutant') for r in mutation_results if r.get('detected') is not True]},present=bool(mutation_results),
            limits='detecting seeded defects is not a field defect-escape rate or evidence of stress-induced improvement; correction-test results require their own execution record'),
        'supported_problem_space_size':{'state':'DECLARED_SCOPE','measurement':'validated input ceilings and exact native domain restrictions',
            'native_workload':['greg/cognition/solvers.py: input validators','tests/unit/test_cognition_seed_gates.py: native domain boundaries'],
            'evidence':{'heldout_problem_count':(benchmark or {}).get('total'),'qualified_field_size':None},
            'limits':'bounded linear-real feasibility, integer optimization, product ranges and complete two-arm synthetic data; declarative ceilings are not empirical coverage of an entire field'},
        'cooperation':measured('separately typed first-pass receipts preserved in one signed heterogeneous composition',
            ['scripts/rehearse_cognition_seed.py: optimization/estimation/synthetic-causal composition'],
            {'receipt_count':len(composition.get('receipts',[])) if composition else None,
             'marginal_gain':None,'superiority':composition.get('superiority') if composition else None},present=composition is not None,
            limits='composition execution is measured; lift over constituents/simple pipeline and shared-error independence remain unproven'),
        'generalization':measured('per-problem task-contract performance on the selected constructed held-out suite',
            ['greg/cognition/seed_evaluation.py: 20 problems per stratum; transformations grouped together'],
            {'correct_all_candidate_trials':(benchmark or {}).get('correct'),'problem_denominator':(benchmark or {}).get('total'),
             'receipted_problem_count':(benchmark or {}).get('receipted_denominator'),
             'fully_completed_problem_count':(benchmark or {}).get('completed'),
             'planned_native_trials':planned,'receipted_native_trials':len(trials),
             'mean_candidate_success_rate':(benchmark or {}).get('mean_candidate_success_rate'),
             'uncompleted_problem_count':len((benchmark or {}).get('uncompleted',[])),
             'sample_size':(benchmark or {}).get('sample_size'),'repetitions':(benchmark or {}).get('repetitions'),
             'strata':(benchmark or {}).get('strata',{})},present=data_present,
            limits='320 problems remain the denominator; repetitions are within-problem observations, not independent tasks. Constructed related families, limited semantic rubric and missing strongest baseline prevent population-superiority claims'),
        'higher_scale_coherence':measured('claim/proof jurisdictions remain separate through metaconsensus',
            ['scripts/rehearse_cognition_seed.py: signed heterogeneous composition','greg/cognition/cortex.py: epistemic reconciliation'],
            composition.get('metaconsensus') if composition else None,present=composition is not None,
            limits='native scoped coherence only; no evidence of unified consciousness, external benefit, authority creation or institutional acceptance')}
    return {'schema':'seed-characterization/2','profile_state':'CONTAMINATED_EVIDENCE' if contaminated else 'OBSERVED_COMPLETE_SCOPED_RUN' if complete else 'PARTIAL_OR_HISTORICAL_EVIDENCE',
            'sources':{'benchmark':b_source,'recovery':r_source,'mutations':m_source},
            'benchmark_binding':{'freeze_digest':(benchmark or {}).get('freeze_digest'),'suite_digest':(benchmark or {}).get('suite_digest'),
                                 'tested_commit':(benchmark or {}).get('tested_commit'),'evaluation_state':(benchmark or {}).get('evaluation_state'),
                                 'source_unchanged_at_completion':(benchmark or {}).get('source_unchanged_at_completion')},
            'harness_sha256':'sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'source_limits':'digests identify selected bytes, not factual truth; receipt validation belongs to the referenced evaluator; current-revision applicability is not inferred from historical files',
            'dimensions':dimensions,'calibration':'unmeasured real-world calibration; no confidence score, causal credit or universal competence badge',
            'correlated_failure':'shared Python, source requirements, declarative translation and deployment; separate numerical checks do not remove these dependencies',
            'authority_created':False,'whole_machine_complete':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('evidence')
    parser.add_argument('--benchmark');parser.add_argument('--recovery');parser.add_argument('--mutations')
    parser.add_argument('--output',help='new versioned output path; existing evidence is never overwritten')
    args=parser.parse_args()
    output=Path(args.output) if args.output else Path(args.evidence)/'characterization-v2.json'
    if output.exists():raise SystemExit('refusing to overwrite retained characterization evidence')
    value=characterize(args.evidence,benchmark_path=args.benchmark,recovery_path=args.recovery,mutation_path=args.mutations)
    output.write_text(json.dumps(value,indent=2)+'\n')
