"""A prewarmed commodity WASM engine must still work after process fork."""
from pathlib import Path
import os
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(not hasattr(os, "fork"), reason="fork lifecycle is platform-specific")
def test_prewarmed_wasm_compilation_finishes_in_a_forked_child():
    # Fresh interpreter prevents a previous test's native pool from masking the
    # regression; warm the pool before forking, not just in a fresh child.
    code = """
import multiprocessing as mp
from foundry.systems import wasm
comp = wasm.compile_rule('pricing', 'base_price * units')
inputs = {'base_price': 2, 'units': 3}
assert wasm.run(comp['wasm'], comp['manifest'], inputs) == 6
def child():
    assert wasm.run(comp['wasm'], comp['manifest'], inputs) == 6
p = mp.get_context('fork').Process(target=child)
p.start()
p.join(5)
if p.is_alive():
    p.kill()
    p.join()
    raise AssertionError('WASM compiler stalled after fork')
assert p.exitcode == 0, p.exitcode
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, text=True,
                            capture_output=True, timeout=15)
    assert result.returncode == 0, result.stderr
