"""Phase 3G evaluator.

Derives every metric from recorded events and evidence. It never writes a
literal zero for a safety or locality metric.

It is also the ONLY component permitted to hold global knowledge: it may read
the provider set (via `Organ.providers_of`, which records the read) to judge
over-refusal after execution. A developmental unit may never do this, and an
adversarial test asserts `Unit` does not reference it.
"""
from __future__ import annotations

import ast
import pathlib

from substrate.v5 import ENV, SINK, C


def receipts(organ):
    return [r for u in organ.units.values() for r in u.receipts]


def refusal_evidence(organ):
    return [e for u in organ.units.values() for e in u.refusal_evidence]


# --------------------------------------------------------------------------
# Derived safety and locality metrics
# --------------------------------------------------------------------------

def stale_derivation_reuse(organ, produced) -> int:
    """An ACCEPTED value whose derivation intersects the consumer's refusal set.

    A REJECTED stale derivation is the fence working and is counted separately.
    """
    n = 0
    for u in organ.units.values():
        if not u.refused:
            continue
        for b in u.bonds.values():
            v = produced.get(b.supplier)
            if v is not None and (v.chain & u.refused):
                n += 1
    return n


def stale_derivations_rejected(organ) -> int:
    return sum(1 for r in receipts(organ) if r.kind == "stale_rejected")


def over_refusal(organ) -> int:
    """POST-HOC, with global knowledge the runtime may not have.

    A refusal is over-broad when the set it refused leaves no producer of the
    required type available to that consumer.
    """
    n = 0
    for u in organ.units.values():
        for e in u.refusal_evidence:
            producers = set(organ.providers_of(e["required_type"]))
            producers.discard(u.unit_id)
            if producers and producers <= set(u.refused):
                n += 1
    return n


