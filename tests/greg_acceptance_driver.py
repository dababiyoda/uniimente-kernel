"""Actual-source receipt capture with explicitly synthetic authority and review."""
import argparse
import json
from pathlib import Path
import subprocess
import time
from egregore.local_console import (initialize,submit_mission,mission_report,record_review,learning_trial,stop,constitution)
from egregore.local_mission import ROOT
from egregore.repository_audit import git_read
from provenance.ledger import EvidenceLedger


def await_brief(root,name):
    end=time.monotonic()+20
    while time.monotonic()<end:
        report=mission_report(root,name)
        if report['brief']: return report
        if report['host_observation'] and report['host_observation']['status']!='COMPLETE': raise RuntimeError(report)
        time.sleep(.1)
    raise RuntimeError('bounded observation expired: '+(root/name/'host.log').read_text())


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--state',required=True); parser.add_argument('--output',required=True)
    args=parser.parse_args(); root=Path(args.state).resolve()
    repos=[dict(role=r,path=str(p),commit=git_read(str(p),'rev-parse','refs/remotes/origin/main').decode().strip())
        for r,p in [('kernel',ROOT),('dale',ROOT.parent/'daleobanks'),('wmi',ROOT.parent/'wmi')]]
    initialize(root,repos,'4999acff1a69502c05af455fbccfca380cad18ee')
    first=submit_mission(root,delay=.5); before=await_brief(root,first['mission'])
    review_ref=record_review(root,first['mission'],'correct',
        'SYNTHETIC operator correction: prioritize demonstrated authority gaps; no permission changes.',before['as_of_head'])
    comparison=learning_trial(root,first['mission'],json.loads((ROOT/'tests/fixtures/greg_held_out.json').read_text()))
    later=submit_mission(root,delay=.5); after=await_brief(root,later['mission'])
    stop_result=stop(root,'acceptance complete; retain evidence')
    ledger=EvidenceLedger(constitution(),str(root/'control.jsonl'),read_only=True); head=ledger.head; ledger.close()
    result={'classification':'ACTUAL_LOCAL_SOURCE_WORK_WITH_SYNTHETIC_AUTHORITY_AND_REVIEW',
        'implementation_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'inspected_sources':repos,'freshness':'cached local refs; no mission-time network fetch',
        'first':first,'first_report':before,'review_ref':review_ref,'comparison':comparison,
        'later':later,'later_report':after,'stop':stop_result,'control_head':head,
        'limits':['Alfonso not authenticated','No Mac or reboot test','No community contact',
            'Synthetic author-labeled held-out cases; independent review absent','Same-user filesystem is not a hostile-worker sandbox']}
    Path(args.output).write_text(json.dumps(result,indent=2,sort_keys=True))
    print(json.dumps({'first':first['mission'],'later':later['mission'],'comparison':comparison,'control_head':head},indent=2))


if __name__=='__main__': main()
