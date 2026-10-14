"""Reality ledger for GREG's Mind: what is built, simulated, held-out supported, externally verified, unresolved
or frontier (founder directive 2026-10-07, section 31 item 17).

Read-only. It reads the frozen evidence index (docs/evidence/greg-mind-evidence-index.json), the frontier
backcasts on greg/path.json, the frozen P8 cycle records and the live catalog (genome library, catalog families,
cortex organs, P6 recipes, reserved cortex families and the executors greg/cognition/reserved.py names), and prints
one JSON document to stdout. It writes no file, changes no routing and creates no authority. Run:

    PYTHONPATH=. python scripts/mind_status.py

Every mechanism gets exactly one label: the first rule below that holds.

  EXTERNALLY_VERIFIED  fresh positive frozen held-out evidence (as for SIMULATED or HELDOUT_SUPPORTED below) and an
                       ``external_verification`` entry that resolves: it cites, as ``path#pointer``, a listed and
                       digested source of the evidence index whose value records ``kind`` external_outcome,
                       ``verdict`` VERIFIED, this mechanism's ledger id, and the version it verified (a genome or
                       organ: the current version) or the code digest it verified (a recipe:
                       greg/cognition/composition.py; the P4 route: greg/cognition/conditional_competence.py; the
                       current file). An entry that does not resolve counts for nothing and is reported. A resolved
                       entry on a mechanism without fresh positive held-out evidence is reported as a conflict and
                       never overrides the frozen record: the compiler routes on that record and does not read
                       external entries. The index builder writes no such entry today.
  FRONTIER             a frontier backcast on greg/path.json, or a FRONTIER_HORIZON admission status.
  SIMULATED            fresh positive frozen held-out evidence (admission DEFAULT_FOR_GEOMETRY or NICHE_CAPABILITY,
                       a recipe's VPL lift) measured on a simulated world, or on a benchmark whose world is not
                       declared: greg/cognition/worlds.py declares, per genome, P6 family and organ, whether the
                       held-out truth came from recorded data, from the instance itself, or from a seeded generator's
                       hidden state (plants, signals, reward, outage or bidder-value processes, structural causal
                       models, constructed composition families). GREG has no physical sensors or actuators, and a
                       simulated world shows nothing about the real process it imitates.
  HELDOUT_SUPPORTED    fresh positive frozen held-out evidence on natural data or on mathematical instances (the
                       instance is the whole problem and its truth is computed independently), or a P4 GAIN.
  UNRESOLVED           frozen evidence that is inconclusive (admission EXPERIMENTAL; a recipe without lift that is
                       not significantly worse than its best constituent; a P4 verdict that is neither GAIN nor
                       REGRESSION), or an intended mechanism nothing executes (a catalog family without an
                       executor, a reserved cortex family with no executor anywhere, a named executor that does not
                       resolve).
  BUILT                executable on GREG's cognition path with no positive evidence at its current version:
                       unevaluated, a stage measured only inside compositions (COMPOSITION_ONLY), refuted for its
                       geometry (SUPERSEDED, REJECTED, a recipe significantly worse than its best constituent, the
                       demoted P4 route), or positive evidence made stale by a version bump.

Genomes and cortex organs follow the same admission rules, from the index's ``genomes`` and ``organs`` sections.
Staleness mirrors greg/cognition/compiler.py: positive evidence binds the version it was measured at and is
stale after a version bump (the compiler then routes the mechanism as UNEVALUATED); negative and inconclusive
evidence (its NOT_POSITIVE statuses) persists until a re-admission replaces it. A genome's or organ's label is
therefore supported (SIMULATED, HELDOUT_SUPPORTED or EXTERNALLY_VERIFIED) exactly when the compiler routes it on
fresh positive evidence (tests/unit/test_mind_status.py checks this against the compiler).

Every executor greg/cognition/reserved.py names has a row: catalog families, genomes and cortex organs have their
own; a ``module:symbol`` executor gets an ``executor`` row. P8 protected evolution
(greg.cognition.evolution:cycle) is labelled BUILT with its frozen cycle decisions
(docs/evidence/greg-protected-evolution/*/cycle-*.json) under ``evidence_outside_index``.

Not verified here: that a frozen result reproduces or that the index matches its sources
(tests/unit/test_mind_evidence_sources.py recomputes both), that a simulated world matches any real system,
that a mechanism was ever used on a real mission, or the quality of evidence outside the index (the cortex
seed runs and the P8 cycles are listed under ``evidence_outside_index`` and never raise a label). A recipe or P4
verdict carries no code version in the index, so a later code change does not make it stale here or in the
compiler.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INDEX = ROOT / "docs" / "evidence" / "greg-mind-evidence-index.json"
PATH = ROOT / "greg" / "path.json"
P8_EVIDENCE = ROOT / "docs" / "evidence" / "greg-protected-evolution"
P8_EXECUTOR = "greg.cognition.evolution:cycle"
SCHEMA = "greg-mind-status/0.2"
LABELS = ("BUILT", "SIMULATED", "HELDOUT_SUPPORTED", "EXTERNALLY_VERIFIED", "UNRESOLVED", "FRONTIER")
SUPPORTED = ("SIMULATED", "HELDOUT_SUPPORTED", "EXTERNALLY_VERIFIED")
POSITIVE = ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY")
REFUTED = ("SUPERSEDED", "REJECTED")
SUPPORTING_WORLDS = ("natural_data", "mathematical_instance")
EXTERNAL_KIND = "external_outcome"
# The code an external verification of a recipe or the P4 route must bind (its digest at verification time).
CODE = {"recipe": "greg/cognition/composition.py", "routing": "greg/cognition/conditional_competence.py"}
ALPHA = 0.05
RULES = {
    "EXTERNALLY_VERIFIED": "fresh positive held-out evidence plus a resolved external_verification entry (a "
                           "listed, digested source recording a verified external outcome for this mechanism at its "
                           "current version or code digest)",
    "FRONTIER": "a frontier backcast on greg/path.json or a FRONTIER_HORIZON admission status",
    "SIMULATED": "fresh positive held-out evidence measured on a simulated world (or an undeclared one): "
                 "greg/cognition/worlds.py",
    "HELDOUT_SUPPORTED": "fresh positive held-out evidence on natural data or mathematical instances, or a P4 GAIN",
    "UNRESOLVED": "inconclusive frozen evidence, or an intended mechanism that nothing executes",
    "BUILT": "executable with no positive evidence at its current version (unevaluated, composition stage, "
             "refuted, demoted, or stale after a version bump)",
}


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _p_at_least(k: int, n: int) -> float:
    """One-sided exact sign test: P(X >= k) for X ~ Binomial(n, 1/2), in exact integers (no float overflow)."""
    if n == 0 or k <= 0:
        return 1.0
    return sum(math.comb(n, i) for i in range(k, n + 1)) / 2 ** n


# ------------------------------------------------------------------ external verification
def _resolve_external(entry, mechanism: str, ctx: dict, *, version=None, code=None) -> tuple[dict | None, str]:
    """One external_verification entry -> (the verified external outcome it cites, "") or (None, why it does not
    count). The cited file must be a listed source of the index whose digest still matches."""
    ref = entry.get("evidence") if isinstance(entry, dict) else None
    if not isinstance(ref, str) or "#" not in ref:
        return None, f"{entry!r}: an entry cites its evidence as 'path#pointer'"
    rel, _, pointer = ref.partition("#")
    digest = ctx["sources"].get(rel)
    if digest is None or Path(rel).is_absolute() or ".." in Path(rel).parts:
        return None, f"{ref}: not a listed, digested source of the evidence index"
    file = Path(ctx["root"]) / rel
    try:
        data = file.read_bytes() if file.is_file() else None     # one read: the digested bytes are the parsed ones
    except OSError:
        data = None
    if data is None or "sha256:" + hashlib.sha256(data).hexdigest() != digest:
        return None, f"{ref}: absent, or changed since the index digested it"
    try:
        # a listed source may be a frozen run's README or log, not JSON: the entry is reported, never a crash
        value = json.loads(data.decode("utf-8"))
    except (ValueError, RecursionError):        # JSONDecodeError and UnicodeDecodeError are ValueErrors
        return None, f"{ref}: not a readable JSON source"
    for key in pointer.split("."):
        if not isinstance(value, dict) or key not in value:
            return None, f"{ref}: pointer does not resolve at {key!r}"
        value = value[key]
    if not isinstance(value, dict) or value.get("kind") != EXTERNAL_KIND or value.get("verdict") != "VERIFIED":
        return None, f"{ref}: does not record a verified external outcome"
    if value.get("mechanism") != mechanism:
        return None, f"{ref}: records {value.get('mechanism')!r}, not {mechanism}"
    if version is not None and (value.get("version") != version or entry.get("version", version) != version):
        return None, f"{ref}: verified version {value.get('version')!r}; the current version is {version}"
    if code is not None and value.get("code_sha256") != code[1]:
        return None, f"{ref}: verified another code digest than the current {code[0]}"
    return value, ""


def _external(record, mechanism: str, ctx: dict, **bind) -> tuple[list, list]:
    accepted, problems = [], []
    for entry in (record or {}).get("external_verification") or []:
        value, why = _resolve_external(entry, mechanism, ctx, **bind)
        if value is None:
            problems.append(why)
        else:
            accepted.append({"evidence": entry["evidence"], "outcome": value})
    return accepted, problems


def _attach_external(row: dict, accepted: list, problems: list, frozen: str) -> dict:
    """Records external entries on a labelled row; a resolved entry the label does not use is a conflict."""
    if accepted:
        row["external_verification"] = accepted
        if row["label"] != "EXTERNALLY_VERIFIED":
            row["external_verification_conflict"] = (
                f"an external outcome is recorded but the frozen record is {frozen}: it does not override that "
                f"record, which the compiler routes on")
    if problems:
        row["external_verification_unresolved"] = problems
    return row


# ------------------------------------------------------------------ admission rules (genomes and organs)
def _positive_label(world: str | None, why: str | None) -> tuple[str, str]:
    if world in SUPPORTING_WORLDS:
        where = "natural data" if world == "natural_data" else "mathematical instances"
        return "HELDOUT_SUPPORTED", f"on {where}" + (f" ({why})" if why else "")
    if world == "simulated_world":
        return "SIMULATED", f"on a simulated world ({why})"
    return "SIMULATED", ("on a benchmark world greg/cognition/worlds.py does not declare: never claimed beyond "
                         "simulation")


def _admission_label(status, measured, current, stale: bool, world, why) -> tuple[str, str]:
    """The label of a genome or organ from its frozen admission status, as the compiler routes it."""
    at = f"at version {measured}" if measured else "(no version recorded)"
    if status == "FRONTIER_HORIZON":
        return "FRONTIER", "admission placed it on the frontier horizon"
    if status in POSITIVE and not stale:
        label, where = _positive_label(world, why)
        return label, f"{status} on held-out seeds {at}, measured {where}"
    if status == "EXPERIMENTAL":
        return "UNRESOLVED", "no demonstrated edge over the simple baseline on held-out seeds"
    if stale:
        return "BUILT", f"{status} was measured at version {measured}; version {current} needs re-admission"
    if status in REFUTED:
        return "BUILT", f"{status} on held-out seeds: refuted as the method for its geometry"
    if status == "COMPOSITION_ONLY":
        return "BUILT", "a composition stage: its contribution is measured through recipes"
    return "BUILT", "no frozen held-out admission (UNEVALUATED)"


def _genomes(index: dict, ctx: dict) -> list[dict]:
    from greg.cognition import worlds
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
        world, why = worlds.GENOMES.get(family, (None, None))
        mid = f"cognition.{family}"
        accepted, problems = _external(record, mid, ctx, version=g.version)
        if accepted and status in POSITIVE and not stale:
            label = "EXTERNALLY_VERIFIED"
            basis = f"{status} on held-out seeds at version {measured} and an external outcome verified at it"
        else:
            label, basis = _admission_label(status, measured, g.version, stale, world, why)
        if heldout and heldout["current"] is False and not stale and status not in POSITIVE:
            basis += (f"; measured at version {measured}, current {g.version}: negative or inconclusive evidence "
                      f"persists until a re-admission replaces it")
        rows.append(_attach_external(
            {"id": mid, "kind": "genome", "label": label, "basis": basis,
             "layer": g.layer, "intelligence_id": g.intelligence_id, "version_current": g.version,
             "epistemic_class": g.epistemic_class, "evidence_type": g.evidence_type,
             "benchmark_world": world, "simulated_world": world not in SUPPORTING_WORLDS, "heldout": heldout},
            accepted, problems, f"{status or 'UNEVALUATED'}{' (stale)' if stale else ''}"))
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


def _cortex_organs(index: dict, ctx: dict) -> list[dict]:
    """Cortex organs, from the index's ``organs`` section when it has a verdict (the compiler routes on it)."""
    from cortex.genome import SEED_ORGANS
    from greg.cognition import worlds
    from greg.cognition.catalog import CORTEX_ENTRIES
    organs = index.get("organs") or {}
    rows = []
    for cid, (version, classes, deterministic, network, description) in sorted(CORTEX_ENTRIES.items()):
        organ = SEED_ORGANS.get(cid.removeprefix("cognition."), {})
        outside = sorted(set(organ.get("benchmarks") or ()))
        record = organs.get(cid)
        status = (record or {}).get("status")
        measured = (record or {}).get("version")
        stale = bool(status in POSITIVE and measured and measured != version)
        world, why = worlds.ORGANS.get(cid, (None, None))
        accepted, problems = _external(record, cid, ctx, version=version)
        if record is None:
            label, basis = ("BUILT", "executable cortex organ on the cognition path; no per-organ verdict in the "
                                     "evidence index")
        elif accepted and status in POSITIVE and not stale:
            label = "EXTERNALLY_VERIFIED"
            basis = f"{status} on held-out evidence at version {measured} and an external outcome verified at it"
        else:
            label, basis = _admission_label(status, measured, version, stale, world, why)
            basis = "per-organ verdict in the evidence index: " + basis
        rows.append(_attach_external(
            {"id": cid, "kind": "cortex_organ", "label": label, "basis": basis, "version_current": version,
             "epistemic_classes": list(classes), "deterministic": deterministic, "network": network,
             "benchmark_world": world, "heldout": record, "evidence_outside_index": outside},
            accepted, problems, f"{status or 'UNEVALUATED'}{' (stale)' if stale else ''}"))
    for cid in sorted(set(organs) - set(CORTEX_ENTRIES)):
        rows.append({"id": cid, "kind": "cortex_organ", "label": "UNRESOLVED",
                     "basis": "a frozen per-organ verdict for an organ no longer in the catalog",
                     "heldout": organs[cid]})
    return rows


