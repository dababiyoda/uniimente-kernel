"""The Mind evidence index cites frozen files by digest: recompute every digest and every cited verdict.

docs/evidence/greg-mind-evidence-index.json is what the Competency Compiler routes on and what
scripts/mind_status.py labels from. This test recomputes, with its own code (hashlib and a pointer walk, never
scripts/build_mind_evidence_index.py):

* the sha256 of every listed source. A source absent from the checkout fails, naming every absent path and
  whether the clone is shallow; a shallow clone still holds every file of its commit, so absence is a defect;
* every genome, recipe, routing and operation row against the file and pointer it cites, every genome history
  entry against its own admission run and every operation history entry against its own file; every cited
  file must be a listed, digested source;
* that the index is complete and current: every frozen admission, P6 and P4 run on disk is a listed source, every
  family with a status in any admission run has a row that cites the latest run containing it (ordered by each
  run's own ``finished_at``) with a history of every run, in order, and every P6 family's recipe likewise; a later
  frozen run replaces an earlier one, never the reverse;
* the derived fields the compiler routes on beyond status and version: ``median_seconds`` (a tie-break),
  ``subregions_vs_competitor`` (it orders fits FAVOURED / NEUTRAL / DOMINATED) and ``competitor``;
* every ``external_verification`` entry: it must cite a listed, digested source whose value records a verified
  external outcome for that mechanism (at the row's version, or with the code digest it verified), and it may sit
  only on a positive frozen record (admitted, VPL_LIFT or GAIN): it never overrides a refutation or demotion;
* that every source names a source commit present in this repository. A shallow clone may not hold a commit
  outside its fetched depth: those commits are then reported by an explicit skip (``pytest -rs``), never passed.

Not verified: that a frozen run reproduces (its own harness re-runs it) or that the source commit is the code
that produced the file (the harness records that inside the file).
"""
from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / "docs" / "evidence" / "greg-mind-evidence-index.json"
ADMISSION = "docs/evidence/greg-genome-admission"
# held-out verdicts measured against a competitor; any other admission label is structural and must not route
MEASURED = ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY", "COMPOSITION_ONLY", "EXPERIMENTAL", "SUPERSEDED", "REJECTED")
P6 = "docs/evidence/greg-composition-lift"
P4 = "docs/evidence/greg-learned-routing"
POSITIVE = ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY")
# The recipe each frozen P6 family measured (from each run's README and development record, written here rather
# than read from the index builder's table). A family a new run adds must be named here before the test passes.
P6_RECIPE = {"F1": "estimate_then_optimize", "F2": "identify_then_optimize", "F2R": "identify_then_optimize",
             "F3": "graph_then_allocate", "F4": "bayes_then_voi", "F5": "forecast_then_allocate",
             "F6": "forecast_then_staff", "F7": "graph_then_allocate", "F2b": "identify_then_optimize"}
# Frozen P6 families that measure no composition recipe (PR #155 lineage): named so a new one cannot slip past.
P6_NOT_A_RECIPE = {"X1": "cortex multi-organ route (Z3 + Fermi)", "X2": "cortex schedule-extraction pipeline"}


def _index() -> dict:
    return json.loads(INDEX.read_text())


def _shallow() -> bool | None:
    """True or False from git; None when git history is not available at all."""
    try:
        out = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT, capture_output=True,
                             text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return None if out.returncode else out.stdout.strip() == "true"


def test_every_listed_source_recomputes_to_its_recorded_sha256():
    sources = _index()["sources"]
    assert sources, "the index lists no frozen sources"
    absent, changed = [], []
    for source in sources:
        file = ROOT / source["path"]
        if not file.is_file():
            absent.append(source["path"])
        elif "sha256:" + hashlib.sha256(file.read_bytes()).hexdigest() != source["sha256"]:
            changed.append(source["path"])
    assert not absent, (f"index sources absent from this checkout (shallow clone: {_shallow()}); a shallow clone "
                        f"still has every file of its commit, so these are missing, not unfetched: {absent}")
    assert not changed, f"frozen sources changed after the index was built (rebuild or restore): {changed}"
    assert len({s['path'] for s in sources}) == len(sources), "a source is listed twice"


