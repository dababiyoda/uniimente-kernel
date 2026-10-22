"""The converged Mind (Track B, 2026-10-14): one entry, one evolution controller, one admission source.

PR #155 and PR #158 built the 2026-10-07 directive in parallel. These checks pin what the convergence decided
(docs/collaboration/MIND-LINEAGE-RECONCILIATION-2026-10-14.md) so a later change cannot silently reopen it:

* the two families' namespaces stay disjoint on the one solver table;
* exactly one protected-evolution controller is reachable from GREG's runtime;
* archival copies of the eight colliding frozen paths are byte-identical to the commits they claim;
* PR #155's frozen held-out verdicts change the Competency Compiler's routing, and the genome inventory reads
  the same index the compiler routes on;
* one Landlock grant path covers both lineages' runtime library lists.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
ARCHIVE = ROOT / "docs" / "collaboration" / "lineage-archive"
LINEAGES = {"pr155-ef5f078": "ef5f078", "pr158-a832c73": "a832c73"}
COLLIDED = ("cortex/evaluation/composition_lift/freeze-v2.json", "cortex/evaluation/composition_lift/freeze-v3.json",
            "cortex/evaluation/composition_lift/run_v2.py", "cortex/evaluation/composition_lift/run_v3.py",
            "cortex/evaluation/learned_routing/freeze-v3.json", "cortex/evaluation/learned_routing/run_v3.py",
            "cortex/evaluation/learned_routing/suite-v3.json",
            "docs/evidence/greg-protected-evolution/2026-10-14/README.md")


def test_repertoire_and_genome_families_share_one_solver_table_without_a_name_clash():
    from greg.cognition import catalog, solvers
    from greg.cognition.genomes import library
    from greg.cognition.repertoire import REPERTOIRE
    genomes = set(library.catalog_families())
    assert not set(REPERTOIRE) & genomes
    assert set(REPERTOIRE) | genomes <= set(solvers.SOLVERS) | {"semantic"}
    assert set(REPERTOIRE) <= set(catalog.FAMILIES)


def _imports_module(path: Path, module: str) -> bool:
    tree = ast.parse(path.read_text(errors="ignore"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[-1] == module:
            return True
        if isinstance(node, ast.ImportFrom) and any(a.name == module for a in node.names):
            return True
        if isinstance(node, ast.Import) and any(a.name.split(".")[-1] == module for a in node.names):
            return True
    return False


def _fold(node: ast.AST) -> str | None:
    """The string a constant expression evaluates to, or None: concatenation, f-strings of constants and
    ``"sep".join`` / ``"...".format`` of constant arguments. No code is evaluated."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _fold(node.left), _fold(node.right)
        return left + right if left is not None and right is not None else None
    if isinstance(node, ast.JoinedStr):
        parts = [_fold(v.value if isinstance(v, ast.FormattedValue) else v) for v in node.values]
        return "".join(parts) if all(p is not None for p in parts) else None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("join", "format"):
        base = _fold(node.func.value)
        if base is None:
            return None
        if node.func.attr == "join" and len(node.args) == 1 and isinstance(node.args[0], (ast.List, ast.Tuple)):
            items = [_fold(e) for e in node.args[0].elts]
            return base.join(items) if all(i is not None for i in items) else None
        if node.func.attr == "format" and not node.keywords:
            items = [_fold(a) for a in node.args]
            if all(i is not None for i in items):
                try:
                    return base.format(*items)
                except (IndexError, KeyError, ValueError):
                    return None
    return None


def _folded_strings(tree: ast.AST) -> set[str]:
    """Every string a constant expression in ``tree`` folds to (round-2 review of #179, L7: a split literal escaped
    the textual scan)."""
    return {v for node in ast.walk(tree) if (v := _fold(node)) is not None}


def test_one_evolution_controller_is_reachable_from_runtime():
    """greg.cognition.evolution is the controller; the #155 routing-genome mechanism is an isolated alternative
    imported only by its historical runner (and its own tests)."""
    # every source tree but tests, docs and the lineage archive (review of #179, L7: a top-level package and a
    # dynamic import by string both escaped the narrower scan)
    skip = {"tests", "docs", "lineage-archive", "node_modules", ".git"}
    sources = [p for p in ROOT.rglob("*.py") if not skip & set(p.relative_to(ROOT).parts[:1])
               and "__pycache__" not in p.parts]
    importers = sorted(str(p.relative_to(ROOT)) for p in sources if _imports_module(p, "evolution_routing"))
    assert importers == ["cortex/evaluation/evolution/run.py"], importers
    allowed = {"cortex/evaluation/evolution/run.py",          # its historical runner
               "greg/cognition/evolution_routing.py",         # itself
               "greg/cognition/genome_library.py",            # names it in the inventory's description text
               # #158's coverage record cites the file as evidence of a benchmarked alternative (a path and a grep
               # pattern); the importer scan above still covers it, so it cannot import the module
               "scripts/build_mind_coverage_record.py"}
    named = sorted(str(p.relative_to(ROOT)) for p in sources
                   if "evolution_routing" in p.read_text(errors="replace") and str(p.relative_to(ROOT)) not in allowed)
    assert named == [], named
    folded = sorted(str(p.relative_to(ROOT)) for p in sources if str(p.relative_to(ROOT)) not in allowed
                    and any("evolution_routing" in v for v in _folded_strings(ast.parse(p.read_text(errors="ignore")))))
    assert folded == [], folded
    if "evolution_routing" in (ROOT / "greg/cognition/genome_library.py").read_text():
        tree = ast.parse((ROOT / "greg/cognition/genome_library.py").read_text())
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and "import" in ast.unparse(n.func)]
        assert not any("evolution_routing" in ast.unparse(c) for c in calls)
    from greg.cognition import evolution
    assert hasattr(evolution, "cycle") and hasattr(evolution, "SealedEvaluator")


def _git_blob_sha(commit: str, path: str) -> str | None:
    out = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True, timeout=60)
    return hashlib.sha256(out.stdout).hexdigest() if out.returncode == 0 else None


def test_archived_frozen_files_are_byte_identical_to_their_source_commits():
    absent = [c for c in LINEAGES.values() if subprocess.run(
        ["git", "cat-file", "-e", f"{c}^{{commit}}"], cwd=ROOT, capture_output=True, timeout=30).returncode]
    if absent:
        pytest.skip(f"git history does not hold {absent}: archival identity not verified on this checkout")
    mismatched = []
    for folder, commit in LINEAGES.items():
        for path in COLLIDED:
            copy = ARCHIVE / folder / path
            if not copy.is_file() or hashlib.sha256(copy.read_bytes()).hexdigest() != _git_blob_sha(commit, path):
                mismatched.append(f"{folder}/{path}")
    assert not mismatched, mismatched
    # #158's file occupies each original path (its live tests import those runners)
    for path in COLLIDED:
        assert (ROOT / path).read_bytes() == (ARCHIVE / "pr158-a832c73" / path).read_bytes(), path


def _rows(data: dict) -> dict:
    from greg.cognition import compiler as C
    return {r["method"]: r for r in C.candidates(data, C.CompetencyGeometry(), C.evidence_index())}


def test_frozen_negative_verdicts_from_pr155_change_the_compilers_routing():
    observations = _rows({"observations": [1, 2, 3, 40]})
    assert observations["cognition.pattern"]["status"] == "REJECTED"           # REJECTED on held-out seeds
    assert "frozen admission status REJECTED" in observations["cognition.pattern"]["rejected"]
    # review of #179 (M3): collective's REJECTED rested on an oracle baseline; against the deployable competitor it
    # tied, so the index's erratum routes it as EXPERIMENTAL (routable, never a DEFAULT)
    assert (observations["cognition.collective"]["status"], observations["cognition.collective"]["rejected"]) == \
        ("EXPERIMENTAL", None)
    assert "cognition.robust_pattern" not in observations                # ambiguous signature: never inferred
    simulate = _rows({"seed": 1, "samples": 10, "steps": 3, "step_probability": 0.5})
    assert simulate["cognition.simulation"]["rejected"]
    blackbox = _rows({"function": "sphere", "shift": [0.0], "bounds": [[-1, 1]], "budget": 100, "seed": 1})
    assert blackbox["cognition.blackbox"]["status"] == "SUPERSEDED" and blackbox["cognition.blackbox"]["rejected"]
    assert (blackbox["cognition.swarm"]["status"], blackbox["cognition.swarm"]["rejected"]) == \
        ("DEFAULT_FOR_GEOMETRY", None)
    crowd = _rows({"classes": ["a", "b"], "labels": [[0, 0, "a"]]})
    assert (crowd["cognition.crowd"]["status"], crowd["cognition.crowd"]["rejected"]) == ("EXPERIMENTAL", None)


def test_a_structural_label_changes_no_route():
    """ALIAS or SUPERSEDED_BY_CANONICAL_ORGAN is not a held-out verdict: the family routes as before."""
    rows = _rows({"factors": {"a": 2.0}})
    assert rows["cognition.estimation"]["status"] == "UNEVALUATED"


def test_the_genome_inventory_reads_the_index_the_compiler_routes_on():
    from greg.cognition import genome_library as lib
    from greg.cognition.compiler import evidence_index
    from greg.cognition.genomes import library
    index, genomes = evidence_index(), library.executables()
    entries = {e.genome_id: e for e in lib.inventory()}
    checked = 0
    for family, row in index["genomes"].items():
        if family in genomes and row.get("version") in (None, genomes[family].genome.version):
            entry = entries[f"cognition.{family}"]
            assert (entry.admission, entry.layer) == (row["status"], genomes[family].genome.layer), family
            checked += 1
    for family, row in index["operations"].items():
        if f"cognition.{family}" in entries:
            assert entries[f"cognition.{family}"].admission == lib.admission_of(family, index)[0]
            checked += 1
    assert checked >= 40
    assert lib.check() == []


def test_one_landlock_grant_path_covers_both_lineages_runtime_libraries():
    from greg import isolation
    assert not hasattr(isolation, "GLIBC_RUNTIME")
    pr158 = ("libc", "libm", "librt", "libdl", "libpthread", "libutil")
    assert {f"{name}.so*" for name in pr158} <= set(isolation.RUNTIME_LIBRARIES)


def test_every_founder_effect_destination_sits_on_the_one_backcast_gps():
    """PR #155's six destination backcasts are a view of greg/path.json horizons, never a second GPS."""
    from greg import path
    from greg.cognition.advantage import DESTINATIONS, backcast
    horizons = {h["id"]: h for h in path.load()["horizons"]}
    for destination in DESTINATIONS:
        assert destination.horizon in horizons, destination.expression
        assert backcast(destination)["horizon"] == destination.horizon
    assert len({d.horizon for d in DESTINATIONS}) == len(DESTINATIONS)


def test_archival_copies_carry_the_digests_the_source_manifest_records():
    import json
    manifest = json.loads((ROOT / "docs/collaboration/MIND-LINEAGE-SOURCE-MANIFEST-2026-10-14.json").read_text())
    assert "byte-identical archival copies" in manifest["archival_copies"]["label"]
    for row in manifest["frozen_path_collisions"]:
        for lineage, folder in (("pr155", "pr155-ef5f078"), ("pr158", "pr158-a832c73")):
            copy = ARCHIVE / folder / row["path"]
            assert hashlib.sha256(copy.read_bytes()).hexdigest() == row["lineages"][lineage]["sha256"], (folder, row["path"])


