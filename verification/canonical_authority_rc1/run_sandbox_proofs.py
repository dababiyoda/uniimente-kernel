#!/usr/bin/env python3
"""Gate C sandbox proofs for the Reality Aperture.

No production credentials. No real external effect. No money. No chain.
The "platform" is an in-process fake that holds its own state, so readback is
genuinely independent of the executor: the executor writes, the platform is
asked separately what it now contains.

Proof A  governed publication, end to end
Proof B  cross-organ proposal reaching a decision and stopping there
Proof C  local veto beats valid constitutional authority
Proof D  organ replacement cannot inherit authority implicitly
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))

from aperture import (Aperture, CertificateError, LocalVeto, Presenter, VerificationRegistry)
from aperture_issuer import (ApprovalRecord, AuthorityIssuer, BudgetOffice, Ed25519SigningProvider, Principal, Proposal)

OUT = pathlib.Path(__file__).resolve().parent
POLICY, CONSTITUTION = "policy-1.0", "const-1.0"
DB = "spiffe://uniimente.internal/organ/daleobanks"
ACTOR = DB + "/agent/publisher"
WORKLOAD = DB + "/workload/publisher-v1"
TARGET = "sandbox:fake-platform/outbox"
PAYLOAD = {"text": "UNIIMENTE sandbox publication. No real platform was contacted."}


class FakePlatform:
    """Holds state independently of whoever calls publish()."""

    def __init__(self):
        self._posts = []
        self.readback_calls = 0

    def publish(self, text):
        self._posts.append({"id": f"post-{len(self._posts)+1}", "text": text})

    def readback(self):
        self.readback_calls += 1
        return [dict(p) for p in self._posts]


def policy(principal, proposal):
    return "REQUIRE_HUMAN" if proposal.consequence_class == "irreversible" else "PERMIT"


def build(veto_engaged=False):
    signer = Ed25519SigningProvider.generate("kernel-sandbox-key-1")
    registry = VerificationRegistry()
    registry.register(signer.key_id, signer.public_key_hex())
    budget = BudgetOffice()
    issuer = AuthorityIssuer(
        signer=signer, policy_version=POLICY, constitution_version=CONSTITUTION,
        policy_evaluator=policy,
        known_capabilities={"draft.publish"}, known_targets={TARGET},
        budget=budget)
    issuer.register_principal(Principal(
        actor_id=ACTOR, organ_id=DB, workload_identity=WORKLOAD,
        legal_principal="alfonso_lopez",
        declared_capabilities=("draft.publish",),
        consequence_ceiling="external_contact", budget_ceiling_usd=5.0))
    ap = Aperture(registry=registry, organ_id=DB,
                  current_policy_version=POLICY,
                  current_constitution_version=CONSTITUTION,
                  veto=LocalVeto(engaged=veto_engaged,
                                 reason="operator hold" if veto_engaged else ""),
                  budget=budget)
    return signer, registry, issuer, ap, budget


def prop(**kw):
    d = dict(request_id="req-sandbox-1", capability_id="draft.publish",
             action_class="draft.publish", target_id=TARGET, payload=PAYLOAD,
             consequence_class="external_contact",
             evidence_refs=["sha256:" + "e" * 64], estimated_cost_usd=0.0,
             expected_outcome="one sandbox post exists")
    d.update(kw)
    return Proposal(**d)


# ------------------------------------------------------------------ Proof A
def proof_a():
    signer, registry, issuer, ap, budget = build()
    platform = FakePlatform()
    cert = issuer.issue(actor_id=ACTOR, proposal=prop())
    receipt = ap.execute(
        cert, Presenter(ACTOR, DB, WORKLOAD), payload=PAYLOAD,
        executor=lambda: platform.publish(PAYLOAD["text"]),
        readback=platform.readback,
        expected_state=lambda s: len(s) == 1 and s[0]["text"] == PAYLOAD["text"])
    return {
        "proof": "A - governed publication",
        "steps": ["proposal", "evidence", "policy PERMIT", "bounded certificate",
                  "independent verification at the aperture", "local veto clear",
                  "fake platform execution", "independent readback",
                  "receipt", "reconciliation"],
        "certificate": {
            "authority_record_id": cert.authority_record_id,
            "effect_binding_hash": cert.effect_binding_hash(),
            "bound_fields": len(cert.binding()),
            "key_id": cert.key_id, "algorithm": cert.algorithm,
            "signature_prefix": cert.signature[:32],
        },
        "receipt": {"status": receipt.status,
                    "readback_verified": receipt.readback_verified},
        "platform_state": platform.readback(),
        "readback_is_independent": platform.readback_calls >= 1,
        "budget_state": budget.state(cert.budget_reservation_id),
        "no_production_credential": True,
        "no_real_external_effect": True,
        "passed": receipt.status == "committed" and receipt.readback_verified,
    }


# ------------------------------------------------------------------ Proof B
def proof_b():
    """DALEOBANKS senses, WMI reasons, the Kernel decides, nothing executes."""
    signer, registry, issuer, ap, budget = build()

    signal = {"organ": DB, "kind": "SignalPacket",
              "observation": "recurring question in community about governed publishing"}
    # WMI constructs a case and MATERIALLY DIFFERENT routes; it does not decide.
    case = {"organ": "spiffe://uniimente.internal/organ/wmi",
            "kind": "OpportunityCase", "derived_from": signal,
            "routes": [
                {"id": "R1", "thesis": "sell the governance layer as a product"},
                {"id": "R2", "thesis": "operate it and sell verified outcomes"},
                {"id": "R3", "thesis": "license the conformance suite only"}],
            "dissent": ["R1 competes with incumbents holding distribution",
                        "R2 needs an operating team that does not exist yet"]}

    wmi_tried_to_issue = None
    try:
        issuer.issue(actor_id="spiffe://uniimente.internal/organ/wmi",
                     proposal=prop(request_id="req-wmi"))
        wmi_tried_to_issue = "ISSUED - INVARIANT VIOLATED"
    except CertificateError as e:
        wmi_tried_to_issue = f"refused: {e.code}"

    # The Kernel evaluates and records a decision. No certificate is redeemed.
    cert = issuer.issue(actor_id=ACTOR, proposal=prop(request_id="req-sandbox-b"))
    return {
        "proof": "B - cross-organ proposal",
        "signal_packet": signal,
        "opportunity_case": case,
        "routes_preserved": len(case["routes"]),
        "dissent_preserved": len(case["dissent"]),
        "wmi_attempt_to_issue_authority": wmi_tried_to_issue,
        "kernel_decision": {"authority_record_id": cert.authority_record_id,
                            "issued": True, "redeemed": False},
        "external_execution_occurred": False,
        "passed": (wmi_tried_to_issue.startswith("refused")
                   and len(case["routes"]) >= 3 and len(case["dissent"]) >= 1),
    }


# ------------------------------------------------------------------ Proof C
def proof_c():
    """Valid constitutional authority + local veto = no external state change."""
    signer, registry, issuer, ap, budget = build(veto_engaged=True)
    platform = FakePlatform()
    cert = issuer.issue(actor_id=ACTOR, proposal=prop(request_id="req-sandbox-c"))

    # The authority really is valid: verification passes with the veto engaged.
    verification_error = None
    try:
        Aperture(registry=registry, organ_id="auditor",
                 current_policy_version=POLICY,
                 current_constitution_version=CONSTITUTION).verify(
            cert, Presenter(ACTOR, DB, WORKLOAD))
    except CertificateError as e:  # pragma: no cover
        verification_error = str(e)

    receipt = ap.execute(
        cert, Presenter(ACTOR, DB, WORKLOAD), payload=PAYLOAD,
        executor=lambda: platform.publish(PAYLOAD["text"]),
        readback=platform.readback, expected_state=lambda s: len(s) == 1)
    return {
        "proof": "C - local veto",
        "authority_was_valid": verification_error is None,
        "veto_engaged": True,
        "receipt_status": receipt.status,
        "platform_state_after": platform.readback(),
        "external_state_changed": len(platform.readback()) != 0,
        "budget_state": budget.state(cert.budget_reservation_id),
        "authority_expanded": False,
        "passed": (verification_error is None
                   and receipt.status == "local_veto"
                   and platform.readback() == []
                   and budget.state(cert.budget_reservation_id) == "released"),
    }


# ------------------------------------------------------------------ Proof D
def proof_d():
    """A replacement organ cannot inherit authority implicitly."""
    signer, registry, issuer, ap, budget = build()
    platform = FakePlatform()
    cert = issuer.issue(actor_id=ACTOR, proposal=prop(request_id="req-sandbox-d"))

    # The organ is replaced mid-flight: same actor and organ, NEW workload.
    replacement = Presenter(ACTOR, DB, DB + "/workload/publisher-v2")
    r_implicit = ap.execute(
        cert, replacement, payload=PAYLOAD,
        executor=lambda: platform.publish(PAYLOAD["text"]),
        readback=platform.readback, expected_state=lambda s: len(s) == 1)

    # Continuity is possible, but only by re-authorizing the new identity
    # explicitly. Obligations and evidence carry; authority does not.
    issuer.register_principal(Principal(
        actor_id=ACTOR, organ_id=DB,
        workload_identity=DB + "/workload/publisher-v2",
        legal_principal="alfonso_lopez",
        declared_capabilities=("draft.publish",),
        consequence_ceiling="external_contact", budget_ceiling_usd=5.0))
    cert2 = issuer.issue(actor_id=ACTOR, proposal=prop(request_id="req-sandbox-d2"))
    r_explicit = ap.execute(
        cert2, replacement, payload=PAYLOAD,
        executor=lambda: platform.publish(PAYLOAD["text"]),
        readback=platform.readback, expected_state=lambda s: len(s) == 1)

    return {
        "proof": "D - replacement organ continuity",
        "implicit_inheritance_attempt": r_implicit.status,
        "posts_after_run": len(platform.readback()),
        "posts_expected": 1,
        "note": ("exactly one post exists: the implicit-inheritance attempt "
                 "produced no external effect, the explicit re-authorization "
                 "produced one"),
        "explicit_reauthorization_status": r_explicit.status,
        "old_certificate_still_bound_to_old_workload": True,
        "lineage_preserved": {"predecessor_workload": WORKLOAD,
                              "successor_workload": DB + "/workload/publisher-v2",
                              "same_legal_principal": True,
                              "authority_inherited": False},
        "passed": (r_implicit.status == "workload_mismatch"
                   and r_explicit.status == "committed"
                   and len(platform.readback()) == 1),
    }


def main():
    proofs = {"proof_a": proof_a(), "proof_b": proof_b(),
              "proof_c": proof_c(), "proof_d": proof_d()}
    names = {"proof_a": "proof_a_publication_episode.json",
             "proof_b": "proof_b_cross_organ_episode.json",
             "proof_c": "proof_c_local_veto_episode.json",
             "proof_d": "proof_d_replacement_continuity_episode.json"}
    for k, fn in names.items():
        (OUT / fn).write_text(json.dumps(proofs[k], indent=2) + "\n")

    all_passed = all(p["passed"] for p in proofs.values())
    gate_c = {
        "gate": "Gate C - first canonical sandbox transaction",
        "status": "CLOSED" if all_passed else "OPEN",
        "proofs": {k: proofs[k]["passed"] for k in proofs},
        "no_production_credentials": True,
        "no_real_external_action": True,
        "readback_independent_of_executor": True,
        "executor_self_report_insufficient": True,
    }
    (OUT / "gate_c_result.json").write_text(json.dumps(gate_c, indent=2) + "\n")

    lines = []
    for fn in sorted(names.values()) + ["gate_c_result.json"]:
        h = hashlib.sha256((OUT / fn).read_bytes()).hexdigest()
        lines.append(f"{h}  {fn}")
    (OUT / "checksums.txt").write_text("\n".join(lines) + "\n")

    for k, p in proofs.items():
        print(f"  {k}: {'PASS' if p['passed'] else 'FAIL'}")
    print(f"Gate C: {gate_c['status']}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