def _cite(ref: str, listed: set, problems: list):
    """'path#a.b' -> the value at keys a, b of that JSON file; records why when it cannot."""
    rel, _, fragment = ref.partition("#")
    if rel not in listed:
        problems.append(f"{ref}: cites a file that is not a listed, digested source")
        return None
    try:
        value = json.loads((ROOT / rel).read_bytes().decode("utf-8"))
    except (OSError, ValueError, RecursionError):         # a listed README or log, or an unreadable file
        problems.append(f"{ref}: not a readable JSON source")
        return None
    for key in fragment.split(".") if fragment else []:
        if not isinstance(value, dict) or key not in value:
            problems.append(f"{ref}: pointer does not resolve at {key!r}")
            return None
        value = value[key]
    return value


def _recipe_verdict(cited: dict) -> dict:
    lift = bool(cited["lift"])
    return {"lift": lift, "status": "VPL_LIFT" if lift else "NO_LIFT", "wins": cited["routed_wins"],
            "losses": cited["routed_losses"], "p_one_sided": cited["sign_test_p_one_sided"],
            "prefer": None if lift else cited["best_constituent"]}


def test_every_cited_verdict_matches_the_source_it_cites():
    index = _index()
    listed = {s["path"] for s in index["sources"]}
    problems = []
    for family, row in index["genomes"].items():
        cited = _cite(row["evidence"], listed, problems)
        if cited is not None and (cited.get("status"), cited.get("version")) != (row["status"], row.get("version")):
            problems.append(f"{family}: index {row['status']}@{row.get('version')} but source "
                            f"{cited.get('status')}@{cited.get('version')}")
        history = row.get("history") or []
        if not history or (history[-1]["status"], history[-1]["version"]) != (row["status"], row.get("version")):
            problems.append(f"{family}: the latest history entry must be the deciding run")
        for entry in history:
            run = _cite(f"{ADMISSION}/{entry['run']}/results.json#genomes.{family}", listed, problems)
            if run is not None and (run.get("status"), run.get("version")) != (entry["status"], entry["version"]):
                problems.append(f"{family}: history {entry} disagrees with its run")
    for recipe, row in index["recipes"].items():
        for verdict in [row, *row.get("history", [])]:
            cited = _cite(verdict["evidence"], listed, problems)
            if cited is None:
                continue
            expected = _recipe_verdict(cited)
            observed = {k: verdict.get(k) for k in expected}
            if observed != expected:
                problems.append(f"recipe {recipe} ({verdict.get('family')}): index {observed} but source {expected}")
    for name, row in index["routing"].items():
        cited = _cite(row["evidence"], listed, problems)
        if cited is not None and cited.get("verdict") != row["verdict"]:
            problems.append(f"routing {name}: index {row['verdict']} but source {cited.get('verdict')}")
    for family, row in (index.get("operations") or {}).items():
        cited = _cite(row["evidence"], listed, problems)
        if cited is not None and cited.get("status") != row["raw_status"]:
            problems.append(f"operation {family}: index {row['raw_status']} but source {cited.get('status')}")
        routed = row["raw_status"] if row["raw_status"] in MEASURED else "UNEVALUATED"
        if (row["status"], row["measured"]) != (routed, row["raw_status"] in MEASURED):
            problems.append(f"operation {family}: routes as {row['status']} but source label {row['raw_status']}")
        history = row.get("history") or []
        if not history or (history[-1]["evidence"], history[-1]["status"]) != (row["evidence"], row["raw_status"]):
            problems.append(f"operation {family}: the latest history entry must be the deciding run")
        for entry in history:
            run = _cite(entry["evidence"], listed, problems)
            if run is not None and run.get("status") != entry["status"]:
                problems.append(f"operation {family}: history {entry} disagrees with its run")
    assert not problems, problems


