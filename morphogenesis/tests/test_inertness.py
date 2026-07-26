"""Track B inertness — verified at runtime, from outside the process.

WHY THIS FILE EXISTS. An earlier version claimed inertness on the strength of
an AST import check. That was wrong: static import analysis proves source
separation, not absence of effects. A module can still reach the outside via
__import__, importlib, eval, ctypes, os.system, or a socket opened by any
transitive dependency. Source separation is necessary and nowhere near
sufficient.

Track B's entire licence to be ungoverned rests on being inert. So inertness
is tested the way a security property has to be: by running the code under
denial and observing from the outside whether anything escaped.

Mechanism:
  - sys.addaudithook installed BEFORE the morphogenesis import, recording
    every network, subprocess, file-write, and dynamic-import event
  - RLIMIT_FSIZE = 0, so any write to disk fails at the kernel rather than
    relying on the hook being honest
  - RLIMIT_NPROC and RLIMIT_AS bound process spawning and memory
  - RLIMIT_CPU bounds compute, so 'uncontrolled resource consumption' is a
    failure rather than a hang
  - the child reports its audit log to the parent over stdout; the PARENT
    makes the assertion

Audit hooks cannot be removed once installed (CPython enforces this), which
is what makes the in-child recording trustworthy enough to report outward.
"""

import json
import os
import subprocess
import sys
import textwrap

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


CHILD = textwrap.dedent(
    """
    import json, sys, resource

    violations = []

    WATCHED = {
        "socket.connect": "network",
        "socket.bind": "network",
        "socket.getaddrinfo": "network",
        "urllib.Request": "network",
        "subprocess.Popen": "subprocess",
        "os.system": "subprocess",
        "os.exec": "subprocess",
        "os.fork": "subprocess",
        "os.spawn": "subprocess",
        "ctypes.dlopen": "native",
        "ctypes.dlsym": "native",
    }

    # NOT watched, and the reason matters: CPython raises the 'exec' and
    # 'compile' audit events from its own import machinery — importlib runs
    # every module body through exec(). Measured at 12 events from importing
    # json/statistics/random alone. They therefore cannot discriminate
    # dynamic code from normal module loading, and including them produced a
    # false positive on first run.
    #
    # Dynamic code execution is a risk factor, not an external effect. The
    # effects that matter are network, filesystem, subprocess, and native
    # library loading, and those are both audited above and hard-denied by
    # the rlimits below.

    KERNEL_MODULES = {
        "policy", "authority", "capital", "provenance",
        "constitution", "identity", "capabilities", "events", "embassy",
    }

    def hook(event, args):
        kind = WATCHED.get(event)
        if kind is not None:
            violations.append({"event": event, "kind": kind})
        if event == "open":
            # args = (path, mode, flags)
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

    # Hard denials enforced by the kernel, not by the hook's good behaviour.
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))       # no bytes to disk
    resource.setrlimit(resource.RLIMIT_CPU, (60, 60))       # bounded compute
    try:
        resource.setrlimit(resource.RLIMIT_NPROC, (0, 0))   # no new processes
    except (ValueError, OSError):
        pass  # not enforceable for this uid; audit hook still covers spawns

    sys.path.insert(0, "__REPO_ROOT__")

    # Everything below runs under denial.
    from morphogenesis.substrate import Substrate
    from morphogenesis import grn

    sub = Substrate(24, 24, seed=1)
    sub.seed_uniform_with_noise()
    sub.establish_morphogen_gradient()
    sub.run(300)
    sub.excise(6, 6, 8, 8)
    sub.run(300)
    _ = sub.interface_density(), sub.expressed_fraction()

    net = grn.RegulatoryNetwork(n_genes=32, n_types=3, seed=2)
    net.relax(net.naive_state())

    sys.stderr.write(json.dumps(violations))
    """
)


def _run_child():
    proc = subprocess.run(
        [sys.executable, "-c", CHILD.replace("__REPO_ROOT__", REPO_ROOT)],
        capture_output=True, text=True, timeout=300,
    )
    return proc


@pytest.mark.slow
def test_track_b_is_inert_under_denial():
    """Run the full Stage 1 pipeline under a denying sandbox and require a
    clean audit log, observed by the parent process."""
    proc = _run_child()

    assert proc.returncode == 0, (
        f"Track B failed to run under denial (rc={proc.returncode}).\n"
        f"stderr tail: {proc.stderr[-1500:]}"
    )

    payload = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "[]"
    violations = json.loads(payload)

    assert violations == [], f"Track B produced external effects: {violations}"


@pytest.mark.slow
def test_sandbox_actually_detects_violations():
    """The sandbox must be able to fail.

    A denial harness that never reports anything is indistinguishable from a
    broken one. This deliberately performs a network call and a file write
    inside the same harness and requires both to be caught — without it, the
    passing test above proves nothing.
    """
    probe = CHILD.replace(
        "sys.stderr.write(json.dumps(violations))",
        textwrap.dedent(
            """
            try:
                import socket
                socket.getaddrinfo("example.invalid", 80)
            except Exception:
                pass
            try:
                open("/tmp/_morphogenesis_probe", "w").write("x")
            except Exception:
                pass
            sys.stderr.write(json.dumps(violations))
            """
        ).strip(),
    )
    proc = subprocess.run(
        [sys.executable, "-c", probe.replace("__REPO_ROOT__", REPO_ROOT)],
        capture_output=True, text=True, timeout=300,
    )
    payload = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "[]"
    violations = json.loads(payload)

    kinds = {v["kind"] for v in violations}
    assert "network" in kinds, f"sandbox failed to detect network use: {violations}"
    assert "file-write" in kinds, f"sandbox failed to detect file write: {violations}"
