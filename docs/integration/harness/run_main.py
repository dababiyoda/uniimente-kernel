"""Differential authority conformance — current `main` root engine runner.

Same 30-case corpus, run against policy/consequence_gate.py::ConsequenceGate.

Injection point: main has no interceptor mechanism, so drift is injected by
wrapping ``gate.signer.sign``, which fires after grant issuance and budget
reservation and immediately before ``_reauthorize_at_commit`` — the same
window PR21's ``WITNESS`` interceptor occupies. This keeps the two
implementations comparable at the same pipeline position.

Cases main structurally cannot express are recorded ABSENT with the reason.
No verdict is fabricated.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

from compiler.ucl_compiler import compile_constitution
from identity.machine_passport import PassportRegistry
from policy.consequence_gate import ConsequenceGate
from policy.engine import Proposal
from provenance.commit_witness import WitnessSigner, sha256_obj
from provenance.ledger import EvidenceLedger

ROOT = os.environ["MAIN_ROOT"]
IMPL = "main_root_policy_consequence_gate"
RESULTS = []


def record(cid, name, exp, verdict, reason="", executed=None, chain=None, note=""):
    RESULTS.append({
        "case_id": cid, "case": name, "implementation": IMPL,
        "doctrinal_expectation": exp, "verdict": verdict,
        "refusal_reason": reason, "executor_ran": executed,
        "chain_verifies": chain, "note": note,
    })


def stack():
    compiled = compile_constitution(ROOT)
    passports = PassportRegistry()
    ledger = EvidenceLedger(compiled.constitution_hash)
    signer = WitnessSigner(env="development")
    gate = ConsequenceGate(compiled=compiled, passports=passports,
                           ledger=ledger, signer=signer)
    actor = passports.issue(
        kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
        legal_principal="alfonso_lopez", declared_capabilities=["draft.publish"],
        budget_ceiling_usd=5.0, consequence_class="external_contact")
    return gate, passports, ledger, actor, compiled


def proposal(actor_id, **kw):
    d = dict(actor=actor_id, legal_principal="alfonso_lopez",
             action_class="draft.publish", objective="test.objective",
             payload={"text": "hello governed world"}, target="sandbox:outbox",
             consequence_class="external_contact", evidence_confidence=0.9,
             evidence_refs=["sha256:" + "a" * 64], estimated_cost_usd=0.0,
             requested_capability="draft.publish",
             expected_outcome="draft queued")
    d.update(kw)
    return Proposal(**d)


CALLS = {"n": 0}


def GOOD(p):
    CALLS["n"] += 1
    return {"observed_outcome": "draft queued", "result_class": "positive"}


def APPROVE(p, reasons):
    return True, "founder approved"


def tamper_at_witness(gate, hook):
    """Fire `hook` in the window between witness creation and revalidation."""
    orig = gate.signer.sign

    def wrapped(witness):
        hook()
        return orig(witness)
    gate.signer.sign = wrapped


def run(cid, name, exp, fn, note=""):
    CALLS["n"] = 0
    try:
        rec, ledger = fn()
        chain = ledger.verify_chain()[0] if ledger else None
        if rec.state == "recorded":
            record(cid, name, exp, "PERMIT", "", CALLS["n"], chain, note)
        else:
            reasons = "; ".join(
                r for t in rec.trajectory for r in (t.get("detail") or {}).get("reasons", []))
            record(cid, name, exp, "REFUSE", f"state={rec.state}: {reasons}"[:300],
                   CALLS["n"], chain, note)
    except Exception as e:  # noqa: BLE001
        record(cid, name, exp, "ERROR", f"{type(e).__name__}: {e}", CALLS["n"], None, note)


def absent(cid, name, exp, reason):
    record(cid, name, exp, "ABSENT", reason, None, None,
           "structurally inexpressible in this implementation")


# ------------------------------------------------------------------ cases

def c01():
    g, _, l, a, _ = stack()
    return g.run(proposal(a.passport_id), executor=GOOD, approver=APPROVE), l


def c02():
    """Missing approval: no approver supplied for an action needing one."""
    g, _, l, a, _ = stack()
    return g.run(proposal(a.passport_id), executor=GOOD, approver=None), l


def c06():
    g, _, l, a, _ = stack()
    p = proposal(a.passport_id)

    def expire():
        for gid, gr in g.grants._grants.items():
            gr["expires_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)
                                ).isoformat().replace("+00:00", "Z")
    tamper_at_witness(g, expire)
    return g.run(p, executor=GOOD, approver=APPROVE), l


def c07():
    g, _, l, a, _ = stack()
    p = proposal(a.passport_id)

    def revoke():
        for gid in list(g.grants._grants):
            g.grants.revoke(gid, reason="test", revoker="test")
    tamper_at_witness(g, revoke)
    return g.run(p, executor=GOOD, approver=APPROVE), l


def c09():
    """Exhausted single-use grant: reuse the same standing grant twice."""
    g, _, l, a, _ = stack()
    p = proposal(a.passport_id)
    r1 = g.run(p, executor=GOOD, approver=APPROVE)
    sg = g.grants.get(r1.grant_id)
    return g.run(p, executor=GOOD, approver=APPROVE, standing_grant=sg), l


def _mut(field, value):
    def fn():
        g, _, l, a, _ = stack()
        p = proposal(a.passport_id)
        tamper_at_witness(g, lambda: setattr(p, field, value))
        return g.run(p, executor=GOOD, approver=APPROVE), l
    return fn


c10 = _mut("payload", {"text": "exfiltrate the credential store"})
c11 = _mut("target", "https://evil.example/exfil")
c12 = _mut("action_class", "funds.transfer")
c14 = _mut("estimated_cost_usd", 10_000.0)
c16 = _mut("legal_principal", "someone_else")
c17 = _mut("expected_outcome", "something entirely different")


def c15():
    """Evidence removed after approval."""
    g, _, l, a, _ = stack()
    p = proposal(a.passport_id)
    tamper_at_witness(g, lambda: setattr(p, "evidence_refs", []))
    return g.run(p, executor=GOOD, approver=APPROVE), l


def c21():
    """Reconciliation mismatch: executor reports a different observed outcome."""
    g, _, l, a, _ = stack()

    def BAD(p):
        CALLS["n"] += 1
        return {"observed_outcome": "something else entirely",
                "result_class": "negative"}
    return g.run(proposal(a.passport_id), executor=BAD, approver=APPROVE), l


def c25():
    g, _, l, a, _ = stack()
    return g.run(proposal(a.passport_id, target="gopher://unknown.invalid/x"),
                 executor=GOOD, approver=APPROVE), l


def c26():
    g, _, l, a, _ = stack()
    return g.run(proposal(a.passport_id, requested_capability="nonexistent.capability",
                          action_class="nonexistent.capability"),
                 executor=GOOD, approver=APPROVE), l


def c27():
    """Attempt to increase authority: escalate consequence class after approval."""
    return _mut("consequence_class", "irreversible")()


def c28():
    """Cross-organ use: a grant issued for actor A redeemed by actor B."""
    g, passports, l, a, _ = stack()
    b = passports.issue(kind="agent", creator="alfonso", owner_organ="daleobanks",
                        legal_principal="alfonso_lopez",
                        declared_capabilities=["draft.publish"],
                        budget_ceiling_usd=5.0, consequence_class="external_contact")
    pa = proposal(a.passport_id)
    r1 = g.run(pa, executor=GOOD, approver=APPROVE)
    sg = g.grants.get(r1.grant_id)
    sg["revoked"] = False
    g.grants._meta[sg["grant_id"]]["used"] = False   # give it the best chance
    pb = proposal(b.passport_id)
    return g.run(pb, executor=GOOD, approver=APPROVE, standing_grant=sg), l


def c30():
    """Concurrent redemption race on one single-use standing grant."""
    import threading
    g, _, l, a, _ = stack()
    p = proposal(a.passport_id)
    r1 = g.run(p, executor=GOOD, approver=APPROVE)
    sg = g.grants.get(r1.grant_id)
    g.grants._meta[sg["grant_id"]]["used"] = False
    CALLS["n"] = 0
    states, lock = [], threading.Lock()

    def go():
        r = g.run(p, executor=GOOD, approver=APPROVE, standing_grant=sg)
        with lock:
            states.append(r.state)
    ts = [threading.Thread(target=go) for _ in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]

    class R:
        state = "recorded" if states.count("recorded") > 1 else "refused"
        trajectory = [{"detail": {"reasons": [f"states={states} executor_calls={CALLS['n']}"]}}]
    return R(), l


for cid, nm, exp, fn in [
    (1, "Valid approved effect", "PERMIT", c01),
    (2, "Missing approval", "REFUSE", c02),
    (6, "Expired grant", "REFUSE", c06),
    (7, "Revoked grant", "REFUSE", c07),
    (9, "Exhausted bounded-use grant", "REFUSE", c09),
    (10, "Payload mutation after approval", "REFUSE", c10),
    (11, "Target mutation after approval", "REFUSE", c11),
    (12, "Action-class mutation after approval", "REFUSE", c12),
    (14, "Budget change after approval", "REFUSE", c14),
    (15, "Evidence removed after approval", "REFUSE", c15),
    (16, "Legal-principal mismatch", "REFUSE", c16),
    (17, "Commit-time state drift", "REFUSE", c17),
    (21, "Reconciliation mismatch", "REFUSE", c21),
    (25, "Unknown external target", "REFUSE", c25),
    (26, "Unknown capability", "REFUSE", c26),
    (27, "Attempt to increase authority", "REFUSE", c27),
    (28, "Grant used through another organ", "REFUSE", c28),
    (30, "Concurrent redemption race", "REFUSE", c30),
]:
    run(cid, nm, exp, fn)

# Cases main cannot express -------------------------------------------------
absent(3, "Approval signed by the wrong principal", "REFUSE",
       "approvals are an in-process Python callable `approver(proposal, reasons) -> (bool, str)`. "
       "There is no signed approval artifact, no approver identity and no signature to check.")
absent(4, "Forged approval", "REFUSE",
       "same cause: nothing is signed, so nothing can be forged or verified. Any caller holding "
       "a reference to the gate can pass an approver that returns True.")
absent(5, "Expired approval", "REFUSE",
       "the 72h APPROVAL_TTL constant exists but applies to the pending_human wait, not to a "
       "durable approval artifact; there is no approval object carrying an expiry.")
absent(8, "Replayed grant/approval", "REFUSE",
       "no nonce and no approval artifact to replay. Grant replay is covered by case 9 "
       "(single_use), but there is no approval-level replay defence.")
absent(13, "Policy-version drift", "REFUSE",
       "policy_version is recorded on the witness and the grant but is NOT part of "
       "bound_effect_hash, which covers only {payload, target, action_class}. Commit-time "
       "revalidation re-runs evaluate() against the CURRENT compiled constitution, so a "
       "version change is not itself detected as drift.")
absent(18, "Missing commit witness", "REFUSE",
       "the executor is an arbitrary callable invoked by the gate; it receives the proposal, "
       "not the witness. There is no adapter boundary that could demand a witness, so "
       "'execution without a witness' cannot be posed to this implementation.")
absent(19, "Missing receipt", "REFUSE",
       "the receipt is written by the gate itself after execution; no separate component "
       "returns one, so its absence is not a reachable state.")
absent(20, "Receipt mismatch / forged receipt", "REFUSE",
       "receipts are appended by the gate to its own ledger and are never signed by an "
       "external adapter. With symmetric HMAC there is no key the gate holds that an "
       "adapter could fail to hold.")
absent(22, "Kernel unavailable", "REFUSE",
       "the gate runs in-process; there is no remote authority whose absence could be simulated.")
absent(23, "Local KillSwitch active", "REFUSE",
       "no KillSwitch concept in the kernel root. It exists only in DALEOBANKS.")
absent(24, "Constitution hash mismatch", "REFUSE",
       "constitution_hash is carried on the witness and the ledger, but revalidation "
       "recompiles from the same on-disk source; a mismatch between an approved hash and a "
       "commit-time hash is not a state this implementation can enter.")
absent(29, "Duplicate grant identifiers", "REFUSE",
       "grant_id is a uuid4 generated inside GrantIssuer; a caller cannot supply one, so a "
       "collision cannot be posed without editing the issuer.")

json.dump(RESULTS, sys.stdout, indent=2)
