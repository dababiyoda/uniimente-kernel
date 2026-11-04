"""Directive 2026-10-28 sections 11 and 54: cleanup never deletes a founder intent or a capability horizon.

"Preserve old founder statements even when superseded. Do not silently rewrite history." "CLOSE PR does not mean
DELETE THE INTENT." A committed snapshot lists every intent id and horizon id at a pinned commit. Every one of them
must still be present at HEAD, unless a successor of its kind present at HEAD names it as a whole ``supersedes``
entry: the successor that a ``superseded_by`` link points to is what keeps the lineage readable once the old record
is gone, and prose that only mentions an id releases nothing. A re-pin only adds, and the pinned commit's ids are
frozen here. The check reads only the working tree and the snapshot, never git history, so it holds on a shallow CI
clone.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

import pytest

from scripts.ci.check_intent_continuity import (KINDS, SNAPSHOT, SnapshotError, current_ids, main, missing, pinned,
                                                repin, successors)

ROOT = Path(__file__).resolve().parents[2]
FILES = ("docs/intent", "docs/FOUNDER_INTENT_LEDGER.md", "greg/path.json")
# The ids at the pinned commit, frozen here so that thinning them takes a visible edit of this test, not only of the
# snapshot (a same-change edit of both is still possible; review sees it).
BASE_COMMIT = "44b3df9698a10d054b4ade4bb2ef77b244c3e0d9"
BASE_COUNTS = {"intent_records": 26, "intent_documents": 7, "ledger_records": 36, "horizons": 40,
               "frontier_backcasts": 13}
BASE_SHA256 = "6e3ea06e1e92be212b2aac058476bb96190387ba487089443b2c285c88a02bb0"


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
    """The pinned commit's ids are exactly the ones frozen above: same counts, same digest."""
    snap = snapshot()
    assert snap["pinned_commit"] == BASE_COMMIT
    assert set(snap["ids"]) == set(KINDS)
    assert {kind: len(ids) for kind, ids in snap["ids"].items()} == BASE_COUNTS
    assert hashlib.sha256(json.dumps(snap["ids"], sort_keys=True).encode()).hexdigest() == BASE_SHA256
    for ids in snap["ids"].values():
        assert ids == sorted(set(ids))


def test_later_pins_only_add():
    snap = snapshot()
    seen = {kind: set(ids) for kind, ids in snap["ids"].items()}
    for pin in snap["added"]:
        assert re.fullmatch(r"[0-9a-f]{40}", pin["commit"]) and pin["ids"] and set(pin["ids"]) <= set(KINDS), pin
        for kind, ids in pin["ids"].items():
            assert ids and ids == sorted(set(ids)) and not seen[kind] & set(ids), (pin["commit"], kind)
            seen[kind] |= set(ids)
    assert pinned(snap) == {kind: sorted(ids) for kind, ids in seen.items()}


def _scrub(root: Path, identifier: str, replacement: str) -> None:
    ledger = root / "docs/FOUNDER_INTENT_LEDGER.md"
    ledger.write_text(ledger.read_text(encoding="utf-8").replace(identifier, replacement), encoding="utf-8")


def test_a_repin_refuses_a_deletion_and_only_adds(tree):
    """A cleanup that deletes a ledger-named intent and then re-pins its own commit no longer launders the deletion;
    a re-pin keeps every pinned id and appends the new ones, which are then guarded too."""
    snap = snapshot()
    _scrub(tree, "INTENT-20261021-PROFESSIONAL-PARALLEL-TEAM", "the parallel-team intent")
    with pytest.raises(SnapshotError, match="INTENT-20261021-PROFESSIONAL-PARALLEL-TEAM"):
        repin(snap, "f" * 40, tree)
    _scrub(tree, "the parallel-team intent", "INTENT-20261021-PROFESSIONAL-PARALLEL-TEAM")
    record = tree / "docs/intent/INTENT-20261104-LATER.json"
    record.write_text(json.dumps({"intent_id": "INTENT-20261104-LATER"}), encoding="utf-8")
    after = repin(snap, "e" * 40, tree)
    assert (after["pinned_commit"], after["ids"]) == (snap["pinned_commit"], snap["ids"])
    later = {"commit": "e" * 40, "ids": {"intent_records": ["INTENT-20261104-LATER"]}}
    assert after["added"] == snap["added"] + [later]
    record.unlink()
    assert missing(after, tree) == [("intent_records", "INTENT-20261104-LATER")]


def test_a_lawfully_superseded_id_stays_pinned_after_a_repin(tree):
    _intent_file(tree, "INTENT-20260930-open-source-first").unlink()
    successor = _intent_file(tree, "INTENT-20261030-BUILD-BEFORE-DEVICE-RUN")
    record = json.loads(successor.read_text(encoding="utf-8"))
    named = dict(record, supersedes=record["supersedes"] + ["INTENT-20260930-open-source-first"])
    successor.write_text(json.dumps(named), encoding="utf-8")
    after = repin(snapshot(), "d" * 40, tree)
    assert "INTENT-20260930-open-source-first" in pinned(after)["intent_records"]
    successor.write_text(json.dumps(record), encoding="utf-8")
    assert missing(after, tree) == [("intent_records", "INTENT-20260930-open-source-first")]


