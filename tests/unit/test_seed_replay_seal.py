"""The sealed-case seed replay seals the runner twice: by its v3 scoring and by the current freeze.

run.py's import path, file list and freeze pointer changed with the seed module rename and
the v4-v6 re-freezes; its loss() and SPEC did not. The scoring seal keeps the replay tied to the
v3 labels; the whole-file seal against the pinned current runner freeze refuses any other edit.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("replay_seed", ROOT / "scripts/ci/replay_seed_compatibility.py")
replay = importlib.util.module_from_spec(spec)
spec.loader.exec_module(replay)


def test_current_runner_scores_with_the_v3_loss_function():
    text = (ROOT / "cortex/evaluation/seed_genome/run.py").read_text()
    assert replay._sealed_loss_sha256(text) == replay.LOSS_V3_SHA256


def test_a_changed_loss_function_is_refused_and_unrelated_edits_are_not():
    text = (ROOT / "cortex/evaluation/seed_genome/run.py").read_text()
    pointer_moved = text.replace("freeze-v6.json", "freeze-v7.json")
    assert replay._sealed_loss_sha256(pointer_moved) == replay.LOSS_V3_SHA256
    tampered = text.replace("matched = receipt['answered'] == expected['answered']",
                            "matched = True", 1)
    assert tampered != text and replay._sealed_loss_sha256(tampered) != replay.LOSS_V3_SHA256


def test_the_scoring_spec_is_read_from_the_replayed_tree_and_equals_v3():
    import json
    text = (ROOT / "cortex/evaluation/seed_genome/run.py").read_text()
    frozen = json.loads((ROOT / "cortex/evaluation/seed_genome/freeze-v3.json").read_text())["inputs"]
    assert replay._literal_spec(text) == frozen["scoring"]
    assert replay._literal_spec(text.replace("'false_claim': .25", "'false_claim': .0", 1)) != frozen["scoring"]


def test_the_runner_is_pinned_to_its_current_freeze():
    import hashlib, json
    manifest, sha = replay.RUNNER_FREEZE
    assert hashlib.sha256((ROOT / manifest).read_bytes()).hexdigest() == sha
    recorded = json.loads((ROOT / manifest).read_text())["inputs"]["files"][replay.RUNNER]
    assert hashlib.sha256((ROOT / replay.RUNNER).read_bytes()).hexdigest() == recorded
