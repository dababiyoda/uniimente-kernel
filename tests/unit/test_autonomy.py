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
            auth.issue("agent-1", _tuple(), level=9, authorized_by="Alfonso Lopez")

    def test_issue_starts_at_declared_level_and_ledgers(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=2, authorized_by="Alfonso Lopez")
        assert lic.level == 2 and lic.active
        kinds = [r.payload["type"] for r in auth.ledger.by_type("event")]
        assert "autonomy.issued" in kinds


class TestPromotion:
    def test_weakest_link_blocks_promotion(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=3, authorized_by="Alfonso Lopez")
        ev = _evidence(criteria={c: True for c in PROMOTION_CRITERIA} | {"security": False})
        with pytest.raises(ValueError, match="weakest link"):
            auth.promote(lic.license_id, ev)
        assert lic.level == 3                            # unchanged
        kinds = [r.payload["type"] for r in auth.ledger.by_type("event")]
        assert "autonomy.promotion_refused" in kinds

    def test_missing_outcome_record_blocks_promotion(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=1, authorized_by="Alfonso Lopez")
        with pytest.raises(ValueError, match="missing_outcome_records"):
            auth.promote(lic.license_id, _evidence(missing_outcome_records=1))

    def test_rising_founder_intervention_blocks_promotion(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=1, authorized_by="Alfonso Lopez")
        with pytest.raises(ValueError, match="founder_intervention"):
            auth.promote(lic.license_id, _evidence(founder_intervention_trend="rising"))

    def test_clean_evidence_promotes_one_level_with_verifier(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=4, authorized_by="Alfonso Lopez")
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
        lic = auth.issue("agent-1", _tuple(), level=7, authorized_by="Alfonso Lopez")
        auth.regress(lic.license_id, failure_class="harm", detail="unforeseen physical risk")
        assert lic.level == 0 and not lic.active
        assert auth.level_of("agent-1", _tuple()) == 0   # inactive reads as zero

    def test_non_severe_failure_steps_down_one(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=5, authorized_by="Alfonso Lopez")
        auth.regress(lic.license_id, failure_class="sloppy_reconciliation", detail="late records")
        assert lic.level == 4 and lic.active

    def test_inactive_license_cannot_promote_without_renewal(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=6, authorized_by="Alfonso Lopez")
        auth.regress(lic.license_id, failure_class="concealment", detail="hid failure")
        with pytest.raises(ValueError, match="renewal"):
            auth.promote(lic.license_id, _evidence())

    def test_renewal_requires_fresh_complete_evidence(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=6, authorized_by="Alfonso Lopez")
        auth.regress(lic.license_id, failure_class="unauthorized_effect", detail="x")
        weak = _evidence(criteria={c: True for c in PROMOTION_CRITERIA} | {"recovery": False})
        with pytest.raises(ValueError, match="renewal criteria"):
            auth.renew(lic.license_id, weak)
        auth.renew(lic.license_id, _evidence())
        assert lic.active and lic.level == 0             # reactivated at A0, not A6


# --- the constructor must not be a way around the ladder ---------------------

class TestIssueIsNotAWayPastPromotion:
    """`promote` enforces ten criteria; `issue` used to enforce none.

    Found 2026-08-24 by asking whether a standing A5/A6 mandate could be
    lawfully granted today. `promote` correctly refused — no external outcomes,
    no calibration — and then `issue(subject, tuple_, level=8)` returned an A8
    license against an empty ledger, on a production-environment tuple with a
    $10,000 budget and an external target. Only A9 was refused.

    The ladder's whole purpose was optional, defeated through its own
    constructor, and the class docstring asserted the opposite: "cannot waive
    criteria". A docstring is not an enforcement mechanism.
    """

    def _auth(self):
        return AutonomyAuthority(EvidenceLedger("sha256:" + "0" * 64))

    def test_autonomy_above_a0_is_refused_without_a_named_authorizer(self):
        auth = self._auth()
        for level in (1, 5, 6, 8):
            with pytest.raises(ValueError, match="named authorizer"):
                auth.issue(f"agent-{level}", _tuple(), level=level)

    def test_a0_needs_no_authorizer_because_a0_grants_nothing(self):
        """A0 is Observe. Minting an observer is not a grant of autonomy."""
        lic = self._auth().issue("agent-observe", _tuple(), level=0)
        assert lic.level == 0

    def test_uniimente_may_not_authorize_its_own_autonomy(self):
        auth = self._auth()
        with pytest.raises(ValueError, match="never creates authority"):
            auth.issue("agent-x", _tuple(), level=5, authorized_by="UNIIMENTE")

    def test_a_whitespace_authorizer_is_not_an_authorizer(self):
        auth = self._auth()
        with pytest.raises(ValueError, match="named authorizer"):
            auth.issue("agent-x", _tuple(), level=5, authorized_by="   ")

    def test_a9_stays_refused_even_with_a_named_authorizer(self):
        """Reserved human sovereignty is not a grant a human can make here."""
        auth = self._auth()
        with pytest.raises(ValueError, match="reserved human sovereignty"):
            auth.issue("agent-x", _tuple(), level=9, authorized_by="Alfonso Lopez")

    def test_the_authorizer_is_recorded_on_the_ledger_and_in_history(self):
        """An attributable grant, or the fix is only a speed bump."""
        ledger = EvidenceLedger("sha256:" + "0" * 64)
        auth = AutonomyAuthority(ledger)
        lic = auth.issue("agent-x", _tuple(), level=5, authorized_by="Alfonso Lopez")

        assert lic.history[0]["authorized_by"] == "Alfonso Lopez"
        issued = [r.payload for r in ledger.by_type("event")
                  if r.payload.get("type") == "autonomy.issued"]
        assert issued and issued[-1]["authorized_by"] == "Alfonso Lopez"

    def test_a_negative_level_is_refused(self):
        with pytest.raises(ValueError, match="may not be negative"):
            self._auth().issue("agent-x", _tuple(), level=-1)

    def test_the_evidence_path_is_still_the_only_way_to_earn_a_level(self):
        """The fix must not have replaced one bypass with another.

        An A0 license still cannot reach A1 without the full criteria set, so
        `authorized_by` buys a starting position and never a promotion.
        """
        auth = self._auth()
        lic = auth.issue("agent-x", _tuple(), level=0)
        unearned = PromotionEvidence(
            criteria={c: False for c in PROMOTION_CRITERIA},
            independent_verifier="none", founder_intervention_trend="flat")
        with pytest.raises(ValueError, match="promotion criteria unmet"):
            auth.promote(lic.license_id, unearned)
        assert auth._licenses[lic.license_id].level == 0
