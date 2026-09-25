"""Actual local sources and subprocesses; explicitly synthetic authority/review."""
import json
import multiprocessing
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import sys
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import pytest
from egregore.local_console import (constitution, initialize, submit_mission, mission_report,
    stop, run_host, record_review, learning_trial)
from egregore.local_mission import ROOT, run_once, submit, supervise
from egregore.repository_audit import git_read
from egregore.development_session import provision
from policy.consequence_gate import ConsequenceGate
from provenance.ledger import EvidenceLedger

PIN = '4999acff1a69502c05af455fbccfca380cad18ee'


@pytest.fixture
def session(tmp_path):
    paths=[('kernel',ROOT),('dale',ROOT.parent/'daleobanks'),('wmi',ROOT.parent/'wmi')]
    if not all(p.is_dir() for _,p in paths):
        pytest.skip('three local repository dependencies required; not a passed acceptance test')
    repos=[dict(role=r,path=str(p),commit=git_read(str(p),'rev-parse','refs/remotes/origin/main').decode().strip()) for r,p in paths]
    root=tmp_path/'session'; initialize(root,repos,PIN)
    yield root
    stop(root,'test cleanup')


def wait_result(root,name):
    end=time.monotonic()+15
    while time.monotonic()<end:
        report=mission_report(root,name)
        if report['brief'] or (report['host_observation'] and report['host_observation']['status']!='COMPLETE'):
            return report
        time.sleep(.1)
    pytest.fail(json.dumps(report)+(root/name/'host.log').read_text())


def test_review_comparison_changes_later_task_and_regression_reverts(session):
    first=submit_mission(session,delay=.2); report=wait_result(session,first['mission'])
    assert report['brief'] and report['actions']['dispatch_claims']==1
    assert len(report['result']['coverage'])==10
    record_review(session,first['mission'],'correct','SYNTHETIC: prioritize evidenced authority gaps.',report['as_of_head'])
    cases=json.loads((ROOT/'tests/fixtures/greg_held_out.json').read_text())
    trial=learning_trial(session,first['mission'],cases)
    assert trial['decision']=='retain' and trial['candidate_accuracy']==1 and trial['baseline_accuracy']==.5
    second=submit_mission(session,delay=.2); later=wait_result(session,second['mission'])
    assert later['brief'][-1]['brief']['ordering']=='security-first'
    assert later['brief'][-1]['brief']['blocker']['kind']=='authority'
    assert later['brief'][-1]['brief']['what_changed']==[]
    bad=[dict(id='contrary-label',findings=[dict(id='dep',kind='dependency'),dict(id='auth',kind='authority')],expected='dep')]
    assert learning_trial(session,first['mission'],bad)['decision']=='regress'
    third=submit_mission(session,delay=.2)
    assert wait_result(session,third['mission'])['brief'][-1]['brief']['ordering']=='unchanged baseline'


def test_intentional_stop_survives_process_restart_and_blocks_dispatch(session):
    task=submit_mission(session,delay=3); stop(session,'intentional stop')
    report=wait_result(session,task['mission'])
    assert report['status']=='STOPPED' and report['actions']['dispatch_claims']==0
    assert run_host(session,task['mission'],3)['status']=='STOPPED'
    with pytest.raises(ValueError,match='intentional stop'): submit_mission(session)
    child=subprocess.run([sys.executable,'-m','egregore.local_console','--state',str(session),'status'],cwd=ROOT,capture_output=True,text=True)
    assert child.returncode==0 and json.loads(child.stdout)['stopped']


def test_budget_wait_cannot_be_overridden_by_restart(session):
    task=submit_mission(session,delay=0,budget=0); report=wait_result(session,task['mission'])
    assert report['status']=='WAIT_BUDGET' and report['actions']['dispatch_claims']==0
    with pytest.raises(ValueError,match='budget differs'): run_host(session,task['mission'],3)
    assert run_host(session,task['mission'],0)['status']=='WAIT_BUDGET'


