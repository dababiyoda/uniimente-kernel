"""Tests for the exact inline workflow validator; no repository runtime imported."""
import json
from pathlib import Path
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[3]
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
    return dict(version=1, repository='dababiyoda/example', base_sha=A, head_sha=B,
        protocol_ref=GUIDE, intent_refs=['intent-1'],
        read_set=[dict(path='AGENTS.md', revision=B), dict(path=GUIDE, revision=C)],
        scope='Only contributor metadata', classification='constitutional',
        deliberation_ref='docs/collaboration/decision.json',
        validation=[dict(command='unit tests', result='pass', evidence='local execution')],
        limitations=['Not production proof'], rollback='Revert the scoped commit',
        handoff=dict(owner='reviewer', next_action='Review draft', stop_condition='No merge permission'),
        review=dict(status='pending', reference=None))

def event(data=None):
    data = receipt() if data is None else data
    return dict(repository=dict(full_name='dababiyoda/example'), pull_request=dict(
        base=dict(sha=A), head=dict(sha=B), draft=True,
        body=f'{START}\n```json\n{json.dumps(data)}\n```\n{END}'))

class ReceiptTests(unittest.TestCase):
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
        e = event(); e['pull_request']['body'] = e['pull_request']['body'].replace('"version": 1', '"version": 1, "version": 1')
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
        e = event(); e['pull_request']['body'] = e['pull_request']['body'].replace('"version": 1', '"version": NaN')
        with self.assertRaises(ReceiptError): validate(e)
    def test_oversized_body(self):
        e = event(); e['pull_request']['body'] += 'x' * 65537
        with self.assertRaises(ReceiptError): validate(e)

if __name__ == '__main__':
    unittest.main(verbosity=2)
