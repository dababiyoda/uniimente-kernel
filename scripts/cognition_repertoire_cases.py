"""Pure future-family qualification inputs and narrowly independent labels.

These fixtures characterize native computation; they cannot establish field
calibration, participant competence, plant stability or scientific novelty.
"""
from fractions import Fraction
import math
import random
from greg.cognition.contracts import digest


def _mdp_tree(data,state,horizon):
    if not horizon:return Fraction(0),None
    scores={}
    for action,distribution in data['transitions'][state].items():
        scores[action]=Fraction(data['rewards'][state][action])+Fraction(data.get('discount',1))*sum(
            Fraction(probability)*_mdp_tree(data,target,horizon-1)[0] for target,probability in distribution.items())
    action=max(sorted(scores),key=scores.get)
    return scores[action],action


def generate_suite():
    cases=[];families={}
    proofs={'beta_update':'posterior','pid':'control_trace','value_of_information':'information_value','simulate':'simulation_trace',
            'minimax':'game_model','anomalies':'pattern_evidence','mdp':'search_trace','quorum':'collective_trace',
            'evolve_vector':'collective_trace','setpoint':'pattern_evidence'}
    def add(stratum,family,t,operation,data,output=None,*,state='NONE',proof_fields=None):
        identity='repertoire:'+digest([stratum,family,t]).split(':')[1][:24]
        expected={'state':state}
        if output is not None:expected['output']=output
        if state=='NONE':expected['proof_type']=proofs[operation]
        if proof_fields:expected['proof_fields']=proof_fields
        cases.append({'id':identity,'stratum':stratum,'family':family,'group':stratum+':'+family,'transformation':t,
                      'request':{'problem_id':identity,'operation':operation,'data':data,'geometry':{'latency_limit':10,'compute_limit':100000}},
                      'expected':expected})
        families.setdefault(stratum,[])
        if family not in families[stratum]:families[stratum].append(family)
    for t in range(5):
        n=t+2
        for family,alpha,beta,successes,failures in [('uniform',1,1,n,n+1),('informative',n,2*n,1,3),('zero_observations',n,n+1,0,0),('imbalanced',.5,.5,3*n,0)]:
            a=Fraction(alpha)+successes;b=Fraction(beta)+failures
            add('probabilistic',family,t,'beta_update',{'alpha':alpha,'beta':beta,'successes':successes,'failures':failures},
                {'alpha':float(a),'beta':float(b),'mean':float(a/(a+b)),'variance':float(a*b/((a+b)**2*(a+b+1)))})
        control=[
            ('positive_saturation',{'observed':0,'target':n,'kp':2,'ki':1,'correction_limit':1},{'correction':1,'state':{'integral':0,'previous_error':n}}),
            ('negative_saturation',{'observed':n,'target':0,'kp':2,'ki':1,'correction_limit':1},{'correction':-1,'state':{'integral':0,'previous_error':-n}}),
            ('unsaturated_proportional',{'observed':1,'target':n,'kp':.5,'correction_limit':10},{'correction':.5*(n-1),'state':{'integral':n-1,'previous_error':n-1}}),
            ('derivative_state',{'observed':n,'target':n,'kp':0,'ki':0,'kd':.5,'dt':.5,'state':{'integral':2,'previous_error':1},'correction_limit':10},{'correction':-1,'state':{'integral':2,'previous_error':0}})]
        for family,data,output in control:add('control',family,t,'pid',data,output)
        for family,prior,cost,scenarios in [
            ('worth_acquiring',n,1,[{'probability':.5,'best_value':n+2},{'probability':.5,'best_value':n+4}]),
            ('exact_cost_tie',n,2,[{'probability':1,'best_value':n+2}]),
            ('negative_decision_value',n,0,[{'probability':.5,'best_value':n-1},{'probability':.5,'best_value':n-3}]),
            ('zero_entropy_value',n,0,[{'probability':.25,'best_value':n},{'probability':.75,'best_value':n}])]:
            gross=sum(Fraction(s['probability'])*Fraction(s['best_value']) for s in scenarios)-prior
            add('information',family,t,'value_of_information',{'prior_best_value':prior,'cost':cost,'posterior_scenarios':scenarios},
                {'gross_value':float(gross),'net_value':float(gross-cost),'acquire':gross>cost})
        for family,p,samples,steps in [('zero_event',0,20,n),('certain_event',1,20,n),('seeded_half',.5,24,n),('full_distribution_prefix',.25,125,n)]:
            seed=101+t;rng=random.Random(seed);values=[sum(rng.random()<p for _ in range(steps)) for _ in range(samples)]
            add('simulation',family,t,'simulate',{'seed':seed,'samples':samples,'steps':steps,'step_probability':p},
                {'mean':sum(values)/samples,'minimum':min(values),'maximum':max(values)},proof_fields={'scenario_digest':digest(values),'samples':samples})
        games=[('symmetric_mixed',[[n,-n],[-n,n]],0),('dominant_row',[[n+2,n+1],[n,n-1]],n+1),
               ('one_column',[[n],[n+1],[n-1]],n+1),('asymmetric_mixed',[[3*n,0],[0,n]],.75*n)]
        for family,payoffs,value in games:add('game',family,t,'minimax',{'payoffs':payoffs},{'value':value,'solver_status':'OPTIMAL'})
        patterns=[('constant',[n]*6,2,[]),('positive_outlier',[0]*5+[n],2,[5]),
                  ('symmetric_outliers',[-n]+[0]*8+[n],2,[0,9]),('balanced_no_outlier',[-n,n]*4,2,[])]
        for family,observations,threshold,anomalies in patterns:
            mean=sum(observations)/len(observations);sd=math.sqrt(sum((x-mean)**2 for x in observations)/len(observations))
            add('pattern',family,t,'anomalies',{'observations':observations,'threshold':threshold},{'anomalies':anomalies,'mean':mean,'sd':sd})
        mdps={
            'absorbing_reward':{'transitions':{'s':{'stay':{'s':1}}},'rewards':{'s':{'stay':n}},'horizon':3},
            'delayed_choice':{'transitions':{'a':{'now':{'a':1},'later':{'b':1}},'b':{'stay':{'b':1}}},'rewards':{'a':{'now':n,'later':0},'b':{'stay':3*n}},'horizon':2},
            'stochastic_transition':{'transitions':{'a':{'choose':{'a':.5,'b':.5}},'b':{'stay':{'b':1}}},'rewards':{'a':{'choose':n},'b':{'stay':2*n}},'horizon':3},
            'discounted_negative':{'transitions':{'a':{'avoid':{'b':1},'stay':{'a':1}},'b':{'stay':{'b':1}}},'rewards':{'a':{'avoid':-1,'stay':-n},'b':{'stay':0}},'horizon':3,'discount':.5}}
        for family,data in mdps.items():
            oracle={state:_mdp_tree(data,state,data['horizon']) for state in data['transitions']}
            add('sequential',family,t,'mdp',data,{'values':{state:float(result[0]) for state,result in oracle.items()},'policy':{state:result[1] for state,result in oracle.items()}})
        quorums=[('unanimous',[('a',1),('a',1),('a',1)],.67),('weighted_majority',[('a',1),('a',.5),('b',(t+1)/8)],.7),
                 ('tie_abstention',[('a',1),('b',1)],.6),('below_threshold',[('a',1),('a',1),('b',1),('c',1)],.75)]
        for family,observations,threshold in quorums:
            scores={}
            for choice,weight in observations:scores[choice]=scores.get(choice,0)+weight
            ordered=sorted(scores,key=lambda choice:(-scores[choice],choice));winner=ordered[0]
            crossed=scores[winner]/sum(scores.values())>=threshold and (len(ordered)==1 or scores[winner]>scores[ordered[1]])
            rows=[{'observer_id':f'o{i}','independence_group':f'declared-{i}','choice':choice,'weight':weight} for i,(choice,weight) in enumerate(observations)]
            add('collective',family,t,'quorum',{'observations':rows,'threshold':threshold,'minimum_independent':2},
                {'choice':winner if crossed else None,'quorum_crossed':crossed,'scores':scores},state='NONE' if crossed else 'NO_QUORUM')
        evolution=[('interior',[.25*n],[[-n,n]]),('upper_clipped',[n+1],[[-1,1]]),('lower_clipped',[-n-1],[[-1,1]]),('two_dimensions',[n+1,-n-1],[[-1,1],[-2,2]])]
        for family,center,bounds in evolution:
            candidate=[max(low,min(high,value)) for value,(low,high) in zip(center,bounds)]
            optimum=sum((x-c)**2 for x,c in zip(candidate,center))
            add('evolutionary',family,t,'evolve_vector',{'center':center,'bounds':bounds,'seed':55+t,'generations':3},
                proof_fields={'analytic_baseline':{'candidate':candidate,'fitness':optimum}})
        for family,observed,low,high,state in [('below',-n,0,n,'stimulate'),('above',2*n,0,n,'inhibit'),('lower_boundary',0,0,n,'abstain'),('upper_boundary',n,0,n,'abstain')]:
            add('micro',family,t,'setpoint',{'observed':observed,'low':low,'high':high},{'state':state})
        for family,panel in [('unverified_expert',{'participants':[f'proposed:expert-{t}'],'expertise':['unverified']}),
                             ('conflict',{'participants':['proposed:reviewer'],'conflicts':['declared conflict']}),
                             ('minority_dissent',{'participants':['proposed:panel'],'dissent':['material unresolved objection']}),
                             ('authority_claim',{'participants':[],'decision_authority':'unauthenticated caller assertion'})]:
            add('human',family,t,'human_review',panel,state='HUMAN_REVIEW_REQUIRED')
    return {'schema':'cognition-repertoire-heldout/1','decision':'P5-20261002-E2','split':'heldout','families':families,'cases':cases,
            'qualification_families':list(families),
            'scope':'11 narrow declared families, 20 held-out cases per family, four structural conditions and five related transformations; native computation qualification, not broad-field competence',
            'oracle_scope':'exact Beta/VOI arithmetic, predeclared bounded PID/state examples, complete finite MDP decision trees, analytic finite game/quadratic references, explicit source-level statistical/quorum expectations',
            'evidence_limits':'simulation uses the specified Python seeded PRNG shared dependency; quorum independence labels are unauthenticated; evolution is judged by checked candidate plus analytic baseline, not superiority; human work remains unavailable without authentic participation; no predictive calibration, plant stability, generalized learning or empirical outcomes'}