def _runs(paths) -> list[tuple[str, dict]]:
    """(repository path, data) of frozen runs, in the order they finished (each file's own finished_at)."""
    runs = [(p.relative_to(ROOT).as_posix(), json.loads(p.read_text())) for p in paths]
    undated = [rel for rel, data in runs if not data.get("finished_at")]
    assert not undated, f"frozen runs without finished_at cannot be ordered: {undated}"
    return sorted(runs, key=lambda run: run[1]["finished_at"])


def _conditional_key(summary: dict) -> str | None:
    return next((k for k in ("primary_conditional_vs_static", "conditional_vs_static") if k in summary), None)


def test_every_frozen_run_is_indexed_and_the_latest_run_decides():
    """A later frozen run for a family or recipe replaces an earlier one; none is dropped, resurrected or skipped."""
    index = _index()
    listed = {s["path"] for s in index["sources"]}
    problems = []
    admission = _runs(sorted((ROOT / ADMISSION).glob("*/results.json")))
    composition = _runs(sorted((ROOT / P6).glob("*/results*.json")))
    routing = _runs([p for p in sorted((ROOT / P4).glob("*/results*.json"))
                     if _conditional_key(json.loads(p.read_text()).get("summary") or {})])
    problems += [f"{rel}: a frozen run that is not a listed source" for rel, _ in admission + composition + routing
                 if rel not in listed]
    # genomes: every family with a status in any run; the latest run containing it decides; history is every run
    measured: dict[str, list] = {}
    for rel, data in admission:
        for family, row in (data.get("genomes") or {}).items():
            if row.get("status"):
                measured.setdefault(family, []).append((rel, row))
    for family in sorted(set(measured) | set(index["genomes"])):
        row = index["genomes"].get(family)
        if family not in measured:
            problems.append(f"{family}: an index row with no status in any frozen admission run")
            continue
        if row is None:
            problems.append(f"{family}: measured by {[rel for rel, _ in measured[family]]} but has no index row")
            continue
        latest_rel, latest = measured[family][-1]
        if row.get("evidence") != f"{latest_rel}#genomes.{family}" or \
                (row.get("status"), row.get("version")) != (latest["status"], latest.get("version")):
            problems.append(f"{family}: not the latest run containing it: cites {row.get('evidence')} "
                            f"({row.get('status')}), latest {latest_rel} ({latest['status']})")
        expected = [{"run": Path(rel).parent.name, "status": r["status"], "version": r.get("version")}
                    for rel, r in measured[family]]
        if [{k: h.get(k) for k in ("run", "status", "version")} for h in row.get("history") or []] != expected:
            problems.append(f"{family}: history is not every run in order: {row.get('history')}, runs {expected}")
    # recipes: every P6 family's recipe; the latest family measured decides; earlier verdicts stay as history
    families: dict[str, list] = {}
    for rel, data in composition:
        for family in (k for k in data.get("summary", {}) if re.fullmatch(r"F\d+[Rb]?|X\d+", k)):
            if family in P6_NOT_A_RECIPE:
                continue
            if family not in P6_RECIPE:
                problems.append(f"{rel}: family {family} measures no recipe named in this test")
                continue
            families.setdefault(P6_RECIPE[family], []).append(f"{rel}#summary.{family}")
    for recipe in sorted(set(families) | set(index["recipes"])):
        row = index["recipes"].get(recipe)
        if recipe not in families or row is None:
            problems.append(f"recipe {recipe}: index row {row is not None}, frozen families {families.get(recipe)}")
            continue
        cited = [h.get("evidence") for h in row.get("history", [])] + [row.get("evidence")]
        if cited != families[recipe]:
            problems.append(f"recipe {recipe}: not the frozen runs in order: cites {cited}, runs {families[recipe]}")
    # routing: the conditional-competence verdict comes from the latest frozen P4 run
    if routing:
        rel, data = routing[-1]
        expected = f"{rel}#summary.{_conditional_key(data['summary'])}"
        if (index["routing"].get("conditional_competence") or {}).get("evidence") != expected:
            cited = (index["routing"].get("conditional_competence") or {}).get("evidence")
            problems.append(f"routing: not the latest frozen P4 run: cites {cited}, latest {expected}")
    assert not problems, problems


