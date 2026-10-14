"""Reality ledger for GREG's Mind: what is built, simulated, held-out supported, externally verified, unresolved
or frontier (founder directive 2026-10-07, section 31 item 17).

Read-only. It reads the frozen evidence index (docs/evidence/greg-mind-evidence-index.json), the frontier
backcasts on greg/path.json and the live catalog (genome library, catalog families, cortex organs, P6 recipes,
reserved cortex families), and prints one JSON document to stdout. It writes no file, changes no routing and
creates no authority. Run:

    PYTHONPATH=. python scripts/mind_status.py

Every mechanism gets exactly one label: the first rule below that holds.

  EXTERNALLY_VERIFIED  its index row carries an ``external_verification`` entry (a ref, and for a genome the
                       version verified, which must be the current one). The index builder writes no such entry
                       today, so nothing is EXTERNALLY_VERIFIED.
  FRONTIER             a frontier backcast on greg/path.json, or a FRONTIER_HORIZON admission status.
  SIMULATED            positive frozen held-out admission (DEFAULT_FOR_GEOMETRY or NICHE_CAPABILITY), fresh at the
                       current version, for a genome whose native geometry is physical or whose evidence type is a
                       simulated world (simulation, control or developmental trace). GREG has no physical
                       sensors or actuators, so that competence was measured on simulated plants, signals, lattices or reward
                       processes only.
  HELDOUT_SUPPORTED    positive frozen held-out evidence, fresh at the current version: a genome's admission
                       status, a composition recipe's VPL lift, or a P4 GAIN.
  UNRESOLVED           frozen evidence that is inconclusive (admission EXPERIMENTAL; a recipe without lift that is
                       not significantly worse than its best constituent; a P4 verdict that is neither GAIN nor
                       REGRESSION), or an intended mechanism nothing executes (a catalog family without an
                       executor, a reserved cortex family with no executor anywhere).
  BUILT                executable on GREG's cognition path with no positive evidence at its current version:
                       unevaluated, a stage measured only inside compositions (COMPOSITION_ONLY), refuted for its
                       geometry (SUPERSEDED, REJECTED, a recipe significantly worse than its best constituent, the
                       demoted P4 route), or positive evidence made stale by a version bump.

Staleness mirrors greg/cognition/compiler.py: positive evidence binds the version it was measured at and is
stale after a version bump (the compiler then routes the genome as UNEVALUATED); negative and inconclusive
evidence (its NOT_POSITIVE statuses) persists until a re-admission replaces it. A genome's label therefore
agrees with what the compiler routes on (tests/unit/test_mind_status.py checks this against the compiler).

Not verified here: that a frozen result reproduces or that the index matches its sources
(tests/unit/test_mind_evidence_sources.py recomputes both), that a simulated world matches any real system,
that a mechanism was ever used on a real mission, or the quality of evidence outside the index (the cortex
seed runs are listed under ``evidence_outside_index`` and never raise a label). A recipe or P4 verdict carries no
code version in the index, so a later code change does not make it stale here or in the compiler.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INDEX = ROOT / "docs" / "evidence" / "greg-mind-evidence-index.json"
PATH = ROOT / "greg" / "path.json"
SCHEMA = "greg-mind-status/0.1"
LABELS = ("BUILT", "SIMULATED", "HELDOUT_SUPPORTED", "EXTERNALLY_VERIFIED", "UNRESOLVED", "FRONTIER")
POSITIVE = ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY")
REFUTED = ("SUPERSEDED", "REJECTED")
SIMULATED_GEOMETRY = ("physical",)
SIMULATED_EVIDENCE = ("simulation", "control_trace", "developmental_trace")
ALPHA = 0.05
RULES = {
    "EXTERNALLY_VERIFIED": "an external_verification entry in the evidence index for the current version",
    "FRONTIER": "a frontier backcast on greg/path.json or a FRONTIER_HORIZON admission status",
    "SIMULATED": "positive held-out admission, fresh at the current version, on a physical geometry or a "
                 "simulated-world evidence type: measured on simulated worlds only",
    "HELDOUT_SUPPORTED": "positive frozen held-out evidence, fresh at the current version",
    "UNRESOLVED": "inconclusive frozen evidence, or an intended mechanism that nothing executes",
    "BUILT": "executable with no positive evidence at its current version (unevaluated, composition stage, "
             "refuted, demoted, or stale after a version bump)",
}


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _p_at_least(k: int, n: int) -> float:
    """One-sided exact sign test: P(X >= k) for X ~ Binomial(n, 1/2)."""
    return 1.0 if n == 0 else math.fsum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n


def _external(record: dict, version: str | None) -> list[dict]:
    """External-verification entries that bind this version (a recipe or route has no version to bind)."""
    out = []
    for entry in (record or {}).get("external_verification") or []:
        if isinstance(entry, dict) and entry.get("ref") and (version is None or entry.get("version") == version):
            out.append(entry)
    return out


def _genomes(index: dict) -> list[dict]:
    from greg.cognition.genomes import library
    rows = []
    for family, item in sorted(library.executables().items()):
        g = item.genome
        record = index.get("genomes", {}).get(family)
        status = (record or {}).get("status")
        measured = (record or {}).get("version")
        stale = bool(status in POSITIVE and measured and measured != g.version)
        heldout = None if record is None else {
            "status": status, "version_measured": measured,
            "current": None if measured is None else measured == g.version,
            "evidence": record.get("evidence"),
            "history": [{k: h.get(k) for k in ("run", "status", "version")} for h in record.get("history", [])],
            # a status that differs between frozen runs at the same version sits near a rule boundary (or the
            # rule changed between runs); the latest run decides, as it does for the compiler
            "status_changed_at_same_version": any(
                h.get("version") == measured and h.get("status") != status for h in record.get("history", [])),
            **({"stale": f"{status} was measured at version {measured}; version {g.version} needs re-admission"}
               if stale else {})}
        simulated = g.epistemic_class in SIMULATED_GEOMETRY or g.evidence_type in SIMULATED_EVIDENCE
        external = _external(record, g.version)
        if external:
            label, basis = "EXTERNALLY_VERIFIED", "external verification recorded for the current version"
        elif status == "FRONTIER_HORIZON":
            label, basis = "FRONTIER", "admission placed it on the frontier horizon"
        elif status in POSITIVE and not stale:
            if simulated:
                label = "SIMULATED"
                basis = (f"{status} on held-out seeds at version {measured}, measured on a simulated world "
                         f"({g.epistemic_class} geometry, {g.evidence_type} evidence)")
            else:
                label, basis = "HELDOUT_SUPPORTED", f"{status} on held-out seeds at version {measured}"
        elif status == "EXPERIMENTAL":
            label, basis = "UNRESOLVED", "no demonstrated edge over the simple baseline on held-out seeds"
        elif stale:
            label, basis = "BUILT", heldout["stale"]
        elif status in REFUTED:
            label, basis = "BUILT", f"{status} on held-out seeds: refuted as the method for its geometry"
        elif status == "COMPOSITION_ONLY":
            label, basis = "BUILT", "a composition stage: its contribution is measured through recipes"
        else:
            label, basis = "BUILT", "no frozen held-out admission (UNEVALUATED)"
        if heldout and heldout["current"] is False and not stale and status not in POSITIVE:
            basis += (f"; measured at version {measured}, current {g.version}: negative or inconclusive evidence "
                      f"persists until a re-admission replaces it")
        rows.append({"id": f"cognition.{family}", "kind": "genome", "label": label, "basis": basis,
                     "layer": g.layer, "intelligence_id": g.intelligence_id, "version_current": g.version,
                     "epistemic_class": g.epistemic_class, "evidence_type": g.evidence_type,
                     "simulated_world": simulated, "heldout": heldout,
                     **({"external_verification": external} if external else {})})
    for family in sorted(set(index.get("genomes", {})) - set(library.executables())):
        rows.append({"id": f"cognition.{family}", "kind": "genome", "label": "UNRESOLVED",
                     "basis": "a frozen admission verdict for a genome no longer in the library",
                     "heldout": index["genomes"][family]})
    return rows


def _catalog_families() -> list[dict]:
    from greg.cognition import cortex as greg_cortex
    from greg.cognition.catalog import FAMILIES, SEED_FAMILIES
    from greg.cognition.genomes import library
    from greg.cognition.solvers import SOLVERS
    genomes = library.executables()
    rows = []
    for family, (layer, operations, classes, proof, dependency) in sorted(FAMILIES.items()):
        if family in genomes:
            continue
        executor = ("greg.cognition.solvers:SOLVERS" if family in SOLVERS else
                    "greg.cognition.cortex:_semantic" if family == "semantic" and hasattr(greg_cortex, "_semantic")
                    else None)
        label, basis = (("BUILT", "executable on the cognition path; no family-level frozen held-out verdict in "
                                  "the evidence index") if executor else
                        ("UNRESOLVED", "registered in the catalog without an executor"))
        rows.append({"id": f"cognition.{family}", "kind": "catalog_family", "label": label, "basis": basis,
                     "layer": layer, "operations": list(operations), "epistemic_classes": list(classes),
                     "proof_class": proof, "dependency": dependency, "seed_family": family in SEED_FAMILIES,
                     "executor": executor})
    return rows


def _cortex_organs() -> list[dict]:
    from cortex.genome import SEED_ORGANS
    from greg.cognition.catalog import CORTEX_ENTRIES
    rows = []
    for cid, (version, classes, deterministic, network, description) in sorted(CORTEX_ENTRIES.items()):
        organ = SEED_ORGANS.get(cid.removeprefix("cognition."), {})
        outside = sorted(set(organ.get("benchmarks") or ()))
        rows.append({"id": cid, "kind": "cortex_organ", "label": "BUILT",
                     "basis": "executable cortex organ on the cognition path; no per-organ verdict in the evidence "
                              "index", "version_current": version, "epistemic_classes": list(classes),
                     "deterministic": deterministic, "network": network,
                     "evidence_outside_index": outside})
    return rows


def _recipes(index: dict) -> list[dict]:
    from greg.cognition.composition import RECIPES
    rows = []
    for name in sorted(set(RECIPES) | set(index.get("recipes", {}))):
        record = index.get("recipes", {}).get(name)
        external = _external(record, None)
        executable = name in RECIPES
        if not executable:
            label, basis = "UNRESOLVED", "a frozen verdict for a recipe no longer in greg.cognition.composition"
        elif external:
            label, basis = "EXTERNALLY_VERIFIED", "external verification recorded"
        elif record is None:
            label, basis = "BUILT", "no frozen P6 verdict"
        elif record.get("status") == "VPL_LIFT":
            label = "HELDOUT_SUPPORTED"
            basis = (f"VPL lift on held-out family {record.get('family')}: {record.get('wins')} wins, "
                     f"{record.get('losses')} losses against the best constituent")
        else:
            wins, losses = int(record.get("wins") or 0), int(record.get("losses") or 0)
            worse = _p_at_least(losses, wins + losses)
            if worse < ALPHA:
                label = "BUILT"
                basis = (f"no lift on {record.get('family')}: significantly worse than its best constituent "
                         f"(one-sided p {worse:.4g}); the compiler prefers {record.get('prefer')}")
            else:
                label = "UNRESOLVED"
                basis = (f"no lift on {record.get('family')}: {wins} wins, {losses} losses, neither direction "
                         f"significant; the compiler prefers {record.get('prefer')}")
        rows.append({"id": f"recipe.{name}", "kind": "recipe", "label": label, "basis": basis,
                     "executable": executable, "verdict": record})
    return rows


def _routing(index: dict) -> list[dict]:
    record = index.get("routing", {}).get("conditional_competence")
    verdict = (record or {}).get("verdict")
    if _external(record, None):
        label, basis = "EXTERNALLY_VERIFIED", "external verification recorded"
    elif verdict == "GAIN":
        label, basis = "HELDOUT_SUPPORTED", "P4 conditional routing gained on its frozen held-out retest"
    elif verdict == "REGRESSION":
        label, basis = "BUILT", "P4 conditional routing was demoted after its frozen retest; it runs in shadow only"
    elif record is None:
        label, basis = "BUILT", "no frozen P4 verdict"
    else:
        label, basis = "UNRESOLVED", f"P4 verdict {verdict}"
    return [{"id": "routing.conditional_competence", "kind": "routing", "label": label, "basis": basis,
             "executor": "greg/cognition/conditional_competence.py", "verdict": record}]


def _reserved() -> tuple[list[dict], dict]:
    from cortex.genome import RESERVED_FAMILIES
    from greg.cognition.reserved import reconciled
    rows, executed = [], {}
    for name, row in sorted(reconciled().items()):
        layer, _, _, diversity, _ = RESERVED_FAMILIES[name]
        if row["executors"]:
            executed[name] = row["executors"]
        else:
            why = row["no_executor_reason"] or "no reconciliation recorded in greg/cognition/reserved.py"
            rows.append({"id": name, "kind": "reserved_cortex_family", "label": "UNRESOLVED",
                         "basis": f"registered and disabled in the cortex with no executor anywhere: {why}",
                         "layer": layer, "diversity": diversity})
    return rows, executed


def _frontier(path_data: dict) -> list[dict]:
    rows = []
    for item in path_data.get("frontier_backcasts") or []:
        rows.append({"id": f"frontier.{item['id']}", "kind": "frontier", "label": "FRONTIER",
                     "basis": "a frontier backcast on greg/path.json: preserved as a destination, not built",
                     "buildability_status": item.get("buildability_status"), "node": item.get("node"),
                     "horizon": item.get("horizon"), "active_gate": item.get("active_gate"),
                     "current_precursor": item.get("current_precursor"),
                     "precursor_mechanisms": item.get("precursor_mechanisms", [])})
    return rows


def status(index_path: Path | None = None, path_file: Path | None = None) -> dict:
    """The reality ledger as a dict (pure: reads files and the catalog, writes nothing)."""
    index_path, path_file = Path(index_path or INDEX), Path(path_file or PATH)
    missing = []
    if index_path.exists():
        index = json.loads(index_path.read_text())
        missing += [f"evidence index lists a missing source: {m}" for m in index.get("missing_sources", [])]
    else:
        index = {"genomes": {}, "recipes": {}, "routing": {}}
        missing.append(f"{_display(index_path)} (no evidence index: nothing can be held-out supported)")
    path_data = json.loads(path_file.read_text())
    reserved, executed = _reserved()
    rows = (_genomes(index) + _catalog_families() + _cortex_organs() + _recipes(index) + _routing(index)
            + reserved + _frontier(path_data))
    ids = [r["id"] for r in rows]
    if len(ids) != len(set(ids)) or any(r["label"] not in LABELS for r in rows):
        raise ValueError("every mechanism needs one unique id and exactly one known label")
    kinds = sorted({r["kind"] for r in rows})
    return {
        "schema": SCHEMA, "labels": list(LABELS), "rules": RULES,
        "generated_from": {
            "evidence_index": {"path": _display(index_path), "present": index_path.exists(),
                               "sha256": _sha(index_path) if index_path.exists() else None},
            "path": {"path": _display(path_file), "sha256": _sha(path_file)}},
        "counts": {label: sum(r["label"] == label for r in rows) for label in LABELS},
        "by_kind": {k: {label: n for label in LABELS
                        if (n := sum(r["label"] == label for r in rows if r["kind"] == k))} for k in kinds},
        "reserved_executed_elsewhere": executed,
        "missing_sources": missing,
        "mechanisms": rows,
    }


def _display(path: Path) -> str:
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def main() -> None:
    json.dump(status(), sys.stdout, indent=1, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