def _recipes(index: dict, ctx: dict) -> list[dict]:
    from greg.cognition import worlds
    from greg.cognition.composition import RECIPES
    code = (CODE["recipe"], _sha(ROOT / CODE["recipe"]))
    rows = []
    for name in sorted(set(RECIPES) | set(index.get("recipes", {}))):
        record = index.get("recipes", {}).get(name)
        mid = f"recipe.{name}"
        accepted, problems = _external(record, mid, ctx, code=code)
        executable = name in RECIPES
        family = (record or {}).get("family")
        world, why = worlds.P6_FAMILIES.get(family, (None, None))
        lift = (record or {}).get("status") == "VPL_LIFT"
        if not executable:
            label, basis = "UNRESOLVED", "a frozen verdict for a recipe no longer in greg.cognition.composition"
        elif accepted and lift:
            label, basis = "EXTERNALLY_VERIFIED", f"VPL lift on held-out family {family} and an external outcome"
        elif record is None:
            label, basis = "BUILT", "no frozen P6 verdict"
        elif lift:
            label, where = _positive_label(world, why)
            basis = (f"VPL lift on held-out family {family}: {record.get('wins')} wins, {record.get('losses')} "
                     f"losses against the best constituent, measured {where}")
        else:
            wins, losses = int(record.get("wins") or 0), int(record.get("losses") or 0)
            worse, better = _p_at_least(losses, wins + losses), _p_at_least(wins, wins + losses)
            prefer = f"the compiler prefers {record.get('prefer')}"
            if worse < ALPHA:
                label = "BUILT"
                basis = (f"no lift on {family}: significantly worse than its best constituent "
                         f"(one-sided p {worse:.4g}); {prefer}")
            elif better < ALPHA:
                label = "UNRESOLVED"
                basis = (f"no VPL lift on {family} under the frozen rule although significantly better on wins "
                         f"({wins} wins, {losses} losses, one-sided p {better:.4g}): the frozen verdict decides "
                         f"(see verdict); {prefer}")
            else:
                label = "UNRESOLVED"
                basis = (f"no lift on {family}: {wins} wins, {losses} losses, neither direction significant "
                         f"(one-sided p {better:.4g} better, {worse:.4g} worse); {prefer}")
        rows.append(_attach_external(
            {"id": mid, "kind": "recipe", "label": label, "basis": basis, "executable": executable,
             "benchmark_world": world, "verdict": record},
            accepted, problems, (record or {}).get("status") or "no frozen P6 verdict"))
    return rows