def test_the_derived_fields_the_compiler_routes_on_match_their_source():
    """median_seconds (tie-break), subregions_vs_competitor (orders fits) and competitor, from the cited run."""
    index = _index()
    listed = {s["path"] for s in index["sources"]}
    problems = []
    for family, row in index["genomes"].items():
        cited = _cite(row["evidence"], listed, problems)
        if cited is None:
            continue
        seconds = ((cited.get("arms") or {}).get("candidate") or {}).get("median_seconds")
        if row.get("median_seconds") != seconds or (seconds is None and "median_seconds" in row):
            problems.append(f"{family}: median_seconds {row.get('median_seconds')} but source {seconds}")
        subregions = {name: {"n": sub["n"], **{k: sub["vs_competitor"][k]
                                               for k in ("wins", "losses", "ties", "p_better", "p_worse")}}
                      for name, sub in (cited.get("subregions") or {}).items()}
        if (row.get("subregions_vs_competitor") or {}) != subregions:
            problems.append(f"{family}: subregions_vs_competitor {row.get('subregions_vs_competitor')} but source "
                            f"{subregions}")
        if "competitor" in row and row["competitor"] != cited.get("competitor"):
            problems.append(f"{family}: competitor {row['competitor']!r} but source {cited.get('competitor')!r}")
        if subregions and "competitor" not in row:
            problems.append(f"{family}: subregion verdicts without the competitor they were measured against")
    assert not problems, problems


def _positive(section: str, row: dict) -> bool:
    if section in ("genomes", "organs"):
        return row.get("status") in POSITIVE
    if section == "recipes":
        return row.get("status") == "VPL_LIFT"
    return row.get("verdict") == "GAIN"


def test_every_external_verification_entry_resolves_to_a_positive_record():
    index = _index()
    listed = {s["path"] for s in index["sources"]}
    problems = []
    prefix = {"genomes": "cognition.", "organs": "", "recipes": "recipe.", "routing": "routing."}
    for section, rows in ((s, index.get(s) or {}) for s in prefix):
        for key, row in rows.items():
            entries = row.get("external_verification") or []
            if entries and not _positive(section, row):
                problems.append(f"{section}.{key}: an external outcome on a record that is not positive "
                                f"({row.get('status') or row.get('verdict')}): it must not override the frozen record")
            for entry in entries:
                ref = entry.get("evidence") if isinstance(entry, dict) else None
                if not isinstance(ref, str) or "#" not in ref:
                    problems.append(f"{section}.{key}: external entry {entry!r} cites no path#pointer evidence")
                    continue
                value = _cite(ref, listed, problems)
                if value is None:
                    continue
                binding = "version" if section in ("genomes", "organs") else "code_sha256"
                if not isinstance(value, dict) or value.get("kind") != "external_outcome" or \
                        value.get("verdict") != "VERIFIED" or value.get("mechanism") != prefix[section] + key or \
                        not value.get(binding) or (binding == "version" and value["version"] != row.get("version")):
                    problems.append(f"{section}.{key}: {ref} does not record a verified external outcome for this "
                                    f"mechanism with its {binding}")
    assert not problems, problems


def test_every_source_names_a_commit_present_in_this_repository():
    sources = _index()["sources"]
    unnamed = [s["path"] for s in sources if not s.get("source_commit")]
    assert not unnamed, f"frozen sources without a source commit: {unnamed}"
    shallow = _shallow()
    if shallow is None:
        pytest.skip("git history unavailable: source commits not verified for " +
                    ", ".join(sorted({s['source_commit'][:12] for s in sources})))
    absent = sorted({s["source_commit"] for s in sources
                     if subprocess.run(["git", "cat-file", "-e", f"{s['source_commit']}^{{commit}}"], cwd=ROOT,
                                       capture_output=True, timeout=30).returncode != 0})
    if absent and shallow:
        pytest.skip(f"shallow clone: {len(absent)} source commit(s) outside the fetched depth were not verified: "
                    f"{absent}")
    assert not absent, f"source commits absent from a full clone: {absent}"


