"""SR10 regression: optional format dependencies must never disable admission checks."""
import pytest
from jsonschema import FormatChecker
from adapters.contract_validation import validate_contract, validator
from tests.unit.test_consequence_gate import stack, make_proposal


def test_invalid_grant_timestamp_is_not_accepted_by_schema(stack):
    gate, _, _, actor, _ = stack
    proposal = make_proposal(actor.passport_id)
    grant = gate.grants.issue_single_action(proposal=proposal, policy_version='1.0.0')
    grant['expires_at'] = 'not-an-observation-time'
    with pytest.raises(ValueError):
        validate_contract(grant, 'capability-grant')


def test_missing_format_implementation_refuses(monkeypatch):
    validator.cache_clear()
    monkeypatch.delitem(FormatChecker.checkers, 'date-time', raising=False)
    try:
        with pytest.raises(ValueError, match='format'):
            validator('capability-grant')
    finally:
        validator.cache_clear()


@pytest.mark.parametrize('schema,payload', [
    ('wire-opportunity-packet', {'id':'fixture-packet','schema_version':'1.1','observed_pain':'retained observation'}),
    ('wire-venture-assessment', {'id':'fixture-assessment','schema_version':'1.1',
        'opportunity_packet_id':'fixture-packet','go_no_go':'defer','requires_human_approval':True}),
])
@pytest.mark.parametrize('timestamp', [None, 'tomorrow', '2026-09-09T00:00:00'])
def test_wire_observation_time_is_required_and_has_timezone(schema, payload, timestamp):
    valid = {**payload, 'created_at':'2026-09-09T00:00:00Z'}
    validate_contract(valid, schema)
    invalid = dict(payload) if timestamp is None else {**payload, 'created_at':timestamp}
    with pytest.raises(ValueError):
        validate_contract(invalid, schema)


@pytest.mark.parametrize('adapter', ['packet', 'assessment'])
def test_translators_cannot_bypass_missing_format_support(monkeypatch, adapter):
    from adapters.daleobanks_opportunity import AdapterError, _validate_canonical
    from adapters.wealthmachine_assessment import _validate
    validator.cache_clear()
    monkeypatch.delitem(FormatChecker.checkers, 'date-time', raising=False)
    try:
        with pytest.raises(AdapterError, match='format implementation unavailable'):
            if adapter == 'packet':
                _validate_canonical({})
            else:
                _validate({}, 'wire-venture-assessment.schema.json', 'wire assessment')
    finally:
        validator.cache_clear()
