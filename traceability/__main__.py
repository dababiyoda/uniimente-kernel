"""Emit the Single Bottleneck Metric as JSON for a ledger on disk.

    python -m traceability <ledger.jsonl> [--constitution-hash HASH]

Exit codes are deliberately blunt, because this runs in CI:

    0  reportable and clean        - a rate exists and nothing is contaminated
    1  contaminated                - at least one unauthorized external effect
    2  not reportable              - no goal claims completion; there is no rate
"""
from __future__ import annotations

import argparse
import json
import sys

from provenance.ledger import EvidenceLedger

from .metric import single_bottleneck_metric


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m traceability")
    parser.add_argument("ledger", help="path to a JSONL evidence ledger")
    parser.add_argument("--constitution-hash", default="",
                        help="expected constitution hash for the ledger genesis record")
    args = parser.parse_args(argv)

    ledger = EvidenceLedger(args.constitution_hash, path=args.ledger)
    report = single_bottleneck_metric(ledger)

    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    print(report.summary(), file=sys.stderr)

    if report.contaminated:
        return 1
    if not report.reportable:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
