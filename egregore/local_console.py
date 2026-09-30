"""Local GREG development console: one supported audit, no general assistant.

The canonical EvidenceLedger owns mission and safety-control histories. The
unconditional stop stream issues no grants. Real founder enrollment is absent.
"""
import argparse
import html
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid
from urllib.parse import parse_qs
from compiler.ucl_compiler import compile_constitution
from egregore.brief_learning import brief, compare
from egregore.development_session import LABEL, provision, restore, write_json
from egregore.local_mission import ROOT, submit, supervise
from egregore.morning_review import review
from egregore.repository_audit import git_read, validate_repositories
from egregore.runtime import StandingCognitionRuntime
from events.spine import EventSpine
from policy.consequence_gate import ConsequenceGate
from provenance.ledger import EvidenceLedger


def constitution():
    return compile_constitution(str(ROOT)).constitution_hash


def open_control(root, read_only=False):
    return EvidenceLedger(constitution(), str(Path(root) / 'control.jsonl'), read_only=read_only)


def stopped(root):
    ledger = open_control(root, True)
    try:
        return bool(ledger.by_type(StandingCognitionRuntime.SUSPEND_RECORD))
    finally:
        ledger.close()


def initialize(root, repositories, expected_pin):
    root = Path(root).resolve()
    if root.exists():
        raise ValueError('use a new development directory; retained sessions cannot be reset')
    validate_repositories(repositories)
    if any(root.is_relative_to(Path(r['path'])) for r in repositories):
        raise ValueError('state must be outside inspected repositories')
    root.mkdir(mode=0o700)
    write_json(root/'config.json', {'classification': LABEL, 'repositories': repositories,
        'expected_pin': expected_pin, 'captured_at': time.time(),
        'freshness': 'local origin/main refs; initialization does not fetch'})
    ledger = open_control(root)
    try:
        ledger.append('greg.console_created', {'classification': LABEL, 'supported': ['integration-v1']})
    finally:
        ledger.close()
    return {'state': str(root), 'classification': LABEL}


def stop(root, reason):
    ledger = open_control(root)
    try:
        runtime = StandingCognitionRuntime(ledger=ledger, proposers={}, evaluators={})
        ref = runtime.suspend(actor='local-unverified-development-operator', reason=reason)
        return {'status': 'STOPPED', 'ref': ref, 'authentication': LABEL,
                'in_flight': 'terminate owned active worker on next bounded host check; inspect retained evidence'}
    finally:
        ledger.close()


