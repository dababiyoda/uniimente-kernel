"""Section-5 disposition index, the authority-plane check it unblocks, and organ seams.

Fail-first acceptance for asks S5.A1, S51.A1, S67.A1 and S51.A2:

1. A second ConsequenceGate constructed outside the Kernel module stays green
   under a filename-only check and fails once the checker reads the AST.
2. A material path with zero dispositions, or two, fails the index.
3. An organ manifest that approves an effect with no Kernel gate decision id fails.
"""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import yaml

from greg.organs import seam_problems
from greg.path import SECTION5_DISPOSITIONS, authority_plane_problems, material_path_names, section5_problems

ROOT = Path(__file__).resolve().parents[2]
METABOLISM = ROOT / "docs/collaboration/REPOSITORY-METABOLISM-2026-09-25.json"
_SPEC = importlib.util.spec_from_file_location(
    "check_authority_singleton", ROOT / "scripts/ci/check_authority_singleton.py")
SINGLETON = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(SINGLETON)

DECISION = "12345678-1234-1234-1234-123456789abc"


def _record(*rows, material=None):
    paths = [row["path"] for row in rows]
    return {"section5_vocabulary": list(SECTION5_DISPOSITIONS),
            "material_paths": list(paths if material is None else material),
            "section5_index": [dict(row) for row in rows]}


def _singletons(root: Path) -> None:
    """One of each filename the existing check counts, and nothing else of those names."""
    (root / "constitution").mkdir()
    (root / "constitution" / "constitution.ucl").write_text("law\n")
    policy = root / "policy"
    policy.mkdir()
    (policy / "consequence_gate.py").write_text(
        "class ConsequenceGate:\n    pass\nclass GrantIssuer:\n    pass\n")
    (root / "authority-matrix.yaml").write_text("one: true\n")
    (root / "legal-principals.yaml").write_text("one: true\n")
    (root / "organ-registry.yaml").write_text("one: true\n")
    (root / "agent-registry.yaml").write_text("one: true\n")


def test_a_second_consequence_gate_is_green_by_filename_and_fails_in_the_ast(tmp_path):
    _singletons(tmp_path)
    rogue = tmp_path / "organs"
    rogue.mkdir()
    (rogue / "second.py").write_text(
        "from policy.consequence_gate import ConsequenceGate, GrantIssuer\n"
        "gate = ConsequenceGate()\n"
        "issuer = GrantIssuer()\n")
    filename = SINGLETON.filename_problems(tmp_path)
    assert filename == [], filename
    record = _record({"path": "organs/", "disposition": "ADAPT"})
    problems = authority_plane_problems(tmp_path, record)
    assert any("organs/second.py" in item and "ConsequenceGate" in item for item in problems), problems
    assert any("organs/second.py" in item and "GrantIssuer" in item for item in problems), problems
    # The Kernel module itself may construct both. A filename-identical twin is the old check's job.
    assert authority_plane_problems(tmp_path, _record({"path": "policy/", "disposition": "ADAPT"})) == [
        "organs/second.py: call ConsequenceGate outside the Kernel module",
        "organs/second.py: call GrantIssuer outside the Kernel module",
    ]


def test_a_material_path_with_zero_or_two_dispositions_fails():
    one = _record({"path": "greg/", "disposition": "ADAPT"})
    assert section5_problems(one) == []
    zero = _record({"path": "greg/", "disposition": "ADAPT"}, material=["greg/", "policy/"])
    assert "policy/: zero current section-5 dispositions" in section5_problems(zero)
    two = copy.deepcopy(one)
    two["section5_index"].append({"path": "greg/", "disposition": "EVIDENCE"})
    assert "greg/: 2 current section-5 dispositions" in section5_problems(two)
    foreign = copy.deepcopy(one)
    foreign["section5_index"][0]["disposition"] = "KEEP"
    assert any("not in the section-5 vocabulary" in item for item in section5_problems(foreign))


def test_metabolism_paths_normalize_without_splitting_notes():
    assert material_path_names("closure/ + verifier/") == ["closure/", "verifier/"]
    assert material_path_names("egregore/goal_chase*.py") == ["egregore/goal_chase*.py"]
    assert material_path_names("(repository)") == []
    assert material_path_names("greg/genesis.py repair() + greg/missions.py _self_repair") == [
        "greg/genesis.py", "greg/missions.py"]


def test_the_live_index_gives_every_material_path_one_disposition():
    record = json.loads(METABOLISM.read_text())
    assert section5_problems(record) == []
    derived = []
    for entry in record["entries"]:
        derived.extend(material_path_names(entry["path"]))
    assert sorted(set(derived)) == sorted(record["material_paths"])
    assert authority_plane_problems(ROOT, record) == []
    assert SINGLETON.filename_problems(ROOT) == []


def test_an_organ_manifest_that_approves_an_effect_without_a_kernel_decision_fails():
    refused = seam_problems({"authority": {"approved_effects": [{"effect": "publish"}]}})
    assert refused == ["publish: approved effect has no Kernel gate decision id"]
    assert seam_problems({"authority": {"approved_effects": [
        {"effect": "publish", "kernel_gate_decision_id": DECISION}]}}) == []
    live = yaml.safe_load((ROOT / "organs/daleobanks.manifest.yaml").read_text())
    assert seam_problems(live) == []
    live["health"]["last_verified"]["notes"] += "\napproved_effect: publish\n"
    assert seam_problems(live) == ["approved_effect: publish: approved effect has no Kernel gate decision id"]
    live["health"]["last_verified"]["notes"] += f"\napproved_effect: publish kernel_gate_decision_id: {DECISION}\n"
    # The bare line is still an approval with no id. A later well-formed line does not erase it.
    assert any("no Kernel gate decision id" in item for item in seam_problems(live))
