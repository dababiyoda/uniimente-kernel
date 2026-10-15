"""The reality ledger (scripts/mind_status.py): one label per mechanism, from frozen evidence only (section 31 item 17).

Checked against independent sources of truth rather than the generator's own code: the Competency Compiler's
actual routing rows for the same evidence (a genome or organ is supported exactly when the compiler routes it on
fresh positive evidence), greg/path.json's frontier records, the live catalog, the instance generators and the
frozen P6 runs' own limits (for which benchmark worlds are simulated), the frozen P8 cycle records, and fixture
indexes that move one fact at a time (a version bump, an external verification, a significant loss).
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

from greg import path as devpath
from greg.cognition import compiler, worlds
from greg.cognition import reserved as reserved_record
from greg.cognition.catalog import CORTEX_ENTRIES, FAMILIES
from greg.cognition.composition import RECIPES
from greg.cognition.genomes import library

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import mind_status as M  # noqa: E402

SUPPORTED = ("HELDOUT_SUPPORTED", "SIMULATED", "EXTERNALLY_VERIFIED")
POSITIVE = ("DEFAULT_FOR_GEOMETRY", "NICHE_CAPABILITY")
# Read off each genome's instance generator and benchmark suite, independently of greg/cognition/worlds.py: the
# held-out truth of these is a seeded generator's hidden state, so no positive verdict on them may read as
# held-out support for the real process they imitate.
SIMULATED_WORLDS = {"basal_bandit", "basal_breaker", "basal_kalman", "basal_pid", "basal_hysteresis",
                    "basal_bayes_filter", "causal_backdoor", "collective_market", "mech_vcg", "collective_flock",
                    "control_mpc", "develop_repair", "pid_simopt", "collective_quorum", "collective_immune",
                    "bayes_interval", "bootstrap_ci"}
NATURAL = {"forecast_quantile"}                     # recorded M4 series and their real continuations
MATHEMATICAL = {"flow_maxflow", "queue_erlang", "verify_modelcheck", "synth_cegis", "mc_importance", "game_minimax",
                "dp_knapsack", "collective_aco", "info_experiment", "search_astar"}
# Organ payload parts the cortex route policy sends to each organ (cortex/routing.py::_route_parts).
ORGAN_PAYLOAD = {"estimation_model": {}, "deterrence_model": {}, "sources": ["s"], "schedule_request": {},
                 "claim": {"type": "intervention"}}
OUTCOMES = "docs/evidence/external/outcomes.json"


def _rows(status: dict) -> dict:
    return {r["id"]: r for r in status["mechanisms"]}


def _fixture(tmp_path, change) -> Path:
    index = json.loads(M.INDEX.read_text())
    change(index)
    out = tmp_path / "index.json"
    out.write_text(json.dumps(index))
    return out


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _with_external(tmp_path, outcomes: dict, cite, *, list_source=True) -> tuple[Path, Path]:
    """A copy of the real index whose rows carry external_verification entries ``cite(index)`` adds, citing a
    listed, digested outcome file under an evidence root in tmp_path."""
    root = tmp_path / "root"
    file = root / OUTCOMES
    file.parent.mkdir(parents=True)
    file.write_text(json.dumps({"outcomes": outcomes}))

    def change(index):
        if list_source:
            index["sources"].append({"path": OUTCOMES, "sha256": _sha(file), "source_commit": "fixture"})
        cite(index)
    return _fixture(tmp_path, change), root


def _outcome(mechanism: str, **binding) -> dict:
    return {"kind": "external_outcome", "verdict": "VERIFIED", "mechanism": mechanism, **binding}


def _agreement(evidence: dict, rows: dict) -> list:
    """Genomes and organs whose label disagrees with the compiler's routing on the same evidence."""
    wrong = []
    for family, item in library.executables().items():
        data = {k: 0 for k in item.genome.required_inputs}
        routed = [c for c in compiler.candidates(data, compiler.CompetencyGeometry(), evidence)
                  if c["method"] == f"cognition.{family}"]
        assert routed, family
        positive = routed[0]["status"] in POSITIVE and not routed[0].get("stale_evidence")
        if (rows[f"cognition.{family}"]["label"] in SUPPORTED) != positive:
            wrong.append((family, routed[0]["status"], rows[f"cognition.{family}"]["label"]))
    organs = [c for c in compiler.candidates(ORGAN_PAYLOAD, compiler.CompetencyGeometry(), evidence)
              if c["kind"] == "problem"]
    assert len(organs) == len(ORGAN_PAYLOAD), organs
    for organ in organs:
        positive = organ["status"] in POSITIVE and not organ.get("stale_evidence")
        if (rows[organ["method"]]["label"] in SUPPORTED) != positive:
            wrong.append((organ["method"], organ["status"], rows[organ["method"]]["label"]))
    return wrong