def test_inventory_applies_the_compilers_version_rule(monkeypatch):
    """Genome admission stays bound to the exact tested version in the inventory too: positive evidence measured at
    another version reads EXPERIMENTAL; negative evidence persists."""
    from greg.cognition import genome_library as lib
    from greg.cognition.genomes import library
    family, item = next((f, x) for f, x in library.executables().items())
    index = {"genomes": {family: {"status": "DEFAULT_FOR_GEOMETRY", "version": "0.0.0-other",
                                  "evidence": "x.json#genomes." + family}}, "operations": {}}
    status, raw, _ = lib.admission_of(family, index)
    assert status == "EXPERIMENTAL" and "stale" in raw
    index["genomes"][family]["status"] = "REJECTED"
    assert lib.admission_of(family, index)[0] == "REJECTED"
    index["genomes"][family].update(status="DEFAULT_FOR_GEOMETRY", version=item.genome.version)
    assert lib.admission_of(family, index)[0] == "DEFAULT_FOR_GEOMETRY"


def test_the_reconciliation_map_covers_every_file_either_lineage_changed():
    """One entry per file changed by either lineage since the merge base, each in the founder's closed vocabulary."""
    import json
    record = json.loads((ROOT / "docs/collaboration/MIND-LINEAGE-RECONCILIATION-MAP-2026-10-14.json").read_text())
    vocabulary = set(record["vocabulary"])
    assert vocabulary == {"complementary", "interchangeable", "semantic incompatibility", "duplicate",
                          "historical evidence", "unresolved"}
    paths = [e["path"] for e in record["entries"]]
    assert len(paths) == len(set(paths))
    assert all(e["classification"] in vocabulary and e["disposition"] and e["note"] for e in record["entries"])
    collided = {e["path"] for e in record["entries"] if e["classification"] == "semantic incompatibility"}
    assert collided == set(COLLIDED)
    heads = [record["base"], record["pr155"], record["pr158"]]
    if any(subprocess.run(["git", "cat-file", "-e", f"{c}^{{commit}}"], cwd=ROOT, capture_output=True,
                          timeout=30).returncode for c in heads):
        pytest.skip("git history does not hold the lineage heads: map coverage not verified on this checkout")
    changed = set()
    for head in heads[1:]:
        changed |= set(subprocess.run(["git", "diff", "--name-only", record["base"], head], cwd=ROOT,
                                      capture_output=True, text=True, timeout=60).stdout.split())
    assert set(paths) == changed
    # review of #179 (M18): the map, and this branch, carry #158's head named in the map
    assert subprocess.run(["git", "merge-base", "--is-ancestor", record["pr158"], "HEAD"], cwd=ROOT,
                          capture_output=True, timeout=60).returncode == 0
    # review of #179 (M20): a disposition says what the tree holds. "kept" and "selected:<lineage>" are that
    # lineage's bytes; "merged", "extended" and "modified" differ from them
    wrong = []
    for e in record["entries"]:
        disposition, lineage = e["disposition"], e["lineage"]
        source = disposition.split(":", 1)[1] if disposition.startswith("selected:") else lineage
        if source not in ("pr155", "pr158"):
            continue
        out = subprocess.run(["git", "show", f"{record[source]}:{e['path']}"], cwd=ROOT, capture_output=True,
                             timeout=60)
        theirs = out.stdout if out.returncode == 0 else None
        here = (ROOT / e["path"]).read_bytes() if (ROOT / e["path"]).exists() else None
        if (disposition == "kept" or disposition.startswith("selected:")) and here != theirs:
            wrong.append(f"{e['path']}: {disposition} but differs from {source}")
        if disposition in ("merged", "extended", "modified") and here == theirs:
            wrong.append(f"{e['path']}: {disposition} but identical to {source}")
    assert not wrong, "\n".join(wrong)
    original = ARCHIVE / "pr155-ef5f078" / "cortex/evaluation/evolution/run.py"
    assert hashlib.sha256(original.read_bytes()).hexdigest() == _git_blob_sha(record["pr155"],
                                                                                "cortex/evaluation/evolution/run.py")


def test_operation_verdicts_are_bound_to_the_solver_code_they_measured():
    """A positive #155 operation verdict routes only on the solver code it measured; once the code differs it
    routes as UNEVALUATED with the reason recorded, while negative evidence persists. Compiler and inventory agree."""
    import copy
    from greg.cognition import compiler as C
    from greg.cognition import genome_library as lib
    evidence = copy.deepcopy(C.evidence_index())
    # swarm: the positive verdict whose solver code is unchanged on the PR #184 merged tree (see the next test)
    assert C.operation_status("swarm", evidence["operations"]["swarm"]) == ("DEFAULT_FOR_GEOMETRY", None)
    evidence["operations"]["swarm"]["code"]["closure_sha256"] = "sha256:" + "1" * 64  # as if the solver changed
    status, why = C.operation_status("swarm", evidence["operations"]["swarm"])
    assert status == "UNEVALUATED" and "needs re-admission" in why
    assert lib.admission_of("swarm", evidence)[0] == "EXPERIMENTAL"
    evidence["operations"]["pattern"]["code"]["closure_sha256"] = "sha256:" + "2" * 64  # a REJECTED verdict persists
    assert C.operation_status("pattern", evidence["operations"]["pattern"]) == ("REJECTED", None)
    del evidence["operations"]["swarm"]["code"]                                       # unbound positive: not trusted
    assert C.operation_status("swarm", evidence["operations"]["swarm"])[0] == "UNEVALUATED"


def test_the_four_operation_verdicts_are_re_admitted_on_the_merged_solvers():
    """Joining this lineage with PR #184 brought #159's native-qualified solvers, so the 2026-10-14 control, game,
    information and probabilistic verdicts were measured on code that has since changed, and code binding routed them
    as UNEVALUATED (fourth review, R2: only each solver function changed; #159's helpers and the unchanged contracts
    functions they reach are newly reached members). Next-wave item 2 re-measured them once on the merged code,
    pre-registered at 462bd98 on fresh seeds 2600-2629: control, game and information DEFAULT_FOR_GEOMETRY;
    probabilistic did not replicate (EXPERIMENTAL). The 2026-10-14 verdicts stay in history and, read alone at the
    merged code, still need re-admission.

    Joined with Track B (#180-#189): operation admission v3 (2026-10-16, on the converged tree) sits between the two
    in each history, and the round-2 binding rule (review of #179, N4) applies. SOLVERS takes non-literal updates and
    the 462bd98 run recorded no runtime dispatch, so read alone its control, game and information verdicts, measured
    on exactly the joined closure, route as UNEVALUATED. The joined-tree re-admission (2026-10-22-joined-operations,
    pre-registered at 244b652c, frozen at 3520efe6, seeds 5920-5949) recorded the function SOLVERS held at runtime:
    control, game and information replicate DEFAULT_FOR_GEOMETRY and route; probabilistic reads NICHE_CAPABILITY
    (it did not replicate the 2026-10-21 EXPERIMENTAL) and routes as NICHE."""
    import json
    import sys
    from greg.cognition import compiler as C
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_mind_evidence_index as B
    run = "docs/evidence/greg-genome-admission/2026-10-21-operations/results.json"
    joined = "docs/evidence/greg-genome-admission/2026-10-22-joined-operations/results.json"
    v3 = "docs/evidence/greg-operation-admission/2026-10-16-v3/results-ops-v3.json"
    lineage = "docs/evidence/greg-genome-admission/2026-10-14/results.json"
    results, before = json.loads((ROOT / run).read_text()), json.loads((ROOT / lineage).read_text())
    rejoined = json.loads((ROOT / joined).read_text())
    assert results["pre_registered"] is True and results["source_commit"] == results["freeze_commit"]
    assert results["source_commit"].startswith("462bd98")
    assert "solver_closures" not in results          # the run recorded no runtime dispatch
    assert rejoined["pre_registered"] is True and rejoined["source_commit"] == rejoined["freeze_commit"]
    assert rejoined["source_commit"].startswith("3520efe6") and rejoined["seed_refusals"] == []
    index = C.evidence_index()
    solver = {"control": "control", "game": "game", "information": "information", "probabilistic": "bayesian"}
    expected = {"control": "DEFAULT_FOR_GEOMETRY", "game": "DEFAULT_FOR_GEOMETRY",
                "information": "DEFAULT_FOR_GEOMETRY", "probabilistic": "EXPERIMENTAL"}
    now_expected = {"control": "DEFAULT_FOR_GEOMETRY", "game": "DEFAULT_FOR_GEOMETRY",
                    "information": "DEFAULT_FOR_GEOMETRY", "probabilistic": "NICHE_CAPABILITY"}
    for family, want in expected.items():
        row = index["operations"][family]
        assert (row["evidence"], row["raw_status"]) == (f"{joined}#families.{family}", now_expected[family]), family
        assert [h["evidence"].partition("#")[0] for h in row["history"]][-4:] == [lineage, v3, run, joined], family
        assert results["families"][family]["status"] == want, family
        # both re-admissions measured the joined tree's solver closure exactly
        assert row["code"]["closure_sha256"] == C.solver_code(family)["closure_sha256"], family
        assert rejoined["solver_closures"][family]["function"] == solver[family], family
        assert row["code"]["dispatched"]["verified_at_runtime"] is True, family
        assert C.operation_status(family, row) == (now_expected[family], None), family
        assert C.family_status(family, index)["stale"] is None
        # the 462bd98 run read alone: a positive verdict binds only a confirmed dispatch (N4)
        alone = dict(row, status=want, raw_status=want, evidence=f"{run}#families.{family}",
                     code=B._measured_code(family, results["source_commit"]))
        status, why = C.operation_status(family, alone)
        if want == "EXPERIMENTAL":                    # inconclusive evidence persists with its scope
            assert (status, why) == (want, None), family
        else:
            assert status == "UNEVALUATED" and "recorded no runtime dispatch" in why, (family, why)
        # the earlier verdict, bound to the code it measured, still reads as stale at the merged code
        then = dict(row, status="DEFAULT_FOR_GEOMETRY", raw_status="DEFAULT_FOR_GEOMETRY",
                    code=B._measured_code(family, before["source_commit"]))
        status, why = C.operation_status(family, then)
        assert status == "UNEVALUATED" and "needs re-admission" in why, (family, why)
        # what changed in its closure (fourth review, R2), read as if its run had recorded a confirming runtime
        # dispatch, so the dispatch rule above does not report first (a fixture, not evidence)
        confirmed = {**then["code"], "dispatched": {**then["code"]["dispatched"], "verified_at_runtime": True}}
        status, why = C.operation_status(family, {**then, "code": confirmed})
        assert status == "UNEVALUATED" and "needs re-admission" in why, (family, why)
        changed = why.split("changed since: ", 1)[1].split(";", 1)[0]
        assert changed == f"greg/cognition/solvers.py::{solver[family]}", (family, why)
        added = why.split("added to the closure since: ", 1)[1].split(";", 1)[0]
        assert "greg/cognition/solvers.py::_native_source" in added and "contracts.py::canonical" in added, why


