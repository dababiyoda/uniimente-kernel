"""Case 2 of the operational slice (a subcontractor's progress-payment draw; SYNTHETIC: no real party, payer or
payment): ``case.assess`` read against the case-2 rulebook on the withheld cases, and each reading graded against
the withheld LABELS.json (pre-registered measure 3).

The labels use the SPEC's vocabulary; ``case.assess`` reports in its own. The translation is fixed here, written
before the first case was assessed, and is applied the same way to every case:

* eligibility is the routing state (``route.state``): ``case.assess`` keeps a three-valued ``eligibility`` and holds
  a case as disputed in a separate field, and its routing state carries both;
* a SPEC rule (R1 to R9) is the group of rulebook rules and disputes whose id starts with it: failed if any of them
  is not met, else disputed if a dispute of it is met, else unknown if any of them is unknown, else passed;
* the deciding rules are the failed SPEC rules of an ineligible case, the disputed ones of a disputed case, the
  unknown ones of an undetermined case and all of them of an eligible case (the labels' convention);
* a missing fact is a fact ``unresolved`` names, written with the SPEC's name (FACT_NAMES);
* the payment status is read from ``payment`` (``observed`` is paid; otherwise the reconciliation's reason), and,
  since ``case.assess`` reads the statement whatever the eligibility, is also given gated: not-applicable unless the
  routing state is eligible, which is what the request-case template does (only the settle route asks for payment).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from greg.capabilities import BUILTINS, InvocationContext
from greg.cases import assess

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "request_case" / "progress_draw"
RULEBOOK = FIXTURE / "rulebook.json"
CASES = FIXTURE / "cases"
LABELS = json.loads((FIXTURE / "LABELS.json").read_text(encoding="utf-8"))
REF = "SYN-SC-2026-0417"
CHANNEL = "subcontractor-draws"
COLUMNS = {"reference": "memo"}        # the case-2 statement carries the contract reference in its memo column
SPEC_RULES = [f"R{i}" for i in range(1, 10)]


def _line(x):
    return x.upper().replace("CO0", "CO-0")


def _fact_names() -> dict:
    names = {"sov_ref": "sov.contract_reference", "ret_pct": "sov.retainage_percent",
             "pay_ref": "pay_app.contract_reference", "pay_draw": "pay_app.draw_number",
             "pay_end": "pay_app.period_end_date", "pay_cur": "pay_app.currency (not a SPEC fact)",
             "pay_ret": "pay_app.retainage_withheld", "pay_req": "pay_app.amount_requested",
             "insp_ref": "inspection.contract_reference", "insp_draw": "inspection.draw_or_period",
             "insp_end": "inspection.draw_or_period", "insp_signed": "inspection.signed",
             "punch_open": "inspection.blocking_punch_items", "lw_ref": "lien_waiver.contract_reference",
             "lw_draw": "lien_waiver.draw_number", "lw_amount": "lien_waiver.amount_waived",
             "lw_signed": "lien_waiver.signed", "reg_ref": "register.contract_reference (not a SPEC fact)",
             "acc_decision": "acceptance.decision (not a SPEC fact)"}
    for x in ("l1", "l2", "l3", "l4", "l5"):
        names.update({f"sv_{x}": f"sov.line[{_line(x)}].scheduled_value",
                      f"pc_{x}": f"pay_app.line[{_line(x)}].percent_complete_to_date",
                      f"pb_{x}": f"pay_app.line[{_line(x)}].previously_billed",
                      f"ob_{x}": f"inspection.line[{_line(x)}].observed_percent_complete"})
    for x in ("co01", "co02"):
        names.update({f"sv_{x}": f"sov.change_order[{_line(x)}].amount",
                      f"ok_{x}": f"sov.change_order[{_line(x)}].approved",
                      f"pc_{x}": f"pay_app.line[{_line(x)}].percent_complete_to_date",
                      f"pb_{x}": f"pay_app.line[{_line(x)}].previously_billed",
                      f"ob_{x}": f"inspection.line[{_line(x)}].observed_percent_complete"})
    for k in range(1, 7):
        names[f"pk{k}"] = "inspection.blocking_punch_items"
        names.update({f"s{k}": f"register.draw[{k}].status", f"g{k}": f"register.draw[{k}].gross_billed",
                      f"n{k}": f"register.draw[{k}].net_paid"})
    for x in ("line", "status", "value", "position", "by"):
        names[f"dsp_{x}"] = f"inspection.dispute_{x} (not a SPEC fact)"
    return names


FACT_NAMES = _fact_names()


class NoHistory:
    """A body ledger with nothing on it yet: no request, no earlier case, no receipt."""

    def replay(self, prefix=""):
        return []

    def find(self, record_hash):
        return None


def params(folder: Path, rulebook: Path = RULEBOOK, reference: str = REF) -> dict:
    return {"rulebook": str(rulebook), "rulebook_sha256": hashlib.sha256(rulebook.read_bytes()).hexdigest(),
            "folder": str(folder), "reference": reference, "statement": str(folder / "statement.csv"),
            "columns": COLUMNS}


def read_case(name: str, deliver_root: Path) -> dict:
    """``case.assess`` on one withheld case folder, read in place (the capability is read-only)."""
    ctx = InvocationContext(workspace=deliver_root / "ws", read_roots=(FIXTURE,), secrets=None,
                            manifest=BUILTINS["case.assess"][0], deliver_root=deliver_root, journal=NoHistory(),
                            mission_id="")
    return assess(params(CASES / name), ctx)


def spec_rule(ident: str) -> str:
    return ident.split(".", 1)[0]


def rule_outcomes(a: dict) -> dict:
    out = {}
    for r in SPEC_RULES:
        rules = [x for x in a["rules"] if spec_rule(x["id"]) == r]
        disputes = [d for d in a["dispute_checks"] if spec_rule(d["id"]) == r]
        states = [x["state"] for x in rules + disputes]
        out[r] = ("fail" if "not_met" in [x["state"] for x in rules] else
                  "disputed" if "met" in [d["state"] for d in disputes] else
                  "unknown" if "unknown" in states else "pass")
    return out


def deciding(state: str, outcomes: dict) -> list:
    wanted = {"ineligible": "fail", "disputed": "disputed", "undetermined": "unknown", "eligible": "pass"}[state]
    return [r for r in SPEC_RULES if outcomes[r] == wanted]


def missing(a: dict) -> list:
    return sorted({FACT_NAMES.get(u.split(" from ", 1)[0], u.split(" from ", 1)[0]) for u in a["unresolved"]})


def payment_status(a: dict) -> str:
    payment = a["payment"]
    if payment["state"] == "observed":
        return "paid"
    seen = payment.get("reconcile") or {}
    if seen.get("text_unreadable"):
        return "unknown-unreadable"
    if seen.get("matches", 0) > 1:
        return "unknown-ambiguous"
    if seen.get("exists") is False or seen.get("detail") == "no posting carries the case reference":
        return "unknown-no-statement"
    return f"other: {payment['reason']}"


def grade(name: str, a: dict) -> dict:
    label = LABELS["cases"][name]
    outcomes = rule_outcomes(a)
    state = a["route"]["state"]
    strict = payment_status(a)
    gated = strict if state == "eligible" else "not-applicable"
    labelled = {r: label["rule_outcomes"][r] for r in SPEC_RULES}
    unknown_decided = [r for r in SPEC_RULES if labelled[r] == "unknown" and outcomes[r] in ("pass", "fail")]
    decided_unknown = [r for r in SPEC_RULES if labelled[r] in ("pass", "fail") and outcomes[r] == "unknown"]
    got_missing, want_missing = missing(a), sorted(label["missing_facts"])
    return {
        "case": name, "eligibility": state, "expected_eligibility": label["expected_eligibility"],
        "route": a["route"]["route"], "expected_route": label["expected_route"],
        "deciding": deciding(state, outcomes), "expected_deciding": sorted(label["deciding_rules"]),
        "missing": got_missing, "expected_missing": want_missing,
        "missing_extra": sorted(set(got_missing) - set(want_missing)),
        "missing_absent": sorted(set(want_missing) - set(got_missing)),
        "payment_strict": strict, "payment_gated": gated, "expected_payment": label["expected_payment_status"],
        "rule_outcomes": outcomes, "expected_rule_outcomes": labelled,
        "unknown_reported_decided": unknown_decided, "decided_reported_unknown": decided_unknown,
        "match": {"eligibility": state == label["expected_eligibility"],
                  "route": a["route"]["route"] == label["expected_route"],
                  "deciding": sorted(deciding(state, outcomes)) == sorted(label["deciding_rules"]),
                  "missing": got_missing == want_missing,
                  "payment_strict": strict == label["expected_payment_status"],
                  "payment_gated": gated == label["expected_payment_status"]},
    }
