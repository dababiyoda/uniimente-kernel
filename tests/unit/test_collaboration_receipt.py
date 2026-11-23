"""Tests for the exact inline workflow validator; no repository runtime imported."""
import json
from pathlib import Path
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github/workflows/collaboration-receipt.yml'
source = textwrap.dedent(WORKFLOW.read_text().split('        run: |\n', 1)[1])
namespace = {'__name__': 'receipt_validator_under_test'}
exec(compile(source, str(WORKFLOW), 'exec'), namespace)
validate = namespace['validate']
ReceiptError = namespace['ReceiptError']
START, END = namespace['START'], namespace['END']
A, B, C = 'a' * 40, 'b' * 40, 'c' * 40
GUIDE = f'https://github.com/dababiyoda/uniimente-kernel/blob/{C}/docs/collaboration/START_HERE.md'

def receipt():
    return dict(version=2, repository='dababiyoda/example', base_sha=A, head_sha=B,
        protocol_ref=GUIDE, intent_refs=['intent-1'],
        read_set=[dict(path='AGENTS.md', revision=B), dict(path=GUIDE, revision=C)],
        scope='Only contributor metadata', classification='constitutional',
        deliberation_ref='docs/collaboration/decision.json',
        validation=[dict(command='unit tests', result='pass', evidence='local execution')],
        limitations=['Not production proof'], rollback='Revert the scoped commit',
        coordination=dict(task_ref='https://github.com/dababiyoda/example/issues/1',
            session_id='worker-session-01', files=['docs/example.md'], interfaces=[],
            recheck_at='2026-10-22T12:00:00Z',
            overlap=dict(status='clear', inspected_refs=['https://github.com/dababiyoda/example/pulls'], acknowledgment_refs=[]),
            integration=dict(repository='dababiyoda/example', branch='main', base_sha=A, owner='unassigned')),
        handoff=dict(owner='reviewer', next_action='Review draft', stop_condition='No merge permission',
            acknowledgment=dict(status='pending', receiver_session=None, reference=None)),
        review=dict(status='pending', reference=None))

def event(data=None):
    data = receipt() if data is None else data
    return dict(repository=dict(full_name='dababiyoda/example'), pull_request=dict(
        base=dict(sha=A), head=dict(sha=B), draft=True,
        body=f'{START}\n```json\n{json.dumps(data)}\n```\n{END}'))

