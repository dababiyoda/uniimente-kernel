"""Budget failures remain observable, without allowing another consequence."""
from datetime import datetime, timezone

import pytest

from greg.lightcone import LightCone, ScopeError


def cone(budget=1):
    return LightCone(frozenset({'worker.appraise', 'worker.commission'}), ('work:job',),
                     'internal_write', budget, '2099-01-01T00:00:00Z')


def test_actual_overspend_remains_observable_but_cannot_fund_another_action():
    scope = cone()
    common = {'target': 'work:job', 'spent_usd': 1.01,
              'at': datetime(2026, 10, 2, tzinfo=timezone.utc)}
    assert scope.admits(capability='worker.appraise', consequence_class='read_only', cost_usd=0, **common) == []
    assert scope.admits(capability='worker.commission', consequence_class='internal_write', cost_usd=0, **common)
    assert scope.admits(capability='worker.appraise', consequence_class='read_only', cost_usd=0.01, **common)
    assert scope.admits(capability='worker.appraise', consequence_class='read_only', cost_usd=0,
                        **{**common, 'target': 'work:outside'})
    assert scope.admits(capability='unregistered.read', consequence_class='read_only', cost_usd=0, **common)
    assert scope.admits(capability='worker.appraise', consequence_class='read_only', cost_usd=0,
                        **{**common, 'at': datetime(2100, 1, 1, tzinfo=timezone.utc)})


@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf'), -1, True])
def test_budget_cannot_hide_an_overrun_in_nonfinite_or_boolean_numbers(value):
    with pytest.raises(ScopeError):
        cone(value)
    with pytest.raises(ScopeError):
        LightCone.from_dict({**cone().to_dict(), 'budget_usd': value})


@pytest.mark.parametrize('value', [float('nan'), float('inf'), float('-inf'), -1, True])
def test_even_free_observation_rejects_invalid_cost_or_retained_spend(value):
    common = {'capability': 'worker.appraise', 'target': 'work:job', 'consequence_class': 'read_only',
              'at': datetime(2026, 10, 2, tzinfo=timezone.utc)}
    assert cone().admits(cost_usd=value, spent_usd=0, **common)
    assert cone().admits(cost_usd=0, spent_usd=value, **common)
