"""Kernel filesystem denial independent of Python audit hooks; no generic-code grant."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from greg import foundry_bridge
from greg.isolation import available
from tests.unit.test_greg_foundry_worker import context


def require_support():
    support = available()
    if os.environ.get("GREG_REQUIRE_LANDLOCK") == "1":
        assert support["available"], support
    if not support["available"]:
        pytest.skip("This host does not provide Landlock ABI >=3; source/provider execution remains refused")
    return support


def test_kernel_denies_native_private_reads_writes_and_links_with_no_audit_hook(tmp_path):
    require_support()
    scope = tmp_path / "stage"; scope.mkdir()
    private = tmp_path / "body-key.fixture"; private.write_text("synthetic-private-material")
    public = tmp_path / "published.fixture"; public.write_text("published")
    code = Path(__file__).resolve().parents[2]
    script = """
import ctypes,json,os,sys
from pathlib import Path
from greg.isolation import confine
root,private,public=map(Path,sys.argv[1:])
libc=ctypes.CDLL(None,use_errno=True)
libc.open.argtypes=[ctypes.c_char_p,ctypes.c_int]
libc.open.restype=ctypes.c_int
installed=confine(root,[public])
native_read=libc.open(os.fsencode(private),os.O_RDONLY)
native_errno=ctypes.get_errno()
try:
    private.write_text('escaped')
    write_denied=False
except PermissionError:
    write_denied=True
try:
    os.truncate(private,0)
    truncate_denied=False
except PermissionError:
    truncate_denied=True
(root/'link').symlink_to(private)
linked=libc.open(os.fsencode(root/'link'),os.O_RDONLY)
(root/'owned').write_text('owned')
try:
    public.write_text('changed')
    public_write_denied=False
except PermissionError:
    public_write_denied=True
print(json.dumps({'native_read':native_read,'native_errno':native_errno,
                 'private_write_denied':write_denied,'truncate_denied':truncate_denied,
                 'linked_read':linked,'public_write_denied':public_write_denied,
                 'public_read':public.read_text(),'owned_read':(root/'owned').read_text(),
                 'installed':installed}))
"""
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "PYTHONPATH": str(code),
           "PYTHONDONTWRITEBYTECODE": "1"}
    result = subprocess.run([sys.executable, "-s", "-c", script, str(scope), str(private), str(public)],
                            cwd=code, env=env, capture_output=True, text=True, timeout=15, close_fds=True)
    assert result.returncode == 0, result.stderr
    observed = json.loads(result.stdout)
    assert observed["native_read"] == -1 and observed["native_errno"] == 13
    assert observed["linked_read"] == -1
    assert observed["private_write_denied"] and observed["public_write_denied"] and observed["truncate_denied"]
    assert observed["public_read"] == "published" and observed["owned_read"] == "owned"
    assert private.read_text() == "synthetic-private-material"
    assert observed["installed"]["filesystem"] == "landlock"


def test_actual_greg_worker_has_os_confinement_and_keeps_caller_source_refusal(tmp_path):
    support = require_support()
    result = foundry_bridge.apply({"system": 36, "op": "put", "args": {"text": "owned"}},
                                 context(tmp_path))
    assert result["execution"]["filesystem"] == "landlock"
    assert result["execution"]["landlock_abi"] == support["abi"]
    assert result["execution"]["arbitrary_source"] == "refused"
    assert result["execution"]["persistence"] == "atomic-store-commit"


def test_landlock_inherits_into_exact_reviewed_dsl_and_packaging_children(tmp_path):
    require_support()
    from foundry.systems import promotion
    source = "max(base_price * units * (1 - 0.05 * customer_tier), cost_per_unit * units * 1.1)"
    out = foundry_bridge.query({"system": 16, "op": "dry_run", "args": {
        "candidate": promotion.candidate(source), "context": promotion.context()}},
        context(tmp_path, "foundry.query"))
    assert out["execution"]["filesystem"] == "landlock"
    verification = next(s for s in out["result"]["stages"] if s["stage"] == "verification")
    assert verification["passed"]
    assert out["result"]["blocked_at"] == "ratification"
    built = foundry_bridge.apply({"system": 53, "op": "build"}, context(tmp_path))
    assert built["execution"]["filesystem"] == "landlock"