def _function_source_digest(text: str, name: str):
    """This test's own digest of a module-level function: its source lines (decorators included), trailing
    whitespace stripped, sha256. Written independently of greg.cognition.compiler.function_digest."""
    tree = ast.parse(text)
    node = next((n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name),
                None)
    if node is None:
        return None
    first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
    body = "\n".join(line.rstrip() for line in text.splitlines()[first - 1:node.end_lineno])
    return "sha256:" + hashlib.sha256(body.encode()).hexdigest()


def test_every_operation_verdict_is_bound_to_the_solver_code_its_run_measured():
    """PR #155's operation-family verdicts route like genome verdicts, so each is bound to the code it measured:
    the solver function's source digest at the run's own source commit, recomputed here from git."""
    index = _index()
    commit_of = {s["path"]: s.get("source_commit") for s in index["sources"]}
    unbound = [f for f, row in index["operations"].items()
               if row["status"] in POSITIVE and not (row.get("code") or {}).get("sha256")]
    assert not unbound, f"positive operation verdicts without a solver-code binding: {unbound}"
    if _shallow() is None:
        pytest.skip("git history unavailable: solver-code bindings not re-derived")
    problems, unreachable = [], []
    for family, row in index["operations"].items():
        code = row.get("code")
        if not code:
            continue
        commit = commit_of[row["evidence"].partition("#")[0]]
        out = subprocess.run(["git", "show", f"{commit}:{code['path']}"], cwd=ROOT, capture_output=True, text=True,
                             timeout=60)
        if out.returncode:
            unreachable.append(commit)
            continue
        if _function_source_digest(out.stdout, code["function"]) != code["sha256"]:
            problems.append(f"operation {family}: code {code['sha256']} is not {code['function']} at {commit[:12]}")
    if unreachable and _shallow():
        pytest.skip(f"shallow clone: solver code at {sorted(set(unreachable))} not verified")
    assert not unreachable, f"source commits absent from a full clone: {sorted(set(unreachable))}"
    assert not problems, problems


def _flip_genome_status(index):
    row = index["genomes"][sorted(index["genomes"])[0]]
    row["status"] = "NICHE_CAPABILITY" if row["status"] == "DEFAULT_FOR_GEOMETRY" else "DEFAULT_FOR_GEOMETRY"


def _route_a_structural_label(index):
    row = next(r for r in index["operations"].values() if not r["measured"])
    row["status"] = "DEFAULT_FOR_GEOMETRY"
def _resurrect_older_run(index):
    """collective_market cites its v1 SUPERSEDED verdict with a v1-only history, as though v2 never ran."""
    row = index["genomes"]["collective_market"]
    first = row["history"][0]
    row.update(status=first["status"], version=first["version"], history=[first],
               evidence=f"{ADMISSION}/{first['run']}/results.json#genomes.collective_market")


def _flip_subregion(index):
    row = index["genomes"]["basal_hysteresis"]["subregions_vs_competitor"]["high_noise"]
    row.update(wins=row["losses"], losses=0, p_better=0.0001, p_worse=1.0)


def _external_on_superseded(index):
    index["genomes"]["basal_pid"]["external_verification"] = [{"ref": "x"}]


def _external_on_positive(index):
    index["genomes"]["basal_breaker"]["external_verification"] = [{"ref": "anything-at-all"}]


def _older_family_decides(index):
    row = index["recipes"]["graph_then_allocate"]
    older = row.pop("history")[0]
    index["recipes"]["graph_then_allocate"] = older


def _external_cites_a_listed_readme(index):
    """A frozen run's README listed with its true digest (a receipt, not JSON) and cited by an external entry."""
    readme = f"{ADMISSION}/2026-10-14-v2/README.md"
    index["sources"].append({"path": readme, "source_commit": "fixture",
                             "sha256": "sha256:" + hashlib.sha256((ROOT / readme).read_bytes()).hexdigest()})
    index["genomes"]["flow_maxflow"]["external_verification"] = [{"evidence": f"{readme}#outcome"}]


