"""The cognition lineage registry: every competing Seed Genome implementation is
registered with an implementation id, measured results and a disposition that
creates no authority (Final Build Order §3, §9, §13)."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = json.loads((ROOT / "docs/cortex/COGNITION_LINEAGES.json").read_text(encoding="utf-8"))
REQUIRED = {"implementation_id", "pr", "head", "commits_ahead_of_main", "contains_pr137", "diff_vs_main", "title",
            "branch", "package", "base", "author", "disposition", "lineage_relation", "measured_results",
            "carried_into_this_branch", "authority_created"}


def test_every_lineage_is_complete_and_unique():
    rows = REGISTRY["lineages"]
    assert len(rows) >= 14
    ids = [r["implementation_id"] for r in rows]
    assert len(ids) == len(set(ids))
    for r in rows:
        assert REQUIRED <= set(r), sorted(REQUIRED - set(r))
        assert r["implementation_id"] == f"cognition-lineage/pr-{r['pr']}"
        assert r["disposition"] in REGISTRY["dispositions"]
        assert r["authority_created"] is False
        assert r["measured_results"].strip() and r["carried_into_this_branch"].strip()


def test_only_main_compatible_lineages_are_carried_into_main_facing_work():
    for r in REGISTRY["lineages"]:
        if r["disposition"] in ("PRODUCTIZE", "RECOMBINE"):
            assert r["contains_pr137"] is False, r["pr"]
            assert r["base"] == "main"
        if r["contains_pr137"]:
            assert r["disposition"].startswith("RETAIN_AS_EVIDENCE"), r["pr"]
            assert "Nothing merged" in r["carried_into_this_branch"], r["pr"]


def test_exactly_one_lineage_is_the_productized_base():
    base = [r for r in REGISTRY["lineages"] if r["disposition"] == "PRODUCTIZE"]
    assert [r["pr"] for r in base] == [141]
    assert any(r["pr"] == 139 and r["disposition"] == "RECOMBINE" for r in REGISTRY["lineages"])
