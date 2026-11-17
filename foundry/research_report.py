"""Optional DuckDB reporting over completed canonical workflow checkpoints."""
from __future__ import annotations

import argparse
import json

from provenance.ledger import EvidenceLedger


def report(ledger):
    import duckdb  # Optional; inference and the assembly do not depend on this package.

    ok, reason = ledger.verify_chain()
    if not ok:
        raise ValueError(reason)
    latest = {}
    for record in ledger.by_type("workflow"):
        latest[record.payload["workflow_id"]] = record.payload
    rows = []
    for workflow_id, checkpoint in latest.items():
        bundle = checkpoint.get("state", {}).get("review_bundle")
        if checkpoint["status"] != "completed" or not bundle:
            continue
        rows.append((workflow_id, bundle["query"], bundle["assessment"]["go_no_go"],
                     len(bundle["sources"]), len(bundle["drafts"]), bundle["status"],
                     bundle["search_mode"], bundle["inference_mode"]))
    with duckdb.connect(":memory:") as database:
        database.execute("CREATE TABLE reviews(workflow_id VARCHAR, query VARCHAR, verdict VARCHAR, "
                         "sources INTEGER, drafts INTEGER, status VARCHAR, search_mode VARCHAR, inference_mode VARCHAR)")
        if rows:
            database.executemany("INSERT INTO reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
        columns = [column[0] for column in database.execute(
            "SELECT * FROM reviews ORDER BY workflow_id").description]
        reviews = [dict(zip(columns, row)) for row in database.fetchall()]
        counts = database.execute(
            "SELECT verdict, count(*) FROM reviews GROUP BY verdict ORDER BY verdict").fetchall()
    return {"reviews": reviews, "verdict_counts": dict(counts),
            "market_validation": "unproven", "note": "Counts describe internal review output, not business success."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--anchor", required=True)
    args = parser.parse_args()
    # A research line may be appending to this ledger now, and the file can end inside the line it is writing (the
    # kernel grows it a page at a time while it copies one write). That line was never acknowledged: it is left out
    # (its checkpoint is counted on the next report) and named in the output, never read as corruption.
    ledger = EvidenceLedger(args.anchor, path=args.ledger, read_only=True, tail="ignore")
    try:
        out = report(ledger)
        if ledger.unacknowledged_tail:
            out["unacknowledged_tail"] = ledger.unacknowledged_tail
        print(json.dumps(out, indent=2))
    finally:
        ledger.close()


if __name__ == "__main__":
    main()
