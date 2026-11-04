"""Directive 2026-10-28 sections 11 and 54: cleanup never deletes a founder intent or a capability horizon.

"Preserve old founder statements even when superseded. Do not silently rewrite history." "CLOSE PR does not mean
DELETE THE INTENT." A committed snapshot lists every intent id and horizon id at a pinned commit. Every one of them
must still be present at HEAD, unless a record present at HEAD names it in its ``supersedes``: the successor that a
``superseded_by`` link points to is what keeps the lineage readable once the old record is gone. The check reads
only the working tree and the snapshot, never git history, so it holds on a shallow CI clone.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil

import pytest

from scripts.ci.check_intent_continuity import KINDS, SNAPSHOT, current_ids, main, missing, successors

ROOT = Path(__file__).resolve().parents[2]
FILES = ("docs/intent", "docs/FOUNDER_INTENT_LEDGER.md", "greg/path.json")


def snapshot() -> dict:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A copy of the files the check reads, which a test may damage."""
    for name in FILES:
        source, target = ROOT / name, tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("sources"))
        else:
            shutil.copy2(source, target)
    return tmp_path


def test_no_id_in_the_pinned_snapshot_is_missing_at_head():
    assert missing(snapshot(), ROOT) == []
    assert main(["--root", str(ROOT)]) == 0


def test_the_snapshot_is_pinned_and_covers_every_kind():
    snap = snapshot()
    assert re.fullmatch(r"[0-9a-f]{40}", snap["pinned_commit"])
    assert set(snap["ids"]) == set(KINDS)
    counts = {kind: len(ids) for kind, ids in snap["ids"].items()}
    assert counts["intent_records"] >= 26 and counts["horizons"] >= 40 and counts["frontier_backcasts"] >= 13, counts
    assert counts["intent_documents"] >= 7 and counts["ledger_records"] >= 10, counts
    for ids in snap["ids"].values():
        assert ids == sorted(set(ids))


def _intent_file(root: Path, intent_id: str) -> Path:
    return root / "docs/intent" / f"{intent_id}.json"


def test_deleting_an_intent_record_fails(tree):
    _intent_file(tree, "INTENT-20260930-open-source-first").unlink()
    assert missing(snapshot(), tree) == [("intent_records", "INTENT-20260930-open-source-first")]
    assert main(["--root", str(tree)]) == 1


def test_renaming_a_record_file_keeps_its_id(tree):
    old = _intent_file(tree, "INTENT-20260930-open-source-first")
    old.rename(old.with_name("renamed-open-source-first.json"))
    assert missing(snapshot(), tree) == []


def test_a_successor_naming_the_id_in_supersedes_lets_it_leave(tree):
    _intent_file(tree, "INTENT-20260930-open-source-first").unlink()
    successor = _intent_file(tree, "INTENT-20261030-BUILD-BEFORE-DEVICE-RUN")
    record = json.loads(successor.read_text(encoding="utf-8"))
    record["supersedes"] = record["supersedes"] + ["INTENT-20260930-open-source-first (merged into this record)"]
    successor.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    assert any("INTENT-20260930-open-source-first" in entry for entry in successors(tree))
    assert missing(snapshot(), tree) == []


def test_a_mention_outside_supersedes_is_not_succession(tree):
    _intent_file(tree, "INTENT-20260930-open-source-first").unlink()
    other = _intent_file(tree, "INTENT-20261030-BUILD-BEFORE-DEVICE-RUN")
    record = json.loads(other.read_text(encoding="utf-8"))
    record["conflicts"] = record["conflicts"] + ["INTENT-20260930-open-source-first was closed in cleanup"]
    record["superseded_by"] = ["INTENT-20260930-open-source-first"]
    other.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    assert missing(snapshot(), tree) == [("intent_records", "INTENT-20260930-open-source-first")]


