"""Layer 2 tests: machine passports (Machine Identity and Authority)."""
import pytest
from datetime import datetime, timezone, timedelta

from identity.machine_passport import PassportRegistry, PassportError, NAMESPACE


@pytest.fixture
def registry():
    return PassportRegistry()


def make(registry, **kw):
    defaults = dict(kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
                    legal_principal="alfonso_lopez", declared_capabilities=["propose"],
                    budget_ceiling_usd=0.0, consequence_class="read_only")
    defaults.update(kw)
    return registry.issue(**defaults)


def test_issue_and_verify(registry):
    p = make(registry)
    assert p.passport_id.startswith(f"{NAMESPACE}/agent/")
    ok, why = registry.verify(p.passport_id)
    assert ok and why == "identity_verified"


def test_identity_is_not_authority(registry):
    p = make(registry)
    assert p.authority is None
    answers = registry.inspect(p.passport_id)
    assert "nothing by identity alone" in answers["what_it_may_do"]
    assert answers["which_entity_bears_liability"] == "alfonso_lopez"


def test_expired_passport_fails(registry):
    p = make(registry, ttl_seconds=1)
    future = datetime.now(timezone.utc) + timedelta(seconds=2)
    ok, why = registry.verify(p.passport_id, at=future)
    assert not ok and why == "expired"


def test_ttl_ceiling_enforced(registry):
    with pytest.raises(PassportError):
        make(registry, ttl_seconds=7200)  # registry max is 3600: identities are short-lived


def test_revocation_is_immediate(registry):
    p = make(registry)
    registry.revoke(p.passport_id, reason="compromise suspected", revoker="alfonso")
    ok, why = registry.verify(p.passport_id)
    assert not ok and "revoked" in why


def test_unknown_identity_fails(registry):
    ok, why = registry.verify(f"{NAMESPACE}/agent/does-not-exist")
    assert not ok and why == "unknown_identity"


def test_uniimente_never_legal_principal(registry):
    with pytest.raises(PassportError):
        make(registry, legal_principal="UNIIMENTE")


def test_every_kind_supported(registry):
    for kind in ("process", "agent", "workflow", "organ", "connector", "venture_cell"):
        p = make(registry, kind=kind)
        assert f"/{kind}/" in p.passport_id
    with pytest.raises(PassportError):
        make(registry, kind="sovereign_being")  # no such thing exists here