DIGESTS = test_every_listed_source_recomputes_to_its_recorded_sha256
VERDICTS = test_every_cited_verdict_matches_the_source_it_cites
COMPLETE = test_every_frozen_run_is_indexed_and_the_latest_run_decides
DERIVED = test_the_derived_fields_the_compiler_routes_on_match_their_source
EXTERNAL = test_every_external_verification_entry_resolves_to_a_positive_record
COMMITS = test_every_source_names_a_commit_present_in_this_repository
BOUND = test_every_operation_verdict_is_bound_to_the_solver_code_its_run_measured


@pytest.mark.parametrize("corrupt, check, needle", [
    (lambda i: i["sources"][0].update(sha256="sha256:" + "0" * 64), DIGESTS, "changed"),
    (lambda i: i["sources"][0].update(path="docs/evidence/nowhere.json"), DIGESTS, "absent"),
    (_flip_genome_status, VERDICTS, "but source"),
    (lambda i: next(iter(i["recipes"].values())).update(wins=10 ** 6), VERDICTS, "but source"),
    (lambda i: i["recipes"]["graph_then_allocate"]["history"][0].update(wins=1), VERDICTS, "but source"),
    (lambda i: i["sources"].pop(), VERDICTS, "not a listed"),
    (lambda i: i["operations"]["pattern"].update(raw_status="DEFAULT_FOR_GEOMETRY"), VERDICTS, "but source"),
    (_route_a_structural_label, VERDICTS, "routes as"),
    (_resurrect_older_run, COMPLETE, "not the latest run containing it"),
    (lambda i: i["genomes"].pop("basal_pid"), COMPLETE, "has no index row"),
    (lambda i: i["genomes"]["collective_market"].update(history=i["genomes"]["collective_market"]["history"][-1:]),
     COMPLETE, "history is not every run in order"),
    (lambda i: i["genomes"].update(never_measured={"status": "DEFAULT_FOR_GEOMETRY"}), COMPLETE, "no status in any"),
    (_older_family_decides, COMPLETE, "not the frozen runs in order"),
    (lambda i: i["recipes"].pop("bayes_then_voi"), COMPLETE, "recipe bayes_then_voi"),
    (lambda i: i["routing"]["conditional_competence"].update(
        evidence=f"{P4}/2026-10-07/results-v2.json#summary.conditional_vs_static"), COMPLETE,
     "not the latest frozen P4 run"),
    (lambda i: i["sources"].remove(next(s for s in i["sources"] if s["path"].startswith(P6))), COMPLETE,
     "not a listed source"),
    (_flip_subregion, DERIVED, "subregions_vs_competitor"),
    (lambda i: i["genomes"]["basal_hysteresis"].update(median_seconds=1e-9), DERIVED, "median_seconds"),
    (lambda i: i["genomes"]["basal_hysteresis"].update(competitor="a forged competitor"), DERIVED, "competitor"),
    (_external_on_superseded, EXTERNAL, "not positive"),
    (_external_on_positive, EXTERNAL, "no path#pointer"),
    (lambda i: i["recipes"]["bayes_then_voi"].update(external_verification=[
        {"evidence": f"{ADMISSION}/2026-10-14-v2/results.json#genomes.collective_market"}]), EXTERNAL,
     "does not record a verified external outcome"),
    (_external_cites_a_listed_readme, EXTERNAL, "not a readable JSON source"),
    (lambda i: i["sources"][0].pop("source_commit"), COMMITS, "without a source commit"),
    (lambda i: i["operations"]["graph"]["code"].update(sha256="sha256:" + "0" * 64), BOUND, "is not graph at"),
    (lambda i: i["operations"]["control"].update(code=None), BOUND, "without a solver-code binding"),
])
def test_the_checks_fail_on_a_corrupted_index(tmp_path, monkeypatch, corrupt, check, needle):
    """Each check is falsifiable: a corrupted copy of the real index must fail it."""
    index = _index()
    corrupt(index)
    fake = tmp_path / "index.json"
    fake.write_text(json.dumps(index))
    monkeypatch.setitem(globals(), "INDEX", fake)
    with pytest.raises(AssertionError, match=needle):
        check()