def test_killed_host_reconstructs_claim_and_refuses_redispatch(session):
    task=submit_mission(session,delay=8); path=session/task['mission']/'ledger.jsonl'
    end=time.monotonic()+5; started=False
    while time.monotonic()<end:
        ledger=EvidenceLedger(constitution(),str(path),read_only=True)
        started=any(r.payload.get('type')=='greg.host_started' for r in ledger.by_type('event')); ledger.close()
        if started: break
        time.sleep(.05)
    assert started
    os.kill(task['host_pid'],signal.SIGKILL); time.sleep(.15)
    assert run_host(session,task['mission'],3)['status']=='HOST_ALREADY_CLAIMED'
    report=mission_report(session,task['mission'])
    assert report['status']=='RUNNING_OR_INTERRUPTED' and report['actions']['dispatch_claims']==0
    assert 'reconcile' in report['blocker']


def test_http_client_closure_and_ui_server_restart(session):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
    args=[sys.executable,'-m','egregore.local_console','--state',str(session),'serve','--port',str(port)]
    url=f'http://127.0.0.1:{port}/'
    def launch():
        p=subprocess.Popen(args,cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        for _ in range(80):
            try:
                with urlopen(url) as response: page=response.read().decode()
                return p,page
            except OSError: time.sleep(.05)
        p.terminate(); p.wait(); pytest.fail('UI failed to start')
    server,page=launch()
    try:
        token=re.search('name="csrf" value="([^"]+)"',page).group(1)
        with urlopen(Request(url,data=urlencode({'csrf':token,'action':'submit'}).encode())) as response:
            assert response.status==200
        names=[p.name for p in session.iterdir() if p.is_dir()]; assert len(names)==1
        server.terminate(); server.wait(timeout=3)
        assert wait_result(session,names[0])['brief']
        server,page=launch()
        assert names[0] in page and 'source_scope' in page
        token=re.search('name="csrf" value="([^"]+)"',page).group(1)
        report=mission_report(session,names[0])
        form=dict(csrf=token,action='accept',mission=names[0],head=report['as_of_head'],correction='SYNTHETIC browser-equivalent review')
        with urlopen(Request(url,data=urlencode(form).encode())) as response: assert response.status==200
        assert mission_report(session,names[0])['result_reviews'][-1]['decision']=='accept'
    finally:
        server.terminate(); server.wait(timeout=3)


def test_stop_terminates_inflight_worker_and_retains_uncertain_dispatch(session,monkeypatch):
    config=json.loads((session/'config.json').read_text()); folder=session/'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
    folder.mkdir(); path=folder/'ledger.jsonl'
    job=dict(mission_id='greg-proof:inflight',repositories=config['repositories'],expected_pin=PIN,expected_version='0.1.2',
        due=time.time(),deadline=time.time()+20,profile='integration-v1',control_ledger=str(session/'control.jsonl'))
    auth=provision(job,folder/'authority.json'); ledger=EvidenceLedger(constitution(),str(path))
    submit(path,job,ConsequenceGate(ledger=ledger,**{k:auth[k] for k in ('compiled','passports','grants','signer')}),actor=auth['actor']); ledger.close()
    marker=folder/'entered'
    def slow(*args): marker.write_text('fault-injected in-flight read'); time.sleep(15); return []
    monkeypatch.setattr('egregore.local_mission.capture',slow)
    def host(): (folder/'result.json').write_text(json.dumps(supervise(path,job,auth)))
    process=multiprocessing.get_context('fork').Process(target=host); process.start()
    try:
        end=time.monotonic()+8
        while not marker.exists() and time.monotonic()<end: time.sleep(.05)
        assert marker.exists(); stop(session,'stop in-flight'); process.join(5)
        assert not process.is_alive()
        result=json.loads((folder/'result.json').read_text())
        assert result['status']=='STOPPED' and result['worker_exits'][0]!=0
        with pytest.raises(Exception,match='intentional stop'): run_once(path,job,**auth)
        ledger=EvidenceLedger(constitution(),str(path),read_only=True)
        assert len(ledger.by_type('grant_dispatch'))==1 and not ledger.by_type('receipt'); ledger.close()
    finally:
        if process.is_alive(): process.kill(); process.join()
