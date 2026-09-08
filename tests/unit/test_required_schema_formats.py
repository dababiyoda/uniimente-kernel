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