def test_write_snapshot_at_head_keeps_the_pinned_ids(tmp_path):
    """The CLI's re-pin through ``git archive``; skipped where the tree is not a git checkout."""
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    if head.returncode != 0:
        pytest.skip("not a git checkout")
    target = tmp_path / "snapshot.json"
    target.write_text(SNAPSHOT.read_text(encoding="utf-8"), encoding="utf-8")
    assert main(["--write-snapshot", "HEAD", "--snapshot", str(target)]) == 0
    old, new = snapshot(), json.loads(target.read_text(encoding="utf-8"))
    assert (new["pinned_commit"], new["ids"]) == (old["pinned_commit"], old["ids"])
    assert all(set(pinned(old)[kind]) <= set(pinned(new)[kind]) for kind in KINDS)


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
    record["supersedes"] = record["supersedes"] + ["INTENT-20260930-open-source-first"]
    successor.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    assert "INTENT-20260930-open-source-first" in successors(tree)["intent"]
    assert missing(snapshot(), tree) == []


def _supersedes(root: Path, intent_id: str, *entries: str) -> None:
    file = _intent_file(root, intent_id)
    record = json.loads(file.read_text(encoding="utf-8"))
    before = record["supersedes"] if isinstance(record["supersedes"], list) else [record["supersedes"]]
    record["supersedes"] = before + list(entries)
    file.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")


def test_prose_that_mentions_an_id_is_not_succession(tree):
    """GOAL-GRAVITY's own record reads "Nothing deleted. Clarifies and extends `INTENT-0030`": a formulation of what
    changed, not a successor link. Prose naming an intent id, or using a horizon id as a word, releases nothing."""
    (tree / "docs/intent/INTENT-0030-effect-not-metaphor.md").unlink()
    _intent_file(tree, "INTENT-20260930-open-source-first").unlink()
    _supersedes(tree, "INTENT-20261014-ONE-MACHINE",
                "Nothing deleted. Clarifies and extends INTENT-0030; keeps model_plurality as written",
                "INTENT-20260930-open-source-first (merged into this record)")
    data = _path(tree)
    data["horizons"] = [h for h in data["horizons"] if h["id"] != "model_plurality"]
    (tree / "greg/path.json").write_text(json.dumps(data, indent=2))
    assert missing(snapshot(), tree) == [("intent_records", "INTENT-20260930-open-source-first"),
                                         ("intent_documents", "INTENT-0030"), ("horizons", "model_plurality")]
    assert main(["--root", str(tree)]) == 1


def test_an_intent_record_cannot_supersede_a_horizon(tree):
    """voice, continuity and robotics are ordinary words. Only a horizon's supersedes releases a horizon; an intent
    record's does not, even when one entry is exactly the horizon id."""
    data = _path(tree)
    data["horizons"] = [h for h in data["horizons"] if h["id"] not in ("continuity", "voice", "robotics")]
    (tree / "greg/path.json").write_text(json.dumps(data, indent=2))
    _supersedes(tree, "INTENT-20261030-BUILD-BEFORE-DEVICE-RUN",
                "The older assumption that continuity, voice or robotics must wait for a second device", "voice")
    assert missing(snapshot(), tree) == [("horizons", "continuity"), ("horizons", "robotics"), ("horizons", "voice")]
    assert main(["--root", str(tree)]) == 1


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
    _scrub(tree, "INTENT-20261023-ORGAN-PINS-UPGRADED", "ORGAN-PINS")
    assert missing(snapshot(), tree) == [("ledger_records", "INTENT-20261023-ORGAN-PINS-UPGRADED")]


def test_a_longer_id_in_the_ledger_does_not_keep_a_shorter_one(tree):
    ledger = tree / "docs/FOUNDER_INTENT_LEDGER.md"
    pins = "INTENT-20261023-ORGAN-PINS-UPGRADED"
    ledger.write_text(ledger.read_text(encoding="utf-8").replace(pins, f"{pins}-AGAIN"), encoding="utf-8")
    assert missing(snapshot(), tree) == [("ledger_records", pins)]


def test_an_intent_the_ledger_only_mentions_is_pinned(tree):
    """Draft #144's intent has no record on this tree; the ledger's mention is what keeps it."""
    harvest = "INTENT-20261001-open-source-mechanism-harvest"
    assert harvest in snapshot()["ids"]["ledger_records"] and harvest in current_ids(ROOT)["ledger_records"]
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
    """A copy of the files the check reads, without git history, gives the repository's ids; missing() and the CLI
    apply the one documented rule to it."""
    assert current_ids(tree) == current_ids(ROOT)
    assert missing(snapshot(), tree) == []
    assert main(["--root", str(tree)]) == 0


def test_every_lawful_path_passes_the_check_and_the_cli(tree):
    """The documented ways an id may leave its place, together: a successor's supersedes, a markdown record becoming
    JSON, and an id the ledger names becoming a record. missing(), the CLI and pytest agree."""
    _intent_file(tree, "INTENT-20260930-open-source-first").unlink()
    _supersedes(tree, "INTENT-20261030-BUILD-BEFORE-DEVICE-RUN", "INTENT-20260930-open-source-first")
    (tree / "docs/intent/INTENT-0001-uniimente-as-legal-principal.md").unlink()
    _intent_file(tree, "INTENT-0001").write_text(json.dumps({"intent_id": "INTENT-0001"}), encoding="utf-8")
    _scrub(tree, "INTENT-20261023-ORGAN-PINS-UPGRADED", "ORGAN-PINS")
    _intent_file(tree, "INTENT-20261023-ORGAN-PINS-UPGRADED").write_text(
        json.dumps({"intent_id": "INTENT-20261023-ORGAN-PINS-UPGRADED"}), encoding="utf-8")
    assert missing(snapshot(), tree) == []
    assert main(["--root", str(tree)]) == 0
