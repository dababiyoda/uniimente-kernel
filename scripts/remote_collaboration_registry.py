"""Shared coordination through a GitHub Contents SHA-conditional file update.

This is cooperative exclusion, not a security boundary against repository writers.
Credentials stay with the existing gh CLI authentication. No implicit bootstrap.
"""
from __future__ import annotations

import base64
import copy
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
from urllib.parse import quote

LIMIT = 512 * 1024
PATH = 'collaboration/claims.json'


class RemoteError(ValueError):
    pass


class ConflictError(RemoteError):
    pass


def require(value, message):
    if not value:
        raise RemoteError(message)


def identity(value):
    require(isinstance(value, str) and value.strip() == value and 0 < len(value) <= 200
            and not any(ord(c) < 32 for c in value), 'invalid session identity')
    return value


def canonical_repository(value):
    require(isinstance(value, str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*', value),
            'canonical repository owner/name required')
    return value.lower()


def utc(value):
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z', value),
            'UTC claim timestamp required')
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise RemoteError('invalid claim timestamp') from exc


def url(value):
    require(isinstance(value, str) and value.startswith('https://') and len(value) <= 2000
            and not any(ord(c) < 32 for c in value), 'https coordination reference required')
    return value


def scope(value):
    require(isinstance(value, str) and value == value.strip() and value, 'scope path required')
    if value == '.':
        return value
    parts = value.rstrip('/').split('/')
    require(all(p and p not in {'.', '..'} for p in parts)
            and not any(c in value for c in ('\\', ':', '<', '>'))
            and not any(ord(c) < 32 for c in value), 'unsafe remote scope')
    return '/'.join(parts)


def overlaps(a, b):
    return a == '.' or b == '.' or a == b or a.startswith(b + '/') or b.startswith(a + '/')


def record(manifest, repository):
    require(isinstance(manifest, dict), 'manifest required')
    paths = manifest.get('paths')
    require(isinstance(paths, list) and paths, 'nonempty paths required')
    paths = [scope(p) for p in paths]
    require(len(paths) == len(set(paths)), 'duplicate scope paths')
    interfaces = manifest.get('interfaces')
    require(isinstance(interfaces, list) and all(isinstance(i, str) and i.strip() == i and i for i in interfaces)
            and len(interfaces) == len(set(interfaces)), 'distinct interface names required')
    head = manifest.get('head_sha')
    require(isinstance(head, str) and re.fullmatch('[a-f0-9]{40}', head), 'full head SHA required')
    expiry = manifest.get('expires_at')
    utc(expiry)
    reads = manifest.get('source_reads')
    require(isinstance(reads, list) and len(reads) == 3, 'three source digests required')
    sources = []
    for read in reads:
        require(isinstance(read, dict) and read.get('kind') in {'protocol', 'discussion', 'board'}, 'invalid source kind')
        digest = read.get('sha256')
        require(isinstance(digest, str) and re.fullmatch('[a-f0-9]{64}', digest), 'full source digest required')
        sources.append({'kind': read['kind'], 'sha256': digest, 'reference': url(read.get('reference'))})
    require(len({s['kind'] for s in sources}) == 3, 'distinct source kinds required')
    return {'session_id': identity(manifest.get('session_id')), 'canonical_repo': canonical_repository(repository),
            'head_sha': head, 'paths': sorted(paths), 'interfaces': sorted(interfaces),
            'expires_at': expiry, 'work_item': url(manifest.get('work_item')),
            'source_reads': sorted(sources, key=lambda s: s['kind'])}


def json_load(raw, limit=LIMIT):
    require(isinstance(raw, str) and len(raw.encode('utf-8')) <= limit, 'registry/API response exceeds size limit')
    def unique(pairs):
        out = {}
        for key, value in pairs:
            require(key not in out, 'duplicate registry key')
            out[key] = value
        return out
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(RemoteError('non-finite registry value')))
    except (ValueError, TypeError) as exc:
        raise RemoteError('invalid registry JSON') from exc


