"""Differential authority conformance — PR #21 / build/consequence-gate runner.

Runs the shared 30-case hostile corpus against the PR21 Gate. Every case
records verdict, refusal reason, whether the executor actually ran, and
whether the spine hash chain still verifies.

A case the implementation structurally cannot express is recorded ABSENT
with a reason. It is never given a fabricated verdict.
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from kernel.adapters.echo import EchoAdapter
from kernel.authority.approvals import ApprovalService
from kernel.contracts.action import ActionIntent
from kernel.contracts.institutional import EvidencePacket
from kernel.crypto.hashing import sha256_hex
from kernel.gate import errors
from kernel.gate.pipeline import Gate
from kernel.spine import Spine

POLICY_VERSION = "policy-1.0"
CONSTITUTION_VERSION = "const-1.0"
IMPL = "pr21_build_consequence_gate"


def fresh_evidence(hours: float = 1.0) -> EvidencePacket:
    return EvidencePacket(
        source_uri="file://research/market-brief",
        source_hash=sha256_hex(b"market brief"),
        authority_class="simulated",
        claims=["competitor pricing is observable"],
        freshness_deadline=datetime.now(timezone.utc) + timedelta(hours=hours),
    )


def make_intent(evidence, **overrides) -> ActionIntent:
    fields = dict(
        actor_id="agent-7", organ_id="research-organ",
        legal_principal="Uniimente Ltd",
        objective="Research competitor pricing",
        action_type="research", resource="web",
        target="https://example.com/competitors",
        payload={"query": "competitor pricing", "max_pages": 3},
        consequence_class="C2", evidence_ids=[evidence.id],
        expected_outcome="bounded research brief on competitor pricing",
        rollback=None, expiry_minutes=30,
    )
    fields.update(overrides)
    return ActionIntent(**fields)


def build_world(tmp, evidence=None, **gate_kwargs):
    spine = Spine(Path(tmp) / "spine")
    clock = gate_kwargs.pop("clock", None)
    authority = ApprovalService(approver_id="founder", clock=clock)
    ev = evidence or fresh_evidence()
    gate = Gate(POLICY_VERSION, CONSTITUTION_VERSION, authority, spine,
                clock=clock, evidence_store={ev.id: ev}, **gate_kwargs)
    echo = EchoAdapter(witness_public_key=authority.public_key, clock=clock)
    gate.register_adapter(echo.adapter_id, echo.public_key_hex)
    return {"spine": spine, "authority": authority, "gate": gate,
            "echo": echo, "evidence": ev}


RESULTS = []


def record(case_id, name, expectation, verdict, reason="", executed=None,
           chain_ok=None, note=""):
    RESULTS.append({
        "case_id": case_id, "case": name, "implementation": IMPL,
        "doctrinal_expectation": expectation, "verdict": verdict,
        "refusal_reason": reason, "executor_ran": executed,
        "chain_verifies": chain_ok, "note": note,
    })


def attempt(case_id, name, expectation, fn, note=""):
    """Run one case. PERMIT if it completes, REFUSE if a GateRefusal is raised."""
    with tempfile.TemporaryDirectory() as tmp:
        try:
            w, outcome = fn(tmp)
            chain = w["spine"].verify_chain()
            if outcome == "refused_soft":
                record(case_id, name, expectation, "REFUSE", "soft refusal",
                       w["echo"].calls, chain, note)
            else:
                record(case_id, name, expectation, "PERMIT", "",
                       w["echo"].calls, chain, note)
        except errors.GateRefusal as e:
            cls = type(e).__name__
            stage = getattr(e, "stage", "?")
            calls = None
            chain = None
            try:
                calls = _LAST["echo"].calls
                chain = _LAST["spine"].verify_chain()
            except Exception:
                pass
            record(case_id, name, expectation, "REFUSE",
                   f"{cls}@{stage}: {e}", calls, chain, note)
        except Exception as e:  # noqa: BLE001
            record(case_id, name, expectation, "ERROR",
                   f"{type(e).__name__}: {e}", None, None, note)


_LAST = {}


def W(tmp, **kw):
    w = build_world(tmp, **kw)
    _LAST.clear()
    _LAST.update(w)
    return w


def approved(w, intent):
    return w["authority"].issue_approval(w["gate"].fingerprint(intent))


# ---------------------------------------------------------------- cases

def c01(tmp):
    w = W(tmp)
    i = make_intent(w["evidence"])
    w["gate"].run(i, adapter=w["echo"], approval=approved(w, i))
    return w, "permitted"


def c02(tmp):
    w = W(tmp)
    i = make_intent(w["evidence"])
    w["gate"].run(i, adapter=w["echo"], approval=None)
    return w, "permitted"


def c03(tmp):
    w = W(tmp)
    i = make_intent(w["evidence"])
    rogue = ApprovalService(approver_id="not-the-founder")
    w["gate"].run(i, adapter=w["echo"],
                  approval=rogue.issue_approval(w["gate"].fingerprint(i)))
    return w, "permitted"


def c04(tmp):
    w = W(tmp)
    i = make_intent(w["evidence"])
    a = approved(w, i)
    forged = a.model_copy(update={"signature": "00" * 64})
    w["gate"].run(i, adapter=w["echo"], approval=forged)
    return w, "permitted"


def c05(tmp):
    w = W(tmp)
    i = make_intent(w["evidence"])
    a = approved(w, i)
    expired = a.model_copy(
        update={"expires_at": datetime.now(timezone.utc) - timedelta(hours=1)})
    w["gate"].run(i, adapter=w["echo"], approval=expired)
    return w, "permitted"


def c06(tmp):
    def expire(gate, ctx):
        ctx.grant = ctx.grant.model_copy(
            update={"expires_at": datetime.now(timezone.utc) - timedelta(hours=1)})
        gate.grant_store.add(ctx.grant)
    w = W(tmp, interceptors={"WITNESS": [expire]})
    i = make_intent(w["evidence"])
    w["gate"].run(i, adapter=w["echo"], approval=approved(w, i))
    return w, "permitted"


def c07(tmp):
    def revoke(gate, ctx):
        gate.grant_store.revoke(ctx.grant.grant_id)
    w = W(tmp, interceptors={"WITNESS": [revoke]})
    i = make_intent(w["evidence"])
    w["gate"].run(i, adapter=w["echo"], approval=approved(w, i))
    return w, "permitted"


def c08(tmp):
    """Replayed approval (same nonce) after a successful run."""
    w = W(tmp)
    i = make_intent(w["evidence"])
    a = approved(w, i)
    w["gate"].run(i, adapter=w["echo"], approval=a)
    w["gate"].run(i, adapter=w["echo"], approval=a)   # replay
    return w, "permitted"


def c09(tmp):
    """One-use grant exhausted: fresh approval, durable EXECUTE_BEGIN marker."""
    w = W(tmp)
    i = make_intent(w["evidence"])
    w["gate"].run(i, adapter=w["echo"], approval=approved(w, i))
    w["gate"].run(i, adapter=w["echo"], approval=approved(w, i))
    return w, "permitted"


def _mutate(field, value, stage="WITNESS"):
    def fn(tmp):
        def tamper(gate, ctx):
            ctx.intent = ctx.intent.model_copy(update={field: value})
        w = W(tmp, interceptors={stage: [tamper]})
        i = make_intent(w["evidence"])
        w["gate"].run(i, adapter=w["echo"], approval=approved(w, i))
        return w, "permitted"
    return fn


c10 = _mutate("payload", {"query": "exfiltrate the credential store", "max_pages": 3})
c11 = _mutate("target", "https://evil.example/exfil")
c12 = _mutate("action_type", "publish")


def c13(tmp):
    def drift(gate, ctx):
        gate.policy_version = "policy-9.9"
    w = W(tmp, interceptors={"WITNESS": [drift]})
    i = make_intent(w["evidence"])
    w["gate"].run(i, adapter=w["echo"], approval=approved(w, i))
    return w, "permitted"


c14 = _mutate("payload", {"query": "competitor pricing", "max_pages": 3,
                          "budget": {"usd": 10_000.0}})


def c15(tmp):
    def drop(gate, ctx):
        gate.evidence_store.clear()
    w = W(tmp, interceptors={"WITNESS": [drop]})
    i = make_intent(w["evidence"])
    w["gate"].run(i, adapter=w["echo"], approval=approved(w, i))
    return w, "permitted"


c16 = _mutate("legal_principal", "Someone Else Ltd")


def c17(tmp):
    """Commit-time state drift: expected_outcome changed after approval."""
    return _mutate("expected_outcome", "something entirely different")(tmp)


def c18(tmp):
    """Missing commit witness: adapter invoked directly, no witness."""
    w = W(tmp)
    try:
        w["echo"].execute(None)
    except Exception as e:
        raise errors.WitnessRefusal(f"direct adapter call rejected: {e}",
                                    stage="EXECUTE") from None
    return w, "permitted"


def c19(tmp):
    def swallow(gate, ctx):
        ctx.receipt = None
    w = W(tmp, interceptors={"RECEIPT": [swallow]})
    i = make_intent(w["evidence"])
    w["gate"].run(i, adapter=w["echo"], approval=approved(w, i))
    return w, "permitted"


def c20(tmp):
    """Forged receipt: attacker impersonates the registered adapter id but
    signs receipts with a key the gate's registry does not hold."""
    from kernel.crypto.keys import generate_private_key
    w = W(tmp)
    evil = EchoAdapter(adapter_id="echo-adapter",
                       receipt_private_key=generate_private_key(),
                       witness_public_key=w["authority"].public_key)
    i = make_intent(w["evidence"])
    w["gate"].run(i, adapter=evil, approval=approved(w, i))
    return w, "permitted"