def test_every_mechanism_has_exactly_one_known_label_and_none_is_left_out():
    status = M.status()
    rows = status["mechanisms"]
    assert len({r["id"] for r in rows}) == len(rows)
    assert all(r["label"] in M.LABELS and r["basis"] for r in rows)
    assert sum(status["counts"].values()) == len(rows) and set(status["counts"]) == set(M.LABELS)
    ids = _rows(status)
    assert {f"cognition.{f}" for f in library.executables()} <= {i for i, r in ids.items() if r["kind"] == "genome"}
    assert {f"cognition.{f}" for f in FAMILIES} <= set(ids)                   # genome or catalog family, never absent
    assert set(CORTEX_ENTRIES) <= set(ids) and {f"recipe.{r}" for r in RECIPES} <= set(ids)
    assert {f"frontier.{b['id']}" for b in devpath.load()["frontier_backcasts"]} <= set(ids)


def test_genome_and_organ_labels_agree_with_what_the_compiler_routes_on():
    """Supported exactly when the compiler routes the genome or organ on fresh positive frozen evidence."""
    assert not _agreement(compiler.evidence_index(), _rows(M.status()))


def test_organ_verdicts_are_labelled_by_the_rules_the_compiler_routes_on(tmp_path):
    def organs(index):
        index["organs"] = {
            "cognition.cortex.estimation.fermi": {"status": "REJECTED"},
            "cognition.cortex.deterrence.accountability": {
                "status": "DEFAULT_FOR_GEOMETRY",
                "version": CORTEX_ENTRIES["cognition.cortex.deterrence.accountability"][0]},
            "cognition.cortex.semantic": {"status": "DEFAULT_FOR_GEOMETRY", "version": "0.0.0-old"},
            "cognition.cortex.extraction.schedule": {"status": "EXPERIMENTAL"},
            "cognition.cortex.evidence_causal": {"status": "NICHE_CAPABILITY"}}
    fixture = _fixture(tmp_path, organs)
    rows = _rows(M.status(index_path=fixture))
    assert rows["cognition.cortex.estimation.fermi"]["label"] == "BUILT"
    assert "refuted" in rows["cognition.cortex.estimation.fermi"]["basis"]
    assert rows["cognition.cortex.deterrence.accountability"]["label"] == "SIMULATED"     # no declared world
    assert rows["cognition.cortex.semantic"]["label"] == "BUILT"                           # stale positive
    assert "needs re-admission" in rows["cognition.cortex.semantic"]["basis"]
    assert rows["cognition.cortex.extraction.schedule"]["label"] == "UNRESOLVED"
    assert not any("no per-organ verdict" in rows[c]["basis"] for c in (
        "cognition.cortex.estimation.fermi", "cognition.cortex.deterrence.accountability"))
    assert not _agreement(json.loads(fixture.read_text()), rows)


