"""Conditional-update fixtures test the remote state machine without network."""
import base64
import copy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import subprocess
import unittest
from unittest.mock import patch

from scripts.remote_collaboration_registry import (
    RemoteRegistry, RemoteError, ConflictError, gh_transport, LIMIT)


def manifest(sid='worker-A', paths=None, interfaces=None, expiry=3600):
    return {'session_id': sid, 'repository': '/never/published', 'head_sha': 'a' * 40,
            'paths': paths or ['src/'], 'interfaces': interfaces or [],
            'expires_at': (datetime.now(timezone.utc) + timedelta(seconds=expiry)).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'work_item': 'https://github.com/owner/kernel/issues/1',
            'source_reads': [{'kind': kind, 'sha256': str(i) * 64,
                              'reference': 'https://github.com/source/' + kind,
                              'path': '/private/snapshot/' + kind}
                             for i, kind in enumerate(('protocol', 'discussion', 'board'), 1)]}


class MemoryContents:
    def __init__(self):
        self.state = {'version': 1, 'claims': {}, 'audit': []}
        self.before_put = None
        self.writes = 0
        self.error = None
        self.unknown_after_write = False
        self.default_branch = 'main'

    def raw(self):
        return json.dumps(self.state, sort_keys=True, separators=(',', ':'))

    def sha(self):
        raw = self.raw().encode()
        return hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()

    def __call__(self, method, endpoint, body=None):
        if self.error:
            raise self.error
        if method == 'GET' and '/contents/' not in endpoint:
            return {'default_branch': self.default_branch}
        if method == 'GET':
            return {'type': 'file', 'encoding': 'base64', 'sha': self.sha(),
                    'content': base64.b64encode(self.raw().encode()).decode()}
        if self.before_put:
            action, self.before_put = self.before_put, None
            action()
        if body['sha'] != self.sha():
            raise ConflictError('stale update')
        self.state = json.loads(base64.b64decode(body['content']))
        self.writes += 1
        if self.unknown_after_write:
            self.unknown_after_write = False
            raise RemoteError('unknown outcome')
        return {'content': {'sha': self.sha()}}


