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
            ``code`` binds the verdict to the solver function's source digest at the run's source commit.

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
    # PR #155 lineage (finished 2026-10-14 11:12 and 12:28 UTC, after #158's v4). F2b re-measured F2's
    # identify -> optimise recipe on fresh seeds. X1 and X2 are cortex multi-organ routes and the v3 file
    # measures runtime-derived chains: frozen sources with no composition-recipe row.
    ("docs/evidence/greg-composition-lift/2026-10-14/results-v2.json", {"F2b": "identify_then_optimize"}),
    ("docs/evidence/greg-composition-lift/2026-10-14/results-v3.json", {}),
    ("docs/evidence/greg-composition-lift/2026-10-14-v5/results-v5.json", {"F8": "track_then_staff"}),
)
# In finish order; the last decides. PR #155's decisive retest (NO_GAIN, 2026-10-14) follows #158's (REGRESSION,
# 2026-10-08); both are kept in ``history`` and neither is a gain, so the default stays shadow.
P4_RUNS = ("docs/evidence/greg-learned-routing/2026-10-07/results-v2.json",
           "docs/evidence/greg-learned-routing/2026-10-08/results-v3.json",
           "docs/evidence/greg-learned-routing/2026-10-07/results-v3.json")
ADMISSION = "docs/evidence/greg-genome-admission"
# Instance identity (review of #179, H1). A later run decides a row only if it measured instances the deciding run
# did not; a run whose instances are a subset of the deciding run's is a same-instance re-run (evidence of
# reproducibility or timing noise), recorded in history, never a replication and never the deciding row.
# P6: (code closure of the generator at the run's source commit, seed). P4: the held-out payload digests in the
# run's suite at its source commit.
GENERATORS = {family: ("cortex/evaluation/composition_lift/run.py", "f2") for family in ("F2", "F2R", "F2b")}
P4_SUITES = {"docs/evidence/greg-learned-routing/2026-10-07/results-v2.json": "cortex/evaluation/learned_routing/suite-v2.json",
             "docs/evidence/greg-learned-routing/2026-10-08/results-v3.json": "cortex/evaluation/learned_routing/suite-v3.json",
             "docs/evidence/greg-learned-routing/2026-10-07/results-v3.json": "cortex/evaluation/learned_routing/suite-v3.json"}


def _git(commit: str | None, path: str) -> str | None:
    import subprocess
    if not commit:
        return None
    out = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True, text=True)
    return out.stdout if out.returncode == 0 else None


def p6_instances(data: dict, family: str) -> set:
    ids = [r["item_id"] for r in data.get("heldout", []) if r.get("family") == family]
    if family in GENERATORS:
        from greg.cognition.code_binding import at_commit, closure
        path, name = GENERATORS[family]
        bound = closure(path, name, at_commit(data["source_commit"])) if data.get("source_commit") else None
        if bound is not None:
            return {(bound["sha256"], int(i.rsplit("-", 1)[1])) for i in ids}
    return {(family, i) for i in ids}


def p4_instances(rel: str, data: dict) -> set:
    ids = {r["item_id"] for r in data.get("heldout", [])}
    text = _git(data.get("source_commit"), P4_SUITES.get(rel, ""))
    if text is None:
        return {("item", i) for i in ids}
    return {hashlib.sha256(json.dumps(item["problem"], sort_keys=True).encode()).hexdigest()
            for item in json.loads(text)["items"] if item["item_id"] in ids}


def _identity(keys: set) -> dict:
    return {"count": len(keys), "sha256": "sha256:" + hashlib.sha256(
        json.dumps(sorted(map(list, keys) if keys and isinstance(next(iter(keys)), tuple) else sorted(keys)),
                   sort_keys=True).encode()).hexdigest()}


def _decide(rows: dict, key: str, new: dict, keys: set, seen: dict) -> None:
    """Install ``new`` as the deciding row for ``key`` unless its instances are a subset of the current deciding
    row's; either way every run stays in ``history``."""
    prior = rows.get(key)
    new["instances"] = _identity(keys)
    if prior is None:
        rows[key], seen[key] = new, keys
        return
    overlap = len(keys & seen[key])
    if keys and keys <= seen[key]:              # unknown instances (no held-out rows) never count as a subset
        rerun = {**new, "kind": "same-instance re-run", "overlap_with": prior["evidence"], "overlap": overlap}
        prior["history"] = [*prior.get("history", []), rerun]
        return
    history = [*prior.pop("history", []), prior]
    new["history"] = history
    new["overlap_with_previous"] = overlap
    rows[key], seen[key] = new, keys
# PR #155 lineage, in run order: (file, key holding the rows, family when the file measures one family).
OPERATION_RUNS = (
    ("docs/evidence/greg-genome-admission/2026-10-14/results.json", "families", None),
    ("docs/evidence/greg-genome-admission/2026-10-14/results-v2.json", "families", None),
    ("docs/evidence/pr155-crowd-sparse/2026-10-14/results.json", "status", "crowd"),
)
# Verdicts measured against a competitor on held-out data; any other label is structural and changes no route.
MEASURED = ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY", "COMPOSITION_ONLY", "EXPERIMENTAL", "SUPERSEDED", "REJECTED")
# Errata on a frozen verdict: the frozen file is unchanged; the index routes on the corrected reading and keeps the
# raw label beside it. (family, raw label) -> (routing status, erratum).
ERRATA = {
    ("collective", "REJECTED"): (
        "EXPERIMENTAL",
        "review of #179 (M3): REJECTED came from 5-16 (p = 0.013) against the most-accurate-observer baseline, "
        "which uses the generator's hidden true accuracies and is not deployable; against the deployable competitor, "
        "simple majority, it tied 7-11 (p = 0.24). Not evidence of rejection; EXPERIMENTAL until a pre-registered "
        "comparison against deployable baselines"),
}


