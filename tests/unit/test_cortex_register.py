"""Cortex seed — both AI review passes, section by section, against a disposition.

``docs/cortex/verbatim-register.json`` gives every numbered section of review
passes 1 and 2 (plus each preamble and pass 2's closing build list and decisive
test) one row: a disposition, resolvable evidence, and a backcast node for
anything not achievable now. Classification lists carry one status per item.
Nothing in the review may silently disappear, and nothing may be claimed
without evidence.
"""
import json
import pathlib
import re

import pytest

from cortex.evidence_refs import resolve, slug
from cortex.genome import seed_registry

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTER = json.loads((ROOT / "docs/cortex/verbatim-register.json").read_text(encoding="utf-8"))
ROWS = REGISTER["rows"]
BACKCAST = (ROOT / "docs/cortex/BACKCAST_GPS_CORTEX.md").read_text(encoding="utf-8")


def _body(letter):
    text = (ROOT / REGISTER["sources"][letter]).read_text(encoding="utf-8")
    return text.split("=== BEGIN VERBATIM TEXT ===\n", 1)[1].split("=== END VERBATIM TEXT ===", 1)[0]


BODIES = {"A": _body("A"), "B": _body("B")}


def test_every_numbered_section_has_exactly_one_row():
    for letter, total in (("A", 53), ("B", 64)):
        numbers = []
        for m in re.finditer(r"⸻\n\n(\d+)\. ", BODIES[letter]):
            n = int(m.group(1))
            if n not in numbers:          # B32's inner list items "2." and "3." repeat earlier numbers
                numbers.append(n)
        assert numbers == list(range(1, total + 1)), letter
        ids = [r["id"] for r in ROWS if r["pass"] == letter]
        expected = [f"{letter}00"] + [f"{letter}{n:02d}" for n in range(1, total + 1)]
        assert ids[:total + 1] == expected
    assert [r["id"] for r in ROWS][-2:] == ["B65", "B66"]
    assert len({r["id"] for r in ROWS}) == len(ROWS)


def test_anchors_are_verbatim():
    for r in ROWS:
        assert r["anchor"] in BODIES[r["pass"]], f"{r['id']}: anchor not verbatim"


def test_dispositions_backcast_and_items_are_well_formed():
    nodes = set(REGISTER["backcast_nodes"])
    for r in ROWS:
        assert r["disposition"] in REGISTER["dispositions"], r["id"]
        assert r["evidence"] and r["notes"], r["id"]
        if r["disposition"] in ("pursued_goal", "implemented_partial", "reserved_profile"):
            assert r["backcast"] in nodes, f"{r['id']}: a not-yet-complete row needs a backcast node"
        for item in r["items"] or []:
            assert item["status"] in REGISTER["item_statuses"], (r["id"], item)
            assert f"* {item['text']}" in BODIES[r["pass"]], (r["id"], item["text"])
            if item["status"] == "pursued":
                assert item["where"] in nodes, (r["id"], item)


def test_classification_lists_are_complete():
    for r in ROWS:
        if not r["items"]:
            continue
        heading = BODIES[r["pass"]].index(r["anchor"])
        nxt = BODIES[r["pass"]].find("⸻", heading)
        listed = re.findall(r"^\* (.+)$", BODIES[r["pass"]][heading:nxt if nxt > 0 else None], re.M)
        assert [i["text"] for i in r["items"]] == listed, r["id"]


def test_reserved_claims_name_registered_disabled_families():
    registry = seed_registry()
    names = {k.split("@")[0]: registry.get(k).profile.enabled for k in registry.keys()}
    for r in ROWS:
        for item in r["items"] or []:
            if item["status"] == "reserved":
                assert names.get(item["where"]) is False, (r["id"], item)
            if item["status"] == "implemented" and item["where"].startswith("cortex.") and "@" not in item["where"] \
                    and " " not in item["where"] and item["where"] in names:
                assert names[item["where"]] is True, (r["id"], item)


def test_backcast_names_every_node():
    headings = {slug(h) for h in re.findall(r"^#{1,6}\s+(.+)$", BACKCAST, re.M)}
    for k in range(1, 7):
        assert any(h.startswith(f"node-{k}-") for h in headings), k
    assert "destinations-beyond-node-6" in headings
    assert "reconciliation-with-the-reviews-backcasts" in headings


@pytest.mark.parametrize("ref", sorted({ref for r in ROWS for ref in r["evidence"]}))
def test_evidence_resolves(ref):
    resolve(ROOT, ref)