def _routing(index: dict, ctx: dict) -> list[dict]:
    record = index.get("routing", {}).get("conditional_competence")
    verdict = (record or {}).get("verdict")
    mid = "routing.conditional_competence"
    accepted, problems = _external(record, mid, ctx, code=(CODE["routing"], _sha(ROOT / CODE["routing"])))
    if accepted and verdict == "GAIN":
        label, basis = "EXTERNALLY_VERIFIED", "P4 GAIN on its frozen held-out retest and an external outcome"
    elif verdict == "GAIN":
        label, basis = "HELDOUT_SUPPORTED", "P4 conditional routing gained on its frozen held-out retest"
    elif verdict == "REGRESSION":
        label, basis = "BUILT", "P4 conditional routing was demoted after its frozen retest; it runs in shadow only"
    elif record is None:
        label, basis = "BUILT", "no frozen P4 verdict"
    else:
        label, basis = "UNRESOLVED", f"P4 verdict {verdict}"
    return [_attach_external({"id": mid, "kind": "routing", "label": label, "basis": basis,
                              "executor": CODE["routing"], "verdict": record},
                             accepted, problems, verdict or "no frozen P4 verdict")]


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


def ledger_id(ref: str) -> str:
    """The ledger row an executor reference is labelled by: ``cognition.<family>`` and ``module:symbol`` as named,
    a cortex seed organ ``cortex.<organ>@<version>`` by its catalog id ``cognition.cortex.<organ>``."""
    return f"cognition.{ref.partition('@')[0]}" if "@" in ref and ":" not in ref else ref