def test_every_genome_declares_its_benchmark_world_consistently_with_its_generator():
    executables = library.executables()
    assert set(worlds.GENOMES) == set(executables), "every executable genome declares its benchmark world"
    for family, item in executables.items():
        world = worlds.world("genome", family)
        assert world in worlds.WORLDS, family
        # a genome samples recorded data exactly when its generator keys a finite pool of real data
        assert (world == "natural_data") == (item.instance_key is not None), family
        g = item.genome
        if g.epistemic_class == "physical" or g.evidence_type in ("simulation", "control_trace",
                                                                  "developmental_trace"):
            assert world == "simulated_world", family     # GREG has no sensors: physical competence is simulated
    assert {f for f in executables if worlds.world("genome", f) == "simulated_world"} >= SIMULATED_WORLDS
    assert {f for f in executables if worlds.world("genome", f) == "natural_data"} == NATURAL
    assert {f for f in executables if worlds.world("genome", f) == "mathematical_instance"} >= MATHEMATICAL


def test_nothing_is_externally_verified_today_and_simulated_worlds_are_never_called_heldout_supported():
    status = M.status()
    assert status["counts"]["EXTERNALLY_VERIFIED"] == 0 and not status["external_verification_problems"]
    rows = _rows(status)
    for family in SIMULATED_WORLDS:
        assert rows[f"cognition.{family}"]["label"] != "HELDOUT_SUPPORTED", family
    for family in ("basal_breaker", "basal_bandit", "causal_backdoor", "collective_market", "mech_vcg",
                   "basal_kalman"):                     # positive held-out verdicts measured on simulated worlds
        assert rows[f"cognition.{family}"]["label"] == "SIMULATED", family
    assert rows["cognition.forecast_quantile"]["label"] == "HELDOUT_SUPPORTED"          # natural data
    assert rows["cognition.flow_maxflow"]["label"] == "HELDOUT_SUPPORTED"               # mathematical instances
    assert rows["cognition.develop_repair"]["label"] != "HELDOUT_SUPPORTED"            # a simulated lattice only


def _family_limits(index: dict) -> dict:
    """P6 family -> the frozen run's own limits text that describes it (every recipe verdict and its history)."""
    out = {}
    for row in index["recipes"].values():
        for verdict in [row, *row.get("history", [])]:
            source = json.loads((ROOT / verdict["evidence"].partition("#")[0]).read_text())
            named = [lim for lim in source["limits"] if verdict["family"] in re.findall(r"\bF\d+R?\b", lim)]
            general = [lim for lim in source["limits"] if not re.findall(r"\bF\d+R?\b", lim)]
            out[verdict["family"]] = named or general
    return out


def test_composition_families_are_declared_as_the_frozen_runs_describe_them_and_constructed_lift_is_simulated():
    index = json.loads(M.INDEX.read_text())
    for family, limits in _family_limits(index).items():
        constructed = any("constructed" in lim for lim in limits)
        real = any(re.search(r"\breal\b", lim) for lim in limits)
        world = worlds.world("p6_family", family)
        assert world is not None, family
        assert (world == "natural_data") == (real and not constructed), (family, limits)
    rows = _rows(M.status())
    for recipe in ("estimate_then_optimize", "identify_then_optimize", "bayes_then_voi"):    # F1, F2R, F4
        assert rows[f"recipe.{recipe}"]["label"] == "SIMULATED", recipe
    for recipe in ("forecast_then_staff", "graph_then_allocate", "track_then_staff"):        # F6, F7, F8: real data
        assert rows[f"recipe.{recipe}"]["label"] == "HELDOUT_SUPPORTED", recipe