# ---------------------------------------------------------------- conflict (f): one intervention generator
OPERATORS_DIGEST = "7d481f6532d053aa5450340b3ec09a4e194dc1a834180bbbdb814fbfb7e7c7cd"   # historical, pinned
LEGAL = ("proof.evidence_preservation", "proof.confidential_review", "proof.authority_submission",
         "proof.public_publication")


def test_every_pr155_operator_has_a_canonical_foundry_mechanism_and_the_view_is_historical():
    """#158's Lawful Leverage Foundry is the one generator (it hard-filters, estimates and hands survivors to the
    ranker; #155's candidates stay UNESTIMATED and the ranker drops them). Every #155 operator maps to Foundry
    mechanisms: five to an existing primary, six to one ported template, and the accountability operator to four
    legal channels. #155's operator table is pinned, so it cannot evolve as a second generator."""
    import hashlib
    import json
    from dataclasses import asdict
    from foundry import lawful_leverage as L
    from greg.cognition import advantage as A
    assert set(A.FOUNDRY_MECHANISM) == {op.id for op in A.OPERATORS}
    targets = [m for ms in A.FOUNDRY_MECHANISM.values() for m in ms]
    assert set(targets) <= set(L.BY_ID) and len(targets) == len(set(targets)) == 15
    ported = {m: op for op, ms in A.FOUNDRY_MECHANISM.items() for m in ms if m not in L.PRIMARY.values()}
    assert ported == L.PORTED_FROM and len(set(ported.values())) == 7
    assert A.FOUNDRY_MECHANISM["accountable_transparency"] == LEGAL
    assert hashlib.sha256(json.dumps([asdict(o) for o in A.OPERATORS], sort_keys=True).encode()).hexdigest() \
        == OPERATORS_DIGEST, "the #155 operator table is historical: extend foundry.lawful_leverage instead"
    for op, ms in A.FOUNDRY_MECHANISM.items():   # a port never raises the operator's lawful-means consequence ceiling
        operator = next(o for o in A.OPERATORS if o.id == op)
        ceiling = max((A.CONSEQUENCE[m] for m in operator.means), key=A.RANK.index)
        assert all(L.CONSEQUENCE.index(L.BY_ID[m].consequence_class) <= L.CONSEQUENCE.index(ceiling) for m in ms), op


def test_one_evidentiary_standard_for_reviewed_and_ported_templates():
    """No lineage-specific priors or selection rules. A route resting on priors alone is labelled as such, cannot
    win the dominance branch over the direct-labour baseline, and ranks after any defensible route with observed
    evidence. Evidence keyed to a ported template's own id is enough to select it."""
    from foundry import lawful_leverage as L
    from tests.unit.test_lawful_leverage import H, problem
    assert not hasattr(L, "ENTRY")                                         # no floor prior for one lineage
    report = L.compile(problem())
    chosen = next(r for r in report["candidates"] if r["candidate_id"] == report["selected"])
    assert report["selection_basis"] == chosen["estimate"]["evidence_basis"]
    if report["selection_basis"] == "PRIOR_ONLY":
        assert "priors alone" in report["selection_basis_note"]
        assert "dominates" not in report["selection_rule"]
    # dominance over a defensible labour baseline must rest on observed evidence: even when every cheaper route's
    # prior-drawn samples beat the labour, a prior-only route is not chosen as dominating it
    import pytest
    mp = pytest.MonkeyPatch()
    mp.setattr(L, "_p_better", lambda xs, ys: (1.0, len(xs)))
    try:
        q = problem(evidence={})
        q["direct_labor"].update(cost_usd_per_cycle=0, effect=0.15, confidence=0.95, effort_hours_per_cycle=5,
                                 consequence_class="internal_write")
        forced = L.compile(q)
        assert any((r.get("vs_direct_labor") or {}).get("verdict") == "DOMINATES" for r in forced["candidates"])
        assert "dominates" not in forced["selection_rule"] and forced["selected"] == "direct_labor"
    finally:
        mp.undo()
    p = problem()
    p["evidence"]["workflow.remove_step"] = dict(successes=8, trials=10, refs=[H])
    lifted = L.compile(p)
    assert lifted["selected"].split(":")[0] == "workflow.remove_step"
    assert lifted["selection_basis"] == "OBSERVED_OUTCOMES" and lifted["selection_basis_note"] is None


def _with_incentives_and_settlement_consent(problem, consent, H):
    p = problem()
    settlement = next(s for s in p["surfaces"] if s["surface"] == "settlement")
    settlement["consent"] = consent("signed escrow terms", "payers")
    settlement["node"] = "proof_gap"                     # upstream of the bottleneck, so the pair is evaluable
    p["surfaces"].append(dict(surface="incentives", node="eligibility_check", state="flat fees", evidence_refs=[H],
                              third_parties=["participants"], consent=consent("fee agreement", "participants")))
    return p


def test_adding_a_mechanism_to_a_surface_erases_no_combination_and_inherits_nothing():
    """Regression for the one-mechanism-per-surface assumption (on e19226a ``_recombine`` keyed a dict by surface,
    so a second mechanism on a surface overwrote the first). Every recombinable pair across complementary surfaces
    is kept; the pairs that existed without the added templates come first and unchanged; each component keeps its
    own identity, surface record, evidence keys and consent check, so a combination inherits neither another
    mechanism's evidence nor its permission."""
    from foundry import lawful_leverage as L
    from tests.unit.test_lawful_leverage import H, consent, problem
    p = L.validate(_with_incentives_and_settlement_consent(problem, consent, H))
    base = L._instantiate(p)
    without = [x for x in base if x[0].mechanism_id not in L.PORTED_FROM]
    ids = lambda combos: [(t[0].mechanism_id, t[2].mechanism_id) for t in combos]  # noqa: E731
    before, after = ids(L._recombine(without)), ids(L._recombine(base))
    assert before and after[:len(before)] == before                         # nothing erased or reordered
    added = after[len(before):]
    assert ("incentives.regenerative_benefit", "settlement.milestone_escrow") in added
    assert not any(m in LEGAL for pair in after for m in pair)              # reports never combine with levers
    other = "sha256:" + "c" * 64
    q = _with_incentives_and_settlement_consent(problem, consent, H)
    q["evidence"]["incentives"] = dict(successes=9, trials=10, refs=[other])  # surface evidence: the primary's
    report = L.compile(q)
    rows = {r["candidate_id"]: r for r in report["candidates"]}
    primary_pair = "incentives.outcome_pricing+settlement.milestone_escrow"
    added_pair = "incentives.regenerative_benefit+settlement.milestone_escrow"
    assert rows[primary_pair]["eligibility"] == "ELIGIBLE"
    assert rows[primary_pair]["estimate"]["evidence_trials_by_channel"]["incentives.outcome_pricing"] == 10
    assert rows[added_pair]["eligibility"] == "REJECTED"                    # permission not inherited
    assert "incentives.regenerative_benefit:REJECTED_CONSENT_NOT_GIVEN_FOR:incentives.regenerative_benefit" \
        in rows[added_pair]["reasons"]
    assert L._evidence_keys("incentives.regenerative_benefit") == ("incentives.regenerative_benefit",)
    for i in report["interventions"]:                                        # evidence cited only where used
        uses = {k for part in i["id"].split("+") for k in L._evidence_keys(part)}
        assert (other in i["evidence_refs"]) == ("incentives" in uses), i["id"]


def test_consent_lawful_basis_and_execution_authority_are_separate():
    """Founder review 2026-10-15. Consent is purpose-bound and never a wildcard (absent, mismatched or revoked
    consent clears nothing, through mutation or recombination). It is not the definition of a lawful report: a
    subject's refusal does not remove the authority-submission channel. Every accountability channel needs a
    lawful basis that people establish; the Foundry establishes none, a problem cannot assert one, and the channel
    produces a legal-review request through the existing ask path, never an executable proposal."""
    import pytest
    from foundry import lawful_leverage as L
    from greg import asks
    from tests.unit.test_lawful_leverage import problem
    p = problem()
    p["surfaces"][0]["third_parties"] = ["payers", "the accused contractor"]  # the subject never consents
    report = L.compile(p)
    rows = {r["candidate_id"]: r for r in report["candidates"]}
    for cid in ("proof.evidence_preservation", "proof.confidential_review", "proof.authority_submission"):
        assert rows[cid]["eligibility"] == "ELIGIBLE", cid                 # refusal does not erase the channel
        assert rows[cid]["authority"]["state"] == "LEGAL_BASIS_REVIEW_REQUIRED"
        assert f"{cid}:consented" not in rows                              # consent is not its basis
    assert rows["proof.evidence_preservation"]["authority"]["consequence_class"] == "internal_write"
    plain = {x["candidate_id"]: x for x in L.compile(problem())["candidates"]}
    assert plain["proof.public_publication"]["reasons"] == ["REJECTED_CONSENT_NOT_GIVEN_FOR:proof.public_publication"]
    assert rows["proof.public_publication"]["eligibility"] == "REJECTED"
    packets = {k["evidence"]["candidate"]: k for k in report["legal_review_packets"]}
    assert set(packets) == {"proof.evidence_preservation", "proof.confidential_review", "proof.authority_submission"}
    for kwargs in packets.values():
        packet = asks.resource_request(**kwargs)
        asks.validate(packet)
        assert asks.screen(packet) == [] and packet["resource"] == "professional"
        assert "lawful" not in packet["recommendation"].replace("lawful basis", "")   # asserts no legality
    p["surfaces"][0]["consent"]["for_mechanisms"] = ["proof.public_publication"]
    rows = {r["candidate_id"]: r for r in L.compile(p)["candidates"]}
    assert rows["proof.public_publication"]["reasons"] == ["REJECTED_CONSENT_DOES_NOT_COVER:the accused contractor"]
    assert not any(c in r for r in rows for c in LEGAL if "+" in r)            # never recombined
    r = problem()                                                              # revoked consent: no wildcard
    r["surfaces"][0]["consent"]["revoked_at"] = "2026-10-07T00:00:00Z"
    rows = {x["candidate_id"]: x for x in L.compile(r)["candidates"]}
    for cid in ("proof.verifiable_receipts", "proof.verifiable_receipts:staged",
                "proof.verifiable_receipts:on_trigger"):
        assert rows[cid]["reasons"] == ["REJECTED_CONSENT_REVOKED"], cid
    combo = "proof.verifiable_receipts+eligibility.published_standard"
    assert "proof.verifiable_receipts:REJECTED_CONSENT_REVOKED" in rows[combo]["reasons"]
    assert rows["proof.authority_submission"]["eligibility"] == "ELIGIBLE"     # revocation does not erase a report
    bad = problem()
    bad["surfaces"][0]["consent"]["for_mechanisms"] = ["workflow.remove_step"]
    with pytest.raises(L.LeverageRefused, match="not a mechanism on that surface"):
        L.compile(bad)
    claim = problem()
    claim["lawful_basis"] = {"proof.authority_submission": "a model says this is lawful"}
    with pytest.raises(L.LeverageRefused):                                    # nothing in a problem asserts legality
        L.compile(claim)