def _measured_code(family: str, commit: str | None) -> dict | None:
    """The family's solver at the run's source commit: its current path and function name, the digest of that
    function's source as committed then (git show), and the digest of its static dependency closure then
    (greg.cognition.code_binding). A positive verdict is bound to the closure; None when there is no solver."""
    import subprocess
    from greg.cognition.compiler import function_digest, solver_code
    now = solver_code(family)
    if now is None:
        return None
    from greg.cognition.code_binding import at_commit, closure
    code = {"path": now["path"], "function": now["function"], "sha256": None, "closure_sha256": None,
            "closure_members": None}
    if commit:
        out = subprocess.run(["git", "show", f"{commit}:{now['path']}"], cwd=ROOT, capture_output=True, text=True)
        if out.returncode == 0:
            code["sha256"] = function_digest(out.stdout, now["function"])      # entry function (historical scope)
        measured = closure(now["path"], now["function"], at_commit(commit))      # the executable closure measured
        if measured is not None:
            code["closure_sha256"], code["closure_members"] = measured["sha256"], measured["members"]
    return code


def _recipe_code(recipe: str, commit: str | None) -> dict | None:
    from greg.cognition.code_binding import at_commit
    from greg.cognition.compiler import recipe_code
    if not commit:
        return None
    measured = recipe_code(recipe, at_commit(commit))
    if measured is None:
        return None
    # the RECIPES entry as it stood at that commit
    text = _git(commit, "greg/cognition/composition.py")
    import ast
    entry = None
    for node in ast.parse(text).body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == "RECIPES" for t in node.targets):
            value = ast.literal_eval(node.value)
            entry = "sha256:" + hashlib.sha256(json.dumps(value.get(recipe), sort_keys=True).encode()).hexdigest()
    return {**measured, "recipe_entry_sha256": entry}


def _genome_code(family: str, commit: str | None) -> dict | None:
    """The genome solver's dependency closure at the admission run's source commit, when it is in git."""
    import inspect
    from greg.cognition.code_binding import ROOT as REPO, at_commit, closure
    from greg.cognition.genomes import library
    item = library.executables().get(family)
    if item is None or not commit:
        return None
    path = Path(inspect.getsourcefile(item.solve)).resolve().relative_to(REPO).as_posix()
    bound = closure(path, item.solve.__name__, at_commit(commit))
    return None if bound is None else {"function": bound["entry"], "closure_sha256": bound["sha256"],
                                       "closure_members": bound["members"]}


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> dict:
    index = {"schema": "greg-mind-evidence-index/0.1", "sources": [], "missing_sources": [],
             "recipes": {}, "routing": {}, "genomes": {}, "operations": {},
             "rule": "frozen held-out verdicts only; a later frozen run for the same recipe or family replaces "
                     "an earlier one, and both stay in git"}
    seen_recipes, seen_routing = {}, {}
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
            # the latest family measured for a recipe decides its routing unless it re-measured the deciding
            # run's instances; earlier verdicts stay visible
            _decide(index["recipes"], recipe, {
                "lift": lift, "status": "VPL_LIFT" if lift else "NO_LIFT", "family": family,
                "prefer": None if lift else row["best_constituent"],
                "wins": row["routed_wins"], "losses": row["routed_losses"],
                "p_one_sided": row["sign_test_p_one_sided"], "evidence": f"{rel}#summary.{family}",
                # the recipe code this verdict measured (greg.cognition.compiler.recipe_stale)
                "code": _recipe_code(recipe, data.get("source_commit"))},
                p6_instances(data, family), seen_recipes)
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
        # every frozen retest stays visible beside the deciding one; a retest of the same instances never decides
        _decide(index["routing"], "conditional_competence", {
            "verdict": verdict, "consequence": data.get("consequence") or summary.get("consequence"),
            "default": "shadow (observed, never applied)" if verdict != "GAIN" else "conditional",
            "evidence": f"{rel}#summary.{key}"}, p4_instances(rel, data), seen_routing)
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
                                            "version": row.get("version"), "history": history,
                                            # the solver closure measured (drift is reported; a changed default
                                            # configuration gates: compiler.family_status)
                                            "code": _genome_code(family, data.get("source_commit"))}
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
            routed, erratum = ERRATA.get((family, raw), (raw if raw in MEASURED else "UNEVALUATED", None))
            index["operations"][family] = {"status": routed, "raw_status": raw,
                                           **({"erratum": erratum} if erratum else {}),
                                           "measured": raw in MEASURED, "evidence": pointer, "history": history,
                                           # the frozen run's named competitor and baseline (None when it had
                                           # none): an acquisition candidate for a SUPERSEDED verdict
                                           "competitor": row.get("competitor"), "baseline": row.get("baseline"),
                                           # the solver code this verdict measured (greg.cognition.compiler
                                           # .operation_status routes a positive verdict only on that code)
                                           "code": _measured_code(family, data.get("source_commit"))}
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
