"""Write the case-2 rulebook (progress-payment draw) as data, from the withheld SPEC.md only.

SYNTHETIC — not a real party. The rulebook language (greg/cases.py) reads one value per literal key, has no lookup by
a fact's value, no per-line iteration, no conditional expression and no rounding. The SPEC's rules are written out for
this contract's schedule lines (L1-L5, CO-01, CO-02), for draws 1 to DRAWS and for up to PUNCH punch items; every such
expansion is listed in RESULT-case-2.md as a deviation. Usage: python make_rulebook.py OUT.json
"""
import json
import sys

DRAWS, PUNCH = 6, 6
LINES = ["L1", "L2", "L3", "L4", "L5"]           # original lines: one value each on every document
COS = ["CO-01", "CO-02"]                          # change orders: a line a pay application may or may not list


def low(line):
    return line.lower().replace("-", "")


facts = {}


def fact(name, kind, doc, key, **extra):
    facts[name] = {"type": kind, "from": {doc: key}, **extra}


ONLY_NUMBER = "^\\s*\\d"                          # a register value that is not a figure ('not paid') is no figure

# schedule of values
fact("sov_ref", "text", "sov", "contract_reference")
fact("ret_pct", "percent", "sov", "retainage_percent")
for line in LINES:
    fact(f"sv_{low(line)}", "amount", "sov", f"{line} scheduled_value")
for co in COS:
    fact(f"sv_{low(co)}", "amount", "sov", f"{co} amount")
    # 'approved: yes' only; no, pending or not recorded is not approved (R6), so the line may be absent: many
    fact(f"ok_{low(co)}", "text", "sov", f"{co} approved", many=True)
# pay application
fact("pay_ref", "text", "pay", "contract_reference")
fact("pay_draw", "number", "pay", "draw_number")
fact("pay_end", "date", "pay", "period_end_date")
fact("pay_cur", "text", "pay", "currency")
for line in LINES:
    fact(f"pc_{low(line)}", "percent", "pay", f"{line} percent_complete_to_date")
    fact(f"pb_{low(line)}", "amount", "pay", f"{line} previously_billed")
for co in COS:
    fact(f"pc_{low(co)}", "percent", "pay", f"{co} percent_complete_to_date", many=True)
    fact(f"pb_{low(co)}", "amount", "pay", f"{co} previously_billed", many=True)
fact("pay_ret", "amount", "pay", "retainage_withheld")
fact("pay_req", "amount", "pay", "amount_requested")
# inspection sign-off
fact("insp_ref", "text", "insp", "contract_reference")
fact("insp_draw", "number", "insp", "draw_number")
fact("insp_end", "date", "insp", "period_end_date")
fact("insp_signed", "yes_no", "insp", "signed")
for line in LINES:
    fact(f"ob_{low(line)}", "percent", "insp", f"{line} observed_percent_complete")
for co in COS:
    fact(f"ob_{low(co)}", "percent", "insp", f"{co} observed_percent_complete", many=True)
fact("punch_open", "number", "insp", "open_punch_items")
for k in range(1, PUNCH + 1):
    fact(f"pk{k}", "text", "insp", f"punch_item_{k} blocking", many=True)
fact("dsp_line", "text", "insp", "dispute_line", many=True)
fact("dsp_status", "text", "insp", "dispute_status", many=True, pattern="^(?P<value>[A-Za-z]+)")
fact("dsp_value", "percent", "insp", "dispute_position", many=True,
     pattern="(?P<value>\\d+(?:\\.\\d+)?)\\s*percent")
fact("dsp_position", "text", "insp", "dispute_position", many=True)
fact("dsp_by", "text", "insp", "dispute_raised_by", many=True)
# lien waiver for the prior draw
fact("lw_ref", "text", "waiver", "contract_reference")
fact("lw_draw", "number", "waiver", "draw_number")
fact("lw_amount", "amount", "waiver", "amount_waived")
fact("lw_signed", "yes_no", "waiver", "signed")
# the payer's draw register
fact("reg_ref", "text", "register", "contract_reference")
for d in range(1, DRAWS + 1):
    fact(f"s{d}", "text", "register", f"draw {d} status", many=True)
    fact(f"g{d}", "amount", "register", f"draw {d} gross_billed", many=True, only=ONLY_NUMBER)
    fact(f"n{d}", "amount", "register", f"draw {d} net_paid", many=True, only=ONLY_NUMBER)
# the payer's recorded acceptance (the SPEC names no file for it; see RESULT-case-2.md)
fact("acc_decision", "text", "acc", "decision")

DOC = {"sov": "sov", "pay": "pay", "insp": "insp", "waiver": "waiver", "register": "register", "acc": "acc"}
import ast  # noqa: E402


def names(condition):
    return sorted({n.id for n in ast.walk(ast.parse(condition, mode="eval")) if isinstance(n, ast.Name)} - {
        "sum", "count", "abs", "min", "max", "date", "True", "False"})