def test_saturated_pool_admits_an_evidence_backed_ported_candidate_and_defers_the_rest_with_a_route():
    """With every surface declared the pool exceeds the 64-candidate contract ceiling. Observed evidence, not
    lineage, decides who is evaluated first; unevidenced candidates are deferred with a reason and a bounded
    sandbox route, and unevidenced reviewed templates keep their slots."""
    from foundry import lawful_leverage as L
    from tests.unit.test_lawful_leverage import H, consent, problem
    p = problem()
    nodes = {"proof": "proof_gap", "information": "payer_rules"}
    p["surfaces"] = [dict(surface=s, node=nodes.get(s, "eligibility_check"), state="declared", evidence_refs=[H],
                          consent=dict(consent("opt-in agreement", "participants"),
                                       for_mechanisms=[m for m in L.PORTED_FROM if L.BY_ID[m].surface == s]))
                     for s in L.SURFACES]
    next(s for s in p["surfaces"] if s["surface"] == "incentives")["third_parties"] = ["participants"]
    p["evidence"]["incentives.regenerative_benefit"] = dict(successes=12, trials=15, refs=[H])
    report = L.compile(p)
    evaluated = {r["candidate_id"] for r in report["candidates"]}
    deferred = {d["candidate_id"]: d for d in report["generated"]["deferred"]}
    assert deferred and set(deferred) == set(report["generated"]["not_evaluated_over_ceiling"])
    assert "incentives.regenerative_benefit" in evaluated                    # evidence gets it in
    row = next(r for r in report["candidates"] if r["candidate_id"] == "incentives.regenerative_benefit")
    assert row["estimate"]["evidence_basis"] == "OBSERVED_OUTCOMES"
    added = lambda cid: any(c.split(":")[0] in L.PORTED_FROM for c in cid.split("+"))  # noqa: E731
    assert all(d["reason"] == "OVER_CEILING_PRIOR_ONLY" for d in deferred.values())
    reviewed_dropped = [c for c in deferred if not added(c)]
    if reviewed_dropped:                                                       # a reviewed slot is lost only
        assert not any(added(c) and not c.startswith("incentives.regenerative_benefit") for c in evaluated)
    target = next(c for c in deferred if c.split(":")[0] == "workflow.remove_step")
    sandbox = L.evaluate_deferred(p, target)
    assert sandbox["candidate"]["candidate_id"] == target and sandbox["executes"] is False
    assert deferred[target]["evaluate_with"]["surfaces"] == ["workflow"]



def test_a_helper_or_configuration_change_invalidates_positive_admission():
    """Founder review 2026-10-15: entry-function binding missed helpers. A positive verdict is now bound to the
    solver's static dependency closure. Mutating a helper it calls (``contracts.number`` under ``graph``) or a
    module constant it reads (``repertoire.OBJECTIVES`` under ``swarm``) routes the family as UNEVALUATED and
    names the changed member; an unrelated solver's change does not; a REJECTED verdict keeps its scope; a
    verdict bound to the entry function only is not trusted. Local names that shadow module definitions are not
    dependencies."""
    import copy
    from greg.cognition import code_binding as CB
    from greg.cognition import compiler as C
    evidence = copy.deepcopy(C.evidence_index())

    def mutated(path, old, new):
        def read(p):
            text = CB.working_tree(p)
            if p == path:
                assert text.count(old) == 1, old
                text = text.replace(old, new)
            return text
        return read

    def status_with(family, read):
        now = C.solver_code(family)
        bound = CB.closure(now["path"], now["function"], read)
        mp = pytest.MonkeyPatch()
        mp.setattr(C, "solver_code", lambda f: {**now, "closure_sha256": bound["sha256"],
                                                "closure_members": bound["members"]} if f == family else None)
        try:
            return C.operation_status(family, evidence["operations"][family])
        finally:
            mp.undo()

    # the closure rule alone, apart from the competitor rule and from graph's measured status (operation admission
    # v3 reads EXPERIMENTAL): a positive fixture record bound to the measured closure
    graph = {**evidence["operations"]["graph"], "status": "DEFAULT_FOR_GEOMETRY",
             "competitor": "local Dijkstra (test fixture)"}
    evidence["operations"]["graph"] = graph
    assert C.operation_status("graph", graph) == ("DEFAULT_FOR_GEOMETRY", None)
    helper = CB.working_tree("greg/cognition/contracts.py")
    start = helper.index("def number(")
    line = helper[start:].splitlines()[1]
    status, why = status_with("graph", mutated("greg/cognition/contracts.py", line, line + "  # behaviour edit"))
    assert status == "UNEVALUATED" and "greg/cognition/contracts.py::number" in why
    status, why = status_with("swarm", mutated("greg/cognition/repertoire.py", "OBJECTIVES = {",
                                               "OBJECTIVES = {**{}, "))
    assert status == "UNEVALUATED" and "greg/cognition/repertoire.py::OBJECTIVES" in why
    source = CB.working_tree("greg/cognition/solvers.py")
    unrelated = source[source.index("def formal("):].splitlines()[1]
    assert status_with("graph", mutated("greg/cognition/solvers.py", unrelated, unrelated + "  # edit")) \
        == ("DEFAULT_FOR_GEOMETRY", None)                       # formal is not in graph's closure
    assert "greg/cognition/solvers.py::formal" not in C.solver_code("graph")["closure_members"]
    entry_only = {**evidence["operations"]["graph"], "code": {
        k: v for k, v in evidence["operations"]["graph"]["code"].items() if k not in ("closure_sha256",
                                                                                      "closure_members")}}
    status, why = C.operation_status("graph", entry_only)
    assert status == "UNEVALUATED" and "entry function only" in why
    assert C.operation_status("pattern", evidence["operations"]["pattern"]) == ("REJECTED", None)


def test_closure_follows_module_attributes_relative_imports_and_classes():
    """The resolver on a synthetic tree: ``import pkg.b as b`` then ``b.g()``, a relative ``from .c import K``,
    a class used by name; and a local that shadows a module function is not followed."""
    from greg.cognition.code_binding import closure
    tree = {"pkg/__init__.py": "",
            "pkg/a.py": "import pkg.b as b\nfrom .c import K\n\nclass Box:\n    def get(self):\n        return K\n\n"
                        "def unused():\n    return 0\n\ndef f(x, unused=None):\n    return b.g(x) + Box().get()\n",
            "pkg/b.py": "def g(x):\n    return x + 1\n",
            "pkg/c.py": "K = 3\n"}
    read = tree.get
    got = closure("pkg/a.py", "f", read)
    assert set(got["members"]) == {"pkg/a.py::f", "pkg/a.py::Box", "pkg/b.py::g", "pkg/c.py::K"}
    changed = closure("pkg/a.py", "f", {**tree, "pkg/b.py": "def g(x):\n    return x + 2\n"}.get)
    assert changed["sha256"] != got["sha256"]
    assert closure("pkg/a.py", "missing", read) is None


def test_f8_fallback_diagnostic_reproduces_from_the_frozen_rows_and_claims_nothing():
    """The diagnostic is a pure recombination of F8's frozen held-out rows: the frozen file is unchanged, the
    committed result is exactly what the script computes, the decomposition matches F8's own README, and the
    record is labelled diagnostic with its selection bias."""
    import hashlib
    import json
    from cortex.evaluation.pr155_f8_fallback_diagnostic import diagnose as D
    committed = json.loads(D.OUT.read_text())
    assert committed["frozen_source"]["sha256"] == "sha256:" + hashlib.sha256(D.FROZEN.read_bytes()).hexdigest()
    assert committed["status"] == "DIAGNOSTIC_ON_EXPOSED_DATA_NOT_A_CLAIM" and committed["selection_bias"]
    recomputed = D.diagnose(json.loads(D.FROZEN.read_text())["heldout"])
    assert {k: committed[k] for k in recomputed} == json.loads(json.dumps(recomputed))
    arms = committed["arms"]
    assert arms["unchanged (routed composition, standing-plan fallback)"]["total_cost"] == 656324
    assert arms["simpler ablation (EWMA ratio + quantile, then Erlang)"]["total_cost"] == 626736
    assert committed["fallbacks"] == 203 and sorted(committed["refusal_reasons_inferred"].values()) == [85, 118]
    draft = json.loads((D.ROOT / "cortex/evaluation/pr155_f8_fallback_diagnostic/prereg-draft.json").read_text())
    assert draft["status"].startswith("DRAFT_NOT_FROZEN") and "fresh held-out" in draft["data"]["requirement"]


def test_one_governed_path_from_problem_to_gate_proposal_and_receipt_keeps_consent_and_evidence_scoped(monkeypatch):
    """Founder review 2026-10-15, point 7, through the existing integration path (Goal Gravity): problem ->
    Foundry generation -> eligibility -> estimation -> institutional-leverage ranker -> CandidateProposals for
    the Consequence Gate -> receipt. Along the way a mechanism's consent and evidence stay its own; accountability
    channels become legal-review requests, never executable proposals; nothing is written or executed."""
    from foundry import lawful_leverage as L
    from greg import asks, gravity
    from tests.unit.test_greg_gravity import situation
    from tests.unit.test_greg_gravity import TRUSTED_NOW
    from tests.unit.test_lawful_leverage import H, consent, problem
    monkeypatch.setattr(gravity, "_utcnow", lambda: TRUSTED_NOW)            # the gravity suite's trusted clock
    other = "sha256:" + "c" * 64
    p = _with_incentives_and_settlement_consent(problem, consent, H)
    p["evidence"]["incentives"] = dict(successes=9, trials=10, refs=[other])
    result = gravity.step(situation(p))
    report = L.compile(gravity._clamped(p, gravity.signed_authority(None, None)))
    assert result["leverage"]["receipt_id"] == report["receipt_id"] and result["receipt_id"]
    assert result["leverage"]["selection_basis"] == report["selection_basis"]
    # consent: a mechanism never rides on consent given for another, on its own surface or in a combination
    rejected = result["leverage"]["rejected"]
    assert rejected["incentives.regenerative_benefit"] == [
        "REJECTED_CONSENT_NOT_GIVEN_FOR:incentives.regenerative_benefit"]
    eligible = {r["candidate_id"] for r in report["candidates"] if r["eligibility"] == "ELIGIBLE"}
    by_id = {i["id"]: i for i in report["interventions"]}
    proposals = result["gate"]["proposals"]
    assert result["gate"]["state"] == "PROPOSED_FOR_GATE" and proposals
    for prop in proposals:
        assert prop["intervention_id"] in eligible and prop["execution_authority"] == "none"
        refs = by_id[prop["intervention_id"]]["evidence_refs"]            # evidence: only what the estimate used
        uses = {k for part in prop["intervention_id"].split("+") for k in L._evidence_keys(part)}
        assert (other in refs) == ("incentives" in uses)
        payload = by_id[prop["intervention_id"]]["action"]["payload"]["lawful_leverage"]
        surfaces = {s["surface"]: s for s in p["surfaces"]}
        parts = [L.BY_ID[x.split(":")[0]].surface for x in prop["intervention_id"].split("+")
                 if x.split(":")[0] in L.BY_ID]
        if parts:                                                          # each component's own consent record
            assert payload["consent"] == [surfaces[s].get("consent") for s in parts]
    # accountability: a legal-review request through the one ask path, never an executable route
    legal = {a["evidence"]["candidate"]: a for a in result["legal_review_asks"]}
    assert "proof.authority_submission" in legal and "proof.public_publication" not in legal
    for ask in legal.values():
        asks.validate({k: v for k, v in ask.items() if k not in ("state", "record_with")})
        assert ask["state"] == "PREPARED_NOT_RECORDED" and ask["authority_requested"]["execution"].startswith("none")
    legal_rows = {r["candidate_id"] for r in report["candidates"]
                  if r["authority"]["state"] == "LEGAL_BASIS_REVIEW_REQUIRED"}
    assert set(legal) <= legal_rows
    if report["selected"] in legal_rows:
        assert result["disposition"] == "LEGAL_REVIEW"
    assert result["authority_created"] is False and result["ledger_writes"] == 0 and result["executes"] is False