class RemoteRegistryTests(unittest.TestCase):
    def setUp(self):
        self.store = MemoryContents()
        self.registry = RemoteRegistry('Owner/Kernel', 'coordination/test', self.store)

    def test_reserve_check_idempotent_and_local_paths_not_published(self):
        claim = manifest()
        self.registry.reserve(claim, 'Owner/Organ')
        self.assertEqual(self.registry.check(claim, 'owner/organ')['state'], 'active')
        self.registry.reserve(claim, 'owner/organ')
        self.assertEqual(self.store.writes, 1)
        self.assertNotIn('/private/', self.store.raw())
        self.assertNotIn('/never/', self.store.raw())

    def test_overlapping_cross_container_paths_refused_disjoint_scopes_admitted(self):
        a, b = manifest(), manifest('B', ['src/nested/'])
        self.registry.reserve(a, 'owner/organ')
        other = RemoteRegistry('owner/kernel', 'coordination/test', self.store)
        with self.assertRaisesRegex(RemoteError, 'conflict'):
            other.reserve(b, 'OWNER/ORGAN')
        other.reserve(manifest('B', ['tests/']), 'owner/organ')
        other.reserve(manifest('C', ['src/']), 'owner/other-organ')

    def test_shared_interfaces_conflict_across_repositories(self):
        self.registry.reserve(manifest(interfaces=['shared-wire']), 'owner/first')
        with self.assertRaisesRegex(RemoteError, 'conflict'):
            self.registry.reserve(manifest('B', interfaces=['shared-wire']), 'owner/second')

    def test_sha_conflict_rereads_and_refuses_new_competing_claim(self):
        other = RemoteRegistry('owner/kernel', 'coordination/test', self.store)
        self.store.before_put = lambda: other.reserve(manifest('winner'), 'owner/organ')
        with self.assertRaisesRegex(RemoteError, 'conflict'):
            self.registry.reserve(manifest('loser'), 'owner/organ')
        self.assertEqual(list(self.store.state['claims']), ['winner'])

    def test_sha_conflict_can_retry_disjoint_claim_without_lost_update(self):
        other = RemoteRegistry('owner/kernel', 'coordination/test', self.store)
        self.store.before_put = lambda: other.reserve(manifest('first', ['tests/']), 'owner/organ')
        self.registry.reserve(manifest('second'), 'owner/organ')
        self.assertEqual(set(self.store.state['claims']), {'first', 'second'})
        self.assertEqual(len(self.store.state['audit']), 2)

    def test_unknown_committed_outcome_is_not_retried_but_next_reserve_reconciles(self):
        claim = manifest()
        self.store.unknown_after_write = True
        with self.assertRaisesRegex(RemoteError, 'unknown'):
            self.registry.reserve(claim, 'owner/organ')
        self.assertEqual(self.store.writes, 1)
        self.registry.reserve(claim, 'owner/organ')
        self.assertEqual(self.store.writes, 1)

    def test_outage_or_denied_access_never_falls_back(self):
        self.store.error = RemoteError('403')
        for call in (lambda: self.registry.reserve(manifest(), 'owner/organ'),
                     lambda: self.registry.check(manifest(), 'owner/organ'),
                     lambda: self.registry.release('A')):
            with self.assertRaises(RemoteError):
                call()
        self.assertEqual(self.store.writes, 0)

    def test_expired_claim_not_stolen_and_owner_can_release(self):
        claim = manifest()
        self.registry.reserve(claim, 'owner/organ')
        self.store.state['claims']['worker-A']['claim']['expires_at'] = manifest(expiry=-10)['expires_at']
        with self.assertRaisesRegex(RemoteError, 'conflict'):
            self.registry.reserve(manifest('B'), 'owner/organ')
        with self.assertRaisesRegex(RemoteError, 'expired'):
            self.registry.check({**claim, 'expires_at': manifest(expiry=-10)['expires_at']}, 'owner/organ')
        self.registry.release('worker-A')
        self.registry.reserve(manifest('B'), 'owner/organ')

    def test_live_session_cannot_replace_its_scope_or_head(self):
        claim = manifest()
        self.registry.reserve(claim, 'owner/organ')
        for changed in ({**claim, 'paths': ['elsewhere/']}, {**claim, 'head_sha': 'b' * 40}):
            with self.assertRaises(RemoteError):
                self.registry.reserve(changed, 'owner/organ')
            with self.assertRaises(RemoteError):
                self.registry.check(changed, 'owner/organ')

    def test_pending_transfer_survives_finish_and_needs_named_receiver(self):
        claim = manifest()
        self.registry.reserve(claim, 'owner/organ')
        self.registry.handoff('worker-A', 'B', 'https://github.com/ack/offer')
        self.registry.finish('worker-A')
        with self.assertRaises(RemoteError): self.registry.check(claim, 'owner/organ')
        with self.assertRaises(RemoteError): self.registry.reserve(manifest('C'), 'owner/organ')
        with self.assertRaises(RemoteError):
            self.registry.accept(manifest('C'), 'owner/organ', 'worker-A', 'https://github.com/ack/accept')
        receiver = manifest('B')
        receiver['head_sha'] = 'b' * 40  # receiver binds its own current checkout
        self.registry.accept(receiver, 'owner/organ', 'worker-A', 'https://github.com/ack/accept')
        self.registry.check(receiver, 'owner/organ')
        self.assertEqual(self.store.state['claims']['worker-A']['state'], 'released')

    def test_receiver_cannot_change_scope_or_take_live_receiver_claim(self):
        self.registry.reserve(manifest(), 'owner/organ')
        self.registry.handoff('worker-A', 'B', 'https://github.com/ack/offer')
        with self.assertRaisesRegex(RemoteError, 'differs'):
            self.registry.accept(manifest('B', ['other/']), 'owner/organ', 'worker-A', 'https://github.com/ack/accept')
        self.registry.reserve(manifest('B', ['other/']), 'owner/organ')
        with self.assertRaisesRegex(RemoteError, 'already owns'):
            self.registry.accept(manifest('B'), 'owner/organ', 'worker-A', 'https://github.com/ack/accept')

    def test_cleanup_idempotent_and_audit_retained(self):
        self.registry.finish('missing')
        self.registry.release('missing')
        self.registry.reserve(manifest(), 'owner/organ')
        self.registry.finish('worker-A')
        self.registry.finish('worker-A')
        self.assertEqual([e['action'] for e in self.store.state['audit']], ['reserve', 'finish'])

    def test_corruption_and_malformed_state_refuse(self):
        for state in ({'version': 1, 'claims': [], 'audit': []},
                      {'version': True, 'claims': {}, 'audit': []},
                      {'version': 1, 'claims': {}, 'audit': [{'action': 'erase'}]}):
            self.store.state = state
            with self.assertRaises(RemoteError): self.registry.reserve(manifest(), 'owner/organ')
        self.store.state = {'version': 1, 'claims': {}, 'audit': []}
        self.registry.reserve(manifest(), 'owner/organ')
        self.store.state['claims']['worker-A']['state'] = 'unknown'
        with self.assertRaises(RemoteError): self.registry.check(manifest(), 'owner/organ')

    def test_size_limit_never_truncates_history(self):
        self.store.state['audit'] = [{'at': manifest()['expires_at'], 'action': 'reserve', 'session': 'past',
                                     'detail': {'data': 'x' * LIMIT}}]
        with self.assertRaises(RemoteError): self.registry.reserve(manifest(), 'owner/organ')
        self.assertEqual(self.store.writes, 0)

    def test_configuration_and_unsafe_manifest_refused(self):
        for branch in ('main', 'master', 'coordination/../main', 'coordination/', 'coordination/a//b'):
            with self.assertRaises(RemoteError): RemoteRegistry('owner/kernel', branch, self.store)
        for paths in (['../outside'], ['/absolute'], ['src//bad']):
            with self.assertRaises(RemoteError): self.registry.reserve(manifest(paths=paths), 'owner/organ')
        with self.assertRaises(RemoteError): self.registry.reserve(manifest(), 'https://github.com/owner/repo')

    def test_coordination_prefix_does_not_allow_actual_default_branch(self):
        self.store.default_branch = 'coordination/test'
        with self.assertRaisesRegex(RemoteError, 'default branch'):
            self.registry.reserve(manifest(), 'owner/organ')
        self.assertEqual(self.store.writes, 0)

    def test_unexpected_write_blob_is_unknown_outcome(self):
        def transport(method, endpoint, body=None):
            response = self.store(method, endpoint, body)
            if method == 'PUT':
                return {'content': {'sha': 'f' * 40}}
            return response
        registry = RemoteRegistry('owner/kernel', 'coordination/test', transport)
        with self.assertRaisesRegex(RemoteError, 'outcome unknown'):
            registry.reserve(manifest(), 'owner/organ')
        self.assertEqual(self.store.writes, 1)

    def test_gh_uses_existing_auth_no_shell_and_sanitizes_errors(self):
        response = subprocess.CompletedProcess([], 0, 'HTTP/2.0 200 OK\nContent-Type: application/json\n\n{"ok":true}', '')
        with patch('scripts.remote_collaboration_registry.subprocess.run', return_value=response) as run:
            self.assertEqual(gh_transport('GET', 'repos/owner/repo/contents/file'), {'ok': True})
            self.assertNotIn('shell', run.call_args.kwargs)
            self.assertEqual(run.call_args.args[0][:5], ['gh', 'api', '--hostname', 'github.com', '--include'])
        response = subprocess.CompletedProcess([], 1, 'HTTP/2.0 409 Conflict\n\n{}', 'secret-never-print')
        with patch('scripts.remote_collaboration_registry.subprocess.run', return_value=response):
            with self.assertRaises(ConflictError): gh_transport('PUT', 'path', {})
        response = subprocess.CompletedProcess([], 1, '', 'secret-never-print')
        with patch('scripts.remote_collaboration_registry.subprocess.run', return_value=response):
            with self.assertRaises(RemoteError) as exc: gh_transport('PUT', 'path', {})
            self.assertNotIn('secret-never-print', str(exc.exception))

    def test_api_envelope_allows_base64_expansion_without_relaxing_state_limit(self):
        content = base64.b64encode(b'x' * (LIMIT - 100)).decode()
        response = subprocess.CompletedProcess([], 0, 'HTTP/2.0 200 OK\n\n' + json.dumps({'content': content}), '')
        with patch('scripts.remote_collaboration_registry.subprocess.run', return_value=response):
            self.assertEqual(gh_transport('GET', 'path')['content'], content)
        response = subprocess.CompletedProcess([], 0, 'HTTP/2.0 200 OK\n\n' + json.dumps({'content': 'x' * (2 * LIMIT)}), '')
        with patch('scripts.remote_collaboration_registry.subprocess.run', return_value=response):
            with self.assertRaises(RemoteError): gh_transport('GET', 'path')


if __name__ == '__main__':
    unittest.main()