def test_a_version_bump_makes_positive_evidence_stale_while_negative_evidence_persists(tmp_path):
    def bump(index):
        for family in ("basal_kalman", "flow_maxflow", "collective_quorum", "flow_reinforce_greedy"):
            index["genomes"][family]["version"] = "0.0.0-old"
    fixture = _fixture(tmp_path, bump)
    rows = _rows(M.status(index_path=fixture))
    for family in ("basal_kalman", "flow_maxflow"):        # positive -> stale -> BUILT, version kept on the row
        row = rows[f"cognition.{family}"]
        assert row["label"] == "BUILT" and row["heldout"]["current"] is False
        assert row["heldout"]["version_measured"] == "0.0.0-old" and "needs re-admission" in row["basis"]
    assert rows["cognition.collective_quorum"]["label"] == "UNRESOLVED"       # EXPERIMENTAL persists
    assert "persists until a re-admission" in rows["cognition.collective_quorum"]["basis"]
    assert rows["cognition.flow_reinforce_greedy"]["label"] == "BUILT"        # SUPERSEDED persists
    assert "refuted" in rows["cognition.flow_reinforce_greedy"]["basis"]
    # the compiler reads the same fixture the same way
    evidence = json.loads(fixture.read_text())
    data = {k: 0 for k in library.genome("flow_maxflow").required_inputs}
    routed = next(c for c in compiler.candidates(data, compiler.CompetencyGeometry(), evidence)
                  if c["method"] == "cognition.flow_maxflow")
    assert routed["status"] == "UNEVALUATED" and routed["stale_evidence"]


def test_external_verification_counts_only_when_it_resolves_for_the_current_version_or_code(tmp_path):
    current = library.genome("flow_maxflow").version
    code = _sha(ROOT / M.CODE["recipe"])
    outcomes = {"maxflow": _outcome("cognition.flow_maxflow", version=current),
                "erlang_old": _outcome("cognition.queue_erlang", version="0.0.1"),
                "voi": _outcome("recipe.bayes_then_voi", code_sha256=code),
                "staff_old_code": _outcome("recipe.forecast_then_staff", code_sha256="sha256:" + "0" * 64),
                "aco_wrong_mechanism": _outcome("cognition.flow_maxflow", version=current),
                "aco_not_external": {"kind": "admission", "verdict": "VERIFIED",
                                     "mechanism": "cognition.collective_aco"}}

    def cite(index):
        genomes, recipes = index["genomes"], index["recipes"]
        genomes["flow_maxflow"]["external_verification"] = [{"evidence": f"{OUTCOMES}#outcomes.maxflow"}]
        genomes["queue_erlang"]["external_verification"] = [{"evidence": f"{OUTCOMES}#outcomes.erlang_old"}]
        genomes["basal_breaker"]["external_verification"] = [{"ref": "anything-at-all"}]     # the unchecked format
        genomes["collective_aco"]["external_verification"] = [
            {"evidence": f"{OUTCOMES}#outcomes.aco_wrong_mechanism"},
            {"evidence": f"{OUTCOMES}#outcomes.aco_not_external"},
            {"evidence": "docs/evidence/unlisted.json#x"}, {"evidence": f"{OUTCOMES}#outcomes.absent"}]
        recipes["bayes_then_voi"]["external_verification"] = [{"evidence": f"{OUTCOMES}#outcomes.voi"}]
        recipes["forecast_then_staff"]["external_verification"] = [{"evidence": f"{OUTCOMES}#outcomes.staff_old_code"}]
    fixture, root = _with_external(tmp_path, outcomes, cite)
    status = M.status(index_path=fixture, evidence_root=root)
    rows = _rows(status)
    assert rows["cognition.flow_maxflow"]["label"] == "EXTERNALLY_VERIFIED"
    assert rows["recipe.bayes_then_voi"]["label"] == "EXTERNALLY_VERIFIED"
    assert rows["cognition.queue_erlang"]["label"] == "HELDOUT_SUPPORTED"     # an old version's check does not count
    assert rows["recipe.forecast_then_staff"]["label"] == "HELDOUT_SUPPORTED"  # nor another code digest's
    assert rows["cognition.basal_breaker"]["label"] == "SIMULATED"            # a bare ref is not evidence
    assert rows["cognition.collective_aco"]["label"] == "HELDOUT_SUPPORTED"
    assert len(rows["cognition.collective_aco"]["external_verification_unresolved"]) == 4
    assert sum(p.startswith("cognition.collective_aco:") for p in status["external_verification_problems"]) == 4
    assert not _agreement(json.loads(fixture.read_text()), rows)          # the compiler never reads the entries
    # the source changed after the index digested it: nothing counts
    (root / OUTCOMES).write_text(json.dumps({"outcomes": {**outcomes, "x": 1}}))
    assert _rows(M.status(index_path=fixture, evidence_root=root))["cognition.flow_maxflow"]["label"] == \
        "HELDOUT_SUPPORTED"


