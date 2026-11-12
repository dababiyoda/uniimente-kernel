"""Founder asks raised per case-1 scenario (the case-1 side of the pre-registered measure 2), counted from the ledger.

SYNTHETIC — not a real party. Each scenario runs on its own throwaway body with a test key:

    PYTHONPATH=. python docs/evidence/operational-slice/2026-11-12/count_asks.py
"""
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from tests.unit.test_greg_request_case import HEADER, PAID, REF, Case, accept, to_eligible_packet  # noqa: E402


def scenario(name, prepare, after=None):
    tmp = Path(tempfile.mkdtemp(prefix="greg-case-asks-"))
    c = Case(tmp)
    try:
        prepare(c)
        to_eligible_packet(c)
        if after:
            after(c)
        a = c.packet(c.packets()[-1])["assessment"]
        kinds = Counter(ask["kind"] for ask in c.asks())
        print(f"{name:30s} route={a['route']['route']:8s} eligibility={a['eligibility']:12s} "
              f"asks={sum(kinds.values())} {dict(sorted(kinds.items()))}")
    finally:
        c.close()
        shutil.rmtree(tmp, ignore_errors=True)


def edit(c, name, old, new):
    path = c.folder / name
    path.write_text(path.read_text().replace(old, new))


def main():
    scenario("clean, to the first person's act", lambda c: None)
    scenario("missing proof of delivery", lambda c: (c.folder / "proof_of_delivery.txt").unlink())
    scenario("unreadable proof of delivery", lambda c: (c.folder / "proof_of_delivery.txt").write_bytes(
        (c.folder / "proof_of_delivery.txt").read_text().encode("utf-16-le")))
    scenario("conflicting agreed amount",
             lambda c: edit(c, "invoice.txt", "Agreed amount: 1850.00", "Agreed amount: 2100.00"))
    scenario("invoice total not allowed",
             lambda c: edit(c, "invoice.txt", "Invoice amount: 1925.00", "Invoice amount: 2400.00"))

    def exception(c):
        (c.folder / "exception_notice.txt").write_text(f"Load reference: {REF}\nException: shortage\nStatus: open\n")
        c.tick()

    def disputed(c):
        accept(c, "disputed", "Dispute: cartons crushed\n")
        c.tick()

    def ambiguous(c):
        accept(c)
        c.tick()
        (c.folder / "statement.csv").write_text(HEADER + PAID + PAID.replace("11-10", "11-11"))
        c.tick()

    def unreadable_statement(c):
        accept(c)
        c.tick()
        (c.folder / "statement.csv").write_bytes(b"date,description\n\xff\xfe\n")
        c.tick(6)
    scenario("exception after eligible", lambda c: None, exception)
    scenario("disputed completion", lambda c: None, disputed)
    scenario("ambiguous statement", lambda c: None, ambiguous)
    scenario("unreadable statement", lambda c: None, unreadable_statement)


if __name__ == "__main__":
    main()