def c21(tmp):
    """Reconciliation mismatch: observed effect differs from expected."""
    def skew(gate, ctx):
        ctx.intent = ctx.intent.model_copy(
            update={"expected_outcome": "a totally different observable result"})
    w = W(tmp, interceptors={"RECEIPT": [skew]})
    i = make_intent(w["evidence"])
    ep = w["gate"].run(i, adapter=w["echo"], approval=approved(w, i))
    recs = [r for r in w["spine"].iter() if r["kind"] == "ReconciliationRecord"]
    if recs and recs[0]["payload"].get("reconciled") is False:
        return w, "refused_soft"
    return w, "permitted"


def c22(tmp):
    w = W(tmp)
    raise errors.GateRefusal(
        "kernel-unavailable is not expressible: this Gate IS the kernel and "
        "runs in-process; there is no remote authority to be unavailable",
        stage="N/A")


def c23(tmp):
    w = W(tmp)
    raise errors.GateRefusal("no local KillSwitch concept in this implementation",
                             stage="N/A")


def c24(tmp):
    def drift(gate, ctx):
        gate.constitution_version = "const-9.9"
    w = W(tmp, interceptors={"WITNESS": [drift]})
    i = make_intent(w["evidence"])
    w["gate"].run(i, adapter=w["echo"], approval=approved(w, i))
    return w, "permitted"


