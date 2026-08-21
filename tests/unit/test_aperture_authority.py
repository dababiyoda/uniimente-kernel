"""Hostile conformance for the Reality Aperture.

Every defect verified against the three previous engines becomes a permanently
named regression test here. The test names carry the defect number so a future
reader can trace a test back to the finding that produced it.

Refusals are checked by REASON, not merely by "something was refused". A gate
that refuses for the wrong reason is a gate that will permit the same attack
once the incidental cause is removed.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from aperture import (Aperture, BINDING_FIELDS, CertificateError, KeyRevoked, LEGACY_INTEGRITY_CHECKED, LEGACY_UNVERIFIABLE, LegacyAuthorityRefused, LocalVeto, MIGRATION_ATTESTED, Presenter, VerificationRegistry, attest_migration, classify_legacy_record, refuse_as_authority)
from aperture_issuer import (ApprovalRecord, ApprovalRequired, AuthorityIssuer, BudgetOffice, Ed25519SigningProvider, Principal, Proposal, ScopeRefusal, SigningUnavailable, UnknownEntity)

POLICY = "policy-1.0"
CONSTITUTION = "const-1.0"
ORG = "spiffe://uniimente.internal/organ/daleobanks"
ACTOR = ORG + "/agent/publisher"
WORKLOAD = ORG + "/workload/publisher-v1"
TARGET = "sandbox:outbox"


def permit_policy(principal, proposal):
    if proposal.consequence_class == "irreversible":
        return "REQUIRE_HUMAN"
    return "PERMIT"


@pytest.fixture
def world():
    signer = Ed25519SigningProvider.generate("kernel-key-1")
    registry = VerificationRegistry()
    registry.register(signer.key_id, signer.public_key_hex())
    budget = BudgetOffice()
    issuer = AuthorityIssuer(
        signer=signer, policy_version=POLICY, constitution_version=CONSTITUTION,
        policy_evaluator=permit_policy,
        known_capabilities={"draft.publish", "funds.transfer"},
        known_targets={TARGET, "sandbox:second-outbox"},
        budget=budget)
    issuer.register_principal(Principal(
        actor_id=ACTOR, organ_id=ORG, workload_identity=WORKLOAD,
        legal_principal="alfonso_lopez",
        declared_capabilities=("draft.publish",),
        consequence_ceiling="external_contact", budget_ceiling_usd=5.0))
    aperture = Aperture(registry=registry, organ_id=ORG,
                        current_policy_version=POLICY,
                        current_constitution_version=CONSTITUTION,
                        veto=LocalVeto(engaged=False, reason=""), budget=budget)
    return {"signer": signer, "registry": registry, "issuer": issuer,
            "aperture": aperture, "budget": budget}


PAYLOAD = {"text": "hello governed world"}


def proposal(**kw):
    d = dict(request_id="req-1", capability_id="draft.publish",
             action_class="draft.publish", target_id=TARGET, payload=PAYLOAD,
             consequence_class="external_contact",
             evidence_refs=["sha256:" + "a" * 64], estimated_cost_usd=0.0,
             expected_outcome="draft queued")
    d.update(kw)
    return Proposal(**d)


def presenter(**kw):
    d = dict(actor_id=ACTOR, organ_id=ORG, workload_identity=WORKLOAD)
    d.update(kw)
    return Presenter(**d)


class Platform:
    """A fake external platform holding state INDEPENDENTLY of the executor.

    The executor writes; readback reads the platform's own state. The executor
    cannot fabricate the readback, which is the point: an executor's own claim
    is not evidence.
    """

    def __init__(self):
        self.posts = []

    def publish(self, text):
        self.posts.append(text)

    def state(self):
        return list(self.posts)


def run(w, cert, *, payload=PAYLOAD, pres=None, platform=None,
        expect=None):
    platform = platform or Platform()
    return w["aperture"].execute(
        cert, pres or presenter(), payload=payload,
        executor=lambda: platform.publish(payload["text"]),
        readback=platform.state,
        expected_state=expect or (lambda s: s == [payload["text"]]))


# ---------------------------------------------------------------- happy path

def test_valid_authorized_effect_commits(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    r = run(world, cert)
    assert r.status == "committed"
    assert r.readback_verified is True
    assert world["budget"].state(cert.budget_reservation_id) == "committed"


def test_certificate_binds_all_twenty_fields(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    assert len(BINDING_FIELDS) == 20
    assert set(cert.binding()) == set(BINDING_FIELDS)


def test_verification_needs_only_a_public_key(world):
    """An auditor with the registry alone can verify. No Kernel call."""
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    auditor = Aperture(registry=world["registry"], organ_id="auditor",
                       current_policy_version=POLICY,
                       current_constitution_version=CONSTITUTION)
    auditor.verify(cert)          # no exception


def test_verification_registry_cannot_sign(world):
    """Verification capability is not signing capability."""
    reg = world["registry"]
    assert not hasattr(reg, "sign")
    assert not any("sign" in a for a in dir(reg) if not a.startswith("_"))


# ------------------------------------------------- verified defect regressions

def test_defect_1_capability_not_held_is_refused(world):
    """REGRESSION - main permitted an actor holding only draft.publish to
    execute funds.transfer and reach state='recorded'."""
    with pytest.raises(ScopeRefusal) as e:
        world["issuer"].issue(
            actor_id=ACTOR,
            proposal=proposal(capability_id="funds.transfer",
                              action_class="funds.transfer"))
    assert e.value.code == "capability_not_held"


def test_defect_2_require_human_cannot_become_permission(world):
    """REGRESSION - main discarded a commit-time REQUIRE_HUMAN because it
    refused only on DENY. Here REQUIRE_HUMAN raises and has no path to a
    signature without an approval record.

    The principal's ceiling is raised first so that the consequence-ceiling
    check (which correctly fires earlier) does not mask the behaviour under
    test. That ordering is itself asserted by
    test_consequence_ceiling_is_enforced_at_issuance.
    """
    world["issuer"]._principals[ACTOR].consequence_ceiling = "irreversible"
    with pytest.raises(ApprovalRequired) as e:
        world["issuer"].issue(
            actor_id=ACTOR,
            proposal=proposal(consequence_class="irreversible"))
    assert e.value.code == "approval_required"


def test_defect_2c_approved_human_decision_does_issue(world):
    """The other half of defect 2: a real approval must actually work, or the
    refusal above would be proving nothing but a broken code path."""
    world["issuer"]._principals[ACTOR].consequence_ceiling = "irreversible"
    ok = ApprovalRecord(approval_id="ap-ok", request_id="req-1",
                        approver_id="alfonso_lopez", granted=True,
                        issued_at="2026-07-27T00:00:00Z")
    cert = world["issuer"].issue(
        actor_id=ACTOR, proposal=proposal(consequence_class="irreversible"),
        approval=ok)
    assert cert.consequence_class == "irreversible"
    assert cert.signature


def test_defect_2d_human_refusal_is_honoured(world):
    world["issuer"]._principals[ACTOR].consequence_ceiling = "irreversible"
    no = ApprovalRecord(approval_id="ap-no", request_id="req-1",
                        approver_id="alfonso_lopez", granted=False,
                        issued_at="2026-07-27T00:00:00Z")
    from aperture_issuer import PolicyRefusal
    with pytest.raises(PolicyRefusal) as e:
        world["issuer"].issue(
            actor_id=ACTOR, proposal=proposal(consequence_class="irreversible"),
            approval=no)
    assert e.value.code == "human_refused"


def test_defect_2b_approval_must_be_bound_to_this_request(world):
    """An approval for another request is not an approval for this one."""
    issuer = world["issuer"]
    issuer._principals[ACTOR].consequence_ceiling = "irreversible"
    wrong = ApprovalRecord(approval_id="ap-1", request_id="some-other-request",
                           approver_id="alfonso_lopez", granted=True,
                           issued_at="2026-07-27T00:00:00Z")
    with pytest.raises(ApprovalRequired) as e:
        issuer.issue(actor_id=ACTOR,
                     proposal=proposal(consequence_class="irreversible"),
                     approval=wrong)
    assert e.value.code == "approval_request_mismatch"


def test_defect_3_certificate_is_not_a_bearer_token(world):
    """REGRESSION - main let a grant issued to actor A be redeemed by actor B.
    actor_id, organ_id and workload_identity are signed fields and are compared
    against the presenter."""
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    r = run(world, cert, pres=presenter(actor_id=ORG + "/agent/someone-else"))
    assert r.status == "actor_mismatch"


def test_defect_3b_cross_organ_use_is_refused(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    r = run(world, cert, pres=presenter(organ_id="spiffe://.../organ/wmi"))
    assert r.status == "organ_mismatch"


def test_defect_3c_cross_workload_use_is_refused(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    r = run(world, cert, pres=presenter(workload_identity=WORKLOAD + "-v2"))
    assert r.status == "workload_mismatch"


def test_defect_4_unknown_capability_is_refused(world):
    """REGRESSION - neither main nor PR21 validated the capability."""
    with pytest.raises(UnknownEntity) as e:
        world["issuer"].issue(
            actor_id=ACTOR, proposal=proposal(capability_id="nonexistent.cap"))
    assert e.value.code == "unknown_capability"


def test_defect_4b_unknown_target_is_refused(world):
    """REGRESSION - neither main nor PR21 validated the target."""
    with pytest.raises(UnknownEntity) as e:
        world["issuer"].issue(
            actor_id=ACTOR, proposal=proposal(target_id="gopher://unknown.invalid/x"))
    assert e.value.code == "unknown_target"


def test_defect_5_local_veto_actually_blocks_execution(world):
    """REGRESSION - the phase7 SDK KillSwitch was written to but never read,
    so a disarmed switch did not stop anything. Here the veto is READ before
    the executor runs."""
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    world["aperture"].veto.engage("operator pulled the cord")
    platform = Platform()
    r = run(world, cert, platform=platform)
    assert r.status == "local_veto"
    assert platform.state() == []            # nothing happened externally
    assert world["budget"].state(cert.budget_reservation_id) == "released"


def test_defect_5b_valid_authority_does_not_override_local_veto(world):
    """The constitutional invariant, stated as a test."""
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    world["aperture"].verify(cert, presenter())      # authority IS valid
    world["aperture"].veto.engage("degraded mode")
    assert run(world, cert).status == "local_veto"


def test_defect_6_legacy_hmac_cannot_authorize_a_new_effect(world):
    """REGRESSION - the HMAC trust model let verification capability imply
    forging power. Legacy records are preserved but never authorize."""
    rec = classify_legacy_record("w-1", {"a": 1}, "hmac-sha256:deadbeef",
                                 shared_secret=b"uniimente-dev-witness-key")
    assert rec.classification in (LEGACY_INTEGRITY_CHECKED, LEGACY_UNVERIFIABLE)
    assert rec.authorizes_new_effect() is False
    with pytest.raises(LegacyAuthorityRefused) as e:
        refuse_as_authority(rec)
    assert e.value.code == "legacy_authority_refused"


def test_defect_6b_integrity_check_is_not_attribution(world):
    """A passing HMAC check proves consistency, never who produced it."""
    secret = b"historical-secret"
    from aperture.certificate import canonical_json
    import hmac, hashlib
    body = {"action": "publish", "n": 1}
    sig = "hmac-sha256:" + hmac.new(secret, canonical_json(body),
                                    hashlib.sha256).hexdigest()
    rec = classify_legacy_record("w-2", body, sig, shared_secret=secret)
    assert rec.integrity_checked is True
    assert rec.classification == LEGACY_INTEGRITY_CHECKED
    assert "NOT signer attribution" in rec.note
    assert rec.authorizes_new_effect() is False


def test_defect_6c_migration_attestation_does_not_claim_original_witness(world):
    rec = classify_legacy_record("w-3", {"x": 1}, "hmac-sha256:00")
    assert rec.classification == LEGACY_UNVERIFIABLE
    rec = attest_migration(rec, reviewer_id="alfonso_lopez",
                           statement="reviewed and admitted to the record")
    assert rec.classification == MIGRATION_ATTESTED
    assert rec.attestation["claims_original_witness"] is False
    assert rec.attestation["confers_authority"] is False
    assert rec.authorizes_new_effect() is False


def test_defect_7_no_hardcoded_development_signing_key(world, monkeypatch):
    """REGRESSION - the previous signer fell back to a hardcoded literal.
    Missing signing infrastructure must fail closed."""
    monkeypatch.delenv("UNIIMENTE_APERTURE_SIGNING_KEY_HEX", raising=False)
    with pytest.raises(SigningUnavailable) as e:
        Ed25519SigningProvider.from_env()
    assert e.value.code == "signing_unavailable"


# ------------------------------------------------------- effect binding

@pytest.mark.parametrize("field_name,new_value", [
    ("actor_id", "spiffe://evil/agent"),
    ("organ_id", "spiffe://evil/organ"),
    ("workload_identity", "spiffe://evil/workload"),
    ("legal_principal", "someone_else"),
    ("capability_id", "funds.transfer"),
    ("action_class", "funds.transfer"),
    ("target_id", "https://evil.example/exfil"),
    ("payload_hash", "sha256:" + "0" * 64),
    ("consequence_class", "irreversible"),
    ("policy_version", "policy-9.9"),
    ("constitution_version", "const-9.9"),
    ("evidence_set_hash", "sha256:" + "0" * 64),
    ("consequence_ceiling", 1e9),
    ("use_limit", 99),
    ("expires_at", "2099-01-01T00:00:00Z"),
])
def test_any_binding_field_mutation_breaks_the_signature(world, field_name, new_value):
    """Tampering with ANY signed field invalidates the certificate.

    This is the property that makes the twenty-field binding meaningful: there
    is no field an attacker can vary while keeping a valid signature.
    """
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    setattr(cert, field_name, new_value)
    r = run(world, cert)
    assert r.status == "bad_signature", (
        f"mutating {field_name} did not invalidate the certificate")


def test_payload_mutation_at_execution_is_refused(world):
    """The payload handed to the executor must be the authorized one."""
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    r = run(world, cert, payload={"text": "exfiltrate the credential store"})
    assert r.status == "payload_mismatch"


# ------------------------------------------------------- lifecycle

def test_replay_is_refused_after_the_use_limit(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    assert run(world, cert).status == "committed"
    assert run(world, cert).status == "replay"


def test_expired_certificate_is_refused(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    later = datetime.now(timezone.utc) + timedelta(hours=2)
    r = world["aperture"].execute(
        cert, presenter(), payload=PAYLOAD, executor=lambda: None,
        readback=lambda: [], expected_state=lambda s: True, now=later)
    assert r.status == "certificate_expired"


def test_policy_version_drift_requires_reauthorization(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    world["aperture"].current_policy_version = "policy-2.0"
    assert run(world, cert).status == "policy_version_drift"


def test_constitution_version_drift_requires_reauthorization(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    world["aperture"].current_constitution_version = "const-2.0"
    assert run(world, cert).status == "constitution_version_drift"


def test_key_revocation_after_issuance_refuses(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    world["registry"].revoke(cert.key_id, reason="suspected compromise")
    with pytest.raises(KeyRevoked):
        world["aperture"].verify(cert, presenter())


def test_certificate_from_an_unregistered_key_is_refused(world):
    """A rogue signer with a perfectly valid Ed25519 key is still not authority."""
    rogue = Ed25519SigningProvider.generate("rogue-key")
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    cert.key_id = rogue.key_id
    cert.signature = rogue.sign(cert.signing_input())
    from aperture import UnknownKey
    with pytest.raises(UnknownKey):
        world["aperture"].verify(cert, presenter())


def test_unregistered_actor_is_refused(world):
    with pytest.raises(UnknownEntity) as e:
        world["issuer"].issue(actor_id="spiffe://nobody", proposal=proposal())
    assert e.value.code == "unknown_actor"


def test_consequence_ceiling_is_enforced_at_issuance(world):
    """A principal ceilinged at external_contact cannot reach financial."""
    world["issuer"].known_capabilities.add("draft.publish")
    with pytest.raises(ScopeRefusal) as e:
        world["issuer"].issue(
            actor_id=ACTOR, proposal=proposal(consequence_class="financial"))
    assert e.value.code == "consequence_ceiling_exceeded"


# ------------------------------------------------------- budget + readback

def test_budget_is_released_on_refusal(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    world["aperture"].veto.engage("stop")
    run(world, cert)
    assert world["budget"].state(cert.budget_reservation_id) == "released"


def test_budget_is_released_when_the_executor_fails(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())

    def boom():
        raise RuntimeError("platform exploded")
    r = world["aperture"].execute(
        cert, presenter(), payload=PAYLOAD, executor=boom,
        readback=lambda: [], expected_state=lambda s: True)
    assert r.status == "executor_failed"
    assert world["budget"].state(cert.budget_reservation_id) == "released"


def test_executor_cannot_fabricate_the_receipt(world):
    """The executor claims success; independent readback disagrees; refused."""
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    platform = Platform()
    r = world["aperture"].execute(
        cert, presenter(), payload=PAYLOAD,
        executor=lambda: None,                  # claims to work, writes nothing
        readback=platform.state,
        expected_state=lambda s: s == [PAYLOAD["text"]])
    assert r.status == "reconciliation_mismatch"
    assert r.readback_verified is False
    assert world["budget"].state(cert.budget_reservation_id) == "released"


def test_readback_mismatch_is_recorded_not_silently_permitted(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    platform = Platform()

    def wrong():
        platform.publish("something completely different")
    r = world["aperture"].execute(
        cert, presenter(), payload=PAYLOAD, executor=wrong,
        readback=platform.state,
        expected_state=lambda s: s == [PAYLOAD["text"]])
    assert r.status == "reconciliation_mismatch"
    assert r.observed_state == ["something completely different"]


# ------------------------------------------------------- veto discipline

def test_local_veto_starts_engaged_by_default(world):
    v = LocalVeto()
    assert v.engaged is True


def test_releasing_a_veto_requires_a_named_operator(world):
    v = LocalVeto()
    with pytest.raises(CertificateError) as e:
        v.release("all clear", authorized_by="")
    assert e.value.code == "veto_release_unattributed"


def test_kernel_cannot_reach_the_local_veto(world):
    """The Aperture owns its veto; the issuer has no reference to it."""
    assert not hasattr(world["issuer"], "veto")
    assert world["aperture"].veto is not None