def gh_transport(method, endpoint, body=None):
    args = ['gh', 'api', '--hostname', 'github.com', '--include', '--method', method,
            '-H', 'Accept: application/vnd.github+json', endpoint]
    if body is not None:
        args += ['--input', '-']
    try:
        result = subprocess.run(args, input=None if body is None else json.dumps(body),
                                capture_output=True, text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise RemoteError('GitHub request outcome unknown; reconcile before retry') from exc
    # Never print gh stderr: it may contain credential-bearing diagnostics.
    output = result.stdout.replace('\r\n', '\n')
    match = re.match(r'HTTP/\S+ (\d{3})[^\n]*\n', output)
    require(match is not None, 'GitHub request failed or outcome unknown; reconcile before retry')
    status = int(match.group(1))
    if status == 409:
        raise ConflictError('GitHub conditional update conflict')
    require(200 <= status < 300 and result.returncode == 0, 'GitHub request refused; no fallback to local-only claims')
    require('\n\n' in output, 'GitHub response missing body')
    # The API envelope contains Base64 and metadata; cap decoded state separately.
    return json_load(output.split('\n\n', 1)[1], limit=2 * LIMIT)


class RemoteRegistry:
    def __init__(self, repo, branch, transport=None):
        self.repo = canonical_repository(repo)
        require(isinstance(branch, str) and branch.startswith('coordination/')
                and re.fullmatch(r'coordination/[A-Za-z0-9][A-Za-z0-9/_-]*', branch)
                and not branch.endswith('/') and '//' not in branch, 'explicit coordination/ branch required')
        self.branch = branch
        self.transport = transport or gh_transport
        self.endpoint = f'repos/{self.repo}/contents/{PATH}'

    def read(self):
        metadata = self.transport('GET', f'repos/{self.repo}')
        require(isinstance(metadata, dict) and isinstance(metadata.get('default_branch'), str)
                and metadata['default_branch'] and metadata['default_branch'] != self.branch,
                'coordination registry must not be the default branch')
        response = self.transport('GET', self.endpoint + '?ref=' + quote(self.branch, safe=''))
        require(isinstance(response, dict) and response.get('type') == 'file'
                and response.get('encoding') == 'base64', 'existing registry file required')
        sha = response.get('sha')
        require(isinstance(sha, str) and re.fullmatch('[a-f0-9]{40}', sha), 'registry blob SHA required')
        try:
            raw = base64.b64decode(''.join(response['content'].split()), validate=True).decode('utf-8')
        except (KeyError, ValueError, UnicodeError) as exc:
            raise RemoteError('invalid registry encoding') from exc
        state = json_load(raw)
        require(isinstance(state, dict) and set(state) == {'version', 'claims', 'audit'}
                and type(state['version']) is int and state['version'] == 1
                and isinstance(state['claims'], dict) and isinstance(state['audit'], list), 'invalid registry schema')
        for sid, entry in state['claims'].items():
            require(isinstance(entry, dict) and set(entry) == {'claim', 'state', 'receiver', 'reference'}, 'invalid registry claim')
            claim = entry['claim']
            require(isinstance(claim, dict) and set(claim) == {'session_id', 'canonical_repo', 'head_sha', 'paths',
                    'interfaces', 'expires_at', 'work_item', 'source_reads'}, 'invalid remote claim fields')
            require(record(claim, claim['canonical_repo']) == claim and sid == claim['session_id'], 'invalid remote claim identity')
            require(entry['state'] in {'active', 'released', 'handoff'}, 'invalid claim state')
            if entry['state'] == 'handoff':
                require(identity(entry['receiver']) != sid, 'invalid handoff receiver')
                url(entry['reference'])
            else:
                require(entry['receiver'] is None, 'unexpected receiver')
                require(entry['reference'] is None or isinstance(entry['reference'], str), 'invalid claim reference')
        for event in state['audit']:
            require(isinstance(event, dict) and set(event) == {'at', 'action', 'session', 'detail'}, 'invalid audit entry')
            utc(event['at']); identity(event['session'])
            require(event['action'] in {'reserve', 'release', 'finish', 'handoff', 'accept'} and isinstance(event['detail'], dict), 'invalid audit action')
        return state, sha

    def mutate(self, session, action, change, detail=None):
        identity(session)
        for _ in range(4):
            state, sha = self.read()
            result, changed = change(state)
            if not changed:
                return result
            state['audit'].append({'at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                   'action': action, 'session': session, 'detail': detail or {}})
            encoded = json.dumps(state, sort_keys=True, separators=(',', ':')).encode('utf-8')
            require(len(encoded) <= LIMIT, 'registry full; preserve history and perform reviewed migration')
            try:
                response = self.transport('PUT', self.endpoint, {'branch': self.branch, 'sha': sha,
                    'message': f'Collaboration {action}', 'content': base64.b64encode(encoded).decode('ascii')})
            except ConflictError:
                continue  # New read, then all ownership checks again; never blind replay.
            expected_blob = hashlib.sha1(b'blob ' + str(len(encoded)).encode('ascii') + b'\0' + encoded).hexdigest()
            require(isinstance(response, dict) and isinstance(response.get('content'), dict)
                    and response['content'].get('sha') == expected_blob,
                    'GitHub update outcome unknown; reconcile before retry')
            return result
        raise RemoteError('registry contention; retry after refreshing ownership')

    @staticmethod
    def fresh(claim):
        require(utc(claim['expires_at']) > datetime.now(timezone.utc), 'remote claim expired; explicit owner recovery required')

    @staticmethod
    def conflicts(state, candidate, ignore=()):
        for sid, entry in state['claims'].items():
            if sid in ignore or entry['state'] == 'released':
                continue
            other = entry['claim']
            clash = other['canonical_repo'] == candidate['canonical_repo'] and any(
                overlaps(a, b) for a in other['paths'] for b in candidate['paths'])
            require(not clash and not set(other['interfaces']) & set(candidate['interfaces']),
                    'remote scope conflict with ' + sid)

    def reserve(self, manifest, canonical_repo):
        claim = record(manifest, canonical_repo); self.fresh(claim)
        sid = claim['session_id']
        def change(state):
            existing = state['claims'].get(sid)
            if existing and existing['state'] != 'released':
                require(existing['state'] == 'active' and existing['claim'] == claim,
                        'session already owns a different claim or pending handoff; release explicitly')
                return copy.deepcopy(existing), False
            self.conflicts(state, claim)
            entry = {'claim': claim, 'state': 'active', 'receiver': None, 'reference': None}
            state['claims'][sid] = entry
            return copy.deepcopy(entry), True
        return self.mutate(sid, 'reserve', change)

    def check(self, manifest, canonical_repo):
        claim = record(manifest, canonical_repo); self.fresh(claim)
        state, _ = self.read()
        entry = state['claims'].get(claim['session_id'])
        require(entry is not None and entry['state'] == 'active' and entry['claim'] == claim,
                'remote session missing, stale, changed or transferring')
        self.conflicts(state, claim, (claim['session_id'],))
        return copy.deepcopy(entry)

    def release(self, session):
        return self._release(session, False)

    def finish(self, session):
        return self._release(session, True)

    def _release(self, session, finish):
        def change(state):
            entry = state['claims'].get(session)
            if entry is None or entry['state'] == 'released' or (finish and entry['state'] == 'handoff'):
                return None, False
            entry['state'], entry['receiver'], entry['reference'] = 'released', None, None
            return None, True
        return self.mutate(session, 'finish' if finish else 'release', change)

    def handoff(self, session, receiver, reference):
        require(identity(receiver) != identity(session), 'self handoff refused'); url(reference)
        def change(state):
            entry = state['claims'].get(session)
            require(entry is not None and entry['state'] == 'active', 'no active sender claim')
            self.fresh(entry['claim'])
            entry.update(state='handoff', receiver=receiver, reference=reference)
            return copy.deepcopy(entry), True
        return self.mutate(session, 'handoff', change, {'receiver': receiver, 'reference': reference})

    def accept(self, manifest, canonical_repo, sender, reference):
        claim = record(manifest, canonical_repo); self.fresh(claim); url(reference)
        session = claim['session_id']; require(session != identity(sender), 'self acceptance refused')
        def change(state):
            prior = state['claims'].get(sender)
            require(prior is not None and prior['state'] == 'handoff' and prior['receiver'] == session,
                    'no handoff offered to this receiver')
            old = prior['claim']
            require(all(old[k] == claim[k] for k in ('canonical_repo', 'paths', 'interfaces', 'work_item')),
                    'receiver scope/work item differs from handoff')
            existing = state['claims'].get(session)
            require(existing is None or existing['state'] == 'released', 'receiver already owns a claim')
            self.conflicts(state, claim, (sender, session))
            prior.update(state='released', receiver=None, reference=None)
            entry = {'claim': claim, 'state': 'active', 'receiver': None, 'reference': reference}
            state['claims'][session] = entry
            return copy.deepcopy(entry), True
        return self.mutate(session, 'accept', change, {'sender': sender, 'reference': reference})
