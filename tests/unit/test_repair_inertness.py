"""Zero unauthorized external effects from the replacement logic — ENFORCED.

Adapted from the Package 2 harness (`tests/unit/test_developmental_inertness.py`),
repointed at the Package 3 candidates. Same reasoning as there: a module's own
report of `external_effects = 0` is the system grading its own homework, and
static import analysis proves source separation rather than absence of effect. So
the work runs under denial in a child process and the PARENT asserts.

WHAT RUNS UNDER DENIAL, AND WHY ONLY THAT. The four candidates and the blind
detector, on the live corpus. Not the full harness: the held-out corpora
materialize real schema files, and `RLIMIT_FSIZE = 0` would fail those writes.
Writing a fixture directory is legitimate test-harness activity, not behaviour of
the component under test, so scoping denial to the resolution logic measures the
thing that matters instead of the scaffolding around it. That scoping is a real
limitation of this proof and is stated rather than glossed.

KERNEL REACH IS A VIOLATION HERE. The component being replaced touches no
authority, so a replacement for it has no business importing `policy`,
`authority`, `capital`, `provenance`, `constitution`, `identity`, `capabilities`
or `embassy`. A candidate that reached for one would have quietly widened its own
blast radius, which is precisely what "no module may widen its own authority"
forbids.
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

    # A replacement for a zero-authority component must not acquire a path to
    # authority or to institutional truth.
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
    from evolution.repair import expectations
    from evolution.repair.baseline import BaselineRestore
    from evolution.repair.candidate import CapabilityProviderRegistry
    from evolution.repair.detector import FunctionLossDetector
    from evolution.repair.r1_contract_index import ContractIndexInversion
    from evolution.repair.r2_constraint import ConstraintSatisfaction
    from evolution.repair.r3_local_rule import LocalRulePropagation
    from linker.manifest import load_all

    from evolution.repair.harness import BASELINE_CORPUS_DIR

    # The frozen Package 3 corpus, not organs/ — see baseline_corpus/README.md.
    manifests = load_all(BASELINE_CORPUS_DIR)
    contracts_dir = __REPO_ROOT__ + "/contracts"
    contract = expectations.live_contract()

    restored = {}
    for cls in (BaselineRestore, ContractIndexInversion, ConstraintSatisfaction,
                LocalRulePropagation):
        candidate = cls()
        registry = CapabilityProviderRegistry()
        registry.register(contract.capability, candidate.candidate_id,
                          lambda c=candidate: c, registered_by="inertness_harness")
        report = FunctionLossDetector(registry).detect(
            contract, manifests, contracts_dir)
        restored[candidate.candidate_id] = report.restored

    __PROBE__

    sys.stderr.write(json.dumps({
        "violations": violations,
        "ran": True,
        "restored": restored,
    }))
    """
)


def _run(probe=""):
    script = (CHILD
              .replace('"__REPO_ROOT__"', repr(REPO_ROOT))
              .replace("__REPO_ROOT__", repr(REPO_ROOT))
              .replace("__PROBE__", probe))
    return subprocess.run([sys.executable, "-c", script],
                          capture_output=True, text=True, timeout=900)


def _payload(proc):
    line = proc.stderr.strip().splitlines()[-1] if proc.stderr.strip() else "{}"
    return json.loads(line)


def test_replacement_logic_produces_zero_external_effects():
    """All four candidates resolve the live corpus under denial, asserted by the
    parent process rather than self-reported by the child."""
    proc = _run()

    assert proc.returncode == 0, (
        f"sealed replacement run failed (rc={proc.returncode}).\n"
        f"stderr tail: {proc.stderr[-2000:]}"
    )

    data = _payload(proc)
    assert data.get("ran") is True
    assert data["violations"] == [], \
        f"replacement logic produced external effects: {data['violations']}"

    # And it actually did the work while denied, rather than trivially passing
    # by doing nothing.
    assert data["restored"] == {"B0-restore": True, "R1-contract-index": True,
                                "R2-constraint": True, "R3-local-rule": True}


def test_harness_detects_a_deliberate_file_write():
    """A denial harness that never reports anything is indistinguishable from a
    broken one. This proves it can fail."""
    proc = _run(probe=textwrap.dedent(
        """
        try:
            open("/tmp/_repair_inertness_probe", "w").write("x")
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


def test_harness_detects_a_candidate_reaching_for_authority():
    """The invariant that matters most here: a replacement for a zero-authority
    component must not acquire a path to authority."""
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
