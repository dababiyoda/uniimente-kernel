"""Founder asks raised per withheld case-2 case (the case-2 side of the pre-registered measure 2), counted from the
ledger with the protocol of count_asks.py: each case on its own throwaway body with a test key, run through the
request-case template to the first packet (approved once), then the case's own event, counting every ask kind.

SYNTHETIC — not a real party:

    PYTHONPATH=. python docs/evidence/operational-slice/2026-11-12/count_asks_case2.py
"""
import shutil
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from tests.unit.test_greg_request_case_2 import Draw  # noqa: E402


def scenario(case, name, after=None):
    tmp = Path(tempfile.mkdtemp(prefix="greg-case2-asks-"))
    d = Draw(tmp, case)
    try:
        d.to_first_packet()
        if after:
            after(d)
        a = d.latest()
        kinds = Counter(ask["kind"] for ask in d.asks())
        print(f"{case:12s} {name:34s} route={a['route']['route']:36s} state={a['route']['state']:12s} "
              f"asks={sum(kinds.values())} {dict(sorted(kinds.items()))} person={d.human()}")
    finally:
        d.close()
        shutil.rmtree(tmp, ignore_errors=True)


def ambiguous(d):
    d.accept()
    d.tick()
    d.statement.write_bytes(d.held)      # the withheld statement: two rows could each be the payment
    d.tick()


def main():
    scenario("01-alder", "clean, to the first person's act")
    scenario("02-birch", "inspection sign-off missing")
    scenario("03-cedar", "prior-draw lien waiver missing")
    scenario("04-dogwood", "retainage short by one line")
    scenario("05-elm", "billed above inspection")
    scenario("06-fir", "unapproved change order billed")
    scenario("07-ginkgo", "conflicting contract reference")
    scenario("08-hazel", "duplicate of an open draw")
    scenario("09-ironwood", "disputed inspection line")
    scenario("10-juniper", "unreadable schedule of values")
    scenario("11-larch", "ambiguous statement", ambiguous)
    scenario("12-maple", "instruction-shaped line, no retainage")


if __name__ == "__main__":
    main()