def test_a_bare_external_ref_counts_for_nothing_and_never_overrides_a_refutation(tmp_path):
    """The unchecked format the index once accepted: any non-empty 'ref' string labelled the row."""
    def change(index):
        for family in ("basal_breaker", "basal_pid"):
            index["genomes"][family]["external_verification"] = [
                {"ref": "anything-at-all", "version": library.genome(family).version}]
        index["recipes"]["forecast_then_allocate"]["external_verification"] = [{"ref": "y"}]
        index["routing"]["conditional_competence"]["external_verification"] = [{"ref": "z"}]
    status = M.status(index_path=_fixture(tmp_path, change))
    rows = _rows(status)
    assert status["counts"]["EXTERNALLY_VERIFIED"] == 0
    assert rows["cognition.basal_breaker"]["label"] == "SIMULATED" and rows["cognition.basal_pid"]["label"] == "BUILT"
    assert rows["recipe.forecast_then_allocate"]["label"] == "UNRESOLVED"
    assert rows["routing.conditional_competence"]["label"] == "BUILT"
    assert len(status["external_verification_problems"]) == 4


def test_an_external_outcome_never_overrides_a_refuted_demoted_or_unadmitted_record(tmp_path):
    """The conflict is reported; the label and the compiler's routing still agree."""
    outcomes = {"pid": _outcome("cognition.basal_pid", version=library.genome("basal_pid").version),
                "lsa": _outcome("cognition.assignment_lsa", version=library.genome("assignment_lsa").version),
                "f5": _outcome("recipe.forecast_then_allocate", code_sha256=_sha(ROOT / M.CODE["recipe"])),
                "p4": _outcome("routing.conditional_competence", code_sha256=_sha(ROOT / M.CODE["routing"]))}

    def cite(index):
        index["genomes"]["basal_pid"]["external_verification"] = [{"evidence": f"{OUTCOMES}#outcomes.pid"}]
        index["genomes"]["assignment_lsa"] = {"external_verification": [{"evidence": f"{OUTCOMES}#outcomes.lsa"}]}
        index["recipes"]["forecast_then_allocate"]["external_verification"] = [{"evidence": f"{OUTCOMES}#outcomes.f5"}]
        index["routing"]["conditional_competence"]["external_verification"] = [
            {"evidence": f"{OUTCOMES}#outcomes.p4"}]
    fixture, root = _with_external(tmp_path, outcomes, cite)
    status = M.status(index_path=fixture, evidence_root=root)
    rows = _rows(status)
    expected = {"cognition.basal_pid": "BUILT", "cognition.assignment_lsa": "BUILT",
                "recipe.forecast_then_allocate": "UNRESOLVED", "routing.conditional_competence": "BUILT"}
    for mid, label in expected.items():
        assert rows[mid]["label"] == label and rows[mid]["external_verification_conflict"], mid
        assert any(p.startswith(f"{mid}:") for p in status["external_verification_problems"]), mid
    assert not _agreement(json.loads(fixture.read_text()), rows)