# ---------------------------------------------------------------- review of PR #179, 2026-10-15 (H2, M16, M1, M2, H4)
class _Journal:
    def __init__(self):
        self.events = []

    def record(self, kind, payload, key=None):
        self.events.append((kind, payload))


def _genesis_offers(required_inputs, geometry):
    from greg import genesis as G
    from greg.cognition.cortex import registry_view
    journal = _Journal()
    found = G.Genesis(journal=journal, registry=registry_view(), workspace_root=ROOT / ".no-workspace")._genome_library(
        "deficit-review", {"required_inputs": required_inputs, "geometry": geometry, "inputs_known": True})
    return found, journal.events


def test_genesis_never_offers_a_rejected_or_superseded_operation_family():
    """H2: Genesis hard-coded UNEVALUATED for operation families, so it offered families the index marks REJECTED
    or SUPERSEDED as attach candidates. It now reads the compiler's one status function."""
    found, events = _genesis_offers(["observations"], None)
    assert "cognition.pattern" not in found                                     # REJECTED
    assert any(k == "genesis.route" and "cognition.pattern" in p["result"] and "REJECTED" in p["result"]
               for k, p in events)
    found, events = _genesis_offers(["function", "shift", "bounds", "budget", "seed"], None)
    assert "cognition.blackbox" not in found and "cognition.swarm" in found      # SUPERSEDED vs DEFAULT
    offered = {p["capability_id"]: p["admission_status"] for k, p in events if k == "deficit.awaiting_attach"}
    assert offered.get("cognition.swarm") == "DEFAULT_FOR_GEOMETRY"


def test_every_admission_surface_agrees_for_every_catalog_family():
    """M16: the compiler, Genesis, the inventory and mind_status read one status function over one index."""
    from greg.cognition import catalog, compiler as C
    from greg.cognition import genome_library as lib
    from scripts import mind_status
    index = C.evidence_index()
    entries = {e.genome_id: e for e in lib.inventory()}
    catalog_rows = {r["id"]: r for r in mind_status._catalog_families()}
    for family in catalog.FAMILIES:
        status = C.family_status(family, index)
        directive = lib.admission_of(family, index)[0]
        if status["stale"] or status["raw"] is None:
            assert directive == "EXPERIMENTAL", family
        elif status["kind"] == "operation":
            # the routed status, never the raw label (round-2 review of #179, N2: collective's erratum)
            assert directive == lib.STRUCTURAL.get(status["status"], status["status"]), family
        if f"cognition.{family}" in entries:
            assert entries[f"cognition.{family}"].admission == directive, family
        row = catalog_rows.get(f"cognition.{family}")
        if row is not None and row["executor"]:
            assert row["admission"] == status, family
            assert (status["raw"] is None) == ("no frozen held-out verdict" in row["basis"]), family
    assert not any(v == "SUPERSEDED" for v in lib.STRUCTURAL.values())         # structural labels never supersede


def test_operation_attach_asks_cite_their_frozen_evidence_and_superseded_rows_name_the_competitor():
    """M1: an operation family's attach ask carried only its status; a SUPERSEDED operation named no acquisition
    candidate."""
    from greg.cognition import compiler as C
    index = C.evidence_index()
    rows = {r["method"]: r for r in C.candidates({"function": "sphere", "shift": [0.0], "bounds": [[-1, 1]],
                                                   "budget": 100, "seed": 1}, C.CompetencyGeometry(), index)}
    assert rows["cognition.blackbox"]["superseded_by"]["mechanism"] == "multistart L-BFGS-B"
    best = {**rows["cognition.swarm"], "usable_why": "VERIFIED (registered, withheld)"}
    ask = C.attach_ask("review-ask", best, None, index)
    evidence = ask["evidence"]
    assert evidence["admission_evidence"].startswith(("docs/evidence/greg-genome-admission/",
                                                      "docs/evidence/greg-operation-admission/"))
    assert evidence["raw_status"] == "DEFAULT_FOR_GEOMETRY" and evidence["admission_history"]
    assert evidence["measured_code_closure"].startswith("sha256:") and "L-BFGS-B" in evidence["caveat"]


def test_the_mission_hook_never_recommends_a_composition_only_genome():
    """M2: the #155 mission hook ranked COMPOSITION_ONLY genomes as attach recommendations; the compiler rejects
    them as standalone decisions."""
    import inspect
    from greg import missions
    source = inspect.getsource(missions.MissionEngine._cognition_ask)
    order = source[source.index("order = ("):source.index(")", source.index("order = ("))]
    assert "COMPOSITION_ONLY" not in order and "DEFAULT_FOR_GEOMETRY" in order


def test_a_positive_operation_verdict_without_a_competitor_is_not_an_admission():
    """H4: micro, exact and sequential are DEFAULT against a baseline only (graph was too, until operation admission
    v3 read it EXPERIMENTAL). They route as UNEVALUATED until a re-admission names a competitor; verdicts with a
    competitor keep their status."""
    from greg.cognition import compiler as C
    index = C.evidence_index()
    for family in ("micro", "exact", "sequential"):
        status, why = C.operation_status(family, index["operations"][family])
        assert status == "UNEVALUATED" and "no competitor" in why, family
    assert C.operation_status("graph", index["operations"]["graph"]) == ("EXPERIMENTAL", None)
    # control, game, information and probabilistic are decided by next-wave item 2's re-admission on the PR #184
    # merged code, which ran after operation admission v3 (test_the_four_operation_verdicts_are_re_admitted...).
    for family in ("swarm", "robust_pattern"):
        assert C.operation_status(family, index["operations"][family]) == ("DEFAULT_FOR_GEOMETRY", None), family


# ---------------------------------------------------------------- review of PR #179, 2026-10-15 (H5 recipes, M15)
P8_SHIPPED = {"forecast_quantile": ("greg.cognition.genomes.forecasting", "DEFAULT_CONFIG"),
              "immune_detect": ("greg.cognition.genomes.collective", "IMMUNE_DEFAULT_CONFIG"),
              "constraint_release": ("greg.cognition.genomes.developmental", "CR_DEFAULT_CONFIG")}


def test_no_rejected_p8_configuration_is_shipped_and_every_incumbent_is_unchanged():
    """M15 / G8: for every frozen P8 cycle with decision REJECT, the shipped constant equals the cycle's incumbent and
    differs from its rejected candidate and every configuration its search evaluated."""
    import importlib
    import json
    records = sorted((ROOT / "docs/evidence/greg-protected-evolution").glob("*/cycle-*.json"))
    assert len(records) >= 4                       # cycles 1-3 and #158's cr-4 (under a committed freeze)
    for path in records:
        cycle = json.loads(path.read_text())
        if cycle["decision"] != "REJECT":
            continue
        module, name = P8_SHIPPED[cycle["target"]]
        shipped = getattr(importlib.import_module(module), name)
        incumbent = cycle["incumbent"]["config"]
        assert {k: shipped[k] for k in incumbent} == incumbent, path.name
        candidate = (cycle.get("candidate") or {}).get("config")
        assert candidate is None or {k: shipped.get(k) for k in candidate} != candidate, path.name
        for entry in cycle["search"].get("lineage") or []:
            config = entry.get("config") if isinstance(entry, dict) else None
            if config and config != incumbent:
                assert {k: shipped.get(k) for k in config} != config, path.name


def test_a_changed_default_configuration_makes_a_positive_genome_verdict_stale(monkeypatch):
    """M15: admission bound to a version string only; a shipped DEFAULT_CONFIG change at the same version kept the
    verdict. It now routes as UNEVALUATED, naming the changed configuration."""
    import copy
    from greg.cognition import code_binding as CB
    from greg.cognition import compiler as C
    index = copy.deepcopy(C.evidence_index())
    family = "forecast_quantile"
    assert C.family_status(family, index)["status"] in ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY")
    now = C.genome_code(family)
    source = CB.working_tree("greg/cognition/genomes/forecasting.py")
    edited = source.replace('"fit_window": 260', '"fit_window": 156', 1)
    assert edited != source
    mutated = CB.closure(now["entry"].split("::")[0], now["entry"].split("::")[1],
                         lambda p: edited if p == "greg/cognition/genomes/forecasting.py" else CB.working_tree(p))
    monkeypatch.setattr(C, "genome_code", lambda f: mutated if f == family else None)
    index["genomes"][family]["code"] = {"closure_members": now["members"]}
    status = C.family_status(family, index)
    assert status["status"] == "UNEVALUATED" and "DEFAULT_CONFIG" in status["stale"]


