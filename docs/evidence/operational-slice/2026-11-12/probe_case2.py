"""Case 2 probes beyond the withheld cases (SYNTHETIC — not a real party). Each prints what the mechanism reads:

P1  an ineligible draw (06-fir) with a statement row for its requested amount: is a payment status given to it?
P2  a later draw on the same body: the case reference is the contract reference, which every draw shares.
P3  the same reading of 01-alder and 11-larch with the case reference written per draw ('SYN-SC-2026-0417 draw 4').

    PYTHONPATH=. python docs/evidence/operational-slice/2026-11-12/probe_case2.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from greg.capabilities import BUILTINS, InvocationContext  # noqa: E402
from greg.cases import assess  # noqa: E402
from greg.missions import validate_mission  # noqa: E402
from greg.templates import request_case  # noqa: E402
from tests.unit.request_case_2_grading import CASES, COLUMNS, FIXTURE, REF, NoHistory, params, payment_status  # noqa: E402
from tests.unit.test_greg_request_case_2 import Draw  # noqa: E402


def read(folder, root, reference=REF):
    ctx = InvocationContext(workspace=root / "ws", read_roots=(root, FIXTURE), secrets=None,
                            manifest=BUILTINS["case.assess"][0], deliver_root=root / "deliver", journal=NoHistory(),
                            mission_id="")
    return assess(params(folder, reference=reference), ctx)


def p1(root):
    folder = root / "06-fir"
    shutil.copytree(CASES / "06-fir", folder)
    (folder / "statement.csv").write_text("date,reference,amount,currency,memo\n"
                                          f"2026-11-10,ACH-60001,36720.00,USD,{REF} draw 4 progress payment\n")
    a = read(folder, root)
    print(f"P1 06-fir with a 36720.00 row: state={a['route']['state']} route={a['route']['route']} "
          f"payment={payment_status(a)} actual={a['projection']['actual'] and a['projection']['actual'][0]['amount']}")


def p2(root):
    (root / "body").mkdir()
    d = Draw(root / "body")
    try:
        d.to_first_packet()
        d.accept()
        d.tick()
        d.statement.write_bytes(d.held)
        d.tick(5)
        print(f"P2 draw 4 mission: achieved={bool(d.events('mission.achieved'))}")
        folder = d.data / "draw-5"
        shutil.copytree(d.folder, folder)
        second = validate_mission(request_case(reference=REF, request="pay application, draw 5",
                                               rulebook=d.rulebook, folder=folder, columns=COLUMNS))
        d.send("MISSION", second)
        d.tick()
        d.mid = second["mission_id"]
        [approval] = d.asks("APPROVAL")
        d.send("DECISION", {"request_id": approval["request_id"], "answer": "approve"})
        d.tick()
        a = d.latest()
        print(f"P2 a later draw's mission on the same body: earlier cases={[x['state'] for x in a['duplicates']]} "
              f"payment reason={a['payment']['reason'][:110]!r}")
    finally:
        d.close()


def p3(root):
    for case in ("01-alder", "11-larch"):
        a = read(CASES / case, root, reference=f"{REF} draw 4")
        print(f"P3 {case} with reference '{REF} draw 4': state={a['route']['state']} payment={payment_status(a)}")


def main():
    with tempfile.TemporaryDirectory(prefix="greg-case2-probe-") as tmp:
        root = Path(tmp)
        p1(root)
        p2(root)
        p3(root)


if __name__ == "__main__":
    main()