def submit_mission(root, delay=1, budget=3):
    if type(delay) not in (int, float) or not 0 <= delay <= 20 or type(budget) is not int or not 0 <= budget <= 3:
        raise ValueError('delay 0..20 seconds and attempt budget 0..3 required')
    root = Path(root).resolve()
    control = open_control(root)
    try:
        if control.by_type(StandingCognitionRuntime.SUSPEND_RECORD):
            raise ValueError('intentional stop is terminal; no dispatch')
        if len(control.by_type('greg.console_submission')) >= 20:
            raise ValueError('session budget exhausted (20 missions); retain and review')
        config = json.loads((root/'config.json').read_text())
        if config['classification'] != LABEL:
            raise ValueError('no authenticated founder provider configured')
        name = uuid.uuid4().hex
        folder = root/name
        folder.mkdir(mode=0o700)
        due = time.time() + delay
        job = dict(mission_id='greg-proof:'+name, repositories=config['repositories'],
            expected_pin=config['expected_pin'], expected_version='0.1.2', due=due, deadline=due+40,
            profile='integration-v1', control_ledger=str(root/'control.jsonl'))
        write_json(folder/'job.json', job)
        auth = provision(job, folder/'synthetic-authority.json')
        ledger = EvidenceLedger(constitution(), str(folder/'ledger.jsonl'))
        try:
            gate = ConsequenceGate(ledger=ledger, **{k: auth[k] for k in ('compiled','passports','grants','signer')})
            submit(folder/'ledger.jsonl', job, gate, actor=auth['actor'])
            ledger.append('greg.obligations', {'goal': 'source-backed integration morning brief',
                'required': ['exact commits','what changed','blocker','next action','independent source appraisal'],
                'attempt_budget': budget, 'authentication': LABEL})
        finally:
            ledger.close()
        control.append('greg.console_submission', {'mission': name, 'budget': budget})
        with open(folder/'host.log', 'ab') as log:
            process = subprocess.Popen([sys.executable,'-m','egregore.local_console','--state',str(root),
                'worker','--mission',name,'--budget',str(budget)], cwd=ROOT,
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        return {'mission': name, 'host_pid': process.pid, 'classification': LABEL}
    finally:
        control.close()


def mission_folder(root, name):
    if len(name) != 32 or any(c not in '0123456789abcdef' for c in name):
        raise ValueError('invalid mission id')
    folder = Path(root).resolve()/name
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError('unknown mission')
    return folder


def mission_report(root, name):
    folder = mission_folder(root, name)
    ledger = EvidenceLedger(constitution(), str(folder/'ledger.jsonl'), read_only=True)
    try:
        job = json.loads((folder/'job.json').read_text())
        report = review(folder/'ledger.jsonl', constitution(), job['mission_id'], ledger.head)
        report['brief'] = []
        for retained in ledger.by_type('greg.morning_brief'):
            data = retained.payload
            anchor = ledger.find(data['source_review_head'])
            if anchor is None or anchor.seq >= retained.seq:
                raise ValueError('brief lacks preceding source review')
            source = review(folder/'ledger.jsonl', constitution(), job['mission_id'], anchor.hash)
            if data['brief'] != brief(source['result'], data['previous_report'], data['security_first']):
                raise ValueError('brief differs from source-derived result; reconcile')
            report['brief'].append(data)
        report['result_reviews'] = [r.payload for r in ledger.by_type('greg.result_review')]
        if report['status'].startswith('RETAINED_AUDIT') and not report['brief']:
            report.update(status='VERIFIED_AUDIT_AWAITING_BRIEF', blocker='Brief obligation remains open.')
        if stopped(root):
            report.update(status='STOPPED', next_reconsideration=None,
                blocker='Intentional stop; review retained evidence. No automatic resume.')
        elif report['host_observation'] and report['host_observation']['status'] == 'WAIT_BUDGET':
            report.update(status='WAIT_BUDGET', blocker='Attempt budget exhausted; no dispatch.')
        elif EventSpine(ledger).replay('greg.host_started') and not EventSpine(ledger).replay('greg.host_stopped'):
            report.update(status='RUNNING_OR_INTERRUPTED', next_reconsideration=job['deadline'],
                blocker='If host exited: reconcile retained claim and receipts; do not redispatch.')
        return report
    finally:
        ledger.close()


def run_host(root, name, budget, crash=False):
    folder = mission_folder(root, name)
    job = json.loads((folder/'job.json').read_text())
    auth = restore(folder/'synthetic-authority.json')
    ledger = EvidenceLedger(constitution(), str(folder/'ledger.jsonl'), read_only=True)
    try:
        if budget != ledger.by_type('greg.obligations')[0].payload['attempt_budget']:
            raise ValueError('budget differs from retained admission')
    finally:
        ledger.close()
    result = supervise(folder/'ledger.jsonl', job, auth, max_attempts=budget, crash_first=crash)
    if result['status'] == 'COMPLETE':
        current = mission_report(root, name)
        report = current['result']
        control = open_control(root, True)
        try:
            trials = control.by_type('greg.learning_comparison')
            learned = bool(trials and trials[-1].payload['comparison']['decision'] == 'retain')
            prior = control.by_type('greg.brief_result')
            previous = prior[-1].payload['report'] if prior else None
        finally:
            control.close()
        ledger = EvidenceLedger(constitution(), str(folder/'ledger.jsonl'))
        try:
            if not ledger.by_type('greg.morning_brief'):
                ledger.append('greg.morning_brief', {'brief': brief(report, previous, learned),
                    'source_review_head': current['as_of_head'], 'previous_report': previous,
                    'security_first': learned, 'verified': True})
        finally:
            ledger.close()
        control = open_control(root)
        try:
            if not any(r.payload['mission'] == name for r in control.by_type('greg.brief_result')):
                control.append('greg.brief_result', {'mission': name, 'report': report})
        finally:
            control.close()
    return result


def record_review(root, name, decision, correction, head):
    if decision not in ('accept','reject','correct') or not isinstance(correction,str) or len(correction)>2000:
        raise ValueError('bounded accept/reject/correct review required')
    report = mission_report(root,name)
    if report['as_of_head'] != head or not report['brief']:
        raise ValueError('current verified result and exact head required')
    ledger = EvidenceLedger(constitution(), str(mission_folder(root,name)/'ledger.jsonl'))
    try:
        if ledger.head != head:
            raise ValueError('history changed; refresh')
        return ledger.append('greg.result_review', {'decision': decision, 'correction': correction,
            'review_head': head, 'evidence_refs': report['evidence_refs'], 'result': report['brief'][-1],
            'classification': 'UNVERIFIED_LOCAL_OPERATOR_REVIEW', 'authentication': LABEL,
            'proposed_improvement': 'Test security-first brief ordering on separate held-out cases; no policy change.'}).hash
    finally:
        ledger.close()


def learning_trial(root,name,cases):
    report = mission_report(root,name)
    if not report['result_reviews']:
        raise ValueError('review actual result first')
    result = compare(cases)
    ledger = open_control(root)
    try:
        ref = ledger.append('greg.learning_comparison', {'mission': name, 'comparison': result,
            'review': report['result_reviews'][-1], 'cases': cases,
            'classification': 'SYNTHETIC_HELD_OUT_PRESENTATION_EVALUATION'}).hash
    finally:
        ledger.close()
    return {'ref': ref, **result}


def overview(root):
    names = [p.name for p in Path(root).iterdir() if p.is_dir() and len(p.name)==32]
    return {'classification': LABEL, 'supported_task': 'integration-v1: bounded static repository audit',
        'stopped': stopped(root), 'missions': {n: mission_report(root,n) for n in sorted(names)}}


def serve(root,port):
    token = secrets.token_urlsafe(24)  # CSRF defense only; never founder identity.
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                self.send_error(403); return
            data = overview(root)
            hidden = '<input type="hidden" name="csrf" value="'+token+'">'
            content = '<form method="post">'+hidden+'<button name="action" value="submit">Submit approved snapshot audit</button><button name="action" value="stop">Stop this session</button></form>'
            for name,r in data['missions'].items():
                b = r['brief'][-1]['brief'] if r['brief'] else {}
                content += '<article><h2>Repository integration audit</h2><b>'+html.escape(r['status'])+'</b><p>'+name+'</p>'
                content += '<p>Blocker: '+html.escape(str(b.get('blocker') or r['blocker']))+'</p>'
                content += '<p>Next action: '+html.escape(str(b.get('next_action') or r['next_step']))+'</p>'
                content += '<p>Next reconsideration: '+html.escape(str(r['next_reconsideration']))+'</p>'
                content += '<form method="post">'+hidden+'<input type="hidden" name="mission" value="'+name+'"><input type="hidden" name="head" value="'+r['as_of_head']+'">'
                content += '<input name="correction" maxlength="2000" placeholder="Correction or reason">'
                content += ''.join('<button name="action" value="'+v+'">'+v+'</button>' for v in ('accept','reject','correct'))+'</form></article>'
            body = ('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>GREG local mission</title>'
                '<style>body{font:16px system-ui;max-width:980px;margin:32px auto;padding:0 20px;color:#16303a;background:#f4f7f6}article,form,details{background:white;padding:16px;margin:16px 0;border:1px solid #cad8d7;border-radius:8px}button,input{font:inherit;padding:8px;margin:4px}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>'
                '<h1>GREG local development mission</h1><p>Synthetic development authority. Alfonso authentication is not configured. No external communications.</p>'
                '<p>Supported: bounded static audit of approved local snapshots. Close the interface; the finite worker continues. Refresh for progress.</p>'
                + content + '<details><summary>Inspect retained history and source evidence</summary><pre>'+html.escape(json.dumps(data,indent=2))+'</pre></details>').encode()
            self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(body)))
            self.end_headers(); self.wfile.write(body)
        def do_POST(self):
            try:
                if self.headers.get('Host') != f'127.0.0.1:{self.server.server_port}':
                    raise ValueError('loopback Host required')
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 8192: raise ValueError('bounded request required')
                form = {k:v[0] for k,v in parse_qs(self.rfile.read(length).decode(),keep_blank_values=True).items()}
                if not secrets.compare_digest(form.get('csrf',''),token): raise ValueError('invalid CSRF')
                if form['action']=='submit': submit_mission(root)
                elif form['action']=='stop': stop(root,'local console safety stop')
                else: record_review(root,form['mission'],form['action'],form.get('correction',''),form['head'])
                self.send_response(303); self.send_header('Location','/'); self.end_headers()
            except Exception as exc:
                self.send_error(409,type(exc).__name__+': '+str(exc))
    HTTPServer(('127.0.0.1',port),Handler).serve_forever()


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--state',required=True)
    sub=parser.add_subparsers(dest='command',required=True)
    init=sub.add_parser('init-synthetic-development')
    for role in ('kernel','dale','wmi'): init.add_argument('--'+role,required=True)
    init.add_argument('--expected-pin',required=True)
    task=sub.add_parser('submit'); task.add_argument('--delay',type=float,default=1); task.add_argument('--budget',type=int,default=3)
    sub.add_parser('status'); sub.add_parser('stop')
    worker=sub.add_parser('worker'); worker.add_argument('--mission',required=True); worker.add_argument('--budget',type=int,default=3); worker.add_argument('--crash-after-receipt',action='store_true')
    web=sub.add_parser('serve'); web.add_argument('--port',type=int,default=8765)
    reviewer=sub.add_parser('review'); reviewer.add_argument('--mission',required=True); reviewer.add_argument('--decision',choices=['accept','reject','correct'],required=True); reviewer.add_argument('--correction',default=''); reviewer.add_argument('--head',required=True)
    learn=sub.add_parser('compare'); learn.add_argument('--mission',required=True); learn.add_argument('--cases',required=True)
    args=parser.parse_args(); root=Path(args.state).resolve()
    if args.command=='init-synthetic-development':
        repos=[dict(role=r,path=str(Path(getattr(args,r)).resolve()),commit=git_read(str(Path(getattr(args,r)).resolve()),'rev-parse','refs/remotes/origin/main').decode().strip()) for r in ('kernel','dale','wmi')]
        result=initialize(root,repos,args.expected_pin)
    elif args.command=='submit': result=submit_mission(root,args.delay,args.budget)
    elif args.command=='status': result=overview(root)
    elif args.command=='stop': result=stop(root,'explicit local safety stop')
    elif args.command=='worker': result=run_host(root,args.mission,args.budget,args.crash_after_receipt)
    elif args.command=='serve': return serve(root,args.port)
    elif args.command=='review': result=record_review(root,args.mission,args.decision,args.correction,args.head)
    else: result=learning_trial(root,args.mission,json.loads(Path(args.cases).read_text()))
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=='__main__': main()