def test_recipe_lifts_bind_the_recipe_code_they_measured():
    """H5 (recipes): a recipe's lift binds the closure of the function that runs it and its RECIPES entry; a changed
    recipe routes as UNEVALUATED until re-measured; no lift persists; every indexed row records its binding."""
    import copy
    from greg.cognition import compiler as C
    index = C.evidence_index()
    assert all("code" in row for row in index["recipes"].values())
    # with the complete closure (review B2), every lift measured on a lineage's freeze commit is stale on the
    # converged tree: the compiler, composition and genesis it reaches have changed since. It routes as UNEVALUATED
    # until a fresh pre-registered run measures the converged Mind (record section 8). P6 converged v1 is that run
    # (record section 22): a live lift is one it measured, on the recipe code it measured. Joined with the #178/#184
    # trunk, that recipe code changed again: composition's stage runner and cortex.reason carry the caller's grant
    # window (COG-5), and #159's native-qualified solvers serve bayes_then_voi's information and probabilistic
    # stages. No lift routes on the joined tree until a pre-registered run measures the joined code
    converged = "docs/evidence/greg-composition-lift/2026-10-21-converged/"
    lifts = {r for r, v in index["recipes"].items() if v.get("lift") and v["evidence"].startswith(converged)}
    assert lifts == {"identify_then_optimize", "bayes_then_voi"}             # P6 converged v1's two lifts, indexed
    assert all("needs re-measurement" in C.recipe_stale(r, index["recipes"][r]) for r in lifts)
    live = {r for r, v in index["recipes"].items() if v.get("lift") and not C.recipe_stale(r, v)}
    assert live == set(), "a lift routes on code that differs from what it measured"
    assert all(index["recipes"][r]["evidence"].startswith(converged) for r in live), \
        "a lift routes on code that differs from what it measured"
    assert all(C.recipe_stale(r, v) for r, v in index["recipes"].items()
               if v.get("lift") and not v["evidence"].startswith(converged))
    honest = copy.deepcopy(index["recipes"]["track_then_staff"])
    honest["code"] = C.recipe_code("track_then_staff")                 # as if measured on today's code
    assert C.recipe_stale("track_then_staff", honest) is None
    changed = copy.deepcopy(index["recipes"]["track_then_staff"])
    changed["code"]["closure_sha256"] = "sha256:" + "3" * 64
    assert "needs re-measurement" in C.recipe_stale("track_then_staff", changed)
    unrecorded = {**index["recipes"]["track_then_staff"], "code": None}
    assert "not recorded" in C.recipe_stale("track_then_staff", unrecorded)
    rows = {r["method"]: r for r in C.candidates({"capacity_network": {"edges": [], "source": "s", "sink": "t",
                                                                        "budget": 1, "costs": {}}},
                                                  C.CompetencyGeometry(), index)}
    # graph_then_allocate's deciding verdict (P6 converged v1, F3) is no lift, and no lift persists like any negative
    # verdict, also where the joined tree has changed the recipe code: the recipe routes NO_LIFT and is demoted, never
    # stale
    row = rows["composition:graph_then_allocate"]
    assert row["status"] == "NO_LIFT" and "stale_evidence" not in row and row["demoted"]
    stale = copy.deepcopy(index)
    stale["recipes"]["graph_then_allocate"]["code"]["closure_sha256"] = "sha256:" + "3" * 64
    stale["recipes"]["graph_then_allocate"].update(lift=True, status="VPL_LIFT")
    rows = {r["method"]: r for r in C.candidates({"capacity_network": {"edges": [], "source": "s", "sink": "t",
                                                                        "budget": 1, "costs": {}}},
                                                  C.CompetencyGeometry(), stale)}
    row = rows["composition:graph_then_allocate"]
    assert row["status"] == "UNEVALUATED" and "re-measurement" in row["stale_evidence"]


def test_admitted_labels_are_reported_by_provenance_and_practitioner_ties_are_visible():
    """Review of #179 (H4, L11): rule admissions, lineage verdicts, recipe lifts and organ labels are not one
    admitted repertoire; and a recipe's practitioner tie reaches the compiler row and the inventory."""
    from greg.cognition import genome_library
    from greg.cognition.compiler import evidence_index
    entries = genome_library.inventory()
    split = genome_library.admitted_by_provenance(entries)["counts"]
    labelled = [e for e in entries if e.admission in ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY")]
    assert sum(split.values()) == len(labelled)
    for e in labelled:
        kind = genome_library.provenance(e)
        if kind == "rule_admitted":           # only pre-registered genome admissions count as admissions
            # any dated pre-registered genome admission (v1-v4 on 2026-10-1x, #158's v5 onward on 2026-10-2x)
            assert all(re.search(r"greg-genome-admission/2026-1\d-\d\d", r)
                       and not r.startswith(genome_library.LINEAGE_ADMISSION_DIR)
                       and not genome_library.OPERATION_READMISSION.match(r) for r in e.evidence_refs), e
        if kind == "operation_readmitted":    # a pre-registered re-admission run's own directory: the merged tree's
            # run_operations.py (<run id>-operations/) or the converged tree's operation-admission harness v3
            assert all(genome_library.OPERATION_READMISSION.match(r) for r in e.evidence_refs), e
            assert all("-operations/" in r or "greg-operation-admission/" in r for r in e.evidence_refs), e
        if e.source in ("composition_recipe", "cortex_organ"):
            assert kind in ("recipe_lift", "organ_label")
    row = evidence_index()["recipes"]["graph_then_allocate"]
    # P6 converged v1 decides (record section 22): no lift, the exact single genome ties it; F7's practitioner
    # tie stays in the recipe's history
    assert row["family"] == "F3" and row["status"] == "NO_LIFT" and row["prefer"] == "exact_single"
    f7 = next(v for v in row["history"] if v["family"] == "F7")
    assert f7["tied_by"] == ["parametric_min_cost_flow"]
    entry = next(e for e in entries if e.genome_id == "composition.graph_then_allocate")
    assert "exact_single" in entry.detail


def test_a_historical_result_that_its_runner_could_rewrite_is_pinned():
    """Review of #179 (L22): #155's developmental-sweep runner still runs at this head and writes its output with no
    existence guard. Its committed result is pinned here, so a rerun over it fails CI instead of passing silently."""
    path = ROOT / "docs/evidence/greg-developmental-sweep/2026-10-14/results.json"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == \
        "ea771ded75fac7ba5a04214bd26f31c5d6ac51fffea2090c65a235de1d12d80d"


# ---------------------------------------------------------------- closure-binding review (B1, B2)
def test_a_rebuilt_index_never_binds_a_function_its_run_did_not_call(monkeypatch):
    """B1: the builder took the family's solver from today's SOLVERS and bound that function's closure as
    measured, so a family re-pointed to another solver kept its positive verdict after a rebuild. The builder now
    resolves the dispatch at the run's commit, and a dispatch that changed routes as UNEVALUATED."""
    import importlib.util
    from greg.cognition import compiler as C
    from greg.cognition import solvers
    spec = importlib.util.spec_from_file_location("_builder_b1", ROOT / "scripts" / "build_mind_evidence_index.py")
    B = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(B)
    # a positive verdict whose solver code is unchanged on both lineages and on their join, and whose run recorded
    # the function SOLVERS held at runtime (operation admission v3)
    family = "swarm"
    record = dict(C.evidence_index()["operations"][family])
    commit = next(s["source_commit"] for s in C.evidence_index()["sources"]
                  if s["path"] == record["evidence"].partition("#")[0])
    if subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=ROOT, capture_output=True).returncode:
        pytest.skip("the measuring commit is not in this clone")
    runtime = (json.loads((ROOT / record["evidence"].partition("#")[0]).read_text()).get("solver_closures")
               or {}).get(family)                                     # the run's recorded runtime dispatch (N4)
    honest = B._measured_code(family, commit, runtime)
    function = honest["function"]
    assert function == C.solver_code(family)["function"] and honest["dispatched"].get("verified_at_runtime")
    assert C.operation_status(family, {**record, "code": honest})[0] == "DEFAULT_FOR_GEOMETRY"
    monkeypatch.setitem(solvers.SOLVERS, family, solvers.SOLVERS["graph"])            # a later re-pointing
    C.solver_code.cache_clear()
    try:
        rebuilt = B._measured_code(family, commit, runtime)
        status, why = C.operation_status(family, {**record, "code": rebuilt})
    finally:
        monkeypatch.undo()
        C.solver_code.cache_clear()
    assert rebuilt["function"] == function and rebuilt["dispatched"]["function"] == function
    assert status == "UNEVALUATED" and "now dispatches to" in why


B2_CASES = {
    "in-body import": ({"pkg/b.py": "def helper(x):\n    return x + 1\n",
                        "pkg/a.py": "def f(x):\n    from pkg.b import helper\n    return helper(x)\n"},
                       ("pkg/b.py", "return x + 1", "return x + 2")),
    "later subscript mutation": ({"pkg/a.py": "TABLE = {'i': 1}\nTABLE['j'] = 2\n\ndef f(k):\n    return TABLE[k]\n"},
                                 ("pkg/a.py", "{'i': 1}", "{'i': 9}")),
    "update call": ({"pkg/a.py": "TABLE = {}\nTABLE.update({'i': 1})\n\ndef f(k):\n    return TABLE[k]\n"},
                    ("pkg/a.py", "{'i': 1}", "{'i': 9}")),
    "global": ({"pkg/a.py": "LIMIT = 3\n\ndef f(x):\n    global LIMIT\n    LIMIT = LIMIT + x\n    return LIMIT\n"},
               ("pkg/a.py", "LIMIT = 3", "LIMIT = 4")),
    "dotted chain": ({"pkg/__init__.py": "", "pkg/b.py": "def helper(x):\n    return x + 1\n",
                      "pkg/a.py": "import pkg.b\n\ndef f(x):\n    return pkg.b.helper(x)\n"},
                     ("pkg/b.py", "return x + 1", "return x + 2")),
    "per-method locals": ({"pkg/a.py": "def scale(x):\n    return 2 * x\n\nclass C:\n    def g(self, scale):\n"
                                       "        return scale\n    def h(self, x):\n        return scale(x)\n\n"
                                       "def f(x):\n    return C().h(x)\n"},
                          ("pkg/a.py", "return 2 * x", "return 3 * x")),
}


@pytest.mark.parametrize("case", sorted(B2_CASES))
def test_each_static_closure_gap_now_changes_the_digest(case):
    """B2: six dependency forms the static closure dropped, so a behaviour-changing mutation left the digest
    unchanged. Each mutation now changes it."""
    from greg.cognition.code_binding import closure
    files, (path, old, new) = B2_CASES[case]
    mutated = {**files, path: files[path].replace(old, new, 1)}
    assert mutated[path] != files[path]
    before = closure("pkg/a.py", "f", files.get)
    after = closure("pkg/a.py", "f", mutated.get)
    assert before is not None and before["sha256"] != after["sha256"], (case, before["members"])


def test_the_dispatch_of_every_positive_operation_verdict_resolves_to_the_function_it_routes_to():
    from greg.cognition import compiler as C
    from greg.cognition.code_binding import dispatch
    for family, row in C.evidence_index()["operations"].items():
        if C.operation_status(family, row)[0] in ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY"):
            now = C.solver_code(family)
            assert row["code"]["dispatched"]["function"] == row["code"]["function"] == now["function"], family
            assert dispatch("greg/cognition/solvers.py", "SOLVERS", family)["function"] == now["function"], family


def test_collective_organs_and_derived_chains_read_one_status_on_every_surface():
    """Round-2 review of #179 (N2): collective read EXPERIMENTAL in the compiler and Genesis but REJECTED in the
    inventory, ``greg genomes`` and the mission hook; the hand-coded organ labels (z3 DEFAULT, fermi COMPOSITION_ONLY)
    and composition.derived (NICHE) disagreed with the compiler's UNEVALUATED. Every surface now reads the
    compiler's status, with the frozen or lineage label kept beside it."""
    from greg.cognition import compiler as C
    from greg.cognition import genome_library as lib
    index = C.evidence_index()
    entries = {e.genome_id: e for e in lib.inventory()}
    import copy
    lineage = copy.deepcopy(index)            # the lineage row as it stood: raw REJECTED, routed EXPERIMENTAL (erratum)
    row = lineage["operations"]["collective"]
    row.update(raw_status="REJECTED", status="EXPERIMENTAL")
    status = C.family_status("collective", lineage)
    assert status["raw"] == "REJECTED" and status["status"] == "EXPERIMENTAL"
    assert lib.admission_of("collective", lineage)[:2] == ("EXPERIMENTAL", "REJECTED")
    assert [h["status"] for h in index["operations"]["collective"]["history"]][:1] == ["REJECTED"]
    assert entries["cognition.collective"].admission == "EXPERIMENTAL"
    for name in lib.ORGAN_ADMISSION:
        key = next(k for k in entries if k.split("@")[0] == name and entries[k].source == "cortex_organ"
                   and entries[k].admission != "SUPERSEDED")
        routed, _ = C.organ_status(f"cognition.{name}", index)
        assert entries[key].admission == lib.STRUCTURAL.get(routed, routed), name
        assert "(not an admission)" in entries[key].detail, name
    assert entries["composition.derived"].admission == "EXPERIMENTAL"
    assert "routes UNEVALUATED" in entries["composition.derived"].detail
    assert lib.admitted_by_provenance()["counts"]["organ_label"] == 0


