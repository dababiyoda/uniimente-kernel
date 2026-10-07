"""Actual CLI, signed test key, real solvers, SIGKILL and recovered evidence.

This exercises developer Linux, not Alfonso's Chromebook, phone or identity.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import pytest
import importlib.util

from greg.body import Body, observe, status
from tests.greg_fixtures import make_body
from tests.unit.test_greg_seed_compat import problem, estimation, allocation

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(any(importlib.util.find_spec(m) is None for m in ('z3', 'ortools')),
                                reason='optional cognition solvers absent')


def cli(home, *args):
    return [sys.executable, '-m', 'greg', '--home', str(home), *args]


@pytest.mark.parametrize('kill_after', ['cognition.receipt', 'mission.action'])
def test_cli_composition_survives_sigkill_without_duplicate_computation(tmp_path, kill_after):
    home, key, bid, _ = make_body(tmp_path)
    p = problem('estimation', estimation(), name='process-recovery')
    p['claims'].append({'claim_id': 'allocation', 'kind': 'optimization',
                        'data': allocation(), 'conditions': {}})
    source = tmp_path / 'problem.json'
    source.write_text(json.dumps(p))
    signed = subprocess.run(cli(home, 'mission', 'new', 'cognition', '--problem', str(source),
                                '--key', str(tmp_path / 'founder.pem'), '--no-passphrase'),
                            cwd=ROOT, capture_output=True, text=True, timeout=15)
    assert signed.returncode == 0, signed.stderr
    child = subprocess.Popen(cli(home, 'run', '--tick-seconds', '0.05'), cwd=ROOT,
                             stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    observed = False
    started = time.monotonic()
    try:
        while time.monotonic() - started < 20:
            with observe(home, actor='spiffe://uniimente.internal/greg/recovery-test') as journal:
                observed = bool([e for e in journal.replay(kill_after)
                                 if kill_after == 'cognition.receipt' or
                                 e.payload.get('capability') == 'cognition.solve'])
            if observed:
                child.kill()  # actual SIGKILL; no orderly close or manual tick
                break
            if child.poll() is not None:
                break
            time.sleep(.01)
    finally:
        if child.poll() is None:
            child.kill()
        _, stderr = child.communicate(timeout=5)
    assert observed, stderr.decode()
    before = time.monotonic()
    recovered = subprocess.run(cli(home, 'run', '--max-ticks', '6', '--tick-seconds', '0.05'),
                               cwd=ROOT, capture_output=True, text=True, timeout=20)
    assert recovered.returncode == 0, recovered.stderr
    recovery_seconds = time.monotonic() - before
    assert recovery_seconds < 20
    with Body(home) as body:
        receipts = body.journal.replay('cognition.receipt')
        assert len(receipts) == 1 and receipts[0].payload['answered']
        assert len({c['method'] for c in receipts[0].payload['claims']}) == 2
        actions = [e for e in body.journal.replay('mission.action')
                   if e.payload.get('capability') == 'cognition.solve']
        # The durable cognition receipt precedes the Gate's final record. A kill
        # in that gap can leave no mission.action, but never a second computation.
        assert len(actions) <= 1
        if kill_after == 'mission.action':
            assert len(actions) == 1
        assert body.engine.book.missions['m:cognition-process-recovery'].status == 'ACHIEVED'
        assert any(e.payload.get('verdict') == 'VERIFIED'
                   for e in body.journal.replay('mission.appraised'))
        assert body.ledger.verify_chain()[0]
    projected = status(home)['cognition']
    assert projected['receipts'][0]['answered']
    # Persisted shutdown beats an otherwise runnable mission on process replacement.
    subprocess.run(cli(home, 'stop', '--local'), cwd=ROOT, check=True, capture_output=True)
    stopped = subprocess.run(cli(home, 'run', '--max-ticks', '2', '--tick-seconds', '0.05'),
                             cwd=ROOT, capture_output=True, text=True, timeout=10)
    assert stopped.returncode == 0
    with observe(home, actor='spiffe://uniimente.internal/greg/recovery-test') as journal:
        assert len(journal.replay('cognition.receipt')) == 1
