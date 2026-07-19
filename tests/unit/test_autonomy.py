"""Layer 13 acceptance tests: evidence-earned autonomy, A0-A8 (A9 reserved).

Doctrine under test: autonomy is exact (a 9-dimension tuple), rises slowly
through weakest-link promotion, falls immediately on severe failure, and
A9 is never granted by the system. A missing outcome record blocks promotion.
"""
import pytest

from autonomy.levels import (AutonomyAuthority, AutonomyTuple, PromotionEvidence,
                             MAX_GRANTABLE, PROMOTION_CRITERIA)
from provenance.ledger import EvidenceLedger

GENESIS = "sha256:" + "0" * 64


def _authority():
    return AutonomyAuthority(EvidenceLedger(GENESIS))


def _tuple(**kw):
    base = dict(capability="draft.publish", domain="comms", action="publish",
                resource="outbox", target="sandbox", consequence_class="external_contact",
                environment="production", budget_usd=25.0, duration="30 days")
    base.update(kw)
    return AutonomyTuple(**base)


def _evidence(**kw):
    base = dict(criteria={c: True for c in PROMOTION_CRITERIA},
                independent_verifier="external_auditor_01",
                founder_intervention_trend="declining", missing_outcome_records=0)
    base.update(kw)
    return PromotionEvidence(**base)


class TestExactness:
    def test_tuple_key_covers_all_nine_dimensions(self):
        k = _tuple().key().split("|")
        assert len(k) == 9
        # changing one dimension yields a different exact grant
        assert _tuple().key() != _tuple(budget_usd=50.0).key()

    def test_unknown_subject_has_zero_autonomy(self):
        auth = _authority()
        assert auth.level_of("nobody", _tuple()) == 0


class TestIssuance:
    def test_a9_never_granted_at_issue(self):
        auth = _authority()
        with pytest.raises(ValueError, match="A9"):
            auth.issue("agent-1", _tuple(), level=9)

    def test_issue_starts_at_declared_level_and_ledgers(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=2)
        assert lic.level == 2 and lic.active
        kinds = [r.payload["type"] for r in auth.ledger.by_type("event")]
        assert "autonomy.issued" in kinds


class TestPromotion:
    def test_weakest_link_blocks_promotion(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=3)
        ev = _evidence(criteria={c: True for c in PROMOTION_CRITERIA} | {"security": False})
        with pytest.raises(ValueError, match="weakest link"):
            auth.promote(lic.license_id, ev)
        assert lic.level == 3                            # unchanged
        kinds = [r.payload["type"] for r in auth.ledger.by_type("event")]
        assert "autonomy.promotion_refused" in kinds

    def test_missing_outcome_record_blocks_promotion(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=1)
        with pytest.raises(ValueError, match="missing_outcome_records"):
            auth.promote(lic.license_id, _evidence(missing_outcome_records=1))

    def test_rising_founder_intervention_blocks_promotion(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=1)
        with pytest.raises(ValueError, match="founder_intervention"):
            auth.promote(lic.license_id, _evidence(founder_intervention_trend="rising"))

    def test_clean_evidence_promotes_one_level_with_verifier(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=4)
        auth.promote(lic.license_id, _evidence())
        assert lic.level == 5
        rec = [r for r in auth.ledger.by_type("event")
               if r.payload["type"] == "autonomy.promoted"][-1]
        assert rec.payload["verifier"] == "external_auditor_01"

    def test_ladder_climbs_to_a8_and_stops(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=0)
        for target in range(1, MAX_GRANTABLE + 1):
            auth.promote(lic.license_id, _evidence())
            assert lic.level == target
        assert lic.level == 8
        with pytest.raises(ValueError):                  # A9 reserved, unreachable
            auth.promote(lic.license_id, _evidence())


class TestRegression:
    def test_severe_failure_zeroes_and_deactivates_immediately(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=7)
        auth.regress(lic.license_id, failure_class="harm", detail="unforeseen physical risk")
        assert lic.level == 0 and not lic.active
        assert auth.level_of("agent-1", _tuple()) == 0   # inactive reads as zero

    def test_non_severe_failure_steps_down_one(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=5)
        auth.regress(lic.license_id, failure_class="sloppy_reconciliation", detail="late records")
        assert lic.level == 4 and lic.active

    def test_inactive_license_cannot_promote_without_renewal(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=6)
        auth.regress(lic.license_id, failure_class="concealment", detail="hid failure")
        with pytest.raises(ValueError, match="renewal"):
            auth.promote(lic.license_id, _evidence())

    def test_renewal_requires_fresh_complete_evidence(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=6)
        auth.regress(lic.license_id, failure_class="unauthorized_effect", detail="x")
        weak = _evidence(criteria={c: True for c in PROMOTION_CRITERIA} | {"recovery": False})
        with pytest.raises(ValueError, match="renewal criteria"):
            auth.renew(lic.license_id, weak)
        auth.renew(lic.license_id, _evidence())
        assert lic.active and lic.level == 0             # reactivated at A0, not A6
