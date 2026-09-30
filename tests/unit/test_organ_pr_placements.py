"""Every open organ PR has a place on the one developmental path (directive section 53).

"Before closing or superseding a PR, extract: founder intention represented; intended effect;
useful mechanisms; evidence; negative evidence; remaining capability gap; new canonical owner;
new developmental node; prerequisites. Closing a PR does not close the founder intention."
"""
from __future__ import annotations

import json
from pathlib import Path

from greg import path as devpath

ROOT = Path(__file__).resolve().parents[2]
RECORD = json.loads((ROOT / "docs/collaboration/ORGAN-PR-PLACEMENTS-2026-09-30.json").read_text())
ORGANS = {"DALEOBANKS", "WealthMachineIntelligence", "RAILSCOUT", "RESEARCH-IN", "PumpStation",
          "gods-eye-view-EGGREGORE-TOOL", "build-your-own-x"}


def test_each_placement_uses_the_path_vocabulary_and_keeps_the_intent():
    nodes = {n["id"] for n in devpath.load()["nodes"]}
    ids = [p["id"] for p in RECORD["placements"]]
    assert len(ids) == len(set(ids)) == 78
    for p in RECORD["placements"]:
        assert p["classification"] in devpath.CLASSES, p["id"]
        assert p["disposition"] in RECORD["dispositions"], p["id"]
        assert p["node"] in nodes and p["intended_effect"].strip() and p["basis"].strip(), p["id"]
        assert p["intended_effect_status"] == "active", p["id"]            # closing a PR never closes the intent
        assert set(p["measured"]) == {"ahead", "behind", "files", "conflicts"}, p["id"]


def test_superseding_names_what_replaced_it_on_main():
    for p in RECORD["placements"]:
        if p["disposition"] == "SUPERSEDED IMPLEMENTATION":
            assert "main" in p["basis"] and "verified" in p["basis"], p["id"]


def test_every_organ_is_covered_and_its_propagation_is_receipted():
    assert {p["id"].split("#")[0] for p in RECORD["placements"]} == ORGANS
    surfaces = RECORD["propagation_receipt"]["surfaces"]
    assert set(surfaces) == ORGANS
    for repo, receipt in surfaces.items():
        assert receipt["draft_pr"].startswith(f"https://github.com/dababiyoda/{repo}/pull/") and "AGENTS.md" in receipt["updated"]
        assert receipt["merged"] is False                                    # a receipt never claims a merge it did not see


def test_the_security_finding_stays_visible_until_decided():
    pump = next(p for p in RECORD["placements"] if p["id"] == "PumpStation#16")
    assert pump["disposition"] == "NEEDS FOUNDER DECISION" and pump["basis"].startswith("SECURITY")
    assert any(f.startswith("SECURITY") for f in RECORD["findings"])
