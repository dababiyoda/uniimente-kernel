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


def credits_conserved(organ) -> bool:
    """No branch, relay, widening round or exhaustion reply may mint credit.

    A need's remaining credit can never exceed what it started with, and can
    never go negative -- either would mean the end-to-end budget was not a
    budget.
    """
    for u in organ.units.values():
        for st in u._search.values():
            init = st.get("initial_credits", 0.0)
            left = st.get("credits", 0.0)
            if left < -1e-9 or left > init + 1e-9:
                return False
    return True


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
