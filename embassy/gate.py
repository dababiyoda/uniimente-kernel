"""Layer 7 — the Agent Embassy: the institution's frontier for foreign agents.

Doctrine (EMBASSY): foreign agents (MCP/A2A) never touch the interior.
They present themselves at the embassy; the embassy issues a short-lived
guest passport (kind "connector"), with minimum privilege by default:
zero budget, consequence ceiling internal_write, TTL ≤ 3600s. Every
guest request is re-expressed as a Proposal and routed through the
Consequence Gate — guests get no path around the gate, ever.

The legal operator stands as legal principal for admitted guests; the
institution itself never is.
"""
from __future__ import annotations

from identity.machine_passport import PassportError

GUEST_CEILING = "internal_write"
GUEST_FORBIDDEN_CLASSES = ("external_contact", "financial", "irreversible")
GUEST_TTL_CEILING_S = 3600


class EmbassyRefused(ValueError):
    """The embassy refuses: the request exceeds guest privilege."""


class AgentEmbassy:
    def __init__(self, passports, gate, ledger, *, operator: str = "alfonso_lopez"):
        self.passports = passports
        self.gate = gate
        self.ledger = ledger
        self.operator = operator

    def _log(self, kind: str, payload: dict) -> None:
        self.ledger.append("event", {"type": f"embassy.{kind}", **payload})

    def present(self, *, foreign_id: str, origin: str,
                declared_capabilities: list[str], requested_ttl_s: int = 3600):
        """Admit a foreign agent as a guest. Minimum privilege by construction."""
        ttl = min(requested_ttl_s, GUEST_TTL_CEILING_S)
        try:
            passport = self.passports.issue(
                kind="connector", creator=f"embassy:{origin}",
                owner_organ="embassy", legal_principal=self.operator,
                declared_capabilities=declared_capabilities,
                budget_ceiling_usd=0.0, consequence_class=GUEST_CEILING,
                ttl_seconds=ttl)
        except PassportError as e:
            self._log("admission_refused", {"foreign_id": foreign_id, "error": str(e)})
            raise EmbassyRefused(str(e))
        self._log("admitted", {"foreign_id": foreign_id, "passport_id": passport.passport_id,
                               "ceiling": GUEST_CEILING, "ttl_s": ttl})
        return passport

    def request(self, passport_id: str, proposal, *, executor):
        """Route a guest request through the Consequence Gate — or refuse early."""
        ok, _ = self.passports.verify(passport_id)
        if not ok:
            self._log("request_refused", {"passport_id": passport_id, "reason": "identity invalid"})
            raise EmbassyRefused("guest identity invalid or expired")
        if proposal.consequence_class in GUEST_FORBIDDEN_CLASSES:
            self._log("request_refused", {"passport_id": passport_id,
                                          "reason": f"guests may not attempt {proposal.consequence_class}"})
            raise EmbassyRefused(f"guest consequence ceiling is {GUEST_CEILING}; "
                                 f"{proposal.consequence_class} refused at the embassy")
        if proposal.estimated_cost_usd > 0:
            self._log("request_refused", {"passport_id": passport_id,
                                          "reason": "guests carry zero budget"})
            raise EmbassyRefused("guests carry zero budget; cost-bearing requests refused")
        rec = self.gate.run(proposal, executor=executor)
        self._log("request_routed", {"passport_id": passport_id, "state": rec.state,
                                     "action_id": rec.action_id})
        return rec
