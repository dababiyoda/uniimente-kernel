"""Stand-in for `gh api` Contents calls. Atomic blob-SHA updates, optional fault injection.

The enrollment gate shells out to `gh`. Tests prepend a directory containing an
executable named `gh` that execs this file. It speaks only the narrow Contents
exchange in scripts/remote_collaboration_registry.py. It does not read
credentials and it does not contact GitHub.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
import fcntl


def blob_sha(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode('ascii') + b'\0' + data).hexdigest()


def respond(status, payload):
    reason = {200: 'OK', 201: 'Created', 409: 'Conflict', 422: 'Unprocessable Entity'}.get(status, 'Error')
    sys.stdout.write(f'HTTP/2.0 {status} {reason}\n\n')
    sys.stdout.write(json.dumps(payload, separators=(',', ':')))
    return 0 if 200 <= status < 300 else 1


def root_dir():
    path = os.environ.get('HARNESS_REGISTRY_DIR')
    if not path:
        sys.stderr.write('fake gh: HARNESS_REGISTRY_DIR is required\n')
        raise SystemExit(2)
    return path


class Lock:
    def __init__(self, directory):
        self.handle = open(os.path.join(directory, 'lock'), 'a+')

    def __enter__(self):
        fcntl.flock(self.handle, fcntl.LOCK_EX)
        return self

    def __exit__(self, *_):
        fcntl.flock(self.handle, fcntl.LOCK_UN)
        self.handle.close()


def counter(directory, name, increment):
    path = os.path.join(directory, name)
    current = int(open(path).read()) if os.path.exists(path) else 0
    if increment:
        current += 1
        with open(path, 'w') as handle:
            handle.write(str(current))
    return current


def wait_for_peers(directory):
    """Hold the first wave of PUTs until HARNESS_BARRIER_N clients have arrived."""
    needed = int(os.environ.get('HARNESS_BARRIER_N') or '0')
    if needed <= 1 or os.path.exists(os.path.join(directory, 'barrier-go')):
        return
    with Lock(directory):
        if os.path.exists(os.path.join(directory, 'barrier-go')):
            return
        arrived = counter(directory, 'barrier-arrive', True)
        if arrived >= needed:
            open(os.path.join(directory, 'barrier-go'), 'w').write('1')
            return
    deadline = time.time() + float(os.environ.get('HARNESS_BARRIER_TIMEOUT') or '15')
    while not os.path.exists(os.path.join(directory, 'barrier-go')):
        if time.time() > deadline:
            sys.stderr.write('fake gh: barrier timed out\n')
            raise SystemExit(2)
        time.sleep(0.02)


def parse_request(argv):
    method = 'GET'
    endpoint = None
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == '--method':
            method = argv[index + 1]
            index += 2
            continue
        if arg in ('-H', '--hostname', '--input'):
            index += 2
            continue
        if arg.startswith('-'):
            index += 1
            continue
        endpoint = arg
        index += 1
    if endpoint is None:
        sys.stderr.write('fake gh: endpoint required\n')
        raise SystemExit(2)
    return method.upper(), endpoint.split('?', 1)[0]


def main(argv):
    if not argv or argv[0] != 'api':
        sys.stderr.write('fake gh: only `gh api` is implemented\n')
        return 2
    directory = root_dir()
    method, endpoint = parse_request(argv[1:])
    claims = os.path.join(directory, 'claims.json')
    if method == 'GET' and '/contents/' not in endpoint:
        return respond(200, {'default_branch': os.environ.get('HARNESS_DEFAULT_BRANCH', 'main')})
    if 'collaboration/claims.json' not in endpoint:
        return respond(404, {'message': 'unexpected endpoint'})
    if method == 'GET':
        with Lock(directory):
            raw = open(claims, 'rb').read()
        return respond(200, {'type': 'file', 'encoding': 'base64', 'sha': blob_sha(raw),
                             'content': base64.b64encode(raw).decode('ascii')})
    if method != 'PUT':
        return respond(405, {'message': 'method not implemented'})
    body = json.loads(sys.stdin.read() or '{}')
    incoming = base64.b64decode(body.get('content', ''))
    wait_for_peers(directory)
    with Lock(directory):
        forced = int(os.environ.get('HARNESS_FORCE_CONFLICTS') or '0')
        seen = counter(directory, 'forced-conflicts', False)
        if seen < forced:
            counter(directory, 'forced-conflicts', True)
            return respond(409, {'message': 'injected conflict'})
        current = open(claims, 'rb').read()
        ignore_sha = os.environ.get('HARNESS_IGNORE_SHA') == '1'
        if not ignore_sha and body.get('sha') != blob_sha(current):
            return respond(409, {'message': 'stale sha'})
        with open(claims, 'wb') as handle:
            handle.write(incoming)
        counter(directory, 'writes', True)
        return respond(200, {'content': {'sha': blob_sha(incoming)}})
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
