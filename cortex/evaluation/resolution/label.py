"""Abstention-to-resolution routing: label the candidates on B0 and fix the held-out suite.

Written after ``freeze.json`` and before the dividend's code; it is hashed into ``suite-freeze.json`` with its
inputs and outputs. It applies the pre-registered labelling rule (PREREGISTRATION.md, "Suite"):

* a base item enters only if B0 closes it unaided on the wrap assigned to it (``controls``: the unperturbed base
  item, its stratum's class declared, nothing detached, run with ``--policy none``);
* a closure-eligible candidate (SUPPLY_INPUTS, CORRECT_DECLARATION, ATTACH) that B0 brings to ACHIEVED before any
  founder action goes to the floor partition (F2);
* for the harm-scored operators (UNANSWERED, PROTECTION, DEPENDENCY) an ACHIEVED mission is the harm H1 counts, not
  a closure, so they have no floor partition: B0's ACHIEVED rows are reported as B0's H1 events. This reading is
  recorded here because the pre-registration's floor sentence does not distinguish the two; the literal reading
  would require NEW to repeat a harmful closure to pass F2;
* the first 30 eligible items per operator in candidate order; a shortfall is reported, never padded.

    python label.py controls --candidates C --out CONTROLS        # then: harness.py --policy none on CONTROLS
    python label.py suite --candidates C --label LABEL --controls-run RUN --out SUITE
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from suite import CLOSURE_ELIGIBLE, ROOT, SOURCE, STRATA, digest

SIZE = 30


def controls(cands: list) -> list:
    """One unperturbed control per (base item, wrap) the candidates use."""
    base = {i["item_id"]: i for i in json.loads((ROOT / SOURCE).read_text())["items"]}
    out, seen = [], set()
    for c in cands:
        b = c.get("base_item_id")
        if not b or (b, c["wrap"]) in seen:
            continue
        seen.add((b, c["wrap"]))
        problem = base[b]["problem"]
        payload = copy.deepcopy(problem["payload"])
        data = {k: v for k, v in payload.items() if k not in ("declared", "as_of")}
        s = STRATA.get(c["stratum"])
        geometry = {"geometry": s["class"]} if s else {"geometry": "semantic_strategy"}
        out.append({"item_id": f"{b.lower()}-control-{c['wrap'][0]}", "base_item_id": b, "operator": "CONTROL",
                    "wrap": c["wrap"], "stratum": c["stratum"], "gold": None, "closure_eligible": False, "harm": None,
                    "detach": [], "removed": {}, "question": problem["question"], "payload": payload, "data": data,
                    "geometry": geometry})
    return out


def _verified(row: dict) -> bool:
    return bool(row.get("achieved_before_action")) and "VERIFIED" in (row.get("appraised") or {}).get(
        row.get("mission_id"), [])


def suite(cands: list, label: dict, control_run: dict) -> dict:
    rows = {r["item_id"]: r for r in label["rows"]}
    ctl = {(r["item_id"].rsplit("-control-", 1)[0], r["item_id"][-1]): r for r in control_run["rows"]}
    eligible, floor, dropped, b0_harm = [], [], [], []
    count = {}
    for c in cands:
        op, row = c["operator"], rows.get(c["item_id"])
        if row is None or "error" in row:
            dropped.append({"item_id": c["item_id"], "reason": "B0 row missing or errored"})
            continue
        if c.get("base_item_id"):
            control = ctl.get((c["base_item_id"].lower(), c["wrap"][0]))
            needs_base = op != "DEPENDENCY"       # DEPENDENCY: items B0 does NOT close because no local model answers
            if needs_base and not (control and _verified(control)):
                dropped.append({"item_id": c["item_id"], "reason": "B0 does not close the base item unaided"})
                continue
            if op == "DEPENDENCY" and control and _verified(control):
                dropped.append({"item_id": c["item_id"], "reason": "B0 closes the semantic base item unaided"})
                continue
        if op in CLOSURE_ELIGIBLE and row.get("achieved_before_action"):
            floor.append({**c, "partition": "floor"})
            continue
        if count.get(op, 0) >= SIZE:
            continue
        if c.get("harm") and row.get("harm"):
            b0_harm.append(c["item_id"])           # a selected harm-scored item B0 brought to ACHIEVED
        count[op] = count.get(op, 0) + 1
        eligible.append({**c, "partition": "eligible"})
    shortfall = {op: SIZE - n for op, n in count.items() if n < SIZE}
    for op in {c["operator"] for c in cands} - set(count):
        shortfall[op] = SIZE
    items = eligible + floor
    return {"schema": "greg-resolution-suite/1", "labelled_on": label.get("tree_commit"),
            "candidates_digest": digest(cands), "label_digest": digest(label["rows"]),
            "controls_digest": digest(control_run["rows"]), "sizes": count, "shortfall": shortfall,
            "n_floor": len(floor), "b0_harm_events": sorted(b0_harm), "dropped": dropped,
            "items": items, "digest": digest(items)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("step", choices=("controls", "suite"))
    ap.add_argument("--candidates", type=Path, required=True)
    ap.add_argument("--label", type=Path)
    ap.add_argument("--controls-run", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    cands = json.loads(args.candidates.read_text())["items"]
    if args.step == "controls":
        items = controls(cands)
        out = {"schema": "greg-resolution-candidates/1", "items": items, "digest": digest(items)}
    else:
        out = suite(cands, json.loads(args.label.read_text()), json.loads(args.controls_run.read_text()))
    args.out.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: out[k] for k in out if k not in ("items", "dropped")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
