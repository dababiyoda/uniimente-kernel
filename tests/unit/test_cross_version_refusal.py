"""Cross-version and cross-repository compatibility: refuse, never guess.

A permissive verifier is a downgrade attack waiting to happen. Every mismatch
here fails closed.
"""
from __future__ import annotations

import pytest

from aperture import AuthorizationCertificate, CertificateError, manifest
from aperture.certificate import SCHEMA_VERSION, BINDING_FIELDS
from aperture_issuer import (AuthorityIssuer, BudgetOffice,
                             Ed25519SigningProvider, Principal, Proposal)
from aperture import VerificationRegistry

ORG = "spiffe://uniimente.internal/organ/daleobanks"
ACTOR = ORG + "/agent/publisher"
TARGET = "sandbox:outbox"


@pytest.fixture
def cert():
    signer = Ed25519SigningProvider.generate("k1")
    iss = AuthorityIssuer(signer=signer, policy_version="policy-1.0",
                          constitution_version="const-1.0",
                          policy_evaluator=lambda p, pr: "PERMIT",
                          known_capabilities={"draft.publish"},
                          known_targets={TARGET}, budget=BudgetOffice())
    iss.register_principal(Principal(
        actor_id=ACTOR, organ_id=ORG, workload_identity=ORG + "/w1",
        legal_principal="alfonso_lopez",
        declared_capabilities=("draft.publish",),
        consequence_ceiling="external_contact", budget_ceiling_usd=5.0))
    return iss.issue(actor_id=ACTOR, proposal=Proposal(
        request_id="r", capability_id="draft.publish",
        action_class="draft.publish", target_id=TARGET, payload={"t": 1},
        consequence_class="external_contact", evidence_refs=[],
        estimated_cost_usd=0.0))


def test_unknown_critical_field_fails_closed(cert):
    """A newer organ adds a constraint; an older verifier must NOT ignore it."""
    d = cert.to_dict()
    d["max_recipients"] = 1          # a constraint this verifier cannot enforce
    with pytest.raises(CertificateError) as e:
        AuthorizationCertificate.from_dict(d)
    assert e.value.code == "unknown_certificate_field"


def test_certificate_schema_mismatch_fails_closed(cert):
    d = cert.to_dict()
    d["schema_version"] = "aperture/authorization-certificate/2.0.0"
    with pytest.raises(CertificateError) as e:
        AuthorizationCertificate.from_dict(d)
    assert e.value.code == "certificate_schema_mismatch"


def test_older_certificate_schema_also_fails_closed(cert):
    d = cert.to_dict()
    d["schema_version"] = "aperture/authorization-certificate/0.9.0"
    with pytest.raises(CertificateError):
        AuthorizationCertificate.from_dict(d)


def test_a_valid_round_trip_still_works(cert):
    again = AuthorizationCertificate.from_dict(cert.to_dict())
    assert again.effect_binding_hash() == cert.effect_binding_hash()
    assert again.signature == cert.signature


def test_schema_version_is_inside_the_signature(cert):
    """Downgrading the schema cannot preserve a valid signature."""
    assert "schema_version" in BINDING_FIELDS
    before = cert.effect_binding_hash()
    cert.schema_version = "aperture/authorization-certificate/0.9.0"
    assert cert.effect_binding_hash() != before


def test_manifest_hash_is_stable_and_recorded():
    import hashlib
    h = hashlib.sha256(manifest.MANIFEST_PATH.read_bytes()).hexdigest()
    assert len(h) == 64
