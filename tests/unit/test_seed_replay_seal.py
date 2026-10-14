"""The sealed-case seed replay seals the runner by its scoring, not by its file bytes.

run.py's import path, file list and freeze pointer changed with the seed module rename and
the v4-v6 re-freezes; its loss() and SPEC did not. The replay must keep refusing a changed
scoring function while accepting those unrelated edits.
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
