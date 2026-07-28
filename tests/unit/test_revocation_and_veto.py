"""Revocation behaviour and local-veto timing.

Two properties are proved here that the sandbox architecture did not have.

REVOCATION. Offline verification is the aperture's strength and its hardest
problem: an effector that never calls home cannot learn that authority was
withdrawn. The hybrid model bounds this. Staleness is permissive for
low-consequence classes and fail-closed at the top.

VETO TIMING. The veto is read at three points, the last of which is inside an
execution lease with the adapter invocation, so it cannot flip between the final
check and the effect.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from aperture import (Aperture, LocalVeto, Presenter, VerificationRegistry, manifest)
from aperture_issuer import (AuthorityIssuer, BudgetOffice, Ed25519SigningProvider, Principal, Proposal)
from aperture_issuer import RevocationAuthority
from aperture.revocation import (RevocationEscalation,
                                 RevocationRefusal, RevocationState,
                                 StaleRevocationState, max_ttl_for)

POLICY, CONSTITUTION = "policy-1.0", "const-1.0"
ORG = "spiffe://uniimente.internal/organ/daleobanks"
ACTOR = ORG + "/agent/publisher"
WORKLOAD = ORG + "/workload/publisher-v1"
TARGET = "sandbox:outbox"
PAYLOAD = {"text": "hello"}
P = Presenter(ACTOR, ORG, WORKLOAD)


@pytest.fixture
def world():
    signer = Ed25519SigningProvider.generate("kernel-key-1")
    registry = VerificationRegistry()
    registry.register(signer.key_id, signer.public_key_hex())
    budget = BudgetOffice()
    issuer = AuthorityIssuer(
        signer=signer, policy_version=POLICY, constitution_version=CONSTITUTION,
        policy_evaluator=lambda p, pr: "PERMIT",
        known_capabilities={"draft.publish"}, known_targets={TARGET},
        budget=budget)
    issuer.register_principal(Principal(
        actor_id=ACTOR, organ_id=ORG, workload_identity=WORKLOAD,
        legal_principal="alfonso_lopez",
        declared_capabilities=("draft.publish",),
        consequence_ceiling="irreversible", budget_ceiling_usd=5.0))
    ra = RevocationAuthority(signer)
    state = RevocationState(registry)
    ap = Aperture(registry=registry, organ_id=ORG,
                  current_policy_version=POLICY,
                  current_constitution_version=CONSTITUTION,
                  veto=LocalVeto(engaged=False, reason=""), budget=budget,
                  revocation=state)
    return {"signer": signer, "registry": registry, "issuer": issuer,
            "aperture": ap, "ra": ra, "state": state, "budget": budget}


def proposal(**kw):
    d = dict(request_id="r1", capability_id="draft.publish",
             action_class="draft.publish", target_id=TARGET, payload=PAYLOAD,
             consequence_class="external_contact",
             evidence_refs=["sha256:" + "a" * 64], estimated_cost_usd=0.0)
    d.update(kw)
    return Proposal(**d)


class Platform:
    def __init__(self):
        self.posts = []

    def publish(self, t):
        self.posts.append(t)

    def state(self):
        return list(self.posts)


def run(w, cert, platform=None, pres=P, now=None):
    platform = platform or Platform()
    return w["aperture"].execute(
        cert, pres, payload=PAYLOAD,
        executor=lambda: platform.publish(PAYLOAD["text"]),
        readback=platform.state,
        expected_state=lambda s: s == [PAYLOAD["text"]], now=now)


# ------------------------------------------------------------ policy shape

def test_every_consequence_class_has_a_revocation_policy():
    for cls in ("internal_read", "internal_write", "external_contact",
                "financial", "irreversible"):
        p = manifest.revocation_policy_for(cls)
        assert "max_certificate_ttl_seconds" in p
        assert "maximum_staleness_seconds" in p
        assert "on_stale_or_unavailable" in p


def test_high_consequence_classes_fail_closed_on_stale_state():
    assert manifest.revocation_policy_for("external_contact")["on_stale_or_unavailable"] == "refuse"
    assert manifest.revocation_policy_for("financial")["on_stale_or_unavailable"] == "refuse"
    assert manifest.revocation_policy_for("irreversible")["on_stale_or_unavailable"] == "human_escalation"


def test_ttl_shrinks_as_consequence_grows():
    ttls = [max_ttl_for(c) for c in ("internal_read", "internal_write",
                                     "external_contact", "financial",
                                     "irreversible")]
    assert ttls == sorted(ttls, reverse=True), ttls


# ------------------------------------------------------------ snapshots

def test_snapshot_must_be_signed_by_the_issuer(world):
    snap = world["ra"].publish()
    world["state"].accept(snap)          # ok
    snap.signature = "00" * 64
    with pytest.raises(RevocationRefusal) as e:
        world["state"].accept(snap)
    assert e.value.code == "snapshot_bad_signature"


def test_snapshot_rollback_is_refused(world):
    s1 = world["ra"].publish()
    s2 = world["ra"].publish()
    world["state"].accept(s2)
    with pytest.raises(RevocationRefusal) as e:
        world["state"].accept(s1)
    assert e.value.code == "snapshot_rollback"


# ------------------------------------------------------------ revocation

def test_revoked_certificate_is_refused(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    world["ra"].revoke_certificate(cert.authority_record_id)
    world["state"].accept(world["ra"].publish())
    platform = Platform()
    r = run(world, cert, platform)
    assert r.status == "certificate_revoked"
    assert platform.state() == []


def test_revoked_actor_is_refused(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    world["ra"].revoke_actor(ACTOR)
    world["state"].accept(world["ra"].publish())
    assert run(world, cert).status == "actor_revoked"


def test_revoked_organ_is_refused(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    world["ra"].revoke_organ(ORG)
    world["state"].accept(world["ra"].publish())
    assert run(world, cert).status == "organ_revoked"


def test_replaced_workload_is_refused(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    world["ra"].revoke_workload(WORKLOAD)
    world["state"].accept(world["ra"].publish())
    assert run(world, cert).status == "workload_revoked"


def test_issuer_key_compromise_refuses_every_certificate_it_signed(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    world["ra"].revoke_key(world["signer"].key_id)
    world["state"].accept(world["ra"].publish())
    r = run(world, cert)
    assert r.status == "issuer_key_revoked"


# ------------------------------------------------------------ staleness

def test_external_contact_refuses_when_no_snapshot_has_arrived(world):
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    r = run(world, cert)                       # state never accepted a snapshot
    assert r.status == "revocation_stale"


def test_external_contact_refuses_a_stale_snapshot(world):
    old = datetime.now(timezone.utc) - timedelta(hours=2)
    world["state"].accept(world["ra"].publish(now=old))
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    assert run(world, cert).status == "revocation_stale"


def test_irreversible_escalates_to_a_human_rather_than_refusing_silently(world):
    cert = world["issuer"].issue(
        actor_id=ACTOR, proposal=proposal(consequence_class="irreversible"))
    r = run(world, cert)
    assert r.status == "revocation_human_escalation"


def test_internal_read_permits_on_stale_state(world):
    """Deliberate asymmetry: low consequence tolerates staleness."""
    world["issuer"].known_capabilities.add("memory.read")
    world["issuer"]._principals[ACTOR] = Principal(
        actor_id=ACTOR, organ_id=ORG, workload_identity=WORKLOAD,
        legal_principal="alfonso_lopez",
        declared_capabilities=("draft.publish", "memory.read"),
        consequence_ceiling="irreversible", budget_ceiling_usd=5.0)
    cert = world["issuer"].issue(
        actor_id=ACTOR,
        proposal=proposal(capability_id="memory.read",
                          consequence_class="internal_read"))
    assert run(world, cert).status == "committed"


def test_clock_skew_tolerance_is_applied(world):
    skew = manifest.revocation_policy()["clock_skew_tolerance_seconds"]
    assert skew > 0
    # A snapshot exactly at the boundary minus skew is still accepted.
    edge = datetime.now(timezone.utc) - timedelta(
        seconds=manifest.revocation_policy_for("external_contact")
        ["maximum_staleness_seconds"] + skew - 5)
    world["state"].accept(world["ra"].publish(now=edge))
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    assert run(world, cert).status == "committed"


# ------------------------------------------------------------ veto timing

def test_veto_is_checked_at_three_points(world):
    world["state"].accept(world["ra"].publish())
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    run(world, cert)
    assert world["aperture"].veto_checks == [
        "before_preparation",
        "after_preparation_before_commit",
        "immediately_before_adapter",
    ]


def test_veto_engaged_before_preparation_stops_everything(world):
    world["state"].accept(world["ra"].publish())
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    world["aperture"].veto.engage("hold")
    platform = Platform()
    r = run(world, cert, platform)
    assert r.status == "local_veto"
    assert world["aperture"].veto_checks == ["before_preparation"]
    assert platform.state() == []


def test_veto_engaged_between_checks_still_stops_execution(world):
    """The TOCTOU case: the veto flips after verification but before commit."""
    world["state"].accept(world["ra"].publish())
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())
    platform = Platform()

    real_blocks = world["aperture"].veto.blocks
    calls = {"n": 0}

    def flipping():
        calls["n"] += 1
        if calls["n"] == 1:
            return False, ""              # clear at the first check
        return True, "operator pulled the cord mid-flight"
    world["aperture"].veto.blocks = flipping

    r = run(world, cert, platform)
    assert r.status == "local_veto"
    assert platform.state() == []
    world["aperture"].veto.blocks = real_blocks


def test_execution_lease_holds_the_final_check_and_the_adapter_together(world):
    """The last veto read and the adapter call are inside one critical section."""
    import inspect
    src = inspect.getsource(Aperture.execute)
    lease = src.index("with self._lease:")
    final_check = src.index("immediately_before_adapter")
    executor_call = src.index("executor()")
    assert lease < final_check < executor_call, (
        "the final veto check and the adapter invocation must both be inside "
        "the execution lease")


def test_shutdown_during_commit_unwinds_and_still_shuts_down(world):
    """Hostile case 40. `except Exception` does not catch KeyboardInterrupt or
    SystemExit, so without explicit handling a shutdown mid-commit would leave
    the budget reserved and no receipt: authority spent with no record.

    Required behaviour: unwind, record, then RE-RAISE. A shutdown must still
    shut down; swallowing it would be worse than the leak.
    """
    world["state"].accept(world["ra"].publish())
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())

    def dying():
        raise KeyboardInterrupt("shutdown during commit")

    with pytest.raises(KeyboardInterrupt):
        world["aperture"].execute(
            cert, P, payload=PAYLOAD, executor=dying,
            readback=lambda: [], expected_state=lambda s: True)

    assert world["budget"].state(cert.budget_reservation_id) == "released"
    assert world["aperture"].receipts[-1].status == "shutdown_during_commit"


def test_system_exit_during_commit_also_unwinds(world):
    world["state"].accept(world["ra"].publish())
    cert = world["issuer"].issue(actor_id=ACTOR, proposal=proposal())

    def dying():
        raise SystemExit(1)

    with pytest.raises(SystemExit):
        world["aperture"].execute(
            cert, P, payload=PAYLOAD, executor=dying,
            readback=lambda: [], expected_state=lambda s: True)
    assert world["budget"].state(cert.budget_reservation_id) == "released"
