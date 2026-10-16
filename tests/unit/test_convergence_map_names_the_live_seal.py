"""Fourth review, R3: the convergence map named `freeze-v10.json` as the seal of the joined tree after the tree was
re-sealed as v11, so a reviewer checking the named seal found two inputs that no longer match. The map's statement
of the joined tree's seal must name the freeze the seed replay pins, and that freeze must hold."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def test_the_map_names_the_seal_the_replay_pins_and_it_holds():
    spec = importlib.util.spec_from_file_location("_replay", ROOT / "scripts" / "ci" / "replay_seed_compatibility.py")
    replay = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(replay)
    pinned = Path(replay.RUNNER_FREEZE[0]).name
    text = (ROOT / "docs" / "opus-maximus" / "REPOSITORY_CONVERGENCE_MAP.md").read_text()
    named = re.findall(r"the joined tree is sealed by `(freeze-[^`]+\.json)`", text)
    assert named and set(named) == {pinned}, (named, pinned)
    freeze = json.loads((ROOT / "cortex" / "evaluation" / "seed_genome" / pinned).read_text())
    broken = [f for f, h in freeze["inputs"]["files"].items()
              if hashlib.sha256((ROOT / f).read_bytes()).hexdigest() != h]
    assert broken == [], broken
