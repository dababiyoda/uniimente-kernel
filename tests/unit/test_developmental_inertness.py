"""Developmental inertness — ENFORCED at runtime, observed from outside.

Adapted from PR #44 (`morphogenesis/tests/test_inertness.py`, commit
`1b4ffbc5df11d0e9246a3ee607ef67610e2e9326`), repointed at this line's
`developmental` package. PR #44's own Gray-Scott substrate was NOT carried
over — that was the duplicate runtime the founder ruled against.

WHY THIS REPLACES A DECLARATION CHECK.
`scripts/ci/check_sealed_developmental.py` verifies the benchmark's own
reported `external_effects=0`. That is the system grading its own homework: a
module that quietly opened a socket would still report zero. Static import
analysis is no better — it proves source separation, not absence of effect,
and says nothing about `__import__`, `importlib`, `eval`, `ctypes`, or a
socket opened by a transitive dependency.

So inertness is tested the way a security property has to be: the work runs
under denial in a child process, and the PARENT makes the assertion.

MECHANISM
  - `sys.addaudithook` installed BEFORE any developmental import, recording
    network, subprocess, file-write, native-load, and Kernel-reach events
  - RLIMIT_FSIZE = 0   — writes fail at the kernel, not at the hook's discretion
  - RLIMIT_CPU         — bounded compute, so a hang is a failure not a wait
  - RLIMIT_NPROC = 0   — no process spawning (best-effort; some uids refuse)
  - the child reports its audit log; the parent asserts on it

NOT WATCHED, AND WHY. `exec` and `compile` audit events fire from CPython's own
import machinery — measured at 12 events from importing json/statistics/random
alone — so they cannot discriminate dynamic code from module loading, and
watching them produced a false positive in PR #44. Dynamic execution is a risk
factor, not an external effect. The effects that matter are network, filesystem,
subprocess, and native loading; all are watched here and rlimit-enforced.
"""

import json
import os
import subprocess
import sys
import textwrap



REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


CHILD = textwrap.dedent(
    """
    import json, sys, resource

    violations = []

    WATCHED = {
        "socket.connect": "network",
        "socket.bind": "network",
        "socket.getaddrinfo": "network",
        "socket.gethostbyname": "network",
        "urllib.Request": "network",
        "subprocess.Popen": "subprocess",
        "os.system": "subprocess",
        "os.exec": "subprocess",
        "os.fork": "subprocess",
        "os.spawn": "subprocess",
        "ctypes.dlopen": "native",
        "ctypes.dlsym": "native",
    }

    # Reaching any of these from sealed developmental work would mean research
    # code had acquired a path to authority or to institutional truth.
    KERNEL_MODULES = {
        "policy", "authority", "capital", "provenance",
        "constitution", "identity", "capabilities", "embassy",
    }

    def hook(event, args):
        kind = WATCHED.get(event)
        if kind is not None:
            violations.append({"event": event, "kind": kind})
        if event == "open":
            mode = args[1] if len(args) > 1 else None
            if mode and any(c in str(mode) for c in "wxa+"):
                violations.append({"event": "open", "kind": "file-write",
                                   "detail": str(args[0])})
        if event == "import":
            name = str(args[0]).split(".")[0]
            if name in KERNEL_MODULES:
                violations.append({"event": "import", "kind": "kernel-reach",
                                   "detail": name})

    sys.addaudithook(hook)

    # Kernel-enforced denial, independent of the hook behaving honestly.
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))
    except (ValueError, OSError):
        pass  # not enforceable for this uid; the audit hook still covers spawns

    sys.path.insert(0, "__REPO_ROOT__")

    # Everything below runs under denial.
    from developmental.cdpe import DevelopmentalProgramExecutor

    report = DevelopmentalProgramExecutor().run()
    payload = report if isinstance(report, dict) else getattr(report, "__dict__", {})

    __PROBE__

    sys.stderr.write(json.dumps({
        "violations": violations,
        "ran": True,
        "external_effects": (payload or {}).get("external_effects"),
    }))
    """
)


def _run(probe=""):
    script = CHILD.replace("__REPO_ROOT__", REPO_ROOT).replace("__PROBE__", probe)
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=900,
    )


def _payload(proc):
    line = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "{}"
    return json.loads(line)


def test_developmental_work_produces_zero_external_effects():
    """The whole TARGET_FORM_001 benchmark under denial, asserted by the parent."""
    proc = _run()

    assert proc.returncode == 0, (
        f"sealed developmental run failed (rc={proc.returncode}).\n"
        f"stderr tail: {proc.stderr[-1500:]}"
    )

    data = _payload(proc)
    assert data.get("ran") is True
    assert data["violations"] == [], (
        f"developmental work produced external effects: {data['violations']}"
    )
    # The benchmark's own declaration must also still hold. Enforcement and
    # declaration agreeing is the point; enforcement alone is what is trusted.
    assert data.get("external_effects") == 0


def test_harness_detects_a_deliberate_file_write():
    """A denial harness that never reports anything is indistinguishable from a
    broken one. This proves it can fail."""
    proc = _run(probe=textwrap.dedent(
        """
        try:
            open("/tmp/_developmental_inertness_probe", "w").write("x")
        except Exception:
            pass
        """
    ).strip())
    kinds = {v["kind"] for v in _payload(proc)["violations"]}
    assert "file-write" in kinds, "harness failed to detect a deliberate file write"


def test_harness_detects_deliberate_network_access():
    proc = _run(probe=textwrap.dedent(
        """
        try:
            import socket
            socket.getaddrinfo("example.invalid", 80)
        except Exception:
            pass
        """
    ).strip())
    kinds = {v["kind"] for v in _payload(proc)["violations"]}
    assert "network" in kinds, "harness failed to detect deliberate network access"


def test_harness_detects_kernel_module_reach():
    """Sealed research reaching for an authority module must be caught."""
    proc = _run(probe=textwrap.dedent(
        """
        try:
            import policy  # noqa: F401
        except Exception:
            pass
        """
    ).strip())
    kinds = {v["kind"] for v in _payload(proc)["violations"]}
    assert "kernel-reach" in kinds, "harness failed to detect a Kernel-module import"