def test_a_prefix_of_an_id_is_not_succession(tree):
    _intent_file(tree, "INTENT-20260930-open-source-first").unlink()
    other = _intent_file(tree, "INTENT-20261030-BUILD-BEFORE-DEVICE-RUN")
    record = json.loads(other.read_text(encoding="utf-8"))
    record["supersedes"] = record["supersedes"] + ["INTENT-20260930-open-source-first-v2"]
    other.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    assert missing(snapshot(), tree) == [("intent_records", "INTENT-20260930-open-source-first")]


def test_an_intent_inside_a_list_file_counts(tree):
    gravity = _intent_file(tree, "INTENT-20261013-GOAL-GRAVITY")
    data = json.loads(gravity.read_text(encoding="utf-8"))
    data["intents"] = []
    gravity.write_text(json.dumps(data), encoding="utf-8")
    assert ("intent_records", "INTENT-20261013-GOAL-GRAVITY") in missing(snapshot(), tree)


def test_deleting_a_markdown_intent_record_fails(tree):
    (tree / "docs/intent/INTENT-0001-uniimente-as-legal-principal.md").unlink()
    assert missing(snapshot(), tree) == [("intent_documents", "INTENT-0001")]


def test_scrubbing_a_ledger_only_intent_fails(tree):
    ledger = tree / "docs/FOUNDER_INTENT_LEDGER.md"
    ledger.write_text(ledger.read_text(encoding="utf-8").replace("INTENT-20261023-ORGAN-PINS-UPGRADED", "ORGAN-PINS"),
                      encoding="utf-8")
    assert missing(snapshot(), tree) == [("ledger_records", "INTENT-20261023-ORGAN-PINS-UPGRADED")]


def test_a_longer_id_in_the_ledger_does_not_keep_a_shorter_one(tree):
    ledger = tree / "docs/FOUNDER_INTENT_LEDGER.md"
    pins = "INTENT-20261023-ORGAN-PINS-UPGRADED"
    ledger.write_text(ledger.read_text(encoding="utf-8").replace(pins, f"{pins}-AGAIN"), encoding="utf-8")
    assert missing(snapshot(), tree) == [("ledger_records", pins)]


def test_an_intent_the_ledger_only_mentions_is_pinned(tree):
    """Draft #144's intent has no record on this tree; the ledger's mention is what keeps it."""
    harvest = "INTENT-20261001-open-source-mechanism-harvest"
    assert harvest in snapshot()["ids"]["ledger_records"]
    ledger = tree / "docs/FOUNDER_INTENT_LEDGER.md"
    ledger.write_text(ledger.read_text(encoding="utf-8").replace(f"`{harvest}`", "the harvest draft"), encoding="utf-8")
    assert missing(snapshot(), tree) == [("ledger_records", harvest)]


def _path(root: Path) -> dict:
    return json.loads((root / "greg/path.json").read_text())


def test_deleting_a_horizon_fails_unless_a_horizon_supersedes_it(tree):
    data = _path(tree)
    data["horizons"] = [h for h in data["horizons"] if h["id"] != "voice"]
    (tree / "greg/path.json").write_text(json.dumps(data, indent=2))
    assert missing(snapshot(), tree) == [("horizons", "voice")]
    next(h for h in data["horizons"] if h["id"] == "remote_interface_iphone")["supersedes"] = ["voice"]
    (tree / "greg/path.json").write_text(json.dumps(data, indent=2))
    assert missing(snapshot(), tree) == []


def test_deleting_a_frontier_backcast_fails(tree):
    data = _path(tree)
    data["frontier_backcasts"] = [b for b in data["frontier_backcasts"] if b["id"] != "advanced_robotic_embodiment"]
    (tree / "greg/path.json").write_text(json.dumps(data, indent=2))
    assert missing(snapshot(), tree) == [("frontier_backcasts", "advanced_robotic_embodiment")]


def test_head_ids_are_read_from_the_tree_alone(tree):
    ids = current_ids(tree)
    snap = snapshot()["ids"]
    for kind in KINDS:
        assert set(snap[kind]) <= set(ids[kind]), kind