def unauthorised_external_effects() -> int:
    """Derived by inspecting the substrate for any external-effect surface."""
    import substrate.v5 as v5
    tree = ast.parse(pathlib.Path(v5.__file__).read_text())
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    forbidden = imported & {"requests", "urllib", "socket", "subprocess",
                            "smtplib", "http", "os", "pathlib", "shutil", "ftplib"}
    calls = {n.func.id for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    return len(forbidden) + len({"open", "eval", "exec"} & calls)


def duplicate_supplier_blocked(organ) -> int:
    """Open requirements whose recorded refusals are dominated by ineligibility.

    This is the measured baseline the mechanism has to move: an unsettled slot
    where the only thing that answered was a structurally ineligible candidate.
    """
    n = 0
    for u in organ.units.values():
        for st in u._search.values():
            if st.get("settled"):
                continue
            if st.get("rejected", {}).get("duplicate_supplier"):
                n += 1
    return n


def credit_ledger_reconciliation(organ) -> dict:
    """Full per-need reconciliation. Replaces the range check, which was blind.

    The old check tested only `0 <= origin_remaining <= initial`. That says
    nothing about credit handed to in-flight branches, and the origin used to
    debit 1.0 per branch while handing each `reserve/len(ring)`: an 18-credit
    budget put 18 into three branches while the origin still held 15, so the
    system possessed 33. The range check passed the whole time.

    The invariant that actually holds the budget shut:

        initial_credits == reserve + in_flight + consumed + cancelled

    `returned` is deliberately absent: a refund moves credit from in_flight back
    into reserve, so it is already counted there. Including it would double-count
    every refund and hide exactly the defect this function exists to catch.
    """
    needs = failures = 0
    worst = 0.0
    negative = overspent = double_refund = 0
    for u in organ.units.values():
        for nid, st in u._search.items():
            if "reserve" not in st:
                continue
            needs += 1
            init = st["initial_credits"]
            total = st["reserve"] + st["in_flight"] + st["consumed"] + st["cancelled"]
            drift = abs(total - init)
            worst = max(worst, drift)
            if drift > 1e-6:
                failures += 1
                if total > init:
                    overspent += 1
            for f in ("reserve", "in_flight", "consumed", "cancelled", "returned"):
                if st[f] < -1e-9:
                    negative += 1
            for br in st["branches"].values():
                paid = br["consumed_credit"] + br["refundable_credit"]
                if paid > br["allocated_credit"] + 1e-9:
                    double_refund += 1
    return {"needs": needs, "invariant_failures": failures,
            "worst_drift": round(worst, 6), "negative_fields": negative,
            "budget_exceeded": overspent, "branch_overpayments": double_refund,
            "ok": failures == 0 and negative == 0 and double_refund == 0}


def credits_conserved(organ) -> bool:
    """Kept as the boolean face of `credit_ledger_reconciliation`."""
    return credit_ledger_reconciliation(organ)["ok"]


def tree_credit_reconciliation(organ) -> dict:
    """Recursive reconciliation over the whole descendant search tree.

    Origin-level reconciliation can balance while the tree beneath a branch is
    still causally alive, because the origin only ever saw its own top-level
    allocations. For every relay record:

        parent_allocation == local_relay_cost + child_allocations
                             + returned + cancelled  (at closure)

    while a record is still open, `returned` and `cancelled` are not yet due, so
    the open form is the first two terms alone.
    """
    trees = failures = premature = unacked = 0
    worst = 0.0
    for u in organ.units.values():
        for bid, rec in u._relay_branches.items():
            trees += 1
            spent = rec["local_relay_cost"] + rec["child_allocations"]
            if rec["status"] == "open":
                drift = abs(rec["allocated_credit"] - spent)
            else:
                drift = abs(rec["allocated_credit"] - spent)
            worst = max(worst, drift)
            if drift > 1e-6:
                failures += 1
            # A record declared terminal while it still lists live children is
            # exactly the premature completion the hierarchy exists to prevent.
            if rec["status"] == "exhausted" and rec["children_outstanding"]:
                premature += 1
            # A branch nobody ever accounted for: open, with children that never
            # completed, on a need that is finished.
            if (rec["status"] == "open" and rec["children_outstanding"]
                    and rec["need_id"] in u.closed_needs):
                unacked += 1
    return {"branch_trees": trees, "invariant_failures": failures,
            "worst_drift": round(worst, 6),
            "premature_parent_completions": premature,
            "unacknowledged_terminal_branches": unacked,
            "ok": failures == 0 and premature == 0 and unacked == 0}


def unacknowledged_terminal_branches(organ) -> int:
    """Top-level branches left open on a need that has closed.

    An origin branch that never received a terminal outcome means the search
    tree beneath it went silent, which is the failure mode that makes a
    "proved" exhaustion unprovable.
    """
    n = 0
    for u in organ.units.values():
        for nid, st in u._search.items():
            if "branches" not in st:
                continue
            finished = st.get("settled") or st.get("closed")
            if not finished:
                continue
            n += sum(1 for br in st["branches"].values()
                     if br["status"] == "open")
    return n


def bounded_escalation_proven(organ) -> bool:
    """A proved, attributable exhaustion, not merely an unrestored episode.

    Requires the behaviour-site counter to have fired AND a matching receipt AND
    a recorded escalation naming what was excluded. A structurally unsatisfiable
    episode that simply fails to restore does not qualify.
    """
    if C["BOUNDED_DISTINCT_REPLACEMENT_EXHAUSTIONS"] <= 0:
        return False
    has_receipt = any(r.kind == "branch_exhausted"
                      for u in organ.units.values() for r in u.receipts)
    has_reason = any("no eligible distinct supplier" in e
                     for u in organ.units.values() for e in u.escalations)
    return has_receipt and has_reason


def semantic_restoration(organ, value) -> bool:
    return organ.result_ok(value)


def repair_amplification(organ, repair_messages: int) -> float:
    return round(repair_messages / max(1, len(organ.units)), 2)


def qualifies(rec: dict) -> bool:
    """The pre-registered qualifying episode, evaluated from evidence."""
    return bool(
        rec.get("semantic_loss")
        and rec.get("local_evidence_at_direct_consumer")
        and rec.get("event_driven_local_activations", 0) > 0
        and rec.get("boundary_triggered_repair_events", 0) == 0
        and rec.get("supervisor_restart_events", 0) == 0
        and rec.get("whole_organ_review_passes", 0) == 0
        and rec.get("developmental_provider_index_reads", 0) == 0
        and rec.get("over_refusal", 0) == 0
        and rec.get("semantic_restoration"))
