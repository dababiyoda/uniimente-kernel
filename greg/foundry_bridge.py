"""GREG <-> Foundry: every implemented Foundry system behind the Authority Office.

``foundry.query`` (read_only) and ``foundry.apply`` (internal_write) take
``{system, op, args}``. The system's store lives inside the mission workspace,
with reviewed operations executed in a disposable, network-denied worker.
Python file guards defend reviewed code against path confusion; they are not
an OS filesystem sandbox. Source execution and child processes require one.
An op the system does not declare for that capability is refused, so a
read-only grant cannot reach a write op.
"""
from __future__ import annotations

from pathlib import Path
import json
import fcntl
import os
import signal
import subprocess
import sys
import tempfile
import time

from greg.capabilities import CapabilityError, InvocationContext


def _call(params, ctx: InvocationContext, table: str) -> dict:
    if ctx.stop_check and ctx.stop_check():
        raise CapabilityError("foundry worker stopped by canonical revocation/pause")
    from foundry.systems import module
    try:
        system = int(params["system"])
        op = str(params["op"])
    except (KeyError, TypeError, ValueError):
        raise CapabilityError("foundry call needs integer 'system' and string 'op'") from None
    try:
        ops = getattr(module(system), table)
    except KeyError as exc:
        raise CapabilityError(str(exc)) from None
    if op not in ops:
        raise CapabilityError(f"system {system} has no {table.split('_')[0].lower()} op {op!r}")
    def source_execution(value):
        if isinstance(value, dict):
            if str(value.get("system")) == "52":
                return True
            return any(source_execution(v) for v in value.values())
        return isinstance(value, list) and any(source_execution(v) for v in value)
    if source_execution(params):
        raise CapabilityError("caller source execution requires OS filesystem confinement")
    root = Path(ctx.workspace) / "foundry" / f"system-{system:02d}"
    request = json.dumps({"system": system, "op": op, "table": table,
                          "args": dict(params.get("args") or {}), "root": str(root.resolve())}, allow_nan=False)
    if len(request.encode()) > 131072:
        raise CapabilityError("foundry request exceeds 128 KiB")
    # Refuse a store aliased outside the signed mission workspace.
    workspace = Path(ctx.workspace).resolve()
    if workspace not in root.resolve().parents:
        raise CapabilityError("foundry store outside mission workspace")
    workspace.mkdir(parents=True, exist_ok=True)
    from greg.capabilities import KERNEL_ROOT, _no_network_preexec
    env = {"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8", "HOME": str(workspace),
           "PYTHONPATH": str(KERNEL_ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    if sys.platform != "linux":
        raise CapabilityError("Foundry worker network confinement requires Linux; platform adapter pending")
    # File-backed output caps avoid unbounded capture in the body process.
    # Serialize Foundry calls without creating a persistent lock file.
    lock = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY)
    try:
        deadline = time.monotonic() + 30
        while True:
            if ctx.stop_check and ctx.stop_check():
                raise CapabilityError("canonical revocation/pause while waiting for Foundry store")
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise CapabilityError("Foundry store lock exceeded 30 second wall budget")
                time.sleep(0.02)
        return _execute(request, ctx, table, root, workspace, env, KERNEL_ROOT, _no_network_preexec)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        os.close(lock)


def _execute(request, ctx, table, root, workspace, env, kernel_root, preexec):
    from greg.foundry_state import stage, commit
    params = json.loads(request)
    system, op = params["system"], params["op"]
    with tempfile.TemporaryDirectory(prefix="greg-foundry-", dir=workspace) as temporary:
        staged = Path(temporary) / "stores"
        before = stage(root.parent, staged)
        with open(Path(temporary) / "request.json", "w+b") as inp, \
                open(Path(temporary) / "result.json", "w+b") as out, \
                open(Path(temporary) / "error.txt", "w+b") as err:
            payload = json.loads(request)
            payload["scratch"] = temporary
            payload["root"] = str(staged / root.name)
            inp.write(json.dumps(payload).encode()); inp.seek(0)
            proc = subprocess.Popen([sys.executable, "-s", "-m", "greg.foundry_worker"],
                                    cwd=kernel_root, env=env, stdin=inp, stdout=out, stderr=err,
                                    preexec_fn=preexec, start_new_session=True, close_fds=True)
            deadline = time.monotonic() + 30
            try:
                while proc.poll() is None:
                    if ctx.stop_check and ctx.stop_check():
                        raise CapabilityError("foundry worker stopped by canonical revocation/pause")
                    if time.monotonic() >= deadline:
                        raise CapabilityError("foundry worker exceeded 30 second wall budget")
                    time.sleep(0.02)
                out.seek(0)
                raw = out.read(1048577)
                if proc.returncode or len(raw) > 1048576:
                    raise CapabilityError(f"system {system} refused {op}: worker exit {proc.returncode}")
                answer = json.loads(raw)
                if "error" in answer:
                    raise CapabilityError(f"system {system} refused {op}: {answer['error']}")
                if ctx.stop_check and ctx.stop_check():
                    raise CapabilityError("canonical revocation/pause before Foundry commit")
                after = commit(staged, root.parent, before) if table == "APPLY_OPS" else before
                return {"system": system, "op": op, "result": answer["result"],
                        "execution": {"process": "disposable", "network": "seccomp-denied",
                                      "filesystem": "reviewed-code-python-guard", "arbitrary_source": "refused",
                                      "cpu_seconds": 12, "wall_seconds": 30, "output_bytes": 1048576,
                                      "persistence": "atomic-store-commit" if table == "APPLY_OPS" else "discarded",
                                      "state_before": before, "state_after": after}}
            finally:
                # Descendants cannot survive either success or refusal.
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait()


def query(params, ctx: InvocationContext) -> dict:
    return _call(params, ctx, "QUERY_OPS")


def apply(params, ctx: InvocationContext) -> dict:
    return _call(params, ctx, "APPLY_OPS")
