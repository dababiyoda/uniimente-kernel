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
        lic = auth.promote(lic.license_id, _evidence())       # licenses are returned as copies
        assert lic.level == 5
        rec = [r for r in auth.ledger.by_type("event")
               if r.payload["type"] == "autonomy.promoted"][-1]
        assert rec.payload["verifier"] == "external_auditor_01"

    def test_ladder_climbs_to_a8_and_stops(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=0)
        for target in range(1, MAX_GRANTABLE + 1):
            lic = auth.promote(lic.license_id, _evidence())
            assert lic.level == target
        assert lic.level == 8
        with pytest.raises(ValueError):                  # A9 reserved, unreachable
            auth.promote(lic.license_id, _evidence())


class TestRegression:
    def test_severe_failure_zeroes_and_deactivates_immediately(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=7, authorized_by="Alfonso Lopez")
        lic = auth.regress(lic.license_id, failure_class="harm", detail="unforeseen physical risk")
        assert lic.level == 0 and not lic.active
        assert auth.level_of("agent-1", _tuple()) == 0   # inactive reads as zero

    def test_non_severe_failure_steps_down_one(self):
        auth = _authority()
        lic = auth.issue("agent-1", _tuple(), level=5, authorized_by="Alfonso Lopez")
        lic = auth.regress(lic.license_id, failure_class="sloppy_reconciliation", detail="late records")
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
        lic = auth.renew(lic.license_id, _evidence())
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


# --- #87 follow-up: the authorizer as read, the level as an int, the ledger first, copies out ----------
# Bypass review of 1ad75be (secscratch attacks/bypass/test_bypass_autonomy.py): each case minted or
# kept a live license on 0c4849b.

