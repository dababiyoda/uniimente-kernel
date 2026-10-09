"""Build docs/evidence/greg-mind-evidence-index.json: frozen verdicts that change the Mind's routing.

The Competency Compiler (greg/cognition/compiler.py) reads this index so negative evidence changes
future routing (directive 2026-10-07, section 31 item 13):

* recipes   P6 composition-lift verdicts per recipe; the latest frozen run for a family wins. A recipe
            without lift names the constituent it lost to, and the compiler prefers that constituent.
* routing   P4 conditional-competence verdicts and their predeclared consequence.
* genomes   IntelligenceGenome admission statuses from frozen held-out admission runs.

Only frozen, committed result files are read; a missing source is listed, never invented. Run:
    PYTHONPATH=. python scripts/build_mind_evidence_index.py
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/evidence/greg-mind-evidence-index.json"
# Family -> recipe, in run order: later files replace earlier verdicts for the same recipe.
P6_RUNS = (
    ("docs/evidence/greg-composition-lift/2026-10-07/results.json",
     {"F1": "estimate_then_optimize", "F2": "identify_then_optimize"}),
    ("docs/evidence/greg-composition-lift/2026-10-08/results-v2.json",
     {"F2R": "identify_then_optimize", "F3": "graph_then_allocate", "F4": "bayes_then_voi",
      "F5": "forecast_then_allocate"}),
)
P4_RUNS = ("docs/evidence/greg-learned-routing/2026-10-07/results-v2.json",
           "docs/evidence/greg-learned-routing/2026-10-08/results-v3.json")
ADMISSION = "docs/evidence/greg-genome-admission"


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    index = {"schema": "greg-mind-evidence-index/0.1", "sources": [], "missing_sources": [],
             "recipes": {}, "routing": {}, "genomes": {},
             "rule": "frozen held-out verdicts only; a later frozen run for the same recipe or family replaces "
                     "an earlier one, and both stay in git"}
    for rel, families in P6_RUNS:
        path = ROOT / rel
        if not path.exists():
            index["missing_sources"].append(rel)
            continue
        data = json.loads(path.read_text())
        index["sources"].append({"path": rel, "sha256": _sha(path), "source_commit": data.get("source_commit")})
        for family, recipe in families.items():
            row = data["summary"].get(family)
            if row is None:
                continue
            lift = bool(row["lift"])
            index["recipes"][recipe] = {
                "lift": lift, "status": "VPL_LIFT" if lift else "NO_LIFT", "family": family,
                "prefer": None if lift else row["best_constituent"],
                "wins": row["routed_wins"], "losses": row["routed_losses"],
                "p_one_sided": row["sign_test_p_one_sided"], "evidence": f"{rel}#summary.{family}"}
    for rel in P4_RUNS:
        path = ROOT / rel
        if not path.exists():
            index["missing_sources"].append(rel)
            continue
        data = json.loads(path.read_text())
        index["sources"].append({"path": rel, "sha256": _sha(path), "source_commit": data.get("source_commit")})
        summary = data.get("summary", {})
        key = "primary_conditional_vs_static" if "primary_conditional_vs_static" in summary else "conditional_vs_static"
        verdict = (summary.get(key) or {}).get("verdict")
        index["routing"]["conditional_competence"] = {
            "verdict": verdict, "consequence": data.get("consequence") or summary.get("consequence"),
            "default": "shadow (observed, never applied)" if verdict != "GAIN" else "conditional",
            "evidence": f"{rel}#summary.{key}"}
    base = ROOT / ADMISSION
    for path in sorted(base.glob("*/results.json")) if base.exists() else []:
        data = json.loads(path.read_text())
        rel = str(path.relative_to(ROOT))
        index["sources"].append({"path": rel, "sha256": _sha(path), "source_commit": data.get("source_commit")})
        # The admission harness (greg/cognition/genomes/admission.py) writes one entry per family under "genomes".
        for family, row in (data.get("genomes") or {}).items():
            if row.get("status"):
                index["genomes"][family] = {"status": row["status"], "evidence": f"{rel}#genomes.{family}"}
    if not base.exists() or not index["genomes"]:
        index["missing_sources"].append(f"{ADMISSION}/*/results.json (no frozen held-out admission run yet)")
    return index


def main() -> None:
    index = build()
    OUT.write_text(json.dumps(index, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"recipes": {k: v["status"] for k, v in index["recipes"].items()},
                      "routing": index["routing"], "genomes": len(index["genomes"]),
                      "missing": index["missing_sources"]}, indent=1))


if __name__ == "__main__":
    main()