def _p8_cycles() -> list[dict]:
    cycles = []
    for path in sorted(P8_EVIDENCE.glob("*/cycle-*.json")):
        data = json.loads(path.read_text())
        cycles.append({"path": _display(path), "sha256": _sha(path), "target": data.get("target"),
                       "decision": data.get("decision"), "finished_at": data.get("finished_at")})
    return sorted(cycles, key=lambda c: (c["finished_at"] or "", c["path"]))


def _resolves(ref: str) -> bool:
    module, _, symbol = ref.partition(":")
    try:
        return getattr(importlib.import_module(module), symbol, None) is not None
    except ImportError:
        return False


def _p8_basis(cycles: list[dict]) -> str:
    head = "P8 protected evolution executes under a sealed evaluator; "
    if not cycles:
        return head + "no frozen cycle yet"
    summary = "; ".join(f"{c['target']} {c['decision']}" for c in cycles)
    if all(c["decision"] == "REJECT" for c in cycles):
        return head + (f"{len(cycles)} frozen cycles ({summary}): every one rejected its candidate, so it has never "
                       f"kept an improvement")
    return head + (f"{len(cycles)} frozen cycles ({summary}); a cycle record is evidence outside the evidence index "
                   f"and never raises a label")


def _executors(executed: dict, ids: set) -> list[dict]:
    """A row for every executor greg/cognition/reserved.py names that no other row labels."""
    named: dict[str, list] = {}
    for name, refs in sorted(executed.items()):
        for ref in refs:
            if ledger_id(ref) not in ids:
                named.setdefault(ref, []).append(name)
    rows = []
    for ref, reserved in sorted(named.items()):
        row = {"id": ledger_id(ref), "kind": "executor", "executes_reserved": reserved}
        if ":" not in ref or not _resolves(ref):
            row.update(label="UNRESOLVED", basis=f"named in greg/cognition/reserved.py as the executor of "
                                                  f"{', '.join(reserved)} but resolves to nothing on GREG's path")
        elif ref == P8_EXECUTOR:
            cycles = _p8_cycles()
            row.update(label="BUILT", basis=_p8_basis(cycles), evidence_outside_index=cycles)
        else:
            row.update(label="BUILT", basis=f"executes on GREG's cognition path as the executor of "
                                            f"{', '.join(reserved)}; no frozen held-out verdict in the evidence index")
        rows.append(row)
    return rows


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