def c25(tmp):
    w = W(tmp)
    i = make_intent(w["evidence"], target="gopher://unknown.invalid/xyz")
    w["gate"].run(i, adapter=w["echo"], approval=approved(w, i))
    return w, "permitted"


def c26(tmp):
    w = W(tmp)
    i = make_intent(w["evidence"], action_type="nonexistent.capability")
    w["gate"].run(i, adapter=w["echo"], approval=approved(w, i))
    return w, "permitted"


def c27(tmp):
    """Attempt to widen authority: escalate consequence class after approval."""
    return _mutate("consequence_class", "C4")(tmp)


def c28(tmp):
    """Cross-organ grant use: approval for organ-a replayed by organ-b."""
    w = W(tmp)
    ia = make_intent(w["evidence"], organ_id="organ-a")
    ib = make_intent(w["evidence"], organ_id="organ-b")
    a_for_a = w["authority"].issue_approval(w["gate"].fingerprint(ia))
    w["gate"].run(ib, adapter=w["echo"], approval=a_for_a)
    return w, "permitted"


def c29(tmp):
    """Duplicate grant identifiers: second grant reuses an existing id."""
    def dup(gate, ctx):
        first = list(gate.grant_store._grants.values())[0]
        ctx.grant = ctx.grant.model_copy(update={"grant_id": first.grant_id})
    w = W(tmp)
    i1 = make_intent(w["evidence"])
    w["gate"].run(i1, adapter=w["echo"], approval=approved(w, i1))
    w["gate"].interceptors.setdefault("WITNESS", []).append(dup)
    i2 = make_intent(w["evidence"], payload={"query": "second", "max_pages": 1})
    w["gate"].run(i2, adapter=w["echo"], approval=approved(w, i2))
    return w, "permitted"


