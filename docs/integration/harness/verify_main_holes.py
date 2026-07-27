"""Targeted verification of the four PERMIT results on `main` that would be
authority defects if real. Each is checked directly, not via the harness.
"""
import os
from policy.consequence_gate import ConsequenceGate
from policy.engine import Proposal, Verdict, evaluate
from compiler.ucl_compiler import compile_constitution
from identity.machine_passport import PassportRegistry
from provenance.commit_witness import WitnessSigner
from provenance.ledger import EvidenceLedger

ROOT = os.environ["MAIN_ROOT"]
CALLS = {"n": 0}


def stack():
    compiled = compile_constitution(ROOT)
    p = PassportRegistry()
    g = ConsequenceGate(compiled=compiled, passports=p,
                        ledger=EvidenceLedger(compiled.constitution_hash),
                        signer=WitnessSigner(env="development"))
    a = p.issue(kind="agent", creator="alfonso", owner_organ="uniimente-kernel",
                legal_principal="alfonso_lopez",
                declared_capabilities=["draft.publish"],
                budget_ceiling_usd=5.0, consequence_class="external_contact")
    return g, p, a, compiled


def prop(actor, **kw):
    d = dict(actor=actor, legal_principal="alfonso_lopez", action_class="draft.publish",
             objective="o", payload={"text": "hi"}, target="sandbox:outbox",
             consequence_class="external_contact", evidence_confidence=0.9,
             evidence_refs=["sha256:" + "a" * 64], estimated_cost_usd=0.0,
             requested_capability="draft.publish", expected_outcome="draft queued")
    d.update(kw)
    return Proposal(**d)


def EX(p):
    CALLS["n"] += 1
    return {"observed_outcome": "draft queued", "result_class": "positive"}


print("=" * 78)
print("CASE 2 — is 'missing approval' a real bypass, or did policy simply ALLOW?")
g, _, a, compiled = stack()
p = prop(a.passport_id)
d = evaluate(compiled, p, identity_ok=True, grant=None, thresholds=None)
print(f"  external_contact @0.9 evidence -> verdict={d.verdict}")
print("  => approver=None is legitimately unnecessary here; NOT a bypass.")

# Now force a class that must have a human.
p2 = prop(a.passport_id, consequence_class="irreversible")
d2 = evaluate(compiled, p2, identity_ok=True, grant=None, thresholds=None)
print(f"  irreversible -> verdict={d2.verdict}")
CALLS["n"] = 0
r = g.run(p2, executor=EX, approver=None)
print(f"  gate.run(irreversible, approver=None) -> state={r.state!r} executor_ran={CALLS['n']}")
print(f"  => VERDICT: {'fails closed, correct' if r.state != 'recorded' else 'BYPASS'}")

print()
print("=" * 78)
print("CASE 26 — can an actor execute a capability it was never granted?")
g, _, a, _ = stack()
print(f"  actor declared_capabilities = {a.declared_capabilities}")
CALLS["n"] = 0
r = g.run(prop(a.passport_id, requested_capability="funds.transfer",
               action_class="funds.transfer"), executor=EX, approver=lambda p, w: (True, "ok"))
print(f"  requested_capability='funds.transfer' -> state={r.state!r} executor_ran={CALLS['n']}")
print(f"  => {'PERMITTED an undeclared capability' if r.state == 'recorded' else 'refused'}")

print()
print("=" * 78)
print("CASE 27 — authority escalation after approval (consequence_class raised)")
g, _, a, _ = stack()
p = prop(a.passport_id)
orig = g.signer.sign


def esc(w):
    p.consequence_class = "irreversible"     # escalate in the commit window
    return orig(w)


g.signer.sign = esc
CALLS["n"] = 0
r = g.run(p, executor=EX, approver=lambda pr, w: (True, "approved as external_contact"))
print(f"  approved as external_contact, escalated to irreversible before commit")
print(f"  -> state={r.state!r} executor_ran={CALLS['n']}")
d3 = evaluate(compiled, p, identity_ok=True, grant=None, thresholds=None)
print(f"  evaluate(escalated) would say: {d3.verdict}")
print("  NOTE: _reauthorize_at_commit refuses only on Verdict.DENY, not REQUIRE_HUMAN.")
print(f"  => {'ESCALATION NOT CAUGHT' if r.state == 'recorded' else 'caught'}")

print()
print("=" * 78)
print("CASE 28 — cross-actor grant redemption")
g, passports, a, _ = stack()
b = passports.issue(kind="agent", creator="alfonso", owner_organ="daleobanks",
                    legal_principal="alfonso_lopez",
                    declared_capabilities=["draft.publish"],
                    budget_ceiling_usd=5.0, consequence_class="external_contact")
r1 = g.run(prop(a.passport_id), executor=EX, approver=lambda p, w: (True, "ok"))
sg = g.grants.get(r1.grant_id)
print(f"  grant grantee            = {sg['grantee']}")
print(f"  actor B passport         = {b.passport_id}")
g.grants._meta[sg["grant_id"]]["used"] = False
CALLS["n"] = 0
r2 = g.run(prop(b.passport_id), executor=EX, approver=lambda p, w: (True, "ok"),
           standing_grant=sg)
print(f"  B redeems A's grant -> state={r2.state!r} executor_ran={CALLS['n']}")
print(f"  bound_effect_hash covers: payload, target, action_class  (NOT actor/grantee)")
print(f"  => {'CROSS-ACTOR REDEMPTION PERMITTED' if r2.state == 'recorded' else 'refused'}")
