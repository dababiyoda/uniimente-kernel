"""Actual disposable-worker tests; no claim of OS filesystem sandboxing."""
from dataclasses import replace
import os

import pytest

from greg import foundry_bridge
from greg.capabilities import BUILTINS, CapabilityError, InvocationContext, SecretBroker


def context(tmp_path, capability="foundry.apply"):
    return InvocationContext(tmp_path / "ws", (tmp_path,), SecretBroker(tmp_path / "vault.json"),
                             BUILTINS[capability][0])


def test_query_demonstration_cannot_persist_its_internal_writes(tmp_path):
    result = foundry_bridge.query({"system": 15, "op": "demonstrate"}, context(tmp_path, "foundry.query"))
    assert result["result"]["no_step_repeated"]
    assert not (tmp_path / "ws" / "foundry").exists()
    assert result["execution"]["filesystem"] in {"reviewed-code-python-guard", "landlock"}


def test_workspace_traversal_and_symlink_cannot_read_body_files(tmp_path):
    canary = tmp_path / "body-key.txt"
    canary.write_text("synthetic-private-canary")
    for state in (str(tmp_path), "../../.."):
        with pytest.raises(CapabilityError, match="workspace access refused"):
            foundry_bridge.apply({"system": 21, "op": "snapshot", "args": {"state": state}}, context(tmp_path))
    root = tmp_path / "ws" / "foundry" / "system-21" / "state"
    root.mkdir(parents=True)
    (root / "key").symlink_to(canary)
    with pytest.raises(CapabilityError, match="linked or special Foundry state refused"):
        foundry_bridge.apply({"system": 21, "op": "snapshot", "args": {"state": "state"}}, context(tmp_path))
    assert canary.read_text() == "synthetic-private-canary"


def test_hardlinked_files_cannot_be_read_as_workspace_owned(tmp_path):
    canary = tmp_path / "body-key.txt"
    canary.write_text("synthetic-private-canary")
    root = tmp_path / "ws" / "foundry" / "system-21" / "state"
    root.mkdir(parents=True)
    os.link(canary, root / "key")
    with pytest.raises(CapabilityError, match="linked or special Foundry state refused"):
        foundry_bridge.apply({"system": 21, "op": "snapshot", "args": {"state": "state"}}, context(tmp_path))


def test_caller_source_is_refused_in_direct_and_composed_operations(tmp_path):
    canary = tmp_path / "canary.txt"
    source = f"from pathlib import Path\nPath({str(canary)!r}).write_text('escaped')\ndef f(x): return x\n"
    args = {"source": source, "func": "f", "failing": [{"args": [1]}], "passing": []}
    for request in ({"system": 52, "op": "localize", "args": args},
                    {"system": 15, "op": "run", "args": {"workflow_id": "no-source", "steps": [
                        {"name": "repair", "system": 52, "op": "localize", "args": args}]}}):
        with pytest.raises(CapabilityError, match="source execution requires OS filesystem confinement"):
            foundry_bridge._call(request, context(tmp_path), "QUERY_OPS" if request["system"] == 52 else "APPLY_OPS")
    assert not canary.exists()


def test_revocation_prevents_even_worker_start_and_oversized_inputs_are_refused(tmp_path):
    ctx = replace(context(tmp_path), stop_check=lambda: True)
    with pytest.raises(CapabilityError, match="canonical revocation/pause"):
        foundry_bridge.apply({"system": 36, "op": "put", "args": {"text": "hello"}}, ctx)
    assert not ctx.workspace.exists()
    with pytest.raises(CapabilityError, match="128 KiB"):
        foundry_bridge.apply({"system": 36, "op": "put", "args": {"text": "x" * 131072}}, context(tmp_path))


