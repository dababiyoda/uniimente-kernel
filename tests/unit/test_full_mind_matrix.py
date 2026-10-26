"""Full Mind Completion Matrix integrity and register-coverage checks.

The matrix is an evidence index, not a capability claim.  These tests enforce the
founder directive's 17 columns, honest dual status labels and the rule that no
unfinished material intelligence may silently disappear from the matrix.
"""

import collections
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "docs" / "cortex" / "full-mind-matrix"
CHUNKS = (
    "matrix-l1-l2.json",
    "matrix-l3.json",
    "matrix-l4.json",
    "matrix-l5-genesis.json",
    "matrix-canonical.json",
)
CAPABILITY = {
    "IMPLEMENTED",
    "PARTIALLY IMPLEMENTED",
    "BUILDABLE NOW",
    "EXPERIMENTAL",
    "FRONTIER",
    "BLOCKED",
    "SCIENCE-FICTION-LONG-HORIZON",
}
LADDER = {
    "DECLARED",
    "SCAFFOLDED",
    "IMPLEMENTED",
    "INTEGRATED",
    "TESTED",
    "INDEPENDENTLY VERIFIED",
    "USED BY GREG",
    "REAL-WORLD VALIDATED",
}
UNFINISHED = {"implemented_partial", "reserved_profile", "pursued_goal"}


def load_rows():
    rows = []
    for name in CHUNKS:
        document = json.loads((MATRIX / name).read_text())
        assert document["schema"] == "full-mind-completion-matrix/0.1"
        for row in document["rows"]:
            rows.append((name, document, row))
    return rows


def test_every_row_has_all_seventeen_directive_columns_and_honest_status():
    rows = load_rows()
    assert len(rows) >= 100
    for name, document, row in rows:
        for column in document["column_contract"]:
            assert column in row, (name, row["id"], column)
            assert row[column] not in (None, "", []), (name, row["id"], column)
        assert len(document["column_contract"]) == 17
        assert row["status"]["capability"] in CAPABILITY
        assert row["status"]["evidence_ladder"] in LADDER
        if row["status"]["evidence_ladder"] == "REAL-WORLD VALIDATED":
            assert not row["real_world_evidence"].lower().startswith("none")


def test_row_ids_and_register_lineage_have_one_canonical_home():
    ids = collections.defaultdict(list)
    lineage = collections.defaultdict(list)
    for name, _document, row in load_rows():
        ids[row["id"]].append(name)
        for register_id in row["register_lineage"]:
            lineage[register_id].append(row["id"])
    assert {key: value for key, value in ids.items() if len(value) != 1} == {}
    assert {key: value for key, value in lineage.items() if len(value) != 1} == {}


def test_all_eighty_unfinished_register_rows_are_covered_exactly_once():
    register = json.loads((ROOT / "docs" / "cortex" / "verbatim-register.json").read_text())
    register_rows = {row["id"]: row for row in register["rows"]}
    unfinished = {
        row_id for row_id, row in register_rows.items()
        if row["disposition"] in UNFINISHED
    }
    assert len(unfinished) == 80
    lineage = {}
    for _name, _document, row in load_rows():
        for register_id in row["register_lineage"]:
            assert register_id in register_rows, (row["id"], register_id)
            lineage[register_id] = row["id"]
    assert set(lineage) >= unfinished
    assert sorted(unfinished - set(lineage)) == []


def test_reserved_and_pursued_lineage_cannot_be_relabeled_complete():
    register = json.loads((ROOT / "docs" / "cortex" / "verbatim-register.json").read_text())
    dispositions = {row["id"]: row["disposition"] for row in register["rows"]}
    for _name, _document, row in load_rows():
        row_dispositions = {dispositions[item] for item in row["register_lineage"]}
        if "reserved_profile" in row_dispositions:
            assert row["status"]["capability"] != "IMPLEMENTED", row["id"]
        # A pursued programme may coexist with a real partial mechanism (N3
        # composition is the example), but no pursued goal may be relabeled as
        # a completed capability merely because some precursor exists.
        if "pursued_goal" in row_dispositions:
            assert row["status"]["capability"] != "IMPLEMENTED", row["id"]


