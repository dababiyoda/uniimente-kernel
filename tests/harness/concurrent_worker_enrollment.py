"""Two OS processes claim through collaboration/claims.json and the enrollment gate.

The gate implementation stays on #206 (`31d0c57`). This harness extracts that
published tree into a temp directory and runs it. It does not copy those
sources into this branch.

Default mode uses a local SHA-conditional contents file and a `gh` stand-in,
so the race window is real and the shared registry branch is not modified.
`--live` uses the real `gh` transport against
`dababiyoda/uniimente-kernel` branch `coordination/worker-claims-20261030`.
Docker is not required; each worker has its own workspace, git checkout and
SQLite database. `--live` is not part of the unit test.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timedelta, timezone
import io

PIN_DEFAULT = '31d0c57af90d714da7d9be2c6d6317a41fdc9ca3'
LIVE_REPO = 'dababiyoda/uniimente-kernel'
LIVE_BRANCH = 'coordination/worker-claims-20261030'
LIVE_ORIGIN = 'https://github.com/dababiyoda/uniimente-kernel.git'
HARNESS_DIR = Path(__file__).resolve().parent
FAKE_GH = HARNESS_DIR / 'fake_contents_gh.py'
EMPTY = b'{"audit":[],"claims":{},"version":1}'


def stamp(seconds):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).strftime('%Y-%m-%dT%H:%M:%SZ')


def run(cmd, **kwargs):
    return subprocess.run(cmd, check=True, text=True, **kwargs)


def git_bytes(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def ensure_pin(repo, pin):
    found = subprocess.run(['git', '-C', str(repo), 'cat-file', '-e', pin + '^{commit}'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if found.returncode == 0:
        return
    run(['git', '-C', str(repo), 'fetch', '--depth', '1', 'origin',
         'codex/workspace-entry-20261025'], stdout=subprocess.DEVNULL)


def extract_gate(repo, pin, destination):
    payload = git_bytes(repo, 'archive', pin, 'scripts/collaboration_gate.py',
                        'scripts/remote_collaboration_registry.py')
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:') as archive:
        archive.extractall(destination, filter='data')


def write_snapshots(directory):
    directory.mkdir(parents=True, exist_ok=True)
    reads = []
    for kind in ('protocol', 'discussion', 'board'):
        path = directory / (kind + '.md')
        path.write_text(kind + ' snapshot\n', encoding='utf-8')
        reads.append({'kind': kind, 'path': str(path),
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                      'reference': 'https://github.com/dababiyoda/uniimente-kernel/issues/96',
                      'retrieved_at': stamp(-2)})
    return reads


def init_checkout(workspace, origin):
    repo = workspace / 'repo'
    repo.mkdir(parents=True)
    run(['git', 'init', '-q'], cwd=repo, stdout=subprocess.DEVNULL)
    run(['git', 'config', 'user.email', 'harness@example.invalid'], cwd=repo)
    run(['git', 'config', 'user.name', 'Enrollment Harness'], cwd=repo)
    (repo / 'README').write_text('enrollment harness checkout\n', encoding='utf-8')
    run(['git', 'add', 'README'], cwd=repo, stdout=subprocess.DEVNULL)
    run(['git', 'commit', '-qm', 'initial'], cwd=repo, stdout=subprocess.DEVNULL)
    run(['git', 'remote', 'add', 'origin', origin], cwd=repo)
    head = git_bytes(repo, 'rev-parse', 'HEAD').decode().strip()
    return repo, head


def manifest(session, checkout, head, reads, paths, work_item):
    return {'version': 1, 'session_id': session, 'repository': str(checkout), 'head_sha': head,
            'source_reads': reads, 'work_item': work_item, 'paths': paths, 'interfaces': [],
            'expires_at': stamp(900)}


def install_fake_gh(directory):
    bindir = directory / 'bin'
    bindir.mkdir()
    wrapper = bindir / 'gh'
    wrapper.write_text(f'#!/bin/sh\nexec {sys.executable} {FAKE_GH} "$@"\n', encoding='utf-8')
    wrapper.chmod(0o755)
    return bindir


def fresh_registry(directory):
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'claims.json').write_bytes(EMPTY)
    for name in ('barrier-arrive', 'barrier-go', 'forced-conflicts', 'writes', 'lock'):
        path = directory / name
        if path.exists():
            path.unlink()


def read_registry(directory):
    return json.loads((directory / 'claims.json').read_text(encoding='utf-8'))


def active_sessions(state):
    return sorted(sid for sid, entry in state['claims'].items() if entry['state'] != 'released')


class Workers:
    def __init__(self, source, gh_dir, registry_dir, remote_registry, remote_branch, live=False,
                 rewrite_bypass=False):
        self.source = source
        self.gh_dir = gh_dir
        self.registry_dir = registry_dir
        self.remote_registry = remote_registry
        self.remote_branch = remote_branch
        self.live = live
        self.rewrite_bypass = rewrite_bypass

    def environment(self, extra=None):
        env = os.environ.copy()
        env.pop('HARNESS_BARRIER_N', None)
        env.pop('HARNESS_IGNORE_SHA', None)
        env.pop('HARNESS_FORCE_CONFLICTS', None)
        if not self.live:
            env['PATH'] = str(self.gh_dir) + os.pathsep + env.get('PATH', '')
            env['HARNESS_REGISTRY_DIR'] = str(self.registry_dir)
            env['HARNESS_DEFAULT_BRANCH'] = 'main'
        if self.rewrite_bypass or not self.live:
            # Local races, and an explicitly marked live retry, must see the
            # origin URL stored in the checkout. A global insteadOf rewrite
            # hides that URL behind credentials. Unmodified live runs do not
            # set this.
            env['GIT_CONFIG_GLOBAL'] = os.devnull
            env['GIT_CONFIG_NOSYSTEM'] = '1'
        if extra:
            env.update({key: value for key, value in extra.items() if value is not None})
        return env

    def popen(self, workspace, args, extra=None, stdin=None):
        command = [sys.executable, str(self.source / 'scripts/collaboration_gate.py'),
                   '--workspace', str(workspace), '--remote-registry', self.remote_registry,
                   '--remote-branch', self.remote_branch, *args]
        return subprocess.Popen(command, env=self.environment(extra), stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def together(self, calls, extra=None):
        """calls: list of (workspace, args, stdin)."""
        processes = [self.popen(workspace, args, extra, stdin) for workspace, args, stdin in calls]
        results = []
        for process, (_, _, stdin) in zip(processes, calls):
            stdout, stderr = process.communicate(stdin, timeout=60)
            results.append({'code': process.returncode, 'stdout': stdout.strip(), 'stderr': stderr.strip()})
        return results

    def one(self, workspace, args, extra=None, stdin=None):
        return self.together([(workspace, args, stdin)], extra)[0]


def snippet(result):
    text = (result.get('stderr') or result.get('stdout') or '')
    text = re.sub(r'x-access-token:[^@\s]+', 'x-access-token:[redacted]', text)
    text = re.sub(r'https://[^/\s]+@github\.com', 'https://[redacted]@github.com', text)
    return text[-400:]


def scenario_overlap(workers, workspaces, reads, work_item):
    fresh_registry(workers.registry_dir)
    calls = []
    for session, path in (('worker-alpha', ['alpha']), ('worker-beta', ['alpha/nested.py'])):
        checkout, head = workspaces[session]
        payload = manifest(session, checkout, head, reads, path, work_item)
        path_file = checkout.parent / 'overlap.json'
        path_file.write_text(json.dumps(payload), encoding='utf-8')
        calls.append((checkout.parent, ['enroll', '--manifest', str(path_file)], None))
    results = workers.together(calls, {'HARNESS_BARRIER_N': '2'})
    state = read_registry(workers.registry_dir)
    admitted = [item for item in results if item['code'] == 0]
    refused = [item for item in results if item['code'] != 0]
    for session in ('worker-alpha', 'worker-beta'):
        workers.one(workspaces[session][0].parent, ['finish', '--session', session])
    return {'admitted': len(admitted), 'refused': len(refused),
            'active_while_contended': len(active_sessions(state)),
            'refused_mentions_conflict': bool(refused) and 'conflict' in refused[0]['stderr'],
            'diagnostics': [snippet(item) for item in results if item['code'] not in (0, 2)]}


def scenario_disjoint(workers, workspaces, reads, work_item):
    fresh_registry(workers.registry_dir)
    calls = []
    owned = {}
    for session, path in (('worker-alpha', ['alpha/a.py']), ('worker-beta', ['beta/b.py'])):
        checkout, head = workspaces[session]
        payload = manifest(session, checkout, head, reads, path, work_item)
        path_file = checkout.parent / 'disjoint.json'
        path_file.write_text(json.dumps(payload), encoding='utf-8')
        owned[session] = path_file
        calls.append((checkout.parent, ['enroll', '--manifest', str(path_file)], None))
    results = workers.together(calls, {'HARNESS_BARRIER_N': '2'})
    state = read_registry(workers.registry_dir)
    return {'results': results, 'manifests': owned, 'state': state,
            'admitted': sum(item['code'] == 0 for item in results),
            'active_sessions': len(active_sessions(state)),
            'reserve_audit': sum(event['action'] == 'reserve' for event in state['audit']),
            'diagnostics': [snippet(item) for item in results if item['code'] != 0]}


def scenario_hooks(workers, workspaces, disjoint):
    alpha = workspaces['worker-alpha'][0]
    beta_workspace = workspaces['worker-beta'][0].parent
    outside_workspace = workspaces['worker-gamma'][0].parent
    events = {
        'in_scope': (alpha.parent, {'session_id': 'worker-alpha', 'tool_name': 'Write',
                                    'cwd': str(alpha), 'tool_input': {'file_path': 'alpha/a.py'}}),
        'outside': (alpha.parent, {'session_id': 'worker-alpha', 'tool_name': 'Write',
                                   'cwd': str(alpha), 'tool_input': {'file_path': 'beta/b.py'}}),
        'unenrolled': (outside_workspace, {'session_id': 'worker-gamma', 'tool_name': 'Write',
                                           'cwd': str(workspaces['worker-gamma'][0]),
                                           'tool_input': {'file_path': 'gamma/c.py'}}),
    }
    report = {}
    for name, (workspace, event) in events.items():
        result = workers.one(workspace, ['hook'], stdin=json.dumps(event))
        report[name] = result['code']
        if result['code'] not in (0, 2):
            report.setdefault('diagnostics', []).append(snippet(result))
    report['unenrolled_database_absent'] = not (outside_workspace / '.uniimente' / 'collaboration.sqlite').exists()
    report['beta_workspace_separate'] = beta_workspace != alpha.parent
    for session in ('worker-alpha', 'worker-beta'):
        workers.one(workspaces[session][0].parent, ['finish', '--session', session])
    finished = read_registry(workers.registry_dir)
    report['active_after_finish'] = len(active_sessions(finished))
    report['disjoint_manifests_used'] = sorted(str(path.name) for path in disjoint['manifests'].values())
    return report


def scenario_idempotent(workers, workspaces, reads, work_item):
    fresh_registry(workers.registry_dir)
    # Two processes and two local databases, one published claim.
    # Distinct db paths keep SQLite from serializing the remote race.
    checkout, head = workspaces['worker-alpha']
    payload = manifest('worker-alpha', checkout, head, reads, ['alpha/a.py'], work_item)
    path_file = checkout.parent / 'idempotent.json'
    path_file.write_text(json.dumps(payload), encoding='utf-8')
    db_a = checkout.parent / 'a.sqlite'
    db_b = checkout.parent / 'b.sqlite'
    calls = [
        (checkout.parent, ['--db', str(db_a), 'enroll', '--manifest', str(path_file)], None),
        (checkout.parent, ['--db', str(db_b), 'enroll', '--manifest', str(path_file)], None),
    ]
    # together() places gate args after the remote branch. --db must precede the action,
    # and the gate accepts --db anywhere before the subcommand because argparse does.
    results = workers.together(calls, {'HARNESS_BARRIER_N': '2'})
    state = read_registry(workers.registry_dir)
    workers.one(checkout.parent, ['finish', '--session', 'worker-alpha'])
    return {'admitted': sum(item['code'] == 0 for item in results),
            'reserve_audit': sum(event['action'] == 'reserve' for event in state['audit']),
            'active_sessions': len(active_sessions(state)),
            'diagnostics': [snippet(item) for item in results if item['code'] != 0]}


def scenario_handoff(workers, workspaces, reads, work_item):
    fresh_registry(workers.registry_dir)
    sender_checkout, sender_head = workspaces['worker-alpha']
    receiver_checkout, receiver_head = workspaces['worker-beta']
    sender = manifest('worker-alpha', sender_checkout, sender_head, reads, ['alpha/a.py'], work_item)
    sender_path = sender_checkout.parent / 'sender.json'
    sender_path.write_text(json.dumps(sender), encoding='utf-8')
    enrolled = workers.one(sender_checkout.parent, ['enroll', '--manifest', str(sender_path)])
    offer = 'https://github.com/dababiyoda/uniimente-kernel/pull/206#harness-offer'
    handed = workers.one(sender_checkout.parent, ['handoff', '--session', 'worker-alpha',
                                                  '--receiver', 'worker-beta', '--reference', offer])
    finished = workers.one(sender_checkout.parent, ['finish', '--session', 'worker-alpha'])
    receiver = manifest('worker-beta', receiver_checkout, receiver_head, reads, ['alpha/a.py'], work_item)
    receiver_path = receiver_checkout.parent / 'receiver.json'
    receiver_path.write_text(json.dumps(receiver), encoding='utf-8')
    accept_ref = 'https://github.com/dababiyoda/uniimente-kernel/pull/206#harness-accept'
    accepted = workers.one(receiver_checkout.parent, ['accept', '--session', 'worker-beta',
                                                      '--from-session', 'worker-alpha',
                                                      '--reference', accept_ref,
                                                      '--manifest', str(receiver_path)])
    sender_check = workers.one(sender_checkout.parent, ['check', '--session', 'worker-alpha'])
    receiver_check = workers.one(receiver_checkout.parent, ['check', '--session', 'worker-beta'])
    # Remote accept runs in the receiver's database, so the sender's local row
    # can still say handoff. finish preserves that pending row on purpose.
    retry = manifest('worker-alpha', sender_checkout, sender_head, reads, ['beta/b.py'], work_item)
    retry_path = sender_checkout.parent / 'sender-retry.json'
    retry_path.write_text(json.dumps(retry), encoding='utf-8')
    reenroll = workers.one(sender_checkout.parent, ['enroll', '--manifest', str(retry_path)])
    released = workers.one(sender_checkout.parent, ['release', '--session', 'worker-alpha'])
    reenroll_after = workers.one(sender_checkout.parent, ['enroll', '--manifest', str(retry_path)])
    workers.one(sender_checkout.parent, ['finish', '--session', 'worker-alpha'])
    workers.one(receiver_checkout.parent, ['finish', '--session', 'worker-beta'])
    state = read_registry(workers.registry_dir)
    return {'enroll': enrolled['code'], 'handoff': handed['code'], 'sender_finish': finished['code'],
            'accept': accepted['code'], 'sender_check': sender_check['code'],
            'receiver_check': receiver_check['code'],
            'sender_head_differs': sender_head != receiver_head,
            'reenroll_while_local_handoff': reenroll['code'],
            'reenroll_mentions_handoff': 'handoff pending' in reenroll['stderr'],
            'release_after_remote_accept': released['code'],
            'reenroll_after_release': reenroll_after['code'],
            'active_after_finish': len(active_sessions(state)),
            'diagnostics': [snippet(item) for item in
                            (enrolled, handed, finished, accepted, receiver_check, released, reenroll_after)
                            if item['code'] != 0]}


def scenario_retry_budget(workers, workspaces, reads, work_item):
    fresh_registry(workers.registry_dir)
    checkout, head = workspaces['worker-alpha']
    payload = manifest('worker-alpha', checkout, head, reads, ['alpha/a.py'], work_item)
    path_file = checkout.parent / 'budget.json'
    path_file.write_text(json.dumps(payload), encoding='utf-8')
    result = workers.one(checkout.parent, ['enroll', '--manifest', str(path_file)],
                         {'HARNESS_FORCE_CONFLICTS': '4'})
    state = read_registry(workers.registry_dir)
    return {'code': result['code'], 'mentions_contention': 'contention' in result['stderr'],
            'active_sessions': len(active_sessions(state)),
            'writes': int((workers.registry_dir / 'writes').read_text())
            if (workers.registry_dir / 'writes').exists() else 0,
            'diagnostics': [] if result['code'] == 2 else [snippet(result)]}


def scenario_detector(workers, root, reads, work_item):
    """Disable the SHA check. Both clients can observe success while one claim is lost."""
    fresh_registry(workers.registry_dir)
    calls = []
    fresh = {}
    for session, path in (('worker-alpha', ['alpha/a.py']), ('worker-beta', ['beta/b.py'])):
        checkout, head = init_checkout(root / ('detector-' + session), 'https://github.com/Owner/Organ.git')
        fresh[session] = checkout.parent
        payload = manifest(session, checkout, head, reads, path, work_item)
        path_file = checkout.parent / 'detector.json'
        path_file.write_text(json.dumps(payload), encoding='utf-8')
        calls.append((checkout.parent, ['enroll', '--manifest', str(path_file)], None))
    results = workers.together(calls, {'HARNESS_BARRIER_N': '2', 'HARNESS_IGNORE_SHA': '1'})
    state = read_registry(workers.registry_dir)
    admitted = sum(item['code'] == 0 for item in results)
    stored = len(active_sessions(state))
    for session, workspace in fresh.items():
        workers.one(workspace, ['finish', '--session', session])
    return {'admitted': admitted, 'stored': stored, 'lost_update': admitted == 2 and stored == 1,
            'diagnostics': [snippet(item) for item in results if item['code'] != 0]}


def product_races(report):
    races = []
    overlap = report['overlap']
    if overlap['admitted'] != 1 or overlap['refused'] != 1 or overlap['active_while_contended'] != 1:
        races.append('overlapping claims were not reduced to one admission')
    if not overlap['refused_mentions_conflict']:
        races.append('overlapping refusal did not report a scope conflict')
    disjoint = report['disjoint']
    if disjoint['admitted'] != 2 or disjoint['active_sessions'] != 2 or disjoint['reserve_audit'] != 2:
        races.append('disjoint claims lost an admission or an audit record under the same blob SHA')
    hooks = report['hooks']
    if hooks['in_scope'] != 0:
        races.append('enrolled in-scope hook was refused')
    if hooks['outside'] == 0 or hooks['unenrolled'] == 0:
        races.append('out-of-scope or unenrolled hook was admitted')
    if not hooks['unenrolled_database_absent']:
        races.append('unenrolled hook created a local claim database')
    if hooks['active_after_finish'] != 0:
        races.append('finish left an active shared claim')
    idempotent = report['idempotent']
    if idempotent['admitted'] != 2 or idempotent['reserve_audit'] != 1 or idempotent['active_sessions'] != 1:
        races.append('concurrent retry of one claim wrote two reservations or dropped the claim')
    handoff = report['handoff']
    if any(handoff[key] != 0 for key in ('enroll', 'handoff', 'sender_finish', 'accept', 'receiver_check')):
        races.append('cross-process handoff or receiver acceptance failed')
    if handoff['sender_check'] == 0 or handoff['active_after_finish'] != 0:
        races.append('sender remained active after receiver acceptance, or finish left a claim')
    if handoff['release_after_remote_accept'] != 0 or handoff['reenroll_after_release'] != 0:
        races.append('sender could not clear a local handoff row after the receiver accepted remotely')
    budget = report['retry_budget']
    if budget['code'] != 2 or budget['active_sessions'] != 0 or budget['writes'] != 0:
        races.append('retry budget wrote a claim or failed open after repeated conflicts')
    return races


def local_report(repo, pin):
    ensure_pin(repo, pin)
    root = Path(tempfile.mkdtemp(prefix='enrollment-harness-'))
    try:
        source = root / 'source'
        extract_gate(repo, pin, source)
        registry = root / 'registry'
        fresh_registry(registry)
        gh_dir = install_fake_gh(root)
        snapshots = write_snapshots(root / 'snapshots')
        work_item = 'https://github.com/dababiyoda/uniimente-kernel/issues/96'
        workspaces = {}
        for name in ('worker-alpha', 'worker-beta', 'worker-gamma'):
            workspace = root / name
            checkout, head = init_checkout(workspace, 'https://github.com/Owner/Organ.git')
            if name == 'worker-beta':
                (checkout / 'README').write_text('receiver checkout\n', encoding='utf-8')
                run(['git', 'add', 'README'], cwd=checkout, stdout=subprocess.DEVNULL)
                run(['git', 'commit', '-qm', 'receiver'], cwd=checkout, stdout=subprocess.DEVNULL)
                head = git_bytes(checkout, 'rev-parse', 'HEAD').decode().strip()
            workspaces[name] = (checkout, head)
        workers = Workers(source, gh_dir, registry, 'owner/kernel', 'coordination/harness')
        report = {
            'pin': pin,
            'transport': 'local-sha-conditional-contents',
            'processes': 2,
            'containers': 'not_run',
            'container_reason': 'docker and podman are not installed; workers are separate processes and workspaces',
            'overlap': scenario_overlap(workers, workspaces, snapshots, work_item),
            'disjoint': {},
        }
        disjoint = scenario_disjoint(workers, workspaces, snapshots, work_item)
        report['disjoint'] = {key: disjoint[key] for key in ('admitted', 'active_sessions', 'reserve_audit', 'diagnostics')}
        report['hooks'] = scenario_hooks(workers, workspaces, disjoint)
        report['idempotent'] = scenario_idempotent(workers, workspaces, snapshots, work_item)
        report['handoff'] = scenario_handoff(workers, workspaces, snapshots, work_item)
        report['retry_budget'] = scenario_retry_budget(workers, workspaces, snapshots, work_item)
        report['detector'] = scenario_detector(workers, root, snapshots, work_item)
        report['product_races'] = product_races(report)
        report['limits'] = []
        if not report['retry_budget']['mentions_contention']:
            report['limits'].append('four injected conflicts did not surface the contention message')
        else:
            report['limits'].append('A client stops after four conditional conflicts and writes nothing. '
                                     'Two workers fit in that budget; a larger simultaneous wave can refuse '
                                     'a disjoint claim without losing a committed one.')
        return report
    finally:
        shutil.rmtree(root, ignore_errors=True)


def gh_json(method, endpoint, body=None):
    command = ['gh', 'api', '--hostname', 'github.com', '--method', method,
               '-H', 'Accept: application/vnd.github+json', endpoint]
    payload = None if body is None else json.dumps(body)
    if body is not None:
        command += ['--input', '-']
    result = subprocess.run(command, input=payload, capture_output=True, text=True, timeout=45)
    if result.returncode != 0:
        status = result.stdout.splitlines()[0] if result.stdout.startswith('HTTP/') else ''
        raise RuntimeError('gh ' + method + ' failed ' + status)
    return json.loads(result.stdout)


def live_state():
    response = gh_json('GET', f'repos/{LIVE_REPO}/contents/collaboration/claims.json?ref='
                       + LIVE_BRANCH.replace('/', '%2F'))
    raw = base64.b64decode(''.join(response['content'].split()))
    return response['sha'], json.loads(raw), raw


def live_report(repo, pin):
    """One real gh run. Releases only the harness session labels it creates."""
    ensure_pin(repo, pin)
    before_sha, before, _ = live_state()
    foreign = [sid for sid, entry in before['claims'].items()
               if entry['state'] != 'released' and not str(sid).startswith('harness-')]
    if foreign:
        return {'transport': 'github-contents', 'aborted': True,
                'reason': 'foreign active claims present; live harness did not write',
                'foreign_active': len(foreign), 'product_races': []}
    root = Path(tempfile.mkdtemp(prefix='enrollment-live-'))
    source = root / 'source'
    extract_gate(repo, pin, source)
    snapshots = write_snapshots(root / 'snapshots')
    work_item = 'https://github.com/dababiyoda/uniimente-kernel/pull/206'
    labels = {
        'harness-alpha-20261030': 'docs/evidence/concurrent-harness-20261030/alpha/file.py',
        'harness-beta-20261030': 'docs/evidence/concurrent-harness-20261030/beta/file.py',
        'harness-gamma-20261030': 'docs/evidence/concurrent-harness-20261030/alpha/file.py',
    }
    workspaces = {}
    for name in labels:
        checkout, head = init_checkout(root / name, LIVE_ORIGIN)
        workspaces[name] = (checkout, head)
    workers = Workers(source, None, root / 'unused', LIVE_REPO, LIVE_BRANCH, live=True)
    started = []
    report = {'transport': 'github-contents', 'pin': pin, 'processes': 2, 'containers': 'not_run',
              'before_sha': before_sha, 'before_active': len([e for e in before['claims'].values()
                                                              if e['state'] != 'released']),
              'product_races': [], 'aborted': False}
    try:
        for sid, entry in before['claims'].items():
            if str(sid).startswith('harness-') and entry['state'] != 'released':
                workers.one(workspaces['harness-alpha-20261030'][0].parent, ['finish', '--session', sid])
        calls = []
        for session in ('harness-alpha-20261030', 'harness-beta-20261030'):
            checkout, head = workspaces[session]
            payload = manifest(session, checkout, head, snapshots, [labels[session]], work_item)
            path_file = checkout.parent / 'live.json'
            path_file.write_text(json.dumps(payload), encoding='utf-8')
            calls.append((checkout.parent, ['enroll', '--manifest', str(path_file)], None))
            started.append(session)
        disjoint = workers.together(calls)
        mid_sha, state, _ = live_state()
        report['disjoint'] = {'admitted': sum(item['code'] == 0 for item in disjoint),
                              'active_sessions': len(active_sessions(state)),
                              'diagnostics': [snippet(item) for item in disjoint if item['code'] != 0]}
        origin_refused = all(item['code'] != 0 and 'unambiguous github.com origin' in item['stderr']
                             for item in disjoint)
        if origin_refused:
            report['unmodified_sha_unchanged'] = mid_sha == before_sha
            report['unmodified_client'] = report['disjoint']
            report['live_blockers'] = [
                'The published gate reads `git remote get-url origin` and accepts only a bare '
                'https://github.com/owner/repo or git@github.com:owner/repo URL. In this environment '
                'a global insteadOf rewrite supplies a credential userinfo URL, so both unmodified '
                'workers were refused before a Contents write.'
            ]
            if not report['unmodified_sha_unchanged']:
                report['product_races'].append('origin refusal still changed the shared registry')
                return report
            # Second pass: same checkouts and the real gh transport, with the
            # rewrite hidden, so two processes can exercise the shared file.
            # This is not what an unmodified client in this environment does.
            workers = Workers(source, None, root / 'unused', LIVE_REPO, LIVE_BRANCH, live=True,
                              rewrite_bypass=True)
            report['rewrite_bypass'] = True
            disjoint = workers.together(calls)
            _, state, _ = live_state()
            report['disjoint'] = {'admitted': sum(item['code'] == 0 for item in disjoint),
                                  'active_sessions': len(active_sessions(state)),
                                  'diagnostics': [snippet(item) for item in disjoint if item['code'] != 0]}
        if report['disjoint']['admitted'] != 2 or report['disjoint']['active_sessions'] < 2:
            report['product_races'].append('live disjoint enrollment did not admit both workers')
        gamma_checkout, gamma_head = workspaces['harness-gamma-20261030']
        gamma = manifest('harness-gamma-20261030', gamma_checkout, gamma_head, snapshots,
                         [labels['harness-gamma-20261030']], work_item)
        gamma_path = gamma_checkout.parent / 'gamma.json'
        gamma_path.write_text(json.dumps(gamma), encoding='utf-8')
        started.append('harness-gamma-20261030')
        refused = workers.one(gamma_checkout.parent, ['enroll', '--manifest', str(gamma_path)])
        report['overlap'] = {'code': refused['code'], 'mentions_conflict': 'conflict' in refused['stderr'],
                             'diagnostics': [] if refused['code'] == 2 else [snippet(refused)]}
        if refused['code'] == 0 or not report['overlap']['mentions_conflict']:
            report['product_races'].append('live overlapping claim was not refused')
        alpha = workspaces['harness-alpha-20261030'][0]
        hooked = workers.one(alpha.parent, ['hook'], stdin=json.dumps({
            'session_id': 'harness-alpha-20261030', 'tool_name': 'Write', 'cwd': str(alpha),
            'tool_input': {'file_path': labels['harness-alpha-20261030']}}))
        blocked = workers.one(alpha.parent, ['hook'], stdin=json.dumps({
            'session_id': 'harness-alpha-20261030', 'tool_name': 'Write', 'cwd': str(alpha),
            'tool_input': {'file_path': 'docs/evidence/concurrent-harness-20261030/outside.py'}}))
        report['hooks'] = {'in_scope': hooked['code'], 'outside': blocked['code']}
        if hooked['code'] != 0 or blocked['code'] == 0:
            report['product_races'].append('live hook admission did not match the claim')
        # Release beta so it can accept alpha's scope. Alpha stays reserved through the handoff.
        workers.one(workspaces['harness-beta-20261030'][0].parent, ['finish', '--session', 'harness-beta-20261030'])
        offer = 'https://github.com/dababiyoda/uniimente-kernel/pull/206#harness-offer'
        handed = workers.one(alpha.parent, ['handoff', '--session', 'harness-alpha-20261030',
                                            '--receiver', 'harness-beta-20261030', '--reference', offer])
        workers.one(alpha.parent, ['finish', '--session', 'harness-alpha-20261030'])
        receiver = manifest('harness-beta-20261030', workspaces['harness-beta-20261030'][0],
                            workspaces['harness-beta-20261030'][1], snapshots,
                            [labels['harness-alpha-20261030']], work_item)
        receiver_path = workspaces['harness-beta-20261030'][0].parent / 'receiver.json'
        receiver_path.write_text(json.dumps(receiver), encoding='utf-8')
        accepted = workers.one(workspaces['harness-beta-20261030'][0].parent, [
            'accept', '--session', 'harness-beta-20261030', '--from-session', 'harness-alpha-20261030',
            '--reference', 'https://github.com/dababiyoda/uniimente-kernel/pull/206#harness-accept',
            '--manifest', str(receiver_path)])
        report['handoff'] = {'handoff': handed['code'], 'accept': accepted['code'],
                             'diagnostics': [snippet(item) for item in (handed, accepted) if item['code'] != 0]}
        if handed['code'] != 0 or accepted['code'] != 0:
            report['product_races'].append('live receiver handoff failed')
    finally:
        for session in started:
            try:
                # release clears a pending handoff; finish would leave it reserved.
                workers.one(workspaces[session][0].parent, ['release', '--session', session])
            except (subprocess.SubprocessError, OSError) as exc:
                report.setdefault('cleanup_errors', []).append(type(exc).__name__)
        try:
            after_sha, after, _ = live_state()
            report['after_sha'] = after_sha
            report['after_active'] = active_sessions(after)
            report['harness_still_active'] = [sid for sid in report['after_active'] if sid.startswith('harness-')]
            if report['harness_still_active']:
                report['product_races'].append('live cleanup left a harness claim active')
        except (RuntimeError, subprocess.SubprocessError, OSError, ValueError) as exc:
            report['product_races'].append('live cleanup could not re-read the registry')
            report['cleanup_errors'] = report.get('cleanup_errors', []) + [type(exc).__name__]
        shutil.rmtree(root, ignore_errors=True)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pin', default=PIN_DEFAULT)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args(argv)
    report = live_report(args.repo, args.pin) if args.live else local_report(args.repo, args.pin)
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write('\n')
    failed = bool(report.get('product_races'))
    if not args.live and not report.get('detector', {}).get('lost_update'):
        failed = True
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
