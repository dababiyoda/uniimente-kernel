"""Abstention-to-resolution routing: the pre-registered floors F1 and F2, computed from recorded runs.

Reporting code written after the freeze (it decides nothing the frozen rule decides):

* F1: on every FORM item, NEW opens Capability Genesis on the same tick as B0;
* F2: every floor item (a closure-eligible item B0 brings to ACHIEVED unaided) still reaches ACHIEVED, appraised
  VERIFIED, before any founder action in NEW.

    python floors.py --suite SUITE --b0 RUN --new RUN [--form-ablated RUN] --out FILE
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def floors(suite: dict, b0: dict, new: dict, form_ablated: dict | None = None) -> dict:
    items = {i["item_id"]: i for i in suite["items"]}
    rb, rn = ({r["item_id"]: r for r in run["rows"]} for run in (b0, new))
    form = [k for k, v in items.items() if v["operator"] == "FORM"]
    f1 = [k for k in form if rn.get(k, {}).get("genesis_first_tick") != rb.get(k, {}).get("genesis_first_tick")
          or rn.get(k, {}).get("genesis_first_tick") is None]
    floor = [k for k, v in items.items() if v.get("partition") == "floor"]

    def unaided(row):
        return bool(row.get("achieved_before_action")) and "VERIFIED" in (row.get("appraised") or {}).get(
            row.get("mission_id"), [])
    f2 = [k for k in floor if not unaided(rn.get(k, {}))]
    out = {"F1": {"form_items": len(form), "differs_or_missing": f1, "pass": not f1},
           "F2": {"floor_items": len(floor), "not_closed_unaided": f2, "pass": not f2}}
    if form_ablated is not None:
        ra = {r["item_id"]: r for r in form_ablated["rows"]}
        kept = [k for k in form if ra.get(k, {}).get("genesis_first_tick") is not None]
        out["ablation_d"] = {"form_items_run": sum(k in ra for k in form), "genesis_still_opened": kept,
                             "pass": not kept and all(k in ra for k in form)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", type=Path, required=True)
    ap.add_argument("--b0", type=Path, required=True)
    ap.add_argument("--new", type=Path, required=True)
    ap.add_argument("--form-ablated", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    load = lambda p: json.loads(p.read_text())  # noqa: E731
    out = floors(load(a.suite), load(a.b0), load(a.new), load(a.form_ablated) if a.form_ablated else None)
    a.out.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v["pass"] for k, v in out.items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
