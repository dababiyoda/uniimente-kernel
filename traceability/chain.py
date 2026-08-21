"""The five-link traceability chain: founder intent -> decision -> action ->
evidence -> outcome.

Doctrine
--------
The Single Bottleneck Metric is:

    Percentage of completed goals that remain traceable from founder intent to
    decision, action, evidence, and outcome without unauthorized external effects.

That sentence is only a metric if every link is a real object in the ledger. This
module walks the links over `provenance.ledger.EvidenceLedger` records and reports
what it finds. It has exactly one hard rule:

    A LINK IS NEVER INFERRED.

If a decision does not name its intent, the intent->decision link is UNRESOLVED.
It does not become resolved because the objectives look similar, because the
timestamps are close, or because only one candidate exists. Fuzzy joins are how a
system starts believing its own unearned continuity. Unresolved is the honest
answer and it is the answer this walker gives.

The walker is read-only. It holds no authority, issues no grants, and cannot
promote, demote or repair anything it inspects.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# The five nodes of the chain, in causal order.
LINKS = ("intent", "decision", "action", "evidence", "outcome")

# An intent claiming this state is claiming completion. The metric audits that
# claim; it does not take it on trust.
COMPLETION_STATE = "implemented"


@dataclass(frozen=True)
class UnresolvedLink:
    """A break in the chain, named precisely enough to be fixed.

    `reason` states what was looked for and what was found. It never speculates
    about what the author meant.
    """
    goal_id: str
    link: str
    reason: str

    def to_dict(self) -> dict:
        return {"goal_id": self.goal_id, "link": self.link, "reason": self.reason}


@dataclass(frozen=True)
class UnauthorizedEffect:
    """An external effect that reached the world without a resolvable authority
    chain. This is the second half of the metric and it is not a rounding error:
    one of these contaminates the institution's claim to governed behaviour.
    """
    action_id: str
    reason: str
    goal_id: str | None = None      # None when the effect belongs to no goal at all

    def to_dict(self) -> dict:
        return {"action_id": self.action_id, "reason": self.reason,
                "goal_id": self.goal_id}


@dataclass
class GoalTrace:
    """One goal's walk through the five links."""
    goal_id: str
    intent: dict | None = None
    decisions: list[dict] = field(default_factory=list)
    actions: list[dict] = field(default_factory=list)       # receipt payloads
    evidence: list[str] = field(default_factory=list)       # resolved evidence hashes
    outcomes: list[dict] = field(default_factory=list)
    unresolved: list[UnresolvedLink] = field(default_factory=list)
    unauthorized_effects: list[UnauthorizedEffect] = field(default_factory=list)

    @property
    def claims_completion(self) -> bool:
        return bool(self.intent) and self.intent.get("state") == COMPLETION_STATE

    @property
    def traceable(self) -> bool:
        """Traceable means every link resolved AND no unauthorized effect was
        attributed to this goal. Both halves of the founder's sentence."""
        return not self.unresolved and not self.unauthorized_effects

    @property
    def broken_links(self) -> list[str]:
        seen, out = {u.link for u in self.unresolved}, []
        for link in LINKS:
            if link in seen:
                out.append(link)
        return out

    def to_dict(self) -> dict:
        return {
            "goal_id": self.goal_id,
            "claims_completion": self.claims_completion,
            "traceable": self.traceable,
            "broken_links": self.broken_links,
            "decisions": len(self.decisions),
            "actions": len(self.actions),
            "evidence": len(self.evidence),
            "outcomes": len(self.outcomes),
            "unresolved": [u.to_dict() for u in self.unresolved],
            "unauthorized_effects": [e.to_dict() for e in self.unauthorized_effects],
        }


