"""The IntelligenceGenome library: one inventory of every intelligence GREG can (or intends to) recruit.

Founder directive 2026-10-07, step 6 ("begin executable IntelligenceGenome expansion"): every family is
inventoried with its founder layer, whether it is implemented and integrated, its buildability, and an
admission status from the directive's vocabulary:

    DEFAULT_FOR_GEOMETRY  NICHE_CAPABILITY  COMPOSITION_ONLY  EXPERIMENTAL  SUPERSEDED  REJECTED  FRONTIER_HORIZON

This module asserts nothing by itself. ``implemented`` and ``integrated`` are read from live code (the
cortex registry, the #140 operation contract, the genome library, the genesis catalog, the composition
recipes); an admission status other than EXPERIMENTAL or FRONTIER_HORIZON must cite a frozen evidence file.
Operation-family and genome statuses come from one place, the Mind evidence index that the Competency
Compiler routes on (``docs/evidence/greg-mind-evidence-index.json``, whose every row
``tests/unit/test_mind_evidence_sources.py`` re-derives from the frozen file it cites); ``check()`` refuses an
entry the index does not support. Registered is not implemented: a
reserved cortex family is FRONTIER_HORIZON as a cortex organ even when its effect is realised elsewhere,
and the ``realized_by`` field names where.

Founder layers: 1 basal, 2 collective, 3 solver, 4 developmental/morphogenetic, 5 Competency Compiler.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUSES = ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY", "COMPOSITION_ONLY", "EXPERIMENTAL", "SUPERSEDED",
            "REJECTED", "FRONTIER_HORIZON")
BUILDABILITY = ("BUILDABLE_NOW", "EXPERIMENTAL_NOW", "FRONTIER_RESEARCH", "SCIENCE_FICTION_DESCENDANT")
CORTEX_LAYER = {"primitive_basal": 1, "distributed_collective": 2, "solver_macro_cognitive": 3,
                "developmental_morphogenetic": 4, "meta_polyintelligence_cortex": 5}

P6_V3 = "docs/evidence/greg-composition-lift/2026-10-14/results-v3.json"
CROSSGEO_V03 = "tests/evidence/greg-crossgeo-v0.3/results.json"
P4_V2 = "docs/evidence/greg-learned-routing/2026-10-07/results-v2.json"
P6_V1 = "docs/evidence/greg-composition-lift/2026-10-07/results.json"
P6_V2 = "docs/evidence/greg-composition-lift/2026-10-14/results-v2.json"
TARGET_FORM = "docs/TARGET_FORM_001.md"
DEV_SWEEP = "docs/evidence/greg-developmental-sweep/2026-10-14/README.md"
P4_V3_PR158 = "docs/evidence/greg-learned-routing/2026-10-08/results-v3.json"
P4_V3_PR155 = "docs/evidence/greg-learned-routing/2026-10-07/results-v3.json"
P8_CYCLES = ("docs/evidence/greg-protected-evolution/2026-10-08", "docs/evidence/greg-protected-evolution/2026-10-09",
             "docs/evidence/greg-protected-evolution/2026-10-14/cycle-cr-3.json")
P8_ROUTING = "docs/evidence/greg-protected-evolution/2026-10-14/results.json"

# Founder layer of each #140 operation family (the catalog's own numbering is kept in ``detail``).
FAMILY_LAYER = {"micro": 1, "control": 1, "pattern": 1, "robust_pattern": 1, "collective": 2, "human": 2, "crowd": 2,
                "swarm": 2, "evolutionary": 4, "blackbox": 4}
# Admission-run structural statuses mapped into the directive's vocabulary.
# Structural labels are not held-out verdicts: they are reported as EXPERIMENTAL (UNEVALUATED for routing) with
# the raw label kept beside them, never as SUPERSEDED (review of #179, M16).
STRUCTURAL = {"UNEVALUATED": "EXPERIMENTAL", "ALIAS": "EXPERIMENTAL", "SUPERSEDED_BY_CANONICAL_ORGAN": "EXPERIMENTAL",
              "NOT_BENCHMARKED": "EXPERIMENTAL", "NOT_RUN": "EXPERIMENTAL", "ROUTE_ONLY": "EXPERIMENTAL"}
# Findings recorded next to a frozen verdict without changing it (see the cited README).
NOTES = {
    "swarm": "post hoc (not pre-registered): multistart L-BFGS-B beats PSO 32/7; acquisition target",
    "blackbox": "superseded by multistart L-BFGS-B 26/8 (p = 0.0015); acquisition target",
    "crowd": "dense crowds: ties the one-step weighted vote (admission v2); sparse multi-class crowds: loses to it "
             "8/32, p = 9e-5 (pr155-crowd-sparse); the one-step vote is the acquisition target; do not attach as default",
    "robust_pattern": "admission v2: beats the rejected z-score 25/5 (reference), not admitted over IQR fences; "
                      "operation admission v3 (fresh seeds): beats IQR fences 14/5, ties Rosner's ESD 4/7 - near "
                      "the rule boundary in both runs",
    "graph": "operation admission v3: equal-weight paths on 36 of 40 items, 4/0 against fewest-hops BFS "
             "(p = 0.0625); #155's DEFAULT did not replicate",
    "collective": "both runs lose to an oracle baseline that knows hidden accuracies (review M3); against the "
                  "deployable majority it ties; EXPERIMENTAL on every surface",
}
# Reserved cortex families whose effect already runs as an operation family or a lab (not as a cortex organ).
REALIZED_BY = {
    "cortex.probabilistic.bayes": "cognition.probabilistic", "cortex.information.voi": "cognition.information",
    "cortex.sequential.bandit": "cognition.sequential", "cortex.simulation.twin": "cognition.simulation",
    "cortex.graph.search": "cognition.graph", "cortex.search.heuristic": "cognition.search",
    "cortex.exact.symbolic": "cognition.exact", "cortex.game.mechanism": "cognition.game",
    "cortex.control.feedback": "cognition.control", "cortex.pattern.anomaly": "cognition.pattern",
    "cortex.collective.hive_quorum": "cognition.collective", "cortex.developmental.evolutionary": "cognition.evolutionary",
    "cortex.human.panel": "cognition.human", "cortex.developmental.mica_field": "developmental/ (MICA/CDPE lab)",
    "cortex.developmental.morphogenetic": "developmental/ (MICA/CDPE lab)",
    "cortex.meta.metaconsensus": "greg.cognition.learned_routing + conditional_competence (P4)",
    "cortex.collective.ecology_market": "greg.cognition.learned_routing (settled competence; P4)",
    "cortex.developmental.program_synthesis": "greg.genesis (open-source acquisition; not synthesis)",
}
# Buildability of reserved families with today's technology (named judgement, recorded as such).
EXPERIMENTAL_NOW = ("cortex.developmental.program_synthesis", "cortex.developmental.constraint_release",
                    "cortex.developmental.mica_field", "cortex.developmental.morphogenetic",
                    "cortex.meta.global_workspace", "cortex.meta.active_inference", "cortex.meta.metaconsensus",
                    "cortex.meta.mental_models", "cortex.collective.ecology_market", "cortex.collective.immune")
# Executable cortex organs with frozen evidence on their native geometry.
ORGAN_ADMISSION = {
    "cortex.formal.z3": ("DEFAULT_FOR_GEOMETRY", "constraint_feasibility: leads the frozen 0.2.1 router; z3_first "
                         "49 vs cpsat_first 44 of 66 in P4 v2", (CROSSGEO_V03, P4_V2)),
    "cortex.optimization.cpsat": ("NICHE_CAPABILITY", "leads optimisation in the frozen router; on P4 v2 tight bin "
                                  "packing the conditional memory preferred it (9 vs 7)", (CROSSGEO_V03, P4_V2)),
    "cortex.estimation.fermi": ("COMPOSITION_ONLY", "0/48 alone on X1, required stage of estimate_then_optimize "
                                "(F1 p=0.00012, X1 48/48)", (P6_V1, P6_V2)),
    "cortex.evidence_causal": ("COMPOSITION_ONLY", "identification stage of identify_then_optimize (F2b 43/3 vs "
                               "35/13); no native single-organ benchmark yet", (P6_V2,)),
    "cortex.extraction.schedule": ("COMPOSITION_ONLY", "0/57 alone on X2, words -> model stage (X2 57/57)", (P6_V2,)),
}


@dataclass(frozen=True)
class GenomeEntry:
    genome_id: str
    source: str                 # cortex_organ | operation_family | genesis_engine | composition_recipe | mechanism
    layer: int
    implemented: bool
    integrated: bool
    buildability: str
    admission: str
    detail: str = ""
    evidence_refs: tuple[str, ...] = ()
    realized_by: str | None = None
    geometries: tuple[str, ...] = field(default_factory=tuple)


def _cortex() -> list[GenomeEntry]:
    from cortex.genome import ROUTABLE_LIFECYCLE, seed_registry
    out = []
    registry = seed_registry()
    for key in registry.keys():
        profile = registry.get(key).profile
        name = key.split("@")[0]
        live = profile.enabled and profile.lifecycle in ROUTABLE_LIFECYCLE
        if profile.lifecycle == "SUPERSEDED":
            admission, detail, refs = "SUPERSEDED", f"lifecycle SUPERSEDED; {', '.join(profile.lineage)}", ()
        elif not live:
            admission, detail, refs = "FRONTIER_HORIZON", f"reserved ({profile.failure_diversity_key}); lifecycle " \
                                                         f"{profile.lifecycle}, disabled", ()
        elif name in ORGAN_ADMISSION:
            # the compiler's organ status is the admission (round-2 review of #179, N2); the lineage label is a
            # measurement note, never an admission (review H4)
            from .compiler import evidence_index, organ_status
            label, note, refs = ORGAN_ADMISSION[name]
            status, stale = organ_status(f"cognition.{name}", evidence_index())
            admission = STRUCTURAL.get(status, status)
            detail = f"lineage label {label} (not an admission): {note}" + (f"; {stale}" if stale else "")
        elif profile.role == "verifier":
            admission, detail, refs = "COMPOSITION_ONLY", "attacks other organs' outputs; never answers alone", \
                ("tests/unit/test_cortex_pipeline.py",)
        else:
            admission, detail, refs = "EXPERIMENTAL", "executable; no native benchmark admits it yet", ()
        if name in ("cortex.semantic", "cortex.extraction.schedule"):
            detail += "; needs the founder-selected local model (none configured here)"
        out.append(GenomeEntry(key, "cortex_organ", CORTEX_LAYER[profile.layer], live, live,
                               "BUILDABLE_NOW" if live or name not in EXPERIMENTAL_NOW else "EXPERIMENTAL_NOW",
                               admission, detail, tuple(refs), None if live else REALIZED_BY.get(name),
                               tuple(profile.supported_geometries)))
    return out


def admitted(index: dict | None = None) -> dict:
    """Operation family -> (raw status, evidence file), from the evidence index's ``operations`` section: the
    newest frozen admission run that measured a family wins (PR #155 lineage runs)."""
    from .compiler import evidence_index
    index = evidence_index() if index is None else index
    return {family: (row["raw_status"], row["evidence"].partition("#")[0])
            for family, row in (index.get("operations") or {}).items()}


def admission_of(family: str, index: dict) -> tuple[str, str, str | None]:
    """(directive status, raw label, evidence file) for one catalog family, read from the evidence index.

    A genome-library family reads ``genomes`` with the compiler's version rule: positive evidence binds the
    version measured, so a bumped version is EXPERIMENTAL until re-admitted; negative evidence persists. Any
    other family reads ``operations`` with the same rule applied to its solver code digest. No index row means
    no frozen run: EXPERIMENTAL, labelled UNEVALUATED."""
    from .compiler import family_status
    admission = family_status(family, index)            # the compiler's one status function (review H2/M16)
    raw, ref = admission["raw"], (admission["evidence"] or "").partition("#")[0] or None
    if raw is None:
        return "EXPERIMENTAL", "UNEVALUATED", None
    if admission["stale"]:
        return "EXPERIMENTAL", f"{raw} (stale: {admission['stale']})", ref
    # the routed status, never the raw label: an erratum (collective) reads the same on every surface (round-2
    # review of #179, N2); the raw label stays beside it
    return STRUCTURAL.get(admission["status"], admission["status"]), raw, ref


def _families() -> list[GenomeEntry]:
    from . import catalog, solvers
    from .compiler import evidence_index
    from .genomes import library
    index, genomes = evidence_index(), library.executables()
    out = []
    for family, (catalog_layer, operations, classes, _, _) in catalog.FAMILIES.items():
        status, raw, ref = admission_of(family, index)
        implemented = family in solvers.SOLVERS
        layer = genomes[family].genome.layer if family in genomes else FAMILY_LAYER.get(family, 3)
        source = "genome" if family in genomes else "operation"
        out.append(GenomeEntry(f"cognition.{family}", "operation_family", layer, implemented,
                               implemented, "BUILDABLE_NOW", status,
                               f"{source}; admission: {raw}; catalog layer {catalog_layer}; ops {', '.join(operations)}"
                               + (f"; {NOTES[family]}" if family in NOTES else ""),
                               (ref,) if ref else (), None, tuple(classes)))
    return out


def _acquired() -> list[GenomeEntry]:
    from greg import genesis
    from . import composition
    out = [GenomeEntry(f"genesis.{engine}", "genesis_engine", 3, True, True, "BUILDABLE_NOW", "EXPERIMENTAL",
                       "open-source mechanism formed by Capability Genesis; GREG certificate check; attach is "
                       "the founder's", ("tests/evidence/greg-open-source-genesis-2026-10-01",))
           for engine in genesis.CATALOG]
    from .compiler import evidence_index, recipe_stale
    recipes = evidence_index().get("recipes") or {}
    # PR #155 lineage lift on further families for the same recipe: corroboration, not the routing verdict
    corroboration = {"estimate_then_optimize": ("PR #155: X1 48/48", (P6_V1, P6_V2)),
                     "identify_then_optimize": ("PR #155: F2b 11/3, p=0.029, a same-instance re-run of F2R "
                                                "(reproducibility, not replication)", (P6_V2,))}
    for recipe in composition.RECIPES:
        verdict = recipes.get(recipe)
        extra, extra_refs = corroboration.get(recipe, ("", ()))
        if verdict is None:
            status, detail, refs = "EXPERIMENTAL", "no held-out lift measured", ()
        else:
            stale = recipe_stale(recipe, verdict) if verdict["lift"] else None
            status = "DEFAULT_FOR_GEOMETRY" if verdict["lift"] and not stale else "EXPERIMENTAL"
            detail = (f"index {verdict['status']} on {verdict['family']} ({verdict['wins']}/{verdict['losses']}, "
                      f"p={verdict['p_one_sided']})" + ("" if verdict["lift"] else
                                                        f"; prefer {verdict['prefer']}")
                      + (f"; stale: {stale}" if stale else "")
                      # the frozen run's practitioner arms (review of #179, H4 and L11): the lift is over GREG's
                      # best constituent, not over these
                      + (f"; tied on every item by {', '.join(verdict['tied_by'])}" if verdict.get("tied_by") else "")
                      + (f"; loses on item count to {', '.join(verdict['loses_to'])}"
                         if verdict.get("loses_to") else ""))
            refs = (verdict["evidence"].partition("#")[0],)
        out.append(GenomeEntry(f"composition.{recipe}", "composition_recipe", 5, True, True, "BUILDABLE_NOW",
                               status, detail + (f"; {extra}" if extra else ""), refs + extra_refs))
    out += [
        GenomeEntry("mechanism.conditional_competence", "mechanism", 5, True, True, "BUILDABLE_NOW", "EXPERIMENTAL",
                    "P4 conditional memory, observed in shadow and never applied by default. #158's pre-registered "
                    "decisive retest found REGRESSION 160 vs 162 of 191; #155's NO_GAIN 111 = 111 re-measured 130 "
                    "of the same payloads (a same-instance re-run: reproducibility, not replication). Conditional "
                    "solver learning is not currently worth its complexity",
                    (P4_V2, P4_V3_PR158, P4_V3_PR155)),
        GenomeEntry("mechanism.protected_evolution", "mechanism", 5, True, False, "BUILDABLE_NOW", "EXPERIMENTAL",
                    "P8 canonical controller (greg.cognition.evolution): Landlock-confined candidates, sealed "
                    "evaluator, recurring-failure trigger; three cycles, all REJECT; never kept an improvement and "
                    "never attaches", P8_CYCLES),
        GenomeEntry("mechanism.protected_evolution_routing", "mechanism", 5, True, False, "BUILDABLE_NOW",
                    "EXPERIMENTAL", "PR #155 lineage alternative (greg.cognition.evolution_routing), not a "
                    "controller: routing-genome search against a hash-pinned evaluator; REJECT (no headroom); "
                    "imported only by its historical runner", (P8_ROUTING,)),
        GenomeEntry("composition.derived", "composition_recipe", 5, True, True, "BUILDABLE_NOW", *_p6v3_status(),
                    (P6_V3,) if (ROOT / P6_V3).exists() else ()),
        GenomeEntry("mechanism.advantage_compiler", "mechanism", 5, True, False, "BUILDABLE_NOW", "EXPERIMENTAL",
                    "mental models as typed operators at evidenced bottlenecks; lawful-means gate; generates "
                    "UNESTIMATED candidates for the existing leverage ranker; no outcome evidence yet"),
        GenomeEntry("mechanism.mica_cdpe", "mechanism", 4, True, False, "EXPERIMENTAL_NOW", "EXPERIMENTAL",
                    "MICA/CDPE damage-recovery lab: MECHANICS_VALIDATED_NOT_PRODUCTION_AUTHORIZED on its fixed "
                    "perturbation; unseen-damage sweep PARITY with adaptive central replanning on 40/40 seeds "
                    "(distributed shortest-path routing; no advantage)", (TARGET_FORM, DEV_SWEEP)),
    ]
    return out


def _p6v3_status() -> tuple[str, str]:
    """DEFAULT only if the derived chain also beats the best fixed recipe; beating singles alone is a niche."""
    base = "chains absent from RECIPES derived by typed dataflow (estimate + identify -> optimize); "
    if not (ROOT / P6_V3).exists():
        return "EXPERIMENTAL", base + "P6 v3 not yet run"
    summary = json.loads((ROOT / P6_V3).read_text())["summary"]
    single, fixed = summary["vs_best_single"], summary["vs_best_fixed_recipe"]
    detail = (base + f"P6 v3: vs best single {single['wins']}/{single['losses']} (lift {single['lift']}), "
              f"vs best fixed recipe {fixed['wins']}/{fixed['losses']} (lift {fixed['lift']})")
    measured = "DEFAULT_FOR_GEOMETRY" if fixed["lift"] else "NICHE_CAPABILITY" if single["lift"] else "EXPERIMENTAL"
    # the compiler routes derived chains as UNEVALUATED until they are re-measured on this tree (round-2 review of
    # #179, N2): the frozen reading is a measurement note, not this surface's admission
    return "EXPERIMENTAL", detail + f"; measured {measured} at P6 v3's freeze, routes UNEVALUATED on this tree"


def inventory() -> list[GenomeEntry]:
    return _cortex() + _families() + _acquired()


def check(entries: list[GenomeEntry] | None = None) -> list[str]:
    """Problems that would make the library claim more than code and frozen evidence support."""
    from .compiler import evidence_index
    problems = []
    index = evidence_index()
    for e in entries if entries is not None else inventory():
        if e.admission not in STATUSES or e.buildability not in BUILDABILITY or e.layer not in range(1, 6):
            problems.append(f"{e.genome_id}: outside the closed vocabulary")
        if e.admission == "FRONTIER_HORIZON" and (e.implemented or e.integrated):
            problems.append(f"{e.genome_id}: a frontier horizon cannot be implemented")
        if e.integrated and not e.implemented:
            problems.append(f"{e.genome_id}: integrated but not implemented")
        if e.admission in ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY", "COMPOSITION_ONLY", "REJECTED") \
                and not e.evidence_refs:
            problems.append(f"{e.genome_id}: {e.admission} without evidence")
        for ref in e.evidence_refs:
            if not (ROOT / ref).exists():
                problems.append(f"{e.genome_id}: missing evidence {ref}")
        if e.source == "operation_family":
            status, raw, _ = admission_of(e.genome_id.removeprefix("cognition."), index)
            if status != e.admission:
                problems.append(f"{e.genome_id}: {e.admission} disagrees with frozen admission {raw}")
    return problems


def matrix(entries: list[GenomeEntry] | None = None) -> dict:
    """Per founder layer: intended, implemented, integrated, admitted (default/niche), rejected, horizon."""
    rows = {}
    for e in entries if entries is not None else inventory():
        row = rows.setdefault(e.layer, {"intended": 0, "implemented": 0, "integrated": 0, "admitted": 0,
                                        "composition_only": 0, "rejected": 0, "experimental": 0, "horizon": 0})
        row["intended"] += 1
        row["implemented"] += e.implemented
        row["integrated"] += e.integrated
        row["admitted"] += e.admission in ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY")
        row["composition_only"] += e.admission == "COMPOSITION_ONLY"
        row["rejected"] += e.admission == "REJECTED"
        row["experimental"] += e.admission == "EXPERIMENTAL"
        row["horizon"] += e.admission == "FRONTIER_HORIZON"
    return dict(sorted(rows.items()))


# where an admitted label comes from (review of #179, H4): only the first is an admission under #158's
# pre-registered rule at the current version; the others are reported, never summed into one "admitted" number
PROVENANCE = {
    "rule_admitted": "#158 genome admission, or the converged tree's operation-admission harness (v3), under a "
                     "pre-registered rule (git freeze before the run), held-out seeds, against a named competitor, "
                     "bound to the measured version or solver closure",
    "lineage_operation_verdict": "#155 operation-family admission runs: held-out, but not pre-registered in git "
                                 "(freeze, runner and results land in one commit); a DEFAULT with no competitor "
                                 "routes as UNEVALUATED",
    "recipe_lift": "a composition's lift over its own constituents on one frozen family: not an admission",
    "organ_label": "a hand-coded cortex-organ label from router evidence: not an admission",
}
LINEAGE_ADMISSION_DIR = "docs/evidence/greg-genome-admission/2026-10-14/"


def provenance(e: GenomeEntry) -> str | None:
    if e.admission not in ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY"):
        return None
    if e.source == "composition_recipe":
        return "recipe_lift"
    if e.source == "cortex_organ":
        return "organ_label"
    if any(r.startswith(LINEAGE_ADMISSION_DIR) for r in e.evidence_refs):
        return "lineage_operation_verdict"
    return "rule_admitted"


def admitted_by_provenance(entries: list[GenomeEntry] | None = None) -> dict:
    counts = {k: 0 for k in PROVENANCE}
    for e in entries if entries is not None else inventory():
        if (kind := provenance(e)) is not None:
            counts[kind] += 1
    return {"counts": counts, "meaning": PROVENANCE}


def export() -> dict:
    entries = inventory()
    return {"schema": "greg-genome-library/0.1", "entries": [asdict(e) for e in entries],
            "matrix": matrix(entries), "admitted_by_provenance": admitted_by_provenance(entries),
            "problems": check(entries)}


if __name__ == "__main__":
    print(json.dumps(export(), indent=1))