def test_failed_composition_discards_partial_effects_and_success_commits_atomically(tmp_path):
    from greg.foundry_state import fingerprint
    good = {"system": 36, "op": "put", "args": {"text": "retained"}}
    ctx = context(tmp_path)
    first = foundry_bridge.apply(good, ctx)
    root = ctx.workspace / "foundry"
    before = fingerprint(root)
    steps = [{"name": "first", "system": 36, "op": "put", "write": True, "args": {"text": "must not persist"}},
             {"name": "fail", "system": 39, "op": "post", "write": True,
              "args": {"date": "d", "memo": "m", "currency": "USD", "lines": []}}]
    with pytest.raises(CapabilityError, match="refused run"):
        foundry_bridge.apply({"system": 15, "op": "run", "args": {"workflow_id": "atomic", "steps": steps}}, ctx)
    assert fingerprint(root) == before
    second = foundry_bridge.apply({"system": 36, "op": "put", "args": {"text": "second"}}, ctx)
    assert second["execution"]["state_before"] == first["execution"]["state_after"]
    assert second["execution"]["state_after"] == fingerprint(root)
    assert second["execution"]["persistence"] == "atomic-store-commit"
    assert not list(ctx.workspace.glob("greg-foundry-*"))


def test_concurrent_mutation_and_quota_refuse_commit(tmp_path, monkeypatch):
    from greg import foundry_state
    root, staged = tmp_path / "root", tmp_path / "staged"
    root.mkdir(); (root / "old").write_text("original")
    before = foundry_state.stage(root, staged)
    (staged / "new").write_text("new")
    (root / "old").write_text("concurrent mutation")
    with pytest.raises(CapabilityError, match="changed during worker execution"):
        foundry_state.commit(staged, root, before)
    assert not (root / "new").exists()
    monkeypatch.setattr(foundry_state, "MAX_BYTES", 1)
    with pytest.raises(CapabilityError, match="quota"):
        foundry_state.fingerprint(staged)

def test_restricted_dsl_verifier_runs_but_ratification_is_still_required(tmp_path):
    from foundry.systems import promotion
    source = "max(base_price * units * (1 - 0.05 * customer_tier), cost_per_unit * units * 1.1)"
    result = foundry_bridge.query({"system": 16, "op": "dry_run", "args": {
        "candidate": promotion.candidate(source), "context": promotion.context()}}, context(tmp_path, "foundry.query"))
    assert result["result"]["status"] == "BLOCKED"
    assert result["result"]["blocked_at"] == "ratification"
    verification = next(s for s in result["result"]["stages"] if s["stage"] == "verification")
    assert verification["passed"] and verification["result"]["verified_cases"] == 41
    assert not (tmp_path / "ws" / "foundry").exists()


def test_fixed_child_recipe_rejects_module_environment_and_scope_substitution(tmp_path):
    import json
    from pathlib import Path
    import subprocess
    import sys
    code = Path(__file__).resolve().parents[2]
    script = """
import json,os,sys,subprocess
from pathlib import Path
from greg.foundry_worker import guard
root=Path(sys.argv[1]); code=Path(sys.argv[2])
guard(root)
base=[sys.executable,'-s','-m','greg.foundry_protocol_worker','dsl-verify']
env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONPATH':str(code),
     'PYTHONDONTWRITEBYTECODE':'1','GREG_FOUNDRY_STORE':str(root)}
attempts=[(base[:-1]+['unknown'],code,env),(base,root,env),
          (base,code,{**env,'PYTHONPATH':str(root)}),
          (base,code,{**env,'GREG_FOUNDRY_STORE':str(root.parent)}),
          (base,code,{**env,'PYTHONINSPECT':'1'})]
denied=0
for argv,cwd,values in attempts:
    try: subprocess.run(argv,cwd=cwd,env=values,input='{}',text=True,timeout=3)
    except PermissionError: denied+=1
print(json.dumps({'denied':denied}))
"""
    proc = subprocess.run([sys.executable, "-s", "-c", script, str(tmp_path), str(code)],
                          capture_output=True, text=True, timeout=10,
                          env={"PATH": "/usr/bin:/bin", "PYTHONPATH": str(code), "PYTHONDONTWRITEBYTECODE": "1"})
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["denied"] == 5
