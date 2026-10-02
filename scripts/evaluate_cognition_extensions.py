"""Frozen, consequence-inert qualification of P5 network and bounded LP methods.

This is an evaluator, not a second runtime. Requests go through the canonical
cortex and its separate verifier worker. Tiny exact exhaustive oracles use the
original declarative input and never the candidate's normalization/certificate.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from fractions import Fraction
from itertools import combinations
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from greg.cognition.contracts import CognitiveReceipt, digest
from greg.cognition.cortex import reason, registry_view
from greg.cognition.seed_evaluation import code_digests, environment_record

SUITE=ROOT/'examples/cognition/extensions-heldout-v1.json'
FREEZE=ROOT/'examples/cognition/extensions-freeze-v1.json'


def shortest_oracle(data):
    """Enumerate simple paths; nonnegative source weights suffice for this scope."""
    adjacency=defaultdict(list)
    for u,v,w in data['edges']:
        adjacency[u].append((v,Fraction(w)))
        if not data.get('directed',True):adjacency[v].append((u,Fraction(w)))
    best=None
    def walk(node,seen,cost):
        nonlocal best
        if node==data['goal']:
            best=cost if best is None else min(best,cost);return
        for nxt,w in adjacency[node]:
            if nxt not in seen:walk(nxt,seen|{nxt},cost+w)
    walk(data['start'],{data['start']},Fraction(0))
    return None if best is None else float(best)


def flow_oracle(data):
    """Enumerate all source/sink cuts on the original directed multigraph."""
    nodes=set(data.get('nodes',[]))|{n for u,v,_ in data['edges'] for n in (u,v)}
    internal=sorted(nodes-{data['source'],data['sink']});minimum=None
    for size in range(len(internal)+1):
        for subset in combinations(internal,size):
            side={data['source'],*subset}
            capacity=sum(c for u,v,c in data['edges'] if u in side and v not in side)
            minimum=capacity if minimum is None else min(minimum,capacity)
    return minimum


def linear_oracle(data):
    """Enumerate exact vertices in one/two finite bounded variables.

    This oracle does not import GLOP or the candidate's canonicalization/dual
    checker. All benchmark coefficients are exact integers or binary fractions.
    """
    names=list(data['variables']);n=len(names)
    if n not in (1,2):raise ValueError('oracle scope is one/two bounded variables')
    rows=[]
    for i,name in enumerate(names):
        lo,hi=map(Fraction,data['variables'][name]);row=[Fraction(0)]*n;row[i]=1
        rows.append((row,'>=',lo));rows.append((row,'<=',hi))
    for constraint in data.get('constraints',[]):
        rows.append(([Fraction(constraint['coefficients'].get(name,0)) for name in names],
                     constraint['op'],Fraction(constraint['rhs'])))
    vertices=[]
    for chosen in combinations(rows,n):
        if n==1:
            (a,_,b),=chosen
            if not a[0]:continue
            point=[b/a[0]]
        else:
            (a,_,b),(c,_,d)=chosen;det=a[0]*c[1]-a[1]*c[0]
            if not det:continue
            point=[(b*c[1]-a[1]*d)/det,(a[0]*d-b*c[0])/det]
        feasible=True
        for row,op,rhs in rows:
            lhs=sum(a*x for a,x in zip(row,point))
            if not {'<=':lhs<=rhs,'>=':lhs>=rhs,'==':lhs==rhs}[op]:feasible=False;break
        if feasible:vertices.append(point)
    if not vertices:return None
    objective=data['objective'];values=[sum(Fraction(objective['coefficients'].get(name,0))*x for name,x in zip(names,point)) for point in vertices]
    return float(min(values) if objective['sense']=='min' else max(values))


def generate_suite():
    cases=[]
    def add(stratum,family,t,operation,data,expected):
        identity='extension:'+digest([stratum,family,t]).split(':')[1][:24]
        cases.append({'id':identity,'stratum':stratum,'family':family,'group':stratum+':'+family,'transformation':t,
                      'request':{'problem_id':identity,'operation':operation,'data':data,'geometry':{'latency_limit':10,'compute_limit':100000}},
                      'expected':expected})
    for t in range(5):
        n=t+2
        networks={
            'indirect_chain':{'nodes':['s','a','b','t'],'edges':[['s','a',n],['a','b',.5],['b','t',n],['s','t',3*n]],'start':'s','goal':'t'},
            'unreachable_component':{'nodes':['s','a','b','t'],'edges':[['s','a',n],['b','t',n]],'start':'s','goal':'t'},
            'parallel_and_self_loop':{'edges':[['s','a',n+5],['s','a',n],['a','a',0],['a','t',1],['s','t',n+4]],'start':'s','goal':'t'},
            'undirected_zero_weight':{'edges':[['a','s',n],['a','b',0],['t','b',n+1],['s','t',4*n]],'start':'s','goal':'t','directed':False}}
        for family,data in networks.items():
            cost=shortest_oracle(data);expected={'state':'NONE','proof_type':'search_trace','output':{'cost':cost,'reachable':cost is not None}}
            add('graph',family,t,'shortest_path',data,expected)
            # The project currently declares state_search as the same bounded
            # graph engine. This qualifies that alias, not arbitrary state search.
            reversed_data={**data,'edges':[[v,u,w] for u,v,w in data['edges']],'start':data['goal'],'goal':data['start']}
            reverse_cost=shortest_oracle(reversed_data)
            add('search_alias',family,t,'state_search',reversed_data,
                {'state':'NONE','proof_type':'search_trace','output':{'cost':reverse_cost,'reachable':reverse_cost is not None}})
        flows={
            'layered_bottleneck':{'edges':[['s','a',2*n],['s','b',n],['a','t',n],['b','t',2*n],['a','b',1]],'source':'s','sink':'t'},
            'antiparallel_cycle':{'edges':[['s','a',n],['a','b',n],['b','a',n+1],['b','t',n-1],['a','t',1]],'source':'s','sink':'t'},
            'disconnected_sink':{'nodes':['s','a','b','t'],'edges':[['s','a',n],['a','b',n],['b','s',1]],'source':'s','sink':'t'},
            'parallel_and_self_loop':{'edges':[['s','a',n],['s','a',1],['a','a',n+7],['a','t',n+2],['s','t',1]],'source':'s','sink':'t'}}
        for family,data in flows.items():
            add('flow',family,t,'max_flow',data,{'state':'NONE','proof_type':'flow_certificate','output':{'value':flow_oracle(data)}})
        lp={
            'covering':{'variables':{'x':[0,n+4],'y':[0,n+4]},'constraints':[{'coefficients':{'x':1,'y':1},'op':'>=','rhs':n+1}], 'objective':{'coefficients':{'x':1,'y':3},'sense':'min'}},
            'packing':{'variables':{'x':[0,n+3],'y':[0,n]},'constraints':[{'coefficients':{'x':1,'y':2},'op':'<=','rhs':n+2}], 'objective':{'coefficients':{'x':1,'y':3},'sense':'max'}},
            'fractional_equality':{'variables':{'x':[-n,n],'y':[-n,n]},'constraints':[{'coefficients':{'x':1,'y':2},'op':'==','rhs':.5}], 'objective':{'coefficients':{'x':1,'y':1},'sense':'min'}},
            'degenerate_faces':{'variables':{'x':[0,n],'y':[0,n]},'constraints':[{'coefficients':{'x':1,'y':1},'op':'<=','rhs':n},{'coefficients':{'x':2,'y':2},'op':'<=','rhs':2*n}], 'objective':{'coefficients':{'x':1,'y':1},'sense':'max'}}}
        for family,data in lp.items():
            add('linear_optimal',family,t,'linear_program',data,
                {'state':'NONE','proof_type':'linear_program_certificate','output':{'solver_status':'OPTIMAL','objective_value':linear_oracle(data)}})
        base={'variables':{'x':[0,n]},'constraints':[], 'objective':{'coefficients':{'x':1},'sense':'min'}}
        add('linear_no_optimum','infeasible',t,'linear_program',{**base,'constraints':[{'coefficients':{'x':1},'op':'>=','rhs':n+1}]},
            {'state':'ABSTAIN','output':{'solver_status':'INFEASIBLE'}})
        add('linear_no_optimum','zero_solver_budget',t,'linear_program',{**base,'solver_budget_seconds':0},
            {'state':'UNKNOWN','output':{'solver_status':'NOT_SOLVED'}})
        add('linear_no_optimum','invalid_bounds',t,'linear_program',{**base,'variables':{'x':[n,0]}},{'state':'ABSTAIN'})
        add('linear_no_optimum','unrepresented_clause',t,'linear_program',{**base,'objective':{**base['objective'],'protected_party':'may not be ignored'}},{'state':'ABSTAIN'})
    return {'schema':'cognition-extension-heldout/1','decision':'P5-20261002-E1','split':'heldout','cases':cases,
            'families':{stratum:sorted({c['family'] for c in cases if c['stratum']==stratum}) for stratum in sorted({c['stratum'] for c in cases})},
            'scope':'five strata, 20 cases each, four structural families with five transformations; engineered examples are not population samples',
            'search_scope':'state_search is a bounded weighted graph alias, not an independently implemented general search mechanism',
            'oracle_scope':'enumerated simple paths, all directed cuts, exact bounded one/two-variable vertices; original inputs, no candidate normalization/certificate reuse'}


def source_digests():
    sources=[Path(__file__),ROOT/'scripts/cognition_repertoire_cases.py']
    return {**code_digests(),**{str(path.relative_to(ROOT)):'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest() for path in sources if path.exists()}}


def matches(actual, expected):
    """Check requested fields only; bool never substitutes for a numeric claim."""
    if isinstance(expected,dict):return isinstance(actual,dict) and all(key in actual and matches(actual[key],value) for key,value in expected.items())
    if isinstance(expected,list):return isinstance(actual,list) and len(actual)==len(expected) and all(matches(a,b) for a,b in zip(actual,expected))
    if isinstance(expected,bool):return type(actual) is bool and actual==expected
    if isinstance(expected,(int,float)):
        return not isinstance(actual,bool) and isinstance(actual,(int,float)) and math.isfinite(actual) and abs(actual-expected)<=1e-7*(1+abs(expected))
    return actual==expected


def freeze():
    suite=json.loads(SUITE.read_text())
    if suite!=generate_suite():raise RuntimeError('CONTAMINATED_EVALUATION: extension generator/input mismatch')
    if FREEZE.exists():raise RuntimeError('refusing to replace retained extension freeze')
    record={'schema':'cognition-extension-freeze/1','suite_digest':digest(suite),'source_digests':source_digests(),
            'environment':environment_record(),'budget':{'global_seconds':900,'per_invocation_seconds':10,'compute_limit':100000,'spend_usd':0,'model_calls':0},
            'evaluation_families':suite.get('qualification_families',['graph','search','flow','linear']),
            'scoring':'exact native outcome/status against independent oracle; valid matching typed receipt and structurally verified native proof for answered cases; all unknown/invalid cases remain in denominator',
            'attachment':'only an ephemeral evaluation registry marks the declared qualification families ATTACHED; durable/body defaults remain unchanged and new methods require signed founder attachment',
            'stop':f'all {len(suite["cases"])} cases or 900 seconds; retain every absent invocation as failure; no runtime/score tuning after freeze',
            'case_count':len(suite['cases']),'suite_scope':{key:suite.get(key) for key in ('scope','search_scope','oracle_scope','evidence_limits')},
            'promotion':'none; native qualification cannot create activation, authority, world applicability or superiority'}
    FREEZE.write_text(json.dumps(record,indent=2)+'\n');return record


def assess(output):
    try:suite=json.loads(SUITE.read_text());frozen=json.loads(FREEZE.read_text())
    except (OSError,json.JSONDecodeError) as exc:raise RuntimeError('CONTAMINATED_EVALUATION: missing/unreadable extension freeze') from exc
    if digest(suite)!=frozen['suite_digest'] or source_digests()!=frozen['source_digests']:
        raise RuntimeError('CONTAMINATED_EVALUATION: extension input/source changed')
    if environment_record()['dependencies']!=frozen['environment']['dependencies']:
        raise RuntimeError('CONTAMINATED_EVALUATION: extension dependencies changed')
    output=Path(output);checkpoint=output.with_suffix(output.suffix+'.cases.jsonl')
    if output.exists() or checkpoint.exists():raise RuntimeError('use a new output path; retained evaluation evidence is immutable')
    output.parent.mkdir(parents=True,exist_ok=True)
    registry=registry_view()
    for family in frozen['evaluation_families']:registry.set_state('cognition.'+family,'ATTACHED')
    started=time.monotonic();rows=[]
    for case in suite['cases']:
        receipt=None;error=None;correct=False;completed=False
        if frozen['budget']['global_seconds']-(time.monotonic()-started)<case['request']['geometry']['latency_limit']:
            error='GLOBAL_BUDGET_EXHAUSTED'
        else:
            try:
                receipt=reason(case['request'],registry=registry)
                CognitiveReceipt(**{k:v for k,v in receipt.items() if k!='receipt_id'})
                completed=True;expected=case['expected'];actual=receipt.get('output') or {}
                correct=receipt['abstention_state']==expected['state']
                correct=correct and matches(actual,expected.get('output',{}))
                if expected.get('proof_type'):
                    correct=correct and receipt['proof_type']==expected['proof_type'] and receipt.get('evaluator_result',{}).get('verdict')=='STRUCTURALLY_VERIFIED'
                if expected.get('proof_fields'):
                    correct=correct and matches(receipt.get('proof_artifact'),expected['proof_fields'])
                correct=correct and receipt['authority_created'] is False
            except Exception as exc:error=type(exc).__name__+': '+str(exc)[:250]
        row={'id':case['id'],'stratum':case['stratum'],'family':case['family'],'group':case['group'],
             'completed':completed,'correct':bool(correct),'receipt':receipt,'error':error};rows.append(row)
        with checkpoint.open('a') as stream:stream.write(json.dumps(row)+'\n')
    unchanged=(source_digests()==frozen['source_digests'] and digest(json.loads(SUITE.read_text()))==frozen['suite_digest'] and
               digest(json.loads(FREEZE.read_text()))==digest(frozen))
    strata={name:{'total':sum(r['stratum']==name for r in rows),'completed':sum(r['stratum']==name and r['completed'] for r in rows),
                  'correct':sum(r['stratum']==name and r['correct'] for r in rows)} for name in suite['families']}
    report={'schema':'cognition-extension-results/1','freeze_digest':digest(frozen),'suite_digest':digest(suite),'tested_commit':frozen['environment']['commit'],
            'environment':frozen['environment'],'total':len(rows),'completed':sum(r['completed'] for r in rows),'correct':sum(r['correct'] for r in rows),
            'strata':strata,'results':rows,'run_seconds':time.monotonic()-started,'source_unchanged_at_completion':unchanged,
            'evaluation_state':'VALID_SCOPED_RUN' if unchanged else 'CONTAMINATED_EVALUATION','authority_created':False,
            'scope_limits':[suite.get(key) for key in ('scope','search_scope','oracle_scope','evidence_limits') if suite.get(key)]+['no routing-superiority, world-applicability, activation or founder-device evidence'],
            'post_run_body_defaults':{family:registry_view().state['cognition.'+family] for family in frozen['evaluation_families']},
            'checkpoint':{'path':str(checkpoint),'sha256':'sha256:'+hashlib.sha256(checkpoint.read_bytes()).hexdigest()}}
    output.write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--generate-suite',action='store_true');parser.add_argument('--freeze',action='store_true')
    parser.add_argument('--repertoire',action='store_true',help='separate predeclared future-family suite, never the seed benchmark')
    parser.add_argument('--output',default='tests/evidence/cognition-seed-20261001/extensions-heldout-v1.json');args=parser.parse_args()
    if args.repertoire:
        from scripts.cognition_repertoire_cases import generate_suite as generate_repertoire_suite
        generate_suite=generate_repertoire_suite
        SUITE=ROOT/'examples/cognition/repertoire-heldout-v1.json';FREEZE=ROOT/'examples/cognition/repertoire-freeze-v1.json'
        if args.output=='tests/evidence/cognition-seed-20261001/extensions-heldout-v1.json':args.output='tests/evidence/cognition-seed-20261001/repertoire-heldout-v1.json'
    if args.generate_suite:
        if SUITE.exists():raise SystemExit('refusing to replace retained extension inputs')
        SUITE.write_text(json.dumps(generate_suite(),indent=2)+'\n')
    elif args.freeze:print(digest(freeze()))
    else:
        report=assess(args.output);print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