class TestAuthorizerLevelLedgerAndCopies:
    def _auth(self):
        return AutonomyAuthority(EvidenceLedger("sha256:" + "0" * 64))

    def _events(self, auth):
        return [r.payload["type"] for r in auth.ledger.by_type("event")]

    @pytest.mark.parametrize("name", [
        "uniimente", "Uniimente", "UNIIMENTE\u200b", "\u200bUNI\u200dIMENTE",
        "\uff35\uff2e\uff29\uff29\uff2d\uff25\uff2e\uff34\uff25",      # fullwidth
        "UN\u0406IM\u0415NTE",                                                 # Cyrillic I and E
        "U.N.I.I.M.E.N.T.E", "UNIIMENTE Kernel", "the uniimente egregore",
        "spiffe://uniimente.internal/kernel/action-gateway",
    ])
    def test_uniimente_may_not_authorize_its_own_autonomy_however_it_is_spelled(self, name):
        auth = self._auth()
        with pytest.raises(ValueError, match="never creates authority"):
            auth.issue("agent-1", _tuple(), level=8, authorized_by=name)
        assert auth.level_of("agent-1", _tuple()) == 0 and "autonomy.issued" not in self._events(auth)

    @pytest.mark.parametrize("name", ["agent-1", "Agent-1", "AGENT-1 (self)", "agent\u200b-1", "agent 1",
                                      "agent1", "\uff41gent-1"])
    def test_the_subject_may_not_authorize_its_own_autonomy(self, name):
        auth = self._auth()
        with pytest.raises(ValueError, match="subject may not authorize"):
            auth.issue("agent-1", _tuple(), level=5, authorized_by=name)
        assert auth.level_of("agent-1", _tuple()) == 0

    @pytest.mark.parametrize("name", ["spiffe://example.org/ops/agent", "https://example.com/approver"])
    def test_a_workload_uri_is_not_a_named_human(self, name):
        with pytest.raises(ValueError, match="workload identity"):
            self._auth().issue("agent-1", _tuple(), level=5, authorized_by=name)

    @pytest.mark.parametrize("name", [None, "", "\u200b\u2063", "...", 42, b"Alfonso Lopez"])
    def test_an_authorizer_with_no_readable_name_is_not_an_authorizer(self, name):
        with pytest.raises(ValueError, match="named authorizer"):
            self._auth().issue("agent-1", _tuple(), level=5, authorized_by=name)

    def test_a_human_authorizer_who_merely_shares_a_letter_with_the_subject_is_accepted(self):
        lic = self._auth().issue("a", _tuple(), level=2, authorized_by="Alfonso Lopez")
        assert lic.level == 2

    @pytest.mark.parametrize("level", [float("nan"), 8.0, 1.5, True, "8", None])
    def test_a_level_that_is_not_an_int_is_refused_before_anything_is_stored(self, level):
        auth = self._auth()
        with pytest.raises(ValueError, match="must be an integer"):
            auth.issue("agent-1", _tuple(), level=level)
        assert auth.level_of("agent-1", _tuple()) == 0 and self._events(auth) == []

    def test_a_ledger_that_refuses_the_issue_leaves_no_license(self):
        auth = self._auth()
        auth.ledger.close()
        with pytest.raises(Exception, match="writer"):
            auth.issue("agent-1", _tuple(), level=8, authorized_by="Alfonso Lopez")
        assert auth.level_of("agent-1", _tuple()) == 0 and auth._licenses == {}

    def test_a_ledger_that_refuses_a_promotion_or_renewal_leaves_the_level(self):
        auth = self._auth()
        lic = auth.issue("agent-1", _tuple(), level=3, authorized_by="Alfonso Lopez")
        auth.ledger.close()
        with pytest.raises(Exception, match="writer"):
            auth.promote(lic.license_id, _evidence())
        assert auth.level_of("agent-1", _tuple()) == 3
        auth._licenses[lic.license_id].active = False           # as after a recorded severe regression
        with pytest.raises(Exception, match="writer"):
            auth.renew(lic.license_id, _evidence())
        assert auth.level_of("agent-1", _tuple()) == 0 and not auth._licenses[lic.license_id].active

    def test_a_regression_the_ledger_refuses_still_drops_autonomy_to_the_floor(self):
        auth = self._auth()
        lic = auth.issue("agent-1", _tuple(), level=6, authorized_by="Alfonso Lopez")
        auth.ledger.close()
        with pytest.raises(Exception, match="writer"):
            auth.regress(lic.license_id, failure_class="sloppy", detail="late records")
        assert auth.level_of("agent-1", _tuple()) == 0 and not auth._licenses[lic.license_id].active

    def test_a_returned_license_is_a_copy(self):
        auth = self._auth()
        lic = auth.issue("agent-1", _tuple(), level=0)
        lic.level, lic.active = 8, True
        lic.history.clear()
        lic.tuple.budget_usd = 1e9
        assert auth.level_of("agent-1", _tuple()) == 0
        stored = auth._licenses[lic.license_id]
        assert stored.level == 0 and stored.history and stored.tuple.budget_usd == 25.0
        promoted = auth.promote(lic.license_id, _evidence())
        promoted.level = 8
        assert auth.level_of("agent-1", _tuple()) == 1
        assert "autonomy.promoted" in self._events(auth)

    def test_the_caller_cannot_edit_the_stored_tuple_through_its_own_object(self):
        auth = self._auth()
        t = _tuple()
        lic = auth.issue("agent-1", t, level=2, authorized_by="Alfonso Lopez")
        t.budget_usd = 1e9
        assert auth._licenses[lic.license_id].tuple.budget_usd == 25.0

    def test_the_closure_probes_use_a_synthetic_authorizer_not_the_founders_name(self, monkeypatch):
        from closure.kernel_registry import build_registry
        seen = []
        real = AutonomyAuthority.issue

        def spy(self, subject, tuple_, level=0, *, authorized_by=None):
            seen.append(authorized_by)
            return real(self, subject, tuple_, level, authorized_by=authorized_by)

        monkeypatch.setattr(AutonomyAuthority, "issue", spy)
        assert build_registry().verify_module("autonomy").complete
        named = [who for who in seen if who]
        assert named and all("synthetic" in who and "alfonso" not in who.lower() for who in named)