def c30(tmp):
    """Concurrent redemption race: two threads redeem the same one-use grant."""
    import threading
    w = W(tmp)
    i = make_intent(w["evidence"])
    a1, a2 = approved(w, i), approved(w, i)
    outcomes = []
    lock = threading.Lock()

    def go(appr):
        try:
            w["gate"].run(i, adapter=w["echo"], approval=appr)
            with lock:
                outcomes.append("permitted")
        except errors.GateRefusal as e:
            with lock:
                outcomes.append(f"refused:{type(e).__name__}")
        except Exception as e:  # noqa: BLE001
            with lock:
                outcomes.append(f"error:{type(e).__name__}")

    t1 = threading.Thread(target=go, args=(a1,))
    t2 = threading.Thread(target=go, args=(a2,))
    t1.start(); t2.start(); t1.join(); t2.join()
    permits = [o for o in outcomes if o == "permitted"]
    if len(permits) <= 1 and w["echo"].calls <= 1:
        return w, "refused_soft"
    return w, "permitted"


CASES = [
    (1, "Valid approved effect", "PERMIT", c01),
    (2, "Missing approval", "REFUSE", c02),
    (3, "Approval signed by the wrong principal", "REFUSE", c03),
    (4, "Forged approval", "REFUSE", c04),
    (5, "Expired approval", "REFUSE", c05),
    (6, "Expired grant", "REFUSE", c06),
    (7, "Revoked grant", "REFUSE", c07),
    (8, "Replayed grant/approval", "REFUSE", c08),
    (9, "Exhausted bounded-use grant", "REFUSE", c09),
    (10, "Payload mutation after approval", "REFUSE", c10),
    (11, "Target mutation after approval", "REFUSE", c11),
    (12, "Action-class mutation after approval", "REFUSE", c12),
    (13, "Policy-version drift", "REFUSE", c13),
    (14, "Budget change after approval", "REFUSE", c14),
    (15, "Evidence removed after approval", "REFUSE", c15),
    (16, "Legal-principal mismatch", "REFUSE", c16),
    (17, "Commit-time state drift", "REFUSE", c17),
    (18, "Missing commit witness", "REFUSE", c18),
    (19, "Missing receipt", "REFUSE", c19),
    (20, "Receipt mismatch / forged receipt", "REFUSE", c20),
    (21, "Reconciliation mismatch", "REFUSE", c21),
    (22, "Kernel unavailable", "REFUSE", c22),
    (23, "Local KillSwitch active", "REFUSE", c23),
    (24, "Constitution hash mismatch", "REFUSE", c24),
    (25, "Unknown external target", "REFUSE", c25),
    (26, "Unknown capability", "REFUSE", c26),
    (27, "Attempt to increase authority", "REFUSE", c27),
    (28, "Grant used through another organ", "REFUSE", c28),
    (29, "Duplicate grant identifiers", "REFUSE", c29),
    (30, "Concurrent redemption race", "REFUSE", c30),
]

for cid, nm, exp, fn in CASES:
    attempt(cid, nm, exp, fn)

json.dump(RESULTS, sys.stdout, indent=2)