class ReceiptTests(unittest.TestCase):
    def test_receiver_placeholder_is_refused(self):
        d = receipt()
        d['handoff']['acknowledgment'] = dict(status='accepted', receiver_session='<receiver>', reference='ack-1')
        with self.assertRaises(ReceiptError): validate(event(d))

    def test_file_claims_stay_repository_relative(self):
        for path in ('/etc/passwd', '../../other-repo/a', 'docs/../a', 'C:\\a', '<file>', 'docs//a'):
            d = receipt(); d['coordination']['files'] = [path]
            with self.subTest(path=path), self.assertRaises(ReceiptError): validate(event(d))
        d = receipt(); d['coordination']['files'] = ['docs/']
        validate(event(d))

    def test_obvious_session_placeholder_is_refused(self):
        d = receipt(); d['coordination']['session_id'] = '<actual session ID>'
        with self.assertRaises(ReceiptError): validate(event(d))

    def test_valid_draft(self):
        self.assertEqual(validate(event())['head_sha'], B)
    def test_lightweight_needs_no_deliberation(self):
        d = receipt(); d.update(classification='lightweight', deliberation_ref=None)
        e = event(d); e['pull_request']['draft'] = False
        validate(e)
    def test_negative_and_unrun_checks_are_preserved(self):
        for result in ('fail', 'not_run'):
            d = receipt(); d['validation'][0]['result'] = result
            self.assertEqual(validate(event(d))['validation'][0]['result'], result)
    def test_missing_receipt(self):
        e = event(); e['pull_request']['body'] = 'no receipt'
        with self.assertRaises(ReceiptError): validate(e)
    def test_duplicate_receipt(self):
        e = event(); e['pull_request']['body'] *= 2
        with self.assertRaises(ReceiptError): validate(e)
    def test_duplicate_json_key(self):
        e = event(); e['pull_request']['body'] = e['pull_request']['body'].replace('"version": 2', '"version": 2, "version": 2')
        with self.assertRaises(ReceiptError): validate(e)
    def test_reversed_markers(self):
        e = event(); e['pull_request']['body'] = END + '\n{}\n' + START
        with self.assertRaises(ReceiptError): validate(e)
    def test_stale_base(self):
        e = event(); e['pull_request']['base']['sha'] = C
        with self.assertRaises(ReceiptError): validate(e)
    def test_stale_head(self):
        e = event(); e['pull_request']['head']['sha'] = C
        with self.assertRaises(ReceiptError): validate(e)
    def test_other_repository(self):
        e = event(); e['repository']['full_name'] = 'other/repo'
        with self.assertRaises(ReceiptError): validate(e)
    def test_floating_guide(self):
        d = receipt(); d['protocol_ref'] = GUIDE.replace(C, 'main')
        with self.assertRaises(ReceiptError): validate(event(d))
    def test_missing_required_read(self):
        d = receipt(); d['read_set'][0]['path'] = 'README.md'
        with self.assertRaises(ReceiptError): validate(event(d))
    def test_inconsistent_guide_revision(self):
        d = receipt(); d['read_set'][1]['revision'] = A
        with self.assertRaises(ReceiptError): validate(event(d))
    def test_no_material_deliberation(self):
        d = receipt(); d['deliberation_ref'] = None
        with self.assertRaises(ReceiptError): validate(event(d))
    def test_unknown_field(self):
        d = receipt(); d['self_authorized'] = True
        with self.assertRaises(ReceiptError): validate(event(d))
    def test_empty_handoff(self):
        d = receipt(); d['handoff']['next_action'] = ''
        with self.assertRaises(ReceiptError): validate(event(d))
    def test_non_draft_pending_review(self):
        e = event(); e['pull_request']['draft'] = False
        with self.assertRaises(ReceiptError): validate(e)
    def test_complete_review_is_metadata_only(self):
        d = receipt(); d['review'] = dict(status='complete', reference='https://github.com/owner/repo/pull/1#review')
        e = event(d); e['pull_request']['draft'] = False
        validate(e)  # Existence/independence is explicitly not authenticated.
    def test_shell_text_is_inert(self):
        d = receipt(); d['scope'] = '$(touch /tmp/DO_NOT_EXECUTE); __import__("os")'
        self.assertEqual(validate(event(d))['scope'], d['scope'])
    def test_boolean_version_is_not_integer_version(self):
        d = receipt(); d['version'] = True
        with self.assertRaises(ReceiptError): validate(event(d))
    def test_malformed_json(self):
        e = event(); e['pull_request']['body'] = f'{START}\n```json\n{{\n```\n{END}'
        with self.assertRaises(ReceiptError): validate(e)
    def test_wrong_event(self):
        with self.assertRaises(ReceiptError): validate({})
    def test_non_finite_json(self):
        e = event(); e['pull_request']['body'] = e['pull_request']['body'].replace('"version": 2', '"version": NaN')
        with self.assertRaises(ReceiptError): validate(e)
    def test_oversized_body(self):
        e = event(); e['pull_request']['body'] += 'x' * 65537
        with self.assertRaises(ReceiptError): validate(e)

    def test_v1_is_not_silently_grandfathered(self):
        d = receipt(); d['version'] = 1
        with self.assertRaises(ReceiptError): validate(event(d))

    def test_agents_revision_must_match_current_head(self):
        d = receipt(); d['read_set'][0]['revision'] = A
        with self.assertRaises(ReceiptError): validate(event(d))

    def test_missing_coordination_or_fields(self):
        d = receipt(); del d['coordination']
        with self.assertRaises(ReceiptError): validate(event(d))
        for key in receipt()['coordination']:
            with self.subTest(key=key):
                d = receipt(); del d['coordination'][key]
                with self.assertRaises(ReceiptError): validate(event(d))

    def test_blank_or_placeholder_session_identity(self):
        for value in (None, [], '', '   ', 'unassigned', 'UNKNOWN'):
            with self.subTest(value=value):
                d = receipt(); d['coordination']['session_id'] = value
                with self.assertRaises(ReceiptError): validate(event(d))

    def test_claimed_files_cannot_be_empty_duplicate_or_malformed(self):
        for value in (None, 'docs/a.md', [], [''], ['x', ' x '], [False]):
            with self.subTest(value=value):
                d = receipt(); d['coordination']['files'] = value
                with self.assertRaises(ReceiptError): validate(event(d))

    def test_bad_recheck_dates_and_non_utc_are_refused(self):
        for value in ('tomorrow', '2026-02-30T12:00:00Z', '2026-10-22T25:00:00Z',
                      '2026-10-22T12:00:00+00:00', '2026-10-22T12:00:00', '', None, 1):
            with self.subTest(value=value):
                d = receipt(); d['coordination']['recheck_at'] = value
                with self.assertRaises(ReceiptError): validate(event(d))

    def test_historical_receipt_is_not_a_live_lock(self):
        d = receipt(); d['coordination']['recheck_at'] = '2020-01-01T00:00:00Z'
        validate(event(d))  # Syntax check only; a worker must refresh expired claims.

    def test_overlap_search_reference_required(self):
        d = receipt(); d['coordination']['overlap']['inspected_refs'] = []
        with self.assertRaises(ReceiptError): validate(event(d))

    def test_split_needs_counterpart_acknowledgment_reference(self):
        d = receipt(); d['coordination']['overlap']['status'] = 'split'
        with self.assertRaises(ReceiptError): validate(event(d))
        d['coordination']['overlap']['acknowledgment_refs'] = ['https://github.com/dababiyoda/example/issues/1#issuecomment-2']
        validate(event(d))  # Reference authentication remains the reviewer's job.

    def test_clear_overlap_cannot_claim_a_split(self):
        d = receipt(); d['coordination']['overlap']['acknowledgment_refs'] = ['split-ack']
        with self.assertRaises(ReceiptError): validate(event(d))

    def test_blocked_overlap_remains_draft_even_with_completed_review(self):
        d = receipt(); d['coordination']['overlap']['status'] = 'blocked'
        d['review'] = dict(status='complete', reference='review')
        validate(event(d))
        e = event(d); e['pull_request']['draft'] = False
        with self.assertRaises(ReceiptError): validate(e)

    def test_blocked_overlap_refuses_even_lightweight_non_draft(self):
        d = receipt(); d.update(classification='lightweight', deliberation_ref=None)
        d['coordination']['overlap']['status'] = 'blocked'
        e = event(d); e['pull_request']['draft'] = False
        with self.assertRaises(ReceiptError): validate(e)

    def test_integration_requires_pinned_destination(self):
        for key, value in [('repository', ''), ('branch', None), ('base_sha', 'main'), ('owner', '')]:
            with self.subTest(key=key):
                d = receipt(); d['coordination']['integration'][key] = value
                with self.assertRaises(ReceiptError): validate(event(d))

    def test_real_receiver_metadata_acceptance(self):
        d = receipt(); d['handoff']['acknowledgment'] = dict(
            status='accepted', receiver_session='receiver-session-02', reference='handoff-comment')
        validate(event(d))

    def test_self_handoff_is_refused(self):
        for receiver in ('worker-session-01', ' WORKER-SESSION-01 '):
            d = receipt(); d['handoff']['acknowledgment'] = dict(
                status='accepted', receiver_session=receiver, reference='handoff-comment')
            with self.assertRaises(ReceiptError): validate(event(d))

    def test_accepted_handoff_needs_actual_receiver_and_reference(self):
        for receiver, reference in [(None, 'ack'), ('unassigned', 'ack'), ('receiver', None), ('receiver', '')]:
            with self.subTest(receiver=receiver, reference=reference):
                d = receipt(); d['handoff']['acknowledgment'] = dict(
                    status='accepted', receiver_session=receiver, reference=reference)
                with self.assertRaises(ReceiptError): validate(event(d))

    def test_pending_handoff_does_not_fabricate_acknowledgment(self):
        d = receipt(); d['handoff']['acknowledgment']['reference'] = 'pretend-ack'
        with self.assertRaises(ReceiptError): validate(event(d))

    def test_pending_handoff_can_name_receiver_without_claiming_acceptance(self):
        d = receipt(); d['handoff']['acknowledgment']['receiver_session'] = 'receiver-session-02'
        validate(event(d))

    def test_pending_handoff_does_not_block_reviewed_pr(self):
        d = receipt(); d['review'] = dict(status='complete', reference='review')
        e = event(d); e['pull_request']['draft'] = False
        validate(e)  # Receiver acceptance is not mandatory before every PR's work is done.

    def test_event_type_errors_are_receipt_errors(self):
        for key, value in [('repository', None), ('repository', []), ('pull_request', []), ('pull_request', None)]:
            with self.subTest(key=key, value=value):
                e = event(); e[key] = value
                with self.assertRaises(ReceiptError): validate(e)
        for key, value in [('base', None), ('head', 'sha'), ('draft', 'true'), ('draft', None)]:
            with self.subTest(key=key, value=value):
                e = event(); e['pull_request'][key] = value
                with self.assertRaises(ReceiptError): validate(e)

    def test_nested_type_errors_are_receipt_errors(self):
        cases = [('coordination',), ('coordination', 'overlap'), ('coordination', 'integration'),
                 ('handoff',), ('handoff', 'acknowledgment'), ('review',)]
        for path in cases:
            for value in (None, [], 'not-an-object', True):
                with self.subTest(path=path, value=value):
                    d = receipt(); target = d
                    for key in path[:-1]: target = target[key]
                    target[path[-1]] = value
                    with self.assertRaises(ReceiptError): validate(event(d))

    def test_no_executable_privilege_added_to_workflow(self):
        workflow = WORKFLOW.read_text()
        self.assertIn('permissions: {}', workflow)
        for forbidden in ('pull_request_target:', 'actions/checkout', '${{', 'secrets:', 'contents: write'):
            self.assertNotIn(forbidden, workflow)

if __name__ == '__main__':
    unittest.main(verbosity=2)

