"""Independent bounded certificate qualification, not benchmark superiority evidence.

Reproduces the review's 250 flow and 250 shortest-path workloads exactly.
Flow generator: random.Random(seed + 50991), seed=0..249, 2..6 nodes,
               ordered pairs independently included with probability .5,
               capacities rng.randrange(10); source=n0, sink=n(last).
Path generator: random.Random(seed + 60991), seed=0..249, 2..6 nodes,
               ordered pairs independently included with probability .25,
               weights rng.randrange(100)/10, directed iff seed is even.
LP cases are deliberate forgeries, with unchanged signed-input digest/model.
No models, network calls, authority changes, or repository writes are performed.
"""
from dataclasses import asdict
from itertools import combinations
from fractions import Fraction
import random
from greg.cognition.contracts import ProblemGeometry
from greg.cognition.solvers import SOLVERS
from greg.cognition.verification import verify
geom=asdict(ProblemGeometry(latency_limit=10,compute_limit=100000))
for seed in range(250):
 r=random.Random(seed+50991);nodes=[f'n{i}' for i in range(r.randint(2,6))]
 edges=[[u,v,r.randrange(10)] for u in nodes for v in nodes if r.random()<.5]
 d={'nodes':nodes,'edges':edges,'source':nodes[0],'sink':nodes[-1]}
 a=SOLVERS['flow'](d,geom)
 cuts=[sum(c for u,v,c in edges if u in side and v not in side) for n in range(len(nodes)-1) for subset in combinations(nodes[1:-1],n) for side in [{nodes[0],*subset}]]
 assert a['output']['value']==min(cuts), (seed,d,a,min(cuts))
 assert verify('flow',d,a,'flow_certificate')['verdict']=='STRUCTURALLY_VERIFIED',(seed,d,a)
print('250 flow cases: antiparallel/selfloop/dense arcs match exhaustive mincut')
for seed in range(250):
 r=random.Random(seed+60991);nodes=[f'n{i}' for i in range(r.randint(2,6))]
 edges=[[u,v,r.randrange(100)/10] for u in nodes for v in nodes if r.random()<.25]
 d={'nodes':nodes,'edges':edges,'start':nodes[0],'goal':nodes[-1],'directed':seed%2==0}
 a=SOLVERS['graph'](d,geom)
 dist={nodes[0]:Fraction(0)}
 arcs=[(u,v,Fraction(w)) for u,v,w in edges]
 if not d['directed']:arcs +=[(v,u,w) for u,v,w in arcs]
 for _ in range(len(nodes)-1):
  for u,v,w in arcs:
   if u in dist and (v not in dist or dist[v]>dist[u]+w):dist[v]=dist[u]+w
 assert a['output']['reachable']==(nodes[-1] in dist),(seed,d,a)
 assert a['output']['cost']==(float(dist[nodes[-1]]) if nodes[-1] in dist else None),(seed,d,a,dist)
 assert verify('graph',d,a,'search_trace')['verdict']=='STRUCTURALLY_VERIFIED',(seed,d,a)
print('250 graph cases: directed/undirected/unreachable/selfloop match Fraction relaxation')
for coefficient,bounds,bad_value,bad_upper in [(1e-7,[0,1e9],1e9,1e-7),(1e-8,[-1e9,0],0.,0.)]:
 d={'variables':{'x':bounds},'constraints':[],'objective':{'coefficients':{'x':coefficient},'sense':'min'}}
 a=SOLVERS['linear'](d,geom)
 true=a['output']['objective_value']
 a['output']['solution']['x']=bad_value;a['output']['objective_value']=coefficient*bad_value
 a['proof']['claim'].update(x=[bad_value],z_l=[0.],z_u=[bad_upper])
 a['proof']['bound']=coefficient*bad_value;a['proof']['gap']=0.
 report=verify('linear',d,a,'linear_program_certificate')
 print('LP adversarial retest',{'coefficient':coefficient,'bounds':bounds,'actual_optimum':true,'forged_objective':a['output']['objective_value'],'verdict':report['verdict'],'dissent':report['dissent']})
 assert report['verdict']=='REFUTED'
