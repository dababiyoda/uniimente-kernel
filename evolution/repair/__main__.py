"""Run the Package 3 experiment and emit its evidence record as JSON.

    python -m evolution.repair > record.json

Ledger-backed, so the run produces a verifiable hash chain alongside the record.
Reads nothing from the network, writes nothing outside stdout, spends nothing.
"""
from __future__ import annotations

import json
import sys

from evolution.repair.harness import ReplacementExperiment
from provenance.ledger import EvidenceLedger


def main() -> int:
    ledger = EvidenceLedger("sha256:package3-governed-functional-replacement")
    record = ReplacementExperiment(ledger=ledger).run()

    chain_ok, chain_msg = ledger.verify_chain()
    record["ledger"] = {"chain_verifies": chain_ok, "detail": chain_msg,
                        "head": ledger.head, "records": len(ledger.records)}

    json.dump(record, sys.stdout, indent=2, sort_keys=True, default=str)
    sys.stdout.write("\n")

    # Non-zero exit if the experiment's own invariants did not hold, so CI
    # cannot record a green run over a broken one.
    ok = (record["continuity"]["unchanged"]
          and record["detected_loss"]["lost"] is True
          and record["control_healthy"]["lost"] is False
          and chain_ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