class TraceabilityWalker:
    """Walks intent -> decision -> action -> evidence -> outcome over a ledger.

    Read-only by construction: it is handed a ledger and only ever calls
    `by_type` and `find` on it.
    """

    def __init__(self, ledger):
        self.ledger = ledger

    # ------------------------------------------------------------- indexes
    def _payloads(self, record_type: str) -> list[dict]:
        return [r.payload for r in self.ledger.by_type(record_type)
                if isinstance(r.payload, dict)]

    def intents(self) -> list[dict]:
        return [p for p in self._payloads("intent") if "intent_id" in p]

    def _decisions_for(self, intent_id: str) -> list[dict]:
        # Exact match on the declared link only. No objective-similarity join.
        return [p for p in self._payloads("decision")
                if p.get("intent_ref") == intent_id]

    def _receipts_for(self, decision_id: str) -> list[dict]:
        """Receipts linked to a decision by explicit declaration only.

        Two declaration paths, because the Consequence Gate cannot supply the
        first one. `policy/consequence_gate.py` is a frozen continuity artifact
        (evolution/repair/spec.py: CONTINUITY_ARTIFACT_SHA256) required to stay
        byte-identical across disable, install and rollback. Adding a field to
        the receipt it writes would mutate an authority invariant to buy a
        reporting convenience, so it stays untouched:

          1. `receipt.decision_ref` - honoured if some other writer sets it.
          2. `trace_link` record     - an attributable assertion, made separately,
                                       that a given decision produced a given
                                       action.

        The second path is the better object anyway. A link is a claim by a named
        party at a named time, so it can be added to historical actions without
        rewriting their receipts, and a wrong link is attributable to whoever
        asserted it. Neither path infers anything: no trace_link, no link.
        """
        direct = [p for p in self._payloads("receipt")
                  if p.get("decision_ref") == decision_id]
        seen = {p.get("action_id") for p in direct}

        by_action = {p.get("action_id"): p for p in self._payloads("receipt")}
        linked = []
        for link in self._trace_links():
            if link.get("decision_ref") != decision_id:
                continue
            action_ref = link.get("action_ref")
            if action_ref in seen:
                continue
            receipt = by_action.get(action_ref)
            if receipt is not None:
                seen.add(action_ref)
                linked.append(receipt)
        return direct + linked

    def _trace_links(self) -> list[dict]:
        return [p for p in self._payloads("trace_link")
                if p.get("decision_ref") and p.get("action_ref")]

    def dangling_link_assertions(self) -> list[dict]:
        """trace_link records naming an action with no receipt. Someone asserted
        a consequence that left no trace of having happened."""
        actions = {p.get("action_id") for p in self._payloads("receipt")}
        return [link for link in self._trace_links()
                if link["action_ref"] not in actions]

    def _outcomes_for(self, action_id: str) -> list[dict]:
        return [p for p in self._payloads("outcome")
                if p.get("action_ref") == action_id]

    def _witness_ids(self) -> set[str]:
        return {p["witness_id"] for p in self._payloads("witness")
                if "witness_id" in p}

    # -------------------------------------------------------- authorization
    def _effect_authority_fault(self, receipt: dict) -> str | None:
        """Why this external effect is unauthorized, or None if it is authorized.

        An effect is authorized only when it carries a grant AND a commit witness
        that actually exists in this ledger. A receipt that names a witness the
        ledger has never seen is not 'mostly authorized' — it is unauthorized,
        and it is the more alarming case because it looks authorized.
        """
        if not receipt.get("grant_id"):
            return "receipt carries no grant_id: external effect with no capability grant"
        witness_id = receipt.get("witness_id")
        if not witness_id:
            return "receipt carries no witness_id: external effect with no commit witness"
        if witness_id not in self._witness_ids():
            return (f"receipt names witness {witness_id!r} which is absent from the "
                    "ledger: the authority chain cannot be reconstructed")
        return None

    def unattributed_effects(self) -> list[UnauthorizedEffect]:
        """Unauthorized external effects that belong to no goal at all.

        These are the worst class: nobody asked for them, so no goal's score is
        harmed by them and they would otherwise be invisible to the metric.
        """
        claimed: set[str] = set()
        for intent in self.intents():
            for decision in self._decisions_for(intent["intent_id"]):
                for receipt in self._receipts_for(decision.get("decision_id", "")):
                    if receipt.get("action_id"):
                        claimed.add(receipt["action_id"])

        out = []
        for receipt in self._payloads("receipt"):
            action_id = receipt.get("action_id")
            if action_id in claimed:
                continue
            fault = self._effect_authority_fault(receipt)
            if fault is not None:
                out.append(UnauthorizedEffect(action_id=action_id or "<no action_id>",
                                              reason=fault, goal_id=None))
        return out

    # ---------------------------------------------------------------- walk
    def trace(self, intent_id: str) -> GoalTrace:
        """Walk one goal. Every failure to resolve is recorded, never patched."""
        trace = GoalTrace(goal_id=intent_id)

        # Link 1 — intent
        intent = next((i for i in self.intents() if i["intent_id"] == intent_id), None)
        if intent is None:
            trace.unresolved.append(UnresolvedLink(
                intent_id, "intent",
                "no IntentRecord with this intent_id exists in the ledger"))
            return trace
        trace.intent = intent

        # An intent may only claim 'implemented' against something that enforces
        # it. This is a claim check, not a chain break, but it breaks the intent
        # link because the first node is itself false.
        if intent.get("state") == COMPLETION_STATE and not intent.get("implementation_refs"):
            trace.unresolved.append(UnresolvedLink(
                intent_id, "intent",
                "state is 'implemented' but implementation_refs is empty: "
                "completion is claimed with nothing enforcing it"))

        # Link 2 — decision
        trace.decisions = self._decisions_for(intent_id)
        if not trace.decisions:
            trace.unresolved.append(UnresolvedLink(
                intent_id, "decision",
                "no decision record names this intent in intent_ref"))
            return trace

        # Links 3, 4, 5 — action, evidence, outcome (per decision)
        for decision in trace.decisions:
            decision_id = decision.get("decision_id", "")

            # Link 4 — evidence. Checked per decision: a decision resting on
            # evidence refs that resolve to nothing is resting on nothing.
            refs = decision.get("evidence_refs") or []
            if not refs:
                trace.unresolved.append(UnresolvedLink(
                    intent_id, "evidence",
                    f"decision {decision_id!r} cites no evidence_refs"))
            for ref in refs:
                if self.ledger.find(ref) is None:
                    trace.unresolved.append(UnresolvedLink(
                        intent_id, "evidence",
                        f"decision {decision_id!r} cites evidence {ref!r} "
                        "which does not resolve to any ledger record"))
                else:
                    trace.evidence.append(ref)

            # Link 3 — action
            receipts = self._receipts_for(decision_id)
            if not receipts:
                trace.unresolved.append(UnresolvedLink(
                    intent_id, "action",
                    f"no receipt names decision {decision_id!r} in decision_ref: "
                    "the decision produced no recorded external action"))
                continue
            trace.actions.extend(receipts)

            for receipt in receipts:
                action_id = receipt.get("action_id", "")

                fault = self._effect_authority_fault(receipt)
                if fault is not None:
                    trace.unauthorized_effects.append(UnauthorizedEffect(
                        action_id=action_id or "<no action_id>",
                        reason=fault, goal_id=intent_id))

                # Link 5 — outcome
                outcomes = self._outcomes_for(action_id)
                if not outcomes:
                    trace.unresolved.append(UnresolvedLink(
                        intent_id, "outcome",
                        f"action {action_id!r} has no outcome record: the effect "
                        "reached the world and was never reconciled"))
                trace.outcomes.extend(outcomes)

        return trace

    def trace_all(self) -> list[GoalTrace]:
        return [self.trace(i["intent_id"]) for i in self.intents()]
