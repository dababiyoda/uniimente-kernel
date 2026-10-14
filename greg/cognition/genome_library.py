"""The IntelligenceGenome library: one inventory of every intelligence GREG can (or intends to) recruit.

Founder directive 2026-10-07, step 6 ("begin executable IntelligenceGenome expansion"): every family is
inventoried with its founder layer, whether it is implemented and integrated, its buildability, and an
admission status from the directive's vocabulary:

    DEFAULT_FOR_GEOMETRY  NICHE_CAPABILITY  COMPOSITION_ONLY  EXPERIMENTAL  SUPERSEDED  REJECTED  FRONTIER_HORIZON

This module asserts nothing by itself. ``implemented`` and ``integrated`` are read from live code (the
cortex registry, the #140 operation contract, the genesis catalog, the composition recipes); an admission
status other than EXPERIMENTAL or FRONTIER_HORIZON must cite a frozen evidence file, and ``check()``
re-reads that file and refuses an entry the file does not support. Registered is not implemented: a
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

ADMISSION = "docs/evidence/greg-genome-admission/2026-10-14/results.json"
ADMISSION_V2 = "docs/evidence/greg-genome-admission/2026-10-14/results-v2.json"
P6_V3 = "docs/evidence/greg-composition-lift/2026-10-14/results-v3.json"
CROSSGEO_V03 = "tests/evidence/greg-crossgeo-v0.3/results.json"
P4_V2 = "docs/evidence/greg-learned-routing/2026-10-07/results-v2.json"
P6_V1 = "docs/evidence/greg-composition-lift/2026-10-07/results.json"
P6_V2 = "docs/evidence/greg-composition-lift/2026-10-14/results-v2.json"
TARGET_FORM = "docs/TARGET_FORM_001.md"

# Founder layer of each #140 operation family (the catalog's own numbering is kept in ``detail``).
FAMILY_LAYER = {"micro": 1, "control": 1, "pattern": 1, "robust_pattern": 1, "collective": 2, "human": 2, "crowd": 2,
                "swarm": 2, "evolutionary": 4, "blackbox": 4}
# Admission-run structural statuses mapped into the directive's vocabulary.
STRUCTURAL = {"ALIAS": "SUPERSEDED", "SUPERSEDED_BY_CANONICAL_ORGAN": "SUPERSEDED",
              "NOT_BENCHMARKED": "EXPERIMENTAL", "NOT_RUN": "EXPERIMENTAL", "ROUTE_ONLY": "EXPERIMENTAL"}
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
            admission, detail, refs = ORGAN_ADMISSION[name]
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


def admitted() -> dict:
    """Family -> (raw status, evidence file); the newest frozen admission run that measured a family wins."""
    out = {}
    for ref in (ADMISSION, ADMISSION_V2):
        if (ROOT / ref).exists():
            for family, row in json.loads((ROOT / ref).read_text())["families"].items():
                out[family] = (row.get("status", "NOT_BENCHMARKED"), ref)
    return out


def _families() -> list[GenomeEntry]:
    from . import catalog, solvers
    runs = admitted()
    out = []
    for family, (catalog_layer, operations, classes, _, _) in catalog.FAMILIES.items():
        raw, ref = runs.get(family, ("NOT_BENCHMARKED", None))
        status = STRUCTURAL.get(raw, raw)
        implemented = family in solvers.SOLVERS
        out.append(GenomeEntry(f"cognition.{family}", "operation_family", FAMILY_LAYER.get(family, 3), implemented,
                               implemented, "BUILDABLE_NOW", status,
                               f"admission run: {raw}; catalog layer {catalog_layer}; ops {', '.join(operations)}",
                               (ref,) if ref else (), None, tuple(classes)))
    return out


def _acquired() -> list[GenomeEntry]:
    from greg import genesis
    from . import composition
    out = [GenomeEntry(f"genesis.{engine}", "genesis_engine", 3, True, True, "BUILDABLE_NOW", "EXPERIMENTAL",
                       "open-source mechanism formed by Capability Genesis; GREG certificate check; attach is "
                       "the founder's", ("tests/evidence/greg-open-source-genesis-2026-10-01",))
           for engine in genesis.CATALOG]
    lift = {"estimate_then_optimize": ("F1 lift p=0.00012; X1 48/48", (P6_V1, P6_V2)),
            "identify_then_optimize": ("F2b lift 11/3, p=0.029", (P6_V2,))}
    for recipe in composition.RECIPES:
        detail, refs = lift.get(recipe, ("no held-out lift measured", ()))
        out.append(GenomeEntry(f"composition.{recipe}", "composition_recipe", 5, True, True, "BUILDABLE_NOW",
                               "DEFAULT_FOR_GEOMETRY" if refs else "EXPERIMENTAL", detail, refs))
    out += [
        GenomeEntry("mechanism.conditional_competence", "mechanism", 5, True, True, "BUILDABLE_NOW", "EXPERIMENTAL",
                    "P4 conditional memory; shadow by default; v1 and v2 INCONCLUSIVE (v3 decides)", (P4_V2,)),
        GenomeEntry("mechanism.protected_evolution", "mechanism", 5, True, False, "BUILDABLE_NOW", "EXPERIMENTAL",
                    "P8 routing-genome search against a hash-pinned evaluator; not attached to runtime routing"),
        GenomeEntry("composition.derived", "composition_recipe", 5, True, True, "BUILDABLE_NOW",
                    "DEFAULT_FOR_GEOMETRY" if _p6v3_lift() else "EXPERIMENTAL",
                    "chains absent from RECIPES derived by typed dataflow (estimate + identify -> optimize); "
                    + ("P6 v3 lift" if _p6v3_lift() else "P6 v3 not yet run or no lift"),
                    (P6_V3,) if (ROOT / P6_V3).exists() else ()),
        GenomeEntry("mechanism.advantage_compiler", "mechanism", 5, True, False, "BUILDABLE_NOW", "EXPERIMENTAL",
                    "mental models as typed operators at evidenced bottlenecks; lawful-means gate; generates "
                    "UNESTIMATED candidates for the existing leverage ranker; no outcome evidence yet"),
        GenomeEntry("mechanism.mica_cdpe", "mechanism", 4, True, False, "EXPERIMENTAL_NOW", "EXPERIMENTAL",
                    "MICA/CDPE damage-recovery lab: MECHANICS_VALIDATED_NOT_PRODUCTION_AUTHORIZED (parity "
                    ">= 90% of adaptive central replanning, no advantage shown)", (TARGET_FORM,)),
    ]
    return out


def _p6v3_lift() -> bool:
    if not (ROOT / P6_V3).exists():
        return False
    return bool(json.loads((ROOT / P6_V3).read_text())["summary"]["vs_best_single"]["lift"])


def inventory() -> list[GenomeEntry]:
    return _cortex() + _families() + _acquired()


def check(entries: list[GenomeEntry] | None = None) -> list[str]:
    """Problems that would make the library claim more than code and frozen evidence support."""
    problems = []
    runs = admitted()
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
            raw = runs.get(e.genome_id.removeprefix("cognition."), ("NOT_BENCHMARKED", None))[0]
            if STRUCTURAL.get(raw, raw) != e.admission:
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


def export() -> dict:
    entries = inventory()
    return {"schema": "greg-genome-library/0.1", "entries": [asdict(e) for e in entries],
            "matrix": matrix(entries), "problems": check(entries)}


if __name__ == "__main__":
    print(json.dumps(export(), indent=1))
