"""R1-A evaluation runner: hostile and honest workers through the canonical path, on one kernel tree.

    python run_evaluation.py --kernel TREE --label new|baseline --out results-LABEL.json [--ablation] [--timing]
    python run_evaluation.py --render results-baseline.json results-new.json    # README tables, from the files

Pre-registered in PREREGISTRATION.md (commit 57b5c17). Every case is a founder-signed mission on a real ``Body``:
``worker.commission`` (private clone, GREG-collected diff, GREG's acceptance run), the in-body ``worker.appraise``
sensor, and, on a closure, the separate-process appraiser the Body runs. Workers are deterministic scripted test
doubles; nothing calls a model or a paid service. The one_machine cases use ``templates.one_machine`` with its
organs check and strategy removed (no organ checkout is needed); its Mind, Genesis, bind and Hands are unchanged.

Regimes: ``required`` (the real bubblewrap envelope runs acceptance) and ``supervised`` (body setting supervised, the
OS envelope refused in this process, as on #178's hosts). Ablation (new tree only) disables one layer at a time by
replacing that layer's function in ``greg.workers`` with one that reports nothing.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("acceptance_dividend_cases",
                                               HERE.parents[3] / "tests" / "acceptance_dividend_cases.py")
cases = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cases)
CASES, ABLATION_CASES, LAYERS, run_case, passed = (cases.CASES, cases.ABLATION_CASES, cases.LAYERS, cases.run_case,
                                                   cases.passed)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kernel")
    ap.add_argument("--label")
    ap.add_argument("--out")
    ap.add_argument("--cases", default=",".join(CASES))
    ap.add_argument("--regimes", default="required,supervised")
    ap.add_argument("--ablation", action="store_true")
    ap.add_argument("--timing", action="store_true")
    ap.add_argument("--scratch", default=None)
    ap.add_argument("--render", nargs="*")
    a = ap.parse_args(argv)
    if a.render:
        print(render([json.loads(Path(p).read_text()) for p in a.render]))
        return 0
    kernel = Path(a.kernel).resolve()
    sys.path.insert(0, str(kernel))
    os.chdir(kernel)
    import tempfile
    head = subprocess.run(["git", "-C", str(kernel), "rev-parse", "HEAD"], capture_output=True,
                          text=True).stdout.strip()
    dirty = subprocess.run(["git", "-C", str(kernel), "status", "--porcelain", "--", "greg", "tests"],
                           capture_output=True, text=True).stdout.strip()
    out = {"label": a.label, "kernel": str(kernel), "head": head, "dirty_greg_or_tests": bool(dirty),
           "python": sys.version.split()[0], "rows": [], "ablation": [], "timing": []}
    scratch = Path(a.scratch) if a.scratch else None

    def tmpdir():
        return tempfile.TemporaryDirectory(prefix="r1a-", dir=scratch)
    for regime in a.regimes.split(","):
        for case in a.cases.split(","):
            with tmpdir() as t:
                row = run_case(kernel, Path(t), case, regime)
            out["rows"].append(row)
            print(json.dumps({k: row[k] for k in ("case", "regime", "final_verdict", "achieved", "separate_appraiser",
                                                  "acceptance_commands_per_appraisal", "wall_seconds")}), flush=True)
        if a.ablation:
            for layer in LAYERS:
                for case in ABLATION_CASES:
                    with tmpdir() as t:
                        row = run_case(kernel, Path(t), case, regime, ablate=layer)
                    out["ablation"].append(row)
                    print(json.dumps({k: row[k] for k in ("case", "regime", "ablate", "final_verdict", "achieved")}),
                          flush=True)
        if a.timing:
            with tmpdir() as t:
                row = run_case(kernel, Path(t), "O1", regime, timing=True)
            out["timing"].append(row)
            print(json.dumps({"timing": row["timing"], "regime": regime}), flush=True)
    Path(a.out).write_text(json.dumps(out, indent=1, sort_keys=True, default=str) + "\n")
    return 0


def render(results: list[dict]) -> str:
    """The README tables, computed from result files only."""
    by = {r["label"]: r for r in results}
    lines = []
    regimes = sorted({row["regime"] for r in results for row in r["rows"]}, key=["required", "supervised"].index)
    labels = [lab for lab in ("baseline", "new") if lab in by]
    head = "| Case | " + " | ".join(f"{lab} / {reg}" for lab in labels for reg in regimes) + " |"
    lines += ["### Hostile and honest cases (in-body verdict; ACHIEVED; separate appraiser)", "", head,
              "|" + "---|" * (1 + len(labels) * len(regimes))]
    for case in CASES:
        cells = []
        for lab in labels:
            for reg in regimes:
                row = next((x for x in by[lab]["rows"] if x["case"] == case and x["regime"] == reg), None)
                if row is None:
                    cells.append("not run")
                    continue
                mark = "PASSED" if passed(row) else "refused"
                cells.append(f"{row['final_verdict']}; {'ACHIEVED' if row['achieved'] else 'not achieved'}; "
                             f"{row['separate_appraiser'] or 'no closure'} ({mark})")
        lines.append(f"| {case} | " + " | ".join(cells) + " |")
    new = by.get("new")
    if new and new["ablation"]:
        lines += ["", "### Ablation (new tree): PASSED means the hostile worker got through with that layer off", "",
                  "| Case | regime | all layers | " + " | ".join(f"- {layer}" for layer in LAYERS) + " |",
                  "|---|---|---|" + "---|" * len(LAYERS)]
        for reg in regimes:
            for case in ABLATION_CASES:
                full = next(x for x in new["rows"] if x["case"] == case and x["regime"] == reg)
                cells = []
                for layer in LAYERS:
                    row = next((x for x in new["ablation"] if x["case"] == case and x["regime"] == reg
                                and x["ablate"] == layer), None)
                    cells.append("not run" if row is None else ("PASSED" if passed(row) else "refused"))
                full_mark = "PASSED" if passed(full) else "refused"
                lines.append(f"| {case} | {reg} | {full_mark} | " + " | ".join(cells) + " |")
        lines += ["", "Unique catches (refused with all layers, PASSED with only that layer off):", ""]
        for layer in LAYERS:
            unique = sorted({x["case"] + "/" + x["regime"] for x in new["ablation"]
                             if x["ablate"] == layer and passed(x)
                             and not passed(next(y for y in new["rows"] if y["case"] == x["case"]
                                                 and y["regime"] == x["regime"]))})
            lines.append(f"- {layer}: {', '.join(unique) or 'none'}")
    lines += ["", "### Cost (honest one_machine path, O1)", "", "| tree | regime | median appraisal s (5 runs) | runs | "
              "acceptance commands per appraisal |", "|---|---|---|---|---|"]
    for lab in labels:
        for row in by[lab]["timing"]:
            t = row["timing"]
            lines.append(f"| {lab} | {row['regime']} | {t['median_seconds']} | {t['seconds']} | {sorted(set(t['commands']))} |")
    for reg in regimes:
        med = {lab: next((r["timing"]["median_seconds"] for r in by[lab]["timing"] if r["regime"] == reg), None)
               for lab in labels}
        if len(labels) == 2 and all(med.values()):
            lines.append(f"\n{reg}: appraisal wall time {100 * (med['new'] / med['baseline'] - 1):+.1f}% (new vs baseline)")
    lines += ["", "Trees: " + "; ".join(f"{lab} `{by[lab]['head'][:9]}`"
                                       + (" (with uncommitted greg/tests changes)" if by[lab]['dirty_greg_or_tests'] else "")
                                       for lab in labels)]
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