# ---------------------------------------------------------------- round-2 review of PR #179 (N4, N5)
N4_CASES = {
    "nested scope shadowing": ({"pkg/__init__.py": "", "pkg/a.py": "def scale(x):\n    return 2 * x\n\n"
                                "def f(x):\n    def g(scale):\n        return scale\n    return scale(x) + g(1)\n"},
                               ("pkg/a.py", "return 2 * x", "return 3 * x")),
    "comprehension shadowing": ({"pkg/__init__.py": "", "pkg/a.py": "def scale(x):\n    return 2 * x\n\n"
                                 "def f(xs):\n    ys = [scale for scale in xs]\n    return scale(len(ys))\n"},
                                ("pkg/a.py", "return 2 * x", "return 3 * x")),
    "helper inside top-level try": ({"pkg/__init__.py": "", "pkg/a.py": "try:\n    import json\n"
                                     "    def helper(x):\n        return x + 1\nexcept ImportError:\n"
                                     "    def helper(x):\n        return x\n\ndef f(x):\n    return helper(x)\n"},
                                    ("pkg/a.py", "return x + 1", "return x + 2")),
    "helper inside top-level if": ({"pkg/__init__.py": "", "pkg/a.py": "import sys\nif sys.version_info >= (3,):\n"
                                    "    LIMIT = 5\nelse:\n    LIMIT = 6\n\ndef f(x):\n    return min(x, LIMIT)\n"},
                                   ("pkg/a.py", "LIMIT = 5", "LIMIT = 7")),
    "top-level for mutation": ({"pkg/__init__.py": "", "pkg/a.py": "T = {'a': 1}\nfor k in ('b',):\n    T[k] = 2\n\n"
                                "def f(k):\n    return T[k]\n"}, ("pkg/a.py", "T[k] = 2", "T[k] = 3")),
    "top-level del mutation": ({"pkg/__init__.py": "", "pkg/a.py": "T = {'a': 1, 'b': 2}\ndel T['b']\n\n"
                                "def f(k):\n    return T.get(k)\n"}, ("pkg/a.py", "del T['b']", "del T['a']")),
    "star import": ({"pkg/__init__.py": "", "pkg/b.py": "def helper(x):\n    return x + 1\n",
                     "pkg/a.py": "from pkg.b import *\n\ndef f(x):\n    return helper(x)\n"},
                    ("pkg/b.py", "return x + 1", "return x + 2")),
    "import_module constant": ({"pkg/__init__.py": "", "pkg/b.py": "def helper(x):\n    return x + 1\n",
                                "pkg/a.py": "import importlib\n\ndef f(x):\n"
                                            "    m = importlib.import_module('pkg.b')\n    return m.helper(x)\n"},
                               ("pkg/b.py", "return x + 1", "return x + 2")),
}


@pytest.mark.parametrize("case", sorted(N4_CASES))
def test_each_round_two_closure_gap_now_changes_the_digest(case):
    """N4: nested-scope and comprehension shadowing, helpers and constants inside top-level try/if, top-level
    for/del mutation, star imports and constant import_module left the digest unchanged under a behaviour edit."""
    from greg.cognition.code_binding import closure
    files, (path, old, new) = N4_CASES[case]
    mutated = {**files, path: files[path].replace(old, new, 1)}
    assert mutated[path] != files[path]
    before, after = closure("pkg/a.py", "f", files.get), closure("pkg/a.py", "f", mutated.get)
    assert before is not None and before["sha256"] != after["sha256"], (case, before["members"])
    assert before["unresolved"] == [], case


