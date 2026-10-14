"""Build docs/evidence/greg-mind-evidence-index.json: frozen verdicts that change the Mind's routing.

The Competency Compiler (greg/cognition/compiler.py) reads this index so negative evidence changes
future routing (directive 2026-10-07, section 31 item 13):

* recipes   P6 composition-lift verdicts per recipe; the latest frozen run for a family wins. A recipe
            without lift names the constituent it lost to, and the compiler prefers that constituent.
* routing   P4 conditional-competence verdicts and their predeclared consequence.
* genomes   IntelligenceGenome admission statuses from frozen held-out admission runs; the latest run's
            status decides, and ``history`` keeps every run's status and version.
* operations  PR #155 lineage: frozen held-out admission verdicts for the operation families (the pre-genome
            solvers and the #155 repertoire), keyed by family. A measured verdict routes; a structural label
            (alias, superseded by a canonical organ, not run, not benchmarked, route only) is kept as
            ``raw_status`` and routes as UNEVALUATED. The latest run decides; ``history`` keeps every run.

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
    ("docs/evidence/greg-composition-lift/2026-10-14-v3/results-v3.json", {"F6": "forecast_then_staff"}),
    ("docs/evidence/greg-composition-lift/2026-10-14-v4/results-v4.json", {"F7": "graph_then_allocate"}),
)
P4_RUNS = ("docs/evidence/greg-learned-routing/2026-10-07/results-v2.json",
           "docs/evidence/greg-learned-routing/2026-10-08/results-v3.json")
ADMISSION = "docs/evidence/greg-genome-admission"
# PR #155 lineage, in run order: (file, key holding the rows, family when the file measures one family).
OPERATION_RUNS = (
    ("docs/evidence/greg-genome-admission/2026-10-14/results.json", "families", None),
    ("docs/evidence/greg-genome-admission/2026-10-14/results-v2.json", "families", None),
    ("docs/evidence/pr155-crowd-sparse/2026-10-14/results.json", "status", "crowd"),
)
# Verdicts measured against a competitor on held-out data; any other label is structural and changes no route.
MEASURED = ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY", "COMPOSITION_ONLY", "EXPERIMENTAL", "SUPERSEDED", "REJECTED")


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    index = {"schema": "greg-mind-evidence-index/0.1", "sources": [], "missing_sources": [],
             "recipes": {}, "routing": {}, "genomes": {}, "operations": {},
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
            prior = index["recipes"].get(recipe)
            index["recipes"][recipe] = {
                "lift": lift, "status": "VPL_LIFT" if lift else "NO_LIFT", "family": family,
                "prefer": None if lift else row["best_constituent"],
                "wins": row["routed_wins"], "losses": row["routed_losses"],
                "p_one_sided": row["sign_test_p_one_sided"], "evidence": f"{rel}#summary.{family}"}
            if prior:
                # the latest family measured for a recipe decides its routing; earlier verdicts stay visible
                index["recipes"][recipe]["history"] = [*prior.pop("history", []), prior]
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
        if "genomes" not in data:
            continue        # another harness's file in this directory (PR #155's admission runs: see OPERATION_RUNS)
        rel = str(path.relative_to(ROOT))
        index["sources"].append({"path": rel, "sha256": _sha(path), "source_commit": data.get("source_commit")})
        # The admission harness (greg/cognition/genomes/admission.py) writes one entry per family under "genomes".
        for family, row in (data.get("genomes") or {}).items():
            if row.get("status"):
                # every frozen run's status, oldest first: a status that changed between independent held-out
                # runs is a sample near a rule boundary, and routing and the founder should see that
                history = (index["genomes"].get(family) or {}).get("history", []) + [
                    {"run": path.parent.name, "status": row["status"], "version": row.get("version")}]
                # the version the status was measured at: a later code change needs re-admission
                index["genomes"][family] = {"status": row["status"], "evidence": f"{rel}#genomes.{family}",
                                            "version": row.get("version"), "history": history}
                seconds = ((row.get("arms") or {}).get("candidate") or {}).get("median_seconds")
                if seconds is not None:
                    # held-out median latency at this version: a tie-break within one status, never a status
                    index["genomes"][family]["median_seconds"] = seconds
                subs = {name: {"n": sub["n"], **{k: sub["vs_competitor"][k]
                                                 for k in ("wins", "losses", "ties", "p_better", "p_worse")}}
                        for name, sub in (row.get("subregions") or {}).items()}
                if subs:
                    # measured per native subregion against the competitor: reported in receipts, never a status
                    index["genomes"][family]["subregions_vs_competitor"] = subs
                    index["genomes"][family]["competitor"] = row.get("competitor")
    if not base.exists() or not index["genomes"]:
        index["missing_sources"].append(f"{ADMISSION}/*/results.json (no frozen held-out admission run yet)")
    for rel, key, single in OPERATION_RUNS:
        path = ROOT / rel
        if not path.exists():
            index["missing_sources"].append(rel)
            continue
        data = json.loads(path.read_text())
        index["sources"].append({"path": rel, "sha256": _sha(path), "source_commit": data.get("source_commit")})
        for family, row in ({single: data[key]} if single else data[key]).items():
            raw = row.get("status")
            if not raw:
                continue
            pointer = f"{rel}#{key}" if single else f"{rel}#{key}.{family}"
            history = (index["operations"].get(family) or {}).get("history", []) + [{"evidence": pointer,
                                                                                        "status": raw}]
            index["operations"][family] = {"status": raw if raw in MEASURED else "UNEVALUATED", "raw_status": raw,
                                           "measured": raw in MEASURED, "evidence": pointer, "history": history}
    return index


def main() -> None:
    index = build()
    OUT.write_text(json.dumps(index, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"recipes": {k: v["status"] for k, v in index["recipes"].items()},
                      "routing": index["routing"], "genomes": len(index["genomes"]),
                      "operations": {k: v["status"] for k, v in index["operations"].items()},
                      "missing": index["missing_sources"]}, indent=1))


if __name__ == "__main__":
    main()
