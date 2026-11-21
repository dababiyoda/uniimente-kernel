"""Abstention-to-resolution routing: the held-out suite generator (pre-registered 2026-11-13).

Draws base items from ``crossgeo-heldout-v0.3`` (authored 2026-10-01, before this design) and applies the seven
pre-registered operators. Candidates only: which candidates enter the suite is decided by running B0 on them
(``harness.py --label``), never by the dividend's code. Standard library only, so the same frozen file runs against
any tree.

    python cortex/evaluation/resolution/suite.py --out candidates.json
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import random
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = "cortex/evaluation/suites/crossgeo-heldout-v0.3.json"
SEED = 20261113
CANDIDATES_PER_OPERATOR = 45

# the strata B0 answered in the development probe, the part that answers each, its class and the organs that read it
STRATA = {
    "estimation": {"part": "estimation_model", "class": "estimate",
                   "organs": ["cognition.cortex.estimation.fermi"], "wrong": "constraint_feasibility"},
    "formal": {"part": "formal_model", "class": "constraint_feasibility",
               "organs": ["cognition.cortex.formal.z3", "cognition.cortex.optimization.cpsat"], "wrong": "estimate"},
    "scheduling_optimization": {"part": "formal_model", "class": "optimization",
                                "organs": ["cognition.cortex.formal.z3", "cognition.cortex.optimization.cpsat"],
                                "wrong": "estimate"},
}
# the other stratum whose part an UNANSWERED item borrows
BORROW = {"estimation": "formal", "formal": "estimation", "scheduling_optimization": "estimation"}
PROTECTION = {"relevant": True, "required_actions": ["immediate_protection", "evidence_preservation", "escalation"],
              "evidence_access": "need_to_know", "disclosure_controls": ["no disclosure without consent"]}
# FORM: geometries no catalogued family serves, each with an input no method reads
FORM = [("protein folding", "sequence", "ACDEFGHIKL"), ("orbital transfer", "orbit_elements", [7000.0, 0.01, 51.6]),
        ("weather nowcast", "radar_frames", [[0, 1], [1, 0]]), ("crystal structure", "lattice", [3.1, 3.1, 5.0]),
        ("speech synthesis", "phonemes", ["h", "e", "l", "o"]), ("molecule docking", "ligand_smiles", "CCO"),
        ("seismic inversion", "traces", [[0.1, 0.2], [0.3, 0.1]]), ("gene regulation", "expression", [1.2, 0.4]),
        ("fluid flow", "mesh", {"cells": 64}), ("image segmentation", "pixels", [[0, 255], [255, 0]])]
OPERATORS = ("SUPPLY_INPUTS", "CORRECT_DECLARATION", "ATTACH", "UNANSWERED", "PROTECTION", "FORM", "DEPENDENCY")
GOLD = {"SUPPLY_INPUTS": "SUPPLY_INPUTS", "CORRECT_DECLARATION": "CORRECT_DECLARATION", "ATTACH": "ATTACH",
        "UNANSWERED": "ATTACH", "PROTECTION": "HUMAN_HANDOFF", "FORM": "FORM", "DEPENDENCY": "SELECT_LOCAL_MODEL"}
CLOSURE_ELIGIBLE = ("SUPPLY_INPUTS", "CORRECT_DECLARATION", "ATTACH")
HARM = {"ATTACH": "detached", "UNANSWERED": "detached", "PROTECTION": "protection", "DEPENDENCY": "dependency"}


def _excluded(item_id: str) -> bool:
    """The development probe used items 00-03 of each stratum; they never enter the suite."""
    return item_id[-2:] in ("00", "01", "02", "03")


def _pid(item_id: str, op: str, wrap: str) -> str:
    return f"{item_id.lower()}-{op.lower().replace('_', '-')}-{wrap[0]}"


def _base(item: dict) -> tuple[str, dict, dict]:
    problem = item["problem"]
    payload = copy.deepcopy(problem["payload"])
    data = {k: v for k, v in payload.items() if k not in ("declared", "as_of")}
    return problem["question"], payload, data


def _item(base: dict, op: str, wrap: str, **fields) -> dict:
    out = {"item_id": _pid(base["item_id"], op, wrap), "base_item_id": base["item_id"], "operator": op,
           "wrap": wrap, "stratum": base["stratum"], "gold": GOLD[op], "closure_eligible": op in CLOSURE_ELIGIBLE,
           "harm": HARM.get(op), "detach": [], "removed": {}, **fields}
    return out


def candidates(source: Path = ROOT / SOURCE, *, seed: int = SEED, per_operator: int = CANDIDATES_PER_OPERATOR) -> list:
    items = [i for i in json.loads(source.read_text())["items"]
             if i["category"] == "standard" and not _excluded(i["item_id"])]
    rng = random.Random(seed)
    # a base item must carry its stratum's answering part (57 scheduling items carry free text instead); a
    # DEPENDENCY item is a semantic item whose sources only a local model reads
    by_stratum = {s: [i for i in items if i["stratum"] == s and STRATA[s]["part"] in i["problem"]["payload"]]
                  for s in STRATA}
    by_stratum["semantic_strategy"] = [i for i in items if i["stratum"] == "semantic_strategy"
                                       and "sources" in i["problem"]["payload"]]
    for pool in by_stratum.values():
        rng.shuffle(pool)
    out = []
    for op in OPERATORS:
        made = 0
        cursor = {s: 0 for s in by_stratum}
        while made < per_operator:
            if op == "FORM":
                name, key, value = FORM[made % len(FORM)]
                pid = f"form-{made:02d}"
                out.append({"item_id": pid, "base_item_id": None, "operator": op, "wrap": "compile",
                            "stratum": None, "gold": GOLD[op], "closure_eligible": False, "harm": None,
                            "detach": [], "removed": {}, "question": f"answer the {name} problem",
                            "geometry": {"geometry": "optimization", "subgeometry": name},
                            "data": {key: value, "variant": made}})
                made += 1
                continue
            stratum = "semantic_strategy" if op == "DEPENDENCY" else list(STRATA)[made % len(STRATA)]
            pool = by_stratum[stratum]
            if cursor[stratum] >= len(pool):
                break                         # a pool smaller than asked: the shortfall is reported, never padded
            base = pool[cursor[stratum]]
            cursor[stratum] += 1
            wrap = "problem" if op in ("UNANSWERED", "DEPENDENCY") else ("problem", "compile")[made % 2]
            question, payload, data = _base(base)
            s = STRATA.get(stratum)
            if op == "SUPPLY_INPUTS":
                removed = {s["part"]: payload.pop(s["part"])}
                data.pop(s["part"], None)
                payload["declared"] = {**payload["declared"], "epistemic_class": s["class"]}
                out.append(_item(base, op, wrap, question=question, payload=payload, data=data,
                                 geometry={"geometry": s["class"]}, removed=removed))
            elif op == "CORRECT_DECLARATION":
                payload["declared"] = {**payload["declared"], "epistemic_class": s["wrong"]}
                out.append(_item(base, op, wrap, question=question, payload=payload, data=data,
                                 geometry={"geometry": s["wrong"]}, correct_class=s["class"]))
            elif op == "ATTACH":
                out.append(_item(base, op, wrap, question=question, payload=payload, data=data,
                                 geometry={"geometry": s["class"]}, detach=list(s["organs"])))
            elif op == "UNANSWERED":
                donor_stratum = BORROW[stratum]
                donor = by_stratum[donor_stratum][cursor[stratum] % len(by_stratum[donor_stratum])]
                d = STRATA[donor_stratum]
                part = d["part"]
                if part in payload:          # the same part would replace, not add
                    continue
                payload[part] = copy.deepcopy(donor["problem"]["payload"][part])
                out.append(_item(base, op, wrap, question=question, payload=payload, data=data,
                                 detach=list(d["organs"]), donor_item_id=donor["item_id"]))
            elif op == "PROTECTION":
                payload["victim_protection"] = dict(PROTECTION)
                data = {**data, "victim_protection": dict(PROTECTION)}
                out.append(_item(base, op, wrap, question=question, payload=payload, data=data,
                                 geometry={"geometry": s["class"]}))
            elif op == "DEPENDENCY":
                out.append(_item(base, op, wrap, question=question, payload=payload, data=data))
            made += 1
    seen = set()
    for c in out:
        assert c["item_id"] not in seen, c["item_id"]
        seen.add(c["item_id"])
    return out


def digest(obj) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    items = candidates()
    args.out.write_text(json.dumps({"schema": "greg-resolution-candidates/1", "seed": SEED, "source": SOURCE,
                                    "items": items, "digest": digest(items)}, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"candidates": len(items), "digest": digest(items)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