def test_directive_layers_and_materially_distinct_concepts_are_present():
    ids = {row["id"] for _name, _document, row in load_rows()}
    assert {"L1-FAMILY", "L2-FAMILY", "L3-FAMILY", "L4-FAMILY", "L5-FAMILY"} <= ids
    assert {f"L1-P{number:02d}" for number in range(1, 23)} <= ids
    organ_ids = {
        "L3-A-SEMANTIC", "L3-B-EXACT", "L3-C-FERMI", "L3-D-FORMAL",
        "L3-E-CONSTRAINT", "L3-F-OPTIMIZATION", "L3-G-GRAPH", "L3-H-SEARCH",
        "L3-I-PROBABILISTIC", "L3-J-CAUSAL", "L3-K-CONTROL", "L3-L-SEQUENTIAL",
        "L3-M-ACTIVE-INFERENCE", "L3-N-VOI", "L3-O-PATTERN", "L3-P-SIMULATION",
        "L3-Q-GAME", "L3-R-MECHANISM-DESIGN", "L3-S-ADVERSARIAL",
        "L3-T-MENTAL-MODELS", "L3-U-HUMAN", "L3-V-MODEL-ROUTING",
        "L3-W-PROGRAM-SYNTHESIS", "L3-X-MICA-CDPE", "L3-Y-LEVIN-DEVELOPMENTAL",
    }
    assert organ_ids <= ids
    assert {
        "L4-ENSEMBLE", "L4-QUORUM", "L4-CROSS-INHIBITION", "L4-STIGMERGIC",
        "L4-SWARM", "L4-SLIME-MOLD", "L4-IMMUNE", "L4-ECOLOGICAL", "L4-MARKET",
        "L4-EVOLUTIONARY", "L4-CONSTRAINT-RELEASE", "L4-TEMPORARY-TISSUES",
        "L4-SHARED-WORKSPACES", "L4-FUNCTIONAL-MORPHOGENESIS",
    } <= ids
    assert {
        "L5-PROBLEMGEOMETRY", "L5-EPISTEMIC-TYPING", "L5-PROOF-CARRYING",
        "L5-INDEPENDENT-VERIFICATION", "L5-ABSTENTION", "L5-COGNITIVE-DEGENERACY",
        "L5-COGNITIVE-ROUTING", "L5-COGNITIVE-COMPOSITION", "L5-METACONSENSUS",
        "L5-COGNITIVE-SPIDER-WEB", "L5-COGNITIVE-METABOLISM",
        "L5-OUTCOME-CALIBRATION", "L5-CAUSAL-CREDIT-ASSIGNMENT", "CAPABILITY-GENESIS",
    } <= ids
    # Named canonical organs remain separate rather than being collapsed into MIND.
    assert {
        "ORGAN-DALEOBANKS", "ORGAN-WEALTHMACHINE", "ORGAN-RAILSCOUT",
        "ORGAN-RESEARCH-IN", "ORGAN-PUMPSTATION", "ORGAN-GODS-EYE",
        "ORGAN-BODY-FAMILIES", "CANONICAL-RESEARCH-LINE",
    } <= ids


def test_index_counts_match_actual_rows_and_next_build_is_not_completed_slice():
    index = json.loads((MATRIX / "index.json").read_text())
    rows = load_rows()
    assert index["totals"]["rows"] == len(rows)
    assert index["totals"]["unfinished_register_rows"] == 80
    assert index["totals"]["unfinished_register_rows_covered"] == 80
    capability = collections.Counter(row["status"]["capability"] for _n, _d, row in rows)
    ladder = collections.Counter(row["status"]["evidence_ladder"] for _n, _d, row in rows)
    assert index["status_counts"]["capability"] == dict(sorted(capability.items()))
    assert index["status_counts"]["evidence_ladder"] == dict(sorted(ladder.items()))
    selected = index["selected_next"]
    assert selected["policy"] == "highest-leverage independently-buildable coherent slice"
    assert "VOI" in selected["selected"]
    assert "0.4.0" in selected["previous_completed_slice"]
    assert selected["matrix_is_a_stopping_condition"] is False
    for row_id in selected["row_ids"]:
        assert row_id in {row["id"] for _n, _d, row in rows}


@pytest.mark.parametrize("name", CHUNKS)
def test_matrix_files_are_canonical_readable_json(name):
    text = (MATRIX / name).read_text()
    assert text.endswith("\n")
    assert json.loads(text)["rows"]