def needs(condition):
    return {n: list(facts[n]["from"]) for n in names(condition)}


rules = []


def rule(ident, description, condition):
    assert len(condition) <= 600, (ident, len(condition))
    rules.append({"id": ident, "description": description, "needs": needs(condition), "condition": condition})


# R1. Required documents: the schedule, the pay application, a signed sign-off for draw N (its draw number is N or
# its period end equals the pay application's), a waiver for draw N-1, the register. A reference to a fact of a
# document makes the rule wait on it when the document is absent, empty or unreadable.
rule("R1", "R1 required documents: schedule of values, pay application, a signed inspection sign-off for this draw "
     "(draw number or period end), the prior-draw lien waiver and the draw register are on file",
     "sov_ref == sov_ref and reg_ref == reg_ref and lw_draw == lw_draw and insp_signed == True "
     "and (insp_draw == pay_draw or insp_end == pay_end)")
# R2. Every readable contract reference agrees (case and surrounding spaces ignored): each document against the pay
# application, one rule per document so that a known difference fails whatever another document leaves unknown.
for kind, f in (("schedule-of-values", "sov_ref"), ("inspection", "insp_ref"), ("lien-waiver", "lw_ref"),
                ("register", "reg_ref")):
    rule(f"R2.{kind}", f"R2 contract reference agrees: the {kind.replace('-', ' ')} carries the pay application's "
         "contract reference", f"pay_ref == {f}")
# R3. The draw number is one more than the highest draw the register shows settled (0 when none).
for n in range(1, DRAWS + 1):
    later = " and ".join(f"'settled' not in s{d}" for d in range(n, DRAWS + 1))
    prior = f"'settled' in s{n - 1} and " if n > 1 else ""
    rule(f"R3.draw{n}", f"R3 draw sequence, for draw {n}: the last settled draw is {n - 1}",
         f"pay_draw != {n} or ({prior}{later})")
rule("R3.bound", f"R3 draw sequence: this rulebook reads the register's draws 1 to {DRAWS} only",
     f"pay_draw >= 1 and pay_draw <= {DRAWS}")
# R4. Billed percent complete is at most the inspection's observation plus 2 points; a line billed at 0 passes.
for line in LINES:
    p, o = f"pc_{low(line)}", f"ob_{low(line)}"
    rule(f"R4.{line}", f"R4 {line} percent complete is within 2 points of what inspection observed",
         f"{p} == 0 or {p} <= {o} + 2")
for co in COS:
    p, o = f"pc_{low(co)}", f"ob_{low(co)}"
    rule(f"R4.{co}", f"R4 {co} percent complete is within 2 points of what inspection observed",
         f"sum({p}) == 0 or (count({o}) == 1 and sum({p}) <= sum({o}) + 2)")


# R5. Value to date = scheduled value x percent; work this period = value to date - previously billed; gross = the
# sum; retainage = retainage percent x gross; net = gross - retainage. An unapproved change order's scheduled value
# counts as zero, so the gross is written once for each combination of the two change orders' approvals.
def gross(approved):
    terms = [f"sv_{low(x)} * pc_{low(x)} / 100 - pb_{low(x)}" for x in LINES]
    for co, ok in zip(COS, approved):
        terms.append(f"sv_{low(co)} * sum(pc_{low(co)}) / 100 - sum(pb_{low(co)})" if ok
                     else f"0 - sum(pb_{low(co)})")
    return "(" + " + ".join(terms) + ")"


for a1 in (True, False):
    for a2 in (True, False):
        guard = " or ".join(f"'yes' {'not in' if ok else 'in'} ok_{low(co)}" for co, ok in zip(COS, (a1, a2)))
        tag = ".".join(f"{co}-{'approved' if ok else 'not-approved'}" for co, ok in zip(COS, (a1, a2)))
        g = gross((a1, a2))
        rule(f"R5.net.{tag}", "R5 amount arithmetic: the amount requested equals gross minus retainage within one "
             f"cent (change orders {tag})", f"{guard} or abs(pay_req - {g} * (100 - ret_pct) / 100) <= 0.01")
        rule(f"R5.retainage.{tag}", "R5 amount arithmetic: the retainage withheld equals the retainage percent of "
             f"the gross within one cent (change orders {tag})", f"{guard} or abs(pay_ret - {g} * ret_pct / 100) <= 0.01")
billed = " + ".join([f"pb_{low(x)}" for x in LINES] + [f"sum(pb_{low(co)})" for co in COS])
for n in range(1, DRAWS + 1):
    register = " + ".join(f"sum(g{d})" for d in range(1, n)) or "0"
    rule(f"R5.prior.draw{n}", f"R5 amount arithmetic, for draw {n}: previously billed over all lines equals the "
         f"register's gross billed for draws 1 to {n - 1} within one cent",
         f"pay_draw != {n} or abs({billed} - ({register})) <= 0.01")