def test_a_dynamic_import_or_a_non_literal_dispatch_update_binds_nothing_positive():
    """N4: a non-constant import_module and a comprehension-rebuilt dispatch table cannot be followed statically;
    a positive verdict bound to either routes as UNEVALUATED with the reason."""
    import copy
    from greg.cognition import compiler as C
    from greg.cognition.code_binding import closure, dispatch
    files = {"pkg/__init__.py": "", "pkg/a.py": "import importlib\n\ndef f(x, name):\n"
                                                 "    return importlib.import_module(name).helper(x)\n"}
    assert closure("pkg/a.py", "f", files.get)["unresolved"]
    table = {"pkg/__init__.py": "", "pkg/s.py": "def a():\n    return 1\n\ndef b():\n    return 2\n\n"
                                                "T = {'k': a}\nT.update({k: b for k in ('k',)})\n"}
    assert dispatch("pkg/s.py", "T", "k", table.get)["unresolved_updates"] == 1
    index = C.evidence_index()
    positive = next(f for f, r in index["operations"].items()
                    if C.operation_status(f, r)[0] in ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY"))
    row = copy.deepcopy(index["operations"][positive])
    assert row["code"]["dispatched"].get("verified_at_runtime") is True   # the v3 run recorded its runtime dispatch
    row["code"]["dispatched"] = {**row["code"]["dispatched"], "unresolved_updates": 1}
    assert C.operation_status(positive, row)[0] in ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY")
    row["code"]["dispatched"].pop("verified_at_runtime")                # a run with no runtime record
    status, why = C.operation_status(positive, row)
    assert status == "UNEVALUATED" and "non-literal update" in why
    row = copy.deepcopy(index["operations"][positive])
    row["code"]["closure_unresolved"] = ["pkg/a.py::f: dynamic import with a non-constant module name"]
    status, why = C.operation_status(positive, row)
    assert status == "UNEVALUATED" and "dynamic import" in why


def test_a_recipe_binds_the_function_its_run_called_and_stops_at_cortex_reason(monkeypatch):
    """N5: recipe_code resolved the function from today's OPERATION_RECIPES (re-pointing bound a function the run
    never called), and its closure reached through cortex.reason into the compiler (568 members; a docstring edit in
    code_binding staled an honest verdict). It now resolves at the measured tree and stops at the boundary."""
    from greg.cognition import code_binding as CB
    from greg.cognition import compiler as C
    from greg.cognition import composition
    now = C.recipe_code("forecast_then_staff")
    assert now["function"].endswith("::_forecast_then_staff")
    assert not any(k.startswith(("greg/cognition/compiler.py", "greg/cognition/code_binding.py"))
                   for k in now["closure_members"])
    assert set(C.RECIPE_BOUNDARY) & set(now["closure_members"])           # hashed, not followed
    monkeypatch.setitem(composition.OPERATION_RECIPES, "forecast_then_staff", composition.OPERATION_RECIPES[
        "track_then_staff"])                                             # a later in-memory re-pointing
    assert C.recipe_code("forecast_then_staff")["function"] == now["function"]   # the tree decides, not the dict

    def edited(path):
        text = CB.working_tree(path)
        if path == "greg/cognition/code_binding.py":
            text = text.replace('def working_tree(path: str) -> str | None:\n',
                                'def working_tree(path: str) -> str | None:\n    """A docstring edit."""\n', 1)
        return text
    assert C.recipe_code("forecast_then_staff", edited)["closure_sha256"] == now["closure_sha256"]


def test_a_synthetic_retain_record_changes_no_shipped_configuration(tmp_path):
    """L9 (round-2 review: the cited test did not exist). P8 only proposes: a RETAIN record written through P8's own
    record path changes no shipped default configuration, and no runtime module applies a P8 proposal."""
    import importlib
    from greg.cognition import evolution
    before = {name: copy_of(module, constant) for name, (module, constant) in P8_SHIPPED.items()}
    target = evolution.cr_target()
    candidate = {**target.incumbent, "p_restart": 0.5 if target.incumbent.get("p_restart") != 0.5 else 0.25}
    assert candidate != target.incumbent                       # a real configuration change (round-3 review, L9)
    record = {"decision": "RETAIN", "incumbent": {"id": evolution.config_id(target.incumbent)},
              "proposal": {"state": "PROPOSED_NOT_APPLIED", "change": {
                  "module": "greg.cognition.genomes.developmental", "constant": "CR_DEFAULT_CONFIG",
                  "from": target.incumbent, "to": candidate}}}
    shipped = {m: hashlib.sha256(Path(importlib.import_module(m).__file__).read_bytes()).hexdigest()
               for m, _ in P8_SHIPPED.values()}
    written = evolution._finish(record, tmp_path / "cycle-synthetic.json")
    assert written["authority_created"] is False and (tmp_path / "cycle-synthetic.json").exists()
    sources = shipped
    assert {name: copy_of(module, constant) for name, (module, constant) in P8_SHIPPED.items()} == before
    assert sources == {m: hashlib.sha256(Path(importlib.import_module(m).__file__).read_bytes()).hexdigest()
                       for m in sources}                       # the shipped source files are untouched
    for root in ("greg", "cortex", "foundry"):                     # nothing applies a proposal at runtime
        for path in (ROOT / root).rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            assert "setattr(" not in text or "PROPOSED_NOT_APPLIED" not in text, path
            if path.name != "evolution.py":
                assert "PROPOSED_NOT_APPLIED" not in text, path


def copy_of(module: str, constant: str):
    import copy
    import importlib
    return copy.deepcopy(getattr(importlib.import_module(module), constant))


def test_a_split_string_literal_naming_the_alternative_controller_is_caught():
    """L7 residual: ``'greg.cognition.' + 'evolution_' + 'routing'`` passed the textual scan. Stated limit (round-3
    review): a static scan cannot follow names built at runtime (variables, ``%`` formatting, slicing); the
    runtime guarantee is that ``evolution_routing`` is never imported by a runtime module, checked here statically
    for every form that folds to a constant."""
    for source in ("import importlib\nm = importlib.import_module('greg.cognition.' + 'evolution_' + 'routing')\n",
                   "name = ''.join(['greg.cognition.', 'evolution_', 'routing'])\n",
                   "x = 'evolution_'\nname = f'{\"evolution_\"}routing'\n"):
        assert any("evolution_routing" in v for v in _folded_strings(ast.parse(source))), source


# ---------------------------------------------------------------- round-3 re-verification of PR #179
def test_a_stage_solver_change_stales_its_recipe_binding():
    """Finding 1: the recipe closure stops at cortex.reason, so an edit inside a stage genome (Erlang C under
    track_then_staff) left the recipe digest unchanged. Every genome that can serve a stage operation is bound."""
    from greg.cognition import code_binding as CB
    from greg.cognition import compiler as C
    now = C.recipe_code("track_then_staff")
    assert {"queue_erlang", "basal_kalman"} <= set(now["stage_closures"])

    def edited(path):
        text = CB.working_tree(path)
        if path == "greg/cognition/genomes/solvers_b.py":
            head = "def erlang_solve("
            start = text.index(head)
            body = text.index("\n", text.index("):", start)) + 1
            text = text[:body] + "    _behaviour_edit = 1\n" + text[body:]
        return text
    changed = C.recipe_code("track_then_staff", edited)
    assert changed["stage_closures"]["queue_erlang"] != now["stage_closures"]["queue_erlang"]
    assert changed["closure_sha256"] == now["closure_sha256"]        # the recipe's own code is unchanged
    verdict = {"code": {k: changed[k] for k in ("closure_sha256", "recipe_entry_sha256", "stage_closures")}}
    assert C.recipe_stale("track_then_staff", verdict) is not None


ROUND3_DISPATCH = {
    "for-loop rebind": "for _k in ('control',):\n    T[_k] = b\n",
    "augmented update": "T |= {'control': b}\n",
    "pop and setdefault": "T.pop('control')\nT.setdefault('control', b)\n",
    "mutating helper": "def _patch():\n    T['control'] = b\n\n_patch()\n",
    "if-block rebind": "if True:\n    T['control'] = b\n",
    "__setitem__": "T.__setitem__('control', b)\n",
}


@pytest.mark.parametrize("case", sorted(ROUND3_DISPATCH))
def test_every_other_touch_of_a_dispatch_table_is_unresolved(case):
    """Finding 2: these forms were read with unresolved_updates 0, so a static binding could name a function the
    table no longer holds."""
    from greg.cognition.code_binding import dispatch
    text = "def a():\n    return 1\n\ndef b():\n    return 2\n\nT = {'control': a}\n" + ROUND3_DISPATCH[case]
    got = dispatch("pkg/s.py", "T", "control", {"pkg/__init__.py": "", "pkg/s.py": text}.get)
    assert got["unresolved_updates"] >= 1, (case, got)


def test_a_runtime_dispatch_that_disagrees_binds_nothing():
    """Finding 2: a recorded runtime dispatch that disagreed with the static reading was ignored."""
    import copy
    from greg.cognition import compiler as C
    index = C.evidence_index()
    # swarm: a positive verdict whose run recorded its runtime dispatch (control's deciding run, on the joined tree,
    # is next-wave item 2's, which recorded none: test_the_four_operation_verdicts_are_re_admitted...)
    family = "swarm"
    row = copy.deepcopy(index["operations"][family])
    assert C.operation_status(family, row)[0] == "DEFAULT_FOR_GEOMETRY"
    assert row["code"]["dispatched"]["verified_at_runtime"]
    row["code"]["dispatched"] = {k: v for k, v in row["code"]["dispatched"].items() if k != "verified_at_runtime"}
    row["code"]["dispatched"]["runtime_disagrees"] = {"path": "greg/cognition/solvers.py", "function": "game"}
    status, why = C.operation_status(family, row)
    assert status == "UNEVALUATED" and "at runtime" in why


# ---------------------------------------------------------------- round-4 re-verification of PR #179
def test_operation_family_and_organ_stages_are_bound_into_their_recipes():
    """Finding A: stages served through SOLVERS (bayes_then_voi's information and probabilistic,
    graph_then_allocate's optimize) and the template recipes' cortex-organ stages were unbound."""
    from greg.cognition import code_binding as CB
    from greg.cognition import compiler as C
    from greg.cognition.composition import RECIPES
    for recipe in RECIPES:
        stages = C.recipe_code(recipe)["stage_closures"]
        assert stages and all(v is not None for v in stages.values()), (recipe, stages)
    now = C.recipe_code("bayes_then_voi")
    assert {"solvers:information", "solvers:probabilistic"} <= set(now["stage_closures"])

    def edited(path):
        text = CB.working_tree(path)
        if path == "greg/cognition/solvers.py":
            start = text.index("def information(")
            body = text.index("\n", text.index("):", start)) + 1
            text = text[:body] + "    _behaviour_edit = 1\n" + text[body:]
        return text
    changed = C.recipe_code("bayes_then_voi", edited)
    assert changed["stage_closures"]["solvers:information"] != now["stage_closures"]["solvers:information"]
    verdict = {"code": {k: changed[k] for k in ("closure_sha256", "recipe_entry_sha256", "stage_closures")}}
    assert C.recipe_stale("bayes_then_voi", verdict) is not None
    for recipe in ("estimate_then_optimize", "identify_then_optimize"):
        assert any(k.startswith("organ:") for k in C.recipe_code(recipe)["stage_closures"]), recipe


ROUND4_DISPATCH = {
    "pop assigned": "_ = T.pop('control')\n", "setdefault assigned": "_ = T.setdefault('control', b)\n",
    "alias": "_t = T\n_t['control'] = b\n", "helper taking the table": "def h(t):\n    t['control'] = b\n\nh(T)\n",
    "dict.update": "dict.update(T, control=b)\n", "dict.__setitem__": "dict.__setitem__(T, 'control', b)\n",
    "globals": "globals()['T']['control'] = b\n", "lambda helper": "f = lambda: T.update(control=b)\nf()\n",
    "class body": "class C:\n    T['control'] = b\n", "list display": "[T.update(control=b)]\n",
    "assert": "assert T.update(control=b) is None\n", "map": "list(map(T.__setitem__, ['control'], [b]))\n",
}


@pytest.mark.parametrize("case", sorted(ROUND4_DISPATCH))
def test_any_other_statement_naming_a_dispatch_table_is_unresolved(case):
    """Finding B: dispatch() fails closed: any module-level statement outside the recognised literal forms that
    names the table, as a name or a string, counts as an unresolved update."""
    from greg.cognition.code_binding import dispatch
    text = "def a():\n    return 1\n\ndef b():\n    return 2\n\nT = {'control': a}\n" + ROUND4_DISPATCH[case]
    got = dispatch("pkg/s.py", "T", "control", {"pkg/__init__.py": "", "pkg/s.py": text}.get)
    assert got["unresolved_updates"] >= 1, (case, got)
    clean = dispatch("pkg/s.py", "T", "control", {"pkg/__init__.py": "", "pkg/s.py": text.split("T = {")[0] +
                                                  "T = {'control': a}\nT['other'] = b\n"}.get)
    assert clean["unresolved_updates"] == 0 and clean["function"] == "a"



ROUND5_DISPATCH = {
    "update keywords": "T.update({}, control=b)\n", "update double star": "T.update({}, **{'control': b})\n",
    "pop inside a literal assignment": "T['j'] = T.pop('control') and b\n",
    "setitem inside a literal assignment": "T['j'] = (T.__setitem__('control', b), a)[1]\n",
    "helper inside a literal assignment": "def h(t):\n    t['control'] = b\n\nT['j'] = h(T)\n",
    "globals keyword": "globals().update(T={'control': b})\n",
    "module attribute": "import sys\nsys.modules[__name__].T['control'] = b\n",
    "entry attribute": "T['control'].__code__ = b.__code__\n",
}


@pytest.mark.parametrize("case", sorted(ROUND5_DISPATCH))
def test_round5_dispatch_forms_are_unresolved(case):
    """Round-5 review of #179 (N5): these forms still read unresolved_updates 0 with the stale function."""
    from greg.cognition.code_binding import dispatch
    text = "def a():\n    return 1\n\ndef b():\n    return 2\n\nT = {'control': a}\n" + ROUND5_DISPATCH[case]
    got = dispatch("pkg/s.py", "T", "control", {"pkg/__init__.py": "", "pkg/s.py": text}.get)
    assert got["unresolved_updates"] >= 1, (case, got)


def test_recipe_bindings_cover_the_runtime_adapter_every_solvers_statement_and_the_route_policy():
    """Round-5 review of #179 (N4): stages run through solvers._genome_solver and library.run, not the bound solve;
    a comprehension appended to SOLVERS rerouted a stage without changing any bound closure; the route policy and
    the organ set were unbound or a hand copy. Each edit below now stales the recipe."""
    from greg.cognition import code_binding as CB
    from greg.cognition import compiler as C

    def edit(target, needle, insert):
        def read(path):
            text = CB.working_tree(path)
            if path == target:
                at = text.index("\n", text.index(needle)) + 1
                text = text[:at] + insert + text[at:]
            return text
        return read

    def stale(recipe, read):
        changed = C.recipe_code(recipe, read)
        verdict = {"code": {k: changed[k] for k in ("closure_sha256", "recipe_entry_sha256", "stage_closures")}}
        return C.recipe_stale(recipe, verdict)

    assert stale("track_then_staff", edit("greg/cognition/genomes/library.py", "def run(", "    _edit = 1\n"))
    def appended(p):
        text = CB.working_tree(p)
        if p == "greg/cognition/solvers.py":
            text += "\nSOLVERS.update({k: v for k, v in [('information', SOLVERS['bayesian'])]})\n"
        return text
    assert stale("bayes_then_voi", appended)
    assert stale("identify_then_optimize", edit("cortex/routing.py", "def _route_parts(", "    _edit = 1\n"))
    for organ in ("cortex/organs/semantic.py", "cortex/organs/schedule_extraction.py"):
        def read(p, o=organ):
            return _edit_first_method(CB.working_tree(p)) if p == o else CB.working_tree(p)
        assert stale("estimate_then_optimize", read), organ


def _edit_first_method(text: str) -> str:
    import re
    m = re.search(r"\n    def [^\n]*:\n", text)
    return text[:m.end()] + "        _edit = 1\n" + text[m.end():]


def test_the_committed_evidence_index_is_what_the_builder_produces(tmp_path, monkeypatch):
    """Round-5 review of #179 (N3): the committed index was not byte-reproducible (stale unresolved_updates) and no
    test checked it. Rebuilding into a temporary path must reproduce the committed bytes."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("bmei", ROOT / "scripts/build_mind_evidence_index.py")
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    out = tmp_path / "index.json"
    monkeypatch.setattr(builder, "OUT", out)
    monkeypatch.setattr("sys.argv", ["build_mind_evidence_index.py"])
    builder.main()
    assert out.read_bytes() == (ROOT / "docs/evidence/greg-mind-evidence-index.json").read_bytes(), \
        "the committed evidence index is stale: run PYTHONPATH=. python scripts/build_mind_evidence_index.py"


def test_adding_an_unrelated_genome_module_does_not_stale_a_genome_stage_recipe():
    """The genome registry tuple decides only which genome serves a family; each stage family is bound by its own
    solve closure. A new module stales nothing it cannot reach, while a change to the adapter itself still does."""
    from greg.cognition import code_binding as CB
    from greg.cognition import compiler as C
    now = C.recipe_code("bayes_then_voi")

    def added(p):
        text = CB.working_tree(p)
        if p == "greg/cognition/genomes/library.py":
            text = text.replace("MODULES = (", "MODULES = (\n    \"greg.cognition.genomes.unrelated\",", 1)
        return text
    assert C.recipe_code("bayes_then_voi", added)["stage_closures"] == now["stage_closures"]

    def changed(p):
        text = CB.working_tree(p)
        if p == "greg/cognition/genomes/library.py":
            at = text.index("\n", text.index("def run(")) + 1
            text = text[:at] + "    _edit = 1\n" + text[at:]
        return text
    assert C.recipe_code("bayes_then_voi", changed)["stage_closures"]["adapter:run"] != now["stage_closures"]["adapter:run"]
