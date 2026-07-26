"""Run the Package 4 experiment and emit its evidence record as JSON.

    python -m evolution.migration > record.json

Isolated ledger, experiment-local workflow ids, no network, no files written
outside stdout, $0.00 spent.
"""
from __future__ import annotations

import json
import sys

from evolution.migration.harness import StatefulReplacementExperiment
from provenance.ledger import EvidenceLedger


def main() -> int:
    ledger = EvidenceLedger("sha256:package4-stateful-canonical-replacement")
    record = StatefulReplacementExperiment(ledger=ledger).run()

    chain_ok, chain_msg = ledger.verify_chain()
    record["ledger"] = {"chain_verifies": chain_ok, "detail": chain_msg,
                        "head": ledger.head, "records": len(ledger.records)}

    json.dump(record, sys.stdout, indent=2, sort_keys=True, default=str)
    sys.stdout.write("\n")

    control = record["malformed_checkpoint_control"]
    ok = (record["continuity"]["unchanged"]
          and control["refused_before_append"]
          and control["malformed_checkpoints_in_ledger"] == 0
          and record["rollback"]["default_is_original_after_all_scopes"]
          and record["rollback"]["simulated_restart_default"]
          and chain_ok)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
