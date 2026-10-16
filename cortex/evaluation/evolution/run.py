"""P8 run: protected evolution of the routing-policy genome, then one held-out comparison with the baseline.

1. ``--freeze`` pins the evaluator source, its data files and the search settings (before any search).
2. The search (``greg.cognition.evolution.evolve``) sees development scores only.
3. Adversarial checks run against the live machinery: a candidate naming an authority-bearing key is
   refused; an edited evaluator stops the run.
4. The champion and the baseline are scored once on held-out data.

Verdict (frozen): RETAIN the champion only if it decides more held-out items correctly than the baseline,
adds no wrong answer, and the one-sided exact sign test over discordant items gives p < 0.05; otherwise
REJECT (the baseline genome stays). Selection never touches held-out data.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from greg.cognition.evolution_routing import (BASELINE, MutationRefused, ProtectedEvaluator, evolve,  # noqa: E402
                                              sha256, validate)

EVALUATOR = HERE / "evaluator.py"
MANIFEST = HERE / "freeze-v1.json"
DATA = ["docs/evidence/greg-learned-routing/2026-10-07/results-v2.json",
        "docs/evidence/greg-learned-routing/2026-10-07/results-v3.json",
        "cortex/evaluation/learned_routing/suite-v3.json", "greg/cognition/conditional_competence.py",
        "greg/cognition/evolution.py"]
SETTINGS = {"generations": 12, "population": 8, "seed": 20261007}
RULE = "RETAIN if held-out correct > baseline, no added wrong, one-sided sign test p < 0.05; else REJECT"


def inputs() -> dict:
    return {"evaluator": sha256(EVALUATOR), "data": {p: sha256(ROOT / p) for p in DATA}, "settings": SETTINGS,
            "rule": RULE}


def sign_test(wins, losses):
    n = wins + losses
    return 1.0 if n == 0 else sum(math.comb(n, k) for k in range(wins, n + 1)) / 2 ** n


def adversarial(evaluate: ProtectedEvaluator) -> dict:
    out = {}
    try:
        validate({**BASELINE, "approval_threshold": 0})
        out["authority_key"] = "ACCEPTED (defect)"
    except MutationRefused as exc:
        out["authority_key"] = f"refused: {exc}"
    try:
        validate({**BASELINE, "features": ["kind", "owner_override"]})
        out["unknown_feature"] = "ACCEPTED (defect)"
    except MutationRefused as exc:
        out["unknown_feature"] = f"refused: {exc}"
    with tempfile.TemporaryDirectory() as tmp:          # an edited copy of the evaluator must be refused
        forged = Path(tmp) / "evaluator.py"
        shutil.copy(EVALUATOR, forged)
        forged.write_text(forged.read_text() + "\n# a candidate tried to edit its judge\n")
        try:
            ProtectedEvaluator(forged, evaluate.pinned, cwd=ROOT)(BASELINE, "dev")
            out["edited_evaluator"] = "ACCEPTED (defect)"
        except RuntimeError as exc:
            out["edited_evaluator"] = f"refused: {str(exc)[:120]}"
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.freeze:
        if MANIFEST.exists():
            raise SystemExit("refusing to overwrite an existing freeze; create a new version")
        MANIFEST.write_text(json.dumps({"frozen_at": datetime.now(timezone.utc).isoformat(), "inputs": inputs()},
                                       indent=2) + "\n")
        return
    frozen = json.loads(MANIFEST.read_text())["inputs"]
    if frozen != inputs():
        raise SystemExit("FROZEN_INPUT_CHANGED: results cannot be reported")
    evaluate = ProtectedEvaluator(EVALUATOR, frozen["evaluator"], cwd=ROOT)
    result = evolve(evaluate, **SETTINGS)
    champion, baseline = result["champion"], result["baseline"]
    held = {"champion": evaluate(champion["genome"], "heldout"), "baseline": evaluate(baseline["genome"], "heldout")}
    c, b = held["champion"]["per_item"], held["baseline"]["per_item"]
    wins = sum(1 for x, y in zip(c, b) if x == "correct" and y != "correct")
    losses = sum(1 for x, y in zip(c, b) if y == "correct" and x != "correct")
    p = sign_test(wins, losses)
    retain = (held["champion"]["correct"] > held["baseline"]["correct"]
              and held["champion"]["wrong"] <= held["baseline"]["wrong"] and p < 0.05)
    report = {"schema": "greg-protected-evolution/1", "manifest_sha256": sha256(MANIFEST),
              "finished_at": datetime.now(timezone.utc).isoformat(),
              "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "settings": SETTINGS, "rule": RULE,
              "dev": {"baseline": {k: baseline["dev"][k] for k in ("correct", "wrong", "no_decision", "n")},
                      "champion": {k: champion["dev"][k] for k in ("correct", "wrong", "no_decision", "n")},
                      "champion_genome": champion["genome"], "champion_id": champion["id"]},
              "heldout": {k: {f: v[f] for f in ("correct", "wrong", "no_decision", "n")} for k, v in held.items()},
              "discordant": {"wins": wins, "losses": losses, "sign_test_p_one_sided": round(p, 6)},
              "verdict": "RETAIN" if retain else "REJECT",
              "adversarial": adversarial(evaluate),
              "lineage": [{"id": x["id"], "parent": x["parent"], "move": x["move"], "genome": x["genome"],
                           "dev_correct": x["dev"]["correct"], "dev_wrong": x["dev"]["wrong"]}
                          for x in result["lineage"]]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps({k: report[k] for k in ("dev", "heldout", "discordant", "verdict", "adversarial")}, indent=1))


if __name__ == "__main__":
    main()