def test_an_external_entry_citing_a_listed_source_that_is_not_json_is_reported_not_a_crash(tmp_path):
    """A listed, correctly digested source need not be JSON (a frozen run's README is a receipt). An entry citing
    it, or a source that is not UTF-8 or nests past the parser's limit, counts for nothing and is reported; the
    ledger is still produced."""
    readme = "docs/evidence/greg-genome-admission/2026-10-14-v2/README.md"
    files = {readme: (ROOT / readme).read_bytes(),
             "docs/evidence/external/latin1.json": '{"outcomes": "caf\xe9"}'.encode("latin-1"),
             "docs/evidence/external/deep.json": b"[" * 200_000 + b"]" * 200_000}
    root = tmp_path / "root"
    for rel, data in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    cited = {("genomes", "flow_maxflow"): readme, ("recipes", "bayes_then_voi"): "docs/evidence/external/latin1.json",
             ("routing", "conditional_competence"): "docs/evidence/external/deep.json"}

    def change(index):
        for rel in files:
            index["sources"].append({"path": rel, "sha256": _sha(root / rel), "source_commit": "fixture"})
        for (section, key), rel in cited.items():
            index[section][key]["external_verification"] = [{"evidence": f"{rel}#outcomes.x"}]
    fixture = _fixture(tmp_path, change)
    status = M.status(index_path=fixture, evidence_root=root)
    rows, plain = _rows(status), _rows(M.status())
    for mid in ("cognition.flow_maxflow", "recipe.bayes_then_voi", "routing.conditional_competence"):
        assert rows[mid]["label"] == plain[mid]["label"], mid                  # counts for nothing
        assert [p for p in rows[mid]["external_verification_unresolved"] if "not a readable JSON source" in p], mid
        assert any(p.startswith(f"{mid}:") for p in status["external_verification_problems"]), mid
    assert status["counts"]["EXTERNALLY_VERIFIED"] == 0


@pytest.mark.parametrize("wins, losses, label", [(17, 13, "UNRESOLVED"), (2, 15, "BUILT")])
def test_a_recipe_without_lift_is_unresolved_unless_significantly_worse(tmp_path, wins, losses, label):
    def change(index):
        index["recipes"]["forecast_then_allocate"].update(wins=wins, losses=losses)
    rows = _rows(M.status(index_path=_fixture(tmp_path, change)))
    assert rows["recipe.forecast_then_allocate"]["label"] == label


def test_a_no_lift_basis_never_calls_significant_wins_insignificant(tmp_path):
    def change(index):
        index["recipes"]["forecast_then_allocate"].update(wins=25, losses=2)     # lift False for another reason
    row = _rows(M.status(index_path=_fixture(tmp_path, change)))["recipe.forecast_then_allocate"]
    assert row["label"] == "UNRESOLVED"
    assert "neither direction significant" not in row["basis"] and "significantly better on wins" in row["basis"]
    real = _rows(M.status())["recipe.forecast_then_allocate"]                  # 17-13: neither is significant
    assert "neither direction significant" in real["basis"]


def test_the_sign_test_is_exact_for_large_families(tmp_path):
    from scipy.stats import binomtest
    for k, n in ((515, 1029), (580, 1100), (5200, 10000), (0, 5000), (5000, 5000)):
        assert M._p_at_least(k, n) == pytest.approx(binomtest(k, n, 0.5, alternative="greater").pvalue, rel=1e-9)

    def change(index):
        index["recipes"]["forecast_then_allocate"].update(wins=520, losses=580)
    row = _rows(M.status(index_path=_fixture(tmp_path, change)))["recipe.forecast_then_allocate"]
    assert row["label"] == "BUILT"                                     # 580 of 1100 worse: one-sided p 0.038


@pytest.mark.parametrize("verdict, label", [("GAIN", "HELDOUT_SUPPORTED"), ("REGRESSION", "BUILT"),
                                            ("NO_SIGNIFICANT_DIFFERENCE", "UNRESOLVED")])
def test_the_p4_route_is_labelled_from_its_frozen_verdict(tmp_path, verdict, label):
    def change(index):
        index["routing"]["conditional_competence"]["verdict"] = verdict
    rows = _rows(M.status(index_path=_fixture(tmp_path, change)))
    assert rows["routing.conditional_competence"]["label"] == label


def _expected_id(ref: str) -> str:
    if ":" in ref or "@" not in ref:
        return ref
    return "cognition." + ref.split("@")[0]


