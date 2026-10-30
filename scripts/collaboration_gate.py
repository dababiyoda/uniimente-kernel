"""Local, opt-in collaboration gate. Not a sandbox or authenticated remote lock.

Trusted clients must invoke the PreToolUse hook with failure blocking enabled.
Read tools remain available for enrollment. Bash requires an exclusive whole-repo
claim because arbitrary shell writes cannot be bounded by inspecting command text.
Snapshots declare which source bytes were consulted, not comprehension or truth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone


class GateError(ValueError):
    pass


def require(ok, message):
    if not ok:
        raise GateError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def identity(value):
    require(text(value) and value == value.strip() and '<' not in value
            and value.casefold() not in {'unknown', 'unassigned', 'pending', 'none'},
            'actual session identifier required')
    return value


def now():
    return datetime.now(timezone.utc)


def utc(value):
    require(isinstance(value, str) and re.fullmatch(
        r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value) is not None,
        'expires_at requires YYYY-MM-DDTHH:MM:SSZ')
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise GateError('invalid expiry calendar date') from exc


def no_symlinks(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)),
            'symlink path refused: ' + str(path))
    return path


def digest(path):
    path = no_symlinks(path)
    require(path.is_file(), 'source file missing: ' + str(path))
    require(path.stat().st_size <= 4 * 1024 * 1024, 'source snapshot exceeds 4 MiB')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(repo, *args):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                            text=True, timeout=15, check=False)
    require(result.returncode == 0, 'git inspection failed: ' + result.stderr.strip())
    return result.stdout.strip()


def repository(repo):
    repo = no_symlinks(repo).resolve()
    require(repo.is_dir(), 'repository directory missing')
    top = Path(git(repo, 'rev-parse', '--show-toplevel')).resolve()
    require(top == repo, 'repository must name the worktree root')
    common = Path(git(repo, 'rev-parse', '--path-format=absolute', '--git-common-dir')).resolve()
    return repo, str(common), git(repo, 'rev-parse', 'HEAD')


def scope_path(value):
    require(text(value) and value == value.strip(), 'scope path required')
    if value == '.':
        return '.'
    require(not value.startswith('/') and '\\' not in value and ':' not in value
            and '<' not in value and '>' not in value,
            'scope must be repository-relative')
    parts = value.rstrip('/').split('/')
    require(all(part and part not in ('.', '..') for part in parts), 'unsafe scope path')
    return '/'.join(parts)


def overlap(a, b):
    return a == '.' or b == '.' or a == b or a.startswith(b + '/') or b.startswith(a + '/')


def url(value):
    require(text(value) and value.startswith('https://') and '\n' not in value,
            'https work/acknowledgment reference required')
    return value


def load_json(path):
    def unique(pairs):
        out = {}
        for k, v in pairs:
            require(k not in out, 'duplicate JSON key')
            out[k] = v
        return out
    raw = Path(path).read_text(encoding='utf-8')
    require(len(raw) <= 4 * 1024 * 1024, 'JSON input too large')
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: (_ for _ in ()).throw(GateError('non-finite JSON')))


class Gate:
    def __init__(self, workspace, db=None):
        self.workspace = no_symlinks(workspace).resolve()
        require(self.workspace.is_dir(), 'workspace must exist')
        raw_db = Path(db or self.workspace / '.uniimente/collaboration.sqlite')
        require('..' not in raw_db.parts, 'database traversal refused')
        self.db = no_symlinks(raw_db).resolve()
        require(self.db.is_relative_to(self.workspace), 'database must be under shared workspace')

    def connection(self, create=False):
        no_symlinks(self.db)
        if create:
            self.db.parent.mkdir(parents=True, exist_ok=True)
        else:
            require(self.db.is_file(), 'not enrolled: collaboration database missing')
        connection = sqlite3.connect(str(self.db) if create else self.db.as_uri() + '?mode=rw',
                                     uri=not create, timeout=15, isolation_level=None)
        connection.execute('BEGIN IMMEDIATE')
        if create:
            connection.execute('CREATE TABLE IF NOT EXISTS claims (session TEXT PRIMARY KEY, '
                               'manifest TEXT NOT NULL, state TEXT NOT NULL, receiver TEXT, reference TEXT)')
            connection.execute('CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, '
                               'at TEXT NOT NULL, action TEXT NOT NULL, session TEXT NOT NULL, detail TEXT NOT NULL)')
        require(connection.execute('PRAGMA quick_check').fetchone()[0] == 'ok', 'registry integrity failed')
        return connection

    def event(self, db, action, session, detail):
        db.execute('INSERT INTO audit(at,action,session,detail) VALUES(?,?,?,?)',
                   (now().isoformat(), action, session, json.dumps(detail, sort_keys=True)))

    def validate(self, manifest):
        require(isinstance(manifest, dict) and manifest.get('version') == 1
                and type(manifest.get('version')) is int, 'manifest version 1 required')
        identity(manifest.get('session_id'))
        repo, common, head = repository(manifest.get('repository', ''))
        require(repo.is_relative_to(self.workspace), 'repository outside shared workspace')
        require(isinstance(manifest.get('head_sha'), str) and re.fullmatch('[0-9a-f]{40}', manifest['head_sha']),
                'full head SHA required')
        require(head == manifest['head_sha'], 'stale repository head: reenroll after refreshing work')
        require(utc(manifest.get('expires_at')) > now(), 'claim expired: refresh and reenroll; do not steal it')
        url(manifest.get('work_item'))
        reads = manifest.get('source_reads')
        require(isinstance(reads, list) and len(reads) >= 3, 'protocol, discussion and board snapshots required')
        kinds = set()
        for read in reads:
            require(isinstance(read, dict) and read.get('kind') in {'protocol', 'discussion', 'board'},
                    'unknown source kind')
            require(read['kind'] not in kinds, 'duplicate source kind')
            kinds.add(read['kind'])
            url(read.get('reference'))
            require(utc(read.get('retrieved_at')) <= now(), 'source retrieval time is in the future')
            require(isinstance(read.get('path'), str) and Path(read['path']).is_absolute(), 'absolute source path required')
            require(isinstance(read.get('sha256'), str) and re.fullmatch('[0-9a-f]{64}', read['sha256']),
                    'full source digest required')
            require(digest(read['path']) == read['sha256'], 'source drift: ' + read['kind'])
        require(kinds == {'protocol', 'discussion', 'board'}, 'all three source kinds required')
        paths = manifest.get('paths')
        require(isinstance(paths, list) and paths, 'nonempty claimed paths required')
        paths = [scope_path(p) for p in paths]
        require(len(set(paths)) == len(paths), 'duplicate claimed paths')
        for path in paths:
            no_symlinks(repo / path)
        interfaces = manifest.get('interfaces')
        require(isinstance(interfaces, list) and all(text(i) for i in interfaces)
                and len(set(interfaces)) == len(interfaces), 'interfaces must be distinct text entries')
        return {**manifest, 'repository': str(repo), 'repo_identity': common, 'paths': paths}

    def enroll(self, manifest):
        manifest = self.validate(manifest)
        db = self.connection(create=True)
        try:
            sid = manifest['session_id']
            existing = db.execute('SELECT state FROM claims WHERE session=?', (sid,)).fetchone()
            require(not existing or existing[0] != 'handoff', 'handoff pending; receiver must accept or owner release')
            for other, raw, state in db.execute('SELECT session,manifest,state FROM claims'):
                if other == sid or state == 'released':
                    continue
                prior = json.loads(raw)
                # Expiration is deliberately NOT an automatic release.
                same_repo = prior['repo_identity'] == manifest['repo_identity']
                clash = same_repo and any(overlap(a, b) for a in prior['paths'] for b in manifest['paths'])
                clash = clash or bool(set(prior['interfaces']) & set(manifest['interfaces']))
                require(not clash, 'scope conflict with ' + other + '; acknowledge split/release first')
            db.execute('INSERT OR REPLACE INTO claims VALUES(?,?,?,?,?)',
                       (sid, json.dumps(manifest), 'active', None, None))
            self.event(db, 'enroll', sid, manifest)
            db.commit()
            return manifest
        finally:
            db.close()

    def active(self, db, session):
        identity(session)
        row = db.execute('SELECT manifest,state FROM claims WHERE session=?', (session,)).fetchone()
        require(row is not None and row[1] == 'active', 'session has no active enrollment')
        return self.validate(json.loads(row[0]))

    def check(self, session):
        db = self.connection()
        try:
            return self.active(db, session)
        finally:
            db.close()

    def release(self, session):
        identity(session)
        db = self.connection()
        try:
            require(db.execute('SELECT 1 FROM claims WHERE session=? AND state!=?',
                               (session, 'released')).fetchone(), 'claim missing or already released')
            db.execute('UPDATE claims SET state=? WHERE session=?', ('released', session))
            self.event(db, 'release', session, {})
            db.commit()
        finally:
            db.close()

    def handoff(self, session, receiver, reference):
        identity(receiver)
        require(receiver != session, 'self handoff refused')
        url(reference)
        db = self.connection()
        try:
            self.active(db, session)
            db.execute('UPDATE claims SET state=?,receiver=?,reference=? WHERE session=?',
                       ('handoff', receiver, reference, session))
            self.event(db, 'handoff', session, {'receiver': receiver, 'reference': reference})
            db.commit()
        finally:
            db.close()

    def finish(self, session):
        """Release normal completed work without discarding a pending transfer."""
        identity(session)
        if not self.db.exists():
            return
        db = self.connection()
        try:
            row = db.execute('SELECT state FROM claims WHERE session=?', (session,)).fetchone()
            if row is not None and row[0] == 'active':
                db.execute('UPDATE claims SET state=? WHERE session=?', ('released', session))
                self.event(db, 'finish', session, {'previous_state': 'active'})
            db.commit()
        finally:
            db.close()

    def accept(self, session, sender, reference):
        identity(session)
        require(session != sender, 'self acceptance refused')
        url(reference)
        db = self.connection()
        try:
            row = db.execute('SELECT manifest,state,receiver FROM claims WHERE session=?', (sender,)).fetchone()
            require(row is not None and row[1] == 'handoff' and row[2] == session, 'no handoff offered to this receiver')
            manifest = self.validate(json.loads(row[0]))
            require(not db.execute('SELECT 1 FROM claims WHERE session=? AND state!=?',
                                   (session, 'released')).fetchone(), 'receiver already owns a claim')
            manifest['session_id'] = session
            db.execute('UPDATE claims SET state=? WHERE session=?', ('released', sender))
            db.execute('INSERT OR REPLACE INTO claims VALUES(?,?,?,?,?)',
                       (session, json.dumps(manifest), 'active', None, reference))
            self.event(db, 'accept', session, {'sender': sender, 'reference': reference})
            db.commit()
        finally:
            db.close()

    def hook(self, event):
        require(isinstance(event, dict), 'hook event object required')
        tool = event.get('tool_name')
        require(text(tool), 'hook tool_name required')
        if tool not in {'Write', 'Edit', 'MultiEdit', 'NotebookEdit', 'Bash'}:
            return
        manifest = self.check(event.get('session_id'))
        cwd = event.get('cwd')
        require(text(cwd), 'hook cwd required')
        root = Path(git(cwd, 'rev-parse', '--show-toplevel')).resolve()
        _, common, head = repository(root)
        require(common == manifest['repo_identity'] and str(root) == manifest['repository']
                and head == manifest['head_sha'], 'hook repository/worktree differs from enrollment')
        if tool == 'Bash':
            require(manifest['paths'] == ['.'], 'Bash requires exclusive repository-wide claim; use scoped Edit/Write for parallel work')
            return
        data = event.get('tool_input')
        key = 'notebook_path' if tool == 'NotebookEdit' else 'file_path'
        require(isinstance(data, dict) and text(data.get(key)), 'write tool ' + key + ' required')
        path = Path(data[key])
        if not path.is_absolute():
            path = Path(cwd) / path
        path = no_symlinks(path).resolve()
        require(path.is_relative_to(root), 'write outside enrolled repository')
        relative = path.relative_to(root).as_posix()
        require(any(p == '.' or relative == p or relative.startswith(p + '/') for p in manifest['paths']),
                'write outside claimed scope')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--db', type=Path)
    commands = parser.add_subparsers(dest='action', required=True)
    enroll = commands.add_parser('enroll'); enroll.add_argument('--manifest', required=True, type=Path)
    for action in ('check', 'release', 'finish', 'handoff', 'accept'):
        sub = commands.add_parser(action); sub.add_argument('--session', required=True)
        if action == 'handoff': sub.add_argument('--receiver', required=True); sub.add_argument('--reference', required=True)
        if action == 'accept': sub.add_argument('--from-session', required=True); sub.add_argument('--reference', required=True)
    commands.add_parser('hook')
    args = parser.parse_args(argv)
    try:
        gate = Gate(args.workspace, args.db)
        if args.action == 'enroll': gate.enroll(load_json(args.manifest))
        elif args.action == 'check': gate.check(args.session)
        elif args.action == 'release': gate.release(args.session)
        elif args.action == 'finish': gate.finish(args.session)
        elif args.action == 'handoff': gate.handoff(args.session, args.receiver, args.reference)
        elif args.action == 'accept': gate.accept(args.session, args.from_session, args.reference)
        else:
            raw = sys.stdin.read(4 * 1024 * 1024 + 1)
            require(len(raw) <= 4 * 1024 * 1024, 'hook input too large')
            gate.hook(json.loads(raw))
        if args.action != 'hook': print('Collaboration gate: ' + args.action + ' accepted')
        return 0
    except (GateError, OSError, ValueError, TypeError, KeyError, sqlite3.Error, subprocess.SubprocessError) as exc:
        print('Collaboration gate blocked: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
