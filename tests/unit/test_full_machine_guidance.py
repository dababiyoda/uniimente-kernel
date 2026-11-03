"""The 2026-10-02 full-machine correction stays binding where agents enter, and no cortex path node parks
buildable work behind founder use (INTENT-20261002-FULL-MACHINE-CONTINUATION).

Body + Organs + Mind is the completion boundary. A node may wait only on a named founder-only action, a genuine
external dependency or a demonstrated technology limit; everything else is work now.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = "docs/intent/sources/FULL-MACHINE-COMPLETION-CORRECTION-20261002.md"
ENTRY = ["AGENTS.md", "CLAUDE.md", ".github/copilot-instructions.md", "README.md", "docs/BUILD_ORDER.md",
         "docs/UNIIMENTE_FINAL_BUILD_ORDER.md", "docs/CANONICAL_EXECUTION_ORDER.md", "docs/FOUNDER_EFFECT_COMPILER.md",
         "docs/RECURSIVE_COLLABORATION_PROTOCOL.md", "docs/FOUNDER_INTENT_LEDGER.md"]
CLASSES = {"DONE_IN_TESTED_ENVIRONMENT", "BUILDABLE_NOW", "SEQUENCED", "FOUNDER_ONLY", "EXTERNAL_DEPENDENCY",
           "TECHNOLOGY_LIMIT"}
WAITS = {"FOUNDER_ONLY", "EXTERNAL_DEPENDENCY", "TECHNOLOGY_LIMIT"}


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def cortex_nodes():
    path = json.loads(read("greg/path.json"))
    [ws] = [w for w in path["workstreams"] if w["id"] == "cognition_cortex"]
    return {n["id"]: n for n in ws["nodes"]}


def test_every_entry_surface_carries_the_boundary_and_its_source():
    assert (ROOT / SOURCE).is_file()
    for rel in ENTRY:
        text = read(rel)
        assert "BODY + ORGANS + MIND" in text, rel
        assert Path(SOURCE).name in text, rel


def test_the_sop_keeps_vepmc_as_an_item_gate_and_one_delta_is_not_an_exit():
    sop = read("docs/PROJECT_COGNITION_SOP.md")
    section_8 = sop.split("## 8.")[1].split("## 9.")[0]
    assert "Superseded 2026-10-02" in section_8 and "item-specific gate" in section_8
    assert "VEPMC 0 -> 1" in section_8                       # the old line is preserved, marked superseded
    assert "not the stopping condition" in sop.split("## 22.")[1]


def test_every_cortex_node_names_its_completion_class_and_what_any_wait_is_on():
    nodes = cortex_nodes()
    for nid, node in nodes.items():
        completion = node["completion"]
        assert completion["class"] in CLASSES, nid
        if completion["class"] in WAITS:
            assert completion.get("wait"), f"{nid} waits without naming what on"
        if completion["class"] == "BUILDABLE_NOW":
            assert completion.get("build_now"), f"{nid} is buildable but names nothing to build"
        if completion["class"] == "SEQUENCED":
            after = completion["after"]
            assert after and set(after) <= set(nodes), nid
            # A node sequenced after a waiting node is itself waiting; say so instead.
            assert not {nodes[a]["completion"]["class"] for a in after} & WAITS, nid


def test_a_claim_gate_never_stands_in_for_buildable_machinery():
    for nid, node in cortex_nodes().items():
        completion = node["completion"]
        if "claim_gate" in completion and completion["class"] not in ("DONE_IN_TESTED_ENVIRONMENT",):
            assert completion["class"] in ("BUILDABLE_NOW", "SEQUENCED"), nid


def test_every_unfinished_seed_requirement_resolves_to_a_node_that_says_what_it_waits_on():
    import re
    ledger = json.loads(read("docs/collaboration/requirements-greg-seed-genome-20261001.json"))
    nodes = cortex_nodes()
    done = {"VERIFIED_IN_TESTED_ENVIRONMENT", "INTEGRATED", "IMPLEMENTED"}
    for row in ledger["requirements"]:
        if row["implementation_state"] in done:
            continue
        gate = re.match(r"(P\d+|N1)\b", row["next_gate"])
        assert gate, (row["requirement_id"], row["next_gate"])
        if gate.group(1) != "N1":                         # N1 is the founder's device run (FOUNDER_ONLY)
            assert nodes[gate.group(1)]["completion"]["class"] in CLASSES, row["requirement_id"]


def test_greg_path_shows_the_work_queue_and_names_every_wait():
    from greg.path import full_machine, load, position
    view = full_machine(load())
    building = {r["node"] for r in view["build_now"]}
    waiting = {r["node"]: r["wait"] for r in view["waits"]}
    assert {"P4", "P5", "P8", "P10"} <= building and not building & set(waiting)
    assert {"P12", "P13"} <= set(waiting) and all(waiting.values())
    assert {r["node"]: r["after"] for r in view["sequenced"]}["P9"] == ["P6", "P8"]
    assert any(r["node"] == "P2" for r in view["claim_gates"])        # model arms wait; P2 is still done
    assert position(None)["full_machine"] == view                     # `greg path` carries it