# R6. A change order billed above 0 percent is recorded approved: yes.
for co in COS:
    rule(f"R6.{co}", f"R6 {co} is billed only if the schedule of values records it approved: yes",
         f"sum(pc_{low(co)}) == 0 or 'yes' in ok_{low(co)}")
# R7. The waiver refers to draw N-1, is signed, and waives the register's net paid for draw N-1 within one cent.
for n in range(2, DRAWS + 1):
    rule(f"R7.draw{n}", f"R7 prior-draw lien waiver, for draw {n}: it is for draw {n - 1}, signed, and waives the "
         f"register's net paid for draw {n - 1}",
         f"pay_draw != {n} or (lw_draw == {n - 1} and lw_signed == True and count(n{n - 1}) == 1 "
         f"and abs(lw_amount - sum(n{n - 1})) <= 0.01)")
# R8. No open punch item is marked blocking: yes; every open item carries a blocking mark.
marks = " + ".join(f"count(pk{k})" for k in range(1, PUNCH + 1))
blocking = " and ".join(f"'yes' not in pk{k}" for k in range(1, PUNCH + 1))
rule("R8", f"R8 no blocking punch item: no open punch item is marked blocking: yes (items 1 to {PUNCH} read)",
     f"punch_open == {marks} and {blocking}")
# R9. Not a duplicate: the register holds no draw N for this contract whose status is open or settled.
for n in range(1, DRAWS + 1):
    rule(f"R9.draw{n}", f"R9 duplicate, for draw {n}: the register holds no draw {n} that is open or settled",
         f"pay_draw != {n} or reg_ref != pay_ref or ('open' not in s{n} and 'settled' not in s{n})")

# Disputed: an inspection records that a party contests a line's observed percent and does not record it resolved,
# and R4's outcome for that line differs between the inspector's figure and the contested one.
disputes = []
for x in LINES + COS:
    p, o = f"pc_{low(x)}", f"ob_{low(x)}"
    if x in COS:
        p, o = f"sum({p})", f"sum({o})"
    condition = (f"'{x}' in dsp_line and 'open' in dsp_status and ({p} == 0 or {p} <= {o} + 2) != "
                 f"({p} == 0 or {p} <= sum(dsp_value) + 2)")
    disputes.append({"id": f"R4.{x}.disputed", "description": f"R4 {x}: a party's recorded position on the "
                     "observed percent, not recorded resolved, would change R4's outcome", "needs": needs(condition),
                     "condition": condition, "name": "dsp_position"})

book = {
    "rulebook": "progress-draw-eligibility",
    "version": "1",
    "label": "SYNTHETIC — not a real party. A sandbox rulebook for a subcontractor's progress-payment draw, written "
             "from the withheld SPEC.md (2026-11-12) for contract schedule lines L1-L5, CO-01 and CO-02; it "
             "describes no real payer.",
    "case_reference": "pay_ref",
    "request": {"channel": "subcontractor-draws"},
    "documents": {
        "sov": {"file": "schedule_of_values.txt", "required": True},
        "pay": {"file": "pay_application.txt", "required": True},
        "insp": {"file": "inspection_signoff.txt", "required": True},
        "waiver": {"file": "lien_waiver_prior_draw.txt", "required": True},
        "register": {"file": "draw_register.txt", "required": True},
        "acc": {"file": "payer_acceptance.txt", "required": False},
    },
    "facts": facts,
    "rules": rules,
    "disputes": disputes,
    "acceptance": {"description": "the payer's recorded decision accepts the draw",
                   "needs": {"acc_decision": ["acc"]}, "condition": "acc_decision == 'accepted'"},
    "settlement": {"amount": "pay_req", "currency": "pay_cur"},
    "estimate": ["pay_req", "pay_ret"],
    "routing": [
        {"state": "ineligible", "route": "decline_naming_failed_rules",
         "action": "decline, naming each failed rule and the facts that failed it; a person tells the subcontractor"},
        {"state": "disputed", "route": "hold_naming_dispute",
         "action": "hold, naming the disputed fact, each party's recorded position and the rule that turns on it; "
                   "no settlement is prepared until it is resolved"},
        {"state": "undetermined", "route": "request_missing_facts",
         "action": "ask for exactly the missing facts, each with the document that should carry it"},
        {"state": "eligible", "route": "prepare_settlement_and_await_payment",
         "action": "record acceptance and prepare a settlement for the amount requested, then wait until the "
                   "payment is observed; the payment itself is a person's act"},
    ],
}

if __name__ == "__main__":
    out = json.dumps(book, indent=1, ensure_ascii=False) + "\n"
    open(sys.argv[1], "w", encoding="utf-8").write(out)
    print(f"{len(facts)} facts, {len(rules)} rules, {len(disputes)} disputes, {out.count(chr(10))} lines")
