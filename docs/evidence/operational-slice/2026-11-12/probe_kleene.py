"""What strong three-valued evaluation would change (a founder decision, review lens 2 F8). SYNTHETIC — not a real
party. Read-only; no body, network or payment; nothing in greg/ changes:

    PYTHONPATH=. python docs/evidence/operational-slice/2026-11-12/probe_kleene.py

Today a rule waits on every fact it needs: one missing fact leaves it unknown even when the facts on file already
decide it ('Signed: no' fails the signed-in-window rule whatever the window says). Under strong (Kleene) three-valued
logic, 'and' is false when any part is false, 'or' is true when any part is true, and anything else that reads an
unknown fact is unknown. This probe evaluates every rule that way, in place of greg.cases.evaluate, for case 1's
reproduction and for the twelve withheld case-2 cases graded by the frozen translation, and prints what differs.
"""
import ast
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
import greg.cases as cases  # noqa: E402
from tests.unit.request_case_2_grading import CASES, grade, read_case  # noqa: E402
from tests.unit.test_greg_request_case import assess, case_files, ctx, params  # noqa: E402

UNKNOWN = object()
TODAY = cases.evaluate


def _reads_unknown(node, env) -> bool:
    return any(isinstance(n, ast.Name) and env.get(n.id) is UNKNOWN for n in ast.walk(node))


def _kleene(node, env):
    if isinstance(node, ast.Expression):
        return _kleene(node.body, env)
    if isinstance(node, ast.BoolOp):
        values = [_kleene(v, env) for v in node.values]
        stop = isinstance(node.op, ast.Or)          # 'or' stops at true, 'and' at false
        if any(v is stop for v in values):
            return stop
        return UNKNOWN if any(v is UNKNOWN for v in values) else (not stop)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        value = _kleene(node.operand, env)
        return UNKNOWN if value is UNKNOWN else not value
    return UNKNOWN if _reads_unknown(node, env) else cases._eval(node, env)


def kleene(condition, needs, facts):
    env, missing, conflicts, _ = cases._resolve(needs, facts)
    if not missing and not conflicts:
        return TODAY(condition, needs, facts)
    try:
        value = _kleene(ast.parse(condition.strip(), mode="eval"),
                        {**env, **{m["fact"]: UNKNOWN for m in missing}, **{c: UNKNOWN for c in conflicts}})
    except Exception:                                # noqa: BLE001 - an undecidable part leaves it as today
        value = UNKNOWN
    if value is UNKNOWN or not isinstance(value, bool):
        return TODAY(condition, needs, facts)
    return {"state": "met" if value else "not_met", "facts_used": {}, "decided_with_unknowns": True}


def case1(root):
    rulebook, folder = case_files(root)
    pod = folder / "proof_of_delivery.txt"
    pod.write_text(pod.read_text().replace("Signed: yes", "Signed: no"))
    (folder / "rate_confirmation.txt").unlink()
    for name, evaluate in (("today", TODAY), ("kleene", kleene)):
        cases.evaluate = evaluate
        a = assess(params(rulebook, folder), ctx(root))
        print(f"case 1 'Signed: no', no rate confirmation, {name:6s}: eligibility={a['eligibility']} "
              f"route={a['route']['route']} unresolved={len(a['unresolved'])}")
    cases.evaluate = TODAY


def case2(root):
    fields = ("eligibility", "route", "deciding", "missing", "payment_strict", "payment_gated")
    graded = {}
    for name, evaluate in (("today", TODAY), ("kleene", kleene)):
        cases.evaluate = evaluate
        graded[name] = {c: grade(c, read_case(c, root / name)) for c in sorted(p.name for p in CASES.iterdir())}
    cases.evaluate = TODAY
    for name in graded:
        rows = graded[name].values()
        print(f"case 2 {name:6s}: " + ", ".join(f"{f} {sum(r['match'][f] for r in rows)}/12" for f in fields)
              + f", label unknown read pass/fail {sum(len(r['unknown_reported_decided']) for r in rows)}"
              + f", label pass/fail read unknown {sum(len(r['decided_reported_unknown']) for r in rows)}")
    for c, today in graded["today"].items():
        other = graded["kleene"][c]
        moved = {f: (today[f], other[f]) for f in ("eligibility", "route", "deciding", "missing", "rule_outcomes")
                 if today[f] != other[f]}
        if moved:
            print(f"  {c}: {moved}")


def main():
    root = Path(tempfile.mkdtemp(prefix="greg-kleene-"))
    try:
        case1(root / "case1")
        case2(root / "case2")
    finally:
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    main()
