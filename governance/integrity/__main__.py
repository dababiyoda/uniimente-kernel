"""`python -m governance.integrity` — the live constitutional integrity reading.

Exit codes are meaningful, because this is the check a build or a review runs:

    0   every watched artifact is where it was authorised
    1   at least one finding
    2   the amendment record itself is unsound (BrokenChain)

2 is deliberately distinct from 1. "Someone changed the Constitution without
authorisation" and "the record of what is authorised no longer follows from
itself" are different emergencies, and collapsing them would hide the second.
"""
from __future__ import annotations

from . import AMENDMENTS, BrokenChain, Verdict, verify


def main(argv: list[str] | None = None) -> int:
    print("=" * 74)
    print("LIVE CONSTITUTIONAL INTEGRITY — the artifacts as they stand today")
    print("=" * 74)

    try:
        report = verify()
    except BrokenChain as exc:
        print()
        print("  AMENDMENT CHAIN UNSOUND — no verdict can be given")
        print(f"  {exc}")
        print()
        print("  This is not a report that the Constitution changed. It is a")
        print("  report that the record of what is authorised cannot be")
        print("  replayed, so no artifact can be judged either way.")
        return 2

    print(f"  {report.headline}")
    print()
    for status in report.statuses:
        mark = "  ok  " if status.ok else "FINDING"
        trail = f"  ({status.amendments} amendment(s))" if status.amendments else ""
        print(f"  [{mark}] {status.artifact}{trail}")
        if status.verdict is Verdict.UNAUTHORISED_CHANGE:
            print(f"            authorised {status.authorized_sha256[:16]}…")
            print(f"            observed   {status.observed_sha256[:16]}…")
        elif status.verdict is Verdict.MISSING:
            print("            declared in the baseline, absent from disk")
        elif status.verdict is Verdict.UNGOVERNED_ADDITION:
            print("            present in a watched tree, declared nowhere")

    print()
    print(f"  amendments on record: {len(AMENDMENTS)}")
    print()
    print("This is the LIVE constitution. The sealed Package 3 experiment")
    print("answers a different question — whether a historical run reproduces —")
    print("and neither reading may be presented as the other.")

    return 0 if report.intact else 1


if __name__ == "__main__":  # pragma: no cover - CLI entry
    raise SystemExit(main())
