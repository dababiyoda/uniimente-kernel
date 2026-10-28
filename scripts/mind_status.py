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
                       not significantly worse than its best constituent; a P4 verdict that is neither GAIN nor a
                       decisive no-gain: REGRESSION or NO_GAIN), or an intended mechanism nothing executes (a catalog family without an
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
fresh positive evidence (tests/unit/test_mind_status.py checks this against the compiler). A genome's held-out
history flags a status that changed between frozen runs at the same version: within one evaluation regime as
``status_changed_at_same_version`` (a sample near a rule boundary, or a rule change), and across a regime change a
run's pre-registration declared (``DECLARED_REGIMES``) as ``status_changed_with_declared_regime_change``.

Every executor greg/cognition/reserved.py names has a row: catalog families, genomes and cortex organs have their
own; a ``module:symbol`` executor gets an ``executor`` row. P8 protected evolution
(greg.cognition.evolution:cycle) is labelled BUILT with its frozen cycle decisions
(docs/evidence/greg-protected-evolution/*/cycle-*.json) under ``evidence_outside_index``.

EXERCISED is a projection beside the labels, never a label and never an input to one: which mechanisms actually ran
inside a recorded GREG mission on the durable mission path, with a receipt (``exercised``). It reads every committed
mission ledger (``*.jsonl``) and JSON trace under tests/evidence and docs/evidence that records a
``greg.cognition.settled`` event, and lists each settlement's method and the methods its causal credit names, with the
mission, the receipt digests and the ledger position. Every source is labelled with the key class that signed its
founder commands and with its environment (sandbox, container, temporary state). A key is the founder's only if its
id is in ``FOUNDER_KEY_IDS``, which is empty: no committed evidence enrolls a founder key, so founder use is claimed
for nothing. A settlement a trace cites without a ledger position is listed and flagged; a trace whose ledger was
not retained says so.

PR #179's operation-family admissions are reported in ``lineage_179``, read from its committed results with git show
at the pinned commit ``LINEAGE_179["commit"]``; no #179 code is imported. Each row names the family's frozen status
there, its seeds and source commit, and the row on this line it corresponds to. A catalog-family row that would
otherwise read as BUILT with no explanation gets a ``lineage_179`` field and a sentence in its basis saying why it
stays BUILT here: the verdict measured #179's solver code, which this line does not run. Neither the projection nor
these rows changes a label, a count or routing.

Not verified here: that a frozen result reproduces or that the index matches its sources
(tests/unit/test_mind_evidence_sources.py recomputes both), that a simulated world matches any real system,
that a mechanism was ever used on a real (founder, non-sandbox) mission, or the quality of evidence outside the index (the cortex
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
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

INDEX = ROOT / "docs" / "evidence" / "greg-mind-evidence-index.json"
PATH = ROOT / "greg" / "path.json"
P8_EVIDENCE = ROOT / "docs" / "evidence" / "greg-protected-evolution"
P8_EXECUTOR = "greg.cognition.evolution:cycle"
SCHEMA = "greg-mind-status/0.4"
LABELS = ("BUILT", "SIMULATED", "HELDOUT_SUPPORTED", "EXTERNALLY_VERIFIED", "UNRESOLVED", "FRONTIER")
SUPPORTED = ("SIMULATED", "HELDOUT_SUPPORTED", "EXTERNALLY_VERIFIED")
POSITIVE = ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY")
REFUTED = ("SUPERSEDED", "REJECTED")
SUPPORTING_WORLDS = ("natural_data", "mathematical_instance")
EXTERNAL_KIND = "external_outcome"
# The code an external verification of a recipe or the P4 route must bind (its digest at verification time).
CODE = {"recipe": "greg/cognition/composition.py", "routing": "greg/cognition/conditional_competence.py"}
# Evaluation regimes a frozen admission run's pre-registration declared changed, before the run, for genomes whose
# version did not change (instance generator, competitor or scorer): an earlier status at the same version measured
# another evaluation, so a different status is a regime change, not a sample near a rule boundary. A declaration
# binds its pre-registration's digest; one that does not resolve declares nothing and is reported on the row.
DECLARED_REGIMES = {
    "2026-10-15-v3": {
        "declared_in": "docs/evidence/greg-genome-admission/2026-10-15-v3/PREREGISTRATION.md",
        "sha256": "sha256:19924fff02c70a53985c646108293b462bafbd8a23a21e388fa4adfadb0b15d5",
        "families": {"collective_quorum": "instance generator",
                     "collective_immune": "instance generator and competitor",
                     "collective_physarum": "instance generator, competitor and scorer",
                     "collective_flock": "instance generator, competitor and scorer"}},
}
ALPHA = 0.05
# Where retained mission ledgers and traces live; a source counts when it records a greg.cognition.settled event.
EXERCISED_ROOTS = ("tests/evidence", "docs/evidence")
SETTLED = "greg.cognition.settled"
# Key ids of founder keys enrolled in committed evidence. Empty: every recorded mission used a per-test or per-run
# key. Adding an id here is a founder act recorded with its enrollment evidence, never an inference.
FOUNDER_KEY_IDS: tuple[str, ...] = ()
TEST_KEY = re.compile(r"NOT Alfonso|not Alfonso's|per-test|per-run test|test key", re.I)
SANDBOX = re.compile(r"container|temporary|pytest|/tmp/|sandbox|state dir", re.I)
# PR #179's operation-family admission v3, read from its committed results at a pinned commit (never imported).
LINEAGE_179 = {"pr": 179, "commit": "0067be618c6f5150e9faac584b99baf5d09f540f",
               "branch": "origin/claude/greg-mind-lineage-convergence",
               "results": "docs/evidence/greg-operation-admission/2026-10-16-v3/results-ops-v3.json",
               "freeze": "cortex/evaluation/genome_admission/freeze-ops-v3.json",
               "solvers": "greg/cognition/solvers.py"}
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


def _history(family: str, record: dict) -> tuple[list, list, list]:
    """A genome's frozen runs, oldest first, each with ``regime``: the run whose evaluation regime it was measured
    under (its first run, or the latest run whose pre-registration declared a regime change for this genome).
    Returns (history, the resolved regime changes, the declarations that did not resolve)."""
    history, changes, unresolved, regime = [], [], [], None
    for h in record.get("history", []):
        declared = DECLARED_REGIMES.get(h.get("run")) or {}
        changed = declared.get("families", {}).get(family)
        if changed:
            file = ROOT / declared["declared_in"]
            if file.is_file() and _sha(file) == declared["sha256"]:
                regime = h.get("run")
                changes.append({"run": regime, "changed": changed, "declared_in": declared["declared_in"]})
            else:
                unresolved.append(f"{h.get('run')}: {declared['declared_in']} is absent or changed since its "
                                  f"declaration was bound, so it declares no regime change")
        regime = regime or h.get("run")
        history.append({**{k: h.get(k) for k in ("run", "status", "version")}, "regime": regime})
    return history, changes, unresolved


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
        history, changes, unresolved = _history(family, record or {})
        runs = [h for h in history if h["version"] == measured]
        within = any(a["regime"] == b["regime"] and a["status"] != b["status"]
                     for i, a in enumerate(runs) for b in runs[i + 1:])
        across = any(a["regime"] != b["regime"] and a["status"] != b["status"] for a, b in zip(runs, runs[1:]))
        heldout = None if record is None else {
            "status": status, "version_measured": measured,
            "current": None if measured is None else measured == g.version,
            "evidence": record.get("evidence"),
            "history": history,
            # a status that differs between any two frozen runs at the same version and in the same evaluation regime
            # sits near a rule boundary (or the rule changed between runs), whichever regime they share; one that
            # differs between the runs either side of a regime change the later run's pre-registration declared
            # measured another evaluation. The latest run decides, as it does for the compiler
            "status_changed_at_same_version": within,
            "status_changed_with_declared_regime_change": across,
            **({"regime_changes": changes} if changes else {}),
            **({"regime_declarations_unresolved": unresolved} if unresolved else {}),
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
        from greg.cognition.compiler import evidence_index, family_status
        admission = family_status(family, evidence_index())   # the compiler's one status function (review M16)
        if not executor:
            label, basis = "UNRESOLVED", "registered in the catalog without an executor"
        elif admission["raw"] is None:
            label, basis = "BUILT", "executable on the cognition path; no frozen held-out verdict in the evidence index"
        else:
            label = "BUILT"
            basis = (f"frozen held-out verdict {admission['raw']} ({admission['evidence']}); routes as "
                     f"{admission['status']}" + (f"; stale: {admission['stale']}" if admission["stale"] else ""))
        rows.append({"id": f"cognition.{family}", "kind": "catalog_family", "label": label, "basis": basis,
                     "layer": layer, "operations": list(operations), "epistemic_classes": list(classes),
                     "proof_class": proof, "dependency": dependency, "seed_family": family in SEED_FAMILIES,
                     "executor": executor, "admission": admission})
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
            from greg.cognition.compiler import recipe_stale
            label, where = _positive_label(world, why)
            stale = recipe_stale(name, record)
            if stale:
                label = "BUILT"
            basis = (f"VPL lift on held-out family {family}: {record.get('wins')} wins, {record.get('losses')} "
                     f"losses against the best constituent, measured {where}"
                     + (f"; stale: {stale}" if stale else ""))
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
    elif verdict in ("REGRESSION", "NO_GAIN"):
        # a decisive retest without gain demotes it (founder rule 2026-10-07: not currently worth its complexity)
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


def _key_class(key_ids: list[str], labels: list[str]) -> str:
    if any(k in FOUNDER_KEY_IDS for k in key_ids):
        return "founder_key"
    if any(TEST_KEY.search(label or "") for label in labels):
        return "test_key"
    return "unverified_key (not shown to be the founder's)"


def _settlements_in(value, pointer: str = "") -> list[tuple[str, dict]]:
    """Every settlement a JSON document cites: ``greg.cognition.settled`` events (with a ledger position) and the
    method entries of a ``*settlements`` list (which may have none)."""
    out = []
    if isinstance(value, dict):
        if value.get("type") == SETTLED and value.get("method"):
            out.append((pointer, value))
        for key, item in value.items():
            if isinstance(item, list) and str(key).endswith("settlements"):
                for i, entry in enumerate(item):
                    if isinstance(entry, dict) and entry.get("method") and entry.get("type") != SETTLED:
                        out.append((f"{pointer}/{key}/{i}", entry))
            out += _settlements_in(item, f"{pointer}/{key}")
    elif isinstance(value, list):
        for i, item in enumerate(value):
            out += _settlements_in(item, f"{pointer}/{i}")
    return out


def _ledger_source(path: Path) -> tuple[dict, list[dict]]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    keys, settled = [], []
    for row in rows:
        event = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        body = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event.get("type") == "greg.founder.enrolled":
            keys.append(body.get("key_id"))
        elif event.get("type") == SETTLED:
            settled.append({"mission_id": body.get("mission_id"), "method": body.get("method"),
                            "method_version": body.get("method_version"), "correct": body.get("correct"),
                            "credited": [c.get("method") for c in body.get("causal_credit") or []],
                            "roles": {c.get("method"): c.get("role") for c in body.get("causal_credit") or []},
                            "receipt": body.get("receipt"), "cognitive_receipt": body.get("cognitive_receipt"),
                            "ledger_seq": row.get("seq"), "ledger_hash": row.get("hash"),
                            "evidence_tier": body.get("evidence_tier")})
    labels, environment = [], []
    for summary in sorted(path.parent.glob("*.json")):
        try:
            doc = json.loads(summary.read_text())
        except ValueError:
            continue
        if isinstance(doc, dict):
            labels += [str(doc[k]) for k in ("founder_key",) if k in doc]
            environment += [str(doc[k]) for k in ("host",) if k in doc]
    source = {"path": _display(path), "sha256": _sha(path), "kind": "mission ledger", "ledger_retained": True,
              "enrolled_key_ids": keys, "key_labels": labels, "key_class": _key_class(keys, labels),
              "environment": environment, "sandbox": any(SANDBOX.search(e) for e in environment) or not environment}
    return source, settled


def _trace_source(path: Path, doc: dict) -> tuple[dict, list[dict]]:
    labels = doc.get("labels") if isinstance(doc.get("labels"), dict) else {}
    key_labels = [str(labels[k]) for k in ("founder_key",) if k in labels] + (
        [str(doc["founder_key"])] if "founder_key" in doc else [])
    environment = [f"{k}: {labels[k]}" for k in ("effects", "state_dir", "clock") if k in labels]
    settled, seen = [], set()
    for pointer, entry in _settlements_in(doc):
        key = (entry.get("seq"), entry.get("hash"), entry.get("method"), pointer if entry.get("seq") is None else "")
        if key in seen or (entry.get("seq") is not None and (entry.get("seq"), entry.get("hash"), entry.get("method"))
                           in {(s, h, m) for s, h, m, _ in seen}):
            continue
        seen.add(key)
        mission = entry.get("mission_id") or next(iter(re.findall(r"mission_\d+", pointer)), None) or \
            "unnamed in the trace"
        settled.append({"mission_id": mission, "check_id": entry.get("check_id"), "method": entry.get("method"),
                        "method_version": entry.get("method_version"), "correct": entry.get("correct"),
                        "credited": [], "roles": {}, "receipt": entry.get("receipt"),
                        "ledger_seq": entry.get("seq"), "ledger_hash": entry.get("hash"), "pointer": pointer,
                        **({} if entry.get("seq") is not None else
                           {"flag": "cited without a ledger position or receipt"})})
    ledger = doc.get("ledger") if isinstance(doc.get("ledger"), dict) else {}
    source = {"path": _display(path), "sha256": _sha(path), "kind": "mission trace",
              "ledger_retained": False, "ledger_head": ledger.get("head"),
              "ledger_chain_verified": ledger.get("chain_verified"), "enrolled_key_ids": [],
              "key_labels": key_labels, "key_class": _key_class([], key_labels), "environment": environment,
              "sandbox": any(SANDBOX.search(e) for e in environment) or not environment}
    return source, settled


def _exercised(rows: list[dict]) -> dict:
    """Mechanisms that ran inside a recorded GREG mission with a receipt; a projection that changes no label."""
    sources, settlements = [], []
    for root in EXERCISED_ROOTS:
        for path in sorted((ROOT / root).rglob("*")):
            if path.suffix not in (".jsonl", ".json") or not path.is_file():
                continue
            text = path.read_text(errors="replace")
            if SETTLED not in text:
                continue
            if path.suffix == ".jsonl":
                source, settled = _ledger_source(path)
            else:
                try:
                    doc = json.loads(text)
                except ValueError:
                    continue
                if not _settlements_in(doc):
                    continue
                source, settled = _trace_source(path, doc)
            sources.append(source)
            settlements += [{"source": source["path"], **s} for s in settled]
    by_source = {s["path"]: s for s in sources}
    ids = {r["id"] for r in rows}
    mechanisms: dict[str, dict] = {}
    for s in settlements:
        src = by_source[s["source"]]
        for method, role in [(s["method"], "settled method"), *[(m, f"credited {s['roles'].get(m) or 'stage'}")
                                                               for m in s["credited"]]]:
            if not method:
                continue
            mid = ledger_id(method) if "@" in method and ":" not in method else method
            entry = mechanisms.setdefault(mid, {"row": mid if mid in ids else None, "missions": set(), "as": set(),
                                                "settlements": 0, "with_ledger_position": 0, "key_classes": set(),
                                                "sandbox": set(), "sources": set(), "named": set()})
            entry["named"].add(method)
            entry["missions"].add(f"{s['source']}#{s['mission_id']}")
            entry["as"].add(role)
            entry["settlements"] += 1
            entry["with_ledger_position"] += s.get("ledger_seq") is not None
            entry["key_classes"].add(src["key_class"])
            entry["sandbox"].add(src["sandbox"])
            entry["sources"].add(s["source"])
    projected = {mid: {**{k: sorted(v) if isinstance(v, set) else v for k, v in e.items()},
                       "founder_use": "founder_key" in e["key_classes"]} for mid, e in sorted(mechanisms.items())}
    return {
        "rule": "a mechanism is EXERCISED when a committed mission ledger or trace records a greg.cognition.settled "
                "event naming it as the settled method or in its causal credit; this projection never sets a label",
        "sources": sources,
        "settlements": settlements,
        "mechanisms": projected,
        "founder_use": sorted(m for m, e in projected.items() if e["founder_use"]),
        "without_row": sorted(m for m, e in projected.items() if e["row"] is None),
    }


def _git_show(commit: str, path: str) -> bytes | None:
    try:
        out = subprocess.run(["git", "cat-file", "blob", f"{commit}:{path}"], cwd=ROOT, capture_output=True,
                             timeout=60, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout if out.returncode == 0 else None


def _lineage_179(rows: list[dict]) -> dict:
    """#179's operation-family admission v3 rows from its committed results at the pinned commit."""
    pin = LINEAGE_179
    raw = _git_show(pin["commit"], pin["results"])
    if raw is None:
        return {**pin, "available": False,
                "why": f"commit {pin['commit']} is not in this clone; fetch {pin['branch']} to read it", "rows": []}
    data = json.loads(raw)
    # On a tree whose own evidence index lists this run (the converged #179 tree), its verdicts already route there
    # through the operation rows: the lineage view would duplicate them and its "raises no label here" would be
    # false, so it reports that and adds no rows (adopted from #179 54278f2f)
    try:
        listed = {s.get("path") for s in json.loads(INDEX.read_text()).get("sources", [])}
    except (OSError, ValueError):
        listed = set()
    if pin["results"] in listed:
        return {**pin, "available": True, "in_this_index": True, "source_commit": data.get("source_commit"),
                "seeds": data.get("seeds"), "rows": [], "families_only_on_179": [],
                "why": "this tree's evidence index lists this run, so its verdicts route here through the operation "
                       "rows; no separate lineage rows"}
    freeze = json.loads(_git_show(pin["commit"], pin["freeze"]) or b"{}")
    frozen_solvers = ((freeze.get("inputs") or {}).get("files") or {}).get(pin["solvers"])
    here_solvers = _sha(ROOT / pin["solvers"]) if (ROOT / pin["solvers"]).exists() else None
    by_id = {r["id"]: r for r in rows}
    measured = [(family, record) for family, record in sorted((data.get("families") or {}).items())]
    if isinstance(data.get("crowd_sparse"), dict):
        measured.append(("crowd_sparse", data["crowd_sparse"]))
    out = []
    for family, record in measured:
        here = by_id.get(f"cognition.{family}")
        status = record.get("status")
        measured_here = "vs_baseline" in record
        out.append({"id": f"lineage179.{family}", "lineage": "#179", "family": family, "status": status,
                    "measured": measured_here, "reason": record.get("reason"),
                    "benchmark": record.get("benchmark"), "candidate": record.get("candidate"),
                    "baseline": record.get("baseline"), "competitor": record.get("competitor"),
                    "vs_baseline": record.get("vs_baseline"), "vs_competitor": record.get("vs_competitor"),
                    "seeds": data.get("seeds"), "source_commit": data.get("source_commit"),
                    "pinned_commit": pin["commit"], "results": pin["results"], "results_sha256":
                    "sha256:" + hashlib.sha256(raw).hexdigest(),
                    "this_line": {"id": here["id"], "kind": here["kind"], "label": here["label"]} if here else None,
                    "counts_here": False,
                    "why": (f"measured on #179's code ({pin['solvers']} {frozen_solvers} at its freeze; this line's is "
                            f"{here_solvers}{', identical' if frozen_solvers == here_solvers else ', different'}); "
                            f"this line neither runs that code nor routes on #179's index, so the verdict raises no "
                            f"label here")})
        if here is not None and here["kind"] == "catalog_family":
            here["lineage_179"] = {"status": status, "seeds": data.get("seeds"),
                                   "source_commit": data.get("source_commit"), "pinned_commit": pin["commit"],
                                   "results": pin["results"]}
            here["lineage_179"] = {**here["lineage_179"], "measured": measured_here}
            here["basis"] += (
                f"; PR #179 (pinned {pin['commit'][:7]}) holds a frozen {status} for this family from its operation "
                f"admission v3 on seeds {data.get('seeds')}, measured on #179's solver code, not this line's: "
                f"reported in lineage_179, it raises no label here" if measured_here else
                f"; PR #179 (pinned {pin['commit'][:7]}) records this family as {status} in its operation admission "
                f"v3 without measuring it ({record.get('reason')}): reported in lineage_179")
    return {**pin, "available": True, "schema": data.get("schema"), "source_commit": data.get("source_commit"),
            "seeds": data.get("seeds"), "solvers_sha256_at_179_freeze": frozen_solvers,
            "solvers_sha256_here": here_solvers, "rows": out,
            "families_only_on_179": sorted(r["family"] for r in out if r["this_line"] is None)}


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
    exercised = _exercised(rows)
    for row in rows:
        entry = exercised["mechanisms"].get(row["id"])
        if entry:
            row["exercised"] = {"missions": entry["missions"], "as": entry["as"], "key_classes": entry["key_classes"],
                                "founder_use": entry["founder_use"]}
    lineage_179 = _lineage_179(rows)
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
        "exercised": exercised,
        "lineage_179": lineage_179,
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
