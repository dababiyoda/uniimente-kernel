"""A founder who types a reader command before ``greg init`` gets one line telling them what to do, never a traceback.

Before this, eleven reader commands raised FileNotFoundError on ``body.json`` and printed a Python stack.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from greg.body import BodyError, Layout

ROOT = Path(__file__).resolve().parents[2]
READERS = ["status", "decisions", "vepmc", "routing", "blockers", "acceptance", "morning", "autonomy",
           "presence", "learning"]


@pytest.mark.parametrize("cmd", READERS)
def test_reader_on_a_home_never_initialised_refuses_in_one_line(cmd, tmp_path):
    home = tmp_path / "never-initialised"
    home.mkdir()
    env = {**os.environ, "PYTHONPATH": str(ROOT)}
    done = subprocess.run([sys.executable, "-B", "-m", "greg", "--home", str(home), cmd],
                          capture_output=True, text=True, cwd=ROOT, env=env, timeout=60)
    assert done.returncode == 2, done.stderr
    assert "Traceback" not in done.stderr
    assert done.stderr.strip().splitlines() == [
        f"greg: no body at {home.resolve()}: run `greg init` first (greg/CHROMEBOOK_FIRST_MISSION.md section 1)"]
    assert list(home.iterdir()) == []   # a refused read creates nothing


def test_read_config_refuses_a_missing_body_and_reads_a_present_one(tmp_path):
    layout = Layout(tmp_path)
    with pytest.raises(BodyError, match="run `greg init` first"):
        layout.read_config()
    layout.config.write_text('{"body_id": "b1"}')
    assert layout.read_config() == {"body_id": "b1"}
