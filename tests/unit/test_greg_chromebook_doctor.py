"""The hardware probe makes no enrollment claim and reports service absence honestly."""
from types import SimpleNamespace

from greg import doctor


def test_chromebook_doctor_ready_only_when_linux_user_service_is_available(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    monkeypatch.setattr(doctor.shutil, "which", lambda binary: "/usr/bin/" + binary)
    calls = []
    def service(cmd, **kw):
        calls.append(cmd)
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(doctor.subprocess, "run", service)
    ready = doctor.chromebook()
    service_probe = ["systemctl", "--user", "show-environment"]
    # the only other commands are the isolation probes: /usr/bin/true in a bubblewrap namespace, and a throwaway
    # child that installs the Kernel seccomp filter and exits (the #26 confined-egress probe)
    import sys
    from greg.capabilities import KERNEL_ROOT

    def seccomp_probe(c):
        return (c[:3] == [sys.executable, "-I", "-c"] and "install_filter()" in c[3]
                and c[4] == str(KERNEL_ROOT / "tools") and len(c) == 5)
    assert ready["ready_for_linux_service"] and calls[0] == service_probe
    assert all(c == service_probe or (c[0].endswith("bwrap") and c[-1] == "/usr/bin/true") or seccomp_probe(c)
               for c in calls)
    assert any(seccomp_probe(c) for c in calls) and ready["confined_egress"]["available"] is True
    assert "VM restart at login" in ready["not_verified"] and "founder identity" in ready["not_verified"]
    assert "ChromeOS host identity and ownership" in ready["not_verified"]
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1))
    blocked = doctor.chromebook()
    assert not blocked["ready_for_linux_service"] and blocked["missing"] == ["user_service_available"]


def test_chromebook_doctor_does_not_probe_service_outside_linux(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(doctor.shutil, "which", lambda binary: "/usr/bin/" + binary)
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **kw: 1 / 0)
    assert not doctor.chromebook()["ready_for_linux_service"]


def test_engines_are_reported_with_version_and_license_but_never_made_prerequisites(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    monkeypatch.setattr(doctor.shutil, "which", lambda binary: "/usr/bin/" + binary)
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0))
    from greg import mechanisms
    monkeypatch.setattr(mechanisms, "installed", lambda name: None)
    report = doctor.chromebook()
    assert report["ready_for_linux_service"] and report["missing"] == []          # N1 is not blocked by engines
    assert report["engines"]["present"] == 0 and report["engines"]["total"] == 5
    assert set(report["engines"]["missing"]) == {"z3-solver", "ortools", "scipy", "networkx", "sympy"}
    assert "never installs" in report["engines"]["note"]
    installed = SimpleNamespace(version="9.9", metadata={"License-Expression": "MIT"})
    monkeypatch.setattr(mechanisms, "installed", lambda name: installed)
    row = doctor.chromebook()["engines"]["engines"][0]
    assert row == {"distribution": "z3-solver", "installed": True, "version": "9.9", "license": "MIT",
                   "serves": doctor.ENGINE_USES["z3-solver"]}


def test_worker_isolation_is_reported_never_a_prerequisite(monkeypatch):
    from greg import worker_isolation as isolation
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    monkeypatch.setattr(doctor.shutil, "which", lambda binary: "/usr/bin/" + binary)
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0))

    def unavailable(**_):
        raise isolation.WorkerIsolationError("worker OS filesystem isolation unavailable: bubblewrap is unavailable")
    monkeypatch.setattr(isolation, "_backend", unavailable)
    report = doctor.chromebook()
    assert report["ready_for_linux_service"]                               # the body does not need workers
    assert report["worker_isolation"]["workers_can_run_confined"] is False
    assert "bubblewrap" in report["worker_isolation"]["fix"]
    monkeypatch.setattr(isolation, "_backend", lambda **_: ("bubblewrap", None, "/usr/bin/bwrap", []))
    assert doctor.chromebook()["worker_isolation"] == {"workers_can_run_confined": True, "mechanism": "bubblewrap"}


def test_confined_egress_is_reported_unavailable_with_its_fix_when_a_probe_fails(monkeypatch):
    monkeypatch.setattr(doctor.platform, "system", lambda: "Linux")
    monkeypatch.setattr(doctor.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1, stderr="no libseccomp"))
    from greg import worker_isolation

    def no_namespaces(**kw):
        raise worker_isolation.WorkerIsolationError("bubblewrap not installed")
    monkeypatch.setattr(worker_isolation, "_backend", no_namespaces)
    report = doctor.confined_egress()
    assert report["available"] is False and "kernel filter" in report["why"] and "network namespaces" in report["why"]
    assert "bubblewrap" in report["fix"] and "libseccomp" in report["fix"]
    monkeypatch.setattr(doctor.platform, "system", lambda: "Darwin")
    assert doctor.confined_egress()["available"] is False


def test_runbook_step_0_doctor_runs_on_a_stdlib_only_python():
    """CHROMEBOOK_FIRST_MISSION.md step 0 runs ``python3 -m greg doctor --chromebook`` with the system python3, before
    install.sh has installed any dependency. -S drops site-packages, so only the standard library is importable."""
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path
    repo = Path(__file__).resolve().parents[2]
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME")}
    stdlib_only = [sys.executable, "-S", "-B", "-m", "greg"]
    control = subprocess.run(stdlib_only + ["status"], cwd=repo, env=env, capture_output=True, text=True, timeout=60)
    assert control.returncode != 0 and "ModuleNotFoundError" in control.stderr   # the deps really are unimportable
    for argv in (["doctor", "--chromebook"], ["--home", "/nonexistent-greg-home", "doctor", "--chromebook"]):
        run = subprocess.run(stdlib_only + argv, cwd=repo, env=env, capture_output=True, text=True, timeout=120)
        assert run.returncode in (0, 2), run.stderr
        assert "Traceback" not in run.stderr
        report = json.loads(run.stdout)
        assert report["ready_for_linux_service"] is (run.returncode == 0) and "missing" in report
