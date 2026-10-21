"""Evidence for the decisive-test table in docs/cortex/SEED_EXPERIMENT_REPORT.md (2026-10-14 section).

Route selection and the finality jurisdiction are recomputed by running the frozen routed arm
(`cortex.evaluation.arms.routed_seed`, the harness clock and the item records) over the frozen held-out suite.
Both are structural: they are the same with or without Z3 and with or without a model, so CI can recompute
them anywhere. Dispositions, states and scores are read from the reported run (`heldout-results.json`), because
the reported run served the semantic organ from a transcript. Whether an abstention carries a
`capability_deficit` follows the routing rule (an abstaining receipt whose state is NO_ELIGIBLE_METHOD or
UNSUPPORTED_GEOMETRY).

    python scripts/analysis/cortex_seed_decisive_test.py            # writes decisive-test-counts.json
    python scripts/analysis/cortex_seed_decisive_test.py --check    # recomputes and compares
"""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from cortex.evaluation import arms as A  # noqa: E402
from cortex.evaluation import run as R  # noqa: E402
from cortex.routing import Cortex  # noqa: E402

EVIDENCE = ROOT / "tests/evidence/cortex-seed-v0.1.6"
OUT = EVIDENCE / "decisive-test-counts.json"
DEFICIT_STATES = ("NO_ELIGIBLE_METHOD", "UNSUPPORTED_GEOMETRY")


def analyse() -> dict:
    held = json.loads((EVIDENCE / "heldout-results.json").read_text(encoding="utf-8"))
    reported = {i["item_id"]: i for i in held["arms"]["routed_seed"]["items"]}
    cortex = Cortex(clock=lambda: "2026-09-30T00:00:00Z")   # the harness clock (cortex/evaluation/run.py)
    rows = []
    for item in R.load_items("heldout"):
        receipt = A.routed_seed(item, cortex)["receipt"]
        rep = reported[item["item_id"]]
        rows.append({"item_id": item["item_id"], "geometry": rep["geometry"],
                     "selected": receipt["route"]["selected"], "decided_by": receipt["route"]["finality"]["decides"],
                     "disposition": rep["disposition"], "state": rep["state"], "score": rep["score"],
                     "correct_abstention": rep["correct_abstention"], "overcautious": rep["overcautious"],
                     "carries_capability_deficit": rep["disposition"] == "abstain" and rep["state"] in DEFICIT_STATES})
    if sorted(r["item_id"] for r in rows) != sorted(reported):
        raise SystemExit("the suite and the reported run name different items")
    count = lambda key: dict(sorted(collections.Counter(key(r) for r in rows).items()))  # noqa: E731
    no_organ = [r for r in rows if not r["selected"]]
    abstains = [r for r in rows if r["disposition"] == "abstain"]
    return {
        "schema": "cortex-seed-decisive-test/0.1",
        "source": "tests/evidence/cortex-seed-v0.1.6/heldout-results.json",
        "freeze_manifest_sha256": held["freeze_manifest_sha256"],
        "items": len(rows),
        "geometry_labels": len({r["geometry"] for r in rows}),
        "route_sets": count(lambda r: " + ".join(r["selected"]) or "none"),
        "decided_by": count(lambda r: r["decided_by"]),
        "no_organ": {"items": len(no_organ),
                     "dispositions": dict(sorted(collections.Counter(r["disposition"] for r in no_organ).items())),
                     "recommended": sorted(r["item_id"] for r in no_organ if r["disposition"] == "recommend")},
        "dispositions": count(lambda r: r["disposition"]),
        "correct_withholdings": sum(r["correct_abstention"] for r in rows),
        "overcautious": sum(r["overcautious"] for r in rows),
        "abstentions_with_capability_deficit": sorted(r["item_id"] for r in abstains if r["carries_capability_deficit"]),
        "abstention_states": dict(sorted(collections.Counter(r["state"] for r in abstains).items())),
        "rows": rows,
    }


def main() -> None:
    text = json.dumps(analyse(), indent=2, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        if OUT.read_text(encoding="utf-8") != text:
            raise SystemExit("decisive-test-counts.json does not match a fresh computation")
        print("decisive-test-counts.json reproduces")
        return
    OUT.write_text(text, encoding="utf-8")
    d = json.loads(text)
    print(json.dumps({k: v for k, v in d.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
