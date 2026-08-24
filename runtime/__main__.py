"""`python -m runtime <state_dir> [--rehearse]` — boot and report.

Exit codes: 0 booted (and any rehearsal completed), 1 a rehearsal halted,
2 the institution refused to boot. A refusal is louder than a halt on purpose:
a halted traversal is the institution working, and a refused boot is the
institution declining to run on ground it does not trust.

This command boots, optionally rehearses one Bridge A traversal on committed
fixtures, and reports. It grants nothing, activates nothing, and reaches
nothing outside its state directory.
"""
from __future__ import annotations

import sys

from runtime import BootRefused
from runtime.session import Session

RULE = "=" * 78


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv

    if not argv or argv[0] in ("-h", "--help"):
        print("usage: python -m runtime <state_dir> [--rehearse]")
        print("  boots the institution from <state_dir> and reports what it holds")
        print("  --rehearse   run one Bridge A traversal on committed fixtures")
        return 0

    state_dir = argv[0]
    rehearse = "--rehearse" in argv[1:]

    try:
        session = Session.open(state_dir)
    except BootRefused as exc:
        print(f"BOOT REFUSED: {exc}", file=sys.stderr)
        return 2

    report = session.runtime.report
    print(RULE)
    print(f"UNIIMENTE — {'resumed' if report.resumed else 'fresh'} from {report.state_dir}")
    print(RULE)
    print(f"  constitution   {report.constitution_verdict}")
    print(f"  chain          {report.chain_detail}")
    print(f"  events         {report.events_replayed} replayed")
    print(f"  inbox          {report.inbox_depth} known event ids")
    print(f"  outbox         {report.outbox_depth} deliveries still owed")
    print(f"  identities     {report.identities_restored} restored "
          f"(re-issued per boot, never restored)")

    exit_code = 0
    if rehearse:
        traversal = session.rehearse()
        print()
        print(f"  rehearsal      {'completed' if traversal.completed else 'HALTED'}"
              f"{'' if traversal.completed else ' at ' + str(traversal.halted_at)}")
        print(f"                 {len(traversal.event_ids)} events, "
              f"causal depth {traversal.causal_depth}, "
              f"records {traversal.records_before} -> {traversal.records_after}")
        print(f"                 proves_external_reality = "
              f"{traversal.proves_external_reality}")
        if not traversal.completed:
            print(f"                 {traversal.reason}")
            exit_code = 1

    history = session.history()
    if history:
        print()
        print(f"  chain holds {len(history)} events across every session:")
        for entry in history[-6:]:
            print(f"    {entry['type']}")
        if len(history) > 6:
            print(f"    ... and {len(history) - 6} earlier")

    print()
    print("This command reports institutional state. It grants nothing, "
          "activates nothing,")
    print("and reaches nothing outside its state directory.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
