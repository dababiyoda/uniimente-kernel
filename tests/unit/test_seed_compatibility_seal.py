"""A compatibility replay may not silently rewrite the original evaluation."""
import json
from pathlib import Path
import shutil
import pytest
from scripts.ci.replay_seed_compatibility import ROOT, replay

@pytest.mark.parametrize('file', ['suite.json', 'run.py', 'build.py', 'freeze-v3.json'])
def test_replay_refuses_tampered_frozen_evaluation(tmp_path, file):
    relative=Path('cortex/evaluation/seed_genome')
    shutil.copytree(ROOT/relative,tmp_path/relative)
    path=tmp_path/relative/file;path.write_bytes(path.read_bytes()+b'\n')
    with pytest.raises(ValueError,match='FROZEN_EVALUATION_CHANGED'):
        replay(tmp_path)
