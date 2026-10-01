"""Read-only cognition/1 extension of the existing rich Cortex geometry.

These projections add explicit unknowns and provenance; they never classify
unseen natural language, alter method eligibility, or authenticate premises.
"""
import math
from cortex.contracts import ProblemGeometry, ConsequenceVector, ResourceLimits, digest

EPISTEMIC = {'formal': 'constraint_feasibility', 'optimization': 'optimization',
             'estimation': 'estimate', 'causal': 'causal', 'semantic': 'semantic', 'evidence': 'semantic'}
OBJECTIVE = {'formal': 'decide_feasibility', 'optimization': 'optimize_objective',
             'estimation': 'estimate_quantity', 'causal': 'estimate_effect', 'semantic': 'synthesize', 'evidence': 'assess_claim'}


def geometry(p, c, *, validated=False):
    # Invalid/ineligible input is still receipted, but cannot populate asserted
    # structural features. Its original bytes remain in the signed mission.
    data, kind = c['data'] if validated else {}, c['kind']
    vector = p['consequence']['exposures']
    canonical_harm = {}
    for dim, wire in [('physical','physical'), ('financial','financial'), ('rights','legal_rights'),
                      ('privacy','privacy'), ('reputational','reputational'), ('discrimination','discrimination'),
                      ('third_party','third_party'), ('irreversible_disclosure','disclosure'), ('systemic','systemic'), ('tail_risk','tail_risk')]:
        canonical_harm[dim] = 'unknown' if vector[wire] is None else ('none','low','medium','high')[vector[wire]]
    constraints = tuple(x['id'] for x in data.get('constraints', []))
    unresolved = ('classification_uncertainty', 'world_domain', 'novelty', 'actors_and_incentives',
                  'empirical_applicability', 'attention_ceiling', 'likelihood_and_affected_parties')
    geo = ProblemGeometry(problem_id=p['problem_id'], epistemic_class=EPISTEMIC.get(kind),
        claim_type='intervention' if kind == 'causal' else 'factual_support' if kind in ('evidence','semantic') else None,
        objective=OBJECTIVE.get(kind, 'unknown'), ambiguity='unknown',
        exactness='exact_required' if kind in ('formal','optimization') else 'approximate_ok' if kind == 'estimation' else 'unknown',
        uncertainty='unknown', causal_structure='declared_experiment' if kind == 'causal' and data.get('design') == 'randomized_two_arm' else 'unidentified' if kind == 'causal' else 'none',
        constraints=constraints, temporal_character='static', evidence_quality='unknown',
        resource_limits=ResourceLimits(max_cost_usd=0, max_latency_s=p['budget_ms']/1000,
             max_model_calls=1 if kind == 'semantic' else 0, max_solver_calls=1 if kind in ('formal','optimization') else 0),
        consequence_vector=ConsequenceVector.from_partial(canonical_harm), consequence_class=p['consequence']['class'],
        reversibility='reversible' if p['consequence']['class'] == 'read_only' else 'unknown',
        unresolved_fields=unresolved, provenance={'epistemic_class': {'source':'requester_declared','input_digest':digest(c)},
          'consequence_vector': {'source':'requester_declared','independent_assessment':False},
          'constraints': {'source':'payload_structure'}, 'unresolved_fields': {'source':'default_unknown'}}).to_dict()
    variables = data.get('variables', {})
    geo['wire_extension'] = {
        'objective_text':p['objective'], 'success_criterion':'every requested claim passes its scoped independent check',
        'failure_criterion':'missing proof, mismatch, refusal, unavailable method or exhausted verification budget',
        'domain':'bounded structured computation; real-world domain unresolved', 'subquestions':[c['claim_id']],
        'classification_uncertainty':None, 'state_observability':'encoded inputs fully observed; world partially observed',
        'determinism':'model-dependent' if kind=='semantic' else 'bounded deterministic calculation',
        'discrete_continuous':'discrete' if variables else 'continuous' if kind in ('estimation','causal') else 'not_applicable',
        'graph_structure':None, 'constraint_density': len(constraints)/len(variables) if variables else None,
        'search_space':math.prod(hi-lo+1 for lo,hi in variables.values()) if variables else None,
        'scale':{'variables':len(variables),'constraints':len(constraints),'sources':len(data.get('sources',[]))},
        'components':{k:k==kind for k in ('causal','forecasting','optimization','control','allocation','strategic','adversarial')},
        'actors_and_incentives':None, 'data_provenance':{s['id']:{k:s[k] for k in ('sha256','observed_at','max_age_seconds','provenance','quality')} for s in data.get('sources',[])},
        'missingness':data.get('missingness','unknown'), 'identifiability':'conditional on declared design' if kind=='causal' else 'not_applicable',
        'novelty':None, 'embodiment_required':'none for computation; consequential use separately gated',
        'deadline':'monotonic invocation budget', 'compute_ceiling':{'address_space_bytes':2*1024**3,'cpu_seconds':12},
        'attention_ceiling':None, 'rights_impact':vector['legal_rights'], 'legal_content':'unresolved',
        'human_value_content':p['consequence']['human_judgment'], 'unknown_geometry':kind not in EPISTEMIC,
        'out_of_distribution':c['conditions'].get('out_of_distribution',False),
        'conditions':c['conditions']}
    return geo