def test_every_executor_the_reserved_record_names_is_labelled_and_p8_carries_its_frozen_cycles():
    status = M.status()
    rows = _rows(status)
    named = {ref for row in reserved_record.reconciled().values() for ref in row["executors"]}
    assert named and {_expected_id(ref) for ref in named} <= set(rows), sorted(
        _expected_id(ref) for ref in named if _expected_id(ref) not in rows)
    for ref in (r for r in named if ":" in r):
        assert rows[ref]["kind"] == "executor" and rows[ref]["label"] == "BUILT", ref
    cycles = sorted(ROOT.glob("docs/evidence/greg-protected-evolution/*/cycle-*.json"))
    decisions = [json.loads(p.read_text())["decision"] for p in cycles]
    p8 = rows["greg.cognition.evolution:cycle"]
    assert len(p8["evidence_outside_index"]) == len(cycles) == 3
    assert sorted(c["decision"] for c in p8["evidence_outside_index"]) == sorted(decisions)
    assert ("never kept an improvement" in p8["basis"]) == all(d == "REJECT" for d in decisions)


def test_an_executor_that_resolves_to_nothing_is_unresolved(monkeypatch):
    monkeypatch.setitem(reserved_record.EXECUTED_ON_GREG, "cortex.meta.metaconsensus",
                        (("greg.cognition.verification:metaconsensus", "greg.cognition.nowhere:thing"), "probe"))
    row = _rows(M.status())["greg.cognition.nowhere:thing"]
    assert row["kind"] == "executor" and row["label"] == "UNRESOLVED"


def test_a_missing_index_is_reported_and_nothing_is_supported(tmp_path):
    status = M.status(index_path=tmp_path / "absent.json")
    assert status["missing_sources"] and status["generated_from"]["evidence_index"]["present"] is False
    assert all(r["label"] not in SUPPORTED for r in status["mechanisms"])


def test_a_verdict_for_a_genome_no_longer_in_the_library_is_unresolved_not_dropped(tmp_path):
    def change(index):
        index["genomes"]["retired_probe"] = {"status": "DEFAULT_FOR_GEOMETRY", "version": "1.0.0", "history": []}
    row = _rows(M.status(index_path=_fixture(tmp_path, change)))["cognition.retired_probe"]
    assert row["label"] == "UNRESOLVED" and row["heldout"]["status"] == "DEFAULT_FOR_GEOMETRY"


def test_a_catalog_family_without_an_executor_is_unresolved(monkeypatch):
    monkeypatch.setitem(FAMILIES, "unbuilt_probe", (3, ("unbuilt_op",), ("estimate",), "bounded_estimate", None))
    row = _rows(M.status())["cognition.unbuilt_probe"]
    assert row["label"] == "UNRESOLVED" and row["executor"] is None


def test_frontier_records_stay_frontier_and_the_descendant_is_never_claimed():
    rows = _rows(M.status())
    frontier = {b["id"]: b for b in devpath.load()["frontier_backcasts"]}
    for record_id, record in frontier.items():
        row = rows[f"frontier.{record_id}"]
        assert row["label"] == "FRONTIER" and row["buildability_status"] == record["buildability_status"]
    descendants = [i for i, b in frontier.items() if b["buildability_status"] == "SCIENCE_FICTION_DESCENDANT"]
    assert descendants == ["substrate_independent_developmental_intelligence"]
    reserved = [r for r in rows.values() if r["kind"] == "reserved_cortex_family"]
    assert reserved and all(r["label"] == "UNRESOLVED" for r in reserved)


def test_the_cli_prints_the_same_json_and_writes_nothing():
    watched = [M.INDEX, M.PATH, ROOT / "cortex" / "genome.py"]
    before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in watched]
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    out = subprocess.run([sys.executable, str(ROOT / "scripts" / "mind_status.py")], cwd=ROOT, env=env,
                         capture_output=True, text=True, timeout=300, check=True)
    assert json.loads(out.stdout) == json.loads(json.dumps(M.status()))
    assert [hashlib.sha256(p.read_bytes()).hexdigest() for p in watched] == before
    assert M.status() == copy.deepcopy(M.status())                      # deterministic: no clock, no randomness
