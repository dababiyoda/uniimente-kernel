"""An approval of one paid attempt cannot approve another after the mission's spend changed (extracted from #157)."""
from greg.authority import AuthorityOffice


def digest(cost, spent, budget=5.0):
    return AuthorityOffice.scope_digest(mission_id="m:x", capability_id="worker.commission", params={"order": "a"},
                                        target="work:a", consequence_class="internal_write", cost_usd=cost,
                                        spent_usd=spent, budget_usd=budget)


def test_a_paid_scope_is_bound_to_the_spend_state_it_was_approved_under():
    approved = digest(1.0, 0.0)
    assert digest(1.0, 0.0) == approved                       # the same attempt keeps its approval
    assert digest(1.0, 1.0) != approved                       # after spend (or a reserved cap) it must be re-asked
    assert digest(1.0, 0.0, budget=6.0) != approved           # and after the mandate changed


def test_free_reads_keep_a_stable_scope_whatever_was_spent():
    assert digest(0.0, 0.0) == digest(0.0, 3.0) == digest(0.0, 0.0, budget=9.0)
