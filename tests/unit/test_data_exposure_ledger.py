"""The all-lineage data-exposure ledger (scripts/data_exposure_ledger.py; coverage build item B02).

Checked against sources the ledger does not write: git objects (every cited artifact and generator file exists at the
commit the ledger names), the live genome library (the static generator resolution agrees with the imported one),
greg/cognition/evolution.py's registered splits, and a byte-identical rebuild from committed artifacts.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import data_exposure_ledger as L  # noqa: E402

LEDGER = json.loads(L.LEDGER.read_text())
PIN_AVAILABLE = L.resolve(L.PIN_179["commit"]) is not None
CR = "greg.cognition.genomes.developmental:constraint_release_instance"


def _exists(commit: str, path: str) -> bool:
    return subprocess.run(["git", "cat-file", "-e", f"{commit}:{path}"], cwd=ROOT, capture_output=True,
                          check=False).returncode == 0


def _by_id():
    return {r["id"]: r for r in LEDGER["exposures"]}


@pytest.mark.skipif(not PIN_AVAILABLE, reason="PR #179's pinned commit is not in this clone")
def test_the_ledger_rebuilds_byte_identically_from_committed_artifacts():
    assert L.render(L.build()) == L.LEDGER.read_text()


def test_every_cited_path_exists_at_the_commit_the_ledger_names():
    missing = []
    for rec in LEDGER["exposures"]:
        art = rec["artifact"]
        read = art.get("read_at") or art["commit"]
        for f in art.get("files") or [{"path": art["path"]}]:
            if not _exists(read, f["path"]):
                missing.append((rec["id"], f["path"]))
        gen = rec["generator"]
        for f in gen.get("files", []):
            if not _exists(art["commit"], f["path"]):
                missing.append((rec["id"], f["path"]))
        if gen.get("kind") == "code" and gen.get("resolved"):
            if not _exists(gen["commit"], gen["module"].replace(".", "/") + ".py"):
                missing.append((rec["id"], gen["module"]))
        if gen.get("kind") == "data" and gen.get("path") and not _exists(gen["commit"], gen["path"]):
            missing.append((rec["id"], gen["path"]))
    for decl in LEDGER["preregistration_declarations"]:
        if not _exists(decl["commit"], decl["path"]):
            missing.append(("prereg", decl["path"]))
    assert not missing, missing[:10]


def test_every_globbed_artifact_is_parsed_or_named_as_carrying_no_declaration():
    for name, by_lineage in LEDGER["coverage"].items():
        for lineage, row in by_lineage.items():
            assert row["missing"] == [], (name, lineage, row["missing"])
            assert row["parsed"] + len(row["no_declaration"]) == row["matched"], (name, lineage)
    assert LEDGER["coverage"]["admission freezes (#158 form)"]["#158"]["parsed"] >= 4
    assert LEDGER["coverage"]["admission freezes (#179 operation form)"]["#179"]["parsed"] == 3


def test_both_lineages_named_seed_ranges_appear():
    held = {L.L158: set(), L.L179: set()}
    for rec in LEDGER["exposures"]:
        for lineage in rec["lineages"]:
            held[lineage] |= L.expand(rec.get("seeds") or [])
    for lo, hi in ((1001, 1040), (2001, 2040), (3001, 3040), (5001, 5040)):
        assert set(range(lo, hi + 1)) <= held[L.L179], (lo, hi)
    for lo, hi in ((1000, 1029), (1100, 1129), (1200, 1229), (1300, 1329), (7000, 7039), (7200, 7259),
                   (7400, 7459), (7600, 7659), (7880, 7999), (8060, 8299), (8300, 8539)):
        assert set(range(lo, hi + 1)) <= held[L.L158], (lo, hi)


def test_registered_p8_splits_match_evolution_and_unrun_ones_are_not_exposures():
    from greg.cognition import evolution
    splits = {(s["target"], s["split"]): s for s in LEDGER["reservations"]["registered_p8_splits"]}
    assert splits[("immune_detect", "cycle-7")]["recorded_cycle"] is False
    assert splits[("immune_detect", "cycle-7")]["train"] == L.ranges(evolution.IMMUNE_SPLITS["cycle-7"][0])
    seven = set(range(8600, 8840))
    assert not any(seven & L.expand(r.get("seeds") or []) for r in LEDGER["exposures"])


def test_recorded_p8_splits_agree_with_their_records_and_held_out_looks_are_truthful():
    p8 = [r for r in LEDGER["exposures"] if r["program"].startswith("P8 ") and "split_check" in r]
    assert len(p8) == 12 and all(r["split_check"]["agree"] for r in p8)
    looked = {r["artifact"]["path"].rsplit("/", 1)[1]: r["looked_at"] for r in p8 if r["role"] == "P8 held-out"}
    assert looked == {"cycle-forecast-1.json": True, "cycle-immune-2.json": False, "cycle-cr-3.json": False,
                      "cycle-cr-4.json": True, "cycle-cr-5.json": False, "cycle-cr-6.json": True}


def test_static_generator_resolution_agrees_with_the_live_library():
    from greg.cognition.genomes import library
    static = L.genome_generators(L.resolve("HEAD"))
    live = {f: (i.instance.__module__, i.instance.__name__) for f, i in library.executables().items()}
    assert static == live


def test_the_aliasing_sample_never_generates_a_reserved_seed():
    assert LEDGER["aliasing"]["sample_seeds"] == list(range(10))
    for seed in (1000, 1029, 1100, 1250, 1399, 5001, 7000, 8600, 9199):
        with pytest.raises(ValueError):
            L.guard_sample([seed])
    with pytest.raises(ValueError):
        L.aliasing(seeds=(3, 1205))
    assert L.guard_sample(range(10)) == tuple(range(10))


def test_regime_delegation_is_detected_and_queried_through():
    eq = {(e["a"], e["b"]): e for e in LEDGER["aliasing"]["equivalences"]}
    gauss = eq[("greg.cognition.genomes.collective:immune_gaussian_instance",
                "greg.cognition.genomes.collective:immune_instance")]
    assert (gauss["modulus"], gauss["residues"]) == (4, [0])
    # P8's immune generator at seed 1200 is the admission v3 collective_immune instance at that seed (1200 % 4 == 0)
    hits = L.exposed("greg.cognition.genomes.collective:immune_gaussian_instance", [1200], LEDGER)
    assert any("2026-10-15-v3" in h["id"] and h["role"] == "admission held-out" for h in hits)
    later = L.exposed("greg.cognition.genomes.collective:immune_gaussian_instance", [1201], LEDGER)
    assert not any("collective_immune" in h["id"] for h in later)      # 1201 % 4 == 1: the mixture regime


def test_the_query_returns_overlaps_by_generator_or_family_and_nothing_for_unused_seeds():
    hits = L.exposed(CR, range(7400, 7460), LEDGER)
    assert [h["role"] for h in hits if "cycle-cr-4" in h["id"]] == ["train"]
    by_family = L.exposed("develop_constraint_release", [1205], LEDGER)
    assert any("2026-10-15-v3" in h["id"] and h["seeds"] == [[1205, 1205]] for h in by_family)
    assert L.exposed(CR, range(9_000_000, 9_000_050), LEDGER) == []


def test_the_forecast_erratum_pattern_is_found_as_shared_data_items():
    same = LEDGER["overlaps"]["same_data_items"]
    pairs = {(o["a"].split("|")[1], o["b"].split("|")[1], tuple(o["roles"])): o["n"] for o in same}
    v2 = "docs/evidence/greg-genome-admission/2026-10-14-v2/freeze.json"
    p8 = "docs/evidence/greg-protected-evolution/2026-10-08/cycle-forecast-1.json"
    shared = sum(n for (a, b, _), n in pairs.items() if {a, b} == {v2, p8})
    held = next(r for r in LEDGER["exposures"] if r["artifact"]["path"] == v2 and r["family"] == "forecast_quantile"
                and r["role"] == "admission held-out")
    assert shared == len(held["series"]) == 30


def test_no_test_fixture_or_pilot_touches_a_held_out_seed_of_the_same_generator():
    for o in LEDGER["overlaps"]["same_generator"]:
        assert not o["involves_heldout"], o
    unresolved = [r for r in LEDGER["exposures"] if not r["generator"].get("resolved")]
    assert all(L.expand(r.get("seeds") or []) <= set(range(10)) for r in unresolved
               if r["program"] == "test fixture"), "an unresolved test generator outside the dev seeds"


def test_counts_add_up_and_every_role_is_known():
    recs = LEDGER["exposures"]
    assert LEDGER["counts"]["exposures"] == len(recs) == len({r["id"] for r in recs})
    assert sum(LEDGER["counts"]["by_role"].values()) == len(recs)
    assert {r["role"] for r in recs} <= set(L.ROLES)
    assert all(r["lineages"] in ([L.L158], [L.L179], [L.L158, L.L179]) for r in recs)
