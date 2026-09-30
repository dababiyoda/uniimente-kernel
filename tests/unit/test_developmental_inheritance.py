"""The founder's 2026-09-30 developmental-inheritance correction, as a test.

"Founder corrections do not automatically invalidate all architecture built under an
earlier assumption." "Never use OUTDATED as a terminal classification by itself."
"No material founder intention may disappear merely because its original
implementation disappears." "At all times identify exactly one operationally
primary developmental node." (INTENT-2026-09-30-DEVELOPMENTAL-INHERITANCE)
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re
import subprocess

import pytest

from greg import metrics
from greg import path as devpath
from greg.body import Body
from tests.greg_fixtures import make_body

ROOT = Path(__file__).resolve().parents[2]
PLACEMENTS = ROOT / "docs/collaboration/DEVELOPMENTAL-INHERITANCE-2026-09-30.json"
RECONCILIATION = ROOT / "docs/collaboration/GREG-RECONCILIATION-2026-09-30.json"

# The founder's own capability lists (2026-09-30 message and directive section 1), verbatim.
FOUNDER_HORIZONS = [
    "richer computer use", "additional hardware", "Mac support", "more powerful local compute", "agent organizations",
    "business autonomy", "human work integration", "robotics", "physical systems", "multi-body deployment",
    "future technology absorption", "broad computer control", "persistent autonomous goal pursuit",
    "many heterogeneous tools", "dynamic agent organizations", "human-AI institutions", "complete business operation",
    "functional regeneration", "self-repair", "multiple physical bodies", "distributed compute", "economic compounding",
    "community feedback", "physical-world capabilities", "increasingly general resourcefulness",
    "Jarvis-like integrated behavior", "future-technology absorption", "persistent identity",
    "durable institutional memory", "persistent goals", "long-running missions", "conversation", "voice",
    "multimodal perception", "reasoning", "multiple model providers", "local models", "computer use", "browser use",
    "filesystem use", "coding", "software generation", "tools", "APIs", "plugins/connectors", "databases", "workflows",
    "SOPs", "specialized AI workers", "temporary multi-agent organizations", "persistent specialist organs",
    "human workers", "businesses", "economic resources", "local compute", "cloud compute",
    "multiple physical computing bodies", "sensors", "actuators", "future robotics or physical capabilities",
    "future technologies not currently known",
]
# Every kernel PR open on 2026-09-30 except this one (#137), read from the GitHub API with pagination.
# Negative evidence: the first pass read one page and missed the 30 July PRs (#11-#62); they were
# found and placed later the same day (placements kernel_sdk_extraction_11_16 ... pr58_62_developmental_substrate).
OPEN_KERNEL_PRS = {11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 35, 44, 46, 51,
                   52, 53, 54, 55, 56, 57, 58, 59, 60, 62, 63, 64, 66, 68, 70, 71, 72, 73, 76, 77,
                   78, 79, 81, 83, 85, 86, 87, 88, 90, 92, 93, 94, 95, 97, 101, 102, 105, 108, 109, 110,
                   111, 113, 114, 115, 118, 119, 120, 121, 122, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134}
# The founder's worked example: a Mac-first lineage after the Chromebook correction.
FOUNDER_MAC_EXAMPLE = {
    "mac.first_body_assumption": {"SUPERSEDED_IMPLEMENTATION_ASSUMPTION"},
    "mac.persistent_body_mechanisms": {"CURRENT_NODE_IMPLEMENTATION", "PORTABLE_MECHANISM"},
    "mac.device_independent_runtime": {"CURRENT_NODE_IMPLEMENTATION"},
    "mac.visual_computer_use": {"FUTURE_NODE_CAPABILITY", "REQUIRES_ADAPTATION"},
    "mac.higher_compute_workstation": {"FUTURE_NODE_CAPABILITY"},
    "mac.multi_body": {"FUTURE_NODE_CAPABILITY"},
}


def placements() -> dict:
    return json.loads(PLACEMENTS.read_text())


def test_the_path_and_the_placements_obey_the_rules():
    devpath.validate_placements(placements(), devpath.load())


def test_every_founder_named_capability_stays_on_the_path():
    covered = {c.lower() for h in devpath.load()["horizons"] for c in h["covers"]}
    missing = [phrase for phrase in FOUNDER_HORIZONS if phrase.lower() not in covered]
    assert not missing, f"founder horizons dropped from greg/path.json: {missing}"


def test_every_open_kernel_pr_is_placed_on_the_path():
    placed = {int(m) for p in placements()["placements"] for item in p["lineage"]
              for m in re.findall(r"^#(\d+)", item)}
    assert OPEN_KERNEL_PRS <= placed, sorted(OPEN_KERNEL_PRS - placed)


def test_the_mac_lineage_is_decomposed_not_discarded():
    by_id = {p["id"]: p for p in placements()["placements"]}
    for pid, allowed in FOUNDER_MAC_EXAMPLE.items():
        assert pid in by_id and by_id[pid]["classification"] in allowed, pid
        assert by_id[pid]["intended_effect_status"] == "active", pid
    mac_specific = [p for p in by_id.values() if p["id"].startswith("mac.")]
    assert not any(p["classification"] == "GENUINELY_OBSOLETE" for p in mac_specific)
    assert "current_hardware" in by_id["mac.first_body_assumption"]["changed_axes"]
    mac_horizon = next(h for h in devpath.load()["horizons"] if "Mac support" in h["covers"])
    assert mac_horizon["node"] == "N8" and mac_horizon["feasibility"] != "CURRENTLY_SCIENCE_FICTION"


def test_no_active_record_uses_a_terminal_outdated_label():
    def labels(value):
        if isinstance(value, dict):
            for key, inner in value.items():
                if key in ("classification", "disposition") and isinstance(inner, str):
                    yield inner
                yield from labels(inner)
        elif isinstance(value, list):
            for inner in value:
                yield from labels(inner)
    for record in (placements(), json.loads(RECONCILIATION.read_text())):
        for label in labels(record):
            if label in devpath.CLASSES:          # e.g. SUPERSEDED_IMPLEMENTATION_ASSUMPTION is decomposed, not terminal
                continue
            first = re.split(r"[\s_/(]", label.strip().upper())[0]
            assert first not in devpath.TERMINAL_WORDS, f"terminal label {label!r}"


def test_referenced_local_mechanisms_exist():
    def local(ref: str):
        token = ref.split()[0]
        if token.startswith("#") or ":" in token or token == "branch" or not ("/" in token or "." in token):
            return None
        return token
    refs = []
    for p in placements()["placements"]:
        refs += p.get("surviving_mechanisms", []) + p.get("evidence_refs", []) + \
            p.get("obsolescence_basis", {}).get("refs", [])
    data = devpath.load()
    for h in data["horizons"]:
        refs += h["nearest_precursor"]
    for n in data["nodes"]:
        refs += n.get("evidence_refs", [])
    missing = sorted({t for t in map(local, refs) if t and not (ROOT / t).exists()})
    assert not missing, missing


@pytest.mark.parametrize("mutate, message", [
    (lambda p: p.update(classification="OUTDATED"), "never a terminal"),
    (lambda p: p.update(classification="SUPERSEDED"), "never a terminal"),
    (lambda p: p.update(changed_axes=["vibes"]), "changed_axes"),
    (lambda p: p.update(changed_axes=[]), "name the axis"),
    (lambda p: p["inheritance_test"].pop("q9_cheapest_distinguishing_test"), "inheritance test"),
    (lambda p: p.update(intended_effect_status="abandoned"), "explicit founder decision"),
    (lambda p: p.update(changed_axes=["final_intended_effect"]), "changes the destination"),
])
def test_each_rule_rejects_a_bad_placement(mutate, message):
    record = copy.deepcopy(placements())
    target = next(p for p in record["placements"] if p["id"] == "mac.first_body_assumption")
    mutate(target)
    with pytest.raises(devpath.PathError, match=message):
        devpath.validate_placements(record)


def test_genuine_obsolescence_needs_a_founder_given_basis():
    record = copy.deepcopy(placements())
    target = next(p for p in record["placements"] if p["classification"] == "GENUINELY_OBSOLETE")
    target["obsolescence_basis"] = {"kind": "felt_old", "refs": ["x"]}
    with pytest.raises(devpath.PathError, match="genuine obsolescence"):
        devpath.validate_placements(record)
    target["obsolescence_basis"] = {"kind": "effect_no_longer_wanted", "refs": ["x"]}
    with pytest.raises(devpath.PathError, match="founder's own words"):
        devpath.validate_placements(record)


def test_an_archived_implementation_left_the_tree_and_its_behaviours_are_still_tested():
    """Directive section 76: archive only when justified; the intent and the behaviours stay."""
    archived = [p for p in placements()["placements"] if p.get("archived")]
    assert archived, "section 76 names egregore/local_console.py; its archive must stay recorded"
    shallow = subprocess.run(["git", "rev-parse", "--is-shallow-repository"], cwd=ROOT, capture_output=True,
                             text=True).stdout.strip() != "false"
    for p in archived:
        record = p["archived"]
        assert p["intended_effect_status"] == "active", p["id"]       # the implementation leaves; the intent stays
        for path in record["paths"]:
            assert not (ROOT / path).exists(), f"{path} is archived but still in the active tree"
            if not shallow:                                              # CI checks out one commit; locally, prove restorability
                assert subprocess.run(["git", "cat-file", "-e", f"{record['last_commit']}:{path}"], cwd=ROOT).returncode == 0
        for old, carriers in record["behaviours_carried"].items():
            assert carriers, old
            for carrier in carriers:
                file, name = carrier.split("::")
                assert re.search(rf"^def {re.escape(name)}\(", (ROOT / file).read_text(), re.M), carrier


@pytest.mark.parametrize("mutate, message", [
    (lambda p: p.update(classification="PORTABLE_MECHANISM"), "only a superseded or genuinely obsolete"),
    (lambda p: p["archived"].pop("last_commit"), "last commit"),
    (lambda p: p["archived"].update(paths=[]), "every path removed"),
    (lambda p: p["archived"].pop("behaviours_carried"), "canonical mechanism and tests"),
])
def test_an_archive_without_its_lineage_is_refused(mutate, message):
    record = copy.deepcopy(placements())
    target = next(p for p in record["placements"] if p.get("archived"))
    mutate(target)
    with pytest.raises(devpath.PathError, match=message):
        devpath.validate_placements(record)


def test_evidence_without_refs_is_unresolved_and_later_horizons_name_prerequisites():
    data = devpath.load()
    bad = copy.deepcopy(data)
    bad["nodes"][3]["evidence_status"] = "verified_by_execution"          # N3 has no refs
    with pytest.raises(devpath.PathError, match="unresolved"):
        devpath.validate(bad)
    bad = copy.deepcopy(data)
    later = next(h for h in bad["horizons"] if h["feasibility"] == "REQUIRES_ECONOMIC_SCALE")
    later.pop("prerequisite")
    with pytest.raises(devpath.PathError, match="prerequisite"):
        devpath.validate(bad)


def test_exactly_one_primary_node_and_it_moves_only_on_ledger_evidence(tmp_path, monkeypatch):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        journal = body.journal
        where = devpath.position(journal)
        assert where["achieved"] == ["N0"] and where["active"]["id"] == "N1" and where["next"]["id"] == "N2"
        assert where["active"]["measurement"]["met"] is False

        counted = {"VEPMC": 1, "external_confirmation_required": "x",
                   "missions": [{"mission_id": "m:brief", "counts": True, "missing": []}]}
        monkeypatch.setattr(metrics, "vepmc", lambda j: counted)
        where = devpath.position(journal)
        assert where["active"]["id"] == "N2" and where["achieved"] == ["N0", "N1"]

        # A deficit resolved by a BUILTIN, or after the closure, is not a novel-capability closure.
        journal.record("deficit.opened", {"deficit_id": "d1", "mission_id": "m:brief", "function": "f"}, key="d1")
        journal.record("deficit.resolved", {"deficit_id": "d1", "capability_id": "fs.read", "mission_id": "m:brief"},
                       key=["d1", "resolved"])
        journal.record("mission.achieved", {"mission_id": "m:brief"}, key=["m:brief", "achieved"])
        journal.record("deficit.opened", {"deficit_id": "d2", "mission_id": "m:brief", "function": "g"}, key="d2")
        journal.record("deficit.resolved", {"deficit_id": "d2", "capability_id": "built:late", "mission_id": "m:brief"},
                       key=["d2", "resolved"])
        assert devpath.position(journal)["active"]["id"] == "N2"

        counted["missions"].append({"mission_id": "m:genesis", "counts": True, "missing": []})
        journal.record("deficit.opened", {"deficit_id": "d3", "mission_id": "m:genesis", "function": "h"}, key="d3")
        journal.record("deficit.resolved", {"deficit_id": "d3", "capability_id": "built:abc", "mission_id": "m:genesis"},
                       key=["d3", "resolved"])
        journal.record("mission.achieved", {"mission_id": "m:genesis"}, key=["m:genesis", "achieved"])
        where = devpath.position(journal)
        assert where["achieved"] == ["N0", "N1", "N2"] and where["active"]["id"] == "N3"
        assert where["active"]["measurement"]["not_yet_measurable"]          # never counted as passed


def test_an_availability_decision_opens_a_pull_forward_seam_without_changing_the_primary_node(tmp_path):
    home, *_ = make_body(tmp_path)
    with Body(home) as body:
        body.journal.record("decision.requested", {"request_id": "req-presence-x", "kind": "BODY_AVAILABILITY",
                                                   "mission_id": None}, key="req-presence-x")
        where = devpath.position(body.journal)
    assert where["active"]["id"] == "N1"
    assert [s["node"] for s in where["pull_forward_seams"]] == ["N8"]
