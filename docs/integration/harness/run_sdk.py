"""Differential authority conformance — phase7 SDK gate runner.

The SDK gate consumes a pre-minted grant. It never consults a constitution,
an identity registry, or a human approver, so a large block of the corpus is
structurally ABSENT for it. What it DOES have that neither other engine has:
a KillSwitch, named_targets, permitted_actions, and fingerprint dedup.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

from uniimente_kernel.capability import (CapabilityError, CapabilityService,
                                         GrantRecord, InMemoryGrantStore)
from uniimente_kernel.gate import ConsequenceGate
from uniimente_kernel.ledger import DecisionLedger
from uniimente_kernel.commit_witness import CommitWitness, KillSwitch
from uniimente_kernel.events import EventSpine

ORG = "spiffe://uniimente.internal/organ/daleobanks"
AGENT = ORG + "/agent/publisher"
IMPL = "phase7_sdk_uniimente_kernel_gate"
RESULTS = []


def record(cid, name, exp, verdict, reason="", executed=None, note=""):
    RESULTS.append({"case_id": cid, "case": name, "implementation": IMPL,
                    "doctrinal_expectation": exp, "verdict": verdict,
                    "refusal_reason": reason, "executor_ran": executed,
                    "chain_verifies": None, "note": note})


def absent(cid, name, exp, reason):
    record(cid, name, exp, "ABSENT", reason, None,
           "structurally inexpressible in this implementation")


class World:
    def __init__(self, armed=True, approval=lambda rid: True):
        self.d = tempfile.TemporaryDirectory()
        self.ledger = DecisionLedger(path=os.path.join(self.d.name, "l.jsonl"))
        self.store = InMemoryGrantStore()
        self.cap = CapabilityService(self.store, self.ledger,
                                     approval_verifier=approval)
        self.applied = []
        self.sw = KillSwitch(ledger=self.ledger, apply=self.applied.append,
                             initially_armed=armed)
        self.witness = CommitWitness(self.ledger, kill_switch=self.sw)
        self.spine = EventSpine(self.ledger, source=ORG, actor=AGENT,
                                legal_principal="alfonso-lopez",
                                policy_version="1.0.0")
        self.gate = ConsequenceGate(self.ledger, capability=self.cap,
                                    witness=self.witness, spine=self.spine)
        self.calls = 0

    def mint(self, **kw):
        f = dict(grantee=AGENT, granted_by="alfonso-lopez",
                 legal_actor="alfonso-lopez", objective="publish one draft",
                 permitted_actions=["publish.post"], resource="draft-1",
                 spending_limit_usd=25.0, maximum_uses=3, named_targets=[],
                 initial_stage="shadow")
        f.update(kw)
        return self.cap.mint(GrantRecord(**f), approval_request_id="a1")

    def go(self, grant_id, **kw):
        def ex():
            self.calls += 1
            return {"ok": True}
        f = dict(grant_id=grant_id, action_type="publish.post",
                 resource="draft-1", executor=ex)
        f.update(kw)
        return self.gate.execute(**f)


def run(cid, name, exp, fn, note=""):
    try:
        w, res = fn()
        if getattr(res, "status", None) in ("committed",):
            record(cid, name, exp, "PERMIT", "", w.calls, note)
        else:
            record(cid, name, exp, "REFUSE",
                   f"status={getattr(res,'status',res)}: {getattr(res,'error','')}"[:280],
                   w.calls, note)
    except CapabilityError as e:
        record(cid, name, exp, "REFUSE", f"CapabilityError: {e}"[:280], None, note)
    except Exception as e:  # noqa: BLE001
        record(cid, name, exp, "ERROR", f"{type(e).__name__}: {e}"[:280], None, note)


def c01():
    w = World(); g = w.mint(); return w, w.go(g.grant_id)


def c07():
    w = World(); g = w.mint()
    w.cap.revoke(g.grant_id, revoked_by="alfonso-lopez", reason="test")
    return w, w.go(g.grant_id)


def c09():
    w = World(); g = w.mint(maximum_uses=1)
    w.go(g.grant_id)
    return w, w.go(g.grant_id, resource="draft-1", action_type="publish.post")


def c08():
    """Fingerprint replay: identical effect submitted twice."""
    w = World(); g = w.mint(maximum_uses=3)
    w.go(g.grant_id)
    return w, w.go(g.grant_id)


def c11():
    w = World(); g = w.mint(named_targets=["approved.example"])
    return w, w.go(g.grant_id, target="https://evil.example/exfil")


def c14():
    w = World(); g = w.mint(spending_limit_usd=1.0)
    return w, w.go(g.grant_id, cost=10_000.0)


def c23():
    """KillSwitch disarmed -> execution must not proceed."""
    w = World(armed=False); g = w.mint()
    res = w.go(g.grant_id)
    # KillSwitch semantics: armed=True permits live effects; the switch
    # "starts disarmed and never arms itself" (fail-safe toward silence).
    # Running here with armed=False and observing execution is the finding.
    return w, res


def c25():
    w = World(); g = w.mint(named_targets=["approved.example"])
    return w, w.go(g.grant_id, target="gopher://unknown.invalid/x")


def c26():
    w = World(); g = w.mint(permitted_actions=["publish.post"])
    return w, w.go(g.grant_id, action_type="funds.transfer")


def c27():
    """Widen authority: act on a resource the grant does not name."""
    w = World(); g = w.mint(resource="draft-1")
    return w, w.go(g.grant_id, resource="the-entire-treasury")


def c02():
    """Mint without a verified approval."""
    w = World(approval=lambda rid: False)
    try:
        g = w.mint()
        return w, w.go(g.grant_id)
    except CapabilityError as e:
        raise


def c29():
    """Duplicate grant identifier: mint, then re-add a grant with the same id."""
    w = World(); g1 = w.mint()
    try:
        w.store.add(g1)
        return w, w.go(g1.grant_id)
    except Exception as e:
        raise CapabilityError(f"duplicate grant id rejected by store: {e}")


for cid, nm, exp, fn in [
    (1, "Valid approved effect", "PERMIT", c01),
    (2, "Missing approval", "REFUSE", c02),
    (7, "Revoked grant", "REFUSE", c07),
    (8, "Replayed grant/approval", "REFUSE", c08),
    (9, "Exhausted bounded-use grant", "REFUSE", c09),
    (11, "Target mutation after approval", "REFUSE", c11),
    (14, "Budget change after approval", "REFUSE", c14),
    (23, "Local KillSwitch active", "REFUSE", c23),
    (25, "Unknown external target", "REFUSE", c25),
    (26, "Unknown capability", "REFUSE", c26),
    (27, "Attempt to increase authority", "REFUSE", c27),
    (29, "Duplicate grant identifiers", "REFUSE", c29),
]:
    run(cid, nm, exp, fn)

NO_LAW = ("the SDK gate never consults a constitution, policy engine, identity "
          "registry or human approver; it consumes a grant that some other "
          "authority already minted")
absent(3, "Approval signed by the wrong principal", "REFUSE",
       "approval is a `approval_verifier(request_id) -> bool` callable supplied by the "
       "caller. No approver identity, no signature. " + NO_LAW)
absent(4, "Forged approval", "REFUSE", "nothing is signed; see case 3. " + NO_LAW)
absent(5, "Expired approval", "REFUSE", "no approval artifact carries an expiry. " + NO_LAW)
absent(6, "Expired grant", "REFUSE",
       "grants carry a TTL at mint, but this runner could not drive the clock past it "
       "without patching time; not claimed either way.")
absent(10, "Payload mutation after approval", "REFUSE",
       "parameters feed the action fingerprint, so a mutation yields a DIFFERENT "
       "fingerprint and is treated as a new effect rather than a refusal. There is no "
       "approved baseline to diverge from, because the gate never saw an approval.")
absent(12, "Action-class mutation after approval", "REFUSE",
       "covered as 'unknown capability' (case 26): there is no approved class to mutate away from.")
absent(13, "Policy-version drift", "REFUSE",
       "policy_version is stamped on emitted events but is not bound into the grant or "
       "the fingerprint, and nothing revalidates it.")
absent(15, "Evidence removed after approval", "REFUSE",
       "evidence_refs are carried on events for provenance only; no evidence store, no "
       "freshness rule, nothing to remove.")
absent(16, "Legal-principal mismatch", "REFUSE",
       "legal_principal is EventSpine construction metadata, not a checked binding.")
absent(17, "Commit-time state drift", "REFUSE",
       "there is no PROPOSE/COMMIT separation: execute() is a single call, so no window "
       "exists in which state could drift.")
absent(18, "Missing commit witness", "REFUSE",
       "the CommitWitness is a constructor dependency of the gate; a caller cannot invoke "
       "the executor through the gate without it.")
absent(19, "Missing receipt", "REFUSE", "the witness always returns a receipt on every path.")
absent(20, "Receipt mismatch / forged receipt", "REFUSE",
       "receipts are produced in-process by the witness and are unsigned; there is no "
       "external adapter whose key could mismatch.")
absent(21, "Reconciliation mismatch", "REFUSE",
       "reconciliation is a SEPARATE later call, record_outcome(); execute() neither "
       "compares nor blocks on expected-vs-observed.")
absent(22, "Kernel unavailable", "REFUSE",
       "despite the name, this SDK embeds its own in-process authority objects; there is "
       "no remote kernel to be unavailable. This is exactly the second-authority hazard.")
absent(24, "Constitution hash mismatch", "REFUSE", "no constitution is loaded at all. " + NO_LAW)
absent(28, "Grant used through another organ", "REFUSE",
       "the grant records a `grantee`, but execute() takes no actor argument, so the "
       "caller's identity is never compared against it. Any holder of the grant_id is "
       "treated as the grantee.")
absent(30, "Concurrent redemption race", "REFUSE",
       "not exercised: InMemoryGrantStore has no locking discipline this runner could "
       "test meaningfully without asserting a specific threading model.")

json.dump(RESULTS, sys.stdout, indent=2)
