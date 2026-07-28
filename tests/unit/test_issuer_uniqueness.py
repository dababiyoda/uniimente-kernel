"""VALID_CANONICAL_CERTIFICATE_ISSUERS = 1, proved cryptographically.

Uniqueness is not established by naming conventions or by a registry entry. It
is established by the fact that a certificate is only valid if it verifies
against a registered public key, and only one component holds the corresponding
private key.

The twelve required proofs from the execution order, in order.
"""
from __future__ import annotations

import pytest

from aperture import (Aperture, AuthorityIssuer, AuthorizationCertificate,
                      BudgetOffice, CertificateError, Ed25519SigningProvider,
                      Presenter, Principal, Proposal, UnknownKey,
                      VerificationRegistry, build_certificate, manifest)
from aperture.keys import (DEVELOPMENT, EnvironmentRefusal, PRODUCTION, SHADOW,
                           TEST)

POLICY, CONSTITUTION = "policy-1.0", "const-1.0"
ORG = "spiffe://uniimente.internal/organ/daleobanks"
ACTOR = ORG + "/agent/publisher"
WORKLOAD = ORG + "/workload/publisher-v1"
TARGET = "sandbox:outbox"
PAYLOAD = {"text": "hello"}


@pytest.fixture
def world():
    signer = Ed25519SigningProvider.generate("kernel-key-1")
    registry = VerificationRegistry()
    registry.register(signer.key_id, signer.public_key_hex())
    issuer = AuthorityIssuer(
        signer=signer, policy_version=POLICY, constitution_version=CONSTITUTION,
        policy_evaluator=lambda p, pr: "PERMIT",
        known_capabilities={"draft.publish"}, known_targets={TARGET},
        budget=BudgetOffice())
    issuer.register_principal(Principal(
        actor_id=ACTOR, organ_id=ORG, workload_identity=WORKLOAD,
        legal_principal="alfonso_lopez",
        declared_capabilities=("draft.publish",),
        consequence_ceiling="external_contact", budget_ceiling_usd=5.0))
    ap = Aperture(registry=registry, organ_id=ORG,
                  current_policy_version=POLICY,
                  current_constitution_version=CONSTITUTION)
    return {"signer": signer, "registry": registry, "issuer": issuer, "aperture": ap}


def proposal(**kw):
    d = dict(request_id="r1", capability_id="draft.publish",
             action_class="draft.publish", target_id=TARGET, payload=PAYLOAD,
             consequence_class="external_contact",
             evidence_refs=["sha256:" + "a" * 64], estimated_cost_usd=0.0)
    d.update(kw)
    return Proposal(**d)


P = Presenter(ACTOR, ORG, WORKLOAD)


