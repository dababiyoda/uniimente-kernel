"""Behavioral profiles bind selected evidence and preserve missing observations."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from scripts.characterize_cognition_seed import characterize


def test_v4_profiles_preserve_problem_denominator_repeated_trials_and_missing_sources(tmp_path):
    benchmark={'total':320,'completed':319,'receipted_denominator':320,'correct':318,
               'freeze_digest':'sha256:fixture-freeze','suite_digest':'sha256:fixture-suite',
               'repetitions':{'problem_denominator':320,'planned_trials_per_measured_arm':360},
               'results':[{'candidate':{'planned':2,'trials':[
                   {'completed':True,'receipt':{'latency':1.5}},
                   {'completed':False,'receipt':None}]}}],
               'strata':{'semantic':{'correct_all_candidate_trials':19}},'uncompleted':[{'id':'fixture'}]}
    path=tmp_path/'explicit-v4.json';path.write_text(json.dumps(benchmark))
    # A named historical file must not override the explicitly selected run.
    (tmp_path/'heldout.json').write_text(json.dumps({'total':999,'correct':999,'results':[]}))
    output=characterize(tmp_path,benchmark_path=path)
    general=output['dimensions']['generalization']['evidence']
    assert general['problem_denominator']==320 and general['correct_all_candidate_trials']==318
    assert general['receipted_problem_count']==320 and general['fully_completed_problem_count']==319
    assert general['planned_native_trials']==360 and general['receipted_native_trials']==1
    assert output['dimensions']['responsiveness']['evidence']['observations']==1
    assert output['dimensions']['persistence']['state']=='NEEDS_EVIDENCE'
    assert output['dimensions']['persistence']['evidence']['seconds'] is None
    assert output['sources']['benchmark']['path']==str(path)
    assert output['sources']['benchmark']['sha256']=='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
    assert output['sources']['recovery']['state']=='MISSING'
    assert output['profile_state']=='PARTIAL_OR_HISTORICAL_EVIDENCE'
    assert output['authority_created'] is False and output['whole_machine_complete'] is False
    assert len(output['dimensions'])==10
    assert all('measurement' in d and 'native_workload' in d and 'limits' in d for d in output['dimensions'].values())


def test_legacy_rows_do_not_turn_uncompleted_problems_into_success_or_invent_latency(tmp_path):
    (tmp_path/'heldout.json').write_text(json.dumps({'total':320,'completed':1,'correct':1,
        'receipted_denominator':1,'results':[{'receipt':{'latency':.2},'correct':True}],'strata':{}}))
    output=characterize(tmp_path)
    responsiveness=output['dimensions']['responsiveness']['evidence']
    assert responsiveness['planned_native_trials']==320 and responsiveness['receipted_native_trials']==1
    assert responsiveness['seconds_p95']==.2
    assert output['dimensions']['generalization']['evidence']['problem_denominator']==320
    assert output['dimensions']['prediction_horizon']['state']=='NOT_APPLICABLE'
    assert output['dimensions']['adaptability']['state']=='NOT_APPLICABLE'
    assert output['dimensions']['memory_depth']['evidence']['measured_maximum_memory_horizon'] is None


def test_characterization_cli_never_overwrites_retained_evidence(tmp_path):
    target=tmp_path/'characterization-v2.json';target.write_text('preserved historical report')
    script=Path(__file__).resolve().parents[2]/'scripts/characterize_cognition_seed.py'
    result=subprocess.run([sys.executable,str(script),str(tmp_path)],capture_output=True,text=True)
    assert result.returncode!=0 and 'refusing to overwrite' in result.stderr
    assert target.read_text()=='preserved historical report'


def test_contaminated_complete_run_cannot_be_presented_as_qualified_complete_profile(tmp_path):
    (tmp_path/'heldout.json').write_text(json.dumps({'total':1,'completed':1,'correct':1,'receipted_denominator':1,
        'planned_trials':{'candidate':1},'evaluation_state':'CONTAMINATED_EVALUATION','source_unchanged_at_completion':False,
        'results':[{'candidate':{'planned':1,'trials':[{'completed':True,'receipt':{'latency':.1},'correct':True}]}}]}))
    output=characterize(tmp_path)
    assert output['profile_state']=='CONTAMINATED_EVIDENCE'
    assert output['benchmark_binding']['source_unchanged_at_completion'] is False