def enrich(p, receipt):
    for c, a in zip(p['claims'], receipt['claims']):
        native = a.get('result') or {}
        valid = bool(a.get('verification') and a['verification']['valid'] and
                     a['outcome'] in ('CONDITIONAL_RESULT','ANSWERED_WITHIN_SCOPE'))
        a['problem_geometry'] = geometry(p,c,validated=valid)
        a['artifact_digest'] = digest({'original_claim':c,'artifact':native,'proof_class':a['proof_class']})
        a['assumptions'] = native.get('assumptions',native.get('coverage',{}).get('assumptions',[]))
        a['formalization_coverage'] = None if c['kind'] not in ('formal','optimization') or not valid else {
            **c['data']['coverage'], 'unsupported_translations':[], 'empirical_evidence_refs':[],
            'model_limits':'restricted signed declarative integers; no natural-language completeness claim'}
        a['excluded_variables'] = c['data']['coverage'].get('omissions',[]) if valid and c['kind'] in ('formal','optimization') else None
        a['uncertainty'] = {'empirical_applicability':'WORLD_UNVERIFIED',
            'calibrated_confidence':None,'interval':native.get('interval_95'),
            'scenario_bounds':[native.get('low'),native.get('high')] if c['kind']=='estimation' else None}
        a['missing_information'] = a['reasons'] if not receipt['answered'] else ['independent world applicability']
        a['contribution'] = {'role':'compute subclaim','causal_attribution':'unproven','separate_outcome_required':True}
    receipt['consequence_vector'] = {dim:{'severity':v,'likelihood_range':None,'affected_parties':[],
        'uncertainty':'requester declaration, not independent harm assessment', 'reversibility':'unknown',
        'mitigations':['read-only computation ceiling; consequential use requires fresh authority'],
        'evidence':['signed problem declaration']} for dim,v in p['consequence']['exposures'].items()}
    receipt['evidence_digests'] = [{ 'claim_id':a['claim_id'], 'sources':(a.get('result') or {}).get('source_digests',{})}
                                 for a in receipt['claims']]
    receipt['outcome_references'] = []  # later references are a projection of append-only settlement events
    receipt['calibration'] = {'status':'NOT_MEASURED','confidence':None}
    receipt['thinking_budget'] = {'mandatory_checks_reserved':True, 'optional_deeper_work':False,
        'stopping_reason':'no authorized optional escalation; smallest eligible exact method or non-answer',
        'decision_value_of_optional_information':None,'limit':'No VOI benefit or entropy-improvement claim.'}
    return receipt