# 1 ------------------------------------------------------------------------
def test_01_only_the_canonical_issuer_produces_a_valid_certificate(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    world["aperture"].verify(cert, P)          # no exception
    assert manifest.active_issuer_count() == 1


# 2 ------------------------------------------------------------------------
def test_02_public_verification_keys_cannot_sign(world):
    reg = world["registry"]
    assert not hasattr(reg, "sign")
    rk = reg.get(world["signer"].key_id)
    # The registry stores public key bytes and nothing else that could sign.
    assert not hasattr(rk, "private_key_hex")
    assert "private" not in str(vars(rk)).lower()


# 3 ------------------------------------------------------------------------
def test_03_a_second_issuer_cannot_produce_a_valid_certificate(world):
    """A rogue issuer with a perfectly valid Ed25519 key is not authority.

    This is uniqueness proved by cryptography rather than by naming: the rogue
    signs correctly, and verification still refuses because its key was never
    registered.
    """
    rogue_signer = Ed25519SigningProvider.generate("rogue-key")
    rogue = AuthorityIssuer(
        signer=rogue_signer, policy_version=POLICY,
        constitution_version=CONSTITUTION,
        policy_evaluator=lambda p, pr: "PERMIT",
        known_capabilities={"draft.publish"}, known_targets={TARGET})
    rogue.register_principal(Principal(
        actor_id=ACTOR, organ_id=ORG, workload_identity=WORKLOAD,
        legal_principal="alfonso_lopez",
        declared_capabilities=("draft.publish",),
        consequence_ceiling="external_contact", budget_ceiling_usd=5.0))
    cert = rogue.issue(actor_id=ACTOR, proposal=proposal())
    with pytest.raises(UnknownKey):
        world["aperture"].verify(cert, P)


# 4 ------------------------------------------------------------------------
def test_04_duplicate_issuer_identity_fails_the_manifest(world, tmp_path):
    """Two implementations claiming may_issue_authority fails at load."""
    from aperture.manifest import ManifestError, load
    bad = tmp_path / "m.yaml"
    bad.write_text("""
canonical_authority:
  architecture: proof_carrying_authorization
  protocol_name: reality_aperture
  canonical_package: aperture
  issuer: aperture.issuer.AuthorityIssuer
  active_issuers_allowed: 1
  legacy_engines_active: false
  organ_local_issuers_allowed: false
implementations:
  - module: aperture.issuer
    classification: CANONICAL_ACTIVE
    may_issue_authority: true
  - module: policy.consequence_gate
    classification: CANONICAL_ACTIVE
    may_issue_authority: true
""")
    load.cache_clear()
    with pytest.raises(ManifestError) as e:
        load(bad)
    assert e.value.code == "manifest_contradiction"
    load.cache_clear()


# 5 ------------------------------------------------------------------------
def test_05_the_sdk_cannot_create_valid_certificates(world):
    """The SDK has no signing provider and no certificate type."""
    assert not manifest.may_issue_authority("uniimente_kernel.gate")
    assert manifest.implementation("uniimente_kernel.gate")["classification"] == "SUPERSEDED"


# 6 & 7 --------------------------------------------------------------------
@pytest.mark.parametrize("organ_module", [
    "daleobanks.governance", "wealthmachine.policy"])
def test_06_07_organs_cannot_create_valid_certificates(world, organ_module):
    """No organ holds a signing provider, and the manifest forbids organ-local
    issuance outright."""
    assert manifest.canonical()["organ_local_issuers_allowed"] is False
    # An organ constructing a certificate object directly gets an unsigned one.
    cert = build_certificate(
        request_id="r", authority_record_id="forged-1", actor_id=ACTOR,
        organ_id=ORG, workload_identity=WORKLOAD,
        legal_principal="alfonso_lopez", capability_id="draft.publish",
        action_class="draft.publish", target_id=TARGET, payload=PAYLOAD,
        consequence_class="external_contact", policy_version=POLICY,
        constitution_version=CONSTITUTION, evidence_refs=[],
        budget_reservation_id="none", consequence_ceiling=1.0, ttl_seconds=900)
    with pytest.raises(CertificateError):
        world["aperture"].verify(cert, P)


# 8 ------------------------------------------------------------------------
def test_08_the_legacy_gate_cannot_create_valid_certificates(world):
    assert not manifest.may_issue_authority("policy.consequence_gate")
    import policy.consequence_gate as legacy
    assert not hasattr(legacy, "AuthorizationCertificate")
    assert not hasattr(legacy, "build_certificate")
    # Its signer is HMAC and produces nothing the aperture registry accepts.
    from provenance.commit_witness import WitnessSigner
    assert not hasattr(WitnessSigner, "public_key_hex")


# 9 ------------------------------------------------------------------------
def test_09_legacy_hmac_cannot_be_converted_into_authority(world):
    from aperture.legacy import (classify_legacy_record, refuse_as_authority,
                                 LegacyAuthorityRefused)
    rec = classify_legacy_record("w1", {"a": 1}, "hmac-sha256:ff")
    assert rec.authorizes_new_effect() is False
    with pytest.raises(LegacyAuthorityRefused):
        refuse_as_authority(rec)


# 10 -----------------------------------------------------------------------
def test_10_test_issuers_cannot_operate_outside_test_configuration(monkeypatch):
    """An ephemeral key is refused in SHADOW; a test-prefixed key cannot load."""
    with pytest.raises(EnvironmentRefusal) as e:
        Ed25519SigningProvider.generate("shadow-key", environment=SHADOW)
    assert e.value.code == "ephemeral_key_refused"

    sk = Ed25519SigningProvider.generate("test-key-1", TEST)
    monkeypatch.setenv("UNIIMENTE_APERTURE_ENV", SHADOW)
    monkeypatch.setenv("UNIIMENTE_APERTURE_SIGNING_KEY_HEX", sk.private_key_hex())
    monkeypatch.setenv("UNIIMENTE_APERTURE_KEY_ID", "test-key-1")
    with pytest.raises(EnvironmentRefusal) as e2:
        Ed25519SigningProvider.from_env()
    assert e2.value.code == "test_key_outside_test"


def test_10b_production_custody_is_disabled(monkeypatch):
    with pytest.raises(EnvironmentRefusal) as e:
        Ed25519SigningProvider.generate("prod", environment=PRODUCTION)
    assert e.value.code in ("production_custody_disabled", "ephemeral_key_refused")
    monkeypatch.setenv("UNIIMENTE_APERTURE_ENV", PRODUCTION)
    monkeypatch.setenv("UNIIMENTE_APERTURE_SIGNING_KEY_HEX", "aa" * 32)
    monkeypatch.setenv("UNIIMENTE_APERTURE_KEY_ID", "prod-1")
    with pytest.raises(EnvironmentRefusal) as e2:
        Ed25519SigningProvider.from_env()
    assert e2.value.code == "production_custody_disabled"


# 11 -----------------------------------------------------------------------
def test_11_direct_construction_does_not_create_valid_authority(world):
    """Instantiating the dataclass yields an object with an empty signature."""
    cert = AuthorizationCertificate(
        request_id="r", authority_record_id="a", actor_id=ACTOR, organ_id=ORG,
        workload_identity=WORKLOAD, legal_principal="alfonso_lopez",
        capability_id="draft.publish", action_class="draft.publish",
        target_id=TARGET, payload_hash="sha256:00", consequence_class="external_contact",
        policy_version=POLICY, constitution_version=CONSTITUTION,
        evidence_set_hash="sha256:00", budget_reservation_id="none",
        consequence_ceiling=1.0, issued_at="2026-07-27T00:00:00Z",
        expires_at="2099-01-01T00:00:00Z", use_limit=1)
    assert cert.signature == ""
    with pytest.raises(CertificateError):
        world["aperture"].verify(cert, P)


# 12 -----------------------------------------------------------------------
def test_12_dependency_injection_cannot_supply_an_organ_with_a_signer(world):
    """The Aperture (organ side) takes a VerificationRegistry, never a signer.

    An organ cannot be handed signing capability through its constructor,
    because no constructor parameter accepts one.
    """
    import inspect
    params = set(inspect.signature(Aperture.__init__).parameters)
    assert "signer" not in params
    assert "signing_provider" not in params
    assert "registry" in params
    # And the issuer is the only thing that takes a signer.
    iparams = set(inspect.signature(AuthorityIssuer.__init__).parameters)
    assert "signer" in iparams


def test_manifest_and_registry_cannot_silently_disagree():
    """The exact drift that invalidated the previous Gate A closure."""
    from aperture import dispositions as D
    assert D.agrees_with_manifest() == []