def status(index_path: Path | None = None, path_file: Path | None = None,
           evidence_root: Path | None = None) -> dict:
    """The reality ledger as a dict (pure: reads files and the catalog, writes nothing). ``evidence_root`` is the
    directory the index's source paths are relative to (default: the repository root)."""
    index_path, path_file = Path(index_path or INDEX), Path(path_file or PATH)
    missing = []
    if index_path.exists():
        index = json.loads(index_path.read_text())
        missing += [f"evidence index lists a missing source: {m}" for m in index.get("missing_sources", [])]
    else:
        index = {"genomes": {}, "recipes": {}, "routing": {}}
        missing.append(f"{_display(index_path)} (no evidence index: nothing can be held-out supported)")
    ctx = {"sources": {s.get("path"): s.get("sha256") for s in index.get("sources", [])},
           "root": Path(evidence_root or ROOT)}
    path_data = json.loads(path_file.read_text())
    reserved, executed = _reserved()
    rows = (_genomes(index, ctx) + _catalog_families() + _cortex_organs(index, ctx) + _recipes(index, ctx)
            + _routing(index, ctx) + reserved + _frontier(path_data))
    rows += _executors(executed, {r["id"] for r in rows})
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
        "external_verification_problems": [
            f"{r['id']}: {problem}" for r in rows
            for problem in [*r.get("external_verification_unresolved", []),
                            *([r["external_verification_conflict"]] if r.get("external_verification_conflict")
                              else [])]],
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
